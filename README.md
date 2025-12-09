# Prototype Chameleon MCP Server

A dynamic Model Context Protocol (MCP) server that allows execution of tools, resources, and prompts stored in a database with persona-based filtering. This is version 2 of the Chameleon MCP server.

## Overview

Chameleon is an innovative MCP server implementation that stores executable code in a database and dynamically serves tools, resources, and prompts based on personas. It provides:

- **Dynamic Tool Registry**: Tools are stored in a database and can be added/modified without server code changes
- **Resource Management**: Support for both static and dynamic resources with code execution
- **Prompt Templates**: Store and format prompt templates with argument substitution
- **Persona-Based Filtering**: Different tools can be exposed to different personas
- **Code Integrity**: SHA-256 hashing ensures code hasn't been tampered with
- **Flexible Execution**: Tools and dynamic resources are defined as Python code snippets stored in the database

## Architecture

The project consists of four main components:

1. **models.py**: Database schema using SQLModel
   - `CodeVault`: Stores executable code with SHA-256 hash as primary key
   - `ToolRegistry`: Maps tools to personas with JSON schema definitions
   - `ResourceRegistry`: Defines resources with static or dynamic content
   - `PromptRegistry`: Stores prompt templates with argument schemas

2. **runtime.py**: Secure code execution engine
   - Validates code integrity via hash checking
   - Executes stored code in controlled environment
   - Provides tool, resource, and prompt listing and execution functions

3. **server.py**: MCP server implementation
   - Implements MCP protocol using low-level Server class
   - Handles tool, resource, and prompt listing and execution requests
   - Manages database lifecycle

4. **seed_db.py**: Database seeding utility
   - Populates database with sample tools, resources, and prompts for testing

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

This creates a SQLite database (`chameleon.db`) with sample data:

**Tools:**
- `greet` - Greets a person by name (persona: default)
- `add` - Adds two numbers (persona: default)
- `multiply` - Multiplies two numbers (persona: assistant)
- `uppercase` - Converts text to uppercase (persona: default)

**Resources:**
- `welcome_message` - Static welcome message (chameleon://welcome)
- `server_time` - Dynamic resource that returns current server time (chameleon://time)

**Prompts:**
- `code_review` - Template for generating code review requests

### 2. Run the MCP Server

Start the server using stdio transport:

```bash
python server.py
```

The server will:
- Initialize the database connection
- Create tables if they don't exist
- Start listening for MCP requests on stdio

### 3. Run the Admin GUI (Optional)

Manage your tools and database using the Streamlit admin interface:

```bash
streamlit run admin_gui.py
```

The admin GUI provides:
- **Dashboard**: View metrics (total tools, code blobs, unique personas)
- **Tool Registry**: Browse, filter by persona, and delete tools
- **Add New Tool**: Create or update tools with a user-friendly form

By default, the GUI connects to `sqlite:///chameleon.db`. To use a different database:

```bash
export CHAMELEON_DB_URL="postgresql://user:pass@host/db"
streamlit run admin_gui.py
```

### 4. Interact with the Server

The server implements the MCP protocol and supports:

- **List Tools**: Returns available tools based on the current persona
- **Call Tool**: Executes a tool with provided arguments
- **List Resources**: Returns available resources
- **Read Resource**: Retrieves resource content (static or dynamic)
- **List Prompts**: Returns available prompt templates
- **Get Prompt**: Retrieves and formats a prompt with arguments

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

## Adding Custom Resources

Resources can be either static or dynamic:

### Static Resource
```python
from models import ResourceRegistry, get_engine
from sqlmodel import Session

engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    resource = ResourceRegistry(
        name="my_static_resource",
        uri_schema="myapp://static/info",
        description="Static information resource",
        is_dynamic=False,
        static_content="This is static content that never changes."
    )
    session.add(resource)
    session.commit()
```

### Dynamic Resource
Dynamic resources execute code from CodeVault to generate content:

```python
from models import CodeVault, ResourceRegistry, get_engine
from sqlmodel import Session
import hashlib

# Code that generates dynamic content
code = """
from datetime import datetime
result = f"Generated at: {datetime.now()}"
"""

code_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()

engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    # Add code to vault
    vault = CodeVault(hash=code_hash, python_blob=code)
    session.add(vault)
    
    # Register dynamic resource
    resource = ResourceRegistry(
        name="my_dynamic_resource",
        uri_schema="myapp://dynamic/timestamp",
        description="Returns current timestamp",
        is_dynamic=True,
        active_hash_ref=code_hash
    )
    session.add(resource)
    session.commit()
```

## Adding Custom Prompts

Prompts are templates that can be formatted with arguments:

```python
from models import PromptRegistry, get_engine
from sqlmodel import Session

engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    prompt = PromptRegistry(
        name="bug_report",
        description="Template for filing bug reports",
        template="Bug Report:\n\nTitle: {title}\n\nDescription: {description}\n\nSteps to reproduce:\n{steps}",
        arguments_schema={
            "arguments": [
                {
                    "name": "title",
                    "description": "Short title for the bug",
                    "required": True
                },
                {
                    "name": "description",
                    "description": "Detailed description of the bug",
                    "required": True
                },
                {
                    "name": "steps",
                    "description": "Steps to reproduce the bug",
                    "required": False
                }
            ]
        }
    )
    session.add(prompt)
    session.commit()
```

## Security Considerations

⚠️ **CRITICAL SECURITY WARNING**:

- The server uses `exec()` to run code from the database with full Python privileges
- **Malicious code could execute arbitrary system commands, access/modify files, make network requests, or compromise the host system**
- Code integrity is verified via SHA-256 hashing (detects tampering, not malicious intent)
- **This design assumes ALL code in CodeVault is from trusted sources**
- **DO NOT use in production with untrusted code without additional security measures**
- For production use with untrusted code, you MUST implement:
  - Additional sandboxing (e.g., RestrictedPython, Docker containers, VMs)
  - Restricted database interfaces with limited privileges
  - Process isolation and resource limits
  - Input validation and sanitization
  - Code review and approval workflows

## Database

The server uses SQLite by default (`chameleon.db`). The database file is automatically created on first run.

To use a different database:
- **Admin GUI**: Set the `CHAMELEON_DB_URL` environment variable (e.g., `export CHAMELEON_DB_URL="postgresql://user:pass@host/db"`)
- **MCP Server**: Modify the connection string in `server.py`, in the `lifespan` function
- **Seed Script**: Modify the default parameter in `seed_db.py`, in the `seed_database` function

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
├── admin_gui.py       # Streamlit admin GUI
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
