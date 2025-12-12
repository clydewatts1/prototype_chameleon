"""
Script to add the get_last_error debugging tool to the database.

This tool enables AI self-debugging by querying the ExecutionLog table
for detailed error information including full Python tracebacks.
"""

import hashlib
from sqlmodel import Session, select
from models import CodeVault, ToolRegistry, get_engine


def _compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def add_debug_tool(database_url: str = "sqlite:///chameleon.db"):
    """
    Add the get_last_error debugging tool to the database.
    
    Args:
        database_url: Database connection string
    """
    engine = get_engine(database_url)
    
    print("=" * 60)
    print("Adding get_last_error Debugging Tool")
    print("=" * 60)
    
    with Session(engine) as session:
        # Define the get_last_error tool code
        get_last_error_code = """from base import ChameleonTool
from sqlmodel import select
from models import ExecutionLog

class GetLastErrorTool(ChameleonTool):
    def run(self, arguments):
        tool_name = arguments.get('tool_name')
        
        # Build query for last error
        query = select(ExecutionLog).where(ExecutionLog.status == 'FAILURE')
        
        # Optional filter by tool_name
        if tool_name:
            query = query.where(ExecutionLog.tool_name == tool_name)
        
        # Order by timestamp descending and get the most recent
        query = query.order_by(ExecutionLog.timestamp.desc()).limit(1)
        
        # Execute query
        result = self.db_session.exec(query).first()
        
        if not result:
            if tool_name:
                return f"No errors found for tool '{tool_name}'"
            else:
                return "No errors found in execution log"
        
        # Format the result
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
        
        print("\n[1] Adding get_last_error tool code to CodeVault...")
        
        # Check if code already exists
        existing_code = session.exec(
            select(CodeVault).where(CodeVault.hash == get_last_error_hash)
        ).first()
        
        if not existing_code:
            code_vault = CodeVault(
                hash=get_last_error_hash,
                code_blob=get_last_error_code,
                code_type="python"
            )
            session.add(code_vault)
            print(f"   ✅ Code added (hash: {get_last_error_hash[:16]}...)")
        else:
            print(f"   ℹ️  Code already exists (hash: {get_last_error_hash[:16]}...)")
        
        print("\n[2] Registering get_last_error tool for 'default' persona...")
        
        # Check if tool already exists
        existing_tool = session.exec(
            select(ToolRegistry).where(
                ToolRegistry.tool_name == "get_last_error",
                ToolRegistry.target_persona == "default"
            )
        ).first()
        
        if not existing_tool:
            tool_registry = ToolRegistry(
                tool_name="get_last_error",
                target_persona="default",
                description="Get the last error from the execution log. Returns detailed error information including full Python traceback. Optionally filter by tool_name.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "Optional: Filter errors by specific tool name"
                        }
                    },
                    "required": []
                },
                active_hash_ref=get_last_error_hash
            )
            session.add(tool_registry)
            print(f"   ✅ Tool 'get_last_error' registered")
        else:
            # Update existing tool to point to new hash
            existing_tool.active_hash_ref = get_last_error_hash
            existing_tool.description = "Get the last error from the execution log. Returns detailed error information including full Python traceback. Optionally filter by tool_name."
            print(f"   ℹ️  Tool 'get_last_error' already exists, updated hash reference")
        
        # Commit changes
        session.commit()
        
        print("\n" + "=" * 60)
        print("✅ get_last_error tool added successfully!")
        print("=" * 60)
        print("\nUsage:")
        print("  - Get last error from any tool: get_last_error()")
        print("  - Get last error from specific tool: get_last_error(tool_name='fibonacci')")
        print("\nThis tool enables AI self-debugging by providing:")
        print("  - Full Python traceback")
        print("  - Exact line numbers and error types")
        print("  - Input arguments that caused the error")
        print("  - Timestamp of the failure")


if __name__ == "__main__":
    add_debug_tool()
