#!/usr/bin/env python3
"""
Bootstrap script for registering Advanced Data Tools (MERGE and DDL).

This script registers two advanced database tools:
1. general_merge_tool - Upsert data (Insert or Update) with dialect-specific SQL
2. execute_ddl_tool - Execute DDL commands (CREATE, ALTER, DROP) with safety checks

Usage:
    python add_advanced_tools.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.hash_utils import compute_hash
from sqlmodel import Session, select
from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables


def register_general_merge_tool(session, config):
    """
    Register the general_merge_tool in the database.
    
    This tool performs upsert operations (Insert or Update) based on a key,
    using dialect-specific SQL templates for SQLite, PostgreSQL, and standard SQL.
    """
    print("\n" + "=" * 60)
    print("Registering general_merge_tool")
    print("=" * 60)
    
    # Define the tool code blob
    tool_code = """from base import ChameleonTool
from sqlalchemy import text
from jinja2 import Template
import json

class GeneralMergeTool(ChameleonTool):
    def run(self, arguments):
        '''
        Upsert data (Insert or Update) based on a key column.
        
        Uses dialect-specific SQL:
        - SQLite: INSERT OR REPLACE INTO
        - PostgreSQL: INSERT ... ON CONFLICT ... DO UPDATE
        - Standard (Teradata/Databricks): MERGE statement
        '''
        # Extract arguments
        table_name = arguments.get('table_name')
        key_column = arguments.get('key_column')
        key_value = arguments.get('key_value')
        data_json = arguments.get('data')
        
        if not all([table_name, key_column, key_value, data_json]):
            raise ValueError("Missing required arguments: table_name, key_column, key_value, data")
        
        # Check if data_session is available
        if self.data_session is None:
            raise RuntimeError(
                "Business database is currently offline. Use 'reconnect_db' tool to try again."
            )
        
        # Parse the data JSON string
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in 'data' argument: {e}")
        
        if not isinstance(data, dict):
            raise ValueError("'data' must be a JSON object (dictionary)")
        
        # Ensure key_column is in data
        data[key_column] = key_value
        
        # Get database dialect
        engine = self.data_session.get_bind()
        dialect = engine.dialect.name
        
        self.log(f"Detected database dialect: {dialect}")
        
        # Build dialect-specific SQL using Jinja2
        if dialect == 'sqlite':
            # SQLite: INSERT OR REPLACE INTO
            template_str = '''INSERT OR REPLACE INTO {{ table_name }} ({{ columns }})
VALUES ({{ placeholders }})'''
        elif dialect == 'postgresql':
            # PostgreSQL: INSERT ... ON CONFLICT ... DO UPDATE
            template_str = '''INSERT INTO {{ table_name }} ({{ columns }})
VALUES ({{ placeholders }})
ON CONFLICT ({{ key_column }}) DO UPDATE SET
{{ update_set }}'''
        else:
            # Standard SQL (Teradata/Databricks): MERGE statement
            template_str = '''MERGE INTO {{ table_name }} AS target
USING (SELECT {{ source_columns }}) AS source
ON target.{{ key_column }} = source.{{ key_column }}
WHEN MATCHED THEN
  UPDATE SET {{ update_set }}
WHEN NOT MATCHED THEN
  INSERT ({{ columns }}) VALUES ({{ source_values }})'''
        
        # Prepare template variables
        columns = ', '.join(data.keys())
        placeholders = ', '.join([f":{col}" for col in data.keys()])
        
        if dialect == 'postgresql':
            # For PostgreSQL, build UPDATE SET clause (excluding key_column)
            update_cols = [col for col in data.keys() if col != key_column]
            update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_cols])
        elif dialect != 'sqlite':
            # For standard SQL (MERGE), build UPDATE SET and source columns
            update_cols = [col for col in data.keys() if col != key_column]
            update_set = ', '.join([f"{col} = source.{col}" for col in update_cols])
            source_columns = ', '.join([f":{col} AS {col}" for col in data.keys()])
            source_values = ', '.join([f"source.{col}" for col in data.keys()])
        
        # Render the template
        template = Template(template_str)
        sql = template.render(
            table_name=table_name,
            key_column=key_column,
            columns=columns,
            placeholders=placeholders,
            update_set=update_set if dialect != 'sqlite' else '',
            source_columns=source_columns if dialect not in ['sqlite', 'postgresql'] else '',
            source_values=source_values if dialect not in ['sqlite', 'postgresql'] else ''
        )
        
        self.log(f"Executing SQL: {sql}")
        self.log(f"Parameters: {data}")
        
        # Execute the SQL
        try:
            self.data_session.exec(text(sql), params=data)
            self.data_session.commit()
            return f"Successfully upserted data into {table_name} (key: {key_column}={key_value})"
        except Exception as e:
            self.data_session.rollback()
            raise RuntimeError(f"Failed to execute merge: {e}")
