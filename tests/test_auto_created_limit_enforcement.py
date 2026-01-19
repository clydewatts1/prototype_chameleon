import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from common.hash_utils import compute_hash as _compute_hash
"""
Pytest test suite for LIMIT 1000 enforcement on auto-created SQL tools.

This test validates:
1. Auto-created SQL tools (via create_new_sql_tool) enforce LIMIT 1000
2. System tools do NOT have LIMIT enforcement (backward compatibility)
3. Temporary tools still enforce LIMIT 3 (unchanged behavior)
4. LIMIT enforcement removes any existing LIMIT clause
5. LIMIT enforcement works with complex queries
"""

import pytest
from datetime import date
from sqlmodel import select

from add_sql_creator_tool import register_sql_creator_tool
from models import CodeVault, ToolRegistry, SalesPerDay
from runtime import execute_tool


@pytest.fixture
def registered_sql_creator(db_session):
    """Fixture to register the SQL creator meta-tool."""
    db_url = str(db_session.get_bind().url)
    success = register_sql_creator_tool(database_url=db_url)
    assert success, "Meta-tool registration failed"
    return db_session


@pytest.fixture
def large_sales_dataset(db_session):
    """Fixture to create a large sales dataset (1500 records) for testing LIMIT enforcement."""
    sales_records = []
    for i in range(1500):
        sales_records.append(
            SalesPerDay(
                business_date=date(2024, 1, (i % 28) + 1),
                store_name=f"Store {chr(65 + (i % 5))}",  # Store A-E
                department=f"Dept{i % 10}",
                sales_amount=100.0 + (i * 0.5)
            )
        )
    
    for sale in sales_records:
        db_session.add(sale)
    db_session.commit()
    
    return db_session


@pytest.mark.integration
def test_auto_created_tool_enforces_limit_1000(registered_sql_creator, large_sales_dataset):
    """Test that auto-created SQL tools enforce LIMIT 1000."""
    session = large_sales_dataset
    
    # Create an auto-created SQL tool (no LIMIT in the query)
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_all_sales_auto',
            'description': 'Get all sales records (auto-created)',
            'sql_query': 'SELECT * FROM sales_per_day ORDER BY business_date',
            'parameters': {}
        },
        session
    )
    
    assert 'Success' in result
    
    # Verify the tool is marked as auto-created
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'get_all_sales_auto'
    )
    tool = session.exec(statement).first()
    assert tool is not None
    assert tool.is_auto_created is True
    
    # Execute the auto-created tool
    sales_result = execute_tool(
        'get_all_sales_auto',
        'default',
        {},
        session,  # meta_session
        session   # data_session
    )
    
    # Should return exactly 1000 rows due to LIMIT 1000, even though we have 1500
    assert sales_result is not None
    assert len(sales_result) == 1000, f"Expected 1000 rows due to LIMIT 1000, got {len(sales_result)}"


@pytest.mark.integration
def test_auto_created_tool_removes_existing_limit(registered_sql_creator, large_sales_dataset):
    """Test that auto-created tools remove any existing LIMIT clause and enforce LIMIT 1000."""
    session = large_sales_dataset
    
    # Create an auto-created SQL tool with LIMIT 500 (should be replaced with LIMIT 1000)
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_limited_sales_auto',
            'description': 'Get limited sales (auto-created with existing LIMIT)',
            'sql_query': 'SELECT * FROM sales_per_day ORDER BY business_date LIMIT 500',
            'parameters': {}
        },
        session
    )
    
    assert 'Success' in result
    
    # Execute the auto-created tool
    sales_result = execute_tool(
        'get_limited_sales_auto',
        'default',
        {},
        session,  # meta_session
        session   # data_session
    )
    
    # Should return exactly 1000 rows (LIMIT 500 was replaced with LIMIT 1000)
    assert sales_result is not None
    assert len(sales_result) == 1000, f"Expected 1000 rows (LIMIT 500 replaced), got {len(sales_result)}"


@pytest.mark.integration
def test_auto_created_tool_with_where_clause(registered_sql_creator, large_sales_dataset):
    """Test that LIMIT 1000 enforcement works with WHERE clauses."""
    session = large_sales_dataset
    
    # Create an auto-created SQL tool with WHERE clause
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_sales_by_store_auto',
            'description': 'Get sales by store (auto-created)',
            'sql_query': 'SELECT * FROM sales_per_day WHERE store_name = :store_name ORDER BY business_date',
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
    
    # Execute the auto-created tool (Store A has 300 records)
    sales_result = execute_tool(
        'get_sales_by_store_auto',
        'default',
        {'store_name': 'Store A'},
        session,  # meta_session
        session   # data_session
    )
    
    # Should return 300 rows (all Store A records, less than LIMIT 1000)
    assert sales_result is not None
    assert len(sales_result) == 300, f"Expected 300 rows for Store A, got {len(sales_result)}"
    
    # Verify all results are for Store A
    for row in sales_result:
        assert row.store_name == 'Store A'


