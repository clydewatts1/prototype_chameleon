"""
MCP Server implementation using low-level Server class.

This module implements a dynamic MCP server that lists and executes tools
based on persona stored in the database.
"""

import asyncio
from typing import Any
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.types import Tool, TextContent
from sqlmodel import Session

from models import get_engine, create_db_and_tables
from runtime import execute_tool, list_tools_for_persona, ToolNotFoundError, SecurityError


# Initialize the server
app = Server('chameleon-engine')

# Database engine - initialized in lifespan
_db_engine = None


def get_db_engine():
    """Get the database engine instance."""
    if _db_engine is None:
        raise RuntimeError("Database not initialized. Server lifespan not started.")
    return _db_engine


@asynccontextmanager
async def lifespan(server_instance):
    """Initialize database on server startup."""
    global _db_engine
    # Setup database
    _db_engine = get_engine("sqlite:///chameleon.db")
    create_db_and_tables(_db_engine)
    yield
    # Cleanup can be added here if needed


# Set up lifespan
app.lifespan = lifespan


def _get_persona_from_context() -> str:
    """
    Extract persona from request context.
    
    Returns:
        The persona string, defaulting to 'default' if not found
    """
    # Default persona
    persona = 'default'
    
    # Try to get persona from request context if available
    # Note: The MCP Server API may not expose request_context directly
    # This is a placeholder for future enhancement when the API supports it
    try:
        if hasattr(app, 'request_context') and app.request_context:
            request_context = app.request_context
            if hasattr(request_context, 'meta'):
                persona = request_context.meta.get('persona', 'default')
    except (AttributeError, Exception):
        # If we can't get the context, use default
        pass
    
    return persona


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    Dynamic tool lister - returns tools based on persona.
    
    The persona is extracted from the request context. If no persona is
    specified, defaults to 'default'.
    
    Returns:
        List of Tool objects available for the current persona
    """
    persona = _get_persona_from_context()
    
    # Get tools from database for this persona
    engine = get_db_engine()
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
        
    Raises:
        Exception: If tool execution fails
    """
    persona = _get_persona_from_context()
    
    try:
        # Execute the tool
        engine = get_db_engine()
        with Session(engine) as session:
            result = execute_tool(name, persona, arguments, session)
        
        # Convert result to string if it's not already
        if result is None:
            result_text = "Tool executed successfully (no return value)"
        else:
            result_text = str(result)
        
        # Wrap in TextContent and return
        return [TextContent(type="text", text=result_text)]
    
    except ToolNotFoundError as e:
        # Tool not found - return helpful error message
        error_text = f"Error: {str(e)}"
        return [TextContent(type="text", text=error_text)]
    
    except SecurityError as e:
        # Security validation failed - return error
        error_text = f"Security Error: {str(e)}"
        return [TextContent(type="text", text=error_text)]
    
    except Exception as e:
        # Unexpected error - return generic error message
        error_text = f"Unexpected error executing tool '{name}': {str(e)}"
        return [TextContent(type="text", text=error_text)]


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