"""
    
    tool_hash = compute_hash(tool_code)
    
    # Upsert code into CodeVault
    print("📝 Registering tool code in CodeVault...")
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
    print("🔧 Registering tool in ToolRegistry...")
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'general_merge_tool',
        ToolRegistry.target_persona == 'default'
    )
    existing_tool = session.exec(statement).first()
    
    input_schema = {
        "type": "object",
        "properties": {
            "table_name": {
                "type": "string",
                "description": "Name of the table to merge data into"
            },
            "key_column": {
                "type": "string",
                "description": "Name of the key column for matching (e.g., 'id')"
            },
            "key_value": {
                "type": "string",
                "description": "Value of the key to match/insert"
            },
            "data": {
                "type": "string",
                "description": "JSON string of columns to update/insert (e.g., '{\"name\": \"John\", \"age\": 30}')"
            }
        },
        "required": ["table_name", "key_column", "key_value", "data"]
    }
    
    if existing_tool:
        # Update existing tool
        existing_tool.description = "Upsert data (Insert or Update) based on a key column. Supports SQLite, PostgreSQL, and standard SQL dialects."
        existing_tool.input_schema = input_schema
        existing_tool.active_hash_ref = tool_hash
        session.add(existing_tool)
        print(f"   ✅ Tool 'general_merge_tool' updated")
    else:
        # Create new tool
        tool = ToolRegistry(
            tool_name='general_merge_tool',
            target_persona='default',
            description="Upsert data (Insert or Update) based on a key column. Supports SQLite, PostgreSQL, and standard SQL dialects.",
            input_schema=input_schema,
            active_hash_ref=tool_hash,
            group='data'
        )
        session.add(tool)
        print(f"   ✅ Tool 'general_merge_tool' created")
    
    return True


def register_execute_ddl_tool(session, config):
    """
    Register the execute_ddl_tool in the database.
    
    This tool executes DDL commands (CREATE, ALTER, DROP) with safety checks.
    """
    print("\n" + "=" * 60)
    print("Registering execute_ddl_tool")
    print("=" * 60)
    
    # Define the tool code blob
    tool_code = """from base import ChameleonTool
from sqlalchemy import text
import re
from common.security import SecurityError

class ExecuteDDLTool(ChameleonTool):
    def run(self, arguments):
        '''
        Execute DDL commands (CREATE, ALTER, DROP, TRUNCATE) with safety checks.
        
        Requires explicit confirmation to prevent accidental schema changes.
        '''
        # Extract arguments
        ddl_command = arguments.get('ddl_command')
        confirmation = arguments.get('confirmation')
        
        if not ddl_command:
            raise ValueError("Missing required argument: ddl_command")
        
        # Safety check: require explicit confirmation
        if confirmation != 'YES':
            raise ValueError(
                "DDL execution requires explicit confirmation. "
                "Set 'confirmation' parameter to 'YES' (all caps) to proceed."
            )
        
        # Check if data_session is available
        if self.data_session is None:
            raise RuntimeError(
                "Business database is currently offline. Use 'reconnect_db' tool to try again."
            )
        
        # Normalize SQL for validation
        sql_upper = ddl_command.strip().upper()
        
        # Remove SQL comments
        sql_cleaned = re.sub(r'--[^\\r\\n]*', '', sql_upper)
        sql_cleaned = re.sub(r'/\\*.*?\\*/', '', sql_cleaned, flags=re.DOTALL)
        sql_cleaned = sql_cleaned.strip()
        
        # Validate that it's a DDL command
        allowed_ddl_keywords = ['CREATE', 'ALTER', 'DROP', 'TRUNCATE']
        is_valid_ddl = any(sql_cleaned.startswith(keyword) for keyword in allowed_ddl_keywords)
        
        if not is_valid_ddl:
            raise ValueError(
                f"Invalid DDL command. Must start with one of: {', '.join(allowed_ddl_keywords)}"
            )
        
        # Additional security: prevent multiple statements
        sql_stripped = ddl_command.rstrip().rstrip(';').rstrip()
        if ';' in sql_stripped:
            raise SecurityError(
                "Multiple SQL statements detected. Only single DDL statements are allowed."
            )
        
        self.log(f"Executing DDL command: {ddl_command}")
        
        # Execute the DDL command
        try:
            self.data_session.exec(text(ddl_command))
            self.data_session.commit()
            return f"Successfully executed DDL command"
        except Exception as e:
            self.data_session.rollback()
            raise RuntimeError(f"Failed to execute DDL: {e}")
