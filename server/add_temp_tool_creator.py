#!/usr/bin/env python3
"""
Bootstrap script for registering the Temporary Test Tool Creator.

This meta-tool allows the LLM to dynamically create temporary SQL-based tools
for testing and debugging purposes. These tools:
- Are not persisted to the database
- Have automatic LIMIT 3 constraint
- Are SELECT-only
- Exist only during runtime

Usage:
    python add_temp_tool_creator.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.hash_utils import compute_hash
from sqlmodel import Session, select
from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables


def register_temp_tool_creator(database_url: str = None):
    """
    Register the create_temp_test_tool meta-tool in the database.
    
    This meta-tool enables the LLM to create temporary SQL-based tools for testing
    with automatic LIMIT 3 constraint and no database persistence.
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
    """
    print("=" * 60)
    print("Temporary Test Tool Creator Registration")
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
    
    # Load the meta-tool code from file using robust path resolution
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tool_code_path = os.path.join(script_dir, "..", "tools", "system", "test_tool_creator.py")
    
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
                ToolRegistry.tool_name == 'create_temp_test_tool',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            # Define input schema for the meta-tool
            input_schema = {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the temporary test tool (e.g., 'test_sales')"
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
                existing_tool.description = "Create a temporary SQL-based test tool (not persisted, auto LIMIT 3)"
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Meta-tool 'create_temp_test_tool' updated")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name='create_temp_test_tool',
                    target_persona='default',
                    description="Create a temporary SQL-based test tool (not persisted, auto LIMIT 3)",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash,
                    group='system'
                )
                session.add(tool)
                print(f"   ✅ Meta-tool 'create_temp_test_tool' created")
            
            # Commit changes
            session.commit()
            
            print("\n" + "=" * 60)
            print("✅ Temporary Test Tool Creator registered successfully!")
            print("=" * 60)
            print("\nThe LLM can now create temporary SQL-based test tools!")
            print("\nExample usage (via MCP client):")
            print("  Tool: create_temp_test_tool")
            print("  Arguments: {")
            print('    "tool_name": "test_sales",')
            print('    "description": "Test query for sales data",')
            print('    "sql_query": "SELECT * FROM sales_per_day WHERE store_name = :store_name",')
            print('    "parameters": {')
            print('      "store_name": {')
            print('        "type": "string",')
            print('        "description": "Store name to filter by",')
            print('        "required": true')
            print('      }')
            print('    }')
            print("  }")
            print("\n🔒 Security & Testing Features:")
            print("  - Only SELECT statements are allowed")
            print("  - No semicolons in the middle of queries (prevents chaining)")
            print("  - Automatic LIMIT 3 constraint (max 3 rows returned)")
            print("  - NOT persisted to database (temporary only)")
            print("  - Perfect for testing and debugging queries")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register meta-tool: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    success = register_temp_tool_creator()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
