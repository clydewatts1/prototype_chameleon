#!/usr/bin/env python3
"""
Database Export Utility for Chameleon MCP Server.

This script exports the current state of the database (Tools, Resources, Prompts,
and their associated Code) into a clean, readable YAML file that matches the format
expected by load_specs.py.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


import argparse
import sys
from typing import Dict, Any, List, Optional

import yaml
from sqlmodel import Session, select

from config import load_config
from models import (
    CodeVault,
    ToolRegistry,
    ResourceRegistry,
    PromptRegistry,
    get_engine,
)


class LiteralString(str):
    """String subclass to force literal block scalar style in YAML."""
    pass


def _export_tools(session: Session, persona: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Export all tools from ToolRegistry.
    
    Args:
        session: SQLModel session
        persona: Optional persona filter
        
    Returns:
        List of tool dictionaries
    """
    # Build query
    statement = select(ToolRegistry)
    if persona:
        statement = statement.where(ToolRegistry.target_persona == persona)
    
    tools = session.exec(statement).all()
    
    exported_tools = []
    for tool in tools:
        # Fetch code from CodeVault
        code_statement = select(CodeVault).where(CodeVault.hash == tool.active_hash_ref)
        code_vault = session.exec(code_statement).first()
        
        if not code_vault:
            print(f"⚠️  Warning: Code not found for tool '{tool.tool_name}' (hash: {tool.active_hash_ref})", file=sys.stderr)
            continue
        
        tool_dict = {
            'name': tool.tool_name,
            'persona': tool.target_persona,
            'description': tool.description,
            'code_type': code_vault.code_type,
            'code': LiteralString(code_vault.code_blob),
            'input_schema': tool.input_schema,
        }
        
        exported_tools.append(tool_dict)
    
    return exported_tools


def _export_resources(session: Session, persona: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Export all resources from ResourceRegistry.
    
    Args:
        session: SQLModel session
        persona: Optional persona filter
        
    Returns:
        List of resource dictionaries
    """
    # Build query
    statement = select(ResourceRegistry)
    if persona:
        statement = statement.where(ResourceRegistry.target_persona == persona)
    
    resources = session.exec(statement).all()
    
    exported_resources = []
    for resource in resources:
        resource_dict = {
            'uri': resource.uri_schema,
            'name': resource.name,
            'persona': resource.target_persona,
            'description': resource.description,
            'mime_type': resource.mime_type,
            'is_dynamic': resource.is_dynamic,
        }
        
        if resource.is_dynamic:
            # Fetch code from CodeVault
            if resource.active_hash_ref:
                code_statement = select(CodeVault).where(CodeVault.hash == resource.active_hash_ref)
                code_vault = session.exec(code_statement).first()
                
                if code_vault:
                    resource_dict['code_type'] = code_vault.code_type
                    resource_dict['code'] = LiteralString(code_vault.code_blob)
                else:
                    print(f"⚠️  Warning: Code not found for dynamic resource '{resource.name}' (hash: {resource.active_hash_ref})", file=sys.stderr)
        else:
            # Static resource
            if resource.static_content:
                resource_dict['static_content'] = LiteralString(resource.static_content)
        
        exported_resources.append(resource_dict)
    
    return exported_resources


def _export_prompts(session: Session, persona: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Export all prompts from PromptRegistry.
    
    Args:
        session: SQLModel session
        persona: Optional persona filter
        
    Returns:
        List of prompt dictionaries
    """
    # Build query
    statement = select(PromptRegistry)
    if persona:
        statement = statement.where(PromptRegistry.target_persona == persona)
    
    prompts = session.exec(statement).all()
    
    exported_prompts = []
    for prompt in prompts:
        prompt_dict = {
            'name': prompt.name,
            'persona': prompt.target_persona,
            'description': prompt.description,
            'template': LiteralString(prompt.template),
            'arguments_schema': prompt.arguments_schema,
        }
        
        exported_prompts.append(prompt_dict)
    
    return exported_prompts


def export_specs(database_url: str, persona: Optional[str] = None) -> Dict[str, Any]:
    """
    Export all specifications from the database.
    
    Args:
        database_url: Database connection string
        persona: Optional persona filter
        
    Returns:
        Dictionary containing tools, resources, and prompts
    """
    engine = get_engine(database_url)
    
    with Session(engine) as session:
        tools = _export_tools(session, persona)
        resources = _export_resources(session, persona)
        prompts = _export_prompts(session, persona)
    
    specs = {}
    if tools:
        specs['tools'] = tools
    if resources:
        specs['resources'] = resources
    if prompts:
        specs['prompts'] = prompts
    
    return specs


def main():
    """Main entry point for the export_specs script."""
    parser = argparse.ArgumentParser(
        description='Export Chameleon MCP Server specifications to YAML format'
    )
    parser.add_argument(
        '--database',
        '-d',
        default=None,
        help='Database URL (overrides config.yaml)'
    )
    parser.add_argument(
        '--persona',
        '-p',
        default=None,
        help='Filter by persona (e.g., "assistant", "default")'
    )
    
    args = parser.parse_args()
    
    # Get database URL from config or command line
    if args.database:
        database_url = args.database
    else:
        config = load_config()
        database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    
    # Export specifications
    try:
        specs = export_specs(database_url, args.persona)
        
        # Create a custom dumper that uses literal block style for strings with newlines
        class LiteralDumper(yaml.Dumper):
            pass
        
        def literal_presenter(dumper, data):
            """
            Custom YAML presenter for literal block scalars.
            
            Uses block style (|) for multiline strings to keep them readable.
            Note: PyYAML preserves trailing whitespace by using quoted strings
            instead of block scalars when necessary.
            """
            if isinstance(data, LiteralString) and '\n' in data:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            elif isinstance(data, str) and '\n' in data:
                # Also handle regular str in case of type conversion
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data)
        
        # Register representer for both str and LiteralString
        LiteralDumper.add_representer(str, literal_presenter)
        LiteralDumper.add_representer(LiteralString, literal_presenter)
        
        # Print YAML to stdout with custom dumper
        # Use reasonable width limit (200 chars) to prevent excessively long lines
        yaml.dump(specs, sys.stdout, Dumper=LiteralDumper, default_flow_style=False, 
                  sort_keys=False, allow_unicode=True, width=200)
        
    except Exception as e:
        print(f"❌ Error exporting specifications: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
