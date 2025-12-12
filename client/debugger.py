"""
AI-Powered MCP Debugger

A Streamlit GUI that spawns an MCP server subprocess and interacts with it using an LLM.
Supports both Gemini and Ollama as LLM providers.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import MCP client
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    st.error("MCP library not installed. Run: pip install mcp")
    st.stop()

# Import LLM providers
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import ollama
except ImportError:
    ollama = None


@dataclass
class ProtocolMessage:
    """Represents a JSON-RPC message"""
    direction: str  # "request" or "response"
    timestamp: str
    message: Dict[str, Any]


@dataclass
class SessionState:
    """Session state management"""
    messages: List[Dict[str, str]] = field(default_factory=list)
    protocol_messages: List[ProtocolMessage] = field(default_factory=list)
    llm_provider: Optional[str] = None
    llm_client: Optional[Any] = None
    server_command: str = "python"
    server_args: List[str] = field(default_factory=lambda: ["../server/server.py"])
    server_cwd: str = "../server"


def init_session_state():
    """Initialize Streamlit session state"""
    if "state" not in st.session_state:
        st.session_state.state = SessionState()


def detect_server_path() -> Path:
    """Automatically detect the path to server.py"""
    # Try relative path from client directory
    current_dir = Path(__file__).parent
    server_path = current_dir.parent / "server" / "server.py"
    
    if server_path.exists():
        return server_path
    
    # Fallback to default
    return Path("../server/server.py")


def setup_llm_provider():
    """Setup LLM provider in sidebar"""
    st.sidebar.header("🤖 LLM Configuration")
    
    provider_options = []
    if genai:
        provider_options.append("Gemini")
    if ollama:
        provider_options.append("Ollama")
    
    if not provider_options:
        st.sidebar.error("No LLM providers available. Install google-generativeai or ollama.")
        return None
    
    provider = st.sidebar.selectbox("Select Provider", provider_options)
    
    if provider == "Gemini":
        api_key = st.sidebar.text_input("Gemini API Key", type="password", 
                                       value=os.getenv("GEMINI_API_KEY", ""))
        if api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-pro')
                st.session_state.state.llm_provider = "Gemini"
                st.session_state.state.llm_client = model
                st.sidebar.success("✅ Gemini configured")
                return model
            except Exception as e:
                st.sidebar.error(f"Error configuring Gemini: {e}")
                return None
        else:
            st.sidebar.warning("Please enter Gemini API key")
            return None
    
    elif provider == "Ollama":
        model_name = st.sidebar.text_input("Model Name", value="llama3")
        if model_name:
            try:
                # Test connection
                ollama.list()
                st.session_state.state.llm_provider = "Ollama"
                st.session_state.state.llm_client = model_name
                st.sidebar.success(f"✅ Ollama configured (model: {model_name})")
                return model_name
            except Exception as e:
                st.sidebar.error(f"Error connecting to Ollama: {e}")
                return None
        else:
            st.sidebar.warning("Please enter model name")
            return None
    
    return None


def setup_server_config():
    """Configure server parameters in sidebar"""
    st.sidebar.header("⚙️ Server Configuration")
    
    # Detect server path
    default_server_path = detect_server_path()
    
    server_command = st.sidebar.text_input("Server Command", 
                                          value=st.session_state.state.server_command)
    server_args_str = st.sidebar.text_input("Server Args (comma-separated)", 
                                           value=",".join(st.session_state.state.server_args))
    server_cwd = st.sidebar.text_input("Server Working Directory",
                                      value=st.session_state.state.server_cwd)
    
    # Update session state
    st.session_state.state.server_command = server_command
    st.session_state.state.server_args = [arg.strip() for arg in server_args_str.split(",")]
    st.session_state.state.server_cwd = server_cwd
    
    st.sidebar.info(f"📁 Detected server path: {default_server_path}")


def translate_tools_to_gemini(tools: List[Dict]) -> List[Any]:
    """Translate MCP tools to Gemini FunctionDeclaration format"""
    if not genai:
        return []
    
    function_declarations = []
    for tool in tools:
        # Extract tool information
        name = tool.get("name", "unknown")
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})
        
        # Build parameters for Gemini
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        # Convert to Gemini format
        parameters = {}
        for prop_name, prop_info in properties.items():
            param_type = prop_info.get("type", "string")
            param_desc = prop_info.get("description", "")
            
            # Map JSON schema types to Gemini types
            type_mapping = {
                "string": "STRING",
                "number": "NUMBER",
                "integer": "INTEGER",
                "boolean": "BOOLEAN",
                "array": "ARRAY",
                "object": "OBJECT"
            }
            
            parameters[prop_name] = {
                "type": type_mapping.get(param_type, "STRING"),
                "description": param_desc
            }
        
        # Create FunctionDeclaration
        func_decl = genai.protos.FunctionDeclaration(
            name=name,
            description=description,
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties=parameters,
                required=required
            )
        )
        function_declarations.append(func_decl)
    
    return function_declarations


def translate_tools_to_ollama(tools: List[Dict]) -> List[Dict]:
    """Translate MCP tools to Ollama tools JSON format"""
    ollama_tools = []
    for tool in tools:
        ollama_tool = {
            "type": "function",
            "function": {
                "name": tool.get("name", "unknown"),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {})
            }
        }
        ollama_tools.append(ollama_tool)
    
    return ollama_tools


async def call_mcp_tool(session: ClientSession, tool_name: str, arguments: Dict) -> Any:
    """Call an MCP tool and return the result"""
    try:
        result = await session.call_tool(tool_name, arguments)
        return result
    except Exception as e:
        return {"error": str(e)}


async def chat_with_mcp(user_message: str):
    """Main agent loop: Connect to MCP, list tools, interact with LLM"""
    state = st.session_state.state
    
    if not state.llm_client:
        st.error("Please configure an LLM provider first")
        return
    
    # Add user message to history
    state.messages.append({"role": "user", "content": user_message})
    
    # Display user message
    with st.chat_message("user"):
        st.write(user_message)
    
    # Show status
    status = st.status("🔄 Processing...", expanded=True)
    
    try:
        # Configure server parameters
        server_params = StdioServerParameters(
            command=state.server_command,
            args=state.server_args,
            cwd=state.server_cwd
        )
        
        status.write("📡 Connecting to MCP server...")
        
        # Connect to MCP server
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()
                
                status.write("🔍 Listing available tools...")
                
                # List tools
                tools_response = await session.list_tools()
                tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    }
                    for tool in tools_response.tools
                ]
                
                status.write(f"✅ Found {len(tools)} tools")
                
                # Translate tools to LLM format
                if state.llm_provider == "Gemini":
                    llm_tools = translate_tools_to_gemini(tools)
                else:
                    llm_tools = translate_tools_to_ollama(tools)
                
                status.write("🤔 Asking LLM...")
                
                # Build conversation for LLM
                if state.llm_provider == "Gemini":
                    # Call Gemini
                    model = state.llm_client
                    
                    # Create tool config
                    tool_config = genai.protos.Tool(function_declarations=llm_tools)
                    
                    # Start chat with history
                    chat_history = []
                    for msg in state.messages[:-1]:  # Exclude the last message we just added
                        role = "user" if msg["role"] == "user" else "model"
                        chat_history.append({"role": role, "parts": [msg["content"]]})
                    
                    chat = model.start_chat(history=chat_history)
                    
                    # Send message with tools
                    response = chat.send_message(
                        user_message,
                        tools=[tool_config]
                    )
                    
                    # Check for function calls
                    if response.candidates and response.candidates[0].content.parts:
                        part = response.candidates[0].content.parts[0]
                        
                        if hasattr(part, 'function_call') and part.function_call:
                            # LLM wants to call a function
                            func_call = part.function_call
                            tool_name = func_call.name
                            tool_args = dict(func_call.args)
                            
                            status.write(f"🛠️ Calling Tool: {tool_name}")
                            
                            # Show tool call in UI
                            with st.chat_message("assistant"):
                                st.write(f"🛠️ **Calling Tool:** `{tool_name}`")
                                with st.expander("📋 Tool Arguments", expanded=False):
                                    st.json(tool_args)
                            
                            # Execute tool
                            tool_result = await call_mcp_tool(session, tool_name, tool_args)
                            
                            # Display result
                            with st.chat_message("assistant"):
                                with st.expander("🔍 Tool Result", expanded=True):
                                    if hasattr(tool_result, 'content'):
                                        for content_item in tool_result.content:
                                            if hasattr(content_item, 'text'):
                                                st.code(content_item.text)
                                            else:
                                                st.json(content_item)
                                    else:
                                        st.json(tool_result)
                            
                            status.write("💭 Getting final response from LLM...")
                            
                            # Send result back to LLM
                            function_response = genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": str(tool_result)}
                                )
                            )
                            
                            final_response = chat.send_message(function_response)
                            final_text = final_response.text
                            
                        else:
                            # Direct response without tool call
                            final_text = response.text
                    else:
                        final_text = "No response from LLM"
                
                else:  # Ollama
                    # Call Ollama
                    model_name = state.llm_client
                    
                    # Build messages for Ollama
                    messages = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in state.messages
                    ]
                    
                    # Send to Ollama with tools
                    response = ollama.chat(
                        model=model_name,
                        messages=messages,
                        tools=llm_tools
                    )
                    
                    # Check for tool calls
                    if response.get('message', {}).get('tool_calls'):
                        tool_calls = response['message']['tool_calls']
                        
                        for tool_call in tool_calls:
                            tool_name = tool_call['function']['name']
                            tool_args = tool_call['function']['arguments']
                            
                            status.write(f"🛠️ Calling Tool: {tool_name}")
                            
                            # Show tool call in UI
                            with st.chat_message("assistant"):
                                st.write(f"🛠️ **Calling Tool:** `{tool_name}`")
                                with st.expander("📋 Tool Arguments", expanded=False):
                                    st.json(tool_args)
                            
                            # Execute tool
                            tool_result = await call_mcp_tool(session, tool_name, tool_args)
                            
                            # Display result
                            with st.chat_message("assistant"):
                                with st.expander("🔍 Tool Result", expanded=True):
                                    if hasattr(tool_result, 'content'):
                                        for content_item in tool_result.content:
                                            if hasattr(content_item, 'text'):
                                                st.code(content_item.text)
                                            else:
                                                st.json(content_item)
                                    else:
                                        st.json(tool_result)
                            
                            status.write("💭 Getting final response from LLM...")
                            
                            # Add tool result to messages
                            messages.append(response['message'])
                            messages.append({
                                "role": "tool",
                                "content": str(tool_result),
                                "name": tool_name
                            })
                            
                            # Get final response
                            final_response = ollama.chat(
                                model=model_name,
                                messages=messages
                            )
                            final_text = final_response['message']['content']
                    else:
                        # Direct response without tool call
                        final_text = response['message']['content']
                
                # Display final response
                with st.chat_message("assistant"):
                    st.write(final_text)
                
                # Add to history
                state.messages.append({"role": "assistant", "content": final_text})
                
                status.update(label="✅ Complete!", state="complete")
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
        status.update(label="❌ Error", state="error")
        import traceback
        st.code(traceback.format_exc())


def display_protocol_inspector():
    """Display Protocol Inspector in sidebar or expandable section"""
    st.sidebar.header("🔍 Protocol Inspector")
    
    state = st.session_state.state
    
    if state.protocol_messages:
        st.sidebar.write(f"**Messages captured:** {len(state.protocol_messages)}")
        
        with st.sidebar.expander("View Messages", expanded=False):
            for i, msg in enumerate(state.protocol_messages):
                st.write(f"**{msg.direction.upper()} [{msg.timestamp}]**")
                st.json(msg.message)
                st.divider()
    else:
        st.sidebar.info("No protocol messages captured yet")


def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="AI-Powered MCP Debugger",
        page_icon="🔧",
        layout="wide"
    )
    
    st.title("🔧 AI-Powered MCP Debugger")
    st.markdown("Debug your MCP server with AI assistance")
    
    # Initialize session state
    init_session_state()
    
    # Sidebar configuration
    setup_llm_provider()
    setup_server_config()
    display_protocol_inspector()
    
    # Clear chat button
    if st.sidebar.button("🗑️ Clear Chat History"):
        st.session_state.state.messages = []
        st.session_state.state.protocol_messages = []
        st.rerun()
    
    # Chat interface
    st.header("💬 Chat")
    
    # Display chat history
    for message in st.session_state.state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about your MCP server..."):
        # Run async chat function
        asyncio.run(chat_with_mcp(prompt))


if __name__ == "__main__":
    main()
