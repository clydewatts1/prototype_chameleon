#!/usr/bin/env python3
"""
Bootstrap script for registering Prompt and Resource Meta-Tools.

This script registers two meta-tools that allow the LLM to:
1. Create or update prompts dynamically in the PromptRegistry
2. Create or update static resources dynamically in the ResourceRegistry

Usage:
    python add_dynamic_meta_tools.py
"""

import hashlib
import sys
from sqlmodel import Session, select

from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables


def _compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def register_prompt_creator_tool(database_url: str = None):
    """
    Register the create_new_prompt meta-tool in the database.
    
    This meta-tool enables the LLM to create or update prompts dynamically.
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
    """
    print("\n📝 Registering Prompt Creator Meta-Tool...")
    
    # Load configuration if database_url not provided
    if database_url is None:
        config = load_config()
        database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    
    # Create engine and tables
    try:
        engine = get_engine(database_url)
        create_db_and_tables(engine)
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        return False
    
    # Define the meta-tool code blob
    tool_code = """from base import ChameleonTool
from sqlmodel import select
import hashlib
import json

class PromptCreatorTool(ChameleonTool):
    def run(self, arguments):
        '''
        Create or update a prompt in the PromptRegistry.
        
        Args:
            name: The prompt name (e.g., 'review_code')
            description: What the prompt does
            template: The Jinja2/f-string template content
            arguments: List of argument definitions (name, description, required)
                      Format: [{"name": "code", "description": "Code to review", "required": true}]
            persona: Target persona (default: 'default')
        
        Returns:
            Success message confirming the prompt is registered
        '''
        from models import PromptRegistry
        
        # Extract arguments
        name = arguments.get('name')
        description = arguments.get('description')
        template = arguments.get('template')
        args_list = arguments.get('arguments', [])
        persona = arguments.get('persona', 'default')
        
        # Validation: Check all required arguments are provided
        if not name:
            return "Error: name is required"
        if not description:
            return "Error: description is required"
        if not template:
            return "Error: template is required"
        
        self.log(f"Creating prompt: {name}")
        
        try:
            # Construct arguments_schema from arguments list
            arguments_schema = {
                'arguments': args_list
            }
            
            # Upsert into PromptRegistry
            statement = select(PromptRegistry).where(
                PromptRegistry.name == name,
                PromptRegistry.target_persona == persona
            )
            existing_prompt = self.db_session.exec(statement).first()
            
            if existing_prompt:
                # Update existing prompt
                existing_prompt.description = description
                existing_prompt.template = template
                existing_prompt.arguments_schema = arguments_schema
                self.db_session.add(existing_prompt)
                self.log(f"Prompt '{name}' updated in PromptRegistry")
            else:
                # Create new prompt
                prompt = PromptRegistry(
                    name=name,
                    target_persona=persona,
                    description=description,
                    template=template,
                    arguments_schema=arguments_schema
                )
                self.db_session.add(prompt)
                self.log(f"Prompt '{name}' created in PromptRegistry")
            
            # Commit changes
            self.db_session.commit()
            
            arg_names = [arg.get('name') for arg in args_list]
            return f"Success: Prompt '{name}' has been registered for persona '{persona}'. The prompt accepts arguments: {arg_names}"
            
        except Exception as e:
            self.db_session.rollback()
            return f"Error: Failed to register prompt - {type(e).__name__}: {str(e)}"
"""
    
    tool_hash = _compute_hash(tool_code)
    
    try:
        with Session(engine) as session:
            # Upsert code into CodeVault
            statement = select(CodeVault).where(CodeVault.hash == tool_hash)
            existing_code = session.exec(statement).first()
            
            if existing_code:
                print(f"   ℹ️  Code already exists (hash: {tool_hash[:16]}...)")
            else:
                code_vault = CodeVault(
                    hash=tool_hash,
                    code_blob=tool_code,
                    code_type="python"
                )
                session.add(code_vault)
                print(f"   ✅ Code registered (hash: {tool_hash[:16]}...)")
            
            # Upsert tool in ToolRegistry
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'create_new_prompt',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            # Define input schema for the meta-tool
            input_schema = {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The prompt name (e.g., 'review_code')"
                    },
                    "description": {
                        "type": "string",
                        "description": "What the prompt does"
                    },
                    "template": {
                        "type": "string",
                        "description": "The Jinja2/f-string template content"
                    },
                    "arguments": {
                        "type": "array",
                        "description": "List of argument definitions. Format: [{name: 'arg1', description: '...', required: true}]"
                    },
                    "persona": {
                        "type": "string",
                        "description": "Target persona (default: 'default')"
                    }
                },
                "required": ["name", "description", "template"]
            }
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = "Create or update a prompt in the PromptRegistry"
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Meta-tool 'create_new_prompt' updated")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name='create_new_prompt',
                    target_persona='default',
                    description="Create or update a prompt in the PromptRegistry",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash
                )
                session.add(tool)
                print(f"   ✅ Meta-tool 'create_new_prompt' created")
            
            # Commit changes
            session.commit()
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register prompt meta-tool: {e}")
        import traceback
        traceback.print_exc()
        return False


