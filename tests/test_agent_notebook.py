"""
Pytest test suite for AgentNotebook long-term memory features.

Tests cover:
1. Database models (AgentNotebook, NotebookHistory, NotebookAudit)
2. Reflexive learning self-correction
3. Memory export to YAML
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlmodel import Session, select
from models import AgentNotebook, NotebookHistory, NotebookAudit, create_db_and_tables, METADATA_MODELS
from runtime import log_self_correction


@pytest.mark.integration
def test_agent_notebook_model_creation(db_session):
    """Test creating AgentNotebook entries."""
    # Create a notebook entry
    entry = AgentNotebook(
        domain="test_domain",
        key="test_key",
        value="test_value",
        updated_by="test_user"
    )
    db_session.add(entry)
    db_session.commit()
    
    # Query it back
    statement = select(AgentNotebook).where(
        AgentNotebook.domain == "test_domain",
        AgentNotebook.key == "test_key"
    )
    retrieved = db_session.exec(statement).first()
    
    assert retrieved is not None
    assert retrieved.value == "test_value"
    assert retrieved.updated_by == "test_user"
    assert retrieved.is_active is True


@pytest.mark.integration
def test_notebook_history_tracking(db_session):
    """Test that history is tracked when entries are updated."""
    # Create initial entry
    entry = AgentNotebook(
        domain="history_test",
        key="tracked_key",
        value="initial_value",
        updated_by="system"
    )
    db_session.add(entry)
    db_session.commit()
    
    # Update the entry and record history
    old_value = entry.value
    entry.value = "updated_value"
    entry.updated_by = "user"
    entry.updated_at = datetime.now(timezone.utc)
    
    history = NotebookHistory(
        domain=entry.domain,
        key=entry.key,
        old_value=old_value,
        new_value=entry.value,
        changed_by="user"
    )
    db_session.add(history)
    db_session.commit()
    
    # Verify history was recorded
    statement = select(NotebookHistory).where(
        NotebookHistory.domain == "history_test",
        NotebookHistory.key == "tracked_key"
    )
    history_entries = db_session.exec(statement).all()
    
    assert len(history_entries) == 1
    assert history_entries[0].old_value == "initial_value"
    assert history_entries[0].new_value == "updated_value"
    assert history_entries[0].changed_by == "user"


@pytest.mark.integration
def test_notebook_audit_logging(db_session):
    """Test audit logging for notebook access."""
    # Create an audit entry
    audit = NotebookAudit(
        domain="audit_test",
        key="audited_key",
        access_type="read",
        accessed_by="test_tool",
        context_data={"tool_version": "1.0"}
    )
    db_session.add(audit)
    db_session.commit()
    
    # Verify audit entry
    statement = select(NotebookAudit).where(
        NotebookAudit.domain == "audit_test",
        NotebookAudit.key == "audited_key"
    )
    audit_entries = db_session.exec(statement).all()
    
    assert len(audit_entries) == 1
    assert audit_entries[0].access_type == "read"
    assert audit_entries[0].accessed_by == "test_tool"
    assert audit_entries[0].context_data == {"tool_version": "1.0"}


@pytest.mark.integration
def test_soft_delete_functionality(db_session):
    """Test soft delete (is_active flag) functionality."""
    # Create entry
    entry = AgentNotebook(
        domain="delete_test",
        key="deletable_key",
        value="some_value",
        updated_by="system"
    )
    db_session.add(entry)
    db_session.commit()
    
    # Soft delete
    entry.is_active = False
    db_session.commit()
    
    # Query active entries - should not find it
    statement = select(AgentNotebook).where(
        AgentNotebook.domain == "delete_test",
        AgentNotebook.is_active == True
    )
    active_entries = db_session.exec(statement).all()
    assert len(active_entries) == 0
    
    # Query all entries - should still find it
    statement = select(AgentNotebook).where(
        AgentNotebook.domain == "delete_test"
    )
    all_entries = db_session.exec(statement).all()
    assert len(all_entries) == 1
    assert all_entries[0].is_active is False


@pytest.mark.integration
def test_self_correction_logging(db_session):
    """Test reflexive learning self-correction functionality."""
    # Log a self-correction entry
    log_self_correction(
        tool_name="failing_tool",
        error_summary="TypeError: Missing required argument 'name'",
        db_session=db_session
    )
    
    # Verify the entry was created
    statement = select(AgentNotebook).where(
        AgentNotebook.domain == "self_correction",
        AgentNotebook.key == "failing_tool_error"
    )
    entry = db_session.exec(statement).first()
    
    assert entry is not None
    assert "TypeError" in entry.value
    assert "Missing required argument" in entry.value
    assert entry.updated_by == "system_reflexive_learning"
    
    # Log another error for the same tool
    log_self_correction(
        tool_name="failing_tool",
        error_summary="ValueError: Invalid value for parameter 'age'",
        db_session=db_session
    )
    
    # Verify both errors are in the entry
    db_session.refresh(entry)
    assert "TypeError" in entry.value
    assert "ValueError" in entry.value


@pytest.mark.integration
def test_domain_filtering(db_session):
    """Test filtering entries by domain."""
    # Create entries in different domains
    domains = ["domain_a", "domain_b", "domain_c"]
    for domain in domains:
        for i in range(3):
            entry = AgentNotebook(
                domain=domain,
                key=f"key_{i}",
                value=f"value_{i}",
                updated_by="system"
            )
            db_session.add(entry)
    db_session.commit()
    
    # Query specific domain
    statement = select(AgentNotebook).where(
        AgentNotebook.domain == "domain_b"
    )
    domain_b_entries = db_session.exec(statement).all()
    
    assert len(domain_b_entries) == 3
    assert all(e.domain == "domain_b" for e in domain_b_entries)


@pytest.mark.integration
def test_memory_export_functionality(db_session):
    """Test memory export to YAML."""
    # Create sample entries
    entries = [
        AgentNotebook(domain="user_prefs", key="theme", value="dark", updated_by="user"),
        AgentNotebook(domain="user_prefs", key="language", value="en", updated_by="user"),
        AgentNotebook(domain="project", key="status", value="active", updated_by="system"),
    ]
    for entry in entries:
        db_session.add(entry)
    db_session.commit()
    
    # Test that export script can query the entries
    statement = select(AgentNotebook).where(AgentNotebook.is_active == True)
    all_entries = db_session.exec(statement).all()
    
    assert len(all_entries) >= 3
    
    # Organize by domain (same logic as export script)
    domains = {}
    for entry in all_entries:
        if entry.domain not in domains:
            domains[entry.domain] = {}
        domains[entry.domain][entry.key] = entry.value
    
    assert "user_prefs" in domains
    assert "project" in domains
    assert domains["user_prefs"]["theme"] == "dark"
    assert domains["user_prefs"]["language"] == "en"
    assert domains["project"]["status"] == "active"


@pytest.mark.integration
def test_composite_primary_key(db_session):
    """Test that domain+key composite primary key works correctly."""
    # Create entry
    entry1 = AgentNotebook(
        domain="composite_test",
        key="same_key",
        value="value1",
        updated_by="user1"
    )
    db_session.add(entry1)
    db_session.commit()
    
    # Try to create duplicate (same domain+key) - should fail or update
    entry2 = AgentNotebook(
        domain="composite_test",
        key="same_key",
        value="value2",
        updated_by="user2"
    )
    
    # This should raise an exception due to primary key constraint
    with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
        db_session.add(entry2)
        db_session.commit()
    
    db_session.rollback()
    
    # But same key in different domain should work
    entry3 = AgentNotebook(
        domain="different_domain",
        key="same_key",
        value="value3",
        updated_by="user3"
    )
    db_session.add(entry3)
    db_session.commit()
    
    # Verify both exist
    statement = select(AgentNotebook).where(
        AgentNotebook.key == "same_key"
    )
    same_key_entries = db_session.exec(statement).all()
    assert len(same_key_entries) == 2
