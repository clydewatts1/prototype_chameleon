#!/usr/bin/env python3
"""
Test suite for the database connection test tool.

This test validates:
1. Tool registration via add_db_test_tool.py
2. Tool execution and diagnostics
3. Idempotency of registration
4. Error handling
"""

import os
import sys
import tempfile
from pathlib import Path

from sqlmodel import Session, select

from add_db_test_tool import register_db_test_tool, _compute_hash
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables
from runtime import execute_tool


def test_tool_registration():
    """Test that the tool can be registered successfully."""
    print("\n🧪 Test 1: Tool registration...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the tool directly with database URL
        success = register_db_test_tool(database_url=db_url)
        
        if not success:
            print("  ❌ Tool registration failed")
            return False
        
        # Verify tool exists in database
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'test_connection'
            )
            tool = session.exec(statement).first()
            
            if tool and tool.description:
                print("  ✅ Tool registered successfully")
                return True
            else:
                print("  ❌ Tool not found in database")
                return False
    finally:
        os.unlink(temp_db.name)


def test_tool_execution_sqlite():
    """Test that the tool executes correctly with SQLite."""
    print("\n🧪 Test 2: Tool execution with SQLite...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register and execute with database URL
        register_db_test_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            result = execute_tool('test_connection', 'default', {}, session)
            
            # Verify result contains expected information
            if ('Status: Success' in result and 
                'Dialect: sqlite' in result and 
                'Driver: pysqlite' in result):
                print("  ✅ Tool executed successfully")
                print(f"     Result preview: {result.split(chr(10))[0]}")
                return True
            else:
                print(f"  ❌ Unexpected result: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_tool_idempotency():
    """Test that running registration twice is safe."""
    print("\n🧪 Test 3: Tool registration idempotency...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register twice with database URL
        register_db_test_tool(database_url=db_url)
        register_db_test_tool(database_url=db_url)
        
        # Verify only one tool exists
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'test_connection'
            )
            tools = session.exec(statement).all()
            
            if len(tools) == 1:
                print("  ✅ Idempotency verified (only 1 tool exists)")
                return True
            else:
                print(f"  ❌ Expected 1 tool, found {len(tools)}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_tool_diagnostics():
    """Test that the tool returns diagnostic information."""
    print("\n🧪 Test 4: Tool diagnostic information...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register with database URL
        register_db_test_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            result = execute_tool('test_connection', 'default', {}, session)
            
            # Check for all required diagnostic fields
            required_fields = [
                'Status:',
                'Dialect:',
                'Driver:',
                'Database:',
                'Host:'
            ]
            
            missing_fields = [f for f in required_fields if f not in result]
            
            if not missing_fields:
                print("  ✅ All diagnostic fields present")
                return True
            else:
                print(f"  ❌ Missing fields: {missing_fields}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_hash_computation():
    """Test that hash computation is consistent."""
    print("\n🧪 Test 5: Hash computation consistency...")
    
    test_code = "test code"
    hash1 = _compute_hash(test_code)
    hash2 = _compute_hash(test_code)
    
    if hash1 == hash2 and len(hash1) == 64:  # SHA-256 produces 64 hex chars
        print("  ✅ Hash computation is consistent")
        return True
    else:
        print(f"  ❌ Hash mismatch or invalid length")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Database Connection Test Tool - Test Suite")
    print("=" * 60)
    
    tests = [
        test_hash_computation,
        test_tool_registration,
        test_tool_execution_sqlite,
        test_tool_idempotency,
        test_tool_diagnostics,
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
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
