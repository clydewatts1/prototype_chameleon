"""
Pytest fixtures for the Chameleon MCP Server test suite.

This module provides shared fixtures for database setup and teardown.
"""

import pytest
from sqlmodel import Session, create_engine
from models import create_db_and_tables


@pytest.fixture(scope="function")
def db_engine():
    """
    Create an in-memory SQLite database engine for testing.
    
    This fixture:
    - Creates an in-memory SQLite database
    - Initializes all database tables
    - Yields the engine for use in tests
    - Disposes of the engine after the test completes
    
    Yields:
        Engine: SQLModel engine instance connected to in-memory database
    """
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Create all tables
    create_db_and_tables(engine)
    
    # Yield engine to the test
    yield engine
    
    # Cleanup: dispose of the engine
    engine.dispose()


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
