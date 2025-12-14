#!/usr/bin/env python3
"""
Test suite for the Dynamic Meta-Tools (Prompt and Resource Creators).

This test validates:
1. Meta-tool registration via add_dynamic_meta_tools.py
2. Creation of prompts via the meta-tool
3. Creation of resources via the meta-tool
4. Validation and error handling
5. Idempotency
"""

import os
import sys
import tempfile
from pathlib import Path

from sqlmodel import Session, select

from add_dynamic_meta_tools import (
    register_prompt_creator_tool,
    register_resource_creator_tool,
    register_dynamic_meta_tools,
    _compute_hash
)
from models import CodeVault, ToolRegistry, PromptRegistry, ResourceRegistry, get_engine, create_db_and_tables
from runtime import execute_tool


def test_prompt_meta_tool_registration():
    """Test that the prompt meta-tool can be registered successfully."""
    print("\n🧪 Test 1: Prompt meta-tool registration...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        success = register_prompt_creator_tool(database_url=db_url)
        
        if not success:
            print("  ❌ Prompt meta-tool registration failed")
            return False
        
        # Verify meta-tool exists in database
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'create_new_prompt'
            )
            tool = session.exec(statement).first()
            
            if tool and tool.description:
                print("  ✅ Prompt meta-tool registered successfully")
                print(f"     Tool name: {tool.tool_name}")
                print(f"     Description: {tool.description[:60]}...")
                return True
            else:
                print("  ❌ Prompt meta-tool not found in database")
                return False
    finally:
        os.unlink(temp_db.name)


def test_resource_meta_tool_registration():
    """Test that the resource meta-tool can be registered successfully."""
    print("\n🧪 Test 2: Resource meta-tool registration...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        success = register_resource_creator_tool(database_url=db_url)
        
        if not success:
            print("  ❌ Resource meta-tool registration failed")
            return False
        
        # Verify meta-tool exists in database
        engine = get_engine(db_url)
        with Session(engine) as session:
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == 'create_new_resource'
            )
            tool = session.exec(statement).first()
            
            if tool and tool.description:
                print("  ✅ Resource meta-tool registered successfully")
                print(f"     Tool name: {tool.tool_name}")
                print(f"     Description: {tool.description[:60]}...")
                return True
            else:
                print("  ❌ Resource meta-tool not found in database")
                return False
    finally:
        os.unlink(temp_db.name)


