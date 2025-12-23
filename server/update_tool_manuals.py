#!/usr/bin/env python3
"""
Script to populate extended_metadata (manuals) for core tools.
This ensures they can be verified by system_verify_tool.
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from sqlmodel import Session, select
from config import load_config
from models import ToolRegistry, get_engine

def update_manuals(database_url: str = None):
    print("=" * 60)
    print("Updating Tool Manuals")
    print("=" * 60)
    
    if database_url is None:
        config = load_config()
        database_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon.db')
    
    # Force use of root DB if default fails or for consistent testing
    if 'server' in database_url and not os.path.exists(database_url.replace('sqlite:///', '')):
         # Fallback to root if server/db doesn't exist
         database_url = 'sqlite:///chameleon_meta.db'

    print(f"Database URL: {database_url}")
    
    engine = get_engine(database_url)
    
    with Session(engine) as session:
        # 1. utility_greet
        greet = session.exec(select(ToolRegistry).where(
            ToolRegistry.tool_name == 'utility_greet', 
            ToolRegistry.target_persona == 'default'
        )).first()
        
        if greet:
            print("Updating utility_greet manual...")
            manual = {
                "usage_guide": "Use this tool to greet a user. Useful for testing basic connectivity.",
                "examples": [
                    {
                        "input": {"name": "World"},
                        "expected_output_summary": "Hello World",
                        "verified": False
                    }
                ],
                "pitfalls": ["Name argument is required."]
            }
            greet.extended_metadata = manual
            session.add(greet)
        else:
            print("❌ utility_greet not found!")

        # 2. general_merge_tool (Data Upsert)
        merge = session.exec(select(ToolRegistry).where(
            ToolRegistry.tool_name == 'general_merge_tool', 
            ToolRegistry.target_persona == 'default'
        )).first()
        
        if merge:
            print("Updating general_merge_tool manual...")
            # Note: This test requires a valid table. We use a likely existing one or fail safely.
            # Ideally verification creates a temp table, but merge tool works on existing tables.
            # We will use 'sales_per_day' if seeded, or just document it.
            # For verification safety, we might need a dedicated test table resource but for now:
            manual = {
                "usage_guide": "Upserts data into any SQL table. supports SQLite, Postgres, etc.",
                "examples": [
                    {
                        "input": {
                            "table_name": "sales_per_day",
                            "key_column": "id",
                            "key_value": "9999", 
                            "data": json.dumps({
                                "business_date": "2024-01-01", 
                                "store_name": "Test Store", 
                                "sales_amount": 100
                            })
                        },
                        "expected_output_summary": "Successfully upserted",
                        "verified": False
                    }
                ],
                "pitfalls": ["Data must be valid JSON string", "Table must exist"]
            }
            merge.extended_metadata = manual
            session.add(merge)
        else:
            print("⚠️ general_merge_tool not found")

        # 3. execute_ddl_tool (Requires confirmation)
        ddl = session.exec(select(ToolRegistry).where(
            ToolRegistry.tool_name == 'execute_ddl_tool', 
            ToolRegistry.target_persona == 'default'
        )).first()
        
        if ddl:
            print("Updating execute_ddl_tool manual...")
            # DDL is dangerous to verify automatically unless we create temp tables.
            # We'll create a benign table
            manual = {
                "usage_guide": "Execute CREATE/ALTER/DROP statements. MUST use confirmation='YES'.",
                "examples": [
                    {
                        "input": {
                            "ddl_command": "CREATE TABLE IF NOT EXISTS verification_test (id INTEGER PRIMARY KEY)",
                            "confirmation": "YES"
                        },
                        "expected_output_summary": "Successfully executed",
                        "verified": False
                    }
                ],
                "pitfalls": ["Only single statements allowed", "Requires confirmation"]
            }
            ddl.extended_metadata = manual
            session.add(ddl)
        else:
             print("⚠️ execute_ddl_tool not found")

        session.commit()
        print("✅ Manuals updated successfully.")

if __name__ == '__main__':
    update_manuals()
