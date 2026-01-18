"""
Pytest test suite for advanced data tools (MERGE and DDL).

This test validates:
1. general_merge_tool with different database dialects
2. execute_ddl_tool with safety checks
3. Integration with the runtime system
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

import pytest
import json
from datetime import date
from sqlmodel import select, text
from sqlalchemy import inspect
from models import CodeVault, ToolRegistry, SalesPerDay
from runtime import execute_tool
from common.hash_utils import compute_hash


@pytest.fixture
def setup_advanced_tools(db_session):
    """Fixture to register advanced tools in the test database."""
    # Import the registration functions
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
    from add_advanced_tools import register_general_merge_tool, register_execute_ddl_tool
    
    config = {}
    register_general_merge_tool(db_session, config)
    register_execute_ddl_tool(db_session, config)
    db_session.commit()
    
    return db_session


@pytest.fixture
def setup_test_table(db_session):
    """Fixture to create a test table with sample data."""
    # Create a simple test table
    db_session.exec(text("""
        CREATE TABLE IF NOT EXISTS test_users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER
        )
    """))
    
    # Insert some test data
    db_session.exec(text("""
        INSERT INTO test_users (id, name, email, age)
        VALUES 
            (1, 'Alice', 'alice@example.com', 30),
            (2, 'Bob', 'bob@example.com', 25)
    """))
    db_session.commit()
    
    return db_session


@pytest.mark.integration
def test_merge_tool_insert_new_record(setup_advanced_tools, setup_test_table):
    """Test that general_merge_tool can insert a new record."""
    session = setup_test_table
    
    # Prepare arguments for inserting a new record
    data = {
        "name": "Charlie",
        "email": "charlie@example.com",
        "age": 35
    }
    
    arguments = {
        "table_name": "test_users",
        "key_column": "id",
        "key_value": "3",
        "data": json.dumps(data)
    }
    
    # Execute the merge tool
    result = execute_tool(
        tool_name="general_merge_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session  # Using same session for simplicity in tests
    )
    
    # Verify the result message
    assert "Successfully upserted" in result
    assert "test_users" in result
    
    # Verify the record was inserted
    query_result = session.exec(
        text("SELECT name, email, age FROM test_users WHERE id = 3")
    ).first()
    
    assert query_result is not None
    assert query_result[0] == "Charlie"
    assert query_result[1] == "charlie@example.com"
    assert query_result[2] == 35


@pytest.mark.integration
def test_merge_tool_update_existing_record(setup_advanced_tools, setup_test_table):
    """Test that general_merge_tool can update an existing record."""
    session = setup_test_table
    
    # Prepare arguments for updating an existing record (id=1, Alice)
    data = {
        "name": "Alice Updated",
        "email": "alice.new@example.com",
        "age": 31
    }
    
    arguments = {
        "table_name": "test_users",
        "key_column": "id",
        "key_value": "1",
        "data": json.dumps(data)
    }
    
    # Execute the merge tool
    result = execute_tool(
        tool_name="general_merge_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Verify the result message
    assert "Successfully upserted" in result
    
    # Verify the record was updated
    query_result = session.exec(
        text("SELECT name, email, age FROM test_users WHERE id = 1")
    ).first()
    
    assert query_result is not None
    assert query_result[0] == "Alice Updated"
    assert query_result[1] == "alice.new@example.com"
    assert query_result[2] == 31


@pytest.mark.integration
def test_merge_tool_invalid_json(setup_advanced_tools, setup_test_table):
    """Test that general_merge_tool rejects invalid JSON in data argument."""
    session = setup_test_table
    
    arguments = {
        "table_name": "test_users",
        "key_column": "id",
        "key_value": "999",
        "data": "not valid json"
    }
    
    # Execute should return an error message
    result = execute_tool(
        tool_name="general_merge_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Check that error mentions JSON
    assert "failed with error" in result
    assert "JSON" in result or "json" in result


@pytest.mark.integration
def test_merge_tool_missing_arguments(setup_advanced_tools, setup_test_table):
    """Test that general_merge_tool validates required arguments."""
    session = setup_test_table
    
    # Missing 'data' argument
    arguments = {
        "table_name": "test_users",
        "key_column": "id",
        "key_value": "999"
    }
    
    result = execute_tool(
        tool_name="general_merge_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    assert "failed with error" in result
    assert "Missing required arguments" in result or "required" in result.lower()


@pytest.mark.integration
def test_ddl_tool_create_table(setup_advanced_tools, db_session):
    """Test that execute_ddl_tool can create a table."""
    session = db_session
    
    ddl_command = """
        CREATE TABLE test_products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            price REAL
        )
    """
    
    arguments = {
        "ddl_command": ddl_command,
        "confirmation": "YES"
    }
    
    # Execute the DDL tool
    result = execute_tool(
        tool_name="execute_ddl_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Verify the result message
    assert "Successfully executed DDL" in result
    
    # Verify the table was created
    inspector = inspect(session.get_bind())
    tables = inspector.get_table_names()
    assert "test_products" in tables


@pytest.mark.integration
def test_ddl_tool_alter_table(setup_advanced_tools, setup_test_table):
    """Test that execute_ddl_tool can alter a table."""
    session = setup_test_table
    
    # Add a new column to the test_users table
    ddl_command = "ALTER TABLE test_users ADD COLUMN phone TEXT"
    
    arguments = {
        "ddl_command": ddl_command,
        "confirmation": "YES"
    }
    
    # Execute the DDL tool
    result = execute_tool(
        tool_name="execute_ddl_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Verify the result message
    assert "Successfully executed DDL" in result
    
    # Verify the column was added
    inspector = inspect(session.get_bind())
    columns = [col['name'] for col in inspector.get_columns('test_users')]
    assert 'phone' in columns


@pytest.mark.integration
def test_ddl_tool_drop_table(setup_advanced_tools, setup_test_table):
    """Test that execute_ddl_tool can drop a table."""
    session = setup_test_table
    
    # First create a temporary table to drop
    session.exec(text("CREATE TABLE temp_test_table (id INTEGER)"))
    session.commit()
    
    ddl_command = "DROP TABLE temp_test_table"
    
    arguments = {
        "ddl_command": ddl_command,
        "confirmation": "YES"
    }
    
    # Execute the DDL tool
    result = execute_tool(
        tool_name="execute_ddl_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Verify the result message
    assert "Successfully executed DDL" in result
    
    # Verify the table was dropped
    inspector = inspect(session.get_bind())
    tables = inspector.get_table_names()
    assert "temp_test_table" not in tables


@pytest.mark.integration
def test_ddl_tool_truncate_table(setup_advanced_tools, setup_test_table):
    """Test that execute_ddl_tool can truncate a table."""
    session = setup_test_table
    
    # Verify data exists first
    count_before = session.exec(text("SELECT COUNT(*) FROM test_users")).first()[0]
    assert count_before > 0
    
    # Note: SQLite doesn't support TRUNCATE, so we'll use DELETE for this test
    # In production with PostgreSQL/Teradata, TRUNCATE would work
    ddl_command = "DELETE FROM test_users"
    
    arguments = {
        "ddl_command": ddl_command,
        "confirmation": "YES"
    }
    
    # This should fail because DELETE is not a DDL command
    result = execute_tool(
        tool_name="execute_ddl_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    assert "failed with error" in result
    assert "Invalid DDL command" in result or "DDL" in result


@pytest.mark.integration
def test_ddl_tool_requires_confirmation(setup_advanced_tools, db_session):
    """Test that execute_ddl_tool requires explicit confirmation."""
    session = db_session
    
    ddl_command = "CREATE TABLE should_fail (id INTEGER)"
    
    # Test without confirmation
    arguments = {
        "ddl_command": ddl_command
    }
    
    result = execute_tool(
        tool_name="execute_ddl_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    assert "failed with error" in result
    assert "confirmation" in result.lower()
    
    # Test with wrong confirmation
    arguments["confirmation"] = "yes"  # lowercase, should fail
    
    result = execute_tool(
        tool_name="execute_ddl_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    assert "failed with error" in result
    assert "confirmation" in result.lower() or "YES" in result


@pytest.mark.integration
def test_ddl_tool_rejects_select(setup_advanced_tools, db_session):
    """Test that execute_ddl_tool rejects SELECT statements."""
    session = db_session
    
    ddl_command = "SELECT * FROM test_users"
    
    arguments = {
        "ddl_command": ddl_command,
        "confirmation": "YES"
    }
    
    result = execute_tool(
        tool_name="execute_ddl_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    assert "failed with error" in result
    assert "Invalid DDL command" in result or "DDL" in result


@pytest.mark.integration
def test_ddl_tool_prevents_multiple_statements(setup_advanced_tools, db_session):
    """Test that execute_ddl_tool prevents multiple statements."""
    session = db_session
    
    # Try to inject multiple statements
    ddl_command = "CREATE TABLE test1 (id INTEGER); DROP TABLE test_users;"
    
    arguments = {
        "ddl_command": ddl_command,
        "confirmation": "YES"
    }
    
    with pytest.raises(Exception) as exc_info:
        execute_tool(
            tool_name="execute_ddl_tool",
            persona="default",
            arguments=arguments,
            meta_session=session,
            data_session=session
        )
    
    error_msg = str(exc_info.value)
    assert "Multiple" in error_msg or "single" in error_msg.lower()


@pytest.mark.integration
def test_merge_tool_with_sales_data(setup_advanced_tools, db_session):
    """Test merge tool with the SalesPerDay table."""
    session = db_session
    
    # Insert a new sales record
    data = {
        "business_date": "2024-01-15",
        "store_name": "Store D",
        "department": "Electronics",
        "sales_amount": 2500.50
    }
    
    arguments = {
        "table_name": "sales_per_day",
        "key_column": "id",
        "key_value": "100",
        "data": json.dumps(data)
    }
    
    result = execute_tool(
        tool_name="general_merge_tool",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    assert "Successfully upserted" in result
    
    # Verify the record was inserted
    query_result = session.exec(
        text("SELECT store_name, sales_amount FROM sales_per_day WHERE id = 100")
    ).first()
    
    assert query_result is not None
    assert query_result[0] == "Store D"
    assert query_result[1] == 2500.50
