#!/usr/bin/env python3
"""
Bootstrap script for registering the Verifier Tool (system_verify_tool).

This tool runs the examples found in a tool's manual (extended_metadata) to verify functionality.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.hash_utils import compute_hash
from sqlmodel import Session, select
from config import load_config
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables

VERIFIER_CODE = """
from base import ChameleonTool
from sqlmodel import select
import json
import traceback

class VerifierTool(ChameleonTool):
    def run(self, arguments):
        target_tool_name = arguments.get('tool_name')
        
        # 1. Setup Session
        if not hasattr(self, 'db_session'): return "Error: No DB session."
        meta_session = self.db_session
        data_session = self.data_session
        
        # Imports needed for reflection
        from models import ToolRegistry, CodeVault
        
        # 2. Fetch Target Tool
        # Using select since PK might not be simple
        statement = select(ToolRegistry).where(
            ToolRegistry.tool_name == target_tool_name,
            ToolRegistry.target_persona == 'default' # Assumption: verifying default persona tools
        )
        if not tool_def: return f"Error: Tool '{target_tool_name}' not found for default persona."
        
        # 3. Load Target Code (Dynamic Loading)
        # Fetching code by hash ref
        code_statement = select(CodeVault).where(CodeVault.hash == tool_def.active_hash_ref)
        code_record = meta_session.exec(code_statement).first()
        
        if not code_record: return "Error: Source code not found."
        
        try:
            # We recreate the tool class dynamically to test it
            local_scope = {'ChameleonTool': ChameleonTool} 
            
            # Use single namespace for both globals and locals to ensure imports work correctly
            exec(code_record.code_blob, local_scope)
            
            # Heuristic: Find the class that inherits from ChameleonTool
            ToolClass = None
            for name, obj in local_scope.items():
                # Check if it's a class, inherits from ChameleonTool, and is NOT ChameleonTool itself
                if isinstance(obj, type) and issubclass(obj, ChameleonTool) and obj is not ChameleonTool:
                    ToolClass = obj
                    break
            
            if not ToolClass: return "Error: Could not find Tool class in source."
            
            # Instantiate with both sessions
            context = {"tool_name": target_tool_name, "user_id": "verifier"}
            target_instance = ToolClass(meta_session, context, data_session)
            
        except Exception as e:
            return f"Error loading tool code: {str(e)}\\n{traceback.format_exc()}"

        # 4. Run Tests (from Manual)
        manual = tool_def.extended_metadata or {}
        # Handle case where extended_metadata is None or empty
        if not manual:
             return f"No manual (extended_metadata) found for '{target_tool_name}'. Nothing to verify."

        examples = manual.get("examples", [])
        
        if not examples:
            return f"No examples found in manual for '{target_tool_name}'. Nothing to verify."

        report = []
        all_passed = True
        
        for idx, ex in enumerate(examples):
            input_args = ex.get("input", {})
            try:
                self.log(f"Verifying {target_tool_name} test {idx+1} with args: {input_args}")
                # RUN THE TEST
                result = target_instance.run(input_args)
                
                # Check Expected Output (if defined)
                # For now, we mainly check it runs without crashing.
                
                report.append(f"Test {idx+1}: PASSED")
                ex['verified'] = True # Mark as verified
                
            except Exception as e:
                report.append(f"Test {idx+1}: FAILED. Error: {str(e)}")
                ex['verified'] = False
                all_passed = False

        # 5. Save Verification Status
        # Update the manual with verified flags
        # We need to explicitly assign it back to trigger SQLModel/SQLAlchemy update for JSON fields
        tool_def.extended_metadata = manual
        meta_session.add(tool_def)
        meta_session.commit()
        
        status = "SUCCESS" if all_passed else "FAILED"
        return f"Verification {status} for '{target_tool_name}':\\n" + "\\n".join(report)
"""

def register_verifier_tool(database_url: str = None):
    print("=" * 60)
    print("Verifier Tool Registration")
    print("=" * 60)
    
    # Load configuration if database_url not provided
    if database_url is None:
        config = load_config()
        database_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon.db')
    print(f"\nDatabase URL: {database_url}")
    
    # Create engine
    try:
        engine = get_engine(database_url)
        create_db_and_tables(engine)
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        return False

    tool_code = VERIFIER_CODE
    tool_hash = compute_hash(tool_code)
    
    try:
        with Session(engine) as session:
            # Upsert code
            print("\n📝 Registering tool code in CodeVault...")
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
            
            # Upsert tool
            print("\n🔧 Registering tool in ToolRegistry...")
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'system_verify_tool',
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = session.exec(statement).first()
            
            input_schema = {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "The tool to test"
                    }
                },
                "required": ["tool_name"]
            }
            
            if existing_tool:
                existing_tool.description = "Runs the examples in a tool's manual to ensure the tool actually works."
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = tool_hash
                session.add(existing_tool)
                print(f"   ✅ Tool 'system_verify_tool' updated")
            else:
                tool = ToolRegistry(
                    tool_name='system_verify_tool',
                    target_persona='default',
                    description="Runs the examples in a tool's manual to ensure the tool actually works.",
                    input_schema=input_schema,
                    active_hash_ref=tool_hash,
                    group='system', # Important: strict namespacing
                    extended_metadata={
                        "usage_guide": "Run this after creating or updating a tool to verify it works.",
                        "examples": [{"input": {"tool_name": "utility_greet"}}]
                    }
                )
                session.add(tool)
                print(f"   ✅ Tool 'system_verify_tool' created")
            
            session.commit()
            
            print("\n" + "=" * 60)
            print("✅ Verifier Tool registered successfully!")
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to register tool: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = register_verifier_tool()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
