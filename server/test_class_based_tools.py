#!/usr/bin/env python3
"""
Test suite for class-based plugin architecture.

This test validates:
1. validate_code_structure security function
2. Class instantiation and execution
3. ChameleonTool inheritance
4. Integration with existing SQL tools
"""

import sys
from datetime import date, timedelta
from sqlmodel import Session, create_engine, SQLModel
from models import CodeVault, ToolRegistry, ResourceRegistry
from runtime import (
    execute_tool, 
    get_resource,
    validate_code_structure,
    SecurityError, 
    ToolNotFoundError
)
import hashlib


def _compute_hash(code: str) -> str:
    """Compute SHA-256 hash of code."""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def setup_test_database():
    """Create a test database."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


def test_validate_code_structure_allows_valid():
    """Test that valid class-based code is allowed."""
    print("\n🧪 Test 1: Valid class-based code is allowed...")
    
    valid_code = """from base import ChameleonTool

class MyTool(ChameleonTool):
    def run(self, arguments):
        return "Hello"
"""
    
    try:
        validate_code_structure(valid_code)
        print("  ✅ Valid code structure accepted")
        return True
    except SecurityError as e:
        print(f"  ❌ Valid code rejected: {e}")
        return False


def test_validate_code_structure_blocks_top_level_exec():
    """Test that top-level executable code is blocked."""
    print("\n🧪 Test 2: Top-level executable code is blocked...")
    
    invalid_codes = [
        ("variable assignment", "x = 5"),
        ("function call", "print('hello')"),
        ("expression", "5 + 5"),
        ("function definition", "def foo(): pass"),
    ]
    
    for name, code in invalid_codes:
        try:
            validate_code_structure(code)
            print(f"  ❌ {name} was NOT blocked!")
            return False
        except SecurityError:
            print(f"  ✅ {name} correctly blocked")
    
    return True


def test_validate_code_structure_allows_imports():
    """Test that imports are allowed."""
    print("\n🧪 Test 3: Imports are allowed...")
    
    code_with_imports = """import os
from datetime import datetime
from base import ChameleonTool

class MyTool(ChameleonTool):
    def run(self, arguments):
        return datetime.now()
"""
    
    try:
        validate_code_structure(code_with_imports)
        print("  ✅ Code with imports accepted")
        return True
    except SecurityError as e:
        print(f"  ❌ Code with imports rejected: {e}")
        return False


def test_class_instantiation_and_execution():
    """Test that class-based tools can be instantiated and executed."""
    print("\n🧪 Test 4: Class-based tools can be instantiated and executed...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
        # Create a simple class-based tool
        tool_code = """from base import ChameleonTool

class GreetTool(ChameleonTool):
    def run(self, arguments):
        name = arguments.get('name', 'World')
        return f"Hello {name}!"
"""
        tool_hash = _compute_hash(tool_code)
        
        code_vault = CodeVault(
            hash=tool_hash,
            code_blob=tool_code,
            code_type="python"
        )
        session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_greet",
            target_persona="default",
            description="Test greeting tool",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=tool_hash
        )
        session.add(tool)
        session.commit()
        
        # Execute the tool
        result = execute_tool("test_greet", "default", {"name": "Alice"}, session)
        
        if result == "Hello Alice!":
            print("  ✅ Class-based tool executed successfully")
            return True
        else:
            print(f"  ❌ Unexpected result: {result}")
            return False


def test_tool_with_db_session_access():
    """Test that tools can access db_session."""
    print("\n🧪 Test 5: Tools can access db_session...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
        # Create a tool that uses db_session
        tool_code = """from base import ChameleonTool
from sqlmodel import select
from models import ToolRegistry

class DbTool(ChameleonTool):
    def run(self, arguments):
        # Query the database to count tools
        statement = select(ToolRegistry)
        tools = self.db_session.exec(statement).all()
        return f"Found {len(tools)} tools"
"""
        tool_hash = _compute_hash(tool_code)
        
        code_vault = CodeVault(
            hash=tool_hash,
            code_blob=tool_code,
            code_type="python"
        )
        session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_db",
            target_persona="default",
            description="Test database access",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=tool_hash
        )
        session.add(tool)
        session.commit()
        
        # Execute the tool
        result = execute_tool("test_db", "default", {}, session)
        
        if "Found 1 tools" in result:
            print("  ✅ Tool accessed db_session successfully")
            return True
        else:
            print(f"  ❌ Unexpected result: {result}")
            return False


def test_tool_with_context_access():
    """Test that tools can access context."""
    print("\n🧪 Test 6: Tools can access context...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
        # Create a tool that uses context
        tool_code = """from base import ChameleonTool

