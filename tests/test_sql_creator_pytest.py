import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from common.utils import compute_hash as _compute_hash
"""
Pytest test suite for the SQL Creator Meta-Tool.

This test validates:
1. Meta-tool registration via add_sql_creator_tool.py
2. Creation of SQL tools via the meta-tool
3. Security validation (SELECT-only, no semicolons)
4. Execution of dynamically created SQL tools
5. Idempotency and error handling
"""

import pytest
from datetime import date
from sqlmodel import select

from add_sql_creator_tool import register_sql_creator_tool
from models import CodeVault, ToolRegistry, SalesPerDay
from runtime import execute_tool, ToolNotFoundError
from common.security import SecurityError


@pytest.fixture
def registered_meta_tool(db_session):
    """Fixture to register the SQL creator meta-tool."""
    db_url = str(db_session.get_bind().url)
    success = register_sql_creator_tool(database_url=db_url)
    assert success, "Meta-tool registration failed"
    return db_session


@pytest.mark.integration
def test_meta_tool_registration(registered_meta_tool):
    """Test that the meta-tool can be registered successfully."""
    session = registered_meta_tool
    
    # Verify meta-tool exists in database
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'create_new_sql_tool'
    )
    tool = session.exec(statement).first()
    
    assert tool is not None
    assert tool.description
    assert 'create_new_sql_tool' == tool.tool_name


@pytest.mark.integration
def test_create_simple_sql_tool(registered_meta_tool):
    """Test creating a simple SQL tool via the meta-tool."""
    session = registered_meta_tool
    
    # Call the meta-tool to create a new SQL tool
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_all_sales',
            'description': 'Get all sales records',
            'sql_query': 'SELECT * FROM sales_per_day',
            'parameters': {}
        },
        session
    )
    
    assert 'Success' in result
    
    # Verify the new tool exists in ToolRegistry
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'get_all_sales'
    )
    new_tool = session.exec(statement).first()
    
    assert new_tool is not None
    assert new_tool.tool_name == 'get_all_sales'
    
    # Verify code in CodeVault has code_type='select'
    statement = select(CodeVault).where(
        CodeVault.hash == new_tool.active_hash_ref
    )
    code = session.exec(statement).first()
    
    assert code is not None
    assert code.code_type == 'select'


@pytest.mark.integration
def test_create_sql_tool_with_parameters(registered_meta_tool):
    """Test creating a SQL tool with parameters."""
    session = registered_meta_tool
    
    # Call the meta-tool to create a new SQL tool with parameters
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_sales_by_store',
            'description': 'Get sales records filtered by store name',
            'sql_query': 'SELECT * FROM sales_per_day WHERE store_name = :store_name',
            'parameters': {
                'store_name': {
                    'type': 'string',
                    'description': 'Name of the store to filter by',
                    'required': True
                }
            }
        },
        session
    )
    
    assert 'Success' in result
    
    # Verify input_schema is correct
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'get_sales_by_store'
    )
    new_tool = session.exec(statement).first()
    
    assert new_tool is not None
    schema = new_tool.input_schema
    assert 'store_name' in schema['properties']
    assert 'store_name' in schema['required']


@pytest.mark.integration
def test_validation_non_select_query(registered_meta_tool):
    """Test that non-SELECT queries are rejected."""
    session = registered_meta_tool
    
    # Try to create a tool with an INSERT statement
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'insert_sales',
            'description': 'Insert sales record',
            'sql_query': 'INSERT INTO sales_per_day (business_date, store_name) VALUES (:date, :store)',
            'parameters': {}
        },
        session
    )
    
    assert 'Error' in result
    assert 'SELECT' in result


@pytest.mark.integration
def test_validation_semicolon_injection(registered_meta_tool):
    """Test that queries with semicolons are rejected."""
    session = registered_meta_tool
    
    # Try to create a tool with semicolon in the middle
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'malicious_tool',
            'description': 'Malicious query',
            'sql_query': 'SELECT * FROM sales_per_day; DROP TABLE sales_per_day',
            'parameters': {}
        },
        session
    )
    
    assert 'Error' in result
    assert 'semicolon' in result


@pytest.mark.integration
def test_execute_created_sql_tool(registered_meta_tool):
    """Test executing a dynamically created SQL tool."""
    session = registered_meta_tool
    
    # Add some test data
    test_sale = SalesPerDay(
        business_date=date(2024, 1, 1),
        store_name="Test Store",
        department="Electronics",
        sales_amount=1000.0
    )
    session.add(test_sale)
    session.commit()
    
    # Create a SQL tool
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_test_sales',
            'description': 'Get sales from test store',
            'sql_query': 'SELECT * FROM sales_per_day WHERE store_name = :store_name',
            'parameters': {
                'store_name': {
                    'type': 'string',
                    'description': 'Store name',
                    'required': True
                }
            }
        },
        session
    )
    
    assert 'Success' in result
    
    # Now execute the created tool
    sales_result = execute_tool(
        'get_test_sales',
        'default',
        {'store_name': 'Test Store'},
        session
    )
    
    assert sales_result is not None
    assert len(sales_result) > 0


@pytest.mark.integration
def test_idempotency(registered_meta_tool):
    """Test that registering the same tool twice is idempotent."""
    session = registered_meta_tool
    
    # Create a tool
    tool_args = {
        'tool_name': 'test_idempotent',
        'description': 'Test tool for idempotency',
        'sql_query': 'SELECT * FROM sales_per_day',
        'parameters': {}
    }
    
    result1 = execute_tool('create_new_sql_tool', 'default', tool_args, session)
    assert 'Success' in result1
    
    # Create the same tool again
    result2 = execute_tool('create_new_sql_tool', 'default', tool_args, session)
    assert 'Success' in result2


@pytest.mark.integration
def test_validation_missing_required_fields(registered_meta_tool):
    """Test that missing required fields are rejected."""
    session = registered_meta_tool
    
    # Try to create a tool without tool_name
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'description': 'Test tool',
            'sql_query': 'SELECT * FROM sales_per_day'
        },
        session
    )
    
    assert 'Error' in result
    assert 'tool_name' in result
