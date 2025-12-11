#!/usr/bin/env python3
"""
Test suite for the SQL Creator Meta-Tool.

This test validates:
1. Meta-tool registration via add_sql_creator_tool.py
2. Creation of SQL tools via the meta-tool
3. Security validation (SELECT-only, no semicolons)
4. Execution of dynamically created SQL tools
5. Idempotency and error handling
"""

import os
import sys
import tempfile
from pathlib import Path

from sqlmodel import Session, select

from add_sql_creator_tool import register_sql_creator_tool, _compute_hash
from models import CodeVault, ToolRegistry, SalesPerDay, get_engine, create_db_and_tables
from runtime import execute_tool
from datetime import date


def test_meta_tool_registration():
    """Test that the meta-tool can be registered successfully."""
    print("\n🧪 Test 1: Meta-tool registration...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool directly with database URL
        success = register_sql_creator_tool(database_url=db_url)
        
        if not success:
            print("  ❌ Meta-tool registration failed")
            return False
        
        # Verify meta-tool exists in database
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'create_new_sql_tool'
            )
            tool = session.exec(statement).first()
            
            if tool and tool.description:
                print("  ✅ Meta-tool registered successfully")
                print(f"     Tool name: {tool.tool_name}")
                print(f"     Description: {tool.description[:60]}...")
                return True
            else:
                print("  ❌ Meta-tool not found in database")
                return False
    finally:
        os.unlink(temp_db.name)


def test_create_simple_sql_tool():
    """Test creating a simple SQL tool via the meta-tool."""
    print("\n🧪 Test 2: Creating a simple SQL tool...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
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
            
            if 'Success' in result:
                print("  ✅ SQL tool created successfully")
                print(f"     Result: {result}")
                
                # Verify the new tool exists in ToolRegistry
                statement = select(ToolRegistry).where(
                    ToolRegistry.tool_name == 'get_all_sales'
                )
                new_tool = session.exec(statement).first()
                
                if new_tool:
                    print(f"     Verified in ToolRegistry: {new_tool.tool_name}")
                    
                    # Verify code in CodeVault has code_type='select'
                    statement = select(CodeVault).where(
                        CodeVault.hash == new_tool.active_hash_ref
                    )
                    code = session.exec(statement).first()
                    
                    if code and code.code_type == 'select':
                        print(f"     Code type verified as 'select'")
                        return True
                    else:
                        print(f"  ❌ Code type is not 'select': {code.code_type if code else 'None'}")
                        return False
                else:
                    print("  ❌ New tool not found in ToolRegistry")
                    return False
            else:
                print(f"  ❌ Tool creation failed: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_create_sql_tool_with_parameters():
    """Test creating a SQL tool with parameters."""
    print("\n🧪 Test 3: Creating SQL tool with parameters...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
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
            
            if 'Success' in result:
                print("  ✅ SQL tool with parameters created successfully")
                
                # Verify input_schema is correct
                statement = select(ToolRegistry).where(
                    ToolRegistry.tool_name == 'get_sales_by_store'
                )
                new_tool = session.exec(statement).first()
                
                if new_tool:
                    schema = new_tool.input_schema
                    if ('store_name' in schema['properties'] and 
                        'store_name' in schema['required']):
                        print(f"     Input schema verified correctly")
                        print(f"     Parameters: {list(schema['properties'].keys())}")
                        return True
                    else:
                        print(f"  ❌ Input schema incorrect: {schema}")
                        return False
                else:
                    print("  ❌ New tool not found in ToolRegistry")
                    return False
            else:
                print(f"  ❌ Tool creation failed: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_validation_non_select_query():
    """Test that non-SELECT queries are rejected."""
    print("\n🧪 Test 4: Validation - Non-SELECT query rejection...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
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
            
            if 'Error' in result and 'SELECT' in result:
                print("  ✅ Non-SELECT query rejected correctly")
                print(f"     Error message: {result}")
                return True
            else:
                print(f"  ❌ Non-SELECT query was not rejected: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_validation_semicolon_injection():
    """Test that queries with semicolons are rejected."""
    print("\n🧪 Test 5: Validation - Semicolon injection prevention...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
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
            
            if 'Error' in result and 'semicolon' in result:
                print("  ✅ Query with semicolon rejected correctly")
                print(f"     Error message: {result}")
                return True
            else:
                print(f"  ❌ Query with semicolon was not rejected: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_execute_created_sql_tool():
    """Test executing a dynamically created SQL tool."""
    print("\n🧪 Test 6: Executing dynamically created SQL tool...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        create_db_and_tables(engine)
        
        with Session(engine) as session:
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
            
            if 'Success' not in result:
                print(f"  ❌ Tool creation failed: {result}")
                return False
            
            # Now execute the created tool
            sales_result = execute_tool(
                'get_test_sales',
                'default',
                {'store_name': 'Test Store'},
                session
            )
            
            if sales_result and len(sales_result) > 0:
                print("  ✅ Dynamically created tool executed successfully")
                print(f"     Found {len(sales_result)} sales record(s)")
                return True
            else:
                print(f"  ❌ Tool execution returned no results: {sales_result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_idempotency():
    """Test that registering the same tool twice is idempotent."""
    print("\n🧪 Test 7: Idempotency test...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Create a tool
            tool_args = {
                'tool_name': 'test_idempotent',
                'description': 'Test tool for idempotency',
                'sql_query': 'SELECT * FROM sales_per_day',
                'parameters': {}
            }
            
            result1 = execute_tool('create_new_sql_tool', 'default', tool_args, session)
            
            if 'Success' not in result1:
                print(f"  ❌ First tool creation failed: {result1}")
                return False
            
            # Create the same tool again
            result2 = execute_tool('create_new_sql_tool', 'default', tool_args, session)
            
            if 'Success' in result2:
                print("  ✅ Tool creation is idempotent")
                print(f"     First result: {result1[:50]}...")
                print(f"     Second result: {result2[:50]}...")
                return True
            else:
                print(f"  ❌ Second tool creation failed: {result2}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_validation_missing_required_fields():
    """Test that missing required fields are rejected."""
    print("\n🧪 Test 8: Validation - Missing required fields...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
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
            
            if 'Error' in result and 'tool_name' in result:
                print("  ✅ Missing tool_name rejected correctly")
                print(f"     Error message: {result}")
                return True
            else:
                print(f"  ❌ Missing tool_name was not rejected: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def run_all_tests():
    """Run all test cases."""
    print("=" * 60)
    print("SQL Creator Meta-Tool Test Suite")
    print("=" * 60)
    
    tests = [
        test_meta_tool_registration,
        test_create_simple_sql_tool,
        test_create_sql_tool_with_parameters,
        test_validation_non_select_query,
        test_validation_semicolon_injection,
        test_execute_created_sql_tool,
        test_idempotency,
        test_validation_missing_required_fields,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ Test raised exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


def main():
    """Main entry point."""
    return run_all_tests()


if __name__ == '__main__':
    sys.exit(main())
