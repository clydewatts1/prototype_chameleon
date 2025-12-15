# GitHub Copilot Instructions for Prototype Chameleon

This document provides guidance for GitHub Copilot when working with the Prototype Chameleon repository.

## Project Overview

Prototype Chameleon is a Model Context Protocol (MCP) server implementation with an AI-powered debugging client. The project features:

- **Server (`server/`)**: Dynamic MCP server that stores tools, resources, and prompts in a database
- **Client (`client/`)**: Streamlit-based AI debugger for interacting with the MCP server
- **Core Features**:
  - Class-based plugin architecture with `ChameleonTool` base class
  - Dynamic tool registry with persona-based filtering
  - Self-modifying capabilities (LLMs can create SQL tools at runtime)
  - Jinja2 + SQLAlchemy for secure dynamic SQL
  - Deep execution audit trail for AI self-healing
  - YAML-based configuration system

## Repository Structure

```
prototype_chameleon/
├── server/                    # MCP Server implementation
│   ├── server.py             # Main MCP server
│   ├── base.py               # ChameleonTool base class
│   ├── models.py             # Database models (CodeVault, ToolRegistry, etc.)
│   ├── runtime.py            # Code execution engine
│   ├── config.py             # Configuration management
│   ├── load_specs.py         # YAML-based tool loader
│   ├── export_specs.py       # Database export utility
│   ├── specs.yaml            # Default tool definitions
│   ├── conftest.py           # Pytest shared fixtures
│   └── tests/                # Pytest test suite
├── client/                    # AI-Powered Debugger
│   ├── debugger.py           # Streamlit GUI
│   └── requirements.txt      # Client dependencies
├── pytest.ini                # Pytest configuration
└── README.md                 # Main documentation
```

## Code Conventions

### Python Style
- Use **Python 3.12** features and standards
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Prefer f-strings for string formatting
- Use descriptive variable names

### Database Models
- All models use **SQLModel** (combines SQLAlchemy + Pydantic)
- Database models are defined in `server/models.py`
- Key models:
  - `CodeVault`: Stores executable code with SHA-256 hash as primary key
  - `ToolRegistry`: Maps tools to personas with JSON schema definitions
  - `ResourceRegistry`: Defines resources with static or dynamic content
  - `PromptRegistry`: Stores prompt templates
  - `ExecutionLog`: Audit trail for tool executions

### Tool Development
All Python tools **MUST** inherit from `ChameleonTool`:

```python
from base import ChameleonTool

class MyTool(ChameleonTool):
    def run(self, arguments):
        # Access arguments
        value = arguments.get('key', 'default')
        
        # Use logging
        self.log(f"Processing {value}")
        
        # Access database session (if needed)
        # result = self.db_session.exec(statement).all()
        
        # Access context
        persona = self.context.get('persona')
        
        # Return result
        return result
```

**Security Rules:**
- Only imports and class definitions allowed at top level
- No arbitrary code execution at module level
- AST-based validation enforces this

### SQL Tools
Use **Jinja2 for structure** and **SQLAlchemy parameter binding for values**:

```sql
SELECT column1, column2
FROM table_name
WHERE 1=1
{% if arguments.filter_field %}
  AND column1 = :filter_field
{% endif %}
ORDER BY column1
```

**CRITICAL Security Rules:**
- ✅ Use Jinja2 for conditional SQL structure
- ✅ Use `:param_name` syntax for all values
- ❌ NEVER use Jinja2 for values (SQL injection risk!)
- ❌ NEVER use string interpolation for values
- Only SELECT statements allowed (enforced)
- Single statement validation (prevents chaining)

## Configuration System

The project uses a **hierarchical configuration system** (priority order):

1. **Command-line arguments** (highest priority)
2. **YAML config file** (`~/.chameleon/config/config.yaml`)
3. **Environment variables** (backward compatibility only)
4. **Default values** (lowest priority)

Configuration structure (`config.yaml`):
```yaml
server:
  transport: "stdio"        # or "sse"
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"         # DEBUG, INFO, WARNING, ERROR, CRITICAL
  logs_dir: "logs"

database:
  url: "sqlite:///chameleon.db"
```

## Testing

### Test Framework
- Use **pytest** for all tests
- Test configuration: `pytest.ini`
- Shared fixtures: `server/conftest.py`
- Test directory: `server/tests/`

### Running Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest server/tests/test_security_pytest.py

# Run tests by marker
pytest -m security
pytest -m integration
```

### Test Markers
- `@pytest.mark.integration` - Integration tests requiring database setup
- `@pytest.mark.security` - Security-related tests
- `@pytest.mark.slow` - Slow-running tests

### Writing Tests
```python
def test_something(db_session):
    """Test description."""
    # Use db_session fixture for database access
    # Use pytest assertions
    assert result == expected
    
    # Use pytest.raises for exception testing
    with pytest.raises(ValueError):
        function_that_should_fail()
