import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from common.utils import compute_hash as _compute_hash
"""
Pytest test suite for seed_db.py to validate database seeding.
"""

import pytest
from sqlmodel import Session, select
from models import ToolRegistry, ResourceRegistry, PromptRegistry, CodeVault
from seed_db import seed_database


@pytest.mark.integration
def test_seed_database(db_session):
    """Test the seeding process and validate inserted data."""
    # Get the database URL from the session's engine
    db_url = str(db_session.get_bind().url)
    
    # Run the seeding function
    seed_database(db_url)
    
    # Query and validate data using the same session
    # Check tools
    tools = db_session.exec(select(ToolRegistry)).all()
    expected_tools = ["greet", "add", "multiply", "uppercase"]
    found_tools = [t.tool_name for t in tools]
    
    for tool in expected_tools:
        assert tool in found_tools, f"Tool '{tool}' not found in database"
    
    # Check resources
    resources = db_session.exec(select(ResourceRegistry)).all()
    expected_resources = ["welcome_message", "server_time"]
    found_resources = [r.name for r in resources]
    
    for resource in expected_resources:
        assert resource in found_resources, f"Resource '{resource}' not found in database"
    
    # Check prompts
    prompts = db_session.exec(select(PromptRegistry)).all()
    assert any(p.name == "review_code" for p in prompts), "Prompt 'review_code' not found"
    
    # Check code vaults
    vaults = db_session.exec(select(CodeVault)).all()
    assert len(vaults) > 0, "No code vaults found in database"


@pytest.mark.integration
def test_seed_database_tools_have_descriptions(db_session):
    """Test that all seeded tools have non-empty descriptions."""
    db_url = str(db_session.get_bind().url)
    seed_database(db_url)
    
    tools = db_session.exec(select(ToolRegistry)).all()
    assert len(tools) > 0, "No tools found in database"
    
    for tool in tools:
        assert tool.description, f"Tool '{tool.tool_name}' has no description"
        assert len(tool.description) > 0, f"Tool '{tool.tool_name}' has empty description"


@pytest.mark.integration
def test_seed_database_tools_have_valid_hash_refs(db_session):
    """Test that all seeded tools have valid hash references to CodeVault."""
    db_url = str(db_session.get_bind().url)
    seed_database(db_url)
    
    tools = db_session.exec(select(ToolRegistry)).all()
    assert len(tools) > 0, "No tools found in database"
    
    for tool in tools:
        # Verify hash reference exists in CodeVault
        code = db_session.exec(
            select(CodeVault).where(CodeVault.hash == tool.active_hash_ref)
        ).first()
        assert code is not None, f"Tool '{tool.tool_name}' has invalid hash reference"
        assert code.code_blob, f"Code for tool '{tool.tool_name}' is empty"
