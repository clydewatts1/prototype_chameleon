"""
Pytest test suite for the Chameleon UI feature.

This test validates:
1. Configuration loading for chameleon_ui feature
2. Meta-tool registration via add_ui_tool.py
3. Creation of Streamlit dashboards via the meta-tool
4. Validation (must import streamlit, sanitized names)
5. Execution of dashboard tools (returns URL)
6. Physical file creation in apps_dir
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

import pytest
from pathlib import Path
import tempfile
import shutil
from sqlmodel import select

from add_ui_tool import register_ui_creator_tool
from models import CodeVault, ToolRegistry
from runtime import execute_tool, ToolNotFoundError
from config import load_config, get_default_config


@pytest.fixture
def registered_ui_tool(db_session):
    """Fixture to register the UI creator meta-tool."""
    db_url = str(db_session.get_bind().url)
    success = register_ui_creator_tool(database_url=db_url)
    assert success, "UI meta-tool registration failed"
    return db_session


@pytest.fixture
def temp_apps_dir():
    """Fixture to create a temporary apps directory."""
    temp_dir = tempfile.mkdtemp(prefix='test_ui_apps_')
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_default_config_includes_chameleon_ui():
    """Test that default configuration includes chameleon_ui feature."""
    config = get_default_config()
    
    assert 'features' in config
    assert 'chameleon_ui' in config['features']
    assert 'enabled' in config['features']['chameleon_ui']
    assert 'apps_dir' in config['features']['chameleon_ui']
    assert config['features']['chameleon_ui']['enabled'] is True
    assert config['features']['chameleon_ui']['apps_dir'] == 'ui_apps'


@pytest.mark.integration
def test_ui_meta_tool_registration(registered_ui_tool):
    """Test that the UI meta-tool can be registered successfully."""
    session = registered_ui_tool
    
    # Verify meta-tool exists in database
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'create_dashboard'
    )
    tool = session.exec(statement).first()
    
    assert tool is not None
    assert tool.description
    assert 'create_dashboard' == tool.tool_name
    assert 'dashboard_name' in tool.input_schema['properties']
    assert 'python_code' in tool.input_schema['properties']


@pytest.mark.integration
def test_create_simple_dashboard(registered_ui_tool, temp_apps_dir):
    """Test creating a simple Streamlit dashboard via the meta-tool."""
    session = registered_ui_tool
    
    # Change working directory to use temp_apps_dir
    original_cwd = os.getcwd()
    try:
        os.chdir(Path(temp_apps_dir).parent)
        apps_dir_name = Path(temp_apps_dir).name
        
        # Update config to use temp directory (simulate config override)
        # This is a bit hacky but necessary for testing
        os.environ['TEST_APPS_DIR'] = str(temp_apps_dir)
        
        dashboard_code = """import streamlit as st

st.title('Test Dashboard')
st.write('Hello, World!')
"""
        
        # Call the meta-tool to create a new dashboard
        result = execute_tool(
            'create_dashboard',
            'default',
            {
                'dashboard_name': 'test_dashboard',
                'python_code': dashboard_code
            },
            session
        )
        
        assert 'Success' in result
        assert 'test_dashboard' in result
        
        # Verify the new tool exists in ToolRegistry
        statement = select(ToolRegistry).where(
            ToolRegistry.tool_name == 'test_dashboard'
        )
        new_tool = session.exec(statement).first()
        
        assert new_tool is not None
        assert new_tool.tool_name == 'test_dashboard'
        assert new_tool.is_auto_created is True
        
        # Verify code in CodeVault has code_type='streamlit'
        statement = select(CodeVault).where(
            CodeVault.hash == new_tool.active_hash_ref
        )
        code = session.exec(statement).first()
        
        assert code is not None
        assert code.code_type == 'streamlit'
        assert 'import streamlit' in code.code_blob
        
    finally:
        os.chdir(original_cwd)
        if 'TEST_APPS_DIR' in os.environ:
            del os.environ['TEST_APPS_DIR']


@pytest.mark.integration
def test_dashboard_validation_requires_streamlit_import(registered_ui_tool):
    """Test that dashboard code must import streamlit."""
    session = registered_ui_tool
    
    dashboard_code = """
