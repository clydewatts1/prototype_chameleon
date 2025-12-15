#!/usr/bin/env python3
"""
Demonstration of the Deep Execution Audit System for AI Self-Debugging.

This script demonstrates the "Black Box" Recorder pattern workflow:
1. AI creates a broken tool (fibonacci with a bug)
2. AI tests the tool and it fails
3. AI uses get_last_error to retrieve the full stack trace
4. AI can analyze the error and fix the code

This is the workflow described in the problem statement.
"""

import hashlib
from sqlmodel import Session
from models import CodeVault, ToolRegistry, get_engine
from runtime import execute_tool
from config import load_config


def _compute_hash(code: str) -> str:
    """Compute SHA-256 hash of code."""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def demo_self_healing_workflow():
    """
    Demonstrate the self-healing workflow with the ExecutionLog system.
    """
    print("=" * 70)
    print("DEMO: Deep Execution Audit System - AI Self-Debugging Workflow")
    print("=" * 70)
    
    # Load database URL from config
    config = load_config()
    database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    engine = get_engine(database_url)
    
    with Session(engine) as session:
        print("\n📝 Step 1: AI creates a fibonacci tool (with a bug)")
        print("-" * 70)
        
        # Simulate AI creating a broken fibonacci tool
        broken_fibonacci_code = """from base import ChameleonTool

class FibonacciTool(ChameleonTool):
    def run(self, arguments):
        n = arguments.get('n', 10)
        # Broken: This will cause ZeroDivisionError
        return self.fibonacci(n) / 0
    
    def fibonacci(self, n):
        if n <= 1:
            return n
        return self.fibonacci(n-1) + self.fibonacci(n-2)
"""
        
        print("Code created:")
        print(broken_fibonacci_code)
        
        fib_hash = _compute_hash(broken_fibonacci_code)
        
        # Add to database
        code_vault = CodeVault(
            hash=fib_hash,
            code_blob=broken_fibonacci_code,
            code_type="python"
        )
        session.add(code_vault)
        
        tool_registry = ToolRegistry(
            tool_name="fibonacci",
            target_persona="default",
            description="Calculate fibonacci number (has a bug)",
            input_schema={
                "type": "object",
                "properties": {
                    "n": {
                        "type": "number",
                        "description": "The position in fibonacci sequence"
                    }
                },
                "required": ["n"]
            },
            active_hash_ref=fib_hash
        )
        session.add(tool_registry)
        session.commit()
        
        print("\n✅ Tool 'fibonacci' created and registered")
        
        print("\n🧪 Step 2: AI tests the tool with fibonacci(n=10)")
        print("-" * 70)
        
        try:
            result = execute_tool("fibonacci", "default", {"n": 10}, session)
            print(f"Result: {result}")
        except Exception as e:
            print(f"❌ Error: Execution failed")
            print(f"   Exception type: {type(e).__name__}")
            print(f"   Exception message: {e}")
            print("\n⚠️  AI receives generic error. Not enough information to fix!")
        
        print("\n🔍 Step 3: AI uses get_last_error to get detailed information")
        print("-" * 70)
        
        try:
            error_info = execute_tool(
                "get_last_error", 
                "default", 
                {"tool_name": "fibonacci"}, 
                session
            )
            print(error_info)
        except Exception as e:
            print(f"❌ Failed to get error info: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n💡 Step 4: AI analyzes the traceback")
        print("-" * 70)
        print("Analysis:")
        print("  - Error type: ZeroDivisionError")
        print("  - Location: In the run() method")
        print("  - Line: 'return self.fibonacci(n) / 0'")
        print("  - Root cause: Dividing by zero")
        print("  - Fix: Remove the '/ 0' operation")
        
        print("\n🔧 Step 5: AI fixes the code")
        print("-" * 70)
        
        fixed_fibonacci_code = """from base import ChameleonTool

class FibonacciTool(ChameleonTool):
    def run(self, arguments):
        n = arguments.get('n', 10)
        # Fixed: Removed the division by zero
        return self.fibonacci(n)
    
    def fibonacci(self, n):
        if n <= 1:
            return n
        return self.fibonacci(n-1) + self.fibonacci(n-2)
"""
        
        print("Fixed code:")
        print(fixed_fibonacci_code)
        
        fixed_hash = _compute_hash(fixed_fibonacci_code)
        
        # Add fixed code to database
        fixed_code_vault = CodeVault(
            hash=fixed_hash,
            code_blob=fixed_fibonacci_code,
            code_type="python"
        )
        session.add(fixed_code_vault)
        
        # Update tool registry to point to fixed code
        tool = session.get(ToolRegistry, ("fibonacci", "default"))
        tool.active_hash_ref = fixed_hash
        session.commit()
        
        print("\n✅ Code updated in CodeVault")
        
        print("\n✅ Step 6: AI tests the fixed tool")
        print("-" * 70)
        
        try:
            result = execute_tool("fibonacci", "default", {"n": 10}, session)
            print(f"✅ Success! Result: {result}")
            print("\n🎉 The tool is now working correctly!")
        except Exception as e:
            print(f"❌ Still failing: {e}")
        
        print("\n📊 Step 7: Check execution logs")
        print("-" * 70)
        
        # Query execution logs
        from sqlmodel import select
        from models import ExecutionLog
        
        logs = session.exec(
            select(ExecutionLog)
            .where(ExecutionLog.tool_name == "fibonacci")
            .order_by(ExecutionLog.timestamp)
        ).all()
        
        print(f"\nTotal executions logged: {len(logs)}")
        for i, log in enumerate(logs, 1):
            print(f"\n  Execution {i}:")
            print(f"    Status: {log.status}")
            print(f"    Time: {log.timestamp}")
            print(f"    Arguments: {log.arguments}")
            if log.status == "SUCCESS":
                print(f"    Result: {log.result_summary}")
        
        print("\n" + "=" * 70)
        print("✅ DEMO COMPLETE: Self-Healing Workflow Successful!")
        print("=" * 70)
        print("\nKey Benefits:")
        print("  ✓ Full Python tracebacks captured for every failure")
        print("  ✓ AI can query detailed error information")
        print("  ✓ Exact line numbers and error types available")
        print("  ✓ AI can patch tool code based on precise diagnostics")
        print("  ✓ All executions logged for audit trail")


if __name__ == "__main__":
    demo_self_healing_workflow()
