"""
Database models for the custom MCP server using SQLModel.

This module defines the database schema for storing code and tool configurations.
"""

from sqlmodel import Field, SQLModel, create_engine, Column
from sqlalchemy import JSON, Text
from datetime import date, datetime
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
    code_type: str = Field(default="python", description="Type of code: 'python' or 'select'")


class ToolRegistry(SQLModel, table=True):
    """
    Table for registering tools with their configurations and personas.
    
    Attributes:
        tool_name: Name of the tool (Primary Key)
        target_persona: The persona this tool targets (Primary Key)
        description: Description of what the tool does
        input_schema: JSON Schema for the tool arguments (stored as dict/JSON)
        active_hash_ref: Foreign key reference to CodeVault hash
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
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of execution (UTC)")
    tool_name: str = Field(description="Name of the tool executed")
    persona: str = Field(description="Persona context")
    arguments: dict = Field(sa_column=Column(JSON), description="Input arguments (JSON)")
    status: str = Field(description="Execution status: 'SUCCESS' or 'FAILURE'")
    result_summary: str = Field(description="Output/result (truncated to ~2000 chars)")
    error_traceback: str | None = Field(sa_column=Column(Text), default=None, description="Full Python traceback for failures")


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


def create_db_and_tables(engine):
    """
    Create all database tables.
    
    Args:
        engine: SQLModel engine instance
    """
    SQLModel.metadata.create_all(engine)
