#!/usr/bin/env python3
"""
Test suite for the resource bridge tool.

This test validates:
1. Tool registration via add_resource_bridge.py
2. Tool execution for existing resources
3. Error handling with self-discovery of available resources
4. Idempotency of registration
"""

import os
import sys
import tempfile
from pathlib import Path

from sqlmodel import Session, select

from add_resource_bridge import register_resource_bridge_tool
from models import CodeVault, ToolRegistry, ResourceRegistry, get_engine, create_db_and_tables
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
        success = register_resource_bridge_tool(database_url=db_url)
        
        if not success:
            print("  ❌ Tool registration failed")
            return False
        
        # Verify tool exists in database
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'read_resource'
            )
            tool = session.exec(statement).first()
            
            if tool and tool.description:
                print("  ✅ Tool registered successfully")
                return True
            else:
                print("  ❌ Tool not found in registry")
                return False
    finally:
        # Clean up
        os.unlink(temp_db.name)


def test_read_existing_resource():
    """Test reading an existing static resource."""
    print("\n🧪 Test 2: Read existing resource...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Set up database and tool
        engine = get_engine(db_url)
        create_db_and_tables(engine)
        
        with Session(engine) as session:
            # Create a test resource
            test_resource = ResourceRegistry(
                uri_schema="memo://test",
                name="test_resource",
                description="A test resource",
                mime_type="text/plain",
                is_dynamic=False,
                static_content="This is test content",
                target_persona="default"
            )
            session.add(test_resource)
            session.commit()
        
        # Register the tool
        success = register_resource_bridge_tool(database_url=db_url)
        if not success:
            print("  ❌ Tool registration failed")
            return False
        
        # Execute the tool
        with Session(engine) as session:
            result = execute_tool(
                tool_name='read_resource',
                persona='default',
                arguments={'uri': 'memo://test'},
                db_session=session
            )
            
            if result == "This is test content":
                print("  ✅ Resource read successfully")
                return True
            else:
                print(f"  ❌ Unexpected result: {result}")
                return False
    finally:
        # Clean up
        os.unlink(temp_db.name)


def test_resource_not_found_with_discovery():
    """Test error handling with self-discovery of available resources."""
    print("\n🧪 Test 3: Resource not found with self-discovery...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Set up database and tool
        engine = get_engine(db_url)
        create_db_and_tables(engine)
        
        with Session(engine) as session:
            # Create test resources
            test_resource1 = ResourceRegistry(
                uri_schema="memo://resource1",
                name="resource1",
                description="First test resource",
                mime_type="text/plain",
                is_dynamic=False,
                static_content="Content 1",
                target_persona="default"
            )
            test_resource2 = ResourceRegistry(
                uri_schema="memo://resource2",
                name="resource2",
                description="Second test resource",
                mime_type="text/plain",
                is_dynamic=False,
                static_content="Content 2",
                target_persona="default"
            )
            session.add(test_resource1)
            session.add(test_resource2)
            session.commit()
        
        # Register the tool
        success = register_resource_bridge_tool(database_url=db_url)
        if not success:
            print("  ❌ Tool registration failed")
            return False
        
        # Execute the tool with non-existent URI
        with Session(engine) as session:
            result = execute_tool(
                tool_name='read_resource',
                persona='default',
                arguments={'uri': 'memo://nonexistent'},
                db_session=session
            )
            
            # Check if result contains error message and available resources
            if "Resource not found" in result and "memo://resource1" in result and "memo://resource2" in result:
                print("  ✅ Error handling with self-discovery works correctly")
                print(f"     Result preview: {result[:100]}...")
                return True
            else:
                print(f"  ❌ Unexpected result: {result}")
                return False
    finally:
        # Clean up
        os.unlink(temp_db.name)


def test_idempotency():
    """Test that registering the tool twice doesn't cause issues."""
    print("\n🧪 Test 4: Idempotency...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the tool twice
        success1 = register_resource_bridge_tool(database_url=db_url)
        success2 = register_resource_bridge_tool(database_url=db_url)
        
        if success1 and success2:
            print("  ✅ Tool can be registered multiple times (idempotent)")
            return True
        else:
            print("  ❌ Tool registration failed on second attempt")
            return False
    finally:
        # Clean up
        os.unlink(temp_db.name)


def test_missing_uri_parameter():
    """Test error handling when uri parameter is missing."""
    print("\n🧪 Test 5: Missing uri parameter...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Set up database and tool
        engine = get_engine(db_url)
        create_db_and_tables(engine)
        
        # Register the tool
        success = register_resource_bridge_tool(database_url=db_url)
        if not success:
            print("  ❌ Tool registration failed")
            return False
        
        # Execute the tool without uri parameter
        with Session(engine) as session:
            result = execute_tool(
                tool_name='read_resource',
                persona='default',
                arguments={},
                db_session=session
            )
            
            if "Error: 'uri' parameter is required" in result:
                print("  ✅ Missing parameter handled correctly")
                return True
            else:
                print(f"  ❌ Unexpected result: {result}")
                return False
    finally:
        # Clean up
        os.unlink(temp_db.name)


def main():
    """Run all tests."""
    print("=" * 60)
    print("Resource Bridge Tool Test Suite")
    print("=" * 60)
    
    tests = [
        ("Tool registration", test_tool_registration),
        ("Read existing resource", test_read_existing_resource),
        ("Resource not found with discovery", test_resource_not_found_with_discovery),
        ("Idempotency", test_idempotency),
        ("Missing uri parameter", test_missing_uri_parameter),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
