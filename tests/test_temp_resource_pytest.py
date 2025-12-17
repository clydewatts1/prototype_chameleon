import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

"""
Pytest test suite for the Temporary Resource feature.

This test validates:
1. Meta-tool registration via add_temp_resource_creator.py
2. Creation of temporary static resources
3. Creation of temporary dynamic resources
4. Retrieval of temporary resources via get_resource
5. Listing resources includes temporary resources with [TEMP] prefix
6. Non-persistence to database
7. Persona-based filtering
8. Input validation
"""

import pytest
from sqlmodel import select

from add_temp_resource_creator import register_temp_resource_creator
from models import CodeVault, ToolRegistry, ResourceRegistry
from runtime import (
    execute_tool, 
    get_resource, 
    list_resources_for_persona, 
    TEMP_RESOURCE_REGISTRY, 
    TEMP_CODE_VAULT,
    ResourceNotFoundError
)


@pytest.fixture
def registered_temp_resource_creator(db_session):
    """Fixture to register the temporary resource creator meta-tool."""
    db_url = str(db_session.get_bind().url)
    success = register_temp_resource_creator(database_url=db_url)
    assert success, "Meta-tool registration failed"
    return db_session


@pytest.mark.integration
def test_temp_resource_creator_registration(registered_temp_resource_creator):
    """Test that the temporary resource creator can be registered successfully."""
    session = registered_temp_resource_creator
    
    # Verify meta-tool exists in database
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'create_temp_resource'
    )
    tool = session.exec(statement).first()
    
    assert tool is not None
    assert tool.description
    assert 'create_temp_resource' == tool.tool_name
    assert 'temporary' in tool.description.lower() or 'temp' in tool.description.lower()


@pytest.mark.integration
def test_create_static_temp_resource(registered_temp_resource_creator):
    """Test creating a simple static temporary resource."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Call the meta-tool to create a new temporary static resource
    result = execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'memo://test',
            'name': 'Test Memo',
            'description': 'A test memo resource',
            'content': 'This is test memo content',
            'is_dynamic': False,
            'mime_type': 'text/plain'
        },
        session
    )
    
    assert 'Success' in result
    assert 'TEMPORARY' in result or 'TEMP' in result
    assert 'memo://test' in result
    
    # Verify the resource is in temporary storage
    temp_key = 'memo://test:default'
    assert temp_key in TEMP_RESOURCE_REGISTRY
    
    # Verify it's NOT in the database
    statement = select(ResourceRegistry).where(
        ResourceRegistry.uri_schema == 'memo://test'
    )
    db_resource = session.exec(statement).first()
    assert db_resource is None, "Temporary resource should not be in database"


@pytest.mark.integration
def test_create_dynamic_temp_resource(registered_temp_resource_creator):
    """Test creating a dynamic temporary resource with code."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Simple Python code for dynamic resource
    dynamic_code = """
from base import ChameleonTool

class DynamicResource(ChameleonTool):
    def run(self, arguments):
        return "Dynamic content from code"
"""
    
    # Call the meta-tool to create a new temporary dynamic resource
    result = execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'data://dynamic',
            'name': 'Dynamic Test',
            'description': 'A dynamic test resource',
            'content': dynamic_code,
            'is_dynamic': True,
            'mime_type': 'text/plain'
        },
        session
    )
    
    assert 'Success' in result
    assert 'dynamic' in result.lower()
    
    # Verify the resource is in temporary storage
    temp_key = 'data://dynamic:default'
    assert temp_key in TEMP_RESOURCE_REGISTRY
    
    # Verify code is in TEMP_CODE_VAULT
    resource_meta = TEMP_RESOURCE_REGISTRY[temp_key]
    code_hash = resource_meta['code_hash']
    assert code_hash in TEMP_CODE_VAULT


@pytest.mark.integration
def test_retrieve_static_temp_resource(registered_temp_resource_creator):
    """Test retrieving a static temporary resource via get_resource."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary static resource
    test_content = "Hello from temporary resource!"
    execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'memo://retrieve_test',
            'name': 'Retrieve Test',
            'description': 'Resource for retrieval testing',
            'content': test_content,
            'is_dynamic': False
        },
        session
    )
    
    # Now retrieve it using get_resource
    content = get_resource('memo://retrieve_test', 'default', session, session)
    
    assert content == test_content


@pytest.mark.integration
def test_retrieve_dynamic_temp_resource(registered_temp_resource_creator):
    """Test retrieving a dynamic temporary resource via get_resource."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create dynamic code
    dynamic_code = """
from base import ChameleonTool

class TestDynamicResource(ChameleonTool):
    def run(self, arguments):
        return "Generated at runtime: Hello!"
"""
    
    # Create a temporary dynamic resource
    execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'data://dynamic_retrieve',
            'name': 'Dynamic Retrieve Test',
            'description': 'Dynamic resource for retrieval testing',
            'content': dynamic_code,
            'is_dynamic': True
        },
        session
    )
    
    # Now retrieve it using get_resource (should execute the code)
    content = get_resource('data://dynamic_retrieve', 'default', session, session)
    
    assert 'Generated at runtime' in content
    assert 'Hello!' in content


