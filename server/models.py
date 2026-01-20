"""
Database models for the custom MCP server using SQLModel.

This module defines the database schema for storing code and tool configurations.
"""

from sqlmodel import Field, SQLModel, create_engine, Column
from sqlalchemy import JSON, Text
from datetime import date, datetime, timezone
from config import load_config

# Load configuration at module level
_config = load_config()
_db_config = _config.get('database', {})
_table_config = _config.get('tables', {})

# Determine schema argument for all tables
_schema_name = _db_config.get('schema')
_schema_arg = {"schema": _schema_name} if _schema_name else None


def _get_foreign_key(table_key: str, column: str = 'hash') -> str:
    """
    Construct a foreign key reference with optional schema prefix.
    
    Args:
        table_key: The logical table name key (e.g., 'code_vault')
        column: The column name to reference (default: 'hash')
        
    Returns:
        Foreign key reference string (e.g., 'schema.tablename.column' or 'tablename.column')
    """
    table_name = _table_config.get(table_key, table_key)
    if _schema_name:
        return f"{_schema_name}.{table_name}.{column}"
    return f"{table_name}.{column}"


def _get_foreign_key_optional(table_key: str, column: str = 'hash') -> str:
    """Same as _get_foreign_key but doesn't assume logic - just a wrapper for consistency"""
    return _get_foreign_key(table_key, column)


def _utc_now() -> datetime:
    """
    Helper function to get current UTC datetime.
    
    Used as default factory for timestamp fields to ensure consistency
    and avoid code duplication across models.
    
    Returns:
        Current datetime in UTC timezone
    """
    return datetime.now(timezone.utc)


class SalesPerDay(SQLModel, table=True):
    """
    Table for storing daily sales data.
    
    Attributes:
        id: Auto-incrementing primary key
        business_date: Date of the sales transaction
        store_name: Name of the store
        department: Department name
        sales_amount: Sales amount in dollars
    """
    __tablename__ = _table_config.get('sales_per_day', 'sales_per_day')
    __table_args__ = _schema_arg
    
    id: int | None = Field(default=None, primary_key=True, description="Auto-incrementing ID")
    business_date: date = Field(description="Date of the sales transaction")
    store_name: str = Field(description="Name of the store")
    department: str = Field(description="Department name")
    sales_amount: float = Field(description="Sales amount in dollars")


class CodeVault(SQLModel, table=True):
    """
    Table for storing executable code with SHA-256 hash as primary key.
    
    Attributes:
        hash: SHA-256 hash of the code (Primary Key)
        code_blob: The executable code as text
        code_type: Type of code ('python' or 'select')
    """
    __tablename__ = _table_config.get('code_vault', 'codevault')
    __table_args__ = _schema_arg
    
    hash: str = Field(primary_key=True, description="SHA-256 hash of the code")
    code_blob: str = Field(description="The executable code")
    code_type: str = Field(default="python", description="Type of code: 'python', 'select', or 'streamlit'")


class ToolRegistry(SQLModel, table=True):
    """
    Table for registering tools with their configurations and personas.
    
    Attributes:
        tool_name: Name of the tool (Primary Key)
        target_persona: The persona this tool targets (Primary Key)
        description: Description of what the tool does
        input_schema: JSON Schema for the tool arguments (stored as dict/JSON)
        active_hash_ref: Foreign key reference to CodeVault hash
        is_auto_created: True if tool was created by the LLM, False if system/prebuilt
    """
    __tablename__ = _table_config.get('tool_registry', 'toolregistry')
    __table_args__ = _schema_arg
    
    tool_name: str = Field(primary_key=True, description="Name of the tool")
    target_persona: str = Field(primary_key=True, description="Target persona for the tool")
    description: str = Field(description="Description of what the tool does")
    input_schema: dict = Field(sa_column=Column(JSON), description="JSON Schema for the tool arguments")
    active_hash_ref: str = Field(
        foreign_key=_get_foreign_key('code_vault', 'hash'),
        description="Reference to CodeVault hash"
    )
    is_auto_created: bool = Field(default=False, description="True if tool was created by the LLM, False if system/prebuilt")
    group: str = Field(description="Group/Category for organization")
    icon_name: str | None = Field(
        default=None,
        foreign_key=_get_foreign_key('icon_registry', 'icon_name'),
        nullable=True,
        description="Reference to IconRegistry icon_name"
    )
    extended_metadata: dict | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Extended metadata for the tool (manual, examples, usage guide)"
    )