class ContextTool(ChameleonTool):
    def run(self, arguments):
        persona = self.context.get('persona', 'unknown')
        tool_name = self.context.get('tool_name', 'unknown')
        return f"Running as {persona} with tool {tool_name}"
"""
        tool_hash = _compute_hash(tool_code)
        
        code_vault = CodeVault(
            hash=tool_hash,
            code_blob=tool_code,
            code_type="python"
        )
        session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_context",
            target_persona="test_persona",
            description="Test context access",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=tool_hash
        )
        session.add(tool)
        session.commit()
        
        # Execute the tool
        result = execute_tool("test_context", "test_persona", {}, session)
        
        if "Running as test_persona with tool test_context" in result:
            print("  ✅ Tool accessed context successfully")
            return True
        else:
            print(f"  ❌ Unexpected result: {result}")
            return False


def test_tool_with_log_method():
    """Test that tools can use the log method."""
    print("\n🧪 Test 7: Tools can use log method...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
        # Create a tool that uses log
        tool_code = """from base import ChameleonTool

class LogTool(ChameleonTool):
    def run(self, arguments):
        self.log("This is a log message")
        return "Done"
"""
        tool_hash = _compute_hash(tool_code)
        
        code_vault = CodeVault(
            hash=tool_hash,
            code_blob=tool_code,
            code_type="python"
        )
        session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_log",
            target_persona="default",
            description="Test log method",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=tool_hash
        )
        session.add(tool)
        session.commit()
        
        # Execute the tool (log output goes to stdout)
        result = execute_tool("test_log", "default", {}, session)
        
        if result == "Done":
            print("  ✅ Tool used log method successfully")
            return True
        else:
            print(f"  ❌ Unexpected result: {result}")
            return False


def test_missing_chameleon_tool_inheritance():
    """Test that code without ChameleonTool inheritance is rejected."""
    print("\n🧪 Test 8: Code without ChameleonTool inheritance is rejected...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
        # Create code without ChameleonTool inheritance
        tool_code = """from base import ChameleonTool

class NotATool:
    def run(self, arguments):
        return "This should fail"
"""
        tool_hash = _compute_hash(tool_code)
        
        code_vault = CodeVault(
            hash=tool_hash,
            code_blob=tool_code,
            code_type="python"
        )
        session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_no_inherit",
            target_persona="default",
            description="Test missing inheritance",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=tool_hash
        )
        session.add(tool)
        session.commit()
        
        # Execute the tool - should fail
        try:
            execute_tool("test_no_inherit", "default", {}, session)
            print("  ❌ Code without ChameleonTool inheritance was NOT rejected!")
            return False
        except SecurityError as e:
            if "No class inheriting from ChameleonTool" in str(e):
                print("  ✅ Code without ChameleonTool inheritance correctly rejected")
                return True
            else:
                print(f"  ❌ Wrong error: {e}")
                return False


def test_dynamic_resource_with_class():
    """Test that dynamic resources work with class-based code."""
    print("\n🧪 Test 9: Dynamic resources work with class-based code...")
    
    engine = setup_test_database()
    
    with Session(engine) as session:
        # Create a class-based resource
        resource_code = """from base import ChameleonTool

class TimeResource(ChameleonTool):
    def run(self, arguments):
        uri = arguments.get('uri', 'unknown')
        return f"Resource at {uri}"
"""
        resource_hash = _compute_hash(resource_code)
        
        code_vault = CodeVault(
            hash=resource_hash,
            code_blob=resource_code,
            code_type="python"
        )
        session.add(code_vault)
        
        resource = ResourceRegistry(
            uri_schema="test://example",
            name="test_resource",
            description="Test resource",
            mime_type="text/plain",
            is_dynamic=True,
            static_content=None,
            active_hash_ref=resource_hash,
            target_persona="default"
        )
        session.add(resource)
        session.commit()
        
        # Get the resource
        result = get_resource("test://example", "default", session)
        
        if "Resource at test://example" in result:
            print("  ✅ Dynamic resource executed successfully")
            return True
        else:
            print(f"  ❌ Unexpected result: {result}")
            return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Class-Based Plugin Architecture Tests")
    print("=" * 60)
    
    tests = [
        test_validate_code_structure_allows_valid,
        test_validate_code_structure_blocks_top_level_exec,
        test_validate_code_structure_allows_imports,
        test_class_instantiation_and_execution,
        test_tool_with_db_session_access,
        test_tool_with_context_access,
        test_tool_with_log_method,
        test_missing_chameleon_tool_inheritance,
        test_dynamic_resource_with_class,
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
        print("✅ All class-based architecture tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
