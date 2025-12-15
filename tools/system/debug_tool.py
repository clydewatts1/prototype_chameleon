from base import ChameleonTool
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
        output.append(f"\nTraceback:")
        output.append(result.error_traceback or "No traceback available")
        
        return "\n".join(output)
