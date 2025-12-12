#!/usr/bin/env python3
"""
Test suite for the is_auto_created flag feature.

This test validates:
1. System tools (loaded via load_specs.py) have is_auto_created=False
2. Auto-built tools (created via create_new_sql_tool) have is_auto_created=True
3. Tool listing shows [AUTO-BUILD] prefix for auto-created tools
4. Tool listing doesn't show prefix for system tools
"""

import os
import sys
import tempfile
from pathlib import Path

from sqlmodel import Session, select

from add_sql_creator_tool import register_sql_creator_tool
from load_specs import load_specs_from_yaml
from models import ToolRegistry, get_engine, create_db_and_tables
from runtime import execute_tool, list_tools_for_persona


def test_system_tool_flag():
    """Test that system tools loaded from YAML have is_auto_created=False."""
    print("\n🧪 Test 1: System tools have is_auto_created=False...")
    
    # Create temporary database and YAML file
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    temp_yaml = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml_content = """
tools:
  - name: test_system_tool
    description: A test system tool
    persona: default
    code_type: python
    code: |
      from base import ChameleonTool
      
      class TestSystemTool(ChameleonTool):
          def run(self, arguments):
              return "System tool executed"
    input_schema:
      type: object
      properties:
        test_param:
          type: string
          description: Test parameter
"""
    temp_yaml.write(yaml_content)
    temp_yaml.close()
    
    try:
        # Load specs from YAML
        success = load_specs_from_yaml(temp_yaml.name, db_url, clean=True)
        
        if not success:
            print("  ❌ Failed to load specs from YAML")
            return False
        
        # Check that the tool has is_auto_created=False
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'test_system_tool'
            )
            tool = session.exec(statement).first()
            
            if tool and tool.is_auto_created is False:
                print("  ✅ System tool has is_auto_created=False")
                print(f"     Tool: {tool.tool_name}")
                print(f"     is_auto_created: {tool.is_auto_created}")
                return True
            elif tool:
                print(f"  ❌ System tool has incorrect flag: {tool.is_auto_created}")
                return False
            else:
                print("  ❌ System tool not found in database")
                return False
    finally:
        os.unlink(temp_db.name)
        os.unlink(temp_yaml.name)


def test_auto_built_tool_flag():
    """Test that auto-built tools have is_auto_created=True."""
    print("\n🧪 Test 2: Auto-built tools have is_auto_created=True...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the SQL creator meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Create a new tool using the meta-tool
            result = execute_tool(
                'create_new_sql_tool',
                'default',
                {
                    'tool_name': 'test_auto_tool',
                    'description': 'A test auto-built tool',
                    'sql_query': 'SELECT * FROM sales_per_day WHERE store_name = :store_name',
                    'parameters': {
                        'store_name': {
                            'type': 'string',
                            'description': 'Store name',
                            'required': True
                        }
                    }
                },
                session
            )
            
            if 'Success' not in result:
                print(f"  ❌ Tool creation failed: {result}")
                return False
            
            # Check that the tool has is_auto_created=True
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'test_auto_tool'
            )
            tool = session.exec(statement).first()
            
            if tool and tool.is_auto_created == True:
                print("  ✅ Auto-built tool has is_auto_created=True")
                print(f"     Tool: {tool.tool_name}")
                print(f"     is_auto_created: {tool.is_auto_created}")
                return True
            elif tool:
                print(f"  ❌ Auto-built tool has incorrect flag: {tool.is_auto_created}")
                return False
            else:
                print("  ❌ Auto-built tool not found in database")
                return False
    finally:
        os.unlink(temp_db.name)