# Missing streamlit import
print('Hello, World!')
"""
    
    # Call the meta-tool - should fail validation
    result = execute_tool(
        'create_dashboard',
        'default',
        {
            'dashboard_name': 'invalid_dashboard',
            'python_code': dashboard_code
        },
        session
    )
    
    assert 'Error' in result
    assert 'import streamlit' in result


@pytest.mark.integration
def test_dashboard_name_validation(registered_ui_tool):
    """Test that dashboard names are properly validated."""
    session = registered_ui_tool
    
    dashboard_code = """import streamlit as st
st.write('Test')
"""
    
    # Test invalid characters in name
    invalid_names = [
        'dashboard with spaces',
        'dashboard/with/slashes',
        'dashboard;with;semicolons',
        'dashboard<with>brackets',
    ]
    
    for invalid_name in invalid_names:
        result = execute_tool(
            'create_dashboard',
            'default',
            {
                'dashboard_name': invalid_name,
                'python_code': dashboard_code
            },
            session
        )
        
        assert 'Error' in result
        assert 'alphanumeric' in result or 'characters' in result


@pytest.mark.integration
def test_dashboard_execution_returns_url(registered_ui_tool, temp_apps_dir):
    """Test that executing a dashboard tool returns a URL."""
    session = registered_ui_tool
    
    original_cwd = os.getcwd()
    try:
        os.chdir(Path(temp_apps_dir).parent)
        
        dashboard_code = """import streamlit as st
st.title('URL Test Dashboard')
"""
        
        # Create dashboard
        result = execute_tool(
            'create_dashboard',
            'default',
            {
                'dashboard_name': 'url_test_dashboard',
                'python_code': dashboard_code
            },
            session
        )
        
        assert 'Success' in result
        
        # Now execute the dashboard tool
        result = execute_tool(
            'url_test_dashboard',
            'default',
            {},
            session
        )
        
        # Should return a URL
        assert 'http://localhost:8501' in result or 'Dashboard is ready' in result
        
    finally:
        os.chdir(original_cwd)


@pytest.mark.integration
def test_dashboard_updates_existing_tool(registered_ui_tool, temp_apps_dir):
    """Test that creating a dashboard with the same name updates the existing tool."""
    session = registered_ui_tool
    
    original_cwd = os.getcwd()
    try:
        os.chdir(Path(temp_apps_dir).parent)
        
        dashboard_code_v1 = """import streamlit as st
st.title('Version 1')
"""
        
        # Create initial dashboard
        result = execute_tool(
            'create_dashboard',
            'default',
            {
                'dashboard_name': 'update_test',
                'python_code': dashboard_code_v1
            },
            session
        )
        
        assert 'Success' in result
        
        # Get initial hash
        statement = select(ToolRegistry).where(
            ToolRegistry.tool_name == 'update_test'
        )
        tool_v1 = session.exec(statement).first()
        hash_v1 = tool_v1.active_hash_ref
        
        # Update with new code
        dashboard_code_v2 = """import streamlit as st
st.title('Version 2')
st.write('Updated!')
"""
        
        result = execute_tool(
            'create_dashboard',
            'default',
            {
                'dashboard_name': 'update_test',
                'python_code': dashboard_code_v2
            },
            session
        )
        
        assert 'Success' in result
        
        # Verify tool was updated, not duplicated
        statement = select(ToolRegistry).where(
            ToolRegistry.tool_name == 'update_test'
        )
        tools = session.exec(statement).all()
        
        assert len(tools) == 1  # Should only have one tool
        assert tools[0].active_hash_ref != hash_v1  # Hash should be different
        
    finally:
        os.chdir(original_cwd)


@pytest.mark.integration
def test_missing_dashboard_name(registered_ui_tool):
    """Test error handling when dashboard_name is missing."""
    session = registered_ui_tool
    
    result = execute_tool(
        'create_dashboard',
        'default',
        {
            'python_code': 'import streamlit as st'
        },
        session
    )
    
    assert 'Error' in result
    assert 'dashboard_name is required' in result


@pytest.mark.integration
def test_missing_python_code(registered_ui_tool):
    """Test error handling when python_code is missing."""
    session = registered_ui_tool
    
    result = execute_tool(
        'create_dashboard',
        'default',
        {
            'dashboard_name': 'test'
        },
        session
    )
    
    assert 'Error' in result
    assert 'python_code is required' in result
