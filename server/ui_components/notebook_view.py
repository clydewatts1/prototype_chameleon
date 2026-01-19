"""
UI component for displaying and managing AgentNotebook entries.

This module provides a Streamlit-based interface for viewing and editing
the agent's long-term memory (Agent Notebook).
"""

import streamlit as st
from datetime import datetime, timezone
from sqlmodel import Session, select
from models import AgentNotebook, NotebookHistory


def show_notebook_view(engine):
    """
    Display the Agent Notebook "Brain" tab.
    
    Features:
    - Domain filter in sidebar
    - Editor for notebook entries
    - History viewer for each entry
    
    Args:
        engine: SQLModel engine instance for database connection
    """
    st.header("🧠 Agent Notebook - Long-Term Memory")
    
    with Session(engine) as session:
        # Get all unique domains
        statement = select(AgentNotebook.domain).distinct()
        all_domains = session.exec(statement).all()
        
        if not all_domains:
            st.info("📝 No memory entries found yet. The agent will create entries automatically as it learns.")
            return
        
        # Sidebar filter for domain selection
        st.sidebar.subheader("🔍 Filter by Domain")
        selected_domain = st.sidebar.selectbox(
            "Select Domain:",
            options=["All"] + sorted(all_domains),
            help="Filter notebook entries by domain (namespace)"
        )
        
        # Query notebook entries
        if selected_domain == "All":
            statement = select(AgentNotebook).where(AgentNotebook.is_active == True)
        else:
            statement = select(AgentNotebook).where(
                AgentNotebook.domain == selected_domain,
                AgentNotebook.is_active == True
            )
        
        entries = session.exec(statement).all()
        
        if not entries:
            st.warning(f"No active entries found for domain: {selected_domain}")
            return
        
        st.write(f"Found **{len(entries)}** active memory entries")
        st.divider()
        
        # Display entries grouped by domain
        entries_by_domain = {}
        for entry in entries:
            if entry.domain not in entries_by_domain:
                entries_by_domain[entry.domain] = []
            entries_by_domain[entry.domain].append(entry)
        
        # Display each domain
        for domain, domain_entries in sorted(entries_by_domain.items()):
            with st.expander(f"📁 **{domain}** ({len(domain_entries)} entries)", expanded=True):
                for entry in sorted(domain_entries, key=lambda e: e.key):
                    # Create a container for each entry
                    entry_container = st.container()
                    
                    with entry_container:
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**Key:** `{entry.key}`")
                        
                        with col2:
                            # Handle potential null updated_at
                            if entry.updated_at:
                                st.caption(f"Updated: {entry.updated_at.strftime('%Y-%m-%d %H:%M')}")
                            else:
                                st.caption("Updated: N/A")
                            st.caption(f"By: {entry.updated_by}")
                        
                        # Editable value field
                        new_value = st.text_area(
                            "Value:",
                            value=entry.value,
                            key=f"value_{domain}_{entry.key}",
                            height=100
                        )
                        
                        # Save button
                        col1, col2, col3 = st.columns([1, 1, 4])
                        with col1:
                            if st.button("💾 Save", key=f"save_{domain}_{entry.key}"):
                                try:
                                    # Save old value to history
                                    if new_value != entry.value:
                                        history_entry = NotebookHistory(
                                            domain=entry.domain,
                                            key=entry.key,
                                            old_value=entry.value,
                                            new_value=new_value,
                                            changed_by="user_via_ui"
                                        )
                                        session.add(history_entry)
                                        
                                        # Update the entry
                                        entry.value = new_value
                                        entry.updated_at = datetime.now(timezone.utc)
                                        entry.updated_by = "user_via_ui"
                                        
                                        session.commit()
                                        st.success(f"✅ Saved changes to `{entry.key}`")
                                        st.rerun()
                                    else:
                                        st.info("No changes detected")
                                except Exception as e:
                                    session.rollback()
                                    st.error(f"Error saving: {e}")
                        
                        with col2:
                            if st.button("🗑️ Delete", key=f"delete_{domain}_{entry.key}"):
                                try:
                                    # Soft delete
                                    entry.is_active = False
                                    entry.updated_at = datetime.now(timezone.utc)
                                    entry.updated_by = "user_via_ui"
                                    session.commit()
                                    st.success(f"✅ Deleted `{entry.key}`")
                                    st.rerun()
                                except Exception as e:
                                    session.rollback()
                                    st.error(f"Error deleting: {e}")
                        
                        # History viewer
                        with st.expander(f"📜 History for `{entry.key}`"):
                            history_statement = select(NotebookHistory).where(
                                NotebookHistory.domain == entry.domain,
                                NotebookHistory.key == entry.key
                            ).order_by(NotebookHistory.changed_at.desc())
                            
                            history_entries = session.exec(history_statement).all()
                            
                            if history_entries:
                                st.write(f"**{len(history_entries)}** historical changes:")
                                for hist in history_entries:
                                    st.markdown(f"**{hist.changed_at.strftime('%Y-%m-%d %H:%M:%S')}** by `{hist.changed_by}`")
                                    col_old, col_new = st.columns(2)
                                    with col_old:
                                        st.caption("Old Value:")
                                        st.code(hist.old_value or "(empty)", language=None)
                                    with col_new:
                                        st.caption("New Value:")
                                        st.code(hist.new_value, language=None)
                                    st.divider()
                            else:
                                st.info("No history yet for this entry")
                        
                        st.divider()
        
        # Add new entry section
        st.subheader("➕ Add New Memory Entry")
        with st.form("add_new_entry"):
            col1, col2 = st.columns(2)
            with col1:
                new_domain = st.text_input(
                    "Domain:",
                    placeholder="e.g., user_prefs, project_alpha",
                    help="Namespace for grouping related memories"
                )
            with col2:
                new_key = st.text_input(
                    "Key:",
                    placeholder="e.g., theme, language",
                    help="Unique key within the domain"
                )
            
            new_value_input = st.text_area(
                "Value:",
                placeholder="Enter the memory value...",
                height=100
            )
            
            submitted = st.form_submit_button("➕ Add Entry")
            
            if submitted:
                if not new_domain or not new_key or not new_value_input:
                    st.error("Please fill in all fields")
                else:
                    try:
                        # Check if entry already exists
                        check_statement = select(AgentNotebook).where(
                            AgentNotebook.domain == new_domain,
                            AgentNotebook.key == new_key
                        )
                        existing = session.exec(check_statement).first()
                        
                        if existing:
                            if existing.is_active:
                                st.error(f"Entry with domain='{new_domain}' and key='{new_key}' already exists")
                            else:
                                # Reactivate soft-deleted entry
                                existing.is_active = True
                                existing.value = new_value_input
                                existing.updated_at = datetime.now(timezone.utc)
                                existing.updated_by = "user_via_ui"
                                session.commit()
                                st.success(f"✅ Reactivated and updated entry `{new_key}` in domain `{new_domain}`")
                                st.rerun()
                        else:
                            # Create new entry
                            new_entry = AgentNotebook(
                                domain=new_domain,
                                key=new_key,
                                value=new_value_input,
                                updated_by="user_via_ui"
                            )
                            session.add(new_entry)
                            session.commit()
                            st.success(f"✅ Added new entry `{new_key}` to domain `{new_domain}`")
                            st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Error adding entry: {e}")
