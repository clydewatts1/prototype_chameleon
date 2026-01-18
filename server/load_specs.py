#!/usr/bin/env python3
"""
YAML-based data seeding system for Chameleon MCP Server.

This script loads tool, resource, and prompt definitions from a YAML file
and syncs them to the database with idempotent upsert operations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict

import yaml
from sqlmodel import Session, select
from sqlalchemy import text

from config import load_config
from models import (
    CodeVault,
    ToolRegistry,
    ResourceRegistry,
    PromptRegistry,
    get_engine,
    create_db_and_tables,
)


def _compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def _clear_database(session: Session) -> None:
    """
    Clear all existing data from the database.
    
    Args:
        session: SQLModel session
    """
    print("\nWARNING  Clearing existing data...")
    # Delete in order of dependencies
    session.exec(ToolRegistry.__table__.delete())
    session.exec(ResourceRegistry.__table__.delete())
    session.exec(PromptRegistry.__table__.delete())
    session.exec(CodeVault.__table__.delete())
    session.commit()
    print("OK Database cleared")


def _upsert_code_vault(session: Session, code: str, code_type: str = "python") -> str:
    """
    Upsert code into CodeVault and return its hash.
    
    Args:
        session: SQLModel session
        code: The code to store
        code_type: Type of code ('python' or 'select')
        
    Returns:
        SHA-256 hash of the code
    """
    code_hash = _compute_hash(code)
    
    # Check if code already exists
    statement = select(CodeVault).where(CodeVault.hash == code_hash)
    existing = session.exec(statement).first()
    
    if existing:
        # Update if code_type changed
        if existing.code_type != code_type:
            existing.code_type = code_type
            session.add(existing)
    else:
        # Create new entry
        code_vault = CodeVault(
            hash=code_hash,
            code_blob=code,
            code_type=code_type
        )
        session.add(code_vault)
    
    return code_hash


def _upsert_tool(session: Session, tool_data: Dict[str, Any]) -> None:
    """
    Upsert a tool definition into the database.
    
    Args:
        session: SQLModel session
        tool_data: Dictionary containing tool definition
    """
    tool_name = tool_data['name']
    group = tool_data.get('group')
    
    if not group:
         # Legacy support removed: group is required
         # But to prevent crashing if user has old yaml, maybe raise error or print warning?
         # User asked to "remove legacy functionality", so we should probably fail or default strictly?
         # Let's enforce it:
         print(f"ERROR Tool '{tool_name}' missing required 'group' field")
         return
    
    # Auto-prefix name with group if not already present
    if not tool_name.startswith(f"{group}_"):
        # Check if tool_name is exactly the group name (edge case)
        if tool_name == group:
             tool_name = f"{group}_{tool_name}"
        else:
             tool_name = f"{group}_{tool_name}"

    persona = tool_data.get('persona', 'default')
    
    # Hash and store code
    code = tool_data['code']
    code_type = tool_data.get('code_type', 'python')
    code_hash = _upsert_code_vault(session, code, code_type)
    
    # Check if tool already exists
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == tool_name,
        ToolRegistry.target_persona == persona
    )
    existing = session.exec(statement).first()
    
    if existing:
        # Update existing tool
        existing.description = tool_data['description']
        existing.input_schema = tool_data.get('input_schema', {})
        existing.active_hash_ref = code_hash
        existing.is_auto_created = False
        existing.group = group
        session.add(existing)
        print(f"   OK Tool '{tool_name}' updated (hash: {code_hash[:16]}...)")
    else:
        # Create new tool
        tool = ToolRegistry(
            tool_name=tool_name,
            target_persona=persona,
            description=tool_data['description'],
            input_schema=tool_data.get('input_schema', {}),
            active_hash_ref=code_hash,
            is_auto_created=False,
            group=group
        )
        session.add(tool)
        print(f"   OK Tool '{tool_name}' created (hash: {code_hash[:16]}...)")


def _upsert_resource(session: Session, resource_data: Dict[str, Any]) -> None:
    """
    Upsert a resource definition into the database.
    
    Args:
        session: SQLModel session
        resource_data: Dictionary containing resource definition
    """
    uri = resource_data['uri']
    name = resource_data['name']
    group = resource_data.get('group')

    if not group:
         print(f"ERROR Resource '{name}' missing required 'group' field")
         return
    
    # Auto-prefix name with group if not already present
    if not name.startswith(f"{group}_"):
        name = f"{group}_{name}"

    is_dynamic = resource_data.get('is_dynamic', False)
    
    # If dynamic, hash and store code
    code_hash = None
    if is_dynamic:
        code = resource_data.get('code', '')
        code_type = resource_data.get('code_type', 'python')
        code_hash = _upsert_code_vault(session, code, code_type)
    
    # Check if resource already exists
    statement = select(ResourceRegistry).where(ResourceRegistry.uri_schema == uri)
    existing = session.exec(statement).first()
    
    if existing:
        # Update existing resource
        existing.name = name
        existing.description = resource_data['description']
        existing.mime_type = resource_data.get('mime_type', 'text/plain')
        existing.is_dynamic = is_dynamic
        existing.static_content = resource_data.get('static_content')
        existing.active_hash_ref = code_hash
        existing.target_persona = resource_data.get('persona', 'default')
        existing.group = group
        session.add(existing)
        print(f"   OK Resource '{name}' updated (URI: {uri})")
    else:
        # Create new resource
        resource = ResourceRegistry(
            uri_schema=uri,
            name=name,
            description=resource_data['description'],
            mime_type=resource_data.get('mime_type', 'text/plain'),
            is_dynamic=is_dynamic,
            static_content=resource_data.get('static_content'),
            active_hash_ref=code_hash,
            target_persona=resource_data.get('persona', 'default'),
            group=group
        )
        session.add(resource)
        print(f"   OK Resource '{name}' created (URI: {uri})")


def _upsert_prompt(session: Session, prompt_data: Dict[str, Any]) -> None:
    """
    Upsert a prompt definition into the database.
    
    Args:
        session: SQLModel session
        prompt_data: Dictionary containing prompt definition
    """
    name = prompt_data['name']
    name = prompt_data['name']
    group = prompt_data.get('group')
    
    if not group:
         print(f"ERROR Prompt '{name}' missing required 'group' field")
         return
    
    # Auto-prefix name with group if not already present
    if not name.startswith(f"{group}_"):
        name = f"{group}_{name}"

    # Check if prompt already exists
    statement = select(PromptRegistry).where(PromptRegistry.name == name)
    existing = session.exec(statement).first()
    
    if existing:
        # Update existing prompt
        existing.description = prompt_data['description']
        existing.template = prompt_data['template']
        existing.arguments_schema = prompt_data.get('arguments_schema', {})
        existing.target_persona = prompt_data.get('persona', 'default')
        existing.group = group
        session.add(existing)
        print(f"   OK Prompt '{name}' updated")
    else:
        # Create new prompt
        prompt = PromptRegistry(
            name=name,
            description=prompt_data['description'],
            template=prompt_data['template'],
            arguments_schema=prompt_data.get('arguments_schema', {}),
            target_persona=prompt_data.get('persona', 'default'),
            group=group
        )
        session.add(prompt)
        print(f"   OK Prompt '{name}' created")


def load_specs_from_yaml(yaml_path: str, database_url: str, clean: bool = False) -> bool:
    """
    Load specifications from YAML file and sync to database.
    
    Args:
        yaml_path: Path to the YAML specifications file
        database_url: Database connection string
        clean: If True, clear existing data before loading
        
    Returns:
        True if successful, False otherwise
    """
    print("=" * 60)
    print("Loading Chameleon Specifications from YAML")
    print("=" * 60)
    print(f"YAML file: {yaml_path}")
    print(f"Database: {database_url}")
    
    # Check if YAML file exists
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        print(f"\nERROR Error: YAML file not found: {yaml_path}")
        return False
    
    # Load YAML file
    print(f"\n> Reading YAML file...")
    try:
        with open(yaml_file, 'r') as f:
            specs = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"\nERROR Error parsing YAML file: {e}")
        return False
    
    print(f"OK YAML loaded successfully")
    
    # Create engine and tables
    engine = get_engine(database_url)
    create_db_and_tables(engine)

    # Ensure schema is up-to-date for ToolRegistry
    try:
        with Session(engine) as session:
            # Check if 'is_auto_created' exists in toolregistry
            cols = session.exec(text("PRAGMA table_info(toolregistry)")).all()
            col_names = {row[1] for row in cols} if cols else set()
            if 'is_auto_created' not in col_names:
                print("\n*  Reconciling schema: adding column 'is_auto_created' to toolregistry...")
                session.exec(text("ALTER TABLE toolregistry ADD COLUMN is_auto_created BOOLEAN NOT NULL DEFAULT 0"))
                session.commit()
                print("OK Column 'is_auto_created' added")
    except Exception as e:

        # Non-fatal: continue; detailed error shown for awareness
        print(f"\nWARNING  Schema reconciliation skipped: {e}")
    
    # Ensure schema is up-to-date for group field
    try:
        with Session(engine) as session:
            # Check if 'group' exists in toolregistry
            cols = session.exec(text("PRAGMA table_info(toolregistry)")).all()
            col_names = {row[1] for row in cols} if cols else set()
            if 'group' not in col_names:
                print("\n⚙️  Reconciling schema: adding column 'group' to toolregistry...")
                session.exec(text("ALTER TABLE toolregistry ADD COLUMN 'group' VARCHAR DEFAULT 'general'"))
                session.commit()
                print("✅ Column 'group' added to toolregistry")

            # Check if 'group' exists in resourceregistry
            cols = session.exec(text("PRAGMA table_info(resourceregistry)")).all()
            col_names = {row[1] for row in cols} if cols else set()
            if 'group' not in col_names:
                print("\n⚙️  Reconciling schema: adding column 'group' to resourceregistry...")
                session.exec(text("ALTER TABLE resourceregistry ADD COLUMN 'group' VARCHAR DEFAULT 'general'"))
                session.commit()
                print("✅ Column 'group' added to resourceregistry")

            # Check if 'group' exists in promptregistry
            cols = session.exec(text("PRAGMA table_info(promptregistry)")).all()
            col_names = {row[1] for row in cols} if cols else set()
            if 'group' not in col_names:
                print("\n⚙️  Reconciling schema: adding column 'group' to promptregistry...")
                session.exec(text("ALTER TABLE promptregistry ADD COLUMN 'group' VARCHAR DEFAULT 'general'"))
                session.commit()
                print("✅ Column 'group' added to promptregistry")
    except Exception as e:
            print(f"\nWARNING  Schema reconciliation for 'group' column skipped: {e}")
    
    try:
        with Session(engine) as session:
            # Clear database if requested
            if clean:
                _clear_database(session)
            
            # Load tools
            tools = specs.get('tools', [])
            if tools:
                print(f"\n* Loading {len(tools)} tool(s)...")
                for tool_data in tools:
                    _upsert_tool(session, tool_data)
            
            # Load resources
            resources = specs.get('resources', [])
            if resources:
                print(f"\n* Loading {len(resources)} resource(s)...")
                for resource_data in resources:
                    _upsert_resource(session, resource_data)
            
            # Load prompts
            prompts = specs.get('prompts', [])
            if prompts:
                print(f"\n* Loading {len(prompts)} prompt(s)...")
                for prompt_data in prompts:
                    _upsert_prompt(session, prompt_data)
            
            # Commit all changes
            session.commit()
            
            print("\n" + "=" * 60)
            print("OK Specifications loaded successfully!")
            print("=" * 60)
            
            # Print summary
            print(f"\nSummary:")
            print(f"  - Tools: {len(tools)}")
            print(f"  - Resources: {len(resources)}")
            print(f"  - Prompts: {len(prompts)}")
            
            return True
            
    except Exception as e:
        print(f"\nERROR Error loading specifications: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point for the load_specs script."""
    parser = argparse.ArgumentParser(
        description='Load Chameleon MCP Server specifications from YAML file'
    )
    parser.add_argument(
        'yaml_file',
        nargs='?',
        default='specs.yaml',
        help='Path to YAML specifications file (default: specs.yaml)'
    )
    parser.add_argument(
        '--database',
        '-d',
        default=None,
        help='Database URL (overrides config.yaml)'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clear existing data before loading'
    )
    
    args = parser.parse_args()
    
    # Get database URL from config or command line
    if args.database:
        database_url = args.database
    else:
        config = load_config()
        database_url = config.get('metadata_database', {}).get('url', 'sqlite:///data/chameleon_meta.db')
    
    # Load specifications
    success = load_specs_from_yaml(args.yaml_file, database_url, args.clean)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
