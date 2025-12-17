
import pytest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools", "system")))

from tools.system.ui_creator import UiCreatorTool
from tools.system.macro_creator import MacroCreatorTool

class TestUiCreatorTool:
    def test_creates_file_and_db_entry(self):
        """Test successful dashboard creation."""
        tool = UiCreatorTool(None, {}, None)
        tool.log = MagicMock()
        tool.meta_session = MagicMock() 
        tool.meta_session.exec.return_value.first.return_value = None # No existing tool code/registry
        
        args = {
            "dashboard_name": "test_dash",
            "python_code": "import streamlit as st\nst.write('hi')"
        }
        
        # Mock dependencies
        with patch('builtins.open', mock_open()) as m_open, \
             patch('os.makedirs') as m_makedirs, \
             patch('os.path.exists', return_value=False), \
             patch('tools.system.ui_creator.compute_hash', return_value='hash123'), \
             patch('tools.system.ui_creator.select') as m_select, \
             patch('config.load_config', return_value={'features': {'chameleon_ui': {'enabled': True, 'apps_dir': 'ui_apps'}}}), \
             patch.dict('sys.modules', {'runtime': MagicMock(), 'models': MagicMock()}) as m_sys:
             
             # Setup select mock
             # select(Model).where(...) -> returns statement object
             m_select.return_value.where.return_value = "dummy_statement"
             
             result = tool.run(args)
             
             assert "Success" in result
             assert "test_dash" in result
             
             # Verify file writing
             m_makedirs.assert_called_with(os.path.abspath('ui_apps'), exist_ok=True)
             m_open.assert_called()
             handle = m_open()
             handle.write.assert_called_with(args['python_code'])
             
             # Verify DB interactions
             assert tool.meta_session.add.call_count >= 2 # CodeVault + ToolRegistry
             tool.meta_session.commit.assert_called()

    def test_validates_streamlit_import(self):
        """Test check for streamlit import."""
        tool = UiCreatorTool(None, {}, None)
        # Mock load_config to enable UI
        with patch('config.load_config', return_value={'features': {'chameleon_ui': {'enabled': True}}}):
            args = {
                "dashboard_name": "fail_dash",
                "python_code": "print('no streamlit')"
            }
            with patch.dict('sys.modules', {'models': MagicMock(), 'config': MagicMock()}):
                result = tool.run(args)
                assert "Error" in result
                assert "import streamlit" in result

    def test_sanitizes_name(self):
        """Test name sanitization."""
        tool = UiCreatorTool(None, {}, None)
        with patch('config.load_config', return_value={'features': {'chameleon_ui': {'enabled': True}}}):
            args = {
                "dashboard_name": "Bad Name!",
                "python_code": "import streamlit as st"
            }
            with patch.dict('sys.modules', {'models': MagicMock()}):
                result = tool.run(args)
                assert "Error" in result
                assert "alphanumeric" in result or "characters" in result

class TestMacroCreatorTool:
    def test_create_macro_success(self):
        """Test successful macro creation."""
        tool = MacroCreatorTool(None, {'persona': 'default'}, None)
        tool.log = MagicMock()
        tool.db_session = MagicMock()
        tool.db_session.exec.return_value.first.return_value = None
        
        args = {
            "name": "test_macro",
            "description": "Run two steps",
            "template": "{% macro test %}{% endmacro %}"
        }
        
        # Patch models to allow import of MacroRegistry
        with patch.dict('sys.modules', {'models': MagicMock()}) as m_sys, \
             patch('tools.system.macro_creator.select') as m_select:
             
             m_select.return_value.where.return_value = "dummy_statement"
             
             result = tool.run(args)
             
             assert "Success" in result
             assert "test_macro" in result
             
             # Verify DB adds
             assert tool.db_session.add.call_count >= 1
             tool.db_session.commit.assert_called()

    def test_validate_template_format(self):
        """Test validation of template format."""
        tool = MacroCreatorTool(None, {'persona': 'default'}, None)
        
        # Missing template start
        args = {
            "name": "bad_macro",
            "description": "Desc",
            "template": "not a macro"
        }
        with patch.dict('sys.modules', {'models': MagicMock()}):
            result = tool.run(args)
            assert "Error" in result
            assert "{% macro" in result
