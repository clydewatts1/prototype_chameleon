from base import ChameleonTool
from common.hash_utils import compute_hash
import re


class CreateTempTestTool(ChameleonTool):
    """
    Create a temporary test tool that is not persisted to the database.
    
    Temporary tools are stored in memory only and are useful for:
    - Testing and debugging SQL queries
    - Experimenting with query structures
    - Rapid iteration without cluttering the permanent tool registry
    
    Key features:
    - Automatic LIMIT 3 constraint for SQL tools (prevents large data retrieval)
    - SELECT-only validation
    - Not persisted to database
    - Available during runtime only
    """
    
    def run(self, arguments):
        """
        Create a new temporary SQL-based test tool.
        
        Args:
            tool_name: Name of the temporary tool (e.g., "test_sales")
            sql_query: The SQL SELECT statement (must start with SELECT)
            description: Description of what the tool does
            parameters: Dictionary describing the parameters for the input schema
                       Format: {"param_name": {"type": "string", "description": "...", "required": True/False}}
        
        Returns:
            Success message confirming the temporary tool is registered
        """
        # Import here to avoid circular imports
        # runtime module is in the same search path due to how tools are loaded
        from runtime import TEMP_TOOL_REGISTRY, TEMP_CODE_VAULT
        
        # Extract arguments
        tool_name = arguments.get('tool_name')
        sql_query = arguments.get('sql_query')
        description = arguments.get('description')
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
        
        # Validation 4: Check if LIMIT is already present
        if re.search(r'\bLIMIT\b', sql_cleaned):
             return "Error: Do not include LIMIT clause. Test tools automatically enforce LIMIT 3."
             
        # Enforce LIMIT 3
        # Strip trailing semicolon and append LIMIT 3
        sql_query = sql_query.strip().rstrip(';') + " LIMIT 3"
        
        self.log(f"Creating temporary test tool: {tool_name}")
        self.log(f"SQL Query validation passed. Auto-appended LIMIT 3.")
        
        # Compute SHA-256 hash of the sql_query
        code_hash = compute_hash(sql_query)
        
        try:
            # Store code in TEMP_CODE_VAULT
            TEMP_CODE_VAULT[code_hash] = {
                'code_blob': sql_query,
                'code_type': 'select'
            }
            self.log(f"Code stored in temporary vault (hash: {code_hash[:16]}...)")
            
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
            
            # Store tool metadata in TEMP_TOOL_REGISTRY
            # Use "tool_name:persona" as key to support persona filtering
            persona = self.context.get('persona', 'default')
            temp_key = f"{tool_name}:{persona}"
            
            TEMP_TOOL_REGISTRY[temp_key] = {
                'description': description,
                'input_schema': input_schema,
                'target_persona': persona,
                'code_hash': code_hash,
                'is_temp': True
            }
            self.log(f"Temporary tool '{tool_name}' registered for persona '{persona}'")
            
            return (
                f"Success: Temporary test tool '{tool_name}' has been registered and is ready to use.\n"
                f"The tool accepts parameters: {list(parameters.keys())}\n"
                f"NOTE: This is a TEMPORARY tool with automatic LIMIT 3 constraint.\n"
                f"It will return at most 3 rows and is not persisted to the database."
            )
            
        except Exception as e:
            return f"Error: Failed to register temporary tool - {type(e).__name__}: {str(e)}"
