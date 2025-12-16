import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

"""
Pytest test suite for the Macro Registry and Macro Creator Meta-Tool.

This test validates:
1. MacroRegistry model creation and persistence
2. Meta-tool registration via add_macro_tool.py
3. Creation of macros via the meta-tool
4. Validation (must start with {% macro and end with {% endmacro %})
5. Macro loading via _load_macros function
6. End-to-end macro usage in SQL tools
"""

import pytest
from datetime import date
from sqlmodel import select

from add_macro_tool import register_macro_creator_tool
from models import CodeVault, ToolRegistry, MacroRegistry, SalesPerDay
from runtime import execute_tool, _load_macros, ToolNotFoundError


@pytest.fixture
def registered_meta_tool(db_session):
    """Fixture to register the macro creator meta-tool."""
    db_url = str(db_session.get_bind().url)
    success = register_macro_creator_tool(database_url=db_url)
    assert success, "Meta-tool registration failed"
    return db_session


@pytest.mark.integration
def test_macro_registry_model(db_session):
    """Test that MacroRegistry model can be created and persisted."""
    # Create a test macro
    macro = MacroRegistry(
        name="test_macro",
        description="Test macro for validation",
        template="{% macro test(x) %}{{ x }} * 2{% endmacro %}",
        is_active=True
    )
    
    db_session.add(macro)
    db_session.commit()
    
    # Query it back
    statement = select(MacroRegistry).where(MacroRegistry.name == "test_macro")
    retrieved_macro = db_session.exec(statement).first()
    
    assert retrieved_macro is not None
    assert retrieved_macro.name == "test_macro"
    assert retrieved_macro.description == "Test macro for validation"
    assert retrieved_macro.is_active == True


@pytest.mark.integration
def test_meta_tool_registration(registered_meta_tool):
    """Test that the macro creator meta-tool can be registered successfully."""
    session = registered_meta_tool
    
    # Verify meta-tool exists in database
    statement = select(ToolRegistry).where(
        ToolRegistry.tool_name == 'create_new_macro'
    )
    tool = session.exec(statement).first()
    
    assert tool is not None
    assert tool.description
    assert 'create_new_macro' == tool.tool_name


@pytest.mark.integration
def test_create_simple_macro(registered_meta_tool):
    """Test creating a simple macro via the meta-tool."""
    session = registered_meta_tool
    
    # Call the meta-tool to create a new macro
    result = execute_tool(
        'create_new_macro',
        'default',
        {
            'name': 'safe_div',
            'description': 'Safely divide two numbers, returning NULL if divisor is zero',
            'template': '{% macro safe_div(a, b) %}CASE WHEN {{ b }} = 0 THEN NULL ELSE {{ a }} / {{ b }} END{% endmacro %}'
        },
        session
    )
    
    assert 'Success' in result
    
    # Verify the new macro exists in MacroRegistry
    statement = select(MacroRegistry).where(
        MacroRegistry.name == 'safe_div'
    )
    new_macro = session.exec(statement).first()
    
    assert new_macro is not None
    assert new_macro.name == 'safe_div'
    assert new_macro.is_active == True


@pytest.mark.integration
def test_validation_missing_macro_tag(registered_meta_tool):
    """Test that templates without {% macro are rejected."""
    session = registered_meta_tool
    
    # Try to create a macro without proper start tag
    result = execute_tool(
        'create_new_macro',
        'default',
        {
            'name': 'invalid_macro',
            'description': 'Invalid macro',
            'template': 'CASE WHEN {{ b }} = 0 THEN NULL ELSE {{ a }} / {{ b }} END'
        },
        session
    )
    
    assert 'Error' in result
    assert 'macro' in result.lower()


@pytest.mark.integration
def test_validation_missing_endmacro_tag(registered_meta_tool):
    """Test that templates without {% endmacro %} are rejected."""
    session = registered_meta_tool
    
    # Try to create a macro without proper end tag
    result = execute_tool(
        'create_new_macro',
        'default',
        {
            'name': 'invalid_macro',
            'description': 'Invalid macro',
            'template': '{% macro test(x) %}{{ x }} * 2'
        },
        session
    )
    
    assert 'Error' in result
    assert 'endmacro' in result.lower()


