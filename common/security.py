"""
Security validation functions for the Chameleon MCP Server.

This module contains functions to validate SQL queries and Python code for security.
"""

import ast
import re


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


def validate_single_statement(sql: str) -> None:
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


def validate_read_only(sql: str) -> None:
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