def register_resource_creator_tool(database_url: str = None):
    """
    Register the create_new_resource meta-tool in the database.
    
    This meta-tool enables the LLM to create or update static resources dynamically.
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
    """
    print("\n📦 Registering Resource Creator Meta-Tool...")
    
    # Load configuration if database_url not provided
    if database_url is None:
        config = load_config()
        database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    
    # Create engine and tables
    try:
        engine = get_engine(database_url)
        create_db_and_tables(engine)
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        return False
    
    # Define the meta-tool code blob
    tool_code = """from base import ChameleonTool
from sqlmodel import select
import hashlib
import json

class ResourceCreatorTool(ChameleonTool):
    def run(self, arguments):
        '''
        Create or update a STATIC resource in the ResourceRegistry.
        
        Args:
            uri: The resource URI (e.g., 'memo://project_notes')
            name: Human-readable name
            description: Description of content
            content: The static text content of the resource
            mime_type: MIME type (default: 'text/plain')
            persona: Target persona (default: 'default')
        
        Returns:
            Success message confirming the resource is registered
        '''
        from models import ResourceRegistry
        
        # Extract arguments
        uri = arguments.get('uri')
        name = arguments.get('name')
        description = arguments.get('description')
        content = arguments.get('content')
        mime_type = arguments.get('mime_type', 'text/plain')
        persona = arguments.get('persona', 'default')
        
        # Validation: Check all required arguments are provided
        if not uri:
            return "Error: uri is required"
        if not name:
            return "Error: name is required"
        if not description:
            return "Error: description is required"
        if not content:
            return "Error: content is required"
        
        self.log(f"Creating resource: {uri}")
        
        try:
            # Upsert into ResourceRegistry (static only)
            statement = select(ResourceRegistry).where(
                ResourceRegistry.uri_schema == uri,
                ResourceRegistry.target_persona == persona
            )
            existing_resource = self.db_session.exec(statement).first()
            
            if existing_resource:
                # Update existing resource
                existing_resource.name = name
                existing_resource.description = description
                existing_resource.mime_type = mime_type
                existing_resource.is_dynamic = False
                existing_resource.static_content = content
                existing_resource.active_hash_ref = None
                self.db_session.add(existing_resource)
                self.log(f"Resource '{uri}' updated in ResourceRegistry")
            else:
                # Create new resource
                resource = ResourceRegistry(
                    uri_schema=uri,
                    target_persona=persona,
                    name=name,
                    description=description,
                    mime_type=mime_type,
                    is_dynamic=False,
                    static_content=content,
                    active_hash_ref=None
                )
                self.db_session.add(resource)
                self.log(f"Resource '{uri}' created in ResourceRegistry")
            
            # Commit changes
            self.db_session.commit()
            
            return f"Success: Resource '{uri}' has been registered for persona '{persona}' as a static resource with MIME type '{mime_type}'."
            
        except Exception as e:
            self.db_session.rollback()
            return f"Error: Failed to register resource - {type(e).__name__}: {str(e)}"
"""
    
    tool_hash = _compute_hash(tool_code)
    
    try:
        with Session(engine) as session:
            # Upsert code into CodeVault
            statement = select(CodeVault).where(CodeVault.hash == tool_hash)
            existing_code = session.exec(statement).first()
            
            if existing_code:
                print(f"   ℹ️  Code already exists (hash: {tool_hash[:16]}...)")
            else:
                code_vault = CodeVault(
                    hash=tool_hash,
                    code_blob=tool_code,
                    code_type="python"
                )
                session.add(code_vault)
                print(f"   ✅ Code registered (hash: {tool_hash[:16]}...)")
            
            # Upsert tool in ToolRegistry
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'create_new_resource',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            # Define input schema for the meta-tool
            input_schema = {
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "The resource URI (e.g., 'memo://project_notes')"
                    },
                    "name": {
                        "type": "string",
                        "description": "Human-readable name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of content"
                    },
                    "content": {
                        "type": "string",
                        "description": "The static text content of the resource"
                    },
                    "mime_type": {
                        "type": "string",
                        "description": "MIME type (default: 'text/plain')"
                    },
                    "persona": {
                        "type": "string",
                        "description": "Target persona (default: 'default')"
                    }
                },
                "required": ["uri", "name", "description", "content"]
            }
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = "Create or update a STATIC resource in the ResourceRegistry"
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Meta-tool 'create_new_resource' updated")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name='create_new_resource',
                    target_persona='default',
                    description="Create or update a STATIC resource in the ResourceRegistry",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash
                )
                session.add(tool)
                print(f"   ✅ Meta-tool 'create_new_resource' created")
            
            # Commit changes
            session.commit()
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register resource meta-tool: {e}")
        import traceback
        traceback.print_exc()
        return False


