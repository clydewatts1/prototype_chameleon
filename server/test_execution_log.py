#!/usr/bin/env python3
"""
Test suite for ExecutionLog and Deep Execution Audit System.

This test validates:
1. ExecutionLog model creation
2. Successful tool execution logging
3. Failed tool execution logging with traceback
4. get_last_error tool functionality
"""

import sys
import tempfile
import os
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel, select
from models import CodeVault, ToolRegistry, ExecutionLog, get_engine, create_db_and_tables
from runtime import execute_tool, log_execution, ToolNotFoundError
import hashlib


def _compute_hash(code: str) -> str:
    """Compute SHA-256 hash of code."""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def test_execution_log_model():
    """Test that ExecutionLog model can be created and persisted."""
    print("\n🧪 Testing ExecutionLog model creation...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        engine = get_engine(f"sqlite:///{db_path}")
        create_db_and_tables(engine)
        
        with Session(engine) as session:
            # Create a test execution log entry
            log_entry = ExecutionLog(
                tool_name="test_tool",
                persona="default",
                arguments={"arg1": "value1", "arg2": 42},
                status="SUCCESS",
                result_summary="Test result",
                error_traceback=None
            )
            session.add(log_entry)
            session.commit()
            
            # Query it back
            retrieved = session.exec(select(ExecutionLog)).first()
            
            if retrieved:
                print(f"  ✅ ExecutionLog model created successfully")
                print(f"     ID: {retrieved.id}")
                print(f"     Tool: {retrieved.tool_name}")
                print(f"     Status: {retrieved.status}")
                print(f"     Timestamp: {retrieved.timestamp}")
                return True
            else:
                print(f"  ❌ Failed to retrieve ExecutionLog entry")
                return False
                
    except Exception as e:
        print(f"  ❌ Error testing ExecutionLog model: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_successful_execution_logging():
    """Test that successful tool execution is logged."""
    print("\n🧪 Testing successful execution logging...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        engine = get_engine(f"sqlite:///{db_path}")
        create_db_and_tables(engine)
        
        with Session(engine) as session:
            # Create a simple test tool
            test_code = """from base import ChameleonTool

class TestTool(ChameleonTool):
    def run(self, arguments):
        return f"Success: {arguments.get('value', 0) * 2}"
"""
            test_hash = _compute_hash(test_code)
            
            # Add to CodeVault
            code_vault = CodeVault(
                hash=test_hash,
                code_blob=test_code,
                code_type="python"
            )
            session.add(code_vault)
            
            # Register tool
            tool_registry = ToolRegistry(
                tool_name="test_success",
                target_persona="default",
                description="Test tool for success logging",
                input_schema={
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"}
                    }
                },
                active_hash_ref=test_hash
            )
            session.add(tool_registry)
            session.commit()
            
            # Execute the tool
            result = execute_tool("test_success", "default", {"value": 5}, session)
            
            # Check execution log
            log_entry = session.exec(
                select(ExecutionLog)
                .where(ExecutionLog.tool_name == "test_success")
                .where(ExecutionLog.status == "SUCCESS")
            ).first()
            
            if log_entry:
                print(f"  ✅ Successful execution logged")
                print(f"     Tool: {log_entry.tool_name}")
                print(f"     Status: {log_entry.status}")
                print(f"     Arguments: {log_entry.arguments}")
                print(f"     Result: {log_entry.result_summary}")
                return True
            else:
                print(f"  ❌ Execution log entry not found")
                return False
                
    except Exception as e:
        print(f"  ❌ Error testing successful execution logging: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_failed_execution_logging():
    """Test that failed tool execution is logged with traceback."""
    print("\n🧪 Testing failed execution logging with traceback...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        engine = get_engine(f"sqlite:///{db_path}")
        create_db_and_tables(engine)
        
        with Session(engine) as session:
            # Create a tool that will fail
            failing_code = """from base import ChameleonTool

class FailingTool(ChameleonTool):
    def run(self, arguments):
        # This will raise a ZeroDivisionError
        return 1 / 0
"""
            failing_hash = _compute_hash(failing_code)
            
            # Add to CodeVault
            code_vault = CodeVault(
                hash=failing_hash,
                code_blob=failing_code,
                code_type="python"
            )
            session.add(code_vault)
            
            # Register tool
            tool_registry = ToolRegistry(
                tool_name="test_failure",
                target_persona="default",
                description="Test tool for failure logging",
                input_schema={
                    "type": "object",
                    "properties": {}
                },
                active_hash_ref=failing_hash
            )
            session.add(tool_registry)
            session.commit()
            
            # Try to execute the tool (should fail)
            try:
                result = execute_tool("test_failure", "default", {}, session)
                print(f"  ❌ Tool execution should have failed but didn't")
                return False
            except ZeroDivisionError:
                # Expected - the tool should fail
                pass
            
            # Check execution log
            log_entry = session.exec(
                select(ExecutionLog)
                .where(ExecutionLog.tool_name == "test_failure")
                .where(ExecutionLog.status == "FAILURE")
            ).first()
            
            if log_entry:
                print(f"  ✅ Failed execution logged")
                print(f"     Tool: {log_entry.tool_name}")
                print(f"     Status: {log_entry.status}")
                print(f"     Arguments: {log_entry.arguments}")
                
                # Check that traceback is present and contains relevant info
                if log_entry.error_traceback:
                    if "ZeroDivisionError" in log_entry.error_traceback:
                        print(f"  ✅ Traceback contains error type")
                    else:
                        print(f"  ❌ Traceback missing error type")
                        return False
                    
                    if "return 1 / 0" in log_entry.error_traceback:
                        print(f"  ✅ Traceback contains error line")
                    else:
                        print(f"  ⚠️  Traceback might not contain exact error line (this is OK)")
                    
                    print(f"     Traceback preview: {log_entry.error_traceback[:200]}...")
                    return True
                else:
                    print(f"  ❌ Traceback is missing")
                    return False
            else:
                print(f"  ❌ Execution log entry not found")
                return False
                
    except Exception as e:
        print(f"  ❌ Error testing failed execution logging: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_get_last_error_tool():
    """Test the get_last_error debugging tool."""
    print("\n🧪 Testing get_last_error debugging tool...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        engine = get_engine(f"sqlite:///{db_path}")
        create_db_and_tables(engine)
        
        with Session(engine) as session:
            # Create a failing tool
            failing_code = """from base import ChameleonTool

class BrokenFibonacci(ChameleonTool):
    def run(self, arguments):
        # Broken fibonacci with recursion error
        n = arguments.get('n', 10)
        if n < 0:
            raise ValueError("n must be non-negative")
        return 1 / 0  # Intentional error
"""
            failing_hash = _compute_hash(failing_code)
            
            code_vault = CodeVault(
                hash=failing_hash,
                code_blob=failing_code,
                code_type="python"
            )
            session.add(code_vault)
            
            tool_registry = ToolRegistry(
                tool_name="fibonacci",
                target_persona="default",
                description="Broken fibonacci for testing",
                input_schema={
                    "type": "object",
                    "properties": {
                        "n": {"type": "number"}
                    }
                },
                active_hash_ref=failing_hash
            )
            session.add(tool_registry)
            
            # Add get_last_error tool
            get_last_error_code = """from base import ChameleonTool
from sqlmodel import select
from models import ExecutionLog

class GetLastErrorTool(ChameleonTool):
    def run(self, arguments):
        tool_name = arguments.get('tool_name')
        
        query = select(ExecutionLog).where(ExecutionLog.status == 'FAILURE')
        
        if tool_name:
            query = query.where(ExecutionLog.tool_name == tool_name)
        
        query = query.order_by(ExecutionLog.timestamp.desc()).limit(1)
        
        result = self.db_session.exec(query).first()
        
        if not result:
            if tool_name:
                return f"No errors found for tool '{tool_name}'"
            else:
                return "No errors found in execution log"
        
        output = []
        output.append(f"Last error for tool '{result.tool_name}':")
        output.append(f"Time: {result.timestamp}")
        output.append(f"Persona: {result.persona}")
        output.append(f"Input: {result.arguments}")
        output.append(f"\\nTraceback:")
        output.append(result.error_traceback or "No traceback available")
        
        return "\\n".join(output)
"""
            get_last_error_hash = _compute_hash(get_last_error_code)
            
            code_vault2 = CodeVault(
                hash=get_last_error_hash,
                code_blob=get_last_error_code,
                code_type="python"
            )
            session.add(code_vault2)
            
            tool_registry2 = ToolRegistry(
                tool_name="get_last_error",
                target_persona="default",
                description="Get last error from execution log",
                input_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string"}
                    }
                },
                active_hash_ref=get_last_error_hash
            )
            session.add(tool_registry2)
            session.commit()
            
            # Execute failing tool
            try:
                execute_tool("fibonacci", "default", {"n": 10}, session)
            except:
                pass  # Expected to fail
            
            # Now use get_last_error to retrieve the error
            error_info = execute_tool("get_last_error", "default", {"tool_name": "fibonacci"}, session)
            
            if error_info:
                print(f"  ✅ get_last_error tool executed successfully")
                
                # Check that error info contains expected elements
                if "fibonacci" in error_info:
                    print(f"  ✅ Error info contains tool name")
                else:
                    print(f"  ❌ Error info missing tool name")
                    return False
                
                if "ZeroDivisionError" in error_info or "Traceback" in error_info:
                    print(f"  ✅ Error info contains traceback")
                else:
                    print(f"  ❌ Error info missing traceback")
                    return False
                
                print(f"     Error info preview: {error_info[:300]}...")
                return True
            else:
                print(f"  ❌ get_last_error returned empty result")
                return False
                
    except Exception as e:
        print(f"  ❌ Error testing get_last_error tool: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def main():
    """Run all tests for ExecutionLog system."""
    print("=" * 60)
    print("Running ExecutionLog Deep Audit System Tests")
    print("=" * 60)
    
    tests = [
        test_execution_log_model,
        test_successful_execution_logging,
        test_failed_execution_logging,
        test_get_last_error_tool,
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
        print("✅ All ExecutionLog tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
