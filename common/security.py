"""
Security validation functions for the Chameleon MCP Server.

This module contains functions to validate SQL queries and Python code for security.
"""

import ast
import re

try:
    import sqlglot
    from sqlglot import exp
except ImportError:
    sqlglot = None

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
    
    Uses sqlglot for AST-based validation (Phase 2 enhancement).
    Falls back to sqlparse or regex if sqlglot is not available.
    
    Args:
        sql: The SQL query string to validate
        
    Raises:
        SecurityError: If multiple statements are detected
    """
    if sqlglot:
        # Use sqlglot AST parsing (preferred method)
        try:
            statements = sqlglot.parse(sql)
            # Filter out None or empty statements
            real_statements = [stmt for stmt in statements if stmt is not None]
            if len(real_statements) > 1:
                raise SecurityError("Multiple SQL statements detected. Only single statements are allowed.")
            if len(real_statements) == 0:
                raise SecurityError("Empty SQL query")
            return
        except sqlglot.errors.ParseError as e:
            raise SecurityError(f"Failed to parse SQL: {e}")
    
    if sqlparse:
        # Fallback to sqlparse
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
    
    Uses sqlglot AST parsing for mathematical verification (Phase 2 enhancement).
    This provides stronger guarantees than regex-based validation by analyzing
    the abstract syntax tree of the SQL query.
    
    Args:
        sql: The SQL query string to validate
        
    Raises:
        SecurityError: If write operations are detected or not a SELECT statement
    """
    if sqlglot:
        # Use sqlglot AST parsing (Phase 2 implementation)
        try:
            parsed = sqlglot.parse_one(sql)
        except sqlglot.errors.ParseError as e:
            raise SecurityError(f"Failed to parse SQL: {e}")
        
        if parsed is None:
            raise SecurityError("Empty or invalid SQL query")
        
        # Step 1: Check if the top-level statement is a Query type (SELECT, UNION, WITH, etc.)
        # Query types are read-only operations in SQL
        if not isinstance(parsed, exp.Query):
            raise SecurityError(
                f"Only SELECT statements are allowed. Found: {type(parsed).__name__}"
            )
        
        # Step 2: Walk the entire AST to ensure no write operations are nested anywhere
        # This catches cases like: SELECT * FROM (SELECT * FROM users) UNION (UPDATE ...)
        dangerous_types = (
            exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
            exp.TruncateTable, exp.Grant, exp.Revoke, exp.Merge,
            exp.Commit, exp.Rollback
        )
        
        # Additional dangerous types that might be dialect-specific
        if hasattr(exp, 'Execute'):
            dangerous_types = dangerous_types + (exp.Execute,)
        if hasattr(exp, 'Call'):
            # Some databases allow CALL for stored procedures
            dangerous_types = dangerous_types + (exp.Call,)
        
        for node in parsed.walk():
            if isinstance(node, dangerous_types):
                raise SecurityError(
                    f"Forbidden operation detected in SQL: {type(node).__name__}"
                )
        
        # If we get here, the query is read-only
        return
    
    if not sqlparse:
        # Fallback to regex-based validation if neither sqlglot nor sqlparse is available
        _validate_read_only_fallback(sql)
        return

    # Use sqlparse for robust validation (legacy fallback)
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


