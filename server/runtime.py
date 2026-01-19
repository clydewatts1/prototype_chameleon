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

import inspect
import re
import sys
import traceback
import json
from typing import Any, Dict, List, Union
from sqlmodel import Session, select
from sqlalchemy import text, inspect as sa_inspect
from mcp.types import AnyUrl
from jinja2 import Template
from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry, ExecutionLog, MacroRegistry
from base import ChameleonTool
from common.hash_utils import compute_hash
from common.security import (
    SecurityError,
    validate_single_statement,
    validate_read_only,
    validate_code_structure
)


# In-memory storage for temporary test tools
# These tools are not persisted to the database and are only available during runtime
TEMP_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}
"""
Dictionary storing temporary tool metadata.
Key: tool_name
Value: dict with keys: description, input_schema, target_persona, code_hash, is_temp
"""

TEMP_CODE_VAULT: Dict[str, Dict[str, Any]] = {}
"""
Dictionary storing temporary code.
Key: code_hash
Value: dict with keys: code_blob, code_type
"""

TEMP_RESOURCE_REGISTRY: Dict[str, Dict[str, Any]] = {}
"""
Dictionary storing temporary resource metadata.
Key: uri:persona (e.g., "memo://test:default")
Value: dict with keys: name, description, mime_type, is_dynamic, static_content, code_hash, is_temp
"""


class ToolNotFoundError(Exception):
    """Raised when a tool is not found in the registry."""
    pass


class ResourceNotFoundError(Exception):
    """Raised when a resource is not found in the registry."""
    pass


class PromptNotFoundError(Exception):
    """Raised when a prompt is not found in the registry."""
    pass


def _load_macros(meta_session: Session) -> str:
    """
    Load all active Jinja2 macros from the MacroRegistry.
    
    This function queries the MacroRegistry for all active macros and
    concatenates their template strings into a single block that can be
    prepended to SQL tool templates.
    
    Args:
        meta_session: SQLModel Session for metadata database access
        
    Returns:
        String containing all active macro definitions concatenated together,
        or empty string if no active macros exist.
    """
    # Query all active macros
    statement = select(MacroRegistry).where(MacroRegistry.is_active)
    macros = meta_session.exec(statement).all()
    
    if not macros:
        return ""
    
    # Concatenate all macro templates with newlines between them
    macro_block = "\n\n".join(macro.template for macro in macros)
    return macro_block


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


