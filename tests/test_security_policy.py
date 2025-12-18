"""
Pytest test suite for SecurityPolicy model and policy-based AST validation.

This test validates:
1. SecurityPolicy model creation and storage
2. Policy-based validate_code_structure with allow/deny rules
3. Blacklist precedence over whitelist
4. Loading policies from database
5. Backward compatibility with hardcoded defaults
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from sqlmodel import select, Session
from models import SecurityPolicy, get_engine, create_db_and_tables
from common.security import validate_code_structure, SecurityError, load_security_policies


@pytest.fixture
def security_db_session():
    """Fixture to create a temporary database for security policy tests."""
    engine = get_engine("sqlite:///:memory:")
    create_db_and_tables(engine)
    
    with Session(engine) as session:
        yield session


@pytest.mark.security
def test_security_policy_model_creation(security_db_session):
    """Test that SecurityPolicy model can be created and stored."""
    session = security_db_session
    
    policy = SecurityPolicy(
        rule_type="deny",
        category="module",
        pattern="subprocess",
        description="Block subprocess module for security",
        is_active=True
    )
    session.add(policy)
    session.commit()
    
    # Verify it was saved
    statement = select(SecurityPolicy).where(SecurityPolicy.pattern == "subprocess")
    result = session.exec(statement).first()
    
    assert result is not None
    assert result.rule_type == "deny"
    assert result.category == "module"
    assert result.pattern == "subprocess"
    assert result.is_active is True


@pytest.mark.security
def test_policy_based_module_deny(security_db_session):
    """Test that deny policy blocks module imports."""
    session = security_db_session
    
    # Add deny policy for subprocess
    policy = SecurityPolicy(
        rule_type="deny",
        category="module",
        pattern="subprocess",
        is_active=True
    )
    session.add(policy)
    session.commit()
    
    # Load policies and test
    policies = load_security_policies(session)
    
    code_with_subprocess = """
import subprocess

class MyTool:
    pass
"""
    
    with pytest.raises(SecurityError) as exc_info:
        validate_code_structure(code_with_subprocess, policies=policies)
    
    assert "subprocess" in str(exc_info.value)
    assert "blocked" in str(exc_info.value).lower()


@pytest.mark.security
def test_policy_based_function_deny(security_db_session):
    """Test that deny policy blocks function calls."""
    session = security_db_session
    
    # Add deny policy for eval
    policy = SecurityPolicy(
        rule_type="deny",
        category="function",
        pattern="eval",
        is_active=True
    )
    session.add(policy)
    session.commit()
    
    # Load policies and test
    policies = load_security_policies(session)
    
    code_with_eval = """
class MyTool:
    def run(self, args):
        result = eval(args['code'])
        return result
"""
    
    with pytest.raises(SecurityError) as exc_info:
        validate_code_structure(code_with_eval, policies=policies)
    
    assert "eval" in str(exc_info.value)
    assert "blocked" in str(exc_info.value).lower()


@pytest.mark.security
def test_policy_based_attribute_deny(security_db_session):
    """Test that deny policy blocks attribute calls."""
    session = security_db_session
    
    # Add deny policy for os.system
    policy = SecurityPolicy(
        rule_type="deny",
        category="attribute",
        pattern="os.system",
        is_active=True
    )
    session.add(policy)
    session.commit()
    
    # Load policies and test
    policies = load_security_policies(session)
    
    code_with_os_system = """
import os

class MyTool:
    def run(self, args):
        os.system('ls')
        return "done"
"""
    
    with pytest.raises(SecurityError) as exc_info:
        validate_code_structure(code_with_os_system, policies=policies)
    
    assert "os.system" in str(exc_info.value)
    assert "blocked" in str(exc_info.value).lower()


@pytest.mark.security
def test_allow_policy_permits_import(security_db_session):
    """Test that allow policy permits module imports."""
    session = security_db_session
    
    # Add allow policy for requests module
    policy = SecurityPolicy(
        rule_type="allow",
        category="module",
        pattern="requests",
        is_active=True
    )
    session.add(policy)
    session.commit()
    
    # Load policies and test
    policies = load_security_policies(session)
    
    code_with_requests = """
import requests

class MyTool:
    def run(self, args):
        return "ok"
"""
    
    # Should not raise error
    validate_code_structure(code_with_requests, policies=policies)


@pytest.mark.security
def test_deny_overrides_allow_precedence(security_db_session):
    """Test that deny policy always overrides allow policy (blacklist precedence)."""
    session = security_db_session
    
    # Add both allow and deny for the same module
    allow_policy = SecurityPolicy(
        rule_type="allow",
        category="module",
        pattern="subprocess",
        is_active=True
    )
    deny_policy = SecurityPolicy(
        rule_type="deny",
        category="module",
        pattern="subprocess",
        is_active=True
    )
    session.add(allow_policy)
    session.add(deny_policy)
    session.commit()
    
    # Load policies and test
    policies = load_security_policies(session)
    
    code_with_subprocess = """
import subprocess

class MyTool:
    pass
"""
    
    # Deny should take precedence - should raise error
    with pytest.raises(SecurityError) as exc_info:
        validate_code_structure(code_with_subprocess, policies=policies)
    
    assert "subprocess" in str(exc_info.value)
    assert "blocked" in str(exc_info.value).lower()


@pytest.mark.security
def test_inactive_policy_ignored(security_db_session):
    """Test that inactive policies are not enforced."""
    session = security_db_session
    
    # Add inactive deny policy for os module
    policy = SecurityPolicy(
        rule_type="deny",
        category="module",
        pattern="os",
        is_active=False  # Inactive
    )
    session.add(policy)
    session.commit()
    
    # Load policies and test
    policies = load_security_policies(session)
    
    code_with_os = """
