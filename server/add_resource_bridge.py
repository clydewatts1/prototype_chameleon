#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

"""
Script to add the read_resource tool to support clients that don't implement MCP Resources.

This tool enables clients (like Gemini CLI) that only support Tools to fetch data
from the ResourceRegistry manually by calling the read_resource tool.
"""

from common.hash_utils import compute_hash
from sqlmodel import Session, select

from config import load_config
from models import CodeVault, ToolRegistry, ResourceRegistry, get_engine, create_db_and_tables




def register_resource_bridge_tool(database_url: str = None):
    """
    Register the read_resource tool in the database.
    
    This tool allows clients that only support Tools (not Resources) to manually
    fetch resource data from the ResourceRegistry.
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
    """
    print("=" * 60)
    print("Resource Bridge Tool Registration")
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
    
    # Load the tool code from file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tool_code_path = os.path.join(script_dir, '..', 'tools', 'system', 'resource_bridge.py')
    with open(tool_code_path, 'r') as f:
        tool_code = f.read()
    
    
    tool_hash = compute_hash(tool_code)
    
    try:
        with Session(engine) as session:
            # Upsert code into CodeVault
            print("\n📝 Registering tool code in CodeVault...")
            statement = select(CodeVault).where(CodeVault.hash == tool_hash)
            existing_code = session.exec(statement).first()
            
            if existing_code:
                print(f"   ℹ️  Code already exists (hash: {tool_hash[:16]}...)")
            else:
                code_vault = CodeVault(
                    hash=tool_hash,
                    code_blob=tool_code,
                    code_type="python"
                )
                session.add(code_vault)
                print(f"   ✅ Code registered (hash: {tool_hash[:16]}...)")
            
            # Upsert tool in ToolRegistry
            print("\n🔧 Registering tool in ToolRegistry...")
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'read_resource',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = "Read a resource by URI from the ResourceRegistry. Allows clients that only support Tools to fetch resource data manually."
                existing_tool.input_schema = {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "The URI of the resource to read (e.g., 'memo://welcome')"
                        }
                    },
                    "required": ["uri"]
                }
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Tool 'read_resource' updated")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name='read_resource',
                    target_persona='default',
                    description="Read a resource by URI from the ResourceRegistry. Allows clients that only support Tools to fetch resource data manually.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "uri": {
                                "type": "string",
                                "description": "The URI of the resource to read (e.g., 'memo://welcome')"
                            }
                        },
                        "required": ["uri"]
                    },
                    active_hash_ref=tool_hash
                )
                session.add(tool)
                print(f"   ✅ Tool 'read_resource' created")
            
            # Commit changes
            session.commit()
            
            print("\n" + "=" * 60)
            print("✅ Resource Bridge tool registered successfully!")
            print("=" * 60)
            print("\nYou can now use the 'read_resource' tool to fetch resources")
            print("from clients that only support Tools (like Gemini CLI).")
            print("\nExample usage (via MCP client):")
            print("  Tool: read_resource")
            print('  Arguments: {"uri": "memo://welcome"}')
            
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register tool: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    success = register_resource_bridge_tool()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
