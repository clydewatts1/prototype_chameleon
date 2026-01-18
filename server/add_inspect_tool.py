#!/usr/bin/env python3
"""
Bootstrap script for registering the System Inspect Tool (system_inspect_tool).

This tool allows the LLM to inspect the manual and metadata of other tools.
It is a critical component of the Antigravity Safety System (Confidence Check).
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
INSPECT_CODE = """
from base import ChameleonTool
import json

class InspectTool(ChameleonTool):
    def run(self, arguments):
        tool_name = arguments.get('tool_name')
        
        if not hasattr(self, 'db_session'): return "Error: No DB session."
        session = self.db_session
        from models import ToolRegistry
        
        # Look up tool
        # Try default persona first
        tool = session.get(ToolRegistry, (tool_name, 'default'))
        
        # If not found, try to find any tool with this name
        if not tool:
             stmt = select(ToolRegistry).where(ToolRegistry.tool_name == tool_name)
             tool = session.exec(stmt).first()
             
        if not tool: 
            return f"Tool '{tool_name}' not found in registry."
        
        # Construct detailed inspection report
        manual = tool.extended_metadata or {}
        
        report = {
            "tool_name": tool.tool_name,
            "description": tool.description,
            "target_persona": tool.target_persona,
            "group": tool.group,
            "input_schema": tool.input_schema,
            "is_auto_created": tool.is_auto_created,
            "manual": manual
        }
        
        return json.dumps(report, indent=2, default=str)
"""

def register_inspect_tool(database_url: str = None):
    print("=" * 60)
    print("System Inspect Tool Registration")
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
        
    tool_hash = compute_hash(INSPECT_CODE)
    
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
                    code_blob=INSPECT_CODE,
                    code_type="python"
                )
                session.add(code_vault)
                print(f"   ✅ Code registered (hash: {tool_hash[:16]}...)")
            
            # Upsert Tool
            print("\\n🔧 Registering tool in ToolRegistry...")
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'system_inspect_tool',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            input_schema = {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "The name of the tool to inspect"
                    }
                },
                "required": ["tool_name"]
            }
            
            if existing_tool:
                existing_tool.description = "Inspect a tool's documentation (manual), schema, and metadata. Critical for verifying how to use complex tools."
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Tool 'system_inspect_tool' updated")
            else:
                tool = ToolRegistry(
                    tool_name='system_inspect_tool',
                    target_persona='default',
                    description="Inspect a tool's documentation (manual), schema, and metadata. Critical for verifying how to use complex tools.",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash,
                    group='system'
                )
                session.add(tool)
                print(f"   ✅ Tool 'system_inspect_tool' created")
            
            session.commit()
            print("\\n✅ System Inspect Tool registered successfully!")
            return True
            
    except Exception as e:
        print(f"\\n❌ Failed to register tool: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    register_inspect_tool()
