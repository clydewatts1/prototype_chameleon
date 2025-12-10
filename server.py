"""
MCP Server implementation using low-level Server class.

This module implements a dynamic MCP server that lists and executes tools
based on persona stored in the database.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import (
    Tool, 
    TextContent, 
    Resource, 
    Prompt, 
    PromptArgument, 
    GetPromptResult,
    PromptMessage
)
from sqlmodel import Session, select

from config import load_config
from models import get_engine, create_db_and_tables, ToolRegistry
from runtime import (
    execute_tool, 
    list_tools_for_persona, 
    list_resources_for_persona,
    list_prompts_for_persona,
    get_resource,
    get_prompt,
    ToolNotFoundError, 
    SecurityError,
    ResourceNotFoundError,
    PromptNotFoundError
)
from seed_db import seed_database


# Initialize the server
app = Server('chameleon-engine')

# Database engine - initialized in lifespan
_db_engine = None
# Database URL - set in lifespan from config
_database_url = None


def setup_logging(log_level: str = "INFO", logs_dir: str = "logs"):
    """
    Configure logging for the MCP server.
    
    Creates a logs directory if it doesn't exist, generates a timestamped
    log file, and enforces a limit of 10 log files by deleting the oldest ones.
    Configures the root logger to write to both the log file and stderr.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        logs_dir: Directory path for log files (default: "logs")
    """
    # Create logs directory if it doesn't exist
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped log filename with microsecond precision
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_filename = logs_path / f"mcp_server_{timestamp}.log"
    
    # Enforce log file limit (keep only 10 newest)
    log_files = sorted(logs_path.glob("mcp_server_*.log"), key=lambda p: p.stat().st_ctime)
    if len(log_files) >= 10:
        # Delete oldest files to keep only 9, so with the new one we'll have 10
        files_to_delete = log_files[:len(log_files) - 9]
        for old_file in files_to_delete:
            try:
                old_file.unlink()
            except OSError as e:
                # If we can't delete a file, just log it to stderr
                print(f"Warning: Could not delete old log file {old_file}: {e}", file=sys.stderr)
    
    # Parse log level (with validation)
    log_level_upper = log_level.upper()
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level_upper not in valid_levels:
        print(f"Warning: Invalid log level '{log_level}'. Using INFO.", file=sys.stderr)
        log_level_upper = 'INFO'
    
    numeric_level = getattr(logging, log_level_upper)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(numeric_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Stderr handler
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(numeric_level)
    stderr_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    stderr_handler.setFormatter(stderr_formatter)
    root_logger.addHandler(stderr_handler)
    
    logging.info(f"Logging initialized. Log file: {log_filename}, Level: {log_level}")


def get_db_engine():
    """Get the database engine instance."""
    if _db_engine is None:
        raise RuntimeError("Database not initialized. Server lifespan not started.")
    return _db_engine


@asynccontextmanager
async def lifespan(server_instance):
    """Initialize database on server startup."""
    global _db_engine, _database_url
    
    # _database_url should already be set by main() before app.run() is called
    if _database_url is None:
        # Fallback to default if not set
        from config import get_default_config
        _database_url = get_default_config()['database']['url']
    
    # Setup database
    _db_engine = get_engine(_database_url)
    create_db_and_tables(_db_engine)
    logging.info(f"Database initialized at {_database_url}")
    
    # Auto-seed database if empty
    with Session(_db_engine) as session:
        existing_tools = session.exec(select(ToolRegistry)).first()
        if not existing_tools:
            # Database is empty, seed it with sample data
            logging.info("Database is empty, seeding with sample data...")
            seed_database(database_url=_database_url, clear_existing=False)
            logging.info("Database seeding completed")
    
    yield
    # Cleanup can be added here if needed
    logging.info("Server shutting down...")


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
    logging.info(f"Listing tools for persona: {persona}")
    
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
    
    logging.info(f"Returning {len(tools)} tool(s) for persona: {persona}")
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
    logging.info(f"Calling tool '{name}' for persona '{persona}' with arguments: {arguments}")
    
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
        
        logging.info(f"Tool '{name}' executed successfully")
        # Wrap in TextContent and return
        return [TextContent(type="text", text=result_text)]
    
    except ToolNotFoundError as e:
        # Tool not found - return helpful error message
        logging.error(f"Tool not found: {str(e)}")
        error_text = f"Error: {str(e)}"
        return [TextContent(type="text", text=error_text)]
    
    except SecurityError as e:
        # Security validation failed - return error
        logging.error(f"Security error executing tool '{name}': {str(e)}")
        error_text = f"Security Error: {str(e)}"
        return [TextContent(type="text", text=error_text)]
    
    except Exception as e:
        # Unexpected error - return generic error message
        logging.error(f"Unexpected error executing tool '{name}': {str(e)}", exc_info=True)
        error_text = f"Unexpected error executing tool '{name}': {str(e)}"
        return [TextContent(type="text", text=error_text)]


@app.list_resources()
async def handle_list_resources() -> list[Resource]:
    """
    List all available resources.
    
    Returns:
        List of Resource objects available
    """
    persona = _get_persona_from_context()
    logging.info(f"Listing resources for persona: {persona}")
    
    # Get resources from database
    engine = get_db_engine()
    with Session(engine) as session:
        resources_data = list_resources_for_persona(persona, session)
    
    # Convert to MCP Resource objects
    resources = []
    for resource_data in resources_data:
        resource = Resource(
            uri=resource_data['uri'],
            name=resource_data['name'],
            description=resource_data.get('description'),
            mimeType=resource_data.get('mimeType')
        )
        resources.append(resource)
    
    logging.info(f"Returning {len(resources)} resource(s) for persona: {persona}")
    return resources


@app.read_resource()
async def handle_read_resource(uri: str) -> list[ReadResourceContents]:
    """
    Read a specific resource by URI.
    
    Args:
        uri: URI of the resource to read
        
    Returns:
        List of ReadResourceContents with the resource data
        
    Raises:
        Exception: If resource reading fails
    """
    persona = _get_persona_from_context()
    logging.info(f"Reading resource '{uri}' for persona '{persona}'")
    
    try:
        # Get the resource content
        engine = get_db_engine()
        with Session(engine) as session:
            content = get_resource(uri, persona, session)
        
        logging.info(f"Resource '{uri}' read successfully")
        # Return as list of ReadResourceContents
        return [
            ReadResourceContents(
                content=content,
                mime_type="text/plain"
            )
        ]
    
    except ResourceNotFoundError as e:
        # Resource not found - raise exception
        logging.error(f"Resource not found: {str(e)}")
        raise ValueError(f"Error: {str(e)}")
    
    except SecurityError as e:
        # Security validation failed
        logging.error(f"Security error reading resource '{uri}': {str(e)}")
        raise ValueError(f"Security Error: {str(e)}")
    
    except Exception as e:
        # Unexpected error
        logging.error(f"Unexpected error reading resource '{uri}': {str(e)}", exc_info=True)
        raise ValueError(f"Unexpected error reading resource '{uri}': {str(e)}")


@app.list_prompts()
async def handle_list_prompts() -> list[Prompt]:
    """
    List all available prompts.
    
    Returns:
        List of Prompt objects available
    """
    persona = _get_persona_from_context()
    
    # Get prompts from database
    engine = get_db_engine()
    with Session(engine) as session:
        prompts_data = list_prompts_for_persona(persona, session)
    
    # Convert to MCP Prompt objects
    prompts = []
    for prompt_data in prompts_data:
        # Convert arguments to PromptArgument objects
        arguments = []
        for arg in prompt_data.get('arguments', []):
            arguments.append(
                PromptArgument(
                    name=arg['name'],
                    description=arg.get('description'),
                    required=arg.get('required', False)
                )
            )
        
        prompt = Prompt(
            name=prompt_data['name'],
            description=prompt_data.get('description'),
            arguments=arguments if arguments else None
        )
        prompts.append(prompt)
    
    return prompts


@app.get_prompt()
async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    """
    Get a specific prompt by name with formatted arguments.
    
    Args:
        name: Name of the prompt to get
        arguments: Arguments to format the prompt template with
        
    Returns:
        GetPromptResult containing the formatted prompt
        
    Raises:
        Exception: If prompt retrieval fails
    """
    persona = _get_persona_from_context()
    
    try:
        # Get the formatted prompt
        engine = get_db_engine()
        with Session(engine) as session:
            result = get_prompt(name, arguments or {}, persona, session)
        
        # Convert messages to PromptMessage objects
        messages = []
        for msg in result['messages']:
            messages.append(
                PromptMessage(
                    role=msg['role'],
                    content=TextContent(
                        type=msg['content']['type'],
                        text=msg['content']['text']
                    )
                )
            )
        
        # Return as GetPromptResult
        return GetPromptResult(
            description=result.get('description'),
            messages=messages
        )
    
    except PromptNotFoundError as e:
        # Prompt not found
        raise ValueError(f"Error: {str(e)}")
    
    except ValueError as e:
        # Missing required argument
        raise ValueError(f"Error: {str(e)}")
    
    except Exception as e:
        # Unexpected error
        raise ValueError(f"Unexpected error getting prompt '{name}': {str(e)}")


async def main():
    """Main entry point for the MCP server."""
    global _database_url
    
    # Load configuration from YAML file
    config = load_config()
    
    # Parse command-line arguments (overrides config file)
    parser = argparse.ArgumentParser(description='Chameleon MCP Server')
    parser.add_argument(
        '--transport',
        default=config['server']['transport'],
        choices=['stdio', 'sse'],
        help='Transport type (default: from config or stdio)'
    )
    parser.add_argument(
        '--host',
        default=config['server']['host'],
        help='Host for SSE transport (default: from config or 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=config['server']['port'],
        help='Port for SSE transport (default: from config or 8000)'
    )
    parser.add_argument(
        '--log-level',
        default=config['server']['log_level'],
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: from config or INFO)'
    )
    parser.add_argument(
        '--logs-dir',
        default=config['server']['logs_dir'],
        help='Directory path for log files (default: from config or logs)'
    )
    parser.add_argument(
        '--database-url',
        default=config['database']['url'],
        help='Database URL (default: from config or sqlite:///chameleon.db)'
    )
    
    args = parser.parse_args()
    
    # Setup logging with configured level and directory
    setup_logging(args.log_level, args.logs_dir)
    logging.info("Server starting up...")
    logging.info(f"Transport: {args.transport}")
    logging.info(f"Database URL: {args.database_url}")
    logging.info(f"Logs directory: {args.logs_dir}")
    
    # Set database URL for lifespan handler
    _database_url = args.database_url
    
    # Run with appropriate transport
    if args.transport == 'stdio':
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    
    elif args.transport == 'sse':
        # SSE transport support
        try:
            import uvicorn
            from mcp.server.sse import SseServerTransport
            from starlette.applications import Starlette
            from starlette.routing import Route
        except ImportError:
            logging.error("SSE transport requires 'uvicorn' and 'starlette' packages.")
            logging.error("Install with: pip install uvicorn starlette")
            sys.exit(1)
        
        # Create SSE transport
        sse = SseServerTransport("/messages")
        
        # Create Starlette app with SSE endpoint
        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=sse.handle_sse),
                Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
            ],
        )
        
        # Run MCP server as background task
        async def run_mcp_server():
            async with sse.connect_sse() as streams:
                await app.run(
                    streams[0],
                    streams[1],
                    app.create_initialization_options()
                )
        
        # Start MCP server task and keep reference to prevent garbage collection
        mcp_task = asyncio.create_task(run_mcp_server())
        
        # Run uvicorn server
        logging.info(f"Starting SSE server on {args.host}:{args.port}")
        try:
            uvicorn.run(
                starlette_app,
                host=args.host,
                port=args.port,
                log_level=args.log_level.lower()
            )
        finally:
            # Cancel the MCP task when uvicorn stops
            mcp_task.cancel()
            try:
                await mcp_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
