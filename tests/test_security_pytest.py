import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from common.hash_utils import compute_hash as _compute_hash
"""
Pytest test suite for runtime.py security features with Jinja2 + SQLAlchemy binding.

This test validates:
1. Jinja2 template rendering for structural SQL logic
2. SQLAlchemy parameter binding for values
3. Single statement validation
4. Read-only validation (only SELECT allowed)
"""

import pytest
import hashlib
from datetime import date, timedelta
from sqlmodel import select
from models import CodeVault, ToolRegistry, SalesPerDay
from runtime import execute_tool, ToolNotFoundError
from common.security import SecurityError




@pytest.fixture
def setup_sales_data(db_session):
    """Fixture to populate the database with sample sales data."""
    stores = ["Store A", "Store B", "Store C"]
    departments = ["Electronics", "Clothing", "Groceries"]
    base_date = date(2024, 1, 1)
    
    for i in range(15):
        sales_record = SalesPerDay(
            business_date=base_date + timedelta(days=i),
            store_name=stores[i % len(stores)],
            department=departments[i % len(departments)],
            sales_amount=round(1000 + (i * 100), 2)
        )
        db_session.add(sales_record)
    
    db_session.commit()
    return db_session


@pytest.mark.security
def test_basic_select_without_jinja(setup_sales_data):
    """Test basic SELECT without Jinja2 templates works."""
    session = setup_sales_data
    
    # Create a simple SELECT query
    sql_code = "SELECT * FROM sales_per_day LIMIT 5"
    sql_hash = _compute_hash(sql_code)
    
    code_vault = CodeVault(
        hash=sql_hash,
        code_blob=sql_code,
        code_type="select"
    )
    session.add(code_vault)
    
    tool = ToolRegistry(
        tool_name="test_basic_select",
        target_persona="default",
        description="Test basic select",
        input_schema={"type": "object", "properties": {}, "required": []},
        active_hash_ref=sql_hash
    )
    session.add(tool)
    session.commit()
    
    # Execute the tool
    result = execute_tool("test_basic_select", "default", {}, session, session)
    
    assert len(result) == 5


@pytest.mark.security
def test_jinja_conditional_filter(setup_sales_data):
    """Test Jinja2 conditional filtering with SQLAlchemy parameter binding."""
    session = setup_sales_data
    
    # SQL with Jinja2 conditional and SQLAlchemy binding
    sql_code = """SELECT 
    department,
    SUM(sales_amount) as total_sales
FROM sales_per_day
WHERE 1=1
{% if arguments.department %}
  AND department = :department
{% endif %}
GROUP BY department"""
    sql_hash = _compute_hash(sql_code)
    
    code_vault = CodeVault(
        hash=sql_hash,
        code_blob=sql_code,
        code_type="select"
    )
    session.add(code_vault)
    
    tool = ToolRegistry(
        tool_name="test_conditional",
        target_persona="default",
        description="Test conditional filter",
        input_schema={"type": "object", "properties": {}, "required": []},
        active_hash_ref=sql_hash
    )
    session.add(tool)
    session.commit()
    
    # Test without filter - should return all departments
    result_all = execute_tool("test_conditional", "default", {}, session, session)
    assert len(result_all) == 3
    
    # Test with filter - should return only Electronics
    result_filtered = execute_tool("test_conditional", "default", 
                                  {"department": "Electronics"}, session, session)
    assert len(result_filtered) == 1
    assert result_filtered[0][0] == "Electronics"


@pytest.mark.security
def test_multiple_statements_blocked(setup_sales_data):
    """Test that multiple SQL statements are blocked."""
    session = setup_sales_data
    
    # Try to inject a second statement
    sql_code = """SELECT * FROM sales_per_day; DROP TABLE sales_per_day"""
    sql_hash = _compute_hash(sql_code)
    
    code_vault = CodeVault(
        hash=sql_hash,
        code_blob=sql_code,
        code_type="select"
    )
    session.add(code_vault)
    
    tool = ToolRegistry(
        tool_name="test_multi_statement",
        target_persona="default",
        description="Test multi statement",
        input_schema={"type": "object", "properties": {}, "required": []},
        active_hash_ref=sql_hash
    )
    session.add(tool)
    session.commit()
    
    # Execute the tool - should raise SecurityError
    with pytest.raises(SecurityError) as exc_info:
        execute_tool("test_multi_statement", "default", {}, session, session)
    
    assert "Multiple SQL statements" in str(exc_info.value)


