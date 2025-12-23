
import sys
import os
import shutil

# Add server directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from sqlmodel import Session, select, create_engine
from models import ToolRegistry, ResourceRegistry, PromptRegistry, create_db_and_tables
from load_specs import load_specs_from_yaml
from runtime import list_tools_for_persona, list_resources_for_persona

def test_group_feature():
    print("Starting Group Feature Verification...")
    
    # Use a test database
    db_path = "test_group_feature.db"
    db_url = f"sqlite:///{db_path}"
    
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # 1. Load Specs
    print("\n1. Loading specs into test database...")
    # Assume we are running from project root or tests dir, finding specs.yaml relative to server
    specs_path = os.path.join(os.path.dirname(__file__), "..", "server", "specs.yaml")
    
    success = load_specs_from_yaml(specs_path, db_url, clean=True)
    if not success:
        print("ERROR Failed to load specs.")
        return False
        
    engine = create_engine(db_url)
    
    with Session(engine) as session:
        # 2. Verify Database Content
        print("\n2. Verifying database content...")
        
        # Tools
        # Note: We now look for prefixed names
        greet_tool = session.exec(select(ToolRegistry).where(ToolRegistry.tool_name == "utility_greet")).first()
        add_tool = session.exec(select(ToolRegistry).where(ToolRegistry.tool_name == "math_add")).first()
        db_tool = session.exec(select(ToolRegistry).where(ToolRegistry.tool_name == "database_list_all_tools")).first()
        
        if not greet_tool or not add_tool or not db_tool:
             print("ERROR One or more tools not found with expected prefixed names")
             # Try to find what IS there for debugging
             all_tools = session.exec(select(ToolRegistry)).all()
             print(f"DEBUG: Found tools: {[t.tool_name for t in all_tools]}")
             return False
        
        if greet_tool.group != "utility":
            print(f"ERROR 'greet' tool has wrong group: {greet_tool.group}")
            return False
        if greet_tool.tool_name != "utility_greet":
             print(f"ERROR 'greet' tool has wrong name: {greet_tool.tool_name} (expected utility_greet)")
             return False

        if add_tool.group != "math":
            print(f"ERROR 'add' tool has wrong group: {add_tool.group} (expected math)")
            return False
        if add_tool.tool_name != "math_add":
             print(f"ERROR 'add' tool has wrong name: {add_tool.tool_name} (expected math_add)")
             return False

        if db_tool.group != "database":
             print(f"ERROR 'list_all_tools' tool has wrong group: {db_tool.group}")
             return False
        if db_tool.tool_name != "database_list_all_tools":
             print(f"ERROR 'list_all_tools' tool has wrong name: {db_tool.tool_name} (expected database_list_all_tools)")
             return False
        print("OK Database content verified for Tools.")
        
        # Resources
        welcome_res = session.exec(select(ResourceRegistry).where(ResourceRegistry.name == "general_welcome_message")).first()
        time_res = session.exec(select(ResourceRegistry).where(ResourceRegistry.name == "system_server_time")).first()
        
        if not welcome_res or not time_res:
             print("ERROR One or more resources not found with expected prefixed names")
             all_res = session.exec(select(ResourceRegistry)).all()
             print(f"DEBUG: Found resources: {[r.name for r in all_res]}")
             return False
        
        if welcome_res.group != "general":
            print(f"ERROR 'welcome_message' resource has wrong group: {welcome_res.group}")
            return False
        if welcome_res.name != "general_welcome_message":
             print(f"ERROR 'welcome_message' has wrong name: {welcome_res.name}")
             return False

        if time_res.group != "system":
             print(f"ERROR 'server_time' resource has wrong group: {time_res.group}")
             return False
        if time_res.name != "system_server_time":
             print(f"ERROR 'server_time' has wrong name: {time_res.name}")
             return False
        print("OK Database content verified for Resources.")

        # Prompts
        review_prompt = session.exec(select(PromptRegistry).where(PromptRegistry.name == "developer_review_code")).first()
        if review_prompt.group != "developer":
             print(f"ERROR 'review_code' prompt has wrong group: {review_prompt.group}")
             return False
        print("OK Database content verified for Prompts.")

        # 3. Verify Runtime Filtering
        print("\n3. Verifying Runtime Filtering...")
        
        # List all tools (no filter)
        all_tools = list_tools_for_persona("default", session)
        print(f"   Total tools: {len(all_tools)}")
        
        # Filter by group 'utility'
        utility_tools = list_tools_for_persona("default", session, group="utility")
        print(f"   Utility tools: {[t['name'] for t in utility_tools]}")
        if len(utility_tools) != 1: # utility_greet (add is now math)
             print(f"ERROR Expected 1 utility tool, got {len(utility_tools)}")
             return False
        
        # Verify filtering checks the new names too if desired, but here we just check key
        if not utility_tools[0]['name'].startswith("utility_"):
             print("ERROR utility tool name not prefixed correctly")
             return False

        # Filter by group 'database'
        db_tools = list_tools_for_persona("default", session, group="database")
        print(f"   Database tools: {[t['name'] for t in db_tools]}")
        if len(db_tools) != 1: # list_all_tools
             print(f"ERROR Expected 1 database tool, got {len(db_tools)}")
             return False

        # Filter by group 'general' (tools - should be 0 based on specs)
        # Wait, did I set defaults? The specs only set utility and database. 
        # Actually any tools NOT in specs but in DB? No, clean load.
        # So general should be 0.
        general_tools = list_tools_for_persona("default", session, group="general")
        print(f"   General tools: {len(general_tools)}")
        
        # Resources Filtering
        general_resources = list_resources_for_persona("default", session, group="general")
        print(f"   General resources: {[r['name'] for r in general_resources]}")
        if len(general_resources) != 1: # welcome_message
            print(f"ERROR Expected 1 general resource, got {len(general_resources)}")
            return False
            
    print("\nOK All Tests Passed!")
    
    # Cleanup
    engine.dispose()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            print("WARNING: Could not remove test database file (file locked).")
    return True

if __name__ == "__main__":
    if test_group_feature():
        sys.exit(0)
    else:
        sys.exit(1)
