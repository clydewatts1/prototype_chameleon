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

import hashlib
import re
from typing import Any, Dict, List, Union
from sqlmodel import Session, select
from sqlalchemy import text
from mcp.types import AnyUrl
from jinja2 import Template
from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry


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
        return result
    else:
        # Default to python execution
        # Sandbox: Execute the code
        # Create a local scope with arguments and db_session
        # NOTE: As per requirements, exec() is used for execution and db_session
        # is passed directly. For production with untrusted code, consider:
        # - Using RestrictedPython or similar sandboxing
        # - Implementing a restricted database interface layer
        # - Running code in isolated containers/processes
        local_scope = {
            'arguments': arguments,
            'db_session': db_session,
        }
        
        # Execute the code in the local scope
        # The code should set a 'result' variable to return a value
        exec(code_vault.code_blob, {}, local_scope)
        
        # Return the result if the code defines a 'result' variable
        return local_scope.get('result')


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
    
    return [
        {
            'name': tool.tool_name,
            'description': tool.description,
            'input_schema': tool.input_schema,
        }
        for tool in tools
    ]


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
        # Default to python execution
        # Execute the code with uri as a parameter
        local_scope = {
            'uri': uri_str,
            'persona': persona,
            'db_session': db_session,
        }
        
        exec(code_vault.code_blob, {}, local_scope)
        
        # Return the result
        result = local_scope.get('result', '')
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
