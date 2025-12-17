"""
Security validation functions for the Chameleon MCP Server.

This module contains functions to validate SQL queries and Python code for security.
"""

import ast
import re

try:
    import sqlparse
    from sqlparse import tokens as T
except ImportError:
    sqlparse = None

class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


def validate_single_statement(sql: str) -> None:
    """
    Validate that SQL contains only a single statement.
    
    Args:
        sql: The SQL query string to validate
        
    Raises:
        SecurityError: If multiple statements are detected
    """
    if sqlparse:
        # Use sqlparse to count statements
        parsed = sqlparse.parse(sql)
        # Filter out empty statements (comments or whitespace only)
        real_statements = [p for p in parsed if p.get_type() != 'UNKNOWN' or p.tokens]
        if len(real_statements) > 1:
            raise SecurityError("Multiple SQL statements detected. Only single statements are allowed.")
    else:
        # Fallback: simple string check
        sql_stripped = sql.strip().rstrip(';')
        if ';' in sql_stripped:
            raise SecurityError("Multiple SQL statements detected (semicolon check). Only single statements are allowed.")


def validate_read_only(sql: str) -> None:
    """
    Validate that SQL is a read-only SELECT statement.
    
    Args:
        sql: The SQL query string to validate
        
    Raises:
        SecurityError: If write operations are detected or not a SELECT statement
    """
    if not sqlparse:
        # Fallback to regex-based validation if sqlparse not available
        _validate_read_only_fallback(sql)
        return

    # Use sqlparse for robust validation
    try:
        parsed = sqlparse.parse(sql)
    except Exception as e:
         raise SecurityError(f"Failed to parse SQL: {e}")
         
    if not parsed:
        raise SecurityError("Empty or invalid SQL query")
    
    real_statements = [p for p in parsed if p.get_type() != 'UNKNOWN' or p.tokens]
    if len(real_statements) > 1:
        raise SecurityError("Multiple statements are not allowed")
    
    if not real_statements:
         raise SecurityError("Empty SQL query")
         
    stmt = real_statements[0]
    
    # 1 check: Statement type must be SELECT
    if stmt.get_type() != 'SELECT':
        raise SecurityError(f"Only SELECT statements are allowed. Found: {stmt.get_type()}")
        
    # 2 check: Scan tokens for DDL/DML keywords that might be hidden or nested
    # Flatten the statement to iterate through all tokens
    forbidden_types = (T.DML, T.DDL)
    forbidden_keywords = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 
        'CREATE', 'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE', 
        'EXEC', 'EXECUTE', 'MERGE', 'CALL', 'COMMIT', 'ROLLBACK',
        'Bot', 'Upsert' # Common ORM terms sometimes leaking, though SQL tokens are standard
    }
    
    for token in stmt.flatten():
        # Check token type
        if token.ttype in forbidden_types:
            key = token.value.upper()
            if key in forbidden_keywords:
                 raise SecurityError(f"Forbidden keyword detected: {key}")
        
        # Check Keyword types that might be DML/DDL but classified as Keyword
        if token.ttype is T.Keyword:
            key = token.value.upper()
            if key in forbidden_keywords:
                 raise SecurityError(f"Forbidden keyword detected: {key}")
                 
        # Special check for EXEC usage which can sometimes be a function call
        if token.ttype is T.Name and token.value.upper() in ('EXEC', 'EXECUTE'):
             raise SecurityError(f"Forbidden keyword detected: {token.value}")


def _validate_read_only_fallback(sql: str) -> None:
    """Old regex-based validation as fallback."""
    # Normalize: strip and convert to uppercase for checking
    sql_upper = sql.strip().upper()
    
    # Remove SQL comments (both single-line and multi-line) first
    sql_cleaned = re.sub(r'--[^\n]*', '', sql_upper)  # Single-line comments
    sql_cleaned = re.sub(r'/\*.*?\*/', '', sql_cleaned, flags=re.DOTALL)  # Multi-line comments
    sql_cleaned = sql_cleaned.strip()
    
    # Check if it starts with SELECT
    if not sql_cleaned.startswith('SELECT'):
        raise SecurityError("Only SELECT statements are allowed. Query must start with SELECT.")
    
    # Detailed pattern checks
    dangerous_patterns = [
        (r'\bINSERT\s*', 'INSERT'),
        (r'\bUPDATE\s+', 'UPDATE'),
        (r'\bDELETE\s+', 'DELETE'),
        (r'\bDROP\s+', 'DROP'),
        (r'\bALTER\s+', 'ALTER'),
        (r'\bCREATE\s+', 'CREATE'),
        (r'\bTRUNCATE\s+', 'TRUNCATE'),
        (r'\bEXEC(UTE)?\s*', 'EXEC/EXECUTE'),
        (r'\bGRANT\s+', 'GRANT'),
        (r'\bREVOKE\s+', 'REVOKE'),
    ]
    
    for pattern, keyword in dangerous_patterns:
        if re.search(pattern, sql_cleaned):
            raise SecurityError(f"Dangerous keyword '{keyword}' detected. Only SELECT statements are allowed.")


def validate_code_structure(code_str: str) -> None:
    """
    Validate that Python code only contains safe top-level nodes and prevents dangerous operations.
    
    Checks:
    1. Top-level nodes must be Import, ImportFrom, or ClassDef (Plugin architecture).
    2. No imports of dangerous modules (importlib, subprocess, sys).
    3. No calls to dangerous functions (exec, eval, open, os.system, etc.).
    
    Args:
        code_str: The Python code string to validate
        
    Raises:
        SecurityError: If code violates security constraints
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        raise SecurityError(f"Code contains syntax errors: {e}")
    
    # 1. Top-level Structure Validation
    for node in tree.body:
        # Ignore comments/docstrings
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Str, ast.Constant)):
            continue
            
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef)):
            node_type = type(node).__name__
            raise SecurityError(
                f"Invalid top-level node '{node_type}'. Only Import, ImportFrom, "
                f"and ClassDef are allowed at the top level."
            )
            
    # 2. Deep AST Inspection for Dangerous Operations
    BANNED_MODULES = {'importlib', 'subprocess', 'sys', 'shutil', 'marshal', 'pickle'}
    BANNED_FUNCTIONS = {'exec', 'eval', 'compile', 'open', 'input', 'exit', 'quit', 'help', '__import__'}
    
    for node in ast.walk(tree):
        # Check Imports
        if isinstance(node, ast.Import):
            for name in node.names:
                root_module = name.name.split('.')[0]
                if root_module in BANNED_MODULES:
                    raise SecurityError(f"Import of forbidden module '{root_module}' is blocked.")
                    
        if isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split('.')[0]
                if root_module in BANNED_MODULES:
                    raise SecurityError(f"Import of forbidden module '{root_module}' is blocked.")
                    
        # Check Function Calls (Direct & Attribute)
        if isinstance(node, ast.Call):
            # Direct calls: eval(), exec(), open()
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in BANNED_FUNCTIONS:
                    raise SecurityError(f"Call to forbidden function '{func_name}()' is blocked.")
            
            # Attribute calls: os.system(), os.popen()
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    module = node.func.value.id
                    method = node.func.attr
                    
                    # Block os.system, os.popen, etc.
                    if module == 'os' and method in ('system', 'popen', 'spawn', 'exec', 'fork'):
                         raise SecurityError(f"Call to forbidden function 'os.{method}()' is blocked.")
                    
                    # Block subprocess.*
                    if module == 'subprocess':
                        raise SecurityError(f"Call to forbidden module 'subprocess' is blocked.")
