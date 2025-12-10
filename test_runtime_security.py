#!/usr/bin/env python3
"""
Test suite for runtime.py security features with Jinja2 + SQLAlchemy binding.

This test validates:
1. Jinja2 template rendering for structural SQL logic
2. SQLAlchemy parameter binding for values
3. Single statement validation
4. Read-only validation (only SELECT allowed)
"""

import sys
from datetime import date, timedelta
from sqlmodel import Session, create_engine, SQLModel
from models import CodeVault, ToolRegistry, SalesPerDay
from runtime import execute_tool, SecurityError, ToolNotFoundError
import hashlib


def _compute_hash(code: str) -> str:
    """Compute SHA-256 hash of code."""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def setup_test_database():
    """Create a test database with sample data."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Add sample sales data
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
            session.add(sales_record)
        
        session.commit()
    
    return engine


def test_basic_select_without_jinja():
    """Test basic SELECT without Jinja2 templates works."""
    print("\n🧪 Test 1: Basic SELECT without Jinja2...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
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
        result = execute_tool("test_basic_select", "default", {}, session)
        
        assert len(result) == 5, f"Expected 5 results, got {len(result)}"
        print("  ✅ Basic SELECT works")
        return True


def test_jinja_conditional_filter():
    """Test Jinja2 conditional filtering with SQLAlchemy parameter binding."""
    print("\n🧪 Test 2: Jinja2 conditional with parameter binding...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
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
        result_all = execute_tool("test_conditional", "default", {}, session)
        assert len(result_all) == 3, f"Expected 3 departments, got {len(result_all)}"
        
        # Test with filter - should return only Electronics
        result_filtered = execute_tool("test_conditional", "default", 
                                      {"department": "Electronics"}, session)
        assert len(result_filtered) == 1, f"Expected 1 department, got {len(result_filtered)}"
        assert result_filtered[0][0] == "Electronics"
        
        print("  ✅ Jinja2 conditional filtering works")
        return True


def test_multiple_statements_blocked():
    """Test that multiple SQL statements are blocked."""
    print("\n🧪 Test 3: Multiple statements blocked...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
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
        try:
            execute_tool("test_multi_statement", "default", {}, session)
            print("  ❌ Multiple statements were NOT blocked!")
            return False
        except SecurityError as e:
            assert "Multiple SQL statements" in str(e)
            print("  ✅ Multiple statements correctly blocked")
            return True


def test_write_operations_blocked():
    """Test that write operations (UPDATE, INSERT, DELETE) are blocked."""
    print("\n🧪 Test 4: Write operations blocked...")
    
    engine = setup_test_database()
    
    dangerous_queries = [
        ("UPDATE sales_per_day SET sales_amount = 0", "UPDATE"),
        ("INSERT INTO sales_per_day VALUES (1, '2024-01-01', 'Store X', 'Dept', 100)", "INSERT"),
        ("DELETE FROM sales_per_day", "DELETE"),
        ("DROP TABLE sales_per_day", "DROP"),
        ("ALTER TABLE sales_per_day ADD COLUMN test TEXT", "ALTER"),
    ]
    
    for sql_code, operation in dangerous_queries:
        with Session(engine) as session:
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
            try:
                execute_tool(f"test_{operation.lower()}", "default", {}, session)
                print(f"  ❌ {operation} was NOT blocked!")
                return False
            except SecurityError as e:
                if "Only SELECT" in str(e) or "Dangerous keyword" in str(e):
                    print(f"  ✅ {operation} correctly blocked")
                else:
                    print(f"  ❌ {operation} blocked but wrong error: {e}")
                    return False
    
    return True


def test_parameter_binding_prevents_injection():
    """Test that parameter binding prevents SQL injection."""
    print("\n🧪 Test 5: Parameter binding prevents SQL injection...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
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
                            {"department": injection_attempt}, session)
        
        # Should return empty result (no department matches the literal string)
        assert len(result) == 0, f"SQL injection not prevented! Got {len(result)} results"
        
        # Normal query should work
        result_normal = execute_tool("test_param_binding", "default", 
                                    {"department": "Electronics"}, session)
        assert len(result_normal) > 0, "Normal query failed"
        
        print("  ✅ Parameter binding prevents SQL injection")
        return True


def test_trailing_semicolon_allowed():
    """Test that trailing semicolons are allowed."""
    print("\n🧪 Test 6: Trailing semicolon allowed...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
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
        result = execute_tool("test_trailing_semicolon", "default", {}, session)
        assert len(result) == 3, f"Expected 3 results, got {len(result)}"
        
        print("  ✅ Trailing semicolon allowed")
        return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Runtime Security Tests - Jinja2 + SQLAlchemy Binding")
    print("=" * 60)
    
    tests = [
        test_basic_select_without_jinja,
        test_jinja_conditional_filter,
        test_multiple_statements_blocked,
        test_write_operations_blocked,
        test_parameter_binding_prevents_injection,
        test_trailing_semicolon_allowed,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test {test.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All runtime security tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
