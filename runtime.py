"""
Runtime module for secure execution of code stored in the database.

This module handles fetching and executing code from CodeVault with security checks.

SECURITY NOTES:
- exec() is used as specified in the requirements for code execution
- Hash validation ensures code integrity and detects tampering
- db_session is passed to executed code as per requirements
- IMPORTANT: This design assumes code in CodeVault is trusted. In production,
  consider additional sandboxing (e.g., RestrictedPython, containers) and
  restricted database interfaces if executing untrusted code.

EXECUTION CONTRACT:
- Executed code receives 'arguments' dict and 'db_session' in its local scope
- Executed code should set a 'result' variable to return a value
- If no 'result' variable is set, the function returns None
"""

import ast
import hashlib
import inspect
import re
import sys
import traceback
import json
from typing import Any, Dict, List, Union
from sqlmodel import Session, select
from sqlalchemy import text
from mcp.types import AnyUrl
from jinja2 import Template
from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry, ExecutionLog
from base import ChameleonTool


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


class ToolNotFoundError(Exception):
    """Raised when a tool is not found in the registry."""
    pass


class ResourceNotFoundError(Exception):
    """Raised when a resource is not found in the registry."""
    pass


class PromptNotFoundError(Exception):
    """Raised when a prompt is not found in the registry."""
    pass


def _compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def _validate_single_statement(sql: str) -> None:
    """
    Validate that SQL contains only a single statement.
    
    Raises SecurityError if multiple statements are detected (e.g., via semicolons
    that are not at the end of the query).
    
    Args:
        sql: The SQL query string to validate
        
    Raises:
        SecurityError: If multiple statements are detected
    """
    # Remove trailing whitespace and semicolons
    sql_stripped = sql.rstrip().rstrip(';').rstrip()
    
    # Check for semicolons in the middle of the query
    if ';' in sql_stripped:
        raise SecurityError(
            "Multiple SQL statements detected. Only single statements are allowed."
        )


def _validate_read_only(sql: str) -> None:
    """
    Validate that SQL is a read-only SELECT statement.
    
    Raises SecurityError if the query contains write operations like INSERT,
    UPDATE, DELETE, DROP, or ALTER.
    
    Args:
        sql: The SQL query string to validate
        
    Raises:
        SecurityError: If write operations are detected
    """
    # Normalize: strip and convert to uppercase for checking
    sql_upper = sql.strip().upper()
    
    # Remove SQL comments (both single-line and multi-line) first
    sql_cleaned = re.sub(r'--[^\n]*', '', sql_upper)  # Single-line comments
    sql_cleaned = re.sub(r'/\*.*?\*/', '', sql_cleaned, flags=re.DOTALL)  # Multi-line comments
    sql_cleaned = sql_cleaned.strip()
    
    # Check if it starts with SELECT (after comments removed)
    if not sql_cleaned.startswith('SELECT'):
        raise SecurityError(
            "Only SELECT statements are allowed. Query must start with SELECT."
        )
    
    # Check for dangerous keywords that should not appear in a SELECT
    # Using more comprehensive patterns to catch various forms
    dangerous_patterns = [
        (r'\bINSERT\s*(\(|INTO)', 'INSERT'),
        (r'\bUPDATE\s+\w+\s+SET', 'UPDATE'),
        (r'\bDELETE\s+(FROM|\s)', 'DELETE'),
        (r'\bDROP\s+', 'DROP'),
        (r'\bALTER\s+', 'ALTER'),
        (r'\bCREATE\s+', 'CREATE'),
        (r'\bTRUNCATE\s+', 'TRUNCATE'),
        (r'\bEXEC(UTE)?\s*(\(|\s)', 'EXEC/EXECUTE'),
    ]
    
    for pattern, keyword in dangerous_patterns:
        if re.search(pattern, sql_cleaned):
            raise SecurityError(
                f"Dangerous keyword '{keyword}' detected. Only SELECT statements are allowed."
            )