def register_dynamic_meta_tools(database_url: str = None):
    """
    Register both prompt and resource meta-tools.
    
    Args:
        database_url: Optional database URL. If not provided, loads from config.
        
    Returns:
        True if both meta-tools registered successfully, False otherwise
    """
    print("=" * 60)
    print("Dynamic Meta-Tools Registration")
    print("=" * 60)
    
    # Load configuration if database_url not provided
    if database_url is None:
        config = load_config()
        database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    print(f"\nDatabase URL: {database_url}")
    
    # Register both tools
    prompt_success = register_prompt_creator_tool(database_url)
    resource_success = register_resource_creator_tool(database_url)
    
    if prompt_success and resource_success:
        print("\n" + "=" * 60)
        print("✅ Dynamic Meta-Tools registered successfully!")
        print("=" * 60)
        print("\nThe LLM can now create prompts and resources dynamically!")
        
        print("\n📝 Example usage for create_new_prompt:")
        print("  Tool: create_new_prompt")
        print("  Arguments: {")
        print('    "name": "review_code",')
        print('    "description": "Review code for quality and best practices",')
        print('    "template": "Please review this code: {code}",')
        print('    "arguments": [')
        print('      {"name": "code", "description": "The code to review", "required": true}')
        print('    ]')
        print("  }")
        
        print("\n📦 Example usage for create_new_resource:")
        print("  Tool: create_new_resource")
        print("  Arguments: {")
        print('    "uri": "memo://project_notes",')
        print('    "name": "Project Notes",')
        print('    "description": "Important notes about the project",')
        print('    "content": "Project started on 2024-01-01. Key goals: ..."')
        print("  }")
        
        print("\n🔒 Security Note:")
        print("  - Resources created by this tool are STATIC only (no code execution)")
        print("  - Dynamic resources require manual configuration for security")
        
        return True
    else:
        print("\n❌ Failed to register one or more meta-tools")
        return False


def main():
    """Main entry point."""
    success = register_dynamic_meta_tools()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