@pytest.mark.integration
def test_auto_created_tool_with_aggregate(registered_sql_creator, large_sales_dataset):
    """Test that LIMIT 1000 enforcement works with aggregate queries."""
    session = large_sales_dataset
    
    # Create an auto-created SQL tool with aggregation
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_sales_by_department_auto',
            'description': 'Get sales grouped by department (auto-created)',
            'sql_query': 'SELECT department, SUM(sales_amount) as total_sales FROM sales_per_day GROUP BY department ORDER BY total_sales DESC',
            'parameters': {}
        },
        session
    )
    
    assert 'Success' in result
    
    # Execute the auto-created tool (10 departments, much less than LIMIT 1000)
    sales_result = execute_tool(
        'get_sales_by_department_auto',
        'default',
        {},
        session,  # meta_session
        session   # data_session
    )
    
    # Should return 10 rows (one per department, less than LIMIT 1000)
    assert sales_result is not None
    assert len(sales_result) == 10, f"Expected 10 rows (10 departments), got {len(sales_result)}"


@pytest.mark.integration
def test_system_tool_no_limit_enforcement(db_session, large_sales_dataset):
    """Test that system tools (is_auto_created=False) do NOT have LIMIT enforcement."""
    from common.hash_utils import compute_hash
    session = large_sales_dataset
    
    # Manually create a system tool (is_auto_created=False)
    sql_query = 'SELECT * FROM sales_per_day ORDER BY business_date'
    code_hash = compute_hash(sql_query)
    
    # Insert into CodeVault
    code_vault = CodeVault(
        hash=code_hash,
        code_blob=sql_query,
        code_type='select'
    )
    session.add(code_vault)
    
    # Insert into ToolRegistry with is_auto_created=False
    tool = ToolRegistry(
        tool_name='get_all_sales_system',
        target_persona='default',
        description='System tool to get all sales',
        input_schema={'type': 'object', 'properties': {}, 'required': []},
        active_hash_ref=code_hash,
        is_auto_created=False,  # System tool
        group='utility'
    )
    session.add(tool)
    session.commit()
    
    # Execute the system tool
    sales_result = execute_tool(
        'get_all_sales_system',
        'default',
        {},
        session,  # meta_session
        session   # data_session
    )
    
    # Should return all 1500 rows (NO LIMIT enforcement for system tools)
    assert sales_result is not None
    assert len(sales_result) == 1500, f"Expected 1500 rows (no limit for system tools), got {len(sales_result)}"


@pytest.mark.integration
def test_comparison_temp_vs_auto_vs_system(registered_sql_creator, large_sales_dataset):
    """
    Comprehensive test comparing LIMIT enforcement across tool types:
    - Temporary tools: LIMIT 3
    - Auto-created tools: LIMIT 1000
    - System tools: No LIMIT
    """
    from add_temp_tool_creator import register_temp_tool_creator
    from runtime import TEMP_TOOL_REGISTRY, TEMP_CODE_VAULT
    from common.hash_utils import compute_hash
    
    session = large_sales_dataset
    
    # Clear temporary storage
    TEMP_TOOL_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Register the temporary test tool creator
    db_url = str(session.get_bind().url)
    success = register_temp_tool_creator(database_url=db_url)
    assert success
    
    # 1. Create a temporary tool (LIMIT 3)
    result = execute_tool(
        'create_temp_test_tool',
        'default',
        {
            'tool_name': 'test_temp_sales',
            'description': 'Temporary test tool',
            'sql_query': 'SELECT * FROM sales_per_day ORDER BY business_date',
            'parameters': {}
        },
        session
    )
    assert 'Success' in result
    
    # Execute temporary tool
    temp_result = execute_tool(
        'test_temp_sales',
        'default',
        {},
        session,
        session
    )
    assert len(temp_result) == 3, f"Temporary tool should return 3 rows, got {len(temp_result)}"
    
    # 2. Create an auto-created tool (LIMIT 1000)
    result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_auto_sales',
            'description': 'Auto-created tool',
            'sql_query': 'SELECT * FROM sales_per_day ORDER BY business_date',
            'parameters': {}
        },
        session
    )
    assert 'Success' in result
    
    # Execute auto-created tool
    auto_result = execute_tool(
        'get_auto_sales',
        'default',
        {},
        session,
        session
    )
    assert len(auto_result) == 1000, f"Auto-created tool should return 1000 rows, got {len(auto_result)}"
    
    # 3. Create a system tool (no LIMIT)
    sql_query = 'SELECT * FROM sales_per_day ORDER BY business_date'
    code_hash = compute_hash(sql_query)
    
    code_vault = CodeVault(
        hash=code_hash,
        code_blob=sql_query,
        code_type='select'
    )
    session.merge(code_vault)
    
    tool = ToolRegistry(
        tool_name='get_system_sales',
        target_persona='default',
        description='System tool',
        input_schema={'type': 'object', 'properties': {}, 'required': []},
        active_hash_ref=code_hash,
        is_auto_created=False,
        group='utility'
    )
    session.merge(tool)
    session.commit()
    
    # Execute system tool
    system_result = execute_tool(
        'get_system_sales',
        'default',
        {},
        session,
        session
    )
    assert len(system_result) == 1500, f"System tool should return 1500 rows, got {len(system_result)}"
    
    print("\n✓ LIMIT enforcement comparison:")
    print(f"  Temporary tool: {len(temp_result)} rows (LIMIT 3)")
    print(f"  Auto-created tool: {len(auto_result)} rows (LIMIT 1000)")
    print(f"  System tool: {len(system_result)} rows (no LIMIT)")
