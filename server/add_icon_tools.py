"""
Script to register Icon Management tools in the database.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from common.hash_utils import compute_hash
from sqlmodel import Session
from models import CodeVault, ToolRegistry, get_engine, METADATA_MODELS, create_db_and_tables
from config import load_config

def register_icon_tools():
    config = load_config()
    db_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon_meta.db')
    engine = get_engine(db_url)
    
    # Ensure tables exist (including IconRegistry)
    create_db_and_tables(engine, METADATA_MODELS)
    
    with Session(engine) as session:
        # 1. save_icon tool
        save_icon_code = """from base import ChameleonTool
from models import IconRegistry
from sqlmodel import select

class SaveIconTool(ChameleonTool):
    def run(self, arguments):
        name = arguments.get('name')
        content = arguments.get('content')
        fmt = arguments.get('format', 'svg').lower()
        
        if not name or not content:
            return "Error: Name and content are required."
            
        mime_type = "image/png"
        
        # Validation
        if fmt == 'svg':
            mime_type = "image/svg+xml"
            if '<svg' not in content:
                # Basic validation: check for root element
                # If it's base64 encoded, decode to check, or trust user?
                # For simplicity, if it doesn't look like XML, assume it might be base64 encoded SVG or just invalid.
                # Let's support raw SVG string.
                pass
        
        existing = self.db_session.exec(select(IconRegistry).where(IconRegistry.icon_name == name)).first()
        if existing:
            existing.content = content
            existing.mime_type = mime_type
            self.db_session.add(existing)
            self.db_session.commit()
            return f"Updated icon '{name}'"
        else:
            new_icon = IconRegistry(icon_name=name, mime_type=mime_type, content=content)
            self.db_session.add(new_icon)
            self.db_session.commit()
            return f"Created icon '{name}'"
"""
        save_icon_hash = compute_hash(save_icon_code)
        session.merge(CodeVault(hash=save_icon_hash, code_blob=save_icon_code, code_type="python"))
        session.merge(ToolRegistry(
            tool_name="icon_save",
            target_persona="admin",
            description="Save or update an icon. Supports SVG (raw string) or PNG (base64).",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique name for the icon"},
                    "content": {"type": "string", "description": "Icon content (Raw SVG string or Base64 PNG)"},
                    "format": {"type": "string", "description": "Format: 'svg' or 'png'", "default": "svg"}
                },
                "required": ["name", "content"]
            },
            active_hash_ref=save_icon_hash,
            group="admin"
        ))

        # 2. assign_icon tool
        assign_icon_code = """from base import ChameleonTool
from models import ToolRegistry, IconRegistry
from sqlmodel import select

class AssignIconTool(ChameleonTool):
    def run(self, arguments):
        tool_name = arguments.get('tool_name')
        icon_name = arguments.get('icon_name')
        
        # Validate icon exists
        icon = self.db_session.exec(select(IconRegistry).where(IconRegistry.icon_name == icon_name)).first()
        if not icon:
            return f"Error: Icon '{icon_name}' not found."
            
        # Update tool
        tool = self.db_session.exec(select(ToolRegistry).where(ToolRegistry.tool_name == tool_name)).first()
        if not tool:
            return f"Error: Tool '{tool_name}' not found."
            
        tool.icon_name = icon_name
        self.db_session.add(tool)
        self.db_session.commit()
        
        return f"Assigned icon '{icon_name}' to tool '{tool_name}'"
"""
        assign_icon_hash = compute_hash(assign_icon_code)
        session.merge(CodeVault(hash=assign_icon_hash, code_blob=assign_icon_code, code_type="python"))
        session.merge(ToolRegistry(
            tool_name="icon_assign",
            target_persona="admin",
            description="Assign an existing icon to a tool.",
            input_schema={
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "Name of the tool to update"},
                    "icon_name": {"type": "string", "description": "Name of the icon to assign"}
                },
                "required": ["tool_name", "icon_name"]
            },
            active_hash_ref=assign_icon_hash,
            group="admin"
        ))

        # 3. list_icons tool
        list_icons_code = """from base import ChameleonTool
from models import IconRegistry
from sqlmodel import select

class ListIconsTool(ChameleonTool):
    def run(self, arguments):
        icons = self.db_session.exec(select(IconRegistry)).all()
        if not icons:
            return "No icons found."
            
        result = ["Available Icons:"]
        for icon in icons:
            preview = "(Base64)" if len(icon.content) > 50 else icon.content[:20] + "..."
            result.append(f"- {icon.icon_name} ({icon.mime_type})")
            
        return "\\n".join(result)
"""
        list_icons_hash = compute_hash(list_icons_code)
        session.merge(CodeVault(hash=list_icons_hash, code_blob=list_icons_code, code_type="python"))
        session.merge(ToolRegistry(
            tool_name="icon_list",
            target_persona="admin",
            description="List all available icons in the registry.",
            input_schema={"type": "object", "properties": {}},
            active_hash_ref=list_icons_hash,
            group="admin"
        ))
        
        session.commit()
        print("Icon management tools registered successfully!")

if __name__ == "__main__":
    register_icon_tools()