@pytest.mark.integration
def test_load_macros_function(db_session):
    """Test that _load_macros function loads active macros correctly."""
    # Create test macros
    macro1 = MacroRegistry(
        name="macro1",
        description="First test macro",
        template="{% macro m1(x) %}{{ x }} + 1{% endmacro %}",
        is_active=True
    )
    
    macro2 = MacroRegistry(
        name="macro2",
        description="Second test macro",
        template="{% macro m2(x) %}{{ x }} * 2{% endmacro %}",
        is_active=True
    )
    
    # Inactive macro should not be loaded
    macro3 = MacroRegistry(
        name="macro3",
        description="Inactive test macro",
        template="{% macro m3(x) %}{{ x }} - 1{% endmacro %}",
        is_active=False
    )
    
    db_session.add(macro1)
    db_session.add(macro2)
    db_session.add(macro3)
    db_session.commit()
    
    # Load macros
    macro_block = _load_macros(db_session)
    
    # Verify active macros are included
    assert "macro m1" in macro_block
    assert "macro m2" in macro_block
    
    # Verify inactive macro is not included
    assert "macro m3" not in macro_block


@pytest.mark.integration
def test_load_macros_empty(db_session):
    """Test that _load_macros returns empty string when no macros exist."""
    macro_block = _load_macros(db_session)
    assert macro_block == ""


@pytest.mark.integration
def test_macro_idempotency(registered_meta_tool):
    """Test that registering the same macro twice is idempotent."""
    session = registered_meta_tool
    
    # Create a macro
    macro_args = {
        'name': 'test_idempotent',
        'description': 'Test macro for idempotency',
        'template': '{% macro test_idempotent(x) %}{{ x }}{% endmacro %}'
    }
    
    result1 = execute_tool('create_new_macro', 'default', macro_args, session)
    assert 'Success' in result1
    
    # Create the same macro again
    result2 = execute_tool('create_new_macro', 'default', macro_args, session)
    assert 'Success' in result2


@pytest.mark.integration
def test_validation_missing_required_fields(registered_meta_tool):
    """Test that missing required fields are rejected."""
    session = registered_meta_tool
    
    # Try to create a macro without name
    result = execute_tool(
        'create_new_macro',
        'default',
        {
            'description': 'Test macro',
            'template': '{% macro test(x) %}{{ x }}{% endmacro %}'
        },
        session
    )
    
    assert 'Error' in result
    assert 'name' in result


@pytest.mark.integration
def test_end_to_end_macro_in_sql_tool(registered_meta_tool):
    """Test that macros are automatically injected into SQL tools."""
    session = registered_meta_tool
    
    # First, register the SQL creator tool (needed for this test)
    from add_sql_creator_tool import register_sql_creator_tool
    db_url = str(session.get_bind().url)
    register_sql_creator_tool(database_url=db_url)
    
    # Create a macro
    macro_result = execute_tool(
        'create_new_macro',
        'default',
        {
            'name': 'safe_div',
            'description': 'Safely divide two numbers',
            'template': '{% macro safe_div(a, b) %}CASE WHEN {{ b }} = 0 THEN NULL ELSE {{ a }} / {{ b }} END{% endmacro %}'
        },
        session
    )
    assert 'Success' in macro_result
    
    # Create a SQL tool that uses the macro
    tool_result = execute_tool(
        'create_new_sql_tool',
        'default',
        {
            'tool_name': 'get_sales_ratio',
            'description': 'Get sales ratio using safe division',
            'sql_query': 'SELECT store_name, department, {{ safe_div("sales_amount", "100") }} as ratio FROM sales_per_day',
            'parameters': {}
        },
        session
    )
    assert 'Success' in tool_result
    
    # Add some test data
    test_sale = SalesPerDay(
        business_date=date(2024, 1, 1),
        store_name="Test Store",
        department="Electronics",
        sales_amount=1000.0
    )
    session.add(test_sale)
    session.commit()
    
    # Execute the tool (this should work because macro is prepended)
    # Note: We need to pass both meta_session and data_session
    sales_result = execute_tool(
        'get_sales_ratio',
        'default',
        {},
        session,
        session  # Using same session for both in test
    )
    
    # Verify the result is not None and contains data
    assert sales_result is not None
    assert len(sales_result) > 0
