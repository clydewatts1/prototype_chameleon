# Prototype Chameleon MCP Server

A dynamic Model Context Protocol (MCP) server that allows execution of tools stored in a database with persona-based tool filtering. This is version 1 of the Chameleon MCP server.

## Overview

Chameleon is an innovative MCP server implementation that stores executable code in a database and dynamically serves tools based on personas. It provides:

- **Dynamic Tool Registry**: Tools are stored in a database and can be added/modified without server code changes
- **Persona-Based Filtering**: Different tools can be exposed to different personas
- **Code Integrity**: SHA-256 hashing ensures code hasn't been tampered with
- **Flexible Execution**: Tools are defined as Python code snippets stored in the database

## Architecture

The project consists of four main components:

1. **models.py**: Database schema using SQLModel
   - `CodeVault`: Stores executable code with SHA-256 hash as primary key
   - `ToolRegistry`: Maps tools to personas with JSON schema definitions

2. **runtime.py**: Secure code execution engine
   - Validates code integrity via hash checking
   - Executes stored code in controlled environment
   - Provides tool listing and execution functions

3. **server.py**: MCP server implementation
   - Implements MCP protocol using low-level Server class
   - Handles tool listing and execution requests
   - Manages database lifecycle

4. **seed_db.py**: Database seeding utility
   - Populates database with sample tools for testing

## Installation

### Prerequisites

- Python 3.12 or higher
- pip (Python package installer)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd prototype_chameleon
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Seed the Database

Before running the server, populate the database with sample tools:

```bash
python seed_db.py
```

This creates a SQLite database (`chameleon.db`) with sample tools:
- `greet` - Greets a person by name (persona: default)
- `add` - Adds two numbers (persona: default)
- `multiply` - Multiplies two numbers (persona: assistant)
- `uppercase` - Converts text to uppercase (persona: default)

### 2. Run the MCP Server

Start the server using stdio transport:

```bash
python server.py
```

The server will:
- Initialize the database connection
- Create tables if they don't exist
- Start listening for MCP requests on stdio

### 3. Interact with the Server

The server implements the MCP protocol and supports:

- **List Tools**: Returns available tools based on the current persona
- **Call Tool**: Executes a tool with provided arguments

Example tool schemas are defined in the database with JSON Schema for validation.

## Adding Custom Tools

To add your own tools to the database:

1. Write your tool code as a Python snippet that:
   - Reads from `arguments` dict
   - Optionally uses `db_session` for database access
   - Sets a `result` variable to return a value

2. Compute the SHA-256 hash of your code

3. Insert into `CodeVault` table with the hash and code

4. Register in `ToolRegistry` with:
   - Tool name
   - Target persona
   - Description
   - JSON Schema for input validation
   - Reference to the code hash

Example:
```python
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables
from sqlmodel import Session
import hashlib

# Your tool code
code = """
result = arguments.get('value', 0) * 2
"""

# Compute hash
code_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()

# Insert into database
engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    # Add code
    vault = CodeVault(hash=code_hash, python_blob=code)
    session.add(vault)
    
    # Register tool
    tool = ToolRegistry(
        tool_name="double",
        target_persona="default",
        description="Doubles a number",
        input_schema={
            "type": "object",
            "properties": {
                "value": {"type": "number", "description": "Value to double"}
            },
            "required": ["value"]
        },
        active_hash_ref=code_hash
    )
    session.add(tool)
    session.commit()
```

## Security Considerations

⚠️ **Important Security Notes**:

- The server uses `exec()` to run code from the database
- Code integrity is verified via SHA-256 hashing
- **This design assumes code in CodeVault is trusted**
- For production use with untrusted code, consider:
  - Additional sandboxing (e.g., RestrictedPython, containers)
  - Restricted database interfaces
  - Process isolation
  - Input validation and sanitization

## Database

The server uses SQLite by default (`chameleon.db`). The database file is automatically created on first run.

To use a different database, modify the connection string in:
- `server.py` (line 39): `get_engine("sqlite:///chameleon.db")`
- `seed_db.py` (line 25): default parameter

Supported databases: Any SQLAlchemy-compatible database (PostgreSQL, MySQL, etc.)

## Development

### Project Structure
```
prototype_chameleon/
├── README.md           # This file
├── requirements.txt    # Python dependencies
├── models.py          # Database models (CodeVault, ToolRegistry)
├── runtime.py         # Code execution engine
├── server.py          # MCP server implementation
├── seed_db.py         # Database seeding script
└── .gitignore         # Git ignore patterns
```

### Running Tests

Currently, the project uses manual testing via `seed_db.py` and running the server. To test:

1. Seed the database: `python seed_db.py`
2. Run the server: `python server.py`
3. Send MCP requests to test tool listing and execution

## Personas

The persona system allows different tool sets for different contexts:
- `default`: Standard tools available to all users
- `assistant`: Specialized tools for assistant persona
- Custom personas can be added as needed

Currently, persona is determined by the `_get_persona_from_context()` function (defaults to 'default').

## License

[Add your license information here]

## Contributing

[Add contributing guidelines here]
