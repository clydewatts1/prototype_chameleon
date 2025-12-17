import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.hash_utils import compute_hash as _compute_hash
"""
Pytest test suite for the Temporary Test Tools feature.

This test validates:
1. Meta-tool registration via add_temp_tool_creator.py
2. Creation of temporary SQL test tools
3. Security validation (SELECT-only, no semicolons)
4. Execution of temporary tools with LIMIT 3 constraint
5. Non-persistence to database
6. Error logging for temporary tools
7. Listing tools includes temporary tools
"""

import pytest
from datetime import date
from sqlmodel import select

from add_temp_tool_creator import register_temp_tool_creator
from models import CodeVault, ToolRegistry, SalesPerDay, ExecutionLog
from runtime import execute_tool, list_tools_for_persona, TEMP_TOOL_REGISTRY, TEMP_CODE_VAULT
from common.security import SecurityError


@pytest.fixture
def registered_temp_tool_creator(db_session):
    """Fixture to register the temporary test tool creator meta-tool."""
    db_url = str(db_session.get_bind().url)
    success = register_temp_tool_creator(database_url=db_url)
    assert success, "Meta-tool registration failed"
    return db_session


@pytest.fixture
def sample_sales_data(db_session):
    """Fixture to create sample sales data for testing."""
    sales_records = [
        SalesPerDay(
            business_date=date(2024, 1, 1),
            store_name="Store A",
            department="Electronics",
            sales_amount=1000.0
        ),
        SalesPerDay(
            business_date=date(2024, 1, 2),
            store_name="Store A",
            department="Electronics",
            sales_amount=1500.0
        ),
        SalesPerDay(
            business_date=date(2024, 1, 3),
            store_name="Store B",
            department="Clothing",
            sales_amount=800.0
        ),
        SalesPerDay(
            business_date=date(2024, 1, 4),
            store_name="Store B",
            department="Clothing",
            sales_amount=900.0
        ),
        SalesPerDay(
            business_date=date(2024, 1, 5),
            store_name="Store A",
            department="Electronics",
            sales_amount=2000.0
        ),
    ]
    
    for sale in sales_records:
        db_session.add(sale)
    db_session.commit()
    
    return db_session


@pytest.mark.integration
def test_temp_tool_creator_registration(registered_temp_tool_creator):
    """Test that the temporary test tool creator can be registered successfully."""
    session = registered_temp_tool_creator
    
    # Verify meta-tool exists in database
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'create_temp_test_tool'
    )
    tool = session.exec(statement).first()
    
    assert tool is not None
    assert tool.description
    assert 'create_temp_test_tool' == tool.tool_name
    assert 'temporary' in tool.description.lower() or 'temp' in tool.description.lower()


@pytest.mark.integration
def test_create_simple_temp_tool(registered_temp_tool_creator):
    """Test creating a simple temporary SQL test tool."""
    session = registered_temp_tool_creator
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Call the meta-tool to create a new temporary test tool
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_all_sales',
            'description': 'Test tool to get all sales records',
            'sql_query': 'SELECT * FROM sales_per_day',
            'parameters': {}
        },
        session
    )
    
    assert 'Success' in result
    assert 'TEMPORARY' in result or 'TEMP' in result
    assert 'LIMIT 3' in result
    
    # Verify the tool is in temporary storage
    temp_key = 'test_all_sales:default'
    assert temp_key in TEMP_TOOL_REGISTRY
    
    # Verify it's NOT in the database
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'test_all_sales'
    )
    db_tool = session.exec(statement).first()
    assert db_tool is None, "Temporary tool should not be in database"


@pytest.mark.integration
def test_create_temp_tool_with_parameters(registered_temp_tool_creator):
    """Test creating a temporary tool with parameters."""
    session = registered_temp_tool_creator
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Call the meta-tool to create a new temporary tool with parameters
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_sales_by_store',
            'description': 'Test tool to get sales filtered by store',
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
    
    # Verify input_schema is correct in temporary storage
    temp_key = 'test_sales_by_store:default'
    assert temp_key in TEMP_TOOL_REGISTRY
    
    tool_meta = TEMP_TOOL_REGISTRY[temp_key]
    schema = tool_meta['input_schema']
    assert 'store_name' in schema['properties']
    assert 'store_name' in schema['required']


@pytest.mark.integration
def test_execute_temp_tool_with_limit_3(registered_temp_tool_creator, sample_sales_data):
    """Test executing a temporary tool enforces LIMIT 3 constraint."""
    session = sample_sales_data
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary test tool
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_get_sales',
            'description': 'Test tool to get sales',
            'sql_query': 'SELECT * FROM sales_per_day ORDER BY business_date',
            'parameters': {}
        },
        session
    )
    
    assert 'Success' in result
    
    # Now execute the temporary tool (pass session as both meta and data session)
    sales_result = execute_tool(
        'test_get_sales',
        'default',
        {},
        session,  # meta_session
        session   # data_session
    )
    
    # Should return exactly 3 rows even though we have 5 in the database
    assert sales_result is not None
    assert len(sales_result) == 3, f"Expected 3 rows due to LIMIT 3, got {len(sales_result)}"


