"""
Integration test for MCP server logging functionality.

This test verifies that logging works correctly when the server handles requests.
"""

import os
import asyncio
from pathlib import Path
import logging

# Import server components
import sys
sys.path.insert(0, os.path.dirname(__file__))
from server import app, setup_logging, _get_persona_from_context
from models import get_engine, create_db_and_tables
from seed_db import seed_database


async def test_server_logging_integration():
    """Test that logging works when handling MCP requests."""
    print("\n🧪 Running MCP server logging integration tests...\n")
    
    # Clean up test database
    test_db = "test_chameleon_logging.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Clean up existing logs for clean test
    logs_dir = Path("logs")
    if logs_dir.exists():
        for log_file in logs_dir.glob("mcp_server_*.log"):
            try:
                log_file.unlink()
            except Exception:
                pass
    
    try:
        # Setup logging
        print("1️⃣  Setting up logging...")
        setup_logging()
        print("   ✅ Logging setup completed")
        
        # Verify log file was created
        log_files = list(logs_dir.glob("mcp_server_*.log"))
        if len(log_files) != 1:
            print(f"   ❌ Expected 1 log file, found {len(log_files)}")
            return False
        
        log_file_path = log_files[0]
        print(f"   ✅ Log file created: {log_file_path.name}")
        
        # Test 2: Call list_tools handler directly
        print("\n2️⃣  Testing handle_list_tools logging...")
        
        # We need to initialize the database for the handler to work
        from server import _db_engine, DATABASE_URL
        import server
        server._db_engine = get_engine(DATABASE_URL)
        create_db_and_tables(server._db_engine)
        seed_database(database_url=DATABASE_URL, clear_existing=True)
        
        # Import and call the handler
        from server import handle_list_tools
        tools = await handle_list_tools()
        print(f"   ✅ handle_list_tools returned {len(tools)} tools")
        
        # Test 3: Call handle_call_tool handler
        print("\n3️⃣  Testing handle_call_tool logging...")
        from server import handle_call_tool
        
        # Call a valid tool
        result = await handle_call_tool("greet", {"name": "TestUser"})
        print(f"   ✅ handle_call_tool executed successfully")
        
        # Call an invalid tool (should log error)
        result_error = await handle_call_tool("nonexistent_tool", {})
        print(f"   ✅ handle_call_tool error handling logged")
        
        # Test 4: Call handle_list_resources handler
        print("\n4️⃣  Testing handle_list_resources logging...")
        from server import handle_list_resources
        resources = await handle_list_resources()
        print(f"   ✅ handle_list_resources returned {len(resources)} resources")
        
        # Test 5: Call handle_read_resource handler
        print("\n5️⃣  Testing handle_read_resource logging...")
        from server import handle_read_resource
        
        # Read a valid resource
        try:
            content = await handle_read_resource("memo://welcome")
            print(f"   ✅ handle_read_resource executed successfully")
        except Exception as e:
            print(f"   ✅ handle_read_resource executed (result: {e})")
        
        # Try to read an invalid resource (should log error)
        try:
            content_error = await handle_read_resource("invalid://resource")
        except Exception as e:
            print(f"   ✅ handle_read_resource error handling logged")
        
        # Test 6: Verify log file contains expected entries
        print("\n6️⃣  Verifying log file content...")
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        
        expected_messages = [
            "Logging initialized",
            "Listing tools for persona",
            "Calling tool 'greet'",
            "Tool not found",  # From nonexistent_tool call
            "Listing resources for persona",
            "Reading resource"
        ]
        
        all_found = True
        for msg in expected_messages:
            if msg in log_content:
                print(f"   ✅ Found expected log message: '{msg}'")
            else:
                print(f"   ❌ Missing expected log message: '{msg}'")
                all_found = False
        
        if not all_found:
            print("\n   Log file content:")
            print("   " + "\n   ".join(log_content.split("\n")))
            return False
        
        print("\n" + "=" * 60)
        print("✅ All integration tests passed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except Exception:
                pass


if __name__ == "__main__":
    success = asyncio.run(test_server_logging_integration())
    exit(0 if success else 1)
