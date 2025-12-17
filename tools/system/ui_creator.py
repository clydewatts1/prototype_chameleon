from base import ChameleonTool
from sqlmodel import select
from common.hash_utils import compute_hash
import os
import re

class UiCreatorTool(ChameleonTool):
    def run(self, arguments):
        '''
        Create a new Streamlit dashboard with validation.
        
        Args:
            dashboard_name: Name of the dashboard (e.g., "sales_dashboard")
            python_code: The Python code for the Streamlit dashboard
        
        Returns:
            Success message confirming the dashboard is registered
        '''
        from models import CodeVault, ToolRegistry
        from config import load_config
        
        # Extract arguments
        dashboard_name = arguments.get('dashboard_name')
        python_code = arguments.get('python_code')
        
        # Validation 1: Check all required arguments are provided
        if not dashboard_name:
            return "Error: dashboard_name is required"
        if not python_code:
            return "Error: python_code is required"
        
        # Validation 2: Check if feature is enabled
        config = load_config()
        ui_config = config.get('features', {}).get('chameleon_ui', {})
        if not ui_config.get('enabled', True):
            return "Error: Chameleon UI feature is disabled in configuration"
        
        # Validation 3: Ensure code imports streamlit
        if 'import streamlit' not in python_code and 'from streamlit' not in python_code:
            return "Error: python_code must import streamlit (e.g., 'import streamlit as st')"
        
        # Validation 4: Sanitize dashboard_name (alphanumeric, underscore, dash only)
        if not re.match(r'^[a-zA-Z0-9_-]+$', dashboard_name):
            return "Error: dashboard_name must contain only alphanumeric characters, underscores, or dashes"
        
        self.log(f"Creating Streamlit dashboard: {dashboard_name}")
        self.log(f"Dashboard validation passed")
        
        # Compute SHA-256 hash of the python_code
        code_hash = compute_hash(python_code)
        
        try:
            # Get apps directory from config
            apps_dir = ui_config.get('apps_dir', 'ui_apps')
            
            # Create absolute path for apps directory
            # Use current working directory as base
            apps_dir_path = os.path.abspath(apps_dir)
            
            # Create apps directory if it doesn't exist
            os.makedirs(apps_dir_path, exist_ok=True)
            self.log(f"Apps directory: {apps_dir_path}")
            
            # Write code to physical file
            dashboard_file = os.path.join(apps_dir_path, f"{dashboard_name}.py")
            
            # Use safe_write_file from common.file_utils to bypass security check on open()
            from common.file_utils import safe_write_file
            safe_write_file(dashboard_file, python_code)
            
            self.log(f"Dashboard file written: {dashboard_file}")
            
            # Upsert into CodeVault with code_type='streamlit'
            statement = select(CodeVault).where(CodeVault.hash == code_hash)
            existing_code = self.meta_session.exec(statement).first()
            
            if existing_code:
                self.log(f"Code already exists in CodeVault (hash: {code_hash[:16]}...)")
                # Update code_type to ensure it's 'streamlit'
                existing_code.code_type = 'streamlit'
                self.meta_session.add(existing_code)
            else:
                code_vault = CodeVault(
                    hash=code_hash,
                    code_blob=python_code,
                    code_type='streamlit'
                )
                self.meta_session.add(code_vault)
                self.log(f"Code registered in CodeVault (hash: {code_hash[:16]}...)")
            
            # Construct input_schema (no parameters for dashboard display)
            input_schema = {
                'type': 'object',
                'properties': {},
                'required': []
            }
            
            # Upsert into ToolRegistry (default persona)
            statement = select(ToolRegistry).where(
                ToolRegistry.tool_name == dashboard_name,
                ToolRegistry.target_persona == 'default'
            )
            existing_tool = self.meta_session.exec(statement).first()
            
            if existing_tool:
                # Update existing tool
                existing_tool.description = f"Streamlit dashboard: {dashboard_name}"
                existing_tool.input_schema = input_schema
                existing_tool.active_hash_ref = code_hash
                existing_tool.is_auto_created = True
                self.meta_session.add(existing_tool)
                self.log(f"Dashboard '{dashboard_name}' updated in ToolRegistry")
            else:
                # Create new tool
                tool = ToolRegistry(
                    tool_name=dashboard_name,
                    target_persona='default',
                    description=f"Streamlit dashboard: {dashboard_name}",
                    input_schema=input_schema,
                    active_hash_ref=code_hash,
                    is_auto_created=True
                )
                self.meta_session.add(tool)
                self.log(f"Dashboard '{dashboard_name}' created in ToolRegistry")
            
            # Commit changes
            self.meta_session.commit()
            
            return f"Success: Dashboard '{dashboard_name}' has been created and saved to {dashboard_file}. Use 'run_ui.sh' to start the Streamlit server, then call this tool to get the dashboard URL."
            
        except Exception as e:
            self.meta_session.rollback()
            return f"Error: Failed to create dashboard - {type(e).__name__}: {str(e)}"
