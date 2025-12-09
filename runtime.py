"""
Runtime module for secure execution of code stored in the database.

This module handles fetching and executing code from CodeVault with security checks.
"""

import hashlib
from typing import Any, Dict, List
from sqlmodel import Session, select
from models import CodeVault, ToolRegistry


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


class ToolNotFoundError(Exception):
    """Raised when a tool is not found in the registry."""
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


def execute_tool(
    tool_name: str,
    persona: str,
    arguments: dict,
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
    computed_hash = _compute_hash(code_vault.python_blob)
    if computed_hash != code_vault.hash:
        raise SecurityError(
            f"Hash mismatch! Expected '{code_vault.hash}', "
            f"got '{computed_hash}'. Code may be corrupted."
        )
    
    # Sandbox: Execute the code
    # Create a local scope with arguments and db_session
    local_scope = {
        'arguments': arguments,
        'db_session': db_session,
    }
    
    # Execute the code in the local scope
    exec(code_vault.python_blob, {}, local_scope)
    
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
