"""
Pytest fixtures for the Chameleon MCP Server test suite.

This module provides shared fixtures for database setup and teardown.
"""

import pytest
import tempfile
import os
import sys
from sqlmodel import Session, create_engine

# Add server directory to Python path so server modules can import each other
server_path = os.path.join(os.path.dirname(__file__), '..', 'server')
sys.path.insert(0, os.path.abspath(server_path))

from models import create_db_and_tables


@pytest.fixture(scope="function")
def db_engine():
    """
    Create a temporary file-based SQLite database engine for testing.
    
    This fixture:
    - Creates a temporary file-based SQLite database (to allow multiple connections)
    - Initializes all database tables
    - Yields the engine for use in tests
    - Disposes of the engine and deletes the file after the test completes
    
    Note: We use a file-based database instead of :memory: because some tests
    need to pass the database URL to functions that create their own connections,
    and :memory: creates separate databases for each connection.
    
    Yields:
        Engine: SQLModel engine instance connected to temporary database
    """
    # Create temporary database file
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    # Create engine with the file-based database
    engine = create_engine(db_url, echo=False)
    
    # Create all tables
    create_db_and_tables(engine)
    
    # Yield engine to the test
    yield engine
    
    # Cleanup: dispose of the engine and remove the file
    engine.dispose()
    try:
        os.unlink(temp_db.name)
    except OSError:
        # File may already be deleted or locked
        pass


@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    Create a database session for testing.
    
    This fixture:
    - Depends on db_engine fixture
    - Creates a new Session for each test
    - Yields the session for use in tests
    - Rolls back and closes the session after the test completes
    
    Args:
        db_engine: The database engine fixture
        
    Yields:
        Session: SQLModel session instance
    """
    # Create session from engine
    session = Session(db_engine)
    
    # Yield session to the test
    yield session
    
    # Cleanup: rollback any uncommitted changes and close
    session.rollback()
    session.close()
