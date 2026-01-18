#!/usr/bin/env python3
"""
Bootstrap script for registering the Librarian Tool (system_update_manual).

This tool allows the LLM to update the documentation (manual) for other tools.
It implements the "Librarian Protocol" for self-documentation.
"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.hash_utils import compute_hash
from sqlmodel import Session, select
from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables

# The code that runs when the tool is executed by the LLM
LIBRARIAN_CODE = """
from base import ChameleonTool
import json

class LibrarianTool(ChameleonTool):
    def run(self, arguments):
        target_tool = arguments.get('tool_name')
        new_content = arguments.get('manual_content')
        mode = arguments.get('mode', 'merge')
        
        if not hasattr(self, 'db_session'): return "Error: No DB session."
        session = self.db_session
        from models import ToolRegistry
        
        # REC A: VALIDATION
        # Prevent LLM from inventing random keys
        ALLOWED_KEYS = {"usage_guide", "examples", "pitfalls", "error_codes"}
        if not set(new_content.keys()).issubset(ALLOWED_KEYS):
            return f"Error: Invalid keys in manual_content. Allowed keys are: {list(ALLOWED_KEYS)}"

        # RISK 2: VERIFICATION FLAG
        # Automatically mark new examples as unverified
        if "examples" in new_content:
            for ex in new_content["examples"]:
                ex["verified"] = False  # Admin must review this later
                ex["source"] = "AI_Generated"

        # [Fetch Tool Logic]
        # We need to fetch the tool to identify it. But since we need modifying it,
        # we need to ensure we are modifying the ToolRegistry entry.
        # Note: The tool assumes it's updating metadata for a tool that exists in ToolRegistry.
        
        tool = session.get(ToolRegistry, (target_tool, 'default'))
        if not tool: return f"Tool '{target_tool}' not found."
        
        current_manual = tool.extended_metadata or {}
        
        # [Merge Logic]
        final_manual = current_manual.copy()
        
        if mode == 'overwrite':
             final_manual = new_content
        else:
            # Merge mode
            for key, value in new_content.items():
                if key == "examples":
                    # Append examples if they exist
                    # Ensure value is a list
                    if not isinstance(value, list):
                        return "Error: 'examples' must be a list."
                    
                    current_examples = final_manual.get("examples", [])
                    if not isinstance(current_examples, list):
                         current_examples = []
                    
                    final_manual["examples"] = current_examples + value
                else:
                    # Overwrite other sections
                    final_manual[key] = value

        tool.extended_metadata = final_manual
        session.add(tool)
        session.commit()
        
        return f"Manual for '{target_tool}' updated. Examples marked as unverified."
"""

def register_librarian_tool(database_url: str = None):
    print("=" * 60)
    print("Librarian Tool (system_update_manual) Registration")
    print("=" * 60)
    
    if database_url is None:
        config = load_config()
        database_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon.db')
    print(f"\\nDatabase URL: {database_url}")
    
    try:
        engine = get_engine(database_url)
        create_db_and_tables(engine)
    except Exception as e:
        print(f"❌ Failed to connect/create DB: {e}")
        return False
        
    tool_hash = compute_hash(LIBRARIAN_CODE)
    
    try:
        with Session(engine) as session:
            # Upsert Code
            print("\\n📝 Registering tool code in CodeVault...")
            statement = select(CodeVault).where(CodeVault.hash == tool_hash)
            existing_code = session.exec(statement).first()
            
            if existing_code:
                print(f"   ℹ️  Code already exists (hash: {tool_hash[:16]}...)")
            else:
                code_vault = CodeVault(
                    hash=tool_hash,
                    code_blob=LIBRARIAN_CODE,
                    code_type="python"
                )
                session.add(code_vault)
                print(f"   ✅ Code registered (hash: {tool_hash[:16]}...)")
            
            # Upsert Tool
            print("\\n🔧 Registering tool in ToolRegistry...")
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'system_update_manual',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            input_schema = {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "The name of the tool to update documentation for"
                    },
                    "manual_content": {
                        "type": "object",
                        "description": "Dictionary containing documentation sections (usage_guide, examples, pitfalls, error_codes)"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["merge", "overwrite"],
                        "default": "merge",
                        "description": "Whether to merge with existing manual or overwrite it"
                    }
                },
                "required": ["tool_name", "manual_content"]
            }
            
            if existing_tool:
                existing_tool.description = "Update the external documentation (manual) for a tool. Use this to save successful usage patterns."
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Tool 'system_update_manual' updated")
            else:
                tool = ToolRegistry(
                    tool_name='system_update_manual',
                    target_persona='default',
                    description="Update the external documentation (manual) for a tool. Use this to save successful usage patterns.",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash,
                    group='system'
                )
                session.add(tool)
                print(f"   ✅ Tool 'system_update_manual' created")
            
            session.commit()
            print("\\n✅ Librarian Tool registered successfully!")
            return True
            
    except Exception as e:
        print(f"\\n❌ Failed to register tool: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    register_librarian_tool()
