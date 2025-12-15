#!/usr/bin/env python3
"""
Standalone diagnostic script for Chameleon MCP Server.

This script registers a test_connection tool that allows the LLM to self-diagnose
database connectivity issues across different database environments (SQLite, PostgreSQL,
Teradata, Oracle, etc.).

Usage:
    python add_db_test_tool.py
"""

from common.utils import compute_hash
import sys
from sqlmodel import Session, select

from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables




def register_db_test_tool(database_url: str = None):
    """
    Register the test_connection tool in the database.
    
    This tool performs a heartbeat query to verify database connectivity
    and returns diagnostic information about the database connection.
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
    """
    print("=" * 60)
    print("Database Connection Test Tool Registration")
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
from sqlalchemy import text

class ConnectionTestTool(ChameleonTool):
    def run(self, arguments):
        '''
        Test database connectivity and return diagnostic information.
        '''
        result = {
            'status': 'Unknown',
            'driver': None,
            'dialect': None,
            'database': None,
            'host': None,
            'error': None
        }
        
        try:
            # Get engine information from the session
            engine = self.db_session.get_bind()
            
            # Extract connection details
            result['dialect'] = engine.dialect.name
            result['driver'] = engine.driver
            
            # Get database and host from URL
            if hasattr(engine.url, 'database'):
                result['database'] = engine.url.database
            if hasattr(engine.url, 'host'):
                result['host'] = engine.url.host
            
            # Determine appropriate heartbeat query based on dialect
            if result['dialect'] == 'oracle':
                heartbeat_query = "SELECT 1 FROM DUAL"
            else:
                # Works for PostgreSQL, MySQL, SQLite, Teradata, etc.
                heartbeat_query = "SELECT 1"
            
            # Execute heartbeat query
            self.log(f"Executing heartbeat query: {heartbeat_query}")
            query_result = self.db_session.exec(text(heartbeat_query)).first()
            
            if query_result:
                result['status'] = 'Success'
                result['heartbeat_result'] = str(query_result[0])
                self.log("Database connection test successful")
            else:
                result['status'] = 'Error'
                result['error'] = 'Heartbeat query returned no results'
                
        except Exception as e:
            result['status'] = 'Error'
            result['error'] = f"{type(e).__name__}: {str(e)}"
            self.log(f"Database connection test failed: {result['error']}")
        
        # Format the result as a readable string
        output_lines = [
            f"Database Connection Test Results:",
            f"  Status: {result['status']}",
            f"  Dialect: {result['dialect'] or 'Unknown'}",
            f"  Driver: {result['driver'] or 'Unknown'}",
            f"  Database: {result['database'] or 'N/A'}",
            f"  Host: {result['host'] or 'N/A'}"
        ]
        
        if result['status'] == 'Success':
            output_lines.append(f"  Heartbeat Result: {result.get('heartbeat_result', 'N/A')}")
        else:
            output_lines.append(f"  Error: {result['error']}")
        
        return '\\n'.join(output_lines)
"""
    
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
                ToolRegistry.tool_name == 'test_connection',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = "Test database connectivity and return diagnostic information"
                existing_tool.input_schema = {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Tool 'test_connection' updated")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name='test_connection',
                    target_persona='default',
                    description="Test database connectivity and return diagnostic information",
                    input_schema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    },
                    active_hash_ref=tool_hash
                )
                session.add(tool)
                print(f"   ✅ Tool 'test_connection' created")
            
            # Commit changes
            session.commit()
            
            print("\n" + "=" * 60)
            print("✅ Database test tool registered successfully!")
            print("=" * 60)
            print("\nYou can now use the 'test_connection' tool to diagnose")
            print("database connectivity issues in the Chameleon MCP Server.")
            print("\nExample usage (via MCP client):")
            print("  Tool: test_connection")
            print("  Arguments: {}")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register tool: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    success = register_db_test_tool()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
