#!/usr/bin/env python3
"""
Test suite for YAML-based data seeding system.

This test validates:
1. YAML file loading
2. Tool upsert (create and update)
3. Resource upsert (static and dynamic)
4. Prompt upsert
5. Idempotency
6. Integration with runtime execution
"""

import os
import sys
import tempfile
from pathlib import Path

import yaml
from sqlmodel import Session, select

from load_specs import load_specs_from_yaml
from models import (
    CodeVault,
    ToolRegistry,
    ResourceRegistry,
    PromptRegistry,
    get_engine,
)
from runtime import execute_tool, get_resource


def test_yaml_loading():
    """Test that YAML file can be loaded."""
    print("\n🧪 Test 1: YAML file loading...")
    
    yaml_content = """
tools:
  - name: test_tool
    persona: default
    description: Test tool
    code_type: python
    code: |
      from base import ChameleonTool
      
      class TestTool(ChameleonTool):
          def run(self, arguments):
              return "test"
    input_schema:
      type: object
      properties: {}
      required: []
"""
    
    # Create temporary YAML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_yaml = f.name
    
    try:
        # Create temporary database
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        # Load specs
        success = load_specs_from_yaml(temp_yaml, db_url, clean=True)
        
        if success:
            print("  ✅ YAML file loaded successfully")
            return True
        else:
            print("  ❌ YAML file loading failed")
            return False
    finally:
        # Cleanup
        os.unlink(temp_yaml)
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_tool_creation():
    """Test that tools are created correctly."""
    print("\n🧪 Test 2: Tool creation...")
    
    yaml_content = """
tools:
  - name: greet
    persona: default
    description: Greet someone
    code_type: python
    code: |
      from base import ChameleonTool
      
      class GreetTool(ChameleonTool):
          def run(self, arguments):
              name = arguments.get('name', 'World')
              return f"Hello {name}!"
    input_schema:
      type: object
      properties:
        name:
          type: string
      required: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_yaml = f.name
    
    try:
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        # Load specs
        load_specs_from_yaml(temp_yaml, db_url, clean=True)
        
        # Verify tool was created
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry).where(ToolRegistry.tool_name == 'greet')
            tool = session.exec(statement).first()
            
            if tool and tool.description == 'Greet someone':
                print("  ✅ Tool created correctly")
                return True
            else:
                print("  ❌ Tool not found or incorrect")
                return False
    finally:
        os.unlink(temp_yaml)
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_tool_update_idempotency():
    """Test that running loader twice updates tools correctly."""
    print("\n🧪 Test 3: Tool update idempotency...")
    
    yaml_v1 = """
tools:
  - name: test_tool
    persona: default
    description: Version 1
    code_type: python
    code: |
      from base import ChameleonTool
      
      class TestTool(ChameleonTool):
          def run(self, arguments):
              return "v1"
    input_schema:
      type: object
      properties: {}
      required: []
"""
    
    yaml_v2 = """
tools:
  - name: test_tool
    persona: default
    description: Version 2
    code_type: python
    code: |
      from base import ChameleonTool
      
      class TestTool(ChameleonTool):
          def run(self, arguments):
              return "v2"
    input_schema:
      type: object
      properties: {}
      required: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_v1)
        temp_yaml = f.name
    
    try:
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        # Load v1
        load_specs_from_yaml(temp_yaml, db_url, clean=True)
        
        # Update YAML to v2
        with open(temp_yaml, 'w') as f:
            f.write(yaml_v2)
        
        # Load v2 (should update, not duplicate)
        load_specs_from_yaml(temp_yaml, db_url, clean=False)
        
        # Verify only one tool exists with v2 description
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry)
            tools = session.exec(statement).all()
            
            if len(tools) == 1 and tools[0].description == 'Version 2':
                print("  ✅ Tool updated correctly (idempotent)")
                return True
            else:
                print(f"  ❌ Expected 1 tool with 'Version 2', got {len(tools)} tools")
                return False
    finally:
        os.unlink(temp_yaml)
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_static_resource():
    """Test that static resources are loaded correctly."""
    print("\n🧪 Test 4: Static resource loading...")
    
    yaml_content = """
resources:
  - uri: test://static
    name: test_static
    persona: default
    description: Test static resource
    mime_type: text/plain
    is_dynamic: false
    static_content: |
      This is static content.
      It should be stored directly.
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_yaml = f.name
    
    try:
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        # Load specs
        load_specs_from_yaml(temp_yaml, db_url, clean=True)
        
        # Verify resource
        engine = get_engine(db_url)
        with Session(engine) as session:
            result = get_resource('test://static', 'default', session)
            
            if 'This is static content' in result:
                print("  ✅ Static resource loaded correctly")
                return True
            else:
                print(f"  ❌ Unexpected content: {result}")
                return False
    finally:
        os.unlink(temp_yaml)
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_dynamic_resource():
    """Test that dynamic resources are loaded correctly."""
    print("\n🧪 Test 5: Dynamic resource loading...")
    
    yaml_content = """
