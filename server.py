"""
MCP Server implementation using low-level Server class.

This module implements a dynamic MCP server that lists and executes tools
based on persona stored in the database.
"""

import asyncio
from typing import Any
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp import server
from sqlmodel import Session

from models import get_engine, create_db_and_tables
from runtime import execute_tool, list_tools_for_persona


# Initialize the server
app = Server('chameleon-engine')

# Database setup
engine = None


@asynccontextmanager
async def lifespan(server_instance):
    """Initialize database on server startup."""
    global engine
    # Setup database
    engine = get_engine("sqlite:///chameleon.db")
    create_db_and_tables(engine)
    yield
    # Cleanup can be added here if needed


# Set up lifespan
app.lifespan = lifespan


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    Dynamic tool lister - returns tools based on persona.
    
    The persona is extracted from the request context. If no persona is
    specified, defaults to 'default'.
    
    Returns:
        List of Tool objects available for the current persona
    """
    # Get the request context to extract persona
    # For now, we'll use 'default' as the persona
    # In a real implementation, you would extract this from headers or request metadata
    persona = 'default'
    
    # Try to get persona from request context if available
    try:
        request_context = app.request_context
        if request_context and hasattr(request_context, 'meta'):
            persona = request_context.meta.get('persona', 'default')
    except Exception:
        # If we can't get the context, use default
        pass
    
    # Get tools from database for this persona
    with Session(engine) as session:
        tools_data = list_tools_for_persona(persona, session)
    
    # Convert to MCP Tool objects
    tools = []
    for tool_data in tools_data:
        tool = Tool(
            name=tool_data['name'],
            description=tool_data['description'],
            inputSchema=tool_data['input_schema']
        )
        tools.append(tool)
    
    return tools


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Dynamic tool executor - executes tools from the database.
    
    Args:
        name: Name of the tool to execute
        arguments: Arguments to pass to the tool
        
    Returns:
        List containing TextContent with the tool execution result
    """
    # Get persona from request context (default to 'default')
    persona = 'default'
    
    try:
        request_context = app.request_context
        if request_context and hasattr(request_context, 'meta'):
            persona = request_context.meta.get('persona', 'default')
    except Exception:
        pass
    
    # Execute the tool
    with Session(engine) as session:
        result = execute_tool(name, persona, arguments, session)
    
    # Convert result to string if it's not already
    if result is None:
        result_text = "Tool executed successfully (no return value)"
    else:
        result_text = str(result)
    
    # Wrap in TextContent and return
    return [TextContent(type="text", text=result_text)]


async def main():
    """Main entry point for the MCP server."""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
