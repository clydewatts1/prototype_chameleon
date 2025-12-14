# Pytest Migration Guide

This document describes the pytest migration for the Chameleon MCP Server test suite.

## Overview

The test suite has been migrated from standalone test scripts to a professional pytest-based test suite with:
- Centralized configuration via `pytest.ini`
- Shared fixtures for database setup (`server/conftest.py`)
- Organized test structure in `server/tests/`
- Proper test markers for filtering tests
- Better reporting and test isolation

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest server/tests/test_security_pytest.py
```

### Run tests by marker
```bash
# Run only security tests
pytest -m security

# Run only integration tests
pytest -m integration
```

### Run specific test
```bash
pytest server/tests/test_security_pytest.py::test_basic_select_without_jinja
```

## Test Structure

```
prototype_chameleon/
├── pytest.ini                          # Pytest configuration
├── server/
│   ├── conftest.py                    # Shared fixtures
│   └── tests/                         # Test directory
│       ├── __init__.py
│       ├── test_seed_db_pytest.py     # Database seeding tests
│       ├── test_security_pytest.py    # Security validation tests
│       └── test_sql_creator_pytest.py # SQL Creator meta-tool tests
```

## Shared Fixtures

### `db_engine`
Creates a temporary file-based SQLite database for testing. The engine is disposed and the file is cleaned up after the test.

**Usage:**
```python
def test_something(db_engine):
    # Use db_engine to create sessions or pass to functions
    pass
```

### `db_session`
Creates a database session from `db_engine`. The session is rolled back and closed after the test for isolation.

**Usage:**
```python
def test_something(db_session):
    # Use db_session to interact with the database
    pass
```

## Test Markers

- `@pytest.mark.integration` - Tests that require full database setup and integration
- `@pytest.mark.security` - Security-related tests (SQL injection, access control, etc.)
- `@pytest.mark.slow` - Tests that take longer to run

## Migrated Tests

### test_seed_db_pytest.py
Migrated from `test_seed_db.py`:
- Uses `db_session` fixture
- Uses pytest assertions (`assert x == y`)
- Better test isolation
- Multiple test functions for different aspects

### test_security_pytest.py
Migrated from `test_runtime_security.py`:
- Uses `db_session` fixture with `setup_sales_data` helper
- Uses `pytest.raises()` for exception testing
- Uses `@pytest.mark.parametrize` for testing multiple similar cases
- All print statements converted to assertions

### test_sql_creator_pytest.py
Migrated from `test_sql_creator_tool.py`:
- Uses `registered_meta_tool` fixture for setup
- Uses pytest assertions throughout
- Cleaner test structure with better isolation

## Configuration (pytest.ini)

```ini
[pytest]
# Test discovery
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*

# Test directory
testpaths = server/tests

# Output options
addopts = 
    -v
    --strict-markers
    --tb=short

# Markers
markers =
    integration: Integration tests that require database setup
    security: Security-related tests
    slow: Slow-running tests
```

## Benefits of Migration

1. **Better Test Organization**: Tests are now in a dedicated `server/tests/` directory
2. **Shared Fixtures**: Database setup is centralized in `conftest.py`, reducing duplication
3. **Better Reporting**: Pytest provides detailed pass/fail reports with counts
4. **Test Isolation**: Each test gets a fresh database session
5. **Selective Testing**: Run specific test subsets using markers or file paths
6. **Parametrized Tests**: Easily test multiple scenarios with `@pytest.mark.parametrize`
7. **Better Assertions**: Clear, readable assertions that provide helpful error messages

## Notes

- The original test files (`test_*.py` in `server/`) are preserved and still functional
- The new pytest tests are in `server/tests/` directory
- Both old and new tests can coexist during transition
- Temporary database files are automatically cleaned up after tests
