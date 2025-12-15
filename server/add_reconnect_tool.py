"""
Script to add the 'reconnect_db' system tool for reconnecting to the data database at runtime.

This tool allows the server to attempt reconnection to the data database if it was initially
unavailable or disconnected.
"""

import hashlib
from sqlmodel import Session, select
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables, METADATA_MODELS
from config import load_config


def _compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def add_reconnect_tool(metadata_database_url: str = None):
    """
    Add the 'reconnect_db' system tool to the metadata database.
    
    Args:
        metadata_database_url: Database connection string for metadata DB.
                              If None, loads from config.
    """
    # Load configuration if metadata_database_url not provided
    if metadata_database_url is None:
        config = load_config()
        metadata_database_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon_meta.db')
    
    # Create engine and tables
    engine = get_engine(metadata_database_url)
    create_db_and_tables(engine, METADATA_MODELS)
    
    print("=" * 60)
    print("Adding 'reconnect_db' System Tool")
    print("=" * 60)
    
    with Session(engine) as session:
        # Define the reconnect_db tool code
        reconnect_code = """from base import ChameleonTool
import logging

class ReconnectDbTool(ChameleonTool):
    def run(self, arguments):
        \"\"\"
        Attempt to reconnect to the data database.
        
        This tool tries to re-initialize the data_engine using the configuration.
        If successful, it updates the global server._data_engine.
        \"\"\"
        try:
            # Import necessary modules
            from config import load_config
            from models import get_engine, create_db_and_tables, DATA_MODELS
            
            # Load config to get data database URL
            config = load_config()
            data_db_url = config.get('data_database', {}).get('url', 'sqlite:///chameleon_data.db')
            
            # Attempt to create engine and tables
            logging.info(f"Attempting to connect to data database: {data_db_url}")
            data_engine = get_engine(data_db_url)
            create_db_and_tables(data_engine, DATA_MODELS)
            
            # Update global server state
            import server
            server._data_engine = data_engine
            server._data_db_connected = True
            server.app._data_engine = data_engine
            server.app._data_db_connected = True
            
            logging.info("Data database reconnected successfully")
            return f"Successfully reconnected to business database at {data_db_url}"
            
        except Exception as e:
            logging.error(f"Failed to reconnect to data database: {e}")
            return f"Failed to reconnect to business database: {str(e)}"
"""
        reconnect_hash = _compute_hash(reconnect_code)
        
        # Check if tool already exists
        existing_vault = session.exec(
            select(CodeVault).where(CodeVault.hash == reconnect_hash)
        ).first()
        
        if not existing_vault:
            print("\n[1] Adding code to CodeVault...")
            reconnect_vault = CodeVault(
                hash=reconnect_hash,
                code_blob=reconnect_code,
                code_type="python"
            )
            session.add(reconnect_vault)
            print(f"   ✅ Code added (hash: {reconnect_hash[:16]}...)")
        else:
            print(f"\n[1] Code already exists in CodeVault (hash: {reconnect_hash[:16]}...)")
        
        # Check if tool already exists
        existing_tool = session.exec(
            select(ToolRegistry).where(
                ToolRegistry.tool_name == "reconnect_db",
                ToolRegistry.target_persona == "default"
            )
        ).first()
        
        if not existing_tool:
            print("\n[2] Registering 'reconnect_db' tool...")
            reconnect_tool = ToolRegistry(
                tool_name="reconnect_db",
                target_persona="default",
                description="Reconnect to the business data database. Use this tool if data queries fail due to offline database.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                active_hash_ref=reconnect_hash,
                is_auto_created=False
            )
            session.add(reconnect_tool)
            print(f"   ✅ Tool 'reconnect_db' registered")
        else:
            # Update existing tool to point to new code
            print("\n[2] Updating existing 'reconnect_db' tool...")
            existing_tool.active_hash_ref = reconnect_hash
            existing_tool.description = "Reconnect to the business data database. Use this tool if data queries fail due to offline database."
            session.add(existing_tool)
            print(f"   ✅ Tool 'reconnect_db' updated")
        
        # Commit changes
        session.commit()
        
        print("\n" + "=" * 60)
        print("'reconnect_db' Tool Added Successfully!")
        print("=" * 60)
        print("\nThis tool can be used to reconnect to the data database")
        print("at runtime if it was initially unavailable or disconnected.")


if __name__ == "__main__":
    add_reconnect_tool()
