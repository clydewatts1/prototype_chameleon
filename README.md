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

### 1. Configuration (Optional)

The server uses a YAML-based configuration system. You can configure the server by creating a config file at `~/.chameleon/config/config.yaml`.

**Create Configuration:**

```bash
# Create the config directory
mkdir -p ~/.chameleon/config

# Copy the sample config file
cp config.yaml.sample ~/.chameleon/config/config.yaml

# Edit the config file with your preferred settings
nano ~/.chameleon/config/config.yaml
```

**Configuration Structure:**

```yaml
server:
  transport: "stdio"  # or "sse" for HTTP Server-Sent Events
  host: "0.0.0.0"     # Host for SSE transport
  port: 8000          # Port for SSE transport
  log_level: "INFO"   # DEBUG, INFO, WARNING, ERROR, or CRITICAL
  logs_dir: "logs"    # Directory for log files (relative or absolute path)

database:
  url: "sqlite:///chameleon.db"  # Database connection URL
```

**Default Behavior:**

If no config file exists, the server uses these defaults:
- Transport: stdio
- Host: 0.0.0.0
- Port: 8000
- Log Level: INFO
- Logs Directory: logs
- Database: sqlite:///chameleon.db

**Command-Line Overrides:**

You can override any config value using command-line arguments:

```bash
# Override transport and port
python server.py --transport sse --port 9000

# Override database URL
python server.py --database-url postgresql://user:pass@localhost/mydb

# Override log level
python server.py --log-level DEBUG

# Override logs directory
python server.py --logs-dir /var/log/chameleon

# See all options
python server.py --help
```

**Priority:** Command-line arguments > YAML config > Defaults

### 2. Run the MCP Server

Start the server using stdio transport:

```bash
python server.py
```

Or with SSE transport:

```bash
python server.py --transport sse --port 8000
```

The server will:
- Load configuration from `~/.chameleon/config/config.yaml` (if it exists)
- Initialize the database connection
- Create tables if they don't exist
- **Automatically seed the database with sample data if empty** (new in this version!)
- Start listening for MCP requests on the configured transport

**Auto-Seeding**: On first run, the server automatically populates the database with sample tools, resources, and prompts. This means you can start using the server immediately without manually running `seed_db.py`.

**Sample Data Included:**

**Tools:**
- `greet` - Greets a person by name (persona: default)
- `add` - Adds two numbers (persona: default)
- `multiply` - Multiplies two numbers (persona: assistant)
- `uppercase` - Converts text to uppercase (persona: default)
- `get_sales_summary` - Get sales summary using SQL SELECT (persona: default)

