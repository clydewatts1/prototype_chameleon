#!/usr/bin/env python3
"""
Bootstrap script for registering the Temporary Resource Creator.

This meta-tool allows the LLM to dynamically create temporary resources
for testing and debugging purposes. These resources:
- Are not persisted to the database
- Can be static (text content) or dynamic (executable code)
- Exist only during runtime
- Support persona-based filtering

Usage:
    python add_temp_resource_creator.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.hash_utils import compute_hash
from sqlmodel import Session, select
from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables


def register_temp_resource_creator(database_url: str = None):
    """
    Register the create_temp_resource meta-tool in the database.
    
    This meta-tool enables the LLM to create temporary resources for testing
    with no database persistence.
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
    """
    print("=" * 60)
    print("Temporary Resource Creator Registration")
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
    tool_code_path = os.path.join(script_dir, "..", "tools", "system", "temp_resource_creator.py")
    
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
                ToolRegistry.tool_name == 'create_temp_resource',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            # Define input schema for the meta-tool
            input_schema = {
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "URI of the resource (e.g., 'memo://test', 'data://sample')"
                    },
                    "name": {
                        "type": "string",
                        "description": "Human-readable name of the resource"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of what the resource provides"
                    },
                    "content": {
                        "type": "string",
                        "description": "The static content (for static resources) or code (for dynamic resources)"
                    },
                    "is_dynamic": {
                        "type": "boolean",
                        "description": "True for code-based resources, False for static text (default: False)"
                    },
                    "mime_type": {
                        "type": "string",
                        "description": "MIME type of the content (default: 'text/plain')"
                    }
                },
                "required": ["uri", "name", "description", "content"]
            }
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = "Create a temporary resource (not persisted, static or dynamic)"
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Meta-tool 'create_temp_resource' updated")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name='create_temp_resource',
                    target_persona='default',
                    description="Create a temporary resource (not persisted, static or dynamic)",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash
                )
                session.add(tool)
                print(f"   ✅ Meta-tool 'create_temp_resource' created")
            
            # Commit changes
            session.commit()
            
            print("\n" + "=" * 60)
            print("✅ Temporary Resource Creator registered successfully!")
            print("=" * 60)
            print("\nThe LLM can now create temporary resources!")
            print("\nExample usage (via MCP client):")
            print("  Tool: create_temp_resource")
            print("  Arguments: {")
            print('    "uri": "memo://test",')
            print('    "name": "Test Memo",')
            print('    "description": "A test memo resource",')
            print('    "content": "This is a test memo content",')
            print('    "is_dynamic": false,')
            print('    "mime_type": "text/plain"')
            print("  }")
            print("\n🔒 Features:")
            print("  - Static resources store text content directly")
            print("  - Dynamic resources execute code when accessed")
            print("  - NOT persisted to database (temporary only)")
            print("  - Perfect for testing and debugging resources")
            print("  - Supports persona-based filtering")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register meta-tool: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    success = register_temp_resource_creator()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