def execute_tool(
    tool_name: str,
    persona: str,
    arguments: Dict[str, Any],
    meta_session: Session,
    data_session: Session = None
) -> Any:
    """
    Execute a tool by fetching and running its code from the database or temporary storage.
    
    This function:
    1. Checks TEMP_TOOL_REGISTRY for temporary tools first
    2. Falls back to querying ToolRegistry for the tool (from metadata DB)
    3. Fetches code from TEMP_CODE_VAULT or CodeVault
    4. Re-hashes the content for security validation (for DB tools)
    5. Executes the code in a sandboxed environment
    6. For temporary SQL tools, injects LIMIT 3 constraint
    7. Logs execution (SUCCESS or FAILURE) to ExecutionLog (in metadata DB)
    
    Args:
        tool_name: Name of the tool to execute
        persona: The persona/context for which to execute the tool
        arguments: Dictionary of arguments to pass to the tool
        meta_session: SQLModel Session for metadata database access
        data_session: SQLModel Session for data database access (optional, may be None)
        
    Returns:
        The result of the tool execution
        
    Raises:
        ToolNotFoundError: If the tool is not found in the registry or temporary storage
        SecurityError: If hash validation fails
        RuntimeError: If data database is required but not available
    """
    tool_def = None
    try:
        # Check if this is a temporary tool first
        is_temp_tool = False
        temp_tool_key = f"{tool_name}:{persona}"
        
        if temp_tool_key in TEMP_TOOL_REGISTRY:
            is_temp_tool = True
            tool_meta = TEMP_TOOL_REGISTRY[temp_tool_key]
            code_hash = tool_meta['code_hash']
            
            # Fetch code from temporary storage
            if code_hash not in TEMP_CODE_VAULT:
                raise ToolNotFoundError(
                    f"Temporary tool code not found for '{tool_name}'"
                )
            
            code_data = TEMP_CODE_VAULT[code_hash]
            code_blob = code_data['code_blob']
            code_type = code_data['code_type']
        else:
            # Query ToolRegistry for the tool (from metadata DB)
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == tool_name,
                ToolRegistry.target_persona == persona
            )
            tool = meta_session.exec(statement).first()
            tool_def = tool
            
            if not tool:
                raise ToolNotFoundError(
                    f"Tool '{tool_name}' not found for persona '{persona}'"
                )
            
            # Fetch CodeVault content using the hash (from metadata DB)
            statement = select(CodeVault).where(CodeVault.hash == tool.active_hash_ref)
            code_vault = meta_session.exec(statement).first()
            
            if not code_vault:
                raise ToolNotFoundError(
                    f"Code not found for hash '{tool.active_hash_ref}'"
                )
            
            # Security: Re-hash the content and validate
            computed_hash = compute_hash(code_vault.code_blob)
            if computed_hash != code_vault.hash:
                raise SecurityError(
                    f"Hash mismatch! Expected '{code_vault.hash}', "
                    f"got '{computed_hash}'. Code may be corrupted."
                )
            
            code_blob = code_vault.code_blob
            code_type = code_vault.code_type
        
        # Execute based on code type
        if code_type == 'select':
            # Check if data_session is available
            if data_session is None:
                raise RuntimeError(
                    "Business database is currently offline. Use 'reconnect_db' tool to try again."
                )
            
            # Step 1: Load active macros and prepend to SQL template
            macro_block = _load_macros(meta_session)
            if macro_block:
                # Prepend macro definitions to the SQL template
                code_blob_with_macros = f"{macro_block}\n\n{code_blob}"
            else:
                code_blob_with_macros = code_blob
            
            # Step 2: Render SQL template with Jinja2 for structural logic
            # IMPORTANT: Jinja2 is used ONLY for structural elements (e.g., optional WHERE clauses)
            # Values must use SQLAlchemy parameter binding with :param_name syntax
            template = Template(code_blob_with_macros)
            rendered_sql = template.render(arguments=arguments)
            
            # Step 3: Security validation
            # Validate single statement (no SQL injection via multiple statements)
            validate_single_statement(rendered_sql)
            
            # Validate read-only (only SELECT statements allowed)
            validate_read_only(rendered_sql)
            
            # Step 4: For temporary tools, inject LIMIT 3 to prevent large data retrieval
            # For auto-created tools, inject LIMIT 1000 to prevent memory crashes
            if is_temp_tool:
                # Remove any existing LIMIT clause and add LIMIT 3
                # Remove trailing semicolons and whitespace
                sql_stripped = rendered_sql.rstrip().rstrip(';').rstrip()
                # Remove any existing LIMIT clause (case-insensitive)
                sql_no_limit = re.sub(r'\s+LIMIT\s+\d+\s*$', '', sql_stripped, flags=re.IGNORECASE)
                # Add mandatory LIMIT 3
                rendered_sql = f"{sql_no_limit} LIMIT 3"
            elif tool_def and tool_def.is_auto_created:
                # Auto-created tools (created by LLMs) get LIMIT 1000 to prevent memory crashes
                # Remove trailing semicolons and whitespace
                sql_stripped = rendered_sql.rstrip().rstrip(';').rstrip()
                # Remove any existing LIMIT clause (case-insensitive)
                sql_no_limit = re.sub(r'\s+LIMIT\s+\d+\s*$', '', sql_stripped, flags=re.IGNORECASE)
                # Add mandatory LIMIT 1000
                rendered_sql = f"{sql_no_limit} LIMIT 1000"
            
            # Step 5: Safe execution with SQLAlchemy parameter binding
            # The rendered SQL should use :param_name syntax for values
            # Pass arguments dictionary to data_session.exec() as params for safe binding
            result = data_session.exec(text(rendered_sql), params=arguments).all()
            
            # Log success (to metadata DB)
            log_execution(
                tool_name=tool_name,
                persona=persona,
                arguments=arguments,
                status="SUCCESS",
                result=result,
                db_session=meta_session
            )
            
            return result
        elif code_type == 'streamlit':
            # Handle Streamlit dashboard code
            # Check if feature is enabled
            from config import load_config
            config = load_config()
            ui_config = config.get('features', {}).get('chameleon_ui', {})
            
            if not ui_config.get('enabled', True):
                raise RuntimeError(
                    "Chameleon UI feature is disabled in configuration"
                )
            
            # For Streamlit dashboards, we don't execute the code here
            # Instead, we return a message with the URL to access the dashboard
            # The dashboard should already be written to file by the create_dashboard tool
            
            # Get the base URL for Streamlit (default port 8501)
            base_url = "http://localhost:8501"
            
            # The dashboard should be accessible at the base URL
            # Streamlit will show all available apps in the ui_apps directory
            result = f"Dashboard is ready! Access it at: {base_url}/?page={tool_name}"
            
            # Log success (to metadata DB)
            log_execution(
                tool_name=tool_name,
                persona=persona,
                arguments=arguments,
                status="SUCCESS",
                result=result,
                db_session=meta_session
            )
            
            return result
        else:
            # Default to python execution with class-based plugin architecture
            # Step 1: Validate code structure
            # Allow system tools to bypass strict validation (e.g. for exec usage)
            if hasattr(tool, 'group') and tool.group == 'system':
                pass # Skip validation for trusted system tools
            else:
                validate_code_structure(code_blob)
            
            # Step 2: Execute the code to load the class definition
            # Create a namespace with base class available
            namespace = {'ChameleonTool': ChameleonTool}
            exec(code_blob, namespace)
            
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
            
            # Step 4: Instantiate the tool with sessions and context
            # Define sub_executor for nested tool calls (used by ChainTool)
            def sub_executor(sub_tool_name: str, sub_arguments: Dict[str, Any]) -> Any:
                """
                Execute a sub-tool within the context of another tool.
                This enables tools like ChainTool to call other tools.
                Safe from infinite recursion due to DAG validation.
                """
                return execute_tool(sub_tool_name, persona, sub_arguments, meta_session, data_session)
            
            context = {
                'persona': persona,
                'tool_name': tool_name,
                'executor': sub_executor,
            }
            tool_instance = tool_class(meta_session, context, data_session)
            
            # Step 5: Execute the tool's run method
            result = tool_instance.run(arguments)
            
            # Log success (to metadata DB)
            log_execution(
                tool_name=tool_name,
                persona=persona,
                arguments=arguments,
                status="SUCCESS",
                result=result,
                db_session=meta_session
            )
            
            return result
            
    except SecurityError:
        # Re-raise security errors so they are not swallowed by the Smart Error Wrapper
        # We still log them for the record
        full_traceback = traceback.format_exc()
        try:
            log_execution(
                tool_name=tool_name,
                persona=persona,
                arguments=arguments,
                status="FAILURE",
                error_traceback_str=full_traceback,
                db_session=meta_session
            )
        except Exception:
            pass # Best effort logging
        raise

    except Exception as e:
        # --- SMART ERROR WRAPPER ---
        # 1. Log full failure for Admin
        full_traceback = traceback.format_exc()
        log_execution(
            tool_name=tool_name,
            persona=persona,
            arguments=arguments,
            status="FAILURE",
            error_traceback_str=full_traceback,
            db_session=meta_session
        )
        
        # 2. Fetch Manual
        # tool_def should be available from the successfully found tool scope
        # If tool_def is None (e.g. temp tool or tool not found), manual is empty
        manual = {}
        if tool_def and hasattr(tool_def, 'extended_metadata'):
             manual = tool_def.extended_metadata or {}
        
        # 3. Construct Helpful Error
        error_msg = f"Tool '{tool_name}' failed with error: {str(e)}"
        
        if manual:
            # RISK 1 FIX: Context Explosion Protection
            # We only grab specific helpful sections, not the whole blob
            helpful_subset = {
                "usage_guide": manual.get("usage_guide", "No guide available."),
                # Only show top 2 examples to save tokens
                "examples": manual.get("examples", [])[:2],
                "common_pitfalls": manual.get("pitfalls", [])
            }
            
            manual_str = json.dumps(helpful_subset, indent=2)
            
            # Hard limit on characters just in case
            if len(manual_str) > 1500:
                manual_str = manual_str[:1500] + "\n... (truncated, use 'system_inspect_tool' for more)"

            error_msg += (
                "\n\n--- 🛡️ AUTOMATIC HELP SYSTEM ---\n"
                f"I found the manual for '{tool_name}'. Please use this to correct your request:\n"
                f"{manual_str}"
            )
        
        return error_msg