class ResourceRegistry(SQLModel, table=True):
    """
    Table for registering Resources.
    Resources can be static (text stored here) or dynamic (code in CodeVault).
    """
    __tablename__ = _table_config.get('resource_registry', 'resourceregistry')
    __table_args__ = _schema_arg
    
    uri_schema: str = Field(primary_key=True, description="The URI pattern (e.g. 'note://{id}')")
    name: str = Field(description="Human readable name")
    description: str = Field(description="Description of the resource")
    mime_type: str = Field(default="text/plain", description="MIME type of the content")
    
    # Dynamic vs Static
    is_dynamic: bool = Field(default=False, description="If True, executes code from CodeVault")
    static_content: str | None = Field(default=None, description="Hardcoded content for static resources")
    active_hash_ref: str | None = Field(
        default=None,
        foreign_key=_get_foreign_key('code_vault', 'hash'),
        nullable=True,
        description="Ref to CodeVault if dynamic"
    )
    
    # Persona support
    target_persona: str = Field(default="default", description="Target persona for the resource")
    group: str = Field(description="Group/Category for organization")


class PromptRegistry(SQLModel, table=True):
    """
    Table for registering Prompts.
    Prompts are templates that the LLM can request.
    """
    __tablename__ = _table_config.get('prompt_registry', 'promptregistry')
    __table_args__ = _schema_arg
    
    name: str = Field(primary_key=True, description="Name of the prompt (e.g. 'review_code')")
    description: str = Field(description="What this prompt does")
    template: str = Field(description="The Jinja2 or f-string template")
    arguments_schema: dict = Field(sa_column=Column(JSON), description="JSON Schema for arguments")
    
    # Persona support
    target_persona: str = Field(default="default", description="Target persona for the prompt")
    group: str = Field(description="Group/Category for organization")


class ExecutionLog(SQLModel, table=True):
    """
    Table for logging tool execution for debugging and self-healing.
    
    This is the "Black Box" Recorder pattern that allows AI agents to:
    1. Run tools and capture full execution details
    2. Query for detailed error information when a tool fails
    3. Analyze exact line numbers and error types
    4. Patch tool code based on precise error information
    
    Attributes:
        id: Auto-incrementing primary key
        timestamp: When the execution occurred (UTC)
        tool_name: Name of the tool that was executed
        persona: The persona context for the execution
        arguments: The input arguments passed to the tool (JSON)
        status: Execution status ("SUCCESS" or "FAILURE")
        result_summary: The output/result (truncated to ~2000 chars)
        error_traceback: Full Python traceback for failures (Text)
    """
    __tablename__ = _table_config.get('execution_log', 'executionlog')
    __table_args__ = _schema_arg
    
    id: int | None = Field(default=None, primary_key=True, description="Auto-incrementing ID")
    timestamp: datetime = Field(default_factory=_utc_now, description="Timestamp of execution (UTC)")
    tool_name: str = Field(description="Name of the tool executed")
    persona: str = Field(description="Persona context")
    arguments: dict = Field(sa_column=Column(JSON), description="Input arguments (JSON)")
    status: str = Field(description="Execution status: 'SUCCESS' or 'FAILURE'")
    result_summary: str = Field(description="Output/result (truncated to ~2000 chars)")
    error_traceback: str | None = Field(sa_column=Column(Text), default=None, description="Full Python traceback for failures")


