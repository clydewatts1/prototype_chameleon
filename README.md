# Chameleon MCP Server🦎
**A Dynamic, Self-Modifying MCP Server & AI Debugger**

Prototype Chameleon is an advanced Model Context Protocol (MCP) implementation that shifts tool management from static files to a database-backed registry. It is designed to empower autonomous AI agents with the ability to evolve their capabilities at runtime while maintaining strict security standards.

**Key Features:**
* **🧠 Self-Modifying Architecture:** LLMs can dynamically create new SQL tools via a meta-tool, using Jinja2 templates for structure and SQLAlchemy for secure parameter binding.
* **❤️‍🩹 AI Self-Healing:** Implements a "Black Box" recorder pattern that captures full Python tracebacks during failures, allowing agents to diagnose bugs and patch their own tools.
* **🗄️ Database Agnostic:** Built on SQLModel and SQLAlchemy, enabling seamless deployment on SQLite (default), PostgreSQL, MySQL, or any other supported backend without code changes.
* **📊 Generative UI:** Includes a "Chameleon UI" feature that enables LLMs to write and host interactive Streamlit dashboards on demand.
* **🛡️ Secure Execution:** Features a custom runtime with AST-based code validation, hash integrity checks, and persona-based tool filtering.
* **📂 Group Organization:** Tools, resources, and prompts are organized into logical groups (e.g., `utility`, `system`) with automatic namespacing.
* **🚀 Self-Improving Agentic System:** An "Autopoietic System" capable of maintaining and creating itself, enabling fully autonomous evolution.
* **🐞 AI Debugger:** A built-in Streamlit client that connects via stdio to inspect protocol messages and interactively debug server tools.

# Prototype Chameleon - MCP Server and AI Debugger

This repository contains a Model Context Protocol (MCP) server implementation and an AI-powered debugging client.


> 🚧 **Project Status: Alpha**
> This project is currently in Alpha. APIs may change, and "self-modifying" features should be used in controlled environments.

Prototype Chameleon is an advanced Model Context Protocol (MCP) implementation...
## Repository Structure

```
prototype_chameleon/
├── server/          # MCP Server implementation
│   ├── server.py    # Main MCP server
│   ├── base.py      # Base classes for tools
│   ├── models.py    # Database models
│   ├── runtime.py   # Code execution engine
│   ├── config.py    # Configuration management
│   └── ...          # Additional server files and tests
│
└── client/          # AI-Powered MCP Debugger
    ├── debugger.py  # Streamlit GUI debugger
    ├── requirements.txt
    └── README.md    # Client documentation
```

## Quick Start

### 1. Set Up the Server

```bash
cd server
pip install -r requirements.txt

# Run the server (database auto-seeds on first run)
python server.py

# Optional: Load custom tools from YAML
python load_specs.py specs.yaml
```

**Note:** The server automatically initializes and seeds the database on first run. You no longer need to manually run `seed_db.py` unless you want to reset to defaults.

See [server/README.md](server/README.md) for detailed server documentation.

### 2. Set Up the Client (AI Debugger)

```bash
cd client
pip install -r requirements.txt

# Configure your LLM provider (Gemini or Ollama)
# For Gemini: Create .env file with GEMINI_API_KEY
# For Ollama: Ensure ollama is installed and running

# Run the debugger
streamlit run debugger.py
```

See [client/README.md](client/README.md) for detailed client documentation.

## Schema Migration & Specs Loader

The specs loader (server/load_specs.py) creates tables and synchronizes tools/resources/prompts from YAML (e.g., server/specs.yaml, server/retail.yml). It also performs a light schema reconciliation for SQLite to keep the `toolregistry` table compatible across versions.

- Auto-migration: If the `toolregistry.is_auto_created` column is missing, the loader adds it automatically (BOOLEAN NOT NULL DEFAULT 0). This prevents errors when loading specs after upgrading code.
- Clean load: Use `--clean` to clear existing rows before reloading specs.

Examples (PowerShell):

```powershell
# Load default specs from server/specs.yaml
python .\server\load_specs.py .\server\specs.yaml

# Load and clear existing data first
python .\server\load_specs.py .\server\specs.yaml --clean

# Load a different spec file (e.g., retail tools)
python .\server\load_specs.py .\server\retail.yml
```

Notes:
- The database URL is taken from config.yaml by default. Override with `--database` if needed.
- The loader will create tables if they don’t exist. For SQLite, schema changes are applied minimally to preserve data.

## What's Included

### MCP Server (`server/`)

A dynamic MCP server featuring:

**Core Capabilities:**
- Stores tools, resources, and prompts in a database
- Supports persona-based filtering
- YAML-based configuration
- Comprehensive testing suite

**Advanced Features:**
- **Jinja2 + SQLAlchemy SQL**: Secure dynamic SQL queries with Jinja2 for structure and parameter binding for values
- **SQL Creator Meta-Tool**: LLMs can create new SQL tools dynamically at runtime
- **Deep Execution Audit**: Full traceback logging for AI self-diagnosis and self-healing
- **Auto-Created Tool Tracking**: `is_auto_created` flag distinguishes LLM-created vs. system tools

