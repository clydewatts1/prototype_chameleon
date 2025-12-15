from base import ChameleonTool
from sqlmodel import select
import hashlib
import json

class SqlCreatorTool(ChameleonTool):
    def run(self, arguments):
        '''
        Create a new SQL-based tool with security validation.
        
        Args:
            tool_name: Name of the tool to create (e.g., "get_high_value_customers")
            description: Description of what the tool does
            sql_query: The SQL SELECT statement (must start with SELECT)
            parameters: Dictionary describing the parameters for the input schema
                       Format: {"param_name": {"type": "string", "description": "...", "required": True/False}}
        
        Returns:
            Success message confirming the tool is registered
        '''
        from models import CodeVault, ToolRegistry
        
        # Extract arguments
        tool_name = arguments.get('tool_name')
        description = arguments.get('description')
        sql_query = arguments.get('sql_query')
        parameters = arguments.get('parameters', {})
        
        # Validation 1: Check all required arguments are provided
        if not tool_name:
            return "Error: tool_name is required"
        if not description:
            return "Error: description is required"
        if not sql_query:
            return "Error: sql_query is required"
        
        # Validation 2: Ensure sql_query starts with SELECT (case-insensitive)
        sql_stripped = sql_query.strip()
        sql_upper = sql_stripped.upper()
        
        # Remove SQL comments before checking
        import re
        sql_cleaned = re.sub(r'--[^\n]*', '', sql_upper)  # Single-line comments
        sql_cleaned = re.sub(r'/\*.*?\*/', '', sql_cleaned, flags=re.DOTALL)  # Multi-line comments
        sql_cleaned = sql_cleaned.strip()
        
        if not sql_cleaned.startswith('SELECT'):
            return f"Error: sql_query must start with SELECT. Got: {sql_stripped[:50]}..."
        
        # Validation 3: Check for semicolons (to prevent chaining DROP statements)
        # Remove all SQL comments first to prevent comment-based bypasses
        sql_no_comments = re.sub(r'--[^\n]*', '', sql_stripped)  # Single-line comments
        sql_no_comments = re.sub(r'/\*.*?\*/', '', sql_no_comments, flags=re.DOTALL)  # Multi-line comments
        
        # Allow trailing semicolons only, not in the middle
        sql_no_trailing = sql_no_comments.rstrip().rstrip(';').rstrip()
        if ';' in sql_no_trailing:
            return "Error: sql_query cannot contain semicolons (;) in the middle. Only single statements are allowed."
        
        self.log(f"Creating SQL tool: {tool_name}")
        self.log(f"SQL Query validation passed")
        
        # Compute SHA-256 hash of the sql_query
        code_hash = hashlib.sha256(sql_query.encode('utf-8')).hexdigest()
        
        try:
            # Upsert into CodeVault with code_type='select'
            statement = select(CodeVault).where(CodeVault.hash == code_hash)
            existing_code = self.db_session.exec(statement).first()
            
            if existing_code:
                self.log(f"Code already exists in CodeVault (hash: {code_hash[:16]}...)")
                # Update code_type to ensure it's 'select'
                existing_code.code_type = 'select'
                self.db_session.add(existing_code)
            else:
                code_vault = CodeVault(
                    hash=code_hash,
                    code_blob=sql_query,
                    code_type='select'  # Force code_type to 'select'
                )
                self.db_session.add(code_vault)
                self.log(f"Code registered in CodeVault (hash: {code_hash[:16]}...)")
            
            # Construct input_schema from parameters argument
            properties = {}
            required_params = []
            
            for param_name, param_def in parameters.items():
                param_type = param_def.get('type', 'string')
                param_desc = param_def.get('description', '')
                param_required = param_def.get('required', False)
                
                properties[param_name] = {
                    'type': param_type,
                    'description': param_desc
                }
                
                if param_required:
                    required_params.append(param_name)
            
            input_schema = {
                'type': 'object',
                'properties': properties,
                'required': required_params
            }
            
            # Upsert into ToolRegistry (default persona)
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == tool_name,
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = self.db_session.exec(statement).first()
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = description
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = code_hash
                existing_tool.is_auto_created = True
                self.db_session.add(existing_tool)
                self.log(f"Tool '{tool_name}' updated in ToolRegistry")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name=tool_name,
                    target_persona='default',
                    description=description,
                    input_schema=input_schema,
                    active_hash_ref=code_hash,
                    is_auto_created=True
                )
                self.db_session.add(tool)
                self.log(f"Tool '{tool_name}' created in ToolRegistry")
            
            # Commit changes
            self.db_session.commit()
            
            return f"Success: Tool '{tool_name}' has been registered and is ready to use. The tool accepts parameters: {list(parameters.keys())}"
            
        except Exception as e:
            self.db_session.rollback()
            return f"Error: Failed to register tool - {type(e).__name__}: {str(e)}"