class MacroRegistry(SQLModel, table=True):
    """
    Table for storing reusable Jinja2 macros for SQL tools.
    
    Macros allow defining common SQL logic (e.g., fiscal year calculations, 
    safe division) that can be shared across multiple SQL tools.
    
    Attributes:
        name: Name of the macro (Primary Key, e.g., 'safe_div')
        description: Description of what the macro does
        template: The Jinja2 macro definition (must start with {% macro and end with {% endmacro %})
        is_active: Whether the macro is currently active (only active macros are loaded)
    """
    __tablename__ = _table_config.get('macro_registry', 'macroregistry')
    __table_args__ = _schema_arg
    
    name: str = Field(primary_key=True, description="Name of the macro (e.g., 'safe_div')")
    description: str = Field(description="Description of what the macro does")
    template: str = Field(sa_column=Column(Text), description="The Jinja2 macro definition")
    is_active: bool = Field(default=True, description="Whether the macro is currently active")


class SecurityPolicy(SQLModel, table=True):
    """
    Table for storing security policies for AST validation.
    
    This table enables dynamic security policy management where policies can be
    updated without code changes. Supports both allow lists (whitelist) and 
    deny lists (blacklist) with strict precedence: deny always overrides allow.
    
    Attributes:
        id: Auto-incrementing primary key
        rule_type: Type of rule ('allow' or 'deny')
        category: Category of restriction ('module', 'function', or 'attribute')
        pattern: The name to match (e.g., 'subprocess', 'open', 'os.system')
        description: Optional description of why this policy exists
        is_active: Whether the policy is currently active (only active policies are enforced)
    """
    __tablename__ = _table_config.get('security_policy', 'securitypolicy')
    __table_args__ = _schema_arg
    
    id: int | None = Field(default=None, primary_key=True, description="Auto-incrementing ID")
    rule_type: str = Field(description="Type of rule: 'allow' or 'deny'")
    category: str = Field(description="Category: 'module', 'function', or 'attribute'")
    pattern: str = Field(description="The name to match (e.g., 'subprocess', 'open', 'os.system')")
    description: str | None = Field(default=None, description="Optional description of the policy")
    is_active: bool = Field(default=True, description="Whether the policy is currently active")


class IconRegistry(SQLModel, table=True):
    """
    Table for storing tool icons (SVG or PNG keys).
    
    Attributes:
        icon_name: Unique name of the icon (Primary Key)
        mime_type: MIME type (e.g., 'image/svg+xml', 'image/png')
        content: Base64 encoded string or raw SVG text
    """
    __tablename__ = _table_config.get('icon_registry', 'iconregistry')
    __table_args__ = _schema_arg
    
    icon_name: str = Field(primary_key=True, description="Unique name of the icon")
    mime_type: str = Field(description="MIME type of the icon")
    content: str = Field(sa_column=Column(Text), description="Icon content (Base64 or SVG)")


class AgentNotebook(SQLModel, table=True):
    """
    Table for storing long-term memory entries for the agent.
    
    This serves as the agent's "brain" - a key-value store organized by domains
    for different contexts (user preferences, self-correction logs, project state, etc.).
    
    Attributes:
        domain: Namespace for grouping related memories (e.g., 'user_prefs', 'self_correction')
        key: Unique key within the domain (Primary Key with domain)
        value: The stored memory value as text
        created_at: When this memory was first created (UTC)
        updated_at: When this memory was last modified (UTC)
        updated_by: Who/what last updated this entry (e.g., 'user', 'system', 'tool_name')
        is_active: Whether this memory is currently active (soft delete support)
    """
    __tablename__ = _table_config.get('agent_notebook', 'agentnotebook')
    __table_args__ = _schema_arg
    
    domain: str = Field(primary_key=True, description="Domain/namespace for the memory entry")
    key: str = Field(primary_key=True, description="Unique key within the domain")
    value: str = Field(sa_column=Column(Text), description="The stored memory value")
    created_at: datetime = Field(default_factory=_utc_now, description="When created (UTC)")
    updated_at: datetime = Field(default_factory=_utc_now, description="When last updated (UTC)")
    updated_by: str = Field(default="system", description="Who/what last updated this entry")
    is_active: bool = Field(default=True, description="Whether this memory is active")