### AI-Powered Debugger (`client/`)

A Streamlit GUI that:
- Connects to the MCP server via stdio
- Uses AI (Gemini or Ollama) to interact with server tools
- Provides a chat interface for debugging
- Displays tool execution details
- Captures protocol messages for inspection

## Key Features

### 1. Jinja2 + SQLAlchemy for Secure Dynamic SQL

Create SQL tools with optional filters using Jinja2 templates for structure and parameter binding for values:

```sql
SELECT * FROM sales
WHERE 1=1
{% if arguments.store_name %}
  AND store_name = :store_name
{% endif %}
{% if arguments.min_amount %}
  AND amount >= :min_amount
{% endif %}
ORDER BY date DESC
```

- **Jinja2**: Controls SQL structure (optional WHERE clauses)
- **SQLAlchemy**: Safely binds values to prevent SQL injection
- **Security**: Only SELECT statements allowed, single statement validation

See [server/README.md](server/README.md) for complete documentation.

### 2. Self-Modifying AI Agent via SQL Creator Meta-Tool

LLMs can create new SQL tools dynamically at runtime:

```json
{
  "tool_name": "search_inventory",
  "description": "Search inventory with optional category filter",
  "sql_query": "SELECT * FROM inventory WHERE 1=1 {% if arguments.category %} AND category = :category {% endif %}",
  "parameters": {
    "category": {"type": "string", "required": false}
  }
}
```

- Created tools are immediately available
- Enforces strict security (SELECT-only, single statement)
- Tools marked with `is_auto_created=true` flag for tracking

See [server/SQL_CREATOR_TOOL_README.md](server/SQL_CREATOR_TOOL_README.md) for complete documentation.

### 3. Deep Execution Audit for AI Self-Healing

Comprehensive execution logging enables AI agents to self-diagnose and fix broken tools:

```python
# AI creates a tool with a bug
# AI tests the tool → receives generic error

# AI queries for detailed error
error_info = execute_tool("get_last_error", "default", {"tool_name": "broken_tool"}, session)

# Returns full Python traceback with line numbers:
# "Traceback (most recent call last):
#   File "runtime.py", line 361, in execute_tool
#     result = tool_instance.run(arguments)
#   File "<string>", line 7, in run
# ZeroDivisionError: division by zero"

# AI analyzes traceback and fixes the code
```

- Automatic logging of all executions
- Full tracebacks with exact line numbers
- Independent persistence (survives transaction failures)
- `get_last_error` tool for querying errors

See [server/EXECUTION_LOG_README.md](server/EXECUTION_LOG_README.md) for complete documentation.

## Use Cases

1. **Autonomous AI Agents**: Self-modifying agents that create tools and self-heal when they break
2. **Interactive Debugging**: Chat with your MCP server to debug issues
3. **Dynamic Data Analysis**: LLMs create custom SQL queries on the fly
4. **Tool Discovery**: Let AI help you explore available tools
5. **Protocol Learning**: View raw JSON-RPC messages to understand MCP
6. **Development Workflow**: Test server changes interactively

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Client    │         │     LLM      │         │ MCP Server  │
│ (Streamlit) │◄───────►│ Gemini/Ollama│◄───────►│  (Python)   │
│             │  Chat   │              │  Tools  │             │
│ debugger.py │         │              │         │  server.py  │
└─────────────┘         └──────────────┘         └─────────────┘
       │                                                  │
       │                                                  │
       │              stdio/JSON-RPC                      │
       └──────────────────────────────────────────────────┘
                                                          │
                                    ┌─────────────────────┴─────────────────────┐
                                    │                                           │
                              ┌─────▼──────┐                           ┌───────▼────────┐
                              │ Metadata   │                           │  Data Database │
                              │  Database  │                           │   (Optional)   │
                              │            │                           │                │
                              │  Tools     │                           │ Business Data  │
                              │  Resources │                           │ sales_per_day  │
                              │  Prompts   │                           │      etc.      │
                              │  Code      │                           │                │
                              └────────────┘                           └────────────────┘
```

**Dual Database Design:**
- **Metadata Database**: Stores all server configuration, tools, and code (required)
- **Data Database**: Stores business/application data (optional, offline mode available)

**Supported Databases:**
- SQLite (default, no additional drivers required)
- PostgreSQL (enterprise-grade, recommended for production)
- MySQL (wide deployment support)
- Neo4j (experimental, graph database for data analytics)

For detailed information on database connectivity, connection strings, and setup instructions, see [DATABASE_CONNECTIVITY.md](DATABASE_CONNECTIVITY.md).

For a detailed flow chart, see [server/SERVER_FLOW_CHART.md](server/SERVER_FLOW_CHART.md)

## Contributing

See individual component READMEs:
- [Server Documentation](server/README.md)
- [Client Documentation](client/README.md)

## License

This project is available for use under the terms specified in the LICENSE file.