resources:
  - uri: test://dynamic
    name: test_dynamic
    persona: default
    description: Test dynamic resource
    mime_type: text/plain
    is_dynamic: true
    code_type: python
    code: |
      from base import ChameleonTool
      
      class DynamicResource(ChameleonTool):
          def run(self, arguments):
              return "Dynamic content generated"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_yaml = f.name
    
    try:
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        # Load specs
        load_specs_from_yaml(temp_yaml, db_url, clean=True)
        
        # Verify resource
        engine = get_engine(db_url)
        with Session(engine) as session:
            result = get_resource('test://dynamic', 'default', session)
            
            if 'Dynamic content generated' in result:
                print("  ✅ Dynamic resource loaded correctly")
                return True
            else:
                print(f"  ❌ Unexpected content: {result}")
                return False
    finally:
        os.unlink(temp_yaml)
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_prompt_loading():
    """Test that prompts are loaded correctly."""
    print("\n🧪 Test 6: Prompt loading...")
    
    yaml_content = """
prompts:
  - name: test_prompt
    persona: default
    description: Test prompt
    template: "Hello {name}, welcome to {place}!"
    arguments_schema:
      arguments:
        - name: name
          description: Person name
          required: true
        - name: place
          description: Place name
          required: true
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_yaml = f.name
    
    try:
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        # Load specs
        load_specs_from_yaml(temp_yaml, db_url, clean=True)
        
        # Verify prompt
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(PromptRegistry).where(PromptRegistry.name == 'test_prompt')
            prompt = session.exec(statement).first()
            
            if prompt and 'Hello {name}' in prompt.template:
                print("  ✅ Prompt loaded correctly")
                return True
            else:
                print("  ❌ Prompt not found or incorrect")
                return False
    finally:
        os.unlink(temp_yaml)
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def test_sql_tool():
    """Test that SQL-based tools work correctly."""
    print("\n🧪 Test 7: SQL-based tool loading...")
    
    yaml_content = """
tools:
  - name: count_tools
    persona: default
    description: Count all tools
    code_type: select
    code: |
      SELECT COUNT(*) as tool_count
      FROM toolregistry
    input_schema:
      type: object
      properties: {}
      required: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_yaml = f.name
    
    try:
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        # Load specs
        load_specs_from_yaml(temp_yaml, db_url, clean=True)
        
        # Execute SQL tool
        engine = get_engine(db_url)
        with Session(engine) as session:
            result = execute_tool('count_tools', 'default', {}, session)
            
            if result and result[0][0] == 1:  # Should count itself
                print("  ✅ SQL-based tool executed correctly")
                return True
            else:
                print(f"  ❌ Unexpected result: {result}")
                return False
    finally:
        os.unlink(temp_yaml)
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


def main():
    """Run all tests."""
    print("=" * 60)
    print("YAML-based Data Seeding System Tests")
    print("=" * 60)
    
    tests = [
        test_yaml_loading,
        test_tool_creation,
        test_tool_update_idempotency,
        test_static_resource,
        test_dynamic_resource,
        test_prompt_loading,
        test_sql_tool,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test {test.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All YAML loader tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