"""
    
    tool_hash = compute_hash(tool_code)
    
    # Upsert code into CodeVault
    print("📝 Registering tool code in CodeVault...")
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
    print("🔧 Registering tool in ToolRegistry...")
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'execute_ddl_tool',
        ToolRegistry.target_persona == 'default'
    )
    existing_tool = session.exec(statement).first()
    
    input_schema = {
        "type": "object",
        "properties": {
            "ddl_command": {
                "type": "string",
                "description": "DDL command to execute (CREATE, ALTER, DROP, TRUNCATE)"
            },
            "confirmation": {
                "type": "string",
                "description": "Must be 'YES' (all caps) to confirm execution"
            }
        },
        "required": ["ddl_command", "confirmation"]
    }
    
    if existing_tool:
        # Update existing tool
        existing_tool.description = "Execute DDL commands (CREATE, ALTER, DROP, TRUNCATE) with safety checks. Requires explicit confirmation."
        existing_tool.input_schema = input_schema
        existing_tool.active_hash_ref = tool_hash
        session.add(existing_tool)
        print(f"   ✅ Tool 'execute_ddl_tool' updated")
    else:
        # Create new tool
        tool = ToolRegistry(
            tool_name='execute_ddl_tool',
            target_persona='default',
            description="Execute DDL commands (CREATE, ALTER, DROP, TRUNCATE) with safety checks. Requires explicit confirmation.",
            input_schema=input_schema,
            active_hash_ref=tool_hash,
            group='data'
        )
        session.add(tool)
        print(f"   ✅ Tool 'execute_ddl_tool' created")
    
    return True


def main():
    """Main entry point."""
    print("=" * 60)
    print("Advanced Data Tools Registration")
    print("=" * 60)
    
    # Load configuration
    config = load_config()
    database_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon.db')
    print(f"\nMetadata Database URL: {database_url}")
    
    # Create engine and tables
    try:
        engine = get_engine(database_url)
        create_db_and_tables(engine)
        print("✅ Database engine created successfully")
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        return False
    
    try:
        with Session(engine) as session:
            # Register general_merge_tool
            if not register_general_merge_tool(session, config):
                return False
            
            # Register execute_ddl_tool
            if not register_execute_ddl_tool(session, config):
                return False
            
            # Commit all changes
            session.commit()
            
            print("\n" + "=" * 60)
            print("✅ Advanced Data Tools registered successfully!")
            print("=" * 60)
            print("\nRegistered tools:")
            print("  1. general_merge_tool - Upsert data with dialect-specific SQL")
            print("  2. execute_ddl_tool - Execute DDL commands with safety checks")
            print("\n📖 Example usage:")
            print("\nMERGE Tool:")
            print('  Tool: general_merge_tool')
            print('  Arguments: {')
            print('    "table_name": "sales_per_day",')
            print('    "key_column": "id",')
            print('    "key_value": "123",')
            print('    "data": "{\\"business_date\\": \\"2024-01-15\\", \\"store_name\\": \\"Store A\\", \\"sales_amount\\": 1500.00}"')
            print('  }')
            print("\nDDL Tool:")
            print('  Tool: execute_ddl_tool')
            print('  Arguments: {')
            print('    "ddl_command": "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)",')
            print('    "confirmation": "YES"')
            print('  }')
            
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register tools: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
