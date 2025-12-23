"""
Script to add the ChainTool (Workflow Engine) to the database.

This tool enables chaining multiple tool calls together with:
- DAG validation to prevent circular dependencies
- Variable substitution between steps
- Rich error feedback with partial execution details
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.hash_utils import compute_hash
from sqlmodel import Session, select
from models import CodeVault, ToolRegistry, get_engine
from config import load_config


def register_chain_tool(session: Session, config: dict = None) -> None:
    """
    Register the ChainTool in the database.
    
    Args:
        session: SQLModel Session for database access
        config: Optional configuration dictionary (for future use)
    """
    # Load the tool code from file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tool_code_path = os.path.join(script_dir, '..', 'tools', 'system', 'chain_tool.py')
    
    with open(tool_code_path, 'r') as f:
        chain_tool_code = f.read()
    
    chain_tool_hash = compute_hash(chain_tool_code)
    
    print("\n[1] Adding ChainTool code to CodeVault...")
    
    # Check if code already exists
    existing_code = session.exec(
        select(CodeVault).where(CodeVault.hash == chain_tool_hash)
    ).first()
    
    if not existing_code:
        code_vault = CodeVault(
            hash=chain_tool_hash,
            code_blob=chain_tool_code,
            code_type="python"
        )
        session.add(code_vault)
        print(f"   ✅ Code added (hash: {chain_tool_hash[:16]}...)")
    else:
        print(f"   ℹ️  Code already exists (hash: {chain_tool_hash[:16]}...)")
    
    print("\n[2] Registering system_run_chain tool for 'default' persona...")
    
    # Check if tool already exists
    existing_tool = session.exec(
        select(ToolRegistry).where(
            ToolRegistry.tool_name == "system_run_chain",
            ToolRegistry.target_persona == "default"
        )
    ).first()
    
    tool_description = (
        "Execute a chain of tool calls in sequence with variable substitution. "
        "Supports ${step_id.key} syntax to pass results between steps. "
        "Validates DAG structure to prevent circular dependencies. "
        "Returns detailed error reports showing partial execution on failure."
    )
    
    input_schema = {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "description": "List of steps to execute in sequence",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for this step (used for variable references)"
                        },
                        "tool": {
                            "type": "string",
                            "description": "Name of the tool to execute"
                        },
                        "args": {
                            "type": "object",
                            "description": "Arguments to pass to the tool. Supports ${step_id.key} variable substitution."
                        }
                    },
                    "required": ["id", "tool", "args"]
                }
            }
        },
        "required": ["steps"]
    }
    
    if not existing_tool:
        tool_registry = ToolRegistry(
            tool_name="system_run_chain",
            target_persona="default",
            description=tool_description,
            input_schema=input_schema,
            active_hash_ref=chain_tool_hash,
            group="system",
            is_auto_created=False
        )
        session.add(tool_registry)
        print(f"   ✅ Tool 'system_run_chain' registered")
    else:
        # Update existing tool
        existing_tool.active_hash_ref = chain_tool_hash
        existing_tool.description = tool_description
        existing_tool.input_schema = input_schema
        existing_tool.group = "system"
        print(f"   ℹ️  Tool 'system_run_chain' already exists, updated")
    
    session.commit()


def add_chain_tool(database_url: str = None):
    """
    Add the ChainTool to the database.
    
    Args:
        database_url: Database connection string. If None, loads from config.
    """
    # Load configuration if database_url not provided
    if database_url is None:
        config = load_config()
        database_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon.db')
    
    engine = get_engine(database_url)
    
    print("=" * 70)
    print("Adding ChainTool (Workflow Engine)")
    print("=" * 70)
    
    with Session(engine) as session:
        register_chain_tool(session)
    
    print("\n" + "=" * 70)
    print("✅ ChainTool added successfully!")
    print("=" * 70)
    print("\nUsage Example 1 (Simple Variable Substitution):")
    print("  system_run_chain({")
    print("    'steps': [")
    print("      {")
    print("        'id': 'date',")
    print("        'tool': 'get_date',")
    print("        'args': {}")
    print("      },")
    print("      {")
    print("        'id': 'greeting',")
    print("        'tool': 'greet',")
    print("        'args': {'name': 'User on ${date}'}") 
    print("      }")
    print("    ]")
    print("  })")
    print("\nUsage Example 2 (Dict Field Access):")
    print("  system_run_chain({")
    print("    'steps': [")
    print("      {")
    print("        'id': 'location',")
    print("        'tool': 'get_location',")
    print("        'args': {}")
    print("      },")
    print("      {")
    print("        'id': 'city_greeting',")
    print("        'tool': 'greet',")
    print("        'args': {'name': '${location.city}'}  # Access nested field")
    print("      }")
    print("    ]")
    print("  })")
    print("\nFeatures:")
    print("  ✅ DAG Validation - Prevents circular dependencies")
    print("  ✅ Variable Substitution - ${step_id} or ${step_id.key} syntax")
    print("  ✅ Error Monitoring - Detailed reports with partial execution info")


if __name__ == "__main__":
    add_chain_tool()