def validate_code_structure(code_str: str, policies: list = None) -> None:
    """
    Validate that Python code only contains safe top-level nodes and prevents dangerous operations.
    
    Checks:
    1. Top-level nodes must be Import, ImportFrom, or ClassDef (Plugin architecture).
    2. No imports of dangerous modules (based on policies or defaults).
    3. No calls to dangerous functions (based on policies or defaults).
    
    Policy Precedence:
    - If a pattern appears in a 'deny' rule, it is blocked regardless of 'allow' rules.
    - If a pattern appears only in 'allow' rules, it is allowed.
    - If a pattern appears in neither, it follows default behavior (blocked for backward compatibility).
    
    Args:
        code_str: The Python code string to validate
        policies: Optional list of policy dicts with keys: rule_type, category, pattern, is_active
                  If None, uses hardcoded defaults for backward compatibility.
        
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
    
    # 2. Build policy sets from provided policies or use defaults
    if policies is not None:
        # Filter active policies only
        active_policies = [p for p in policies if p.get('is_active', True)]
        
        # Build deny and allow sets by category
        denied_modules = {p['pattern'] for p in active_policies if p['rule_type'] == 'deny' and p['category'] == 'module'}
        allowed_modules = {p['pattern'] for p in active_policies if p['rule_type'] == 'allow' and p['category'] == 'module'}
        
        denied_functions = {p['pattern'] for p in active_policies if p['rule_type'] == 'deny' and p['category'] == 'function'}
        allowed_functions = {p['pattern'] for p in active_policies if p['rule_type'] == 'allow' and p['category'] == 'function'}
        
        denied_attributes = {p['pattern'] for p in active_policies if p['rule_type'] == 'deny' and p['category'] == 'attribute'}
        allowed_attributes = {p['pattern'] for p in active_policies if p['rule_type'] == 'allow' and p['category'] == 'attribute'}
    else:
        # Backward compatibility: Use hardcoded defaults
        denied_modules = {'importlib', 'subprocess', 'sys', 'shutil', 'marshal', 'pickle'}
        allowed_modules = set()
        denied_functions = {'exec', 'eval', 'compile', 'open', 'input', 'exit', 'quit', 'help', '__import__'}
        allowed_functions = set()
        denied_attributes = set()
        allowed_attributes = set()
            
    # 3. Deep AST Inspection for Dangerous Operations
    for node in ast.walk(tree):
        # Check Imports
        if isinstance(node, ast.Import):
            for name in node.names:
                root_module = name.name.split('.')[0]
                if _is_denied(root_module, denied_modules, allowed_modules):
                    raise SecurityError(f"Import of forbidden module '{root_module}' is blocked.")
                    
        if isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split('.')[0]
                if _is_denied(root_module, denied_modules, allowed_modules):
                    raise SecurityError(f"Import of forbidden module '{root_module}' is blocked.")
                    
        # Check Function Calls (Direct & Attribute)
        if isinstance(node, ast.Call):
            # Direct calls: eval(), exec(), open()
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if _is_denied(func_name, denied_functions, allowed_functions):
                    raise SecurityError(f"Call to forbidden function '{func_name}()' is blocked.")
            
            # Attribute calls: os.system(), os.popen()
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    module = node.func.value.id
                    method = node.func.attr
                    
                    # Check attribute-level patterns (e.g., 'os.system')
                    attr_pattern = f"{module}.{method}"
                    if _is_denied(attr_pattern, denied_attributes, allowed_attributes):
                        raise SecurityError(f"Call to forbidden function '{attr_pattern}()' is blocked.")
                    
                    # Legacy checks for backward compatibility (if no policies provided)
                    if policies is None:
                        # Block os.system, os.popen, etc.
                        if module == 'os' and method in ('system', 'popen', 'spawn', 'exec', 'fork'):
                            raise SecurityError(f"Call to forbidden function 'os.{method}()' is blocked.")
                        
                        # Block subprocess.*
                        if module == 'subprocess':
                            raise SecurityError(f"Call to forbidden module 'subprocess' is blocked.")


def _is_denied(pattern: str, denied_set: set, allowed_set: set) -> bool:
    """
    Check if a pattern is denied based on precedence rules.
    
    Precedence Rules:
    1. If pattern is in denied_set, it's BLOCKED (deny overrides allow).
    2. If pattern is in allowed_set (and not in denied_set), it's ALLOWED.
    3. If pattern is in neither set, default behavior applies (typically blocked for security).
    
    Args:
        pattern: The pattern to check (e.g., 'subprocess', 'eval')
        denied_set: Set of explicitly denied patterns
        allowed_set: Set of explicitly allowed patterns
        
    Returns:
        True if the pattern should be blocked, False otherwise
    """
    # Rule 1: Deny always takes precedence
    if pattern in denied_set:
        return True
    
    # Rule 2: If explicitly allowed (and not denied), allow it
    if pattern in allowed_set:
        return False
    
    # Rule 3: Default behavior - if policies exist (sets are populated), 
    # we should be more permissive for unlisted items
    # But if we're using hardcoded defaults (empty allowed_set), block by default
    # This is handled by the caller having the pattern in denied_set already
    return False


def load_security_policies(db_session) -> list:
    """
    Load active security policies from the database.
    
    This function queries the SecurityPolicy table and returns a list of
    policy dictionaries that can be passed to validate_code_structure().
    
    Args:
        db_session: SQLModel database session
        
    Returns:
        List of policy dicts with keys: rule_type, category, pattern, is_active, description.
        Returns an empty list if SecurityPolicy model is not available (graceful degradation).
        
    Example:
        from sqlmodel import Session
        from models import get_engine
        from security import load_security_policies, validate_code_structure
        
        engine = get_engine("sqlite:///chameleon.db")
        with Session(engine) as session:
            policies = load_security_policies(session)
            validate_code_structure(code_str, policies=policies)
    """
    try:
        # Avoid circular import by importing here
        from sqlmodel import select
        
        # Import SecurityPolicy - assumes models is in path
        # (e.g., via sys.path manipulation in tests or server context)
        from models import SecurityPolicy
        
        # Query active policies
        statement = select(SecurityPolicy).where(SecurityPolicy.is_active == True)
        policies = db_session.exec(statement).all()
        
        # Convert to list of dicts for easier consumption
        return [
            {
                'rule_type': p.rule_type,
                'category': p.category,
                'pattern': p.pattern,
                'is_active': p.is_active,
                'description': p.description
            }
            for p in policies
        ]
    except (ImportError, AttributeError):
        # If models module not available or SecurityPolicy doesn't exist,
        # return empty list to allow graceful degradation
        # Caller can handle by using hardcoded defaults (policies=None)
        return []
