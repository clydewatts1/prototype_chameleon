# Prototype Chameleon - MCP Server and AI Debugger

This repository contains a Model Context Protocol (MCP) server implementation and an AI-powered debugging client.

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

# Initialize the database
python seed_db.py

# Run the server
python server.py
```

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

A dynamic MCP server that:
- Stores tools, resources, and prompts in a database
- Supports persona-based filtering
- Provides secure code execution
- Offers YAML-based configuration
- Includes comprehensive testing suite

### AI-Powered Debugger (`client/`)

A Streamlit GUI that:
- Connects to the MCP server via stdio
- Uses AI (Gemini or Ollama) to interact with server tools
- Provides a chat interface for debugging
- Displays tool execution details
- Captures protocol messages for inspection

## Use Cases

1. **Interactive Debugging**: Chat with your MCP server to debug issues
2. **Tool Discovery**: Let AI help you explore available tools
3. **Protocol Learning**: View raw JSON-RPC messages to understand MCP
4. **Development Workflow**: Test server changes interactively

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
```

## Contributing

See individual component READMEs:
- [Server Documentation](server/README.md)
- [Client Documentation](client/README.md)

## License

This project is available for use under the terms specified in the LICENSE file.