@pytest.mark.security
@pytest.mark.parametrize("sql_code,operation", [
    ("UPDATE sales_per_day SET sales_amount = 0", "UPDATE"),
    ("INSERT INTO sales_per_day (business_date, store_name, department, sales_amount) VALUES ('2024-01-01', 'Store X', 'Dept', 100)", "INSERT"),
    ("DELETE FROM sales_per_day", "DELETE"),
    ("DROP TABLE sales_per_day", "DROP"),
    ("ALTER TABLE sales_per_day ADD COLUMN test TEXT", "ALTER"),
])
def test_write_operations_blocked(setup_sales_data, sql_code, operation):
    """Test that write operations (UPDATE, INSERT, DELETE) are blocked."""
    session = setup_sales_data
    
    sql_hash = _compute_hash(sql_code)
    
    code_vault = CodeVault(
        hash=sql_hash,
        code_blob=sql_code,
        code_type="select"
    )
    session.add(code_vault)
    
    tool = ToolRegistry(
        tool_name=f"test_{operation.lower()}",
        target_persona="default",
        description=f"Test {operation}",
        input_schema={"type": "object", "properties": {}, "required": []},
        active_hash_ref=sql_hash
    )
    session.add(tool)
    session.commit()
    
    # Execute the tool - should raise SecurityError
    with pytest.raises(SecurityError) as exc_info:
        execute_tool(f"test_{operation.lower()}", "default", {}, session, session)
    
    # Verify it's a SecurityError with some meaningful message
    assert str(exc_info.value)


@pytest.mark.security
def test_parameter_binding_prevents_injection(setup_sales_data):
    """Test that parameter binding prevents SQL injection."""
    session = setup_sales_data
    
    # SQL with parameter binding
    sql_code = """SELECT * FROM sales_per_day WHERE department = :department"""
    sql_hash = _compute_hash(sql_code)
    
    code_vault = CodeVault(
        hash=sql_hash,
        code_blob=sql_code,
        code_type="select"
    )
    session.add(code_vault)
    
    tool = ToolRegistry(
        tool_name="test_param_binding",
        target_persona="default",
        description="Test parameter binding",
        input_schema={"type": "object", "properties": {}, "required": []},
        active_hash_ref=sql_hash
    )
    session.add(tool)
    session.commit()
    
    # Try SQL injection via parameter (should be safely escaped)
    injection_attempt = "Electronics' OR '1'='1"
    result = execute_tool("test_param_binding", "default", 
                        {"department": injection_attempt}, session, session)
    
    # Should return empty result (no department matches the literal string)
    assert len(result) == 0
    
    # Normal query should work
    result_normal = execute_tool("test_param_binding", "default", 
                                {"department": "Electronics"}, session, session)
    assert len(result_normal) > 0


@pytest.mark.security
def test_trailing_semicolon_allowed(setup_sales_data):
    """Test that trailing semicolons are allowed."""
    session = setup_sales_data
    
    # Query with trailing semicolon (common in SQL)
    sql_code = "SELECT * FROM sales_per_day LIMIT 3;"
    sql_hash = _compute_hash(sql_code)
    
    code_vault = CodeVault(
        hash=sql_hash,
        code_blob=sql_code,
        code_type="select"
    )
    session.add(code_vault)
    
    tool = ToolRegistry(
        tool_name="test_trailing_semicolon",
        target_persona="default",
        description="Test trailing semicolon",
        input_schema={"type": "object", "properties": {}, "required": []},
        active_hash_ref=sql_hash
    )
    session.add(tool)
    session.commit()
    
    # Should not raise error
    result = execute_tool("test_trailing_semicolon", "default", {}, session, session)
    assert len(result) == 3


@pytest.mark.security
def test_multiline_comments_handled(setup_sales_data):
    """Test that multi-line SQL comments don't bypass security."""
    session = setup_sales_data
    
    # Try to hide dangerous keyword in multi-line comment before SELECT
    sql_code = """/* This is a comment with DROP keyword */
SELECT * FROM sales_per_day LIMIT 3"""
    sql_hash = _compute_hash(sql_code)
    
    code_vault = CodeVault(
        hash=sql_hash,
        code_blob=sql_code,
        code_type="select"
    )
    session.add(code_vault)
    
    tool = ToolRegistry(
        tool_name="test_multiline_comment",
        target_persona="default",
        description="Test multiline comment",
        input_schema={"type": "object", "properties": {}, "required": []},
        active_hash_ref=sql_hash
    )
    session.add(tool)
    session.commit()
    
    # Should work fine - comment is before SELECT
    result = execute_tool("test_multiline_comment", "default", {}, session, session)
    assert len(result) == 3


@pytest.mark.security
def test_dangerous_keyword_in_query_body_blocked(setup_sales_data):
    """Test that dangerous keywords in the query body are blocked."""
    session = setup_sales_data
    
    # Try to embed UPDATE in a SELECT query
    sql_code = """SELECT * FROM sales_per_day WHERE 1=1 UNION UPDATE sales_per_day SET sales_amount = 0"""
    sql_hash = _compute_hash(sql_code)
    
    code_vault = CodeVault(
        hash=sql_hash,
        code_blob=sql_code,
        code_type="select"
    )
    session.add(code_vault)
    
    tool = ToolRegistry(
        tool_name="test_union_update",
        target_persona="default",
        description="Test union update",
        input_schema={"type": "object", "properties": {}, "required": []},
        active_hash_ref=sql_hash
    )
    session.add(tool)
    session.commit()
    
    # Should be blocked
    with pytest.raises(SecurityError):
        execute_tool("test_union_update", "default", {}, session, session)