def test_create_simple_prompt():
    """Test creating a simple prompt via the meta-tool."""
    print("\n🧪 Test 3: Creating a simple prompt...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_prompt_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Call the meta-tool to create a new prompt
            result = execute_tool(
                'create_new_prompt',
                'default',
                {
                    'name': 'review_code',
                    'description': 'Review code for quality',
                    'template': 'Please review this code: {code}',
                    'arguments': [
                        {
                            'name': 'code',
                            'description': 'The code to review',
                            'required': True
                        }
                    ]
                },
                session
            )
            
            if 'Success' in result:
                print("  ✅ Prompt created successfully")
                print(f"     Result: {result}")
                
                # Verify the new prompt exists in PromptRegistry
                statement = select(PromptRegistry).where(
                    PromptRegistry.name == 'review_code'
                )
                new_prompt = session.exec(statement).first()
                
                if new_prompt:
                    print(f"     Prompt name: {new_prompt.name}")
                    print(f"     Description: {new_prompt.description}")
                    print(f"     Template: {new_prompt.template[:50]}...")
                    return True
                else:
                    print("  ❌ Prompt not found in PromptRegistry")
                    return False
            else:
                print(f"  ❌ Failed to create prompt: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_create_simple_resource():
    """Test creating a simple static resource via the meta-tool."""
    print("\n🧪 Test 4: Creating a simple resource...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        # Register the meta-tool
        register_resource_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Call the meta-tool to create a new resource
            result = execute_tool(
                'create_new_resource',
                'default',
                {
                    'uri': 'memo://project_notes',
                    'name': 'Project Notes',
                    'description': 'Important notes about the project',
                    'content': 'Project started on 2024-01-01. Key goals: achieve excellence.'
                },
                session
            )
            
            if 'Success' in result:
                print("  ✅ Resource created successfully")
                print(f"     Result: {result}")
                
                # Verify the new resource exists in ResourceRegistry
                statement = select(ResourceRegistry).where(
                    ResourceRegistry.uri_schema == 'memo://project_notes'
                )
                new_resource = session.exec(statement).first()
                
                if new_resource:
                    print(f"     URI: {new_resource.uri_schema}")
                    print(f"     Name: {new_resource.name}")
                    print(f"     Is dynamic: {new_resource.is_dynamic}")
                    print(f"     Static content: {new_resource.static_content[:50]}...")
                    
                    # Verify it's static
                    if not new_resource.is_dynamic and new_resource.active_hash_ref is None:
                        print("  ✅ Resource is correctly configured as static")
                        return True
                    else:
                        print("  ❌ Resource is not properly configured as static")
                        return False
                else:
                    print("  ❌ Resource not found in ResourceRegistry")
                    return False
            else:
                print(f"  ❌ Failed to create resource: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_prompt_validation():
    """Test validation of required fields for prompt creation."""
    print("\n🧪 Test 5: Prompt validation...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        register_prompt_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Test missing name
            result = execute_tool(
                'create_new_prompt',
                'default',
                {
                    'description': 'Test',
                    'template': 'Test {arg}'
                },
                session
            )
            
            if 'Error' in result and 'name' in result:
                print("  ✅ Missing name validation works")
            else:
                print(f"  ❌ Missing name validation failed: {result}")
                return False
            
            # Test missing description
            result = execute_tool(
                'create_new_prompt',
                'default',
                {
                    'name': 'test_prompt',
                    'template': 'Test {arg}'
                },
                session
            )
            
            if 'Error' in result and 'description' in result:
                print("  ✅ Missing description validation works")
            else:
                print(f"  ❌ Missing description validation failed: {result}")
                return False
            
            # Test missing template
            result = execute_tool(
                'create_new_prompt',
                'default',
                {
                    'name': 'test_prompt',
                    'description': 'Test'
                },
                session
            )
            
            if 'Error' in result and 'template' in result:
                print("  ✅ Missing template validation works")
                return True
            else:
                print(f"  ❌ Missing template validation failed: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_resource_validation():
    """Test validation of required fields for resource creation."""
    print("\n🧪 Test 6: Resource validation...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        register_resource_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Test missing uri
            result = execute_tool(
                'create_new_resource',
                'default',
                {
                    'name': 'Test',
                    'description': 'Test',
                    'content': 'Test content'
                },
                session
            )
            
            if 'Error' in result and 'uri' in result:
                print("  ✅ Missing uri validation works")
            else:
                print(f"  ❌ Missing uri validation failed: {result}")
                return False
            
            # Test missing content
            result = execute_tool(
                'create_new_resource',
                'default',
                {
                    'uri': 'test://resource',
                    'name': 'Test',
                    'description': 'Test'
                },
                session
            )
            
            if 'Error' in result and 'content' in result:
                print("  ✅ Missing content validation works")
                return True
            else:
                print(f"  ❌ Missing content validation failed: {result}")
                return False
    finally:
        os.unlink(temp_db.name)


def test_prompt_idempotency():
    """Test that creating the same prompt twice updates it."""
    print("\n🧪 Test 7: Prompt idempotency...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        register_prompt_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Create prompt
            result1 = execute_tool(
                'create_new_prompt',
                'default',
                {
                    'name': 'test_prompt',
                    'description': 'First version',
                    'template': 'Version 1: {arg}',
                    'arguments': []
                },
                session
            )
            
            if 'Success' not in result1:
                print(f"  ❌ First creation failed: {result1}")
                return False
            
            # Update prompt (same name)
            result2 = execute_tool(
                'create_new_prompt',
                'default',
                {
                    'name': 'test_prompt',
                    'description': 'Second version',
                    'template': 'Version 2: {arg}',
                    'arguments': []
                },
                session
            )
            
            if 'Success' not in result2:
                print(f"  ❌ Second creation failed: {result2}")
                return False
            
            # Verify only one prompt exists with updated content
            statement = select(PromptRegistry).where(
                PromptRegistry.name == 'test_prompt'
            )
            prompts = list(session.exec(statement).all())
            
            if len(prompts) == 1 and prompts[0].description == 'Second version':
                print("  ✅ Idempotency works - prompt was updated, not duplicated")
                return True
            else:
                print(f"  ❌ Idempotency failed - found {len(prompts)} prompts")
                return False
    finally:
        os.unlink(temp_db.name)


def test_resource_idempotency():
    """Test that creating the same resource twice updates it."""
    print("\n🧪 Test 8: Resource idempotency...")
    
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    try:
        register_resource_creator_tool(database_url=db_url)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Create resource
            result1 = execute_tool(
                'create_new_resource',
                'default',
                {
                    'uri': 'test://resource',
                    'name': 'Test Resource',
                    'description': 'First version',
                    'content': 'Content version 1'
                },
                session
            )
            
            if 'Success' not in result1:
                print(f"  ❌ First creation failed: {result1}")
                return False
            
            # Update resource (same uri)
            result2 = execute_tool(
                'create_new_resource',
                'default',
                {
                    'uri': 'test://resource',
                    'name': 'Test Resource Updated',
                    'description': 'Second version',
                    'content': 'Content version 2'
                },
                session
            )
            
            if 'Success' not in result2:
                print(f"  ❌ Second creation failed: {result2}")
                return False
            
            # Verify only one resource exists with updated content
            statement = select(ResourceRegistry).where(
                ResourceRegistry.uri_schema == 'test://resource'
            )
            resources = list(session.exec(statement).all())
            
            if len(resources) == 1 and resources[0].static_content == 'Content version 2':
                print("  ✅ Idempotency works - resource was updated, not duplicated")
                return True
            else:
                print(f"  ❌ Idempotency failed - found {len(resources)} resources")
                return False
    finally:
        os.unlink(temp_db.name)


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("Dynamic Meta-Tools Test Suite")
    print("=" * 60)
    
    tests = [
        test_prompt_meta_tool_registration,
        test_resource_meta_tool_registration,
        test_create_simple_prompt,
        test_create_simple_resource,
        test_prompt_validation,
        test_resource_validation,
        test_prompt_idempotency,
        test_resource_idempotency,
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
