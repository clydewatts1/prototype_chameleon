#!/usr/bin/env python3
"""
Bootstrap script for registering a SQL Creator Meta-Tool.

This meta-tool allows the LLM to dynamically create new SQL-based tools
while enforcing security constraints (SELECT-only queries).

Usage:
    python add_sql_creator_tool.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.utils import compute_hash
from sqlmodel import Session, select
from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables




def register_sql_creator_tool(database_url: str = None):
    """
    Register the create_new_sql_tool meta-tool in the database.
    
    This meta-tool enables the LLM to create new SQL-based tools dynamically
    with security validation (SELECT-only queries, no semicolons).
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
    """
    print("=" * 60)
    print("SQL Creator Meta-Tool Registration")
    print("=" * 60)
    
    # Load configuration if database_url not provided
    if database_url is None:
        config = load_config()
        database_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon.db')
    print(f"\nDatabase URL: {database_url}")
    
    # Create engine and tables
    try:
        engine = get_engine(database_url)
        create_db_and_tables(engine)
        print("✅ Database engine created successfully")
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        return False
    
    # Load the meta-tool code from file
    tool_code_path = "../tools/system/sql_creator.py"
    try:
        with open(tool_code_path, 'r') as f:
            tool_code = f.read()
    except FileNotFoundError:
        # Fallback to relative path from server directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tool_code_path = os.path.join(script_dir, "..", "tools", "system", "sql_creator.py")
        try:
            with open(tool_code_path, 'r') as f:
                tool_code = f.read()
        except FileNotFoundError:
            print(f"❌ Could not find tool code at {tool_code_path}")
            return False
    
    tool_hash = compute_hash(tool_code)
    
    try:
        with Session(engine) as session:
            # Upsert code into CodeVault
            print("\n📝 Registering meta-tool code in CodeVault...")
            statement = select(CodeVault).where(CodeVault.hash == tool_hash)
            existing_code = session.exec(statement).first()
            
            if existing_code:
                print(f"   ℹ️  Code already exists (hash: {tool_hash[:16]}...)")
            else:
                code_vault = CodeVault(
                    hash=tool_hash,
                    code_blob=tool_code,
                    code_type="python"  # Meta-tool is Python since it needs logic
                )
                session.add(code_vault)
                print(f"   ✅ Code registered (hash: {tool_hash[:16]}...)")
            
            # Upsert tool in ToolRegistry
            print("\n🔧 Registering meta-tool in ToolRegistry...")
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'create_new_sql_tool',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            # Define input schema for the meta-tool
            input_schema = {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to create (e.g., 'get_high_value_customers')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of what the tool does"
                    },
                    "sql_query": {
                        "type": "string",
                        "description": "The SQL SELECT statement (must start with SELECT)"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Dictionary describing the parameters for the input schema. Format: {param_name: {type: 'string', description: '...', required: true/false}}"
                    }
                },
                "required": ["tool_name", "description", "sql_query"]
            }
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = "Create a new SQL-based tool with security validation (SELECT-only queries)"
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Meta-tool 'create_new_sql_tool' updated")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name='create_new_sql_tool',
                    target_persona='default',
                    description="Create a new SQL-based tool with security validation (SELECT-only queries)",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash
                )
                session.add(tool)
                print(f"   ✅ Meta-tool 'create_new_sql_tool' created")
            
            # Commit changes
            session.commit()
            
            print("\n" + "=" * 60)
            print("✅ SQL Creator Meta-Tool registered successfully!")
            print("=" * 60)
            print("\nThe LLM can now create new SQL-based tools dynamically!")
            print("\nExample usage (via MCP client):")
            print("  Tool: create_new_sql_tool")
            print("  Arguments: {")
            print('    "tool_name": "get_recent_orders",')
            print('    "description": "Get recent orders from the last N days",')
            print('    "sql_query": "SELECT * FROM orders WHERE order_date >= :start_date",')
            print('    "parameters": {')
            print('      "start_date": {')
            print('        "type": "string",')
            print('        "description": "Start date in YYYY-MM-DD format",')
            print('        "required": true')
            print('      }')
            print('    }')
            print("  }")
            print("\n🔒 Security Features:")
            print("  - Only SELECT statements are allowed")
            print("  - No semicolons in the middle of queries (prevents chaining)")
            print("  - All SQL tools are registered with code_type='select'")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register meta-tool: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    success = register_sql_creator_tool()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
