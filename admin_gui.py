"""
Admin GUI for Chameleon MCP Server using Streamlit.

This module provides a web-based admin interface for managing tools, code blobs,
and personas in the Chameleon MCP server database.
"""

import os
import hashlib
import json
import streamlit as st
from sqlalchemy import func
from sqlmodel import Session, select, create_engine
from models import CodeVault, ToolRegistry, get_engine


# Database connection setup
def get_db_engine():
    """
    Get database engine using environment variable or default.
    
    Returns:
        SQLModel engine instance
    """
    db_url = os.environ.get('CHAMELEON_DB_URL', 'sqlite:///chameleon.db')
    return get_engine(db_url)


def compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


# Dashboard Page
def show_dashboard():
    """Display dashboard with metrics."""
    st.header("📊 Dashboard")
    
    engine = get_db_engine()
    with Session(engine) as session:
        # Total Tools
        total_tools = session.exec(
            select(func.count(ToolRegistry.tool_name))
        ).first()
        
        # Total Code Blobs
        total_blobs = session.exec(
            select(func.count(CodeVault.hash))
        ).first()
        
        # Count of Unique Personas
        unique_personas = session.exec(
            select(func.count(func.distinct(ToolRegistry.target_persona)))
        ).first()
        
        # Display metrics in columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Tools", total_tools or 0)
        
        with col2:
            st.metric("Total Code Blobs", total_blobs or 0)
        
        with col3:
            st.metric("Unique Personas", unique_personas or 0)


# Tool Registry Page
def show_tool_registry():
    """Display tool registry with filtering and management."""
    st.header("🔧 Tool Registry")
    
    engine = get_db_engine()
    with Session(engine) as session:
        # Get all unique personas for the dropdown
        personas_statement = select(ToolRegistry.target_persona).distinct()
        personas = session.exec(personas_statement).all()
        
        if not personas:
            st.info("No tools found in the registry. Add some tools first!")
            return
        
        # Persona filter dropdown
        selected_persona = st.selectbox(
            "Filter by Persona:",
            options=personas,
            index=0
        )
        
        # Query tools for selected persona
        tools_statement = select(ToolRegistry).where(
            ToolRegistry.target_persona == selected_persona
        )
        tools = session.exec(tools_statement).all()
        
        if not tools:
            st.info(f"No tools found for persona '{selected_persona}'")
            return
        
        st.write(f"**{len(tools)} tool(s) found for persona '{selected_persona}'**")
        
        # Display each tool in an expander
        for tool in tools:
            with st.expander(f"🛠️ {tool.tool_name}"):
                st.write("**Description:**")
                st.write(tool.description)
                
                st.write("**Python Code:**")
                # Fetch python code from CodeVault
                code_statement = select(CodeVault).where(
                    CodeVault.hash == tool.active_hash_ref
                )
                code_vault = session.exec(code_statement).first()
                
                if code_vault:
                    st.code(code_vault.python_blob, language="python")
                else:
                    st.error(f"Code not found for hash: {tool.active_hash_ref}")
                
                st.write("**Input Schema:**")
                st.json(tool.input_schema)
                
                # Delete button
                if st.button(f"🗑️ Delete '{tool.tool_name}'", key=f"delete_{tool.tool_name}_{tool.target_persona}"):
                    try:
                        session.delete(tool)
                        session.commit()
                        st.success(f"Tool '{tool.tool_name}' deleted successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting tool: {e}")
                        session.rollback()


# Add New Tool Page
def show_add_new_tool():
    """Display form for adding new tools."""
    st.header("➕ Add New Tool")
    
    engine = get_db_engine()
    
    # Form for adding a new tool
    with st.form("add_tool_form"):
        tool_name = st.text_input("Tool Name *", placeholder="e.g., greet, calculate, etc.")
        target_persona = st.text_input("Target Persona *", placeholder="e.g., default, assistant, etc.")
        description = st.text_area("Description *", placeholder="Describe what this tool does...")
        
        st.write("**Python Code Editor:**")
        code = st.text_area(
            "Python Logic *",
            placeholder="# Your Python code here\n# Access arguments with: arguments.get('param_name')\n# Set result with: result = your_value",
            height=200
        )
        
        st.write("**JSON Schema Editor:**")
        schema_text = st.text_area(
            "Input Schema (JSON) *",
            value='{}',
            placeholder='{"type": "object", "properties": {...}}',
            height=150
        )
        
        submitted = st.form_submit_button("💾 Save Tool")
        
        if submitted:
            # Validation
            if not tool_name or not target_persona or not description or not code:
                st.error("Please fill in all required fields (marked with *)")
                return
            
            # Validate JSON schema
            try:
                input_schema = json.loads(schema_text)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON schema: {e}")
                return
            
            try:
                with Session(engine) as session:
                    # Compute SHA-256 hash of the code
                    code_hash = compute_hash(code)
                    
                    # Check if hash exists in CodeVault (idempotency)
                    code_statement = select(CodeVault).where(CodeVault.hash == code_hash)
                    existing_code = session.exec(code_statement).first()
                    
                    if not existing_code:
                        # Insert new code into CodeVault
                        new_code = CodeVault(hash=code_hash, python_blob=code)
                        session.add(new_code)
                        st.info(f"New code blob added with hash: {code_hash[:16]}...")
                    else:
                        st.info(f"Code already exists in vault with hash: {code_hash[:16]}...")
                    
                    # Check if tool with this name AND persona exists (upsert logic)
                    tool_statement = select(ToolRegistry).where(
                        ToolRegistry.tool_name == tool_name,
                        ToolRegistry.target_persona == target_persona
                    )
                    existing_tool = session.exec(tool_statement).first()
                    
                    if existing_tool:
                        # Update existing tool
                        existing_tool.description = description
                        existing_tool.input_schema = input_schema
                        existing_tool.active_hash_ref = code_hash
                        st.success(f"Tool '{tool_name}' for persona '{target_persona}' updated successfully!")
                    else:
                        # Insert new tool
                        new_tool = ToolRegistry(
                            tool_name=tool_name,
                            target_persona=target_persona,
                            description=description,
                            input_schema=input_schema,
                            active_hash_ref=code_hash
                        )
                        session.add(new_tool)
                        st.success(f"Tool '{tool_name}' for persona '{target_persona}' added successfully!")
                    
                    # Commit transaction
                    session.commit()
                    
            except Exception as e:
                st.error(f"Error saving tool: {e}")
                session.rollback()


# Main App
def main():
    """Main application entry point."""
    st.set_page_config(
        page_title="Chameleon Admin",
        page_icon="🦎",
        layout="wide"
    )
    
    st.title("🦎 Chameleon MCP Server - Admin GUI")
    
    # Sidebar navigation
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Go to:",
            ["Dashboard", "Tool Registry", "Add New Tool"]
        )
        
        st.divider()
        st.caption("Database Connection")
        db_url = os.environ.get('CHAMELEON_DB_URL', 'sqlite:///chameleon.db')
        st.caption(f"📁 {db_url}")
    
    # Route to appropriate page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Tool Registry":
        show_tool_registry()
    elif page == "Add New Tool":
        show_add_new_tool()


if __name__ == "__main__":
    main()