class NotebookHistory(SQLModel, table=True):
    """
    Table for storing historical changes to AgentNotebook entries.
    
    Every time an AgentNotebook entry is modified, the previous value is saved here
    to maintain a complete audit trail of how the agent's memory evolves.
    
    Attributes:
        id: Auto-incrementing primary key
        domain: Domain of the notebook entry (Foreign Key)
        key: Key of the notebook entry (Foreign Key)
        old_value: The previous value before the change
        new_value: The new value after the change
        changed_at: When this change occurred (UTC)
        changed_by: Who/what made this change (e.g., 'user', 'system', 'tool_name')
    """
    __tablename__ = _table_config.get('notebook_history', 'notebookhistory')
    __table_args__ = _schema_arg
    
    id: int | None = Field(default=None, primary_key=True, description="Auto-incrementing ID")
    domain: str = Field(description="Domain of the notebook entry")
    key: str = Field(description="Key of the notebook entry")
    old_value: str | None = Field(sa_column=Column(Text), default=None, description="Previous value")
    new_value: str = Field(sa_column=Column(Text), description="New value after change")
    changed_at: datetime = Field(default_factory=_utc_now, description="When changed (UTC)")
    changed_by: str = Field(description="Who/what made this change")


class NotebookAudit(SQLModel, table=True):
    """
    Table for auditing access to AgentNotebook entries.
    
    Tracks when and by whom notebook entries are read, providing a complete
    audit trail of memory access patterns.
    
    Attributes:
        id: Auto-incrementing primary key
        domain: Domain of the accessed entry
        key: Key of the accessed entry
        access_type: Type of access ('read', 'write', 'delete')
        accessed_at: When the access occurred (UTC)
        accessed_by: Who/what accessed the entry (e.g., 'user', 'tool_name')
        context_data: Additional context about the access (JSON)
    """
    __tablename__ = _table_config.get('notebook_audit', 'notebookaudit')
    __table_args__ = _schema_arg
    
    id: int | None = Field(default=None, primary_key=True, description="Auto-incrementing ID")
    domain: str = Field(description="Domain of the accessed entry")
    key: str = Field(description="Key of the accessed entry")
    access_type: str = Field(description="Type of access: 'read', 'write', 'delete'")
    accessed_at: datetime = Field(default_factory=_utc_now, description="When accessed (UTC)")
    accessed_by: str = Field(description="Who/what accessed the entry")
    context_data: dict | None = Field(default=None, sa_column=Column(JSON), description="Additional context (JSON)")


# Database engine setup
# Usage: engine = get_engine("sqlite:///database.db")
# For production, replace with appropriate database URL
def get_engine(database_url: str = "sqlite:///database.db", echo: bool = False):
    """
    Create and return a database engine.
    
    Args:
        database_url: Database connection string (default: SQLite database)
        echo: Enable SQL query logging for debugging (default: False)
        
    Returns:
        SQLModel engine instance
    """
    engine = create_engine(database_url, echo=echo)
    return engine


# Model classification for dual-engine architecture
METADATA_MODELS = [ToolRegistry, CodeVault, ResourceRegistry, PromptRegistry, ExecutionLog, MacroRegistry, SecurityPolicy, IconRegistry, AgentNotebook, NotebookHistory, NotebookAudit]
DATA_MODELS = [SalesPerDay]


def create_db_and_tables(engine, models=None):
    """
    Create database tables for specified models.
    
    Args:
        engine: SQLModel engine instance
        models: List of model classes to create. If None, creates all tables.
    """
    if models is None:
        # Create all tables (backward compatibility)
        SQLModel.metadata.create_all(engine)
    else:
        # Create only specified model tables
        tables = [model.__table__ for model in models]
        SQLModel.metadata.create_all(engine, tables=tables)