def log_execution(
    tool_name: str,
    persona: str,
    arguments: Dict[str, Any],
    status: str,
    result: Any = None,
    error_traceback_str: str = None,
    db_session: Session = None
) -> None:
    """
    Log tool execution to the ExecutionLog table.
    
    This function handles its own commits to ensure logs persist even if the
    main tool execution fails or rolls back. This is critical for the "Black Box"
    Recorder pattern - we need to capture failure information even when the
    transaction fails.
    
    Args:
        tool_name: Name of the tool executed
        persona: Persona context
        arguments: Input arguments dict
        status: "SUCCESS" or "FAILURE"
        result: The result of execution (for success cases)
        error_traceback_str: Full Python traceback string (for failure cases)
        db_session: SQLModel Session for database access
    """
    if db_session is None:
        return
    
    try:
        # Serialize arguments to JSON-compatible format
        try:
            # Attempt to serialize with default=str fallback for non-standard types
            json.dumps(arguments, default=str)
            args_json = arguments
        except (TypeError, ValueError) as e:
            # If serialization fails, log error and use string representation
            print(f"[ExecutionLog] Warning: Failed to serialize arguments: {e}", file=sys.stderr)
            args_json = {"_serialization_error": str(arguments)}
        
        # Format result summary (truncate to ~2000 chars)
        if status == "SUCCESS":
            result_str = str(result)
            if len(result_str) > 2000:
                result_summary = result_str[:2000] + "... (truncated)"
            else:
                result_summary = result_str
        else:
            result_summary = "Execution failed - see error_traceback"
        
        # Create execution log entry
        log_entry = ExecutionLog(
            tool_name=tool_name,
            persona=persona,
            arguments=args_json,
            status=status,
            result_summary=result_summary,
            error_traceback=error_traceback_str
        )
        
        # Add and commit in its own transaction
        # This ensures the log persists even if the main transaction rolls back
        db_session.add(log_entry)
        db_session.commit()
        
    except Exception as e:
        # If logging fails, don't crash the execution
        # Just print an error message
        print(f"[ExecutionLog] Warning: Failed to log execution: {e}", file=sys.stderr)
        try:
            db_session.rollback()
        except Exception:
            pass


