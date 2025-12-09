"""
Database models for the custom MCP server using SQLModel.

This module defines the database schema for storing code and tool configurations.
"""

from typing import Optional
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


# Database engine setup
# Usage: engine = create_engine("sqlite:///database.db")
# For production, replace with appropriate database URL
def get_engine(database_url: str = "sqlite:///database.db"):
    """
    Create and return a database engine.
    
    Args:
        database_url: Database connection string (default: SQLite database)
        
    Returns:
        SQLModel engine instance
    """
    engine = create_engine(database_url, echo=True)
    return engine


def create_db_and_tables(engine):
    """
    Create all database tables.
    
    Args:
        engine: SQLModel engine instance
    """
    SQLModel.metadata.create_all(engine)