@pytest.mark.integration
def test_temp_tool_rejects_existing_limit(registered_temp_tool_creator, sample_sales_data):
    """Test that temporary tool rejects any existing LIMIT clause."""
    session = sample_sales_data
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary test tool with LIMIT 10 (should be rejected)
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_limited_sales',
            'description': 'Test tool with limit',
            'sql_query': 'SELECT * FROM sales_per_day ORDER BY business_date LIMIT 10',
            'parameters': {}
        },
        session
    )
    
    # Should return Error
    assert 'Error' in result
    assert 'Do not include LIMIT clause' in result


@pytest.mark.integration
def test_temp_tool_validation_non_select(registered_temp_tool_creator):
    """Test that temporary tools reject non-SELECT queries."""
    session = registered_temp_tool_creator
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Try to create a tool with an INSERT statement
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_insert',
            'description': 'Test insert',
            'sql_query': 'INSERT INTO sales_per_day (business_date, store_name) VALUES (:date, :store)',
            'parameters': {}
        },
        session
    )
    
    assert 'Error' in result
    assert 'SELECT' in result


@pytest.mark.integration
def test_temp_tool_validation_semicolon(registered_temp_tool_creator):
    """Test that temporary tools reject queries with semicolons."""
    session = registered_temp_tool_creator
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Try to create a tool with semicolon in the middle
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_malicious',
            'description': 'Malicious query',
            'sql_query': 'SELECT * FROM sales_per_day; DROP TABLE sales_per_day',
            'parameters': {}
        },
        session
    )
    
    assert 'Error' in result
    assert 'semicolon' in result


@pytest.mark.integration
def test_temp_tool_in_list_tools(registered_temp_tool_creator):
    """Test that temporary tools appear in list_tools_for_persona."""
    session = registered_temp_tool_creator
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary test tool
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_list_sales',
            'description': 'Test tool for listing',
            'sql_query': 'SELECT * FROM sales_per_day',
            'parameters': {}
        },
        session
    )
    
    assert 'Success' in result
    
    # List tools for default persona
    tools = list_tools_for_persona('default', session)
    
    # Find our temporary tool
    temp_tool = None
    for tool in tools:
        if tool['name'] == 'test_list_sales':
            temp_tool = tool
            break
    
    assert temp_tool is not None, "Temporary tool should appear in list"
    assert '[TEMP-TEST]' in temp_tool['description']


@pytest.mark.integration
def test_temp_tool_execution_logging(registered_temp_tool_creator, sample_sales_data):
    """Test that temporary tool executions are logged properly."""
    session = sample_sales_data
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary test tool
    execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_logged_sales',
            'description': 'Test tool for logging',
            'sql_query': 'SELECT * FROM sales_per_day',
            'parameters': {}
        },
        session
    )
    
    # Execute the temporary tool (pass session as both meta and data session)
    execute_tool(
        'test_logged_sales',
        'default',
        {},
        session,  # meta_session
        session   # data_session
    )
    
    # Check that execution was logged
    statement = select(ExecutionLog).where(
        ExecutionLog.tool_name == 'test_logged_sales',
        ExecutionLog.status == 'SUCCESS'
    )
    log_entry = session.exec(statement).first()
    
    assert log_entry is not None, "Temporary tool execution should be logged"
    assert log_entry.persona == 'default'


@pytest.mark.integration
def test_temp_tool_error_logging(registered_temp_tool_creator, sample_sales_data):
    """Test that temporary tool errors are logged and retrievable."""
    session = sample_sales_data
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary test tool with invalid SQL
    execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_error_tool',
            'description': 'Test tool that will error',
            'sql_query': 'SELECT * FROM nonexistent_table',
            'parameters': {}
        },
        session
    )
    
    # Try to execute the temporary tool (should fail)
    try:
        execute_tool(
            'test_error_tool',
            'default',
            {},
            session,  # meta_session
            session   # data_session
        )
    except Exception:
        # Expected to fail
        pass
    
    # Check that error was logged
    statement = select(ExecutionLog).where(
        ExecutionLog.tool_name == 'test_error_tool',
        ExecutionLog.status == 'FAILURE'
    )
    log_entry = session.exec(statement).first()
    
    assert log_entry is not None, "Temporary tool error should be logged"
    assert log_entry.error_traceback is not None
    assert 'nonexistent_table' in log_entry.error_traceback


@pytest.mark.integration
def test_temp_tool_not_persisted_after_clear(registered_temp_tool_creator):
    """Test that clearing temporary storage removes tools completely."""
    session = registered_temp_tool_creator
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary test tool
    execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_temp_clear',
            'description': 'Test tool for clearing',
            'sql_query': 'SELECT * FROM sales_per_day',
            'parameters': {}
        },
        session
    )
    
    # Verify it exists in temporary storage
    temp_key = 'test_temp_clear:default'
    assert temp_key in TEMP_TOOL_REGISTRY
    
    # Clear temporary storage
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Verify it's gone
    assert temp_key not in TEMP_TOOL_REGISTRY
    
    # Verify it was never in the database
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'test_temp_clear'
    )
    db_tool = session.exec(statement).first()
    assert db_tool is None


@pytest.mark.integration
def test_validation_missing_required_fields(registered_temp_tool_creator):
    """Test that missing required fields are rejected."""
    session = registered_temp_tool_creator
    
    # Clear any existing temporary tools
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Try to create a tool without tool_name
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'description': 'Test tool',
            'sql_query': 'SELECT * FROM sales_per_day'
        },
        session
    )
    
    assert 'Error' in result
    assert 'tool_name' in result