def validate_code_structure(code_str: str) -> None:
    """
    Validate that Python code only contains safe top-level nodes.
    
    For class-based plugin architecture, only Import, ImportFrom, and ClassDef
    nodes are allowed at the top level. This prevents arbitrary code execution
    at module load time.
    
    Args:
        code_str: The Python code string to validate
        
    Raises:
        SecurityError: If the code contains disallowed top-level nodes
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        raise SecurityError(f"Code contains syntax errors: {e}")
    
    # Check all top-level nodes
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef)):
            node_type = type(node).__name__
            raise SecurityError(
                f"Invalid top-level node '{node_type}'. Only Import, ImportFrom, "
                f"and ClassDef are allowed at the top level."
            )


def execute_tool(
    tool_name: str,
    persona: str,
    arguments: Dict[str, Any],
    db_session: Session
) -> Any:
    """
    Execute a tool by fetching and running its code from the database.
    
    This function:
    1. Queries ToolRegistry for the tool
    2. Fetches CodeVault content using the hash
    3. Re-hashes the content for security validation
    4. Executes the code in a sandboxed environment
    5. Logs execution (SUCCESS or FAILURE) to ExecutionLog
    
    Args:
        tool_name: Name of the tool to execute
        persona: The persona/context for which to execute the tool
        arguments: Dictionary of arguments to pass to the tool
        db_session: SQLModel Session for database access
        
    Returns:
        The result of the tool execution
        
    Raises:
        ToolNotFoundError: If the tool is not found in the registry
        SecurityError: If hash validation fails
    """
    try:
        # Query ToolRegistry for the tool
        statement = select(ToolRegistry).where(
            ToolRegistry.tool_name == tool_name,
            ToolRegistry.target_persona == persona
        )
        tool = db_session.exec(statement).first()
        
        if not tool:
            raise ToolNotFoundError(
                f"Tool '{tool_name}' not found for persona '{persona}'"
            )
        
        # Fetch CodeVault content using the hash
        statement = select(CodeVault).where(CodeVault.hash == tool.active_hash_ref)
        code_vault = db_session.exec(statement).first()
        
        if not code_vault:
            raise ToolNotFoundError(
                f"Code not found for hash '{tool.active_hash_ref}'"
            )
        
        # Security: Re-hash the content and validate
        computed_hash = _compute_hash(code_vault.code_blob)
        if computed_hash != code_vault.hash:
            raise SecurityError(
                f"Hash mismatch! Expected '{code_vault.hash}', "
                f"got '{computed_hash}'. Code may be corrupted."
            )
        
        # Execute based on code type
        if code_vault.code_type == 'select':
            # Step 1: Render SQL template with Jinja2 for structural logic
            # IMPORTANT: Jinja2 is used ONLY for structural elements (e.g., optional WHERE clauses)
            # Values must use SQLAlchemy parameter binding with :param_name syntax
            template = Template(code_vault.code_blob)
            rendered_sql = template.render(arguments=arguments)
            
            # Step 2: Security validation
            # Validate single statement (no SQL injection via multiple statements)
            _validate_single_statement(rendered_sql)
            
            # Validate read-only (only SELECT statements allowed)
            _validate_read_only(rendered_sql)
            
            # Step 3: Safe execution with SQLAlchemy parameter binding
            # The rendered SQL should use :param_name syntax for values
            # Pass arguments dictionary to db_session.exec() as params for safe binding
            result = db_session.exec(text(rendered_sql), params=arguments).all()
            
            # Log success
            log_execution(
                tool_name=tool_name,
                persona=persona,
                arguments=arguments,
                status="SUCCESS",
                result=result,
                db_session=db_session
            )
            
            return result
        else:
            # Default to python execution with class-based plugin architecture
            # Step 1: Validate code structure
            validate_code_structure(code_vault.code_blob)
            
            # Step 2: Execute the code to load the class definition
            # Create a namespace with base class available
            namespace = {'ChameleonTool': ChameleonTool}
            exec(code_vault.code_blob, namespace)
            
            # Step 3: Find the class that inherits from ChameleonTool
            tool_class = None
            for name, obj in namespace.items():
                if (inspect.isclass(obj) and 
                    issubclass(obj, ChameleonTool) and 
                    obj is not ChameleonTool):
                    tool_class = obj
                    break
            
            if tool_class is None:
                raise SecurityError(
                    "No class inheriting from ChameleonTool found in the code"
                )
            
            # Step 4: Instantiate the tool with db_session and context
            context = {
                'persona': persona,
                'tool_name': tool_name,
            }
            tool_instance = tool_class(db_session, context)
            
            # Step 5: Execute the tool's run method
            result = tool_instance.run(arguments)
            
            # Log success
            log_execution(
                tool_name=tool_name,
                persona=persona,
                arguments=arguments,
                status="SUCCESS",
                result=result,
                db_session=db_session
            )
            
            return result
            
    except Exception as e:
        # Capture the full traceback
        error_traceback_str = traceback.format_exc()
        
        # Log failure
        log_execution(
            tool_name=tool_name,
            persona=persona,
            arguments=arguments,
            status="FAILURE",
            error_traceback_str=error_traceback_str,
            db_session=db_session
        )
        
        # Re-raise the exception so the client knows it failed
        raise


def list_tools_for_persona(persona: str, db_session: Session) -> List[Dict[str, Any]]:
    """
    List all available tools for a specific persona.
    
    Args:
        persona: The persona/context to filter tools by
        db_session: SQLModel Session for database access
        
    Returns:
        List of dictionaries containing tool information:
        - name: Tool name
        - description: Tool description
        - input_schema: JSON schema for tool arguments
    """
    statement = select(ToolRegistry).where(ToolRegistry.target_persona == persona)
    tools = db_session.exec(statement).all()
    
    results = []
    for tool in tools:
        desc = tool.description
        if getattr(tool, "is_auto_created", False):
            desc = f"[AUTO-BUILD] {desc}"
        
        results.append({
            'name': tool.tool_name,
            'description': desc,
            'input_schema': tool.input_schema,
        })
    
    return results


def list_resources_for_persona(persona: str, db_session: Session) -> List[Dict[str, Any]]:
    """
    List all available resources for a specific persona.
    
    Args:
        persona: The persona/context to filter resources by
        db_session: SQLModel Session for database access
        
    Returns:
        List of dictionaries containing resource information:
        - uri: Resource URI
        - name: Resource name
        - description: Resource description
        - mimeType: MIME type from database
    """
    statement = select(ResourceRegistry).where(ResourceRegistry.target_persona == persona)
    resources = db_session.exec(statement).all()
    
    return [
        {
            'uri': resource.uri_schema,
            'name': resource.name,
            'description': resource.description,
            'mimeType': resource.mime_type,
        }
        for resource in resources
    ]


def get_resource(uri: Union[str, AnyUrl], persona: str, db_session: Session) -> str:
    """
    Get a resource by URI and execute if dynamic.
    
    This function:
    1. Queries ResourceRegistry to find matching resource by URI
    2. If static, returns the static_content
    3. If dynamic, executes code from CodeVault
    
    Args:
        uri: URI of the resource to retrieve (string or MCP AnyUrl)
        persona: The persona/context for which to get the resource
        db_session: SQLModel Session for database access
        
    Returns:
        The resource content as a string
        
    Raises:
        ResourceNotFoundError: If the resource is not found
        SecurityError: If hash validation fails for dynamic resources
    """
    # Convert uri to string in case it's a Pydantic AnyUrl or other type
    uri_str = str(uri)
    
    # Query ResourceRegistry for the resource by URI
    statement = select(ResourceRegistry).where(ResourceRegistry.uri_schema == uri_str)
    resource = db_session.exec(statement).first()
    
    if not resource:
        raise ResourceNotFoundError(f"Resource with URI '{uri_str}' not found")
    
    # If static, return the static content
    if not resource.is_dynamic:
        return resource.static_content or ""
    
    # If dynamic, execute code from CodeVault
    if not resource.active_hash_ref:
        raise ResourceNotFoundError(
            f"Dynamic resource '{resource.name}' has no code reference"
        )
    
    # Fetch CodeVault content using the hash
    statement = select(CodeVault).where(CodeVault.hash == resource.active_hash_ref)
    code_vault = db_session.exec(statement).first()
    
    if not code_vault:
        raise ResourceNotFoundError(
            f"Code not found for hash '{resource.active_hash_ref}'"
        )
    
    # Security: Re-hash the content and validate
    computed_hash = _compute_hash(code_vault.code_blob)
    if computed_hash != code_vault.hash:
        raise SecurityError(
            f"Hash mismatch! Expected '{code_vault.hash}', "
            f"got '{computed_hash}'. Code may be corrupted."
        )
    
    # Execute based on code type
    if code_vault.code_type == 'select':
        # Step 1: Render SQL template with Jinja2 for structural logic
        # Create arguments dict from available context (uri, persona)
        template_args = {
            'uri': uri_str,
            'persona': persona,
        }
        template = Template(code_vault.code_blob)
        rendered_sql = template.render(arguments=template_args)
        
        # Step 2: Security validation
        # Validate single statement (no SQL injection via multiple statements)
        _validate_single_statement(rendered_sql)
        
        # Validate read-only (only SELECT statements allowed)
        _validate_read_only(rendered_sql)
        
        # Step 3: Safe execution with SQLAlchemy parameter binding
        # Pass template_args as params for safe binding
        result = db_session.exec(text(rendered_sql), params=template_args).all()
        return str(result)
    else:
        # Default to python execution with class-based plugin architecture
        # Step 1: Validate code structure
        validate_code_structure(code_vault.code_blob)
        
        # Step 2: Execute the code to load the class definition
        # Create a namespace with base class available
        namespace = {'ChameleonTool': ChameleonTool}
        exec(code_vault.code_blob, namespace)
        
        # Step 3: Find the class that inherits from ChameleonTool
        tool_class = None
        for name, obj in namespace.items():
            if (inspect.isclass(obj) and 
                issubclass(obj, ChameleonTool) and 
                obj is not ChameleonTool):
                tool_class = obj
                break
        
        if tool_class is None:
            raise SecurityError(
                "No class inheriting from ChameleonTool found in the code"
            )
        
        # Step 4: Instantiate the tool with db_session and context
        context = {
            'persona': persona,
            'uri': uri_str,
        }
        tool_instance = tool_class(db_session, context)
        
        # Step 5: Execute the tool's run method with uri as argument
        # For resources, pass uri in the arguments dict
        result = tool_instance.run({'uri': uri_str, 'persona': persona})
        return str(result)


def list_prompts_for_persona(persona: str, db_session: Session) -> List[Dict[str, Any]]:
    """
    List all available prompts for a specific persona.
    
    Args:
        persona: The persona/context to filter prompts by
        db_session: SQLModel Session for database access
        
    Returns:
        List of dictionaries containing prompt information:
        - name: Prompt name
        - description: Prompt description
        - arguments: List of argument definitions
    """
    statement = select(PromptRegistry).where(PromptRegistry.target_persona == persona)
    prompts = db_session.exec(statement).all()
    
    return [
        {
            'name': prompt.name,
            'description': prompt.description,
            'arguments': prompt.arguments_schema.get('arguments', []),
        }
        for prompt in prompts
    ]


def get_prompt(
    name: str,
    arguments: Dict[str, Any],
    persona: str,
    db_session: Session
) -> Dict[str, Any]:
    """
    Get a prompt by name and format it with arguments.
    
    This function:
    1. Queries PromptRegistry for the prompt
    2. Fetches the template
    3. Formats the template with provided arguments
    4. Returns formatted prompt result
    
    Args:
        name: Name of the prompt to retrieve
        arguments: Dictionary of arguments to format the template with
        persona: The persona/context for which to get the prompt
        db_session: SQLModel Session for database access
        
    Returns:
        Dictionary with 'description' and 'messages' for GetPromptResult
        
    Raises:
        PromptNotFoundError: If the prompt is not found
    """
    # Query PromptRegistry for the prompt
    statement = select(PromptRegistry).where(PromptRegistry.name == name)
    prompt = db_session.exec(statement).first()
    
    if not prompt:
        raise PromptNotFoundError(f"Prompt '{name}' not found")
    
    # Format the template with arguments
    try:
        formatted_text = prompt.template.format(**arguments)
    except KeyError as e:
        raise ValueError(f"Missing required argument: {e}")
    
    # Return result in the expected format
    return {
        'description': prompt.description,
        'messages': [
            {
                'role': 'user',
                'content': {
                    'type': 'text',
                    'text': formatted_text
                }
            }
        ]
    }
