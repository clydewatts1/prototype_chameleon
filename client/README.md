# AI-Powered MCP Debugger

A Streamlit-based GUI for debugging and interacting with the MCP (Model Context Protocol) server using AI assistance. This tool allows you to chat with your MCP server through an LLM interface (Gemini or Ollama).

## Features

- 🤖 **LLM Integration**: Support for both Google Gemini and Ollama
- 🔧 **MCP Server Connection**: Automatically connects to the MCP server in `../server/server.py`
- 💬 **Chat Interface**: Interactive chat with AI assistance for server debugging
- 🛠️ **Tool Execution**: Automatically discovers and executes MCP server tools
- 🔍 **Protocol Inspector**: View raw JSON-RPC messages between client and server
- ⚙️ **Configurable**: Customize server command, arguments, and working directory

## Installation

1. **Install dependencies**:
   ```bash
   cd client
   pip install -r requirements.txt
   ```

2. **Configure LLM Provider** (choose one):

   ### Option 1: Google Gemini
   - Get an API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a `.env` file in the client directory:
     ```
     GEMINI_API_KEY=your_api_key_here
     ```

   ### Option 2: Ollama
   - Install Ollama from [ollama.ai](https://ollama.ai/)
   - Pull a model:
     ```bash
     ollama pull llama3
     ```

## Usage

1. **Start the debugger**:
   ```bash
   cd client
   streamlit run debugger.py
   ```

2. **Configure in the UI**:
   - Select your LLM provider (Gemini or Ollama) in the sidebar
   - Enter API key (for Gemini) or model name (for Ollama)
   - Verify server configuration (defaults to `../server/server.py`)

3. **Start chatting**:
   - Type your questions in the chat input
   - The AI will automatically discover and use available MCP tools
   - View tool execution details in expandable sections

## How It Works

### The Agent Loop

1. **Connect**: Establishes a stdio connection to the MCP server
2. **List Tools**: Retrieves available tools from the server
3. **Translate**: Converts MCP tool definitions to LLM-compatible format
4. **Think**: Sends your question + available tools to the LLM
5. **Act**: If the LLM decides to use a tool:
   - Displays tool call with arguments
   - Executes the tool via MCP
   - Shows the result
6. **Reply**: LLM generates final response based on tool results
7. **Response**: Displays the answer to you

### Protocol Inspector

The Protocol Inspector captures raw JSON-RPC messages exchanged between the client and server, helping you:
- Debug communication issues
- Understand the MCP protocol
- Trace tool execution flow

## Configuration

### Server Configuration (Sidebar)

- **Server Command**: Command to run the server (default: `python`)
- **Server Args**: Arguments for the server (default: `../server/server.py`)
- **Server Working Directory**: Directory to run server from (default: `../server`)

### LLM Configuration (Sidebar)

#### Gemini
- **API Key**: Your Google Gemini API key

#### Ollama
- **Model Name**: Ollama model to use (default: `llama3`)

## Example Interactions

Here are some example questions you can ask:

- "What tools are available on this server?"
- "List all the customers in the database"
- "Can you help me debug why tool X is not working?"
- "Show me the sales data for last month"

The AI will automatically determine which tools to use and execute them for you.

## Troubleshooting

### "MCP library not installed"
```bash
pip install mcp
```

### "No LLM providers available"
Install at least one LLM provider:
```bash
pip install google-generativeai  # For Gemini
# OR
pip install ollama  # For Ollama
```

### "Error connecting to Ollama"
Make sure Ollama is running:
```bash
ollama serve
```

### Server not found
- Verify the server path in the sidebar configuration
- Ensure the server directory exists at `../server/`
- Check that `server.py` is present in the server directory

## Requirements

- Python 3.8+
- Streamlit
- MCP Python SDK
- Google Generative AI SDK (for Gemini) or Ollama (for Ollama)
- python-dotenv

## License

See the parent repository for license information.