def _complete_sql_column_values(
    session: Session,
    column_name: str,
    value_prefix: str
) -> list[str]:
    """
    Attempt to complete a column by scanning tables and returning distinct values.
    Uses SQLAlchemy reflection to find a table containing the column, then runs a
    bound-parameter query to avoid injection.
    """
    try:
        inspector = sa_inspect(session.get_bind())
    except Exception:
        return []

    value_prefix = value_prefix or ""
    tables = inspector.get_table_names()
    for table_name in tables:
        try:
            columns = inspector.get_columns(table_name)
        except Exception:
            continue
        for col in columns:
            if col.get('name') == column_name:
                query = text(
                    f"SELECT DISTINCT {column_name} "
                    f"FROM {table_name} "
                    f"WHERE {column_name} LIKE :val_prefix "
                    f"ORDER BY {column_name} "
                    f"LIMIT 10"
                )
                try:
                    rows = session.exec(query, params={"val_prefix": f"{value_prefix}%"}).all()
                except Exception:
                    return []
                suggestions = [row[0] for row in rows if row and row[0] is not None]
                return suggestions
    return []


def get_tool_completion(
    tool_name: str,
    argument: str,
    value: str,
    persona: str,
    meta_session: Session,
    data_session: Session = None
) -> list[str]:
    """
    Provide completion suggestions for a tool argument.

    For python tools, delegates to the tool instance's `complete` method.
    For SQL tools, attempts to complete column values by reflection.
    """
    # Resolve tool (temp first)
    is_temp_tool = False
    temp_tool_key = f"{tool_name}:{persona}"

    if temp_tool_key in TEMP_TOOL_REGISTRY:
        is_temp_tool = True
        tool_meta = TEMP_TOOL_REGISTRY[temp_tool_key]
        code_hash = tool_meta['code_hash']

        if code_hash not in TEMP_CODE_VAULT:
            raise ToolNotFoundError(
                f"Temporary tool code not found for '{tool_name}'"
            )
        code_data = TEMP_CODE_VAULT[code_hash]
        code_blob = code_data['code_blob']
        code_type = code_data['code_type']
    else:
        statement = select(ToolRegistry).where(
            ToolRegistry.tool_name == tool_name,
            ToolRegistry.target_persona == persona
        )
        tool = meta_session.exec(statement).first()
        if not tool:
            raise ToolNotFoundError(
                f"Tool '{tool_name}' not found for persona '{persona}'"
            )

        statement = select(CodeVault).where(CodeVault.hash == tool.active_hash_ref)
        code_vault = meta_session.exec(statement).first()
        if not code_vault:
            raise ToolNotFoundError(
                f"Code not found for hash '{tool.active_hash_ref}'"
            )

        computed_hash = compute_hash(code_vault.code_blob)
        if computed_hash != code_vault.hash:
            raise SecurityError(
                f"Hash mismatch! Expected '{code_vault.hash}', "
                f"got '{computed_hash}'. Code may be corrupted."
            )

        code_blob = code_vault.code_blob
        code_type = code_vault.code_type

    if code_type == 'select':
        # Prefer data_session; fall back to meta_session for metadata tools
        sessions_to_try = []
        if data_session is not None:
            sessions_to_try.append(data_session)
        if meta_session is not None and meta_session is not data_session:
            sessions_to_try.append(meta_session)

        for sess in sessions_to_try:
            suggestions = _complete_sql_column_values(sess, argument, value)
            if suggestions:
                return suggestions
        return []

    # Python path (and other code types defaulting to python-like behavior)
    validate_code_structure(code_blob)
    namespace = {'ChameleonTool': ChameleonTool}
    exec(code_blob, namespace)

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

    context = {
        'persona': persona,
        'tool_name': tool_name,
    }
    tool_instance = tool_class(meta_session, context, data_session)
    try:
        return tool_instance.complete(argument, value)
    except Exception:
        return []