import os

class MyTool:
    def run(self, args):
        return "ok"
"""
    
    # Should not raise error because policy is inactive
    validate_code_structure(code_with_os, policies=policies)


@pytest.mark.security
def test_backward_compatibility_with_no_policies():
    """Test that validate_code_structure still works without policies (backward compatibility)."""
    # Test with hardcoded defaults (no policies parameter)
    
    code_with_subprocess = """
import subprocess

class MyTool:
    pass
"""
    
    # Should still block subprocess with hardcoded defaults
    with pytest.raises(SecurityError) as exc_info:
        validate_code_structure(code_with_subprocess, policies=None)
    
    assert "subprocess" in str(exc_info.value)
    
    # Test with eval
    code_with_eval = """
class MyTool:
    def run(self, args):
        eval("1+1")
"""
    
    with pytest.raises(SecurityError) as exc_info:
        validate_code_structure(code_with_eval, policies=None)
    
    assert "eval" in str(exc_info.value)


@pytest.mark.security
def test_safe_code_passes_validation(security_db_session):
    """Test that safe code passes validation with policies."""
    session = security_db_session
    
    # Add some deny policies
    for pattern in ["subprocess", "eval", "exec"]:
        policy = SecurityPolicy(
            rule_type="deny",
            category="module" if pattern == "subprocess" else "function",
            pattern=pattern,
            is_active=True
        )
        session.add(policy)
    session.commit()
    
    # Load policies
    policies = load_security_policies(session)
    
    safe_code = """
import json
from typing import Dict, Any

class SafeTool:
    def run(self, args: Dict[str, Any]):
        data = json.dumps(args)
        return data
"""
    
    # Should not raise error
    validate_code_structure(safe_code, policies=policies)


@pytest.mark.security
def test_load_security_policies_returns_correct_format(security_db_session):
    """Test that load_security_policies returns correct data format."""
    session = security_db_session
    
    # Add multiple policies
    policies_data = [
        {"rule_type": "deny", "category": "module", "pattern": "subprocess", "description": "Block subprocess"},
        {"rule_type": "deny", "category": "function", "pattern": "eval", "description": "Block eval"},
        {"rule_type": "allow", "category": "module", "pattern": "requests", "description": "Allow requests"},
    ]
    
    for data in policies_data:
        policy = SecurityPolicy(**data, is_active=True)
        session.add(policy)
    session.commit()
    
    # Load policies
    loaded = load_security_policies(session)
    
    assert len(loaded) == 3
    assert all(isinstance(p, dict) for p in loaded)
    assert all('rule_type' in p for p in loaded)
    assert all('category' in p for p in loaded)
    assert all('pattern' in p for p in loaded)
    assert all('is_active' in p for p in loaded)
    
    # Verify specific policies
    deny_modules = [p for p in loaded if p['rule_type'] == 'deny' and p['category'] == 'module']
    assert len(deny_modules) == 1
    assert deny_modules[0]['pattern'] == 'subprocess'


@pytest.mark.security
def test_multiple_deny_rules_all_enforced(security_db_session):
    """Test that multiple deny rules are all enforced."""
    session = security_db_session
    
    # Add multiple deny policies
    for pattern in ["subprocess", "sys", "importlib"]:
        policy = SecurityPolicy(
            rule_type="deny",
            category="module",
            pattern=pattern,
            is_active=True
        )
        session.add(policy)
    session.commit()
    
    # Load policies
    policies = load_security_policies(session)
    
    # Test each denied module
    for module in ["subprocess", "sys", "importlib"]:
        code = f"""
import {module}

class MyTool:
    pass
"""
        with pytest.raises(SecurityError) as exc_info:
            validate_code_structure(code, policies=policies)
        
        assert module in str(exc_info.value)


@pytest.mark.security
def test_empty_policy_list_allows_everything():
    """Test that empty policy list (no deny rules) allows all imports."""
    # Empty policies list should not block anything
    policies = []
    
    code_with_os = """
import os

class MyTool:
    def run(self, args):
        return "ok"
"""
    
    # Should not raise error with empty policy list
    validate_code_structure(code_with_os, policies=policies)


@pytest.mark.security
def test_policy_description_field(security_db_session):
    """Test that policy description field is optional and stored correctly."""
    session = security_db_session
    
    # Add policy with description
    policy_with_desc = SecurityPolicy(
        rule_type="deny",
        category="module",
        pattern="pickle",
        description="Pickle module is unsafe for untrusted data",
        is_active=True
    )
    
    # Add policy without description
    policy_no_desc = SecurityPolicy(
        rule_type="deny",
        category="module",
        pattern="marshal",
        is_active=True
    )
    
    session.add(policy_with_desc)
    session.add(policy_no_desc)
    session.commit()
    
    # Load and verify
    policies = load_security_policies(session)
    
    pickle_policy = next(p for p in policies if p['pattern'] == 'pickle')
    marshal_policy = next(p for p in policies if p['pattern'] == 'marshal')
    
    assert pickle_policy['description'] == "Pickle module is unsafe for untrusted data"
    assert marshal_policy['description'] is None
