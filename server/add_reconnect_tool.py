import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

"""
Script to add the 'reconnect_db' system tool for reconnecting to the data database at runtime.

This tool allows the server to attempt reconnection to the data database if it was initially
unavailable or disconnected.
"""

from common.hash_utils import compute_hash
from sqlmodel import Session, select
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables, METADATA_MODELS
from config import load_config




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
import time
import random

class ReconnectDbTool(ChameleonTool):
    def run(self, arguments):
        \"\"\"
        Attempt to reconnect to the data database with exponential back-off.
        
        This tool tries to re-initialize the data_engine using the configuration.
        If successful, it updates the global server state.
        It uses an exponential back-off strategy:
        - Max 5 attempts
        - Base delay 1s
        - Jitter +/- 0.5s
        \"\"\"
        # Import necessary modules
        from config import load_config
        from models import get_engine, create_db_and_tables, DATA_MODELS
        import server
        
        # Load config to get data database URL
        config = load_config()
        # Ensure we have the latest config if it changed
        data_db_url = config.get('data_database', {}).get('url', 'sqlite:///chameleon_data.db')
        
        max_attempts = 5
        base_delay = 1.0
        
        last_error = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                logging.info(f"Connection attempt {attempt}/{max_attempts} to {data_db_url}")
                
                # Create engine - this usually doesn't fail until we try to use it, 
                # but create_db_and_tables will try to use it.
                data_engine = get_engine(data_db_url)
                
                # Test connection by creating tables (idempotent)
                create_db_and_tables(data_engine, DATA_MODELS)
                
                # If we get here, connection is successful
                
                # Update global server state
                server._data_engine = data_engine
                server._data_db_connected = True
                
                # Update app instance state if available
                if hasattr(server, 'app'):
                    server.app._data_engine = data_engine
                    server.app._data_db_connected = True
                
                success_msg = f"Successfully reconnected to business database at {data_db_url} on attempt {attempt}"
                logging.info(success_msg)
                return success_msg
                
            except Exception as e:
                last_error = e
                logging.warning(f"Attempt {attempt} failed: {e}")
                
                if attempt < max_attempts:
                    # Exponential back-off with jitter
                    delay = (base_delay * (2 ** (attempt - 1))) + random.uniform(-0.5, 0.5)
                    delay = max(0.1, delay) # Ensure positive delay
                    logging.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
        
        # If loop finishes without success
        error_msg = f"Failed to reconnect to business database after {max_attempts} attempts. Last error: {str(last_error)}"
        logging.error(error_msg)
        return error_msg
"""
        reconnect_hash = compute_hash(reconnect_code)
        
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