def list_tools_for_persona(persona: str, db_session: Session, group: str = None) -> List[Dict[str, Any]]:
    """
    List all available tools for a specific persona, including temporary test tools.
    
    Args:
        persona: The persona/context to filter tools by
        db_session: SQLModel Session for database access
        group: Optional group/category filter
        
    Returns:
        List of dictionaries containing tool information:
        - name: Tool name
        - description: Tool description
        - input_schema: JSON schema for tool arguments
        - group: Tool group
    """
    query = select(ToolRegistry).where(ToolRegistry.target_persona == persona)
    if group:
        query = query.where(ToolRegistry.group == group)
    
    tools = db_session.exec(query).all()
    
    results = []
    for tool in tools:
        desc = tool.description
        if tool.is_auto_created:
            desc = f"[AUTO-BUILD] {desc}"
        
        results.append({
            'name': tool.tool_name,
            'description': desc,
            'input_schema': tool.input_schema,
            'group': tool.group or 'general',
        })
    
    # Add temporary tools for this persona
    for key, tool_meta in TEMP_TOOL_REGISTRY.items():
        tool_name_from_key, tool_persona = key.split(':', 1)
        if tool_persona == persona:
            desc = tool_meta['description']
            desc = f"[TEMP-TEST] {desc}"
            
            results.append({
                'name': tool_name_from_key,
                'description': desc,
                'input_schema': tool_meta['input_schema'],
            })
    
    return results


