"""Test server with debugging."""
import asyncio
import traceback
from typing import Any
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.types import (
    Tool, 
    TextContent, 
    Resource, 
    Prompt, 
    PromptArgument, 
    GetPromptResult,
    PromptMessage,
    TextResourceContents,
    ReadResourceResult
)
from sqlmodel import Session

from models import get_engine, create_db_and_tables
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

# Initialize the server
app = Server('chameleon-engine')

# Database engine
_db_engine = None

def get_db_engine():
    if _db_engine is None:
        raise RuntimeError("Database not initialized")
    return _db_engine

@asynccontextmanager
async def lifespan(server_instance):
    global _db_engine
    _db_engine = get_engine("sqlite:///chameleon.db")
    create_db_and_tables(_db_engine)
    yield

app.lifespan = lifespan

def _get_persona_from_context() -> str:
    return 'default'

@app.list_resources()
async def handle_list_resources() -> list[Resource]:
    persona = _get_persona_from_context()
    engine = get_db_engine()
    with Session(engine) as session:
        resources_data = list_resources_for_persona(persona, session)
    
    resources = []
    for resource_data in resources_data:
        resource = Resource(
            uri=resource_data['uri'],
            name=resource_data['name'],
            description=resource_data.get('description'),
            mimeType=resource_data.get('mimeType')
        )
        resources.append(resource)
    
    return resources

@app.read_resource()
async def handle_read_resource(uri: str) -> ReadResourceResult:
    print(f"[DEBUG] handle_read_resource called with uri: {uri}")
    persona = _get_persona_from_context()
    
    try:
        engine = get_db_engine()
        with Session(engine) as session:
            content = get_resource(uri, persona, session)
        
        print(f"[DEBUG] Got content: {content}")
        print(f"[DEBUG] Content type: {type(content)}")
        
        # Create TextResourceContents
        text_content = TextResourceContents(
            uri=uri,
            mimeType="text/plain",
            text=content
        )
        print(f"[DEBUG] Created TextResourceContents: {text_content}")
        print(f"[DEBUG] Type: {type(text_content)}")
        
        # Create ReadResourceResult
        result = ReadResourceResult(
            contents=[text_content]
        )
        print(f"[DEBUG] Created ReadResourceResult: {result}")
        print(f"[DEBUG] Result type: {type(result)}")
        print(f"[DEBUG] Result.contents type: {type(result.contents)}")
        print(f"[DEBUG] Result.contents[0] type: {type(result.contents[0])}")
        
        return result
    
    except ResourceNotFoundError as e:
        print(f"[DEBUG] ResourceNotFoundError: {e}")
        traceback.print_exc()
        raise ValueError(f"Error: {str(e)}")
    
    except SecurityError as e:
        print(f"[DEBUG] SecurityError: {e}")
        traceback.print_exc()
        raise ValueError(f"Security Error: {str(e)}")
    
    except Exception as e:
        print(f"[DEBUG] Unexpected error: {e}")
        traceback.print_exc()
        raise ValueError(f"Unexpected error reading resource '{uri}': {str(e)}")


async def main():
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
