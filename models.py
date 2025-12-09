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
        python_blob: The executable code as text
    """
    hash: str = Field(primary_key=True, description="SHA-256 hash of the code")
    python_blob: str = Field(description="The executable code")


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
    Table for registering resources with their configurations.
    
    Attributes:
        name: Name of the resource (Primary Key)
        uri_schema: URI schema template (e.g., "note://{id}")
        description: Description of what the resource provides
        is_dynamic: Whether the resource requires code execution
        static_content: Static content for non-dynamic resources (optional)
        active_hash_ref: Foreign key reference to CodeVault hash for dynamic resources (optional)
    """
    name: str = Field(primary_key=True, description="Name of the resource")
    uri_schema: str = Field(description="URI schema template (e.g., 'note://{id}')")
    description: str = Field(description="Description of what the resource provides")
    is_dynamic: bool = Field(default=False, description="Whether the resource requires code execution")
    static_content: str | None = Field(default=None, description="Static content for non-dynamic resources")
    active_hash_ref: str | None = Field(default=None, foreign_key="codevault.hash", description="Reference to CodeVault hash for dynamic resources")


class PromptRegistry(SQLModel, table=True):
    """
    Table for registering prompts with their templates.
    
    Attributes:
        name: Name of the prompt (Primary Key)
        description: Description of what the prompt does
        template: Template text for the prompt
        arguments_schema: JSON schema for the prompt arguments (stored as dict/JSON)
    """
    name: str = Field(primary_key=True, description="Name of the prompt")
    description: str = Field(description="Description of what the prompt does")
    template: str = Field(description="Template text for the prompt")
    arguments_schema: dict = Field(sa_column=Column(JSON), description="JSON schema for the prompt arguments")


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