def list_resources_for_persona(persona: str, db_session: Session, group: str = None) -> List[Dict[str, Any]]:
    """
    List all available resources for a specific persona, including temporary resources.
    
    Args:
        persona: The persona/context to filter resources by
        db_session: SQLModel Session for database access
        group: Optional group/category filter
        
    Returns:
        List of dictionaries containing resource information:
        - uri: Resource URI
        - name: Resource name
        - description: Resource description
        - mimeType: MIME type from database
        - group: Resource group
    """
    query = select(ResourceRegistry).where(ResourceRegistry.target_persona == persona)
    if group:
        query = query.where(ResourceRegistry.group == group)
        
    resources = db_session.exec(query).all()
    
    results = [
        {
            'uri': resource.uri_schema,
            'name': resource.name,
            'description': resource.description,
            'mimeType': resource.mime_type,
            'group': resource.group or 'general',
        }
        for resource in resources
    ]
    
    # Add temporary resources for this persona
    for key, resource_meta in TEMP_RESOURCE_REGISTRY.items():
        # Split from right to separate URI from persona in the temp_key format
        # Example: "http://example.com:8080:default" -> URI="http://example.com:8080", persona="default"
        uri_from_key, resource_persona = key.rsplit(':', 1)
        if resource_persona == persona:
            desc = resource_meta['description']
            desc = f"[TEMP] {desc}"
            
            results.append({
                'uri': uri_from_key,
                'name': resource_meta['name'],
                'description': desc,
                'mimeType': resource_meta.get('mime_type', 'text/plain'),
            })
    
    return results


