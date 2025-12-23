"""
Pytest test suite for ChainTool (Workflow Engine).

This test validates:
1. DAG validation - forward references blocked
2. Successful chain execution with variable passing
3. Error feedback with partial success reporting
4. Variable substitution edge cases
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

import pytest
from sqlmodel import select
from models import CodeVault, ToolRegistry
from runtime import execute_tool
from common.hash_utils import compute_hash


@pytest.fixture
def setup_test_tools(db_session):
    """Fixture to register simple test tools for chaining."""
    # Tool 1: Returns a constant value
    echo_tool_code = '''
from base import ChameleonTool

class EchoTool(ChameleonTool):
    def run(self, arguments):
        return arguments.get('message', 'default message')
'''
    
    # Tool 2: Adds a prefix to input
    prefix_tool_code = '''
from base import ChameleonTool

class PrefixTool(ChameleonTool):
    def run(self, arguments):
        text = arguments.get('text', '')
        prefix = arguments.get('prefix', 'PREFIX:')
        return f"{prefix} {text}"
'''
    
    # Tool 3: Returns a dict with multiple fields
    multi_field_tool_code = '''
from base import ChameleonTool

class MultiFieldTool(ChameleonTool):
    def run(self, arguments):
        name = arguments.get('name', 'Anonymous')
        return {
            'greeting': f'Hello {name}',
            'status': 'success',
            'count': 42
        }
'''
    
    # Tool 4: Intentionally fails
    fail_tool_code = '''
from base import ChameleonTool

class FailTool(ChameleonTool):
    def run(self, arguments):
        raise ValueError("Intentional failure for testing")
'''
    
    # Add tools to database
    tools = [
        ('test_echo', echo_tool_code, 'Returns the message argument'),
        ('test_prefix', prefix_tool_code, 'Adds a prefix to text'),
        ('test_multi_field', multi_field_tool_code, 'Returns dict with multiple fields'),
        ('test_fail', fail_tool_code, 'Always fails for testing error handling'),
    ]
    
    for tool_name, code, description in tools:
        code_hash = compute_hash(code)
        
        # Add code to CodeVault
        existing_code = db_session.exec(
            select(CodeVault).where(CodeVault.hash == code_hash)
        ).first()
        
        if not existing_code:
            code_vault = CodeVault(
                hash=code_hash,
                code_blob=code,
                code_type="python"
            )
            db_session.add(code_vault)
        
        # Add tool to registry
        existing_tool = db_session.exec(
            select(ToolRegistry).where(
                ToolRegistry.tool_name == tool_name,
                ToolRegistry.target_persona == "default"
            )
        ).first()
        
        if not existing_tool:
            tool_registry = ToolRegistry(
                tool_name=tool_name,
                target_persona="default",
                description=description,
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                active_hash_ref=code_hash,
                group="test",
                is_auto_created=False
            )
            db_session.add(tool_registry)
    
    db_session.commit()
    return db_session


@pytest.fixture
def setup_chain_tool(db_session):
    """Fixture to register ChainTool in the test database."""
    from add_chain_tool import register_chain_tool
    
    register_chain_tool(db_session)
    db_session.commit()
    
    return db_session


@pytest.mark.integration
def test_dag_validation_forward_reference(setup_chain_tool, setup_test_tools):
    """Test that DAG validation blocks forward references."""
    session = setup_test_tools
    
    # Create a chain where step1 references step2 (forward reference)
    arguments = {
        'steps': [
            {
                'id': 'step1',
                'tool': 'test_echo',
                'args': {'message': '${step2}'}  # Forward reference!
            },
            {
                'id': 'step2',
                'tool': 'test_echo',
                'args': {'message': 'Hello'}
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should fail with DAG validation error
    assert "DAG Validation Error" in result
    assert "forward" in result.lower() or "future" in result.lower()
    assert "step2" in result


@pytest.mark.integration
def test_dag_validation_unknown_reference(setup_chain_tool, setup_test_tools):
    """Test that DAG validation blocks unknown step references."""
    session = setup_test_tools
    
    # Create a chain where step1 references non-existent step
    arguments = {
        'steps': [
            {
                'id': 'step1',
                'tool': 'test_echo',
                'args': {'message': '${nonexistent}'}  # Unknown reference
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should fail with DAG validation error
    assert "DAG Validation Error" in result
    assert "nonexistent" in result


@pytest.mark.integration
def test_chain_successful_execution(setup_chain_tool, setup_test_tools):
    """Test successful chain execution with variable passing."""
    session = setup_test_tools
    
    # Create a valid chain
    arguments = {
        'steps': [
            {
                'id': 'step1',
                'tool': 'test_echo',
                'args': {'message': 'World'}
            },
            {
                'id': 'step2',
                'tool': 'test_prefix',
                'args': {
                    'prefix': 'Hello',
                    'text': '${step1}'
                }
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should succeed
    assert "CHAIN EXECUTION COMPLETED" in result
    assert "Total steps executed: 2" in result
    assert "Hello World" in result


@pytest.mark.integration
def test_chain_dict_field_access(setup_chain_tool, setup_test_tools):
    """Test variable substitution with dict field access."""
    session = setup_test_tools
    
    # Create a chain that accesses dict fields
    arguments = {
        'steps': [
            {
                'id': 'step1',
                'tool': 'test_multi_field',
                'args': {'name': 'Alice'}
            },
            {
                'id': 'step2',
                'tool': 'test_echo',
                'args': {'message': '${step1.greeting}'}  # Access dict field
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should succeed and access the greeting field
    assert "CHAIN EXECUTION COMPLETED" in result
    assert "Hello Alice" in result


@pytest.mark.integration
def test_chain_error_feedback(setup_chain_tool, setup_test_tools):
    """Test error feedback with partial success reporting."""
    session = setup_test_tools
    
    # Create a chain where the second step fails
    arguments = {
        'steps': [
            {
                'id': 'step1',
                'tool': 'test_echo',
                'args': {'message': 'Success'}
            },
            {
                'id': 'step2',
                'tool': 'test_fail',  # This will fail
                'args': {}
            },
            {
                'id': 'step3',
                'tool': 'test_echo',
                'args': {'message': 'Should not reach here'}
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should report partial success
    assert "CHAIN EXECUTION FAILED" in result
    assert "Failed at: Step 2/3" in result
    assert "test_fail" in result
    assert "Successfully executed steps: 1/3" in result
    assert "Step 1: test_echo" in result
    assert "Intentional failure" in result


@pytest.mark.integration
def test_chain_multiple_variable_refs(setup_chain_tool, setup_test_tools):
    """Test chain with multiple variable references in a single step."""
    session = setup_test_tools
    
    # Create a chain with multiple refs
    arguments = {
        'steps': [
            {
                'id': 'step1',
                'tool': 'test_echo',
                'args': {'message': 'Hello'}
            },
            {
                'id': 'step2',
                'tool': 'test_echo',
                'args': {'message': 'World'}
            },
            {
                'id': 'step3',
                'tool': 'test_echo',
                'args': {'message': '${step1} ${step2}!'}  # Multiple refs
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should succeed
    assert "CHAIN EXECUTION COMPLETED" in result
    assert "Hello World!" in result


@pytest.mark.integration
def test_chain_empty_steps(setup_chain_tool, setup_test_tools):
    """Test chain with empty steps list."""
    session = setup_test_tools
    
    # Create a chain with no steps
    arguments = {
        'steps': []
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should return error
    assert "Error" in result
    assert "No steps" in result


@pytest.mark.integration
def test_dag_validation_duplicate_ids(setup_chain_tool, setup_test_tools):
    """Test that DAG validation blocks duplicate step IDs."""
    session = setup_test_tools
    
    # Create a chain with duplicate IDs
    arguments = {
        'steps': [
            {
                'id': 'step1',
                'tool': 'test_echo',
                'args': {'message': 'First'}
            },
            {
                'id': 'step1',  # Duplicate!
                'tool': 'test_echo',
                'args': {'message': 'Second'}
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should fail with DAG validation error
    assert "DAG Validation Error" in result
    assert "Duplicate step ID" in result
    assert "step1" in result


@pytest.mark.integration
def test_chain_malformed_steps(setup_chain_tool, setup_test_tools):
    """Test chain with malformed step definitions."""
    session = setup_test_tools
    
    # Create a chain with missing required fields
    arguments = {
        'steps': [
            {
                'id': 'step1',
                # Missing 'tool' field
                'args': {'message': 'Test'}
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should return error
    assert "Error" in result
    assert "missing" in result.lower()


@pytest.mark.integration
def test_chain_complex_nested_refs(setup_chain_tool, setup_test_tools):
    """Test chain with nested object variable references."""
    session = setup_test_tools
    
    # Create a chain that tests multiple field access patterns
    arguments = {
        'steps': [
            {
                'id': 'data',
                'tool': 'test_multi_field',
                'args': {'name': 'Bob'}
            },
            {
                'id': 'greeting',
                'tool': 'test_echo',
                'args': {'message': '${data.greeting}'}
            },
            {
                'id': 'status',
                'tool': 'test_echo',
                'args': {'message': '${data.status}'}
            },
            {
                'id': 'combined',
                'tool': 'test_echo',
                'args': {'message': 'Greeting: ${greeting}, Status: ${status}'}
            }
        ]
    }
    
    # Execute the chain
    result = execute_tool(
        tool_name="system_run_chain",
        persona="default",
        arguments=arguments,
        meta_session=session,
        data_session=session
    )
    
    # Should succeed
    assert "CHAIN EXECUTION COMPLETED" in result
    assert "Hello Bob" in result
    assert "success" in result
