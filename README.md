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
