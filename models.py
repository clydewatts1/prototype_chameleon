"""
Database models for the custom MCP server using SQLModel.

This module defines the database schema for storing code and tool configurations.
"""

from sqlmodel import Field, SQLModel, create_engine, Column
from sqlalchemy import JSON


class CodeVault(SQLModel, table=True):
    """
    Table for storing executable code with SHA-256 hash as primary key.
    
    Attributes:
        hash: SHA-256 hash of the code (Primary Key)
        code_blob: The executable code as text
        code_type: Type of code ('python' or 'select')
    """
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
    tool_name: str = Field(primary_key=True, description="Name of the tool")
    target_persona: str = Field(primary_key=True, description="Target persona for the tool")
    description: str = Field(description="Description of what the tool does")
    input_schema: dict = Field(sa_column=Column(JSON), description="JSON Schema for the tool arguments")
    active_hash_ref: str = Field(foreign_key="codevault.hash", description="Reference to CodeVault hash")


class ResourceRegistry(SQLModel, table=True):
    """
    Table for registering Resources.
    Resources can be static (text stored here) or dynamic (code in CodeVault).
    """
    uri_schema: str = Field(primary_key=True, description="The URI pattern (e.g. 'note://{id}')")
    name: str = Field(description="Human readable name")
    description: str = Field(description="Description of the resource")
    mime_type: str = Field(default="text/plain", description="MIME type of the content")
    
    # Dynamic vs Static
    is_dynamic: bool = Field(default=False, description="If True, executes code from CodeVault")
    static_content: str | None = Field(default=None, description="Hardcoded content for static resources")
    active_hash_ref: str | None = Field(default=None, foreign_key="codevault.hash", nullable=True, description="Ref to CodeVault if dynamic")
    
    # Persona support
    target_persona: str = Field(default="default", description="Target persona for the resource")


class PromptRegistry(SQLModel, table=True):
    """
    Table for registering Prompts.
    Prompts are templates that the LLM can request.
    """
    name: str = Field(primary_key=True, description="Name of the prompt (e.g. 'review_code')")
    description: str = Field(description="What this prompt does")
    template: str = Field(description="The Jinja2 or f-string template")
    arguments_schema: dict = Field(sa_column=Column(JSON), description="JSON Schema for arguments")
    
    # Persona support
    target_persona: str = Field(default="default", description="Target persona for the prompt")


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