def get_resource(uri: Union[str, AnyUrl], persona: str, meta_session: Session, data_session: Session = None) -> str:
    """
    Get a resource by URI and execute if dynamic.
    
    This function:
    1. Checks TEMP_RESOURCE_REGISTRY for temporary resources first
    2. Falls back to querying ResourceRegistry by URI (from metadata DB)
    3. If static, returns the static_content
    4. If dynamic, executes code from CodeVault or TEMP_CODE_VAULT
    
    Args:
        uri: URI of the resource to retrieve (string or MCP AnyUrl)
        persona: The persona/context for which to get the resource
        meta_session: SQLModel Session for metadata database access
        data_session: SQLModel Session for data database access (optional, may be None)
        
    Returns:
        The resource content as a string
        
    Raises:
        ResourceNotFoundError: If the resource is not found
        SecurityError: If hash validation fails for dynamic resources
        RuntimeError: If data database is required but not available
    """
    # Convert uri to string in case it's a Pydantic AnyUrl or other type
    uri_str = str(uri)
    
    # Check if this is a temporary resource first
    is_temp_resource = False
    temp_resource_key = f"{uri_str}:{persona}"
    
    if temp_resource_key in TEMP_RESOURCE_REGISTRY:
        is_temp_resource = True
        resource_meta = TEMP_RESOURCE_REGISTRY[temp_resource_key]
        
        # If static, return the static content
        if not resource_meta.get('is_dynamic', False):
            return resource_meta.get('static_content', '')
        
        # If dynamic, fetch code from TEMP_CODE_VAULT
        code_hash = resource_meta.get('code_hash')
        if not code_hash:
            raise ResourceNotFoundError(
                f"Dynamic temporary resource has no code reference"
            )
        
        if code_hash not in TEMP_CODE_VAULT:
            raise ResourceNotFoundError(
                f"Temporary resource code not found for URI '{uri_str}'"
            )
        
        code_data = TEMP_CODE_VAULT[code_hash]
        code_blob = code_data['code_blob']
        code_type = code_data['code_type']
        
        # Execute based on code type
        if code_type == 'select':
            # Check if data_session is available
            if data_session is None:
                raise RuntimeError(
                    "Business database is currently offline. Use 'reconnect_db' tool to try again."
                )
            
            # Step 1: Render SQL template with Jinja2 for structural logic
            # Create arguments dict from available context (uri, persona)
            template_args = {
                'uri': uri_str,
                'persona': persona,
            }
            template = Template(code_blob)
            rendered_sql = template.render(arguments=template_args)
            
            # Step 2: Security validation
            # Validate single statement (no SQL injection via multiple statements)
            validate_single_statement(rendered_sql)
            
            # Validate read-only (only SELECT statements allowed)
            validate_read_only(rendered_sql)
            
            # Step 3: Safe execution with SQLAlchemy parameter binding
            # Pass template_args as params for safe binding (use data_session for business data)
            result = data_session.exec(text(rendered_sql), params=template_args).all()
            return str(result)
        else:
            # Default to python execution with class-based plugin architecture
            # Step 1: Validate code structure
            validate_code_structure(code_blob)
            
            # Step 2: Execute the code to load the class definition
            # Create a namespace with base class available
            namespace = {'ChameleonTool': ChameleonTool}
            exec(code_blob, namespace)
            
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
            
            # Step 4: Instantiate the tool with sessions and context
            context = {
                'persona': persona,
                'uri': uri_str,
            }
            tool_instance = tool_class(meta_session, context, data_session)
            
            # Step 5: Execute the tool's run method with uri as argument
            # For resources, pass uri in the arguments dict
            result = tool_instance.run({'uri': uri_str, 'persona': persona})
            return str(result)
    
    # If not a temporary resource, query ResourceRegistry for the resource by URI (from metadata DB)
    statement = select(ResourceRegistry).where(ResourceRegistry.uri_schema == uri_str)
    resource = meta_session.exec(statement).first()
    
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
    
    # Fetch CodeVault content using the hash (from metadata DB)
    statement = select(CodeVault).where(CodeVault.hash == resource.active_hash_ref)
    code_vault = meta_session.exec(statement).first()
    
    if not code_vault:
        raise ResourceNotFoundError(
            f"Code not found for hash '{resource.active_hash_ref}'"
        )
    
    # Security: Re-hash the content and validate
    computed_hash = compute_hash(code_vault.code_blob)
    if computed_hash != code_vault.hash:
        raise SecurityError(
            f"Hash mismatch! Expected '{code_vault.hash}', "
            f"got '{computed_hash}'. Code may be corrupted."
        )
    
    # Execute based on code type
    if code_vault.code_type == 'select':
        # Check if data_session is available
        if data_session is None:
            raise RuntimeError(
                "Business database is currently offline. Use 'reconnect_db' tool to try again."
            )
        
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
        validate_single_statement(rendered_sql)
        
        # Validate read-only (only SELECT statements allowed)
        validate_read_only(rendered_sql)
        
        # Step 3: Safe execution with SQLAlchemy parameter binding
        # Pass template_args as params for safe binding (use data_session for business data)
        result = data_session.exec(text(rendered_sql), params=template_args).all()
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
        
        # Step 4: Instantiate the tool with sessions and context
        context = {
            'persona': persona,
            'uri': uri_str,
        }
        tool_instance = tool_class(meta_session, context, data_session)
        
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
