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
from config import load_config
from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry, get_engine


# Database connection setup
def get_db_engine():
    """
    Get database engine using config or environment variable.
    
    Priority:
    1. CHAMELEON_DB_URL environment variable (for backward compatibility)
    2. Configuration from ~/.chameleon/config/config.yaml
    3. Default: sqlite:///chameleon.db
    
    Returns:
        SQLModel engine instance
    """
    # Check environment variable first (backward compatibility)
    db_url = os.environ.get('CHAMELEON_DB_URL')
    
    # If not set, load from config
    if not db_url:
        config = load_config()
        db_url = config['database']['url']
    
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
        
        # Total Resources
        total_resources = session.exec(
            select(func.count(ResourceRegistry.uri_schema))
        ).first()
        
        # Total Prompts
        total_prompts = session.exec(
            select(func.count(PromptRegistry.name))
        ).first()
        
        # Count of Unique Personas
        unique_personas = session.exec(
            select(func.count(func.distinct(ToolRegistry.target_persona)))
        ).first()
        
        # Display metrics in columns
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Tools", total_tools or 0)
        
        with col2:
            st.metric("Total Resources", total_resources or 0)
        
        with col3:
            st.metric("Total Prompts", total_prompts or 0)
        
        with col4:
            st.metric("Code Blobs", total_blobs or 0)
        
        with col5:
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
                
                st.write("**Code:**")
                # Fetch code from CodeVault
                code_statement = select(CodeVault).where(
                    CodeVault.hash == tool.active_hash_ref
                )
                code_vault = session.exec(code_statement).first()
                
                if code_vault:
                    language = "python" if code_vault.code_type == "python" else "sql"
                    st.code(code_vault.code_blob, language=language)
                    st.caption(f"Code Type: {code_vault.code_type}")
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
                        session.rollback()
                        st.error(f"Error deleting tool: {e}")


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
        
        st.write("**Code Editor:**")
        code_type = st.selectbox(
            "Code Type *",
            options=["python", "select"],
            help="Select 'python' for Python code or 'select' for SQL SELECT statements"
        )
        
        if code_type == "python":
            placeholder_text = "# Your Python code here\n# Access arguments with: arguments.get('param_name')\n# Set result with: result = your_value"
        else:
            placeholder_text = "-- Your SQL SELECT statement here\n-- Example: SELECT * FROM table_name WHERE column = value"
        
        code = st.text_area(
            "Code Logic *",
            placeholder=placeholder_text,
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
                        new_code = CodeVault(hash=code_hash, code_blob=code, code_type=code_type)
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


# Resource Registry Page
def show_resource_registry():
    """Display resource registry with filtering and management."""
    st.header("📦 Resource Registry")
    
    engine = get_db_engine()
    with Session(engine) as session:
        # Get all unique personas for the dropdown
        personas_statement = select(ResourceRegistry.target_persona).distinct()
        personas = session.exec(personas_statement).all()
        
        if not personas:
            st.info("No resources found in the registry. Add some resources first!")
            return
        
        # Persona filter dropdown
        selected_persona = st.selectbox(
            "Filter by Persona:",
            options=personas,
            index=0,
            key="resource_persona_filter"
        )
        
        # Query resources for selected persona
        resources_statement = select(ResourceRegistry).where(
            ResourceRegistry.target_persona == selected_persona
        )
        resources = session.exec(resources_statement).all()
        
        if not resources:
            st.info(f"No resources found for persona '{selected_persona}'")
            return
        
        st.write(f"**{len(resources)} resource(s) found for persona '{selected_persona}'**")
        
        # Display each resource in an expander
        for resource in resources:
            with st.expander(f"📦 {resource.name}"):
                st.write("**URI Schema:**")
                st.code(resource.uri_schema)
                
                st.write("**Description:**")
                st.write(resource.description)
                
                st.write("**MIME Type:**")
                st.write(resource.mime_type)
                
                st.write("**Type:**")
                if resource.is_dynamic:
                    st.write("🔄 Dynamic (code-generated)")
                    
                    st.write("**Code:**")
                    # Fetch code from CodeVault
                    if resource.active_hash_ref:
                        code_statement = select(CodeVault).where(
                            CodeVault.hash == resource.active_hash_ref
                        )
                        code_vault = session.exec(code_statement).first()
                        
                        if code_vault:
                            language = "python" if code_vault.code_type == "python" else "sql"
                            st.code(code_vault.code_blob, language=language)
                            st.caption(f"Code Type: {code_vault.code_type}")
                        else:
                            st.error(f"Code not found for hash: {resource.active_hash_ref}")
                    else:
                        st.warning("No code hash reference set")
                else:
                    st.write("📝 Static (hardcoded content)")
                    
                    st.write("**Static Content:**")
                    st.text_area(
                        "Content",
                        value=resource.static_content or "",
                        height=100,
                        disabled=True,
                        key=f"static_content_{resource.uri_schema}"
                    )
                
                # Delete button
                if st.button(f"🗑️ Delete '{resource.name}'", key=f"delete_resource_{resource.uri_schema}"):
                    try:
                        session.delete(resource)
                        session.commit()
                        st.success(f"Resource '{resource.name}' deleted successfully!")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Error deleting resource: {e}")


# Add New Resource Page
def show_add_new_resource():
    """Display form for adding new resources."""
    st.header("➕ Add New Resource")
    
    engine = get_db_engine()
    
    # Form for adding a new resource
    with st.form("add_resource_form"):
        name = st.text_input("Resource Name *", placeholder="e.g., welcome_message, server_time")
        uri_schema = st.text_input("URI Schema *", placeholder="e.g., memo://welcome, system://time")
        target_persona = st.text_input("Target Persona *", placeholder="e.g., default, assistant", value="default")
        description = st.text_area("Description *", placeholder="Describe what this resource provides...")
        mime_type = st.text_input("MIME Type", value="text/plain", placeholder="e.g., text/plain, application/json")
        
        is_dynamic = st.checkbox("Is Dynamic (executes code)?", value=False)
        
        if is_dynamic:
            st.write("**Dynamic Resource - Code Editor:**")
            code_type = st.selectbox(
                "Code Type *",
                options=["python", "select"],
                help="Select 'python' for Python code or 'select' for SQL SELECT statements",
                key="resource_code_type"
            )
            
            if code_type == "python":
                placeholder_text = "# Your Python code here\n# Set result variable to return a value\n# Example:\n# from datetime import datetime\n# result = f'Time: {datetime.now()}'"
            else:
                placeholder_text = "-- Your SQL SELECT statement here\n-- Example: SELECT * FROM table_name WHERE column = value"
            
            code = st.text_area(
                "Code Logic *",
                placeholder=placeholder_text,
                height=200,
                key="resource_code"
            )
            static_content = None
        else:
            st.write("**Static Resource - Content:**")
            static_content = st.text_area(
                "Static Content *",
                placeholder="Enter the static content for this resource...",
                height=200,
                key="resource_static_content"
            )
            code = None
        
        submitted = st.form_submit_button("💾 Save Resource")
        
        if submitted:
            # Validation
            if not name or not uri_schema or not target_persona or not description:
                st.error("Please fill in all required fields (marked with *)")
                return
            
            if is_dynamic and not code:
                st.error("Please provide Python code for dynamic resource")
                return
            
            if not is_dynamic and not static_content:
                st.error("Please provide static content for static resource")
                return
            
            try:
                with Session(engine) as session:
                    code_hash = None
                    
                    if is_dynamic:
                        # Compute SHA-256 hash of the code
                        code_hash = compute_hash(code)
                        
                        # Check if hash exists in CodeVault (idempotency)
                        code_statement = select(CodeVault).where(CodeVault.hash == code_hash)
                        existing_code = session.exec(code_statement).first()
                        
                        if not existing_code:
                            # Insert new code into CodeVault
                            new_code = CodeVault(hash=code_hash, code_blob=code, code_type=code_type)
                            session.add(new_code)
                            st.info(f"New code blob added with hash: {code_hash[:16]}...")
                        else:
                            st.info(f"Code already exists in vault with hash: {code_hash[:16]}...")
                    
                    # Check if resource with this URI schema exists (upsert logic)
                    resource_statement = select(ResourceRegistry).where(
                        ResourceRegistry.uri_schema == uri_schema
                    )
                    existing_resource = session.exec(resource_statement).first()
                    
                    if existing_resource:
                        # Update existing resource
                        existing_resource.name = name
                        existing_resource.description = description
                        existing_resource.mime_type = mime_type
                        existing_resource.is_dynamic = is_dynamic
                        existing_resource.static_content = static_content
                        existing_resource.active_hash_ref = code_hash
                        existing_resource.target_persona = target_persona
                        st.success(f"Resource '{name}' updated successfully!")
                    else:
                        # Insert new resource
                        new_resource = ResourceRegistry(
                            uri_schema=uri_schema,
                            name=name,
                            description=description,
                            mime_type=mime_type,
                            is_dynamic=is_dynamic,
                            static_content=static_content,
                            active_hash_ref=code_hash,
                            target_persona=target_persona
                        )
                        session.add(new_resource)
                        st.success(f"Resource '{name}' added successfully!")
                    
                    # Commit transaction
                    session.commit()
                    
            except Exception as e:
                st.error(f"Error saving resource: {e}")


# Prompt Registry Page
def show_prompt_registry():
    """Display prompt registry with filtering and management."""
    st.header("💬 Prompt Registry")
    
    engine = get_db_engine()
    with Session(engine) as session:
        # Get all unique personas for the dropdown
        personas_statement = select(PromptRegistry.target_persona).distinct()
        personas = session.exec(personas_statement).all()
        
        if not personas:
            st.info("No prompts found in the registry. Add some prompts first!")
            return
        
        # Persona filter dropdown
        selected_persona = st.selectbox(
            "Filter by Persona:",
            options=personas,
            index=0,
            key="prompt_persona_filter"
        )
        
        # Query prompts for selected persona
        prompts_statement = select(PromptRegistry).where(
            PromptRegistry.target_persona == selected_persona
        )
        prompts = session.exec(prompts_statement).all()
        
        if not prompts:
            st.info(f"No prompts found for persona '{selected_persona}'")
            return
        
        st.write(f"**{len(prompts)} prompt(s) found for persona '{selected_persona}'**")
        
        # Display each prompt in an expander
        for prompt in prompts:
            with st.expander(f"💬 {prompt.name}"):
                st.write("**Description:**")
                st.write(prompt.description)
                
                st.write("**Template:**")
                st.text_area(
                    "Template Content",
                    value=prompt.template,
                    height=150,
                    disabled=True,
                    key=f"template_{prompt.name}_{prompt.target_persona}"
                )
                
                st.write("**Arguments Schema:**")
                st.json(prompt.arguments_schema)
                
                # Delete button
                if st.button(f"🗑️ Delete '{prompt.name}'", key=f"delete_prompt_{prompt.name}_{prompt.target_persona}"):
                    try:
                        session.delete(prompt)
                        session.commit()
                        st.success(f"Prompt '{prompt.name}' deleted successfully!")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Error deleting prompt: {e}")


# Add New Prompt Page
def show_add_new_prompt():
    """Display form for adding new prompts."""
    st.header("➕ Add New Prompt")
    
    engine = get_db_engine()
    
    # Form for adding a new prompt
    with st.form("add_prompt_form"):
        name = st.text_input("Prompt Name *", placeholder="e.g., review_code, bug_report")
        target_persona = st.text_input("Target Persona *", placeholder="e.g., default, assistant", value="default")
        description = st.text_area("Description *", placeholder="Describe what this prompt does...")
        
        st.write("**Template Editor:**")
        template = st.text_area(
            "Template *",
            placeholder="Enter template with placeholders like {variable_name}\nExample: Please review this code:\n\n{code}",
            height=200
        )
        
        st.write("**Arguments Schema Editor (JSON):**")
        schema_text = st.text_area(
            "Arguments Schema (JSON) *",
            value='{"arguments": []}',
            placeholder='{"arguments": [{"name": "code", "description": "The code to review", "required": true}]}',
            height=150
        )
        
        submitted = st.form_submit_button("💾 Save Prompt")
        
        if submitted:
            # Validation
            if not name or not target_persona or not description or not template:
                st.error("Please fill in all required fields (marked with *)")
                return
            
            # Validate JSON schema
            try:
                arguments_schema = json.loads(schema_text)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON schema: {e}")
                return
            
            try:
                with Session(engine) as session:
                    # Check if prompt with this name exists (upsert logic)
                    prompt_statement = select(PromptRegistry).where(
                        PromptRegistry.name == name
                    )
                    existing_prompt = session.exec(prompt_statement).first()
                    
                    if existing_prompt:
                        # Update existing prompt
                        existing_prompt.description = description
                        existing_prompt.template = template
                        existing_prompt.arguments_schema = arguments_schema
                        existing_prompt.target_persona = target_persona
                        st.success(f"Prompt '{name}' updated successfully!")
                    else:
                        # Insert new prompt
                        new_prompt = PromptRegistry(
                            name=name,
                            description=description,
                            template=template,
                            arguments_schema=arguments_schema,
                            target_persona=target_persona
                        )
                        session.add(new_prompt)
                        st.success(f"Prompt '{name}' added successfully!")
                    
                    # Commit transaction
                    session.commit()
                    
            except Exception as e:
                st.error(f"Error saving prompt: {e}")


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
            ["Dashboard", "Tool Registry", "Add New Tool", "Resource Registry", "Add New Resource", "Prompt Registry", "Add New Prompt"]
        )
        
        st.divider()
        st.caption("Database Connection")
        # Get DB URL same way as get_db_engine()
        db_url = os.environ.get('CHAMELEON_DB_URL')
        if not db_url:
            config = load_config()
            db_url = config['database']['url']
        st.caption(f"📁 {db_url}")
    
    # Route to appropriate page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Tool Registry":
        show_tool_registry()
    elif page == "Add New Tool":
        show_add_new_tool()
    elif page == "Resource Registry":
        show_resource_registry()
    elif page == "Add New Resource":
        show_add_new_resource()
    elif page == "Prompt Registry":
        show_prompt_registry()
    elif page == "Add New Prompt":
        show_add_new_prompt()


if __name__ == "__main__":
    main()