```

### Shared Fixtures
- `db_engine` - Temporary SQLite database engine
- `db_session` - Database session with automatic rollback

## YAML Tool Definitions

Tools are defined in YAML files (e.g., `server/specs.yaml`):

```yaml
tools:
  - name: tool_name
    persona: default              # Target persona
    description: Tool description
    code_type: python             # 'python' or 'select'
    code: |
      # Python or SQL code here
    input_schema:
      type: object
      properties:
        param_name:
          type: string
          description: Parameter description
      required:
        - param_name
```

Load tools with:
```bash
python load_specs.py specs.yaml
python load_specs.py specs.yaml --clean  # Clear existing data first
```

## Common Patterns

### Database Access
```python
from sqlmodel import Session
from models import get_engine

engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    # Use session for queries
    pass
```

### Configuration Loading
```python
from config import load_config

config = load_config()
db_url = config['database']['url']
log_level = config['server']['log_level']
```

### Tool Execution
```python
from runtime import execute_tool

result = execute_tool(
    tool_name="greet",
    persona="default",
    arguments={"name": "World"},
    db_session=session
)
```

## Key Features to Understand

### 1. Dynamic Tool Creation (SQL Creator Meta-Tool)
- LLMs can create new SQL tools at runtime via `create_new_sql_tool`
- Created tools are marked with `is_auto_created=true`
- Enforces strict security (SELECT-only, single statement)
- See `server/SQL_CREATOR_TOOL_README.md` for details

### 2. Execution Audit Trail
- Every tool execution is logged in `ExecutionLog` table
- Captures full Python tracebacks for failures
- `get_last_error` tool for debugging
- Enables AI self-healing workflows
- See `server/EXECUTION_LOG_README.md` for details

### 3. Persona-Based Filtering
- Tools can target specific personas (default, assistant, etc.)
- Allows different tool sets for different contexts
- Persona is determined by context in MCP requests

### 4. Code Integrity
- SHA-256 hashing ensures code hasn't been tampered with
- Code stored in `CodeVault` with hash as primary key
- Tools reference code via `active_hash_ref`

## Security Considerations

⚠️ **CRITICAL**: 
- Server uses `exec()` to run code from database
- **Only use with trusted code sources**
- **DO NOT use in production with untrusted code without additional sandboxing**
- SQL tools enforce SELECT-only and parameter binding
- AST validation prevents arbitrary top-level code execution

## Documentation Files

When working on specific features, refer to:
- `server/README.md` - Comprehensive server documentation
- `server/SQL_CREATOR_TOOL_README.md` - SQL Creator meta-tool
- `server/EXECUTION_LOG_README.md` - Execution logging and debugging
- `PYTEST_MIGRATION.md` - Testing guide
- `DATABASE_CONFIG_VALIDATION.md` - Database configuration
- `client/README.md` - Client documentation

## Development Workflow

1. **Making Changes**:
   - Understand the component you're modifying
   - Check existing tests for patterns
   - Follow established code conventions

2. **Adding Tools**:
   - Define in YAML (preferred) or use Python seeding
   - Follow tool conventions (Python: inherit from `ChameleonTool`, SQL: use Jinja2 + parameter binding)
   - Include comprehensive input_schema

3. **Testing Changes**:
   - Write tests in `server/tests/` using pytest
   - Use appropriate test markers
   - Ensure tests are isolated and reproducible

4. **Database Changes**:
   - Update models in `server/models.py`
   - Test with both SQLite and PostgreSQL if possible
   - Consider migration path for existing databases

## Common Commands

```bash
# Server
cd server
python server.py                          # Run MCP server
python load_specs.py specs.yaml          # Load tools from YAML
python export_specs.py > output.yaml     # Export database to YAML
python seed_db.py                        # Legacy seeding (deprecated)
streamlit run admin_gui.py               # Run admin GUI

# Client
cd client
streamlit run debugger.py                # Run AI debugger

# Testing
pytest                                   # Run all tests
pytest -v                                # Verbose output
pytest -m security                       # Run security tests only
pytest server/tests/test_config.py       # Run specific test file

# Configuration
mkdir -p ~/.chameleon/config
cp config.yaml.sample ~/.chameleon/config/config.yaml
```

## Tips for Copilot

- When creating new tools, always inherit from `ChameleonTool`
- When writing SQL, remember: Jinja2 for structure, SQLAlchemy binding for values
- When adding tests, use pytest fixtures from `conftest.py`
- When accessing database, use SQLModel Session pattern
- When documenting, maintain consistency with existing documentation style
- Security is paramount: validate all code execution paths
- The project uses modern Python (3.12+) features
