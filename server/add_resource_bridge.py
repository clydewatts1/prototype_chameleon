#!/usr/bin/env python3
"""
Script to add the read_resource tool to support clients that don't implement MCP Resources.

This tool enables clients (like Gemini CLI) that only support Tools to fetch data
from the ResourceRegistry manually by calling the read_resource tool.
"""

import hashlib
import sys
from sqlmodel import Session, select

from config import load_config
from models import CodeVault, ToolRegistry, ResourceRegistry, get_engine, create_db_and_tables


def _compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


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
        database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    print(f"\nDatabase URL: {database_url}")
    
    # Create engine and tables
    try:
        engine = get_engine(database_url)
        create_db_and_tables(engine)
        print("✅ Database engine created successfully")
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        return False
    
    # Define the tool code blob
    tool_code = """from base import ChameleonTool
from runtime import get_resource, ResourceNotFoundError
from sqlmodel import select
from models import ResourceRegistry

class ReadResourceTool(ChameleonTool):
    def run(self, arguments):
        '''
        Read a resource by URI from the ResourceRegistry.
        
        This tool enables clients that only support Tools (not Resources)
        to fetch resource data manually.
        '''
        uri = arguments.get('uri')
        
        if not uri:
            return "Error: 'uri' parameter is required"
        
        # Get persona from context, default to 'default'
        persona = self.context.get('persona', 'default')
        
        try:
            # Call get_resource to fetch the resource
            result = get_resource(uri, persona, self.db_session)
            return result
        except ResourceNotFoundError as e:
            # Query ResourceRegistry for available URIs to help self-correction
            statement = select(ResourceRegistry).where(
                ResourceRegistry.target_persona == persona
            )
            available_resources = self.db_session.exec(statement).all()
            
            if available_resources:
                available_uris = [r.uri_schema for r in available_resources]
                uris_list = '\\n  - '.join(available_uris)
                return f"Resource not found: {uri}\\n\\nAvailable resources are:\\n  - {uris_list}"
            else:
                return f"Resource not found: {uri}\\n\\nNo resources available for persona '{persona}'"
"""
    
    tool_hash = _compute_hash(tool_code)
    
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
