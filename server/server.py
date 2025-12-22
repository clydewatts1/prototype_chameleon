"""
MCP Server implementation using low-level Server class.

This module implements a dynamic MCP server that lists and executes tools
based on persona stored in the database.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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
    PromptMessage,
    Completion
)
from sqlmodel import Session, select

from config import load_config
from config import load_config
from models import get_engine, create_db_and_tables, ToolRegistry, IconRegistry, METADATA_MODELS, DATA_MODELS
from runtime import (
    execute_tool,
    execute_tool, 
    list_tools_for_persona, 
    list_resources_for_persona,
    list_prompts_for_persona,
    get_resource,
    get_prompt,
    get_tool_completion,
    ToolNotFoundError, 
    SecurityError,
    ResourceNotFoundError,
    PromptNotFoundError
)
from seed_db import seed_database
import json
import base64
from utils import normalize_result

try:
    from toon_format import encode as toon_encode
except ImportError:
    toon_encode = None


# Initialize the server
app = Server('chameleon-engine')

# Database engines - initialized in lifespan
_meta_engine = None  # Metadata engine
_data_engine = None  # Data engine
_data_db_connected = False  # Flag indicating if data DB is available
# Database URLs - set in lifespan from config
_database_url = None
_metadata_database_url = None
_data_database_url = None


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
    # Check if root logger is already configured to prevent duplicate handlers/files
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

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
    """Get the database engine instance (legacy - returns metadata engine)."""
    if _meta_engine is None:
        raise RuntimeError("Database not initialized. Server lifespan not started.")
    return _meta_engine


def get_meta_engine():
    """Get the metadata database engine instance."""
    if _meta_engine is None:
        raise RuntimeError("Metadata database not initialized. Server lifespan not started.")
    return _meta_engine


def get_data_engine():
    """Get the data database engine instance. Returns None if not connected."""
    return _data_engine


def is_data_db_connected():
    """Check if data database is connected."""
    return _data_db_connected


@asynccontextmanager
async def lifespan(server_instance):
    """Initialize database on server startup."""
    global _meta_engine, _data_engine, _data_db_connected
    global _metadata_database_url, _data_database_url
    
    # Load URLs from config if not already set by main()
    if _metadata_database_url is None or _data_database_url is None:
        from config import get_default_config
        default_config = get_default_config()
        if _metadata_database_url is None:
            _metadata_database_url = default_config['metadata_database']['url']
        if _data_database_url is None:
            _data_database_url = default_config['data_database']['url']
    
    # Setup metadata database (critical - must succeed)
    logging.info("Initializing metadata database...")
    _meta_engine = get_engine(_metadata_database_url)
    create_db_and_tables(_meta_engine, METADATA_MODELS)
    logging.info(f"Metadata database initialized at {_metadata_database_url}")
    
    # Setup data database (non-critical - allow failure for offline mode)
    logging.info("Initializing data database...")
    try:
        _data_engine = get_engine(_data_database_url)
        create_db_and_tables(_data_engine, DATA_MODELS)
        _data_db_connected = True
        logging.info(f"Data database initialized at {_data_database_url}")
    except Exception as e:
        _data_engine = None
        _data_db_connected = False
        logging.warning(f"Data database connection failed: {e}")
        logging.warning("Server running in OFFLINE MODE - business data queries will be unavailable")
        logging.warning("Use 'reconnect_db' tool to reconnect at runtime")
    

    
    # Store engines on app instance for access by tools
    app._meta_engine = _meta_engine
    app._data_engine = _data_engine
    app._data_db_connected = _data_db_connected
    
    # Auto-seed database if empty
    with Session(_meta_engine) as session:
        existing_tools = session.exec(select(ToolRegistry)).first()
        if not existing_tools:
            # Database is empty, seed it with sample data
            logging.info("Metadata database is empty, seeding with sample data...")
            seed_database(
                metadata_database_url=_metadata_database_url,
                data_database_url=_data_database_url,
                clear_existing=False
            )
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
        if tool_data.get('icon_name'):
            # Fetch specific icon
            icon_obj = session.exec(select(IconRegistry).where(IconRegistry.icon_name == tool_data['icon_name'])).first()
        else:
            # Fallback to default
            icon_obj = session.exec(select(IconRegistry).where(IconRegistry.icon_name == "default_chameleon")).first()
        
        # Format icons list if icon found
        tool_icons = None
        if icon_obj and icon_obj.content:
            # Construct data URI
            if icon_obj.mime_type == 'image/svg+xml':
                # For SVG, valid to just use the content if it's text, but base64 is safer for transport
                # If content already starts with 'data:', use it as is
                if icon_obj.content.startswith('data:'):
                    src = icon_obj.content
                else:
                    # Check if it's base64 already or raw XML. 
                    # Heuristic: SVGs start with <, base64 usually doesn't (unless it's a very fresh coincindence)
                    if icon_obj.content.strip().startswith('<'):
                        # It's raw XML, encode it
                        b64_content = base64.b64encode(icon_obj.content.encode('utf-8')).decode('utf-8')
                        src = f"data:image/svg+xml;base64,{b64_content}"
                    else:
                        # Assume already base64
                        src = f"data:image/svg+xml;base64,{icon_obj.content}"
            else:
                 # PNG or other
                 if icon_obj.content.startswith('data:'):
                     src = icon_obj.content
                 else:
                     src = f"data:{icon_obj.mime_type};base64,{icon_obj.content}"
                     
            tool_icons = [{"src": src, "mimeType": icon_obj.mime_type}]

        tool = Tool(
            name=tool_data['name'],
            description=tool_data['description'],
            inputSchema=tool_data['input_schema']
        )
        # Manually inject icons field since it might not be in the mcp.types.Tool definition yet depending on version,
        # but the JSON serialization will handle it if we add it to the object's __dict__ or if we're careful.
        # Actually, mcp.types.Tool is a Pydantic model. We should check if it supports 'icons'.
        # If the installed SDK version supports it, we just pass it to constructor. 
        # For safety/compatibility let's try to pass it to constructor, catching TypeError if not supported.
        try:
             tool = Tool(
                name=tool_data['name'],
                description=tool_data['description'],
                inputSchema=tool_data['input_schema'],
                icons=tool_icons
            )
        except TypeError:
             # Fallback for older SDKs: standard tool without icons
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
    # 1. Extract format preference
    output_format = arguments.pop('_format', 'json').lower()
    
    persona = _get_persona_from_context()
    logging.info(f"Calling tool '{name}' for persona '{persona}' with arguments: {arguments} (format: {output_format})")
    
    try:
        # Execute the tool with dual sessions
        meta_engine = get_meta_engine()
        data_engine = get_data_engine()
        
        with Session(meta_engine) as meta_session:
            # Create data_session only if data_engine is available
            if data_engine is not None:
                with Session(data_engine) as data_session:
                    result = execute_tool(name, persona, arguments, meta_session, data_session)
            else:
                result = execute_tool(name, persona, arguments, meta_session, None)
        
        # 2. Normalize Data
        clean_result = normalize_result(result)
        
        # 3. Format Output
        if output_format == 'toon':
            if toon_encode:
                try:
                    result_text = toon_encode(clean_result)
                except Exception as e:
                    result_text = f"Error encoding TOON: {e}\n{json.dumps(clean_result, default=str)}"
            else:
                result_text = "Error: toon-format library not installed."
        elif output_format == 'json':
            result_text = json.dumps(clean_result, indent=2, default=str, ensure_ascii=False)
        else:
            result_text = str(clean_result)
        
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


@app.completion()
async def handle_completion(ref: str, argument: str, value: str | None = None) -> list[Completion]:
    """
    Provide completion suggestions for tool arguments.
    """
    persona = _get_persona_from_context()
    logging.info(f"Completion request for tool '{ref}', argument '{argument}', persona '{persona}', prefix='{value}'")

    meta_engine = get_meta_engine()
    data_engine = get_data_engine()
    suggestions: list[str] = []

    try:
        with Session(meta_engine) as meta_session:
            if data_engine is not None:
                with Session(data_engine) as data_session:
                    suggestions = get_tool_completion(ref, argument, value or "", persona, meta_session, data_session)
            else:
                suggestions = get_tool_completion(ref, argument, value or "", persona, meta_session, None)
    except Exception as e:
        logging.error(f"Completion error for tool '{ref}': {e}")
        return []

    return [Completion(value=s) for s in suggestions]
    



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
        # Get the resource content with dual sessions
        meta_engine = get_meta_engine()
        data_engine = get_data_engine()
        
        with Session(meta_engine) as meta_session:
            # Create data_session only if data_engine is available
            if data_engine is not None:
                with Session(data_engine) as data_session:
                    content = get_resource(uri, persona, meta_session, data_session)
            else:
                content = get_resource(uri, persona, meta_session, None)
        
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


@app.read_resource()
async def handle_list_icons_resource(uri: str) -> list[ReadResourceContents]:
    """
    Special handler for icons://list resource.
    Returns a JSON list of all available icons.
    """
    if uri != "icons://list":
        return None
        
    logging.info("Listing all icons via icons://list")
    
    meta_engine = get_meta_engine()
    with Session(meta_engine) as session:
        icons = session.exec(select(IconRegistry)).all()
        
        icon_list = []
        for icon in icons:
            icon_list.append({
                "name": icon.icon_name,
                "mime_type": icon.mime_type,
                "preview": f"(Base64 data length: {len(icon.content)})"
            })
            
        return [
            ReadResourceContents(
                content=json.dumps(icon_list, indent=2),
                mime_type="application/json"
            )
        ]



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
    global _database_url, _metadata_database_url, _data_database_url
    
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
        default=config.get('database', {}).get('url', 'sqlite:///chameleon.db'),
        help='Database URL (legacy single database, default: from config or sqlite:///chameleon.db)'
    )
    parser.add_argument(
        '--metadata-database-url',
        default=config['metadata_database']['url'],
        help='Metadata Database URL (default: from config or sqlite:///chameleon_meta.db)'
    )
    parser.add_argument(
        '--data-database-url',
        default=config['data_database']['url'],
        help='Data Database URL (default: from config or sqlite:///chameleon_data.db)'
    )
    
    args = parser.parse_args()
    
    # Setup logging with configured level and directory
    setup_logging(args.log_level, args.logs_dir)
    logging.info("Server starting up...")
    logging.info(f"Transport: {args.transport}")
    logging.info(f"Metadata Database URL: {args.metadata_database_url}")
    logging.info(f"Data Database URL: {args.data_database_url}")
    logging.info(f"Logs directory: {args.logs_dir}")
    
    # Set database URLs for lifespan handler
    _database_url = args.database_url  # Legacy
    _metadata_database_url = args.metadata_database_url
    _data_database_url = args.data_database_url
    
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