**Resources:**
- `welcome_message` - Static welcome message (memo://welcome)
- `server_time` - Dynamic resource that returns current server time (system://time)
- `sales_report` - Recent sales report (data://sales/recent)

**Prompts:**
- `review_code` - Template for generating code review requests

### 3. Manually Seed the Database (Optional)

If you want to reset the database or manually populate it with fresh sample data:

```bash
python seed_db.py
```

This will clear existing data and repopulate the database with sample tools, resources, and prompts.

### 4. Run the Admin GUI (Optional)

Manage your tools and database using the Streamlit admin interface:

```bash
streamlit run admin_gui.py
```

The admin GUI provides:
- **Dashboard**: View metrics (total tools, code blobs, unique personas)
- **Tool Registry**: Browse, filter by persona, and delete tools
- **Add New Tool**: Create or update tools with a user-friendly form

**Database Connection:**

The admin GUI uses the same configuration system as the server:

1. **CHAMELEON_DB_URL environment variable** (highest priority)
2. **~/.chameleon/config/config.yaml** config file
3. **Default:** `sqlite:///chameleon.db`

Examples:

```bash
# Use environment variable
export CHAMELEON_DB_URL="postgresql://user:pass@host/db"
streamlit run admin_gui.py

# Or use the config file (create ~/.chameleon/config/config.yaml)
streamlit run admin_gui.py
```

### 5. Interact with the Server

The server implements the MCP protocol and supports:

- **List Tools**: Returns available tools based on the current persona
- **Call Tool**: Executes a tool with provided arguments
- **List Resources**: Returns available resources
- **Read Resource**: Retrieves resource content (static or dynamic)
- **List Prompts**: Returns available prompt templates
- **Get Prompt**: Retrieves and formats a prompt with arguments

Example tool schemas are defined in the database with JSON Schema for validation.

## Connecting AI Clients

Once your Chameleon MCP server is running, you can connect it to various AI clients that support the Model Context Protocol (MCP). Below are configuration instructions for popular AI CLI tools.

### Claude Desktop

Claude Desktop supports MCP servers through its configuration file.

1. **Locate the Claude Desktop configuration file:**
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Add the Chameleon server configuration:**

```json
{
  "mcpServers": {
    "chameleon": {
      "command": "python",
      "args": ["/absolute/path/to/prototype_chameleon/server.py"],
      "env": {
        "CHAMELEON_DB_URL": "sqlite:///chameleon.db"
      }
    }
  }
}
```

3. **Restart Claude Desktop** to load the new configuration.

4. **Verify connection**: The Chameleon tools should now appear in Claude Desktop's tool menu.

### VS Code with Cline Extension

The Cline extension for VS Code supports MCP servers.

1. **Install the Cline extension** from the VS Code marketplace.

2. **Open VS Code settings** (File → Preferences → Settings or `Cmd/Ctrl + ,`).

3. **Search for "MCP"** and add the Chameleon server to the MCP servers configuration:

```json
{
  "cline.mcpServers": {
    "chameleon": {
      "command": "python",
      "args": ["/absolute/path/to/prototype_chameleon/server.py"],
      "env": {
        "CHAMELEON_DB_URL": "sqlite:///chameleon.db"
      }
    }
  }
}
```

4. **Reload VS Code** to activate the configuration.

### Google Gemini CLI (Experimental)

**Note**: As of December 2025, Google's Gemini CLI does not have official MCP support. However, if/when support is added, the configuration pattern would likely be similar:

1. **Check Gemini CLI documentation** for MCP configuration instructions.

2. **Expected configuration pattern** (hypothetical):

```bash
# In your shell configuration (~/.bashrc, ~/.zshrc, etc.)
export GEMINI_MCP_SERVERS='{"chameleon": {"command": "python", "args": ["/absolute/path/to/prototype_chameleon/server.py"]}}'
```

Or via a configuration file (location TBD by Google):

```json
{
  "mcpServers": {
    "chameleon": {
      "command": "python",
      "args": ["/absolute/path/to/prototype_chameleon/server.py"]
    }
  }
}
```

3. **Monitor Google AI documentation** at [https://ai.google.dev/](https://ai.google.dev/) for official MCP support announcements.

### Generic MCP Client Configuration

For any MCP-compatible client, you'll need:

- **Command**: Path to your Python interpreter (e.g., `python`, `python3`, or `/path/to/venv/bin/python`)
- **Args**: `["/absolute/path/to/prototype_chameleon/server.py"]`
- **Environment Variables** (optional):
  - `CHAMELEON_DB_URL`: Database connection string (default: `sqlite:///chameleon.db`)

### Testing the Connection

After configuring your AI client:

1. **Start the client** (restart if already running)
2. **Look for available tools** in the client's interface
3. **Test a simple tool** like `greet` with the argument `{"name": "World"}`
4. **Expected result**: `"Hello World! I am running from the database."`

If tools don't appear, check:
- Server path is correct and absolute
- Python environment has required dependencies installed
- Server has write permissions to create the database file (auto-seeded on first run)
- Client logs for connection errors

### Using Virtual Environments

If you're using a virtual environment for Chameleon, specify the full path to the Python interpreter:

```json
{
  "mcpServers": {
    "chameleon": {
      "command": "/path/to/prototype_chameleon/venv/bin/python",
      "args": ["/path/to/prototype_chameleon/server.py"]
    }
  }
}
```

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

**Configuration Methods (in priority order):**

1. **Command-line argument:**
   ```bash
   python server.py --database-url "postgresql://user:pass@host/db"
   ```

2. **YAML configuration file** (`~/.chameleon/config/config.yaml`):
   ```yaml
   database:
     url: "postgresql://user:pass@host/db"
   ```

3. **Environment variable** (for Admin GUI backward compatibility):
   ```bash
   export CHAMELEON_DB_URL="postgresql://user:pass@host/db"
   streamlit run admin_gui.py
   ```

4. **Default:** `sqlite:///chameleon.db`

**Supported databases:** Any SQLAlchemy-compatible database (SQLite, PostgreSQL, MySQL, etc.)

**Examples:**

```yaml
# SQLite (default)
database:
  url: "sqlite:///chameleon.db"

# PostgreSQL
database:
  url: "postgresql://username:password@localhost:5432/chameleon"

# MySQL
database:
  url: "mysql://username:password@localhost:3306/chameleon"
```

## Development

### Project Structure
```
prototype_chameleon/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── config.py             # Configuration module (YAML config loading)
├── config.yaml.sample    # Sample configuration file
├── models.py             # Database models (CodeVault, ToolRegistry, etc.)
├── runtime.py            # Code execution engine
├── server.py             # MCP server implementation
├── seed_db.py            # Database seeding script
├── admin_gui.py          # Streamlit admin GUI
├── test_config.py        # Configuration module tests
├── test_seed_db.py       # Database seeding tests
├── test_logging.py       # Logging tests
└── .gitignore            # Git ignore patterns
```

### Running Tests

The project includes several test scripts:

1. **Configuration tests:** `python test_config.py`
2. **Database seeding tests:** `python test_seed_db.py`
3. **Server tests:** `python server.py` (database will be auto-seeded on first run)

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