@pytest.mark.integration
def test_list_resources_includes_temp_resources(registered_temp_resource_creator):
    """Test that list_resources_for_persona includes temporary resources with [TEMP] prefix."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary resource
    execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'memo://list_test',
            'name': 'List Test Resource',
            'description': 'Resource for listing test',
            'content': 'Test content',
            'is_dynamic': False
        },
        session
    )
    
    # List resources for default persona
    resources = list_resources_for_persona('default', session)
    
    # Find our temporary resource
    temp_resource = None
    for resource in resources:
        if resource['uri'] == 'memo://list_test':
            temp_resource = resource
            break
    
    assert temp_resource is not None, "Temporary resource should appear in list"
    assert '[TEMP]' in temp_resource['description']
    assert temp_resource['name'] == 'List Test Resource'


@pytest.mark.integration
def test_temp_resource_not_persisted_to_database(registered_temp_resource_creator):
    """Test that temporary resources are never written to the database."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary resource
    execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'memo://persistence_test',
            'name': 'Persistence Test',
            'description': 'Testing non-persistence',
            'content': 'Should not be in DB',
            'is_dynamic': False
        },
        session
    )
    
    # Verify it's in temporary storage
    temp_key = 'memo://persistence_test:default'
    assert temp_key in TEMP_RESOURCE_REGISTRY
    
    # Verify it's NOT in the database
    statement = select(ResourceRegistry).where(
        ResourceRegistry.uri_schema == 'memo://persistence_test'
    )
    db_resource = session.exec(statement).first()
    assert db_resource is None, "Temporary resource should never be in database"


@pytest.mark.integration
def test_temp_resource_persona_filtering(registered_temp_resource_creator):
    """Test that temporary resources are filtered by persona."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary resource for 'default' persona
    execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'memo://persona_test',
            'name': 'Persona Test',
            'description': 'Testing persona filtering',
            'content': 'Default persona content',
            'is_dynamic': False
        },
        session
    )
    
    # List resources for 'default' persona - should include our resource
    resources_default = list_resources_for_persona('default', session)
    found_in_default = any(r['uri'] == 'memo://persona_test' for r in resources_default)
    assert found_in_default, "Resource should be visible to default persona"
    
    # List resources for a different persona - should NOT include our resource
    resources_other = list_resources_for_persona('other_persona', session)
    found_in_other = any(r['uri'] == 'memo://persona_test' for r in resources_other)
    assert not found_in_other, "Resource should NOT be visible to other persona"


@pytest.mark.integration
def test_temp_resource_validation_missing_uri(registered_temp_resource_creator):
    """Test that missing URI is rejected."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Try to create a resource without URI
    result = execute_tool(
        'create_temp_resource',
        'default',
        {
            'name': 'Test',
            'description': 'Test',
            'content': 'Test'
        },
        session
    )
    
    assert 'Error' in result
    assert 'uri' in result.lower()


@pytest.mark.integration
def test_temp_resource_validation_invalid_uri_format(registered_temp_resource_creator):
    """Test that invalid URI format is rejected."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Try to create a resource with invalid URI (no scheme)
    result = execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'invalid_uri_format',
            'name': 'Test',
            'description': 'Test',
            'content': 'Test'
        },
        session
    )
    
    assert 'Error' in result
    assert '://' in result


@pytest.mark.integration
def test_temp_resource_validation_missing_content(registered_temp_resource_creator):
    """Test that missing content is rejected."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Try to create a resource without content
    result = execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'memo://test',
            'name': 'Test',
            'description': 'Test'
        },
        session
    )
    
    assert 'Error' in result
    assert 'content' in result.lower()


@pytest.mark.integration
def test_temp_resource_not_found_error(registered_temp_resource_creator):
    """Test that accessing non-existent temporary resource raises ResourceNotFoundError."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Try to retrieve a non-existent resource
    with pytest.raises(ResourceNotFoundError):
        get_resource('memo://nonexistent', 'default', session, session)


@pytest.mark.integration
def test_temp_resource_cleared_after_registry_clear(registered_temp_resource_creator):
    """Test that clearing temporary storage removes resources completely."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary resource
    execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'memo://clear_test',
            'name': 'Clear Test',
            'description': 'Testing clearing',
            'content': 'Test content',
            'is_dynamic': False
        },
        session
    )
    
    # Verify it exists in temporary storage
    temp_key = 'memo://clear_test:default'
    assert temp_key in TEMP_RESOURCE_REGISTRY
    
    # Clear temporary storage
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Verify it's gone
    assert temp_key not in TEMP_RESOURCE_REGISTRY
    
    # Verify it was never in the database
    statement = select(ResourceRegistry).where(
        ResourceRegistry.uri_schema == 'memo://clear_test'
    )
    db_resource = session.exec(statement).first()
    assert db_resource is None


@pytest.mark.integration
def test_temp_resource_mime_type_default(registered_temp_resource_creator):
    """Test that MIME type defaults to text/plain when not specified."""
    session = registered_temp_resource_creator
    
    # Clear any existing temporary resources
    TEMP_RESOURCE_REGISTRY.clear()
    TEMP_CODE_VAULT.clear()
    
    # Create a temporary resource without specifying mime_type
    execute_tool(
        'create_temp_resource',
        'default',
        {
            'uri': 'memo://mime_test',
            'name': 'MIME Test',
            'description': 'Testing MIME type default',
            'content': 'Test content',
            'is_dynamic': False
        },
        session
    )
    
    # List resources and check MIME type
    resources = list_resources_for_persona('default', session)
    mime_test_resource = None
    for resource in resources:
        if resource['uri'] == 'memo://mime_test':
            mime_test_resource = resource
            break
    
    assert mime_test_resource is not None
    assert mime_test_resource['mimeType'] == 'text/plain'
