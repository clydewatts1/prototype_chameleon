#!/usr/bin/env python3
"""
Bootstrap script for registering the Dashboard Builder Meta-Tool.

This meta-tool allows the LLM to dynamically create Streamlit dashboards
and host them as interactive UIs.

Usage:
    python add_ui_tool.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.utils import compute_hash
from sqlmodel import Session, select
from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables


def register_ui_creator_tool(database_url: str = None):
    """
    Register the create_dashboard meta-tool in the database.
    
    This meta-tool enables the LLM to create Streamlit dashboards dynamically
    with validation (must import streamlit, sanitized names).
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
    """
    print("=" * 60)
    print("Dashboard Builder Meta-Tool Registration")
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
    tool_code_path = "../tools/system/ui_creator.py"
    try:
        with open(tool_code_path, 'r') as f:
            tool_code = f.read()
    except FileNotFoundError:
        # Fallback to relative path from server directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tool_code_path = os.path.join(script_dir, "..", "tools", "system", "ui_creator.py")
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
                    code_type="python"  # Meta-tool is Python
                )
                session.add(code_vault)
                print(f"   ✅ Code registered (hash: {tool_hash[:16]}...)")
            
            # Upsert tool in ToolRegistry
            print("\n🔧 Registering meta-tool in ToolRegistry...")
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'create_dashboard',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            # Define input schema for the meta-tool
            input_schema = {
                "type": "object",
                "properties": {
                    "dashboard_name": {
                        "type": "string",
                        "description": "Name of the dashboard (alphanumeric, underscore, or dash only, e.g., 'sales_dashboard')"
                    },
                    "python_code": {
                        "type": "string",
                        "description": "The Python code for the Streamlit dashboard (must import streamlit)"
                    }
                },
                "required": ["dashboard_name", "python_code"]
            }
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = "Create a new Streamlit dashboard with validation"
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Meta-tool 'create_dashboard' updated")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name='create_dashboard',
                    target_persona='default',
                    description="Create a new Streamlit dashboard with validation",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash
                )
                session.add(tool)
                print(f"   ✅ Meta-tool 'create_dashboard' created")
            
            # Commit changes
            session.commit()
            
            print("\n" + "=" * 60)
            print("✅ Dashboard Builder Meta-Tool registered successfully!")
            print("=" * 60)
            print("\nThe LLM can now create Streamlit dashboards dynamically!")
            print("\nExample usage (via MCP client):")
            print("  Tool: create_dashboard")
            print("  Arguments: {")
            print('    "dashboard_name": "my_dashboard",')
            print('    "python_code": "import streamlit as st\\nst.title(\'Hello World\')\\nst.write(\'Welcome!\')"')
            print("  }")
            print("\n🔒 Security Features:")
            print("  - Dashboard code must import streamlit")
            print("  - Dashboard names are sanitized (alphanumeric, underscore, dash only)")
            print("  - Code is saved both to database and physical file")
            print("  - Feature can be disabled via config (features.chameleon_ui.enabled)")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register meta-tool: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    success = register_ui_creator_tool()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