def test_auto_build_prefix_in_listing():
    """Test that [AUTO-BUILD] prefix appears for auto-created tools."""
    print("\n🧪 Test 3: [AUTO-BUILD] prefix appears in tool listing...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the SQL creator meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Create an auto-built tool
            result = execute_tool(
                'create_new_sql_tool',
                'default',
                {
                    'tool_name': 'test_prefix_tool',
                    'description': 'Tool to test prefix',
                    'sql_query': 'SELECT * FROM sales_per_day',
                    'parameters': {}
                },
                session
            )
            
            if 'Success' not in result:
                print(f"  ❌ Tool creation failed: {result}")
                return False
            
            # List tools and check for prefix
            tools = list_tools_for_persona('default', session)
            
            # Find our test tool
            test_tool = None
            for tool in tools:
                if tool['name'] == 'test_prefix_tool':
                    test_tool = tool
                    break
            
            if test_tool:
                if test_tool['description'].startswith('[AUTO-BUILD]'):
                    print("  ✅ [AUTO-BUILD] prefix found in description")
                    print(f"     Tool: {test_tool['name']}")
                    print(f"     Description: {test_tool['description']}")
                    return True
                else:
                    print(f"  ❌ [AUTO-BUILD] prefix not found in description: {test_tool['description']}")
                    return False
            else:
                print("  ❌ Test tool not found in listing")
                return False
    finally:
        os.unlink(temp_db.name)


def test_no_prefix_for_system_tools():
    """Test that system tools don't get [AUTO-BUILD] prefix."""
    print("\n🧪 Test 4: System tools don't get [AUTO-BUILD] prefix...")
    
    # Create temporary database and YAML file
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    temp_yaml = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml_content = """
tools:
  - name: test_no_prefix_tool
    description: Tool should not have prefix
    persona: default
    code_type: python
    code: |
      from base import ChameleonTool
      
      class TestNoPrefix(ChameleonTool):
          def run(self, arguments):
              return "No prefix expected"
    input_schema:
      type: object
      properties: {}
"""
    temp_yaml.write(yaml_content)
    temp_yaml.close()
    
    try:
        # Load specs from YAML
        success = load_specs_from_yaml(temp_yaml.name, db_url, clean=True)
        
        if not success:
            print("  ❌ Failed to load specs from YAML")
            return False
        
        # List tools and verify no prefix
        engine = get_engine(db_url)
        with Session(engine) as session:
            tools = list_tools_for_persona('default', session)
            
            # Find our test tool
            test_tool = None
            for tool in tools:
                if tool['name'] == 'test_no_prefix_tool':
                    test_tool = tool
                    break
            
            if test_tool:
                if not test_tool['description'].startswith('[AUTO-BUILD]'):
                    print("  ✅ System tool has no [AUTO-BUILD] prefix")
                    print(f"     Tool: {test_tool['name']}")
                    print(f"     Description: {test_tool['description']}")
                    return True
                else:
                    print(f"  ❌ System tool incorrectly has [AUTO-BUILD] prefix: {test_tool['description']}")
                    return False
            else:
                print("  ❌ Test tool not found in listing")
                return False
    finally:
        os.unlink(temp_db.name)
        os.unlink(temp_yaml.name)


def test_mixed_tools_listing():
    """Test listing with both system and auto-built tools."""
    print("\n🧪 Test 5: Mixed tools listing (system + auto-built)...")
    
    # Create temporary database and YAML file
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    temp_yaml = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml_content = """
tools:
  - name: system_tool_1
    description: First system tool
    persona: default
    code_type: python
    code: |
      from base import ChameleonTool
      
      class SystemTool1(ChameleonTool):
          def run(self, arguments):
              return "System tool 1"
    input_schema:
      type: object
      properties: {}
"""
    temp_yaml.write(yaml_content)
    temp_yaml.close()
    
    try:
        # Load system tool from YAML
        success = load_specs_from_yaml(temp_yaml.name, db_url, clean=True)
        
        if not success:
            print("  ❌ Failed to load specs from YAML")
            return False
        
        # Register SQL creator and create an auto-built tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Create auto-built tool
            result = execute_tool(
                'create_new_sql_tool',
                'default',
                {
                    'tool_name': 'auto_tool_1',
                    'description': 'First auto-built tool',
                    'sql_query': 'SELECT * FROM sales_per_day',
                    'parameters': {}
                },
                session
            )
            
            if 'Success' not in result:
                print(f"  ❌ Auto tool creation failed: {result}")
                return False
            
            # List all tools
            tools = list_tools_for_persona('default', session)
            
            # Check each tool
            system_tool_found = False
            auto_tool_found = False
            meta_tool_found = False
            
            for tool in tools:
                if tool['name'] == 'system_tool_1':
                    system_tool_found = True
                    if tool['description'].startswith('[AUTO-BUILD]'):
                        print(f"  ❌ System tool has incorrect prefix: {tool['description']}")
                        return False
                elif tool['name'] == 'auto_tool_1':
                    auto_tool_found = True
                    if not tool['description'].startswith('[AUTO-BUILD]'):
                        print(f"  ❌ Auto tool missing prefix: {tool['description']}")
                        return False
                elif tool['name'] == 'create_new_sql_tool':
                    meta_tool_found = True
                    # Meta-tool should not have prefix (it's a system tool)
                    if tool['description'].startswith('[AUTO-BUILD]'):
                        print(f"  ❌ Meta-tool has incorrect prefix: {tool['description']}")
                        return False
            
            if system_tool_found and auto_tool_found and meta_tool_found:
                print("  ✅ Mixed tool listing correct")
                print(f"     Found system tool without prefix")
                print(f"     Found auto-built tool with prefix")
                print(f"     Found meta-tool without prefix")
                return True
            else:
                print(f"  ❌ Not all expected tools found")
                print(f"     system_tool_1: {system_tool_found}")
                print(f"     auto_tool_1: {auto_tool_found}")
                print(f"     create_new_sql_tool: {meta_tool_found}")
                return False
    finally:
        os.unlink(temp_db.name)
        os.unlink(temp_yaml.name)


def test_update_preserves_flag():
    """Test that updating a tool preserves the is_auto_created flag."""
    print("\n🧪 Test 6: Updating tools preserves is_auto_created flag...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the SQL creator meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Create an auto-built tool
            result = execute_tool(
                'create_new_sql_tool',
                'default',
                {
                    'tool_name': 'test_update_tool',
                    'description': 'Original description',
                    'sql_query': 'SELECT * FROM sales_per_day',
                    'parameters': {}
                },
                session
            )
            
            if 'Success' not in result:
                print(f"  ❌ Tool creation failed: {result}")
                return False
            
            # Update the same tool
            result = execute_tool(
                'create_new_sql_tool',
                'default',
                {
                    'tool_name': 'test_update_tool',
                    'description': 'Updated description',
                    'sql_query': 'SELECT * FROM sales_per_day WHERE department = :dept',
                    'parameters': {
                        'dept': {
                            'type': 'string',
                            'description': 'Department name',
                            'required': True
                        }
                    }
                },
                session
            )
            
            if 'Success' not in result:
                print(f"  ❌ Tool update failed: {result}")
                return False
            
            # Check that the tool still has is_auto_created=True
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'test_update_tool'
            )
            tool = session.exec(statement).first()
            
            if tool and tool.is_auto_created is True:
                print("  ✅ Updated tool still has is_auto_created=True")
                print(f"     Tool: {tool.tool_name}")
                print(f"     Description: {tool.description}")
                print(f"     is_auto_created: {tool.is_auto_created}")
                return True
            elif tool:
                print(f"  ❌ Updated tool lost is_auto_created flag: {tool.is_auto_created}")
                return False
            else:
                print("  ❌ Updated tool not found in database")
                return False
    finally:
        os.unlink(temp_db.name)


def run_all_tests():
    """Run all test cases."""
    print("=" * 60)
    print("is_auto_created Flag Feature Test Suite")
    print("=" * 60)
    
    tests = [
        test_system_tool_flag,
        test_auto_built_tool_flag,
        test_auto_build_prefix_in_listing,
        test_no_prefix_for_system_tools,
        test_mixed_tools_listing,
        test_update_preserves_flag,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ Test raised exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


def main():
    """Main entry point."""
    return run_all_tests()


if __name__ == '__main__':
    sys.exit(main())
