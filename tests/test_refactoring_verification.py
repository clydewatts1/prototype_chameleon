
import pytest
import sys
import os
import re
from unittest.mock import MagicMock, patch

# Add server to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))
# Add tools/system to path for direct tool import testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools", "system")))

from common.security import validate_single_statement, validate_read_only, validate_code_structure, SecurityError

# Mock dependencies for CreateTempTestTool if runtime cannot be imported easily
# But since we added server to path, it should be fine.
from test_tool_creator import CreateTempTestTool

class TestSecurityHardening:
    """Test suite for security hardening changes."""
    
    def test_block_dangerous_imports(self):
        """Test that importlib, subprocess, etc. are blocked."""
        dangerous_codes = [
            "import importlib",
            "from importlib import util",
            "import subprocess",
            "import sys",
            "import os" # os is allowed in some contexts? logic says check os.system calls. 
                        # Wait, code says BANNED_MODULES include 'sys'.
        ]
        
        # Note: os might not be banned in import, but os.system calls are.
        # Let's check validate_code_structure implementation for 'os'.
        # BANNED_MODULES = {'importlib', 'subprocess', 'sys', 'shutil', 'marshal', 'pickle'}
        # So 'import os' is ALLOWED (it wasn't in BANNED_MODULES set in my write).
        
        # Test banned modules
        for code in ["import importlib", "import subprocess", "import sys"]:
            with pytest.raises(SecurityError, match="forbidden module"):
                validate_code_structure(code)

    def test_block_dangerous_functions(self):
        """Test that exec, eval, open, etc. are blocked."""
        # Must wrap in class to pass top-level check
        dangerous_codes = [
            "class A:\n def run(self):\n  exec('print(1)')",
            "class A:\n def run(self):\n  eval('1+1')",
            "class A:\n def run(self):\n  open('file.txt')",
            "class A:\n def run(self):\n  __import__('os')",
            "class A:\n def run(self):\n  input('prompt')",
            "class A:\n def run(self):\n  compile('src', 'f', 'exec')"
        ]
        
        for code in dangerous_codes:
            with pytest.raises(SecurityError, match="forbidden function"):
                validate_code_structure(code)

    def test_block_os_system(self):
        """Test that os.system is blocked."""
        code = """
class Exploit:
    def run(self):
        import os
        os.system("ls")
"""
        with pytest.raises(SecurityError, match="os.system"):
            validate_code_structure(code)

    def test_sqlparse_validation_readonly(self):
        """Test validate_read_only using strict checks."""
        valid_sql = "SELECT * FROM users WHERE id = 1"
        validate_read_only(valid_sql)
        
        invalid_sqls = [
            "DELETE FROM users",
            "UPDATE users SET name='Hack'",
            "INSERT INTO users VALUES (1)",
            "DROP TABLE users",
            "ALTER TABLE users ADD COLUMN hack TEXT",
            "GRANT ALL ON users TO hacker",
            "EXEC used_stored_proc"
        ]
        
        for sql in invalid_sqls:
            with pytest.raises(SecurityError):
                validate_read_only(sql)

    def test_sqlparse_validation_single_statement(self):
        """Test validate_single_statement."""
        valid_sql = "SELECT * FROM users"
        validate_single_statement(valid_sql)
        
        multi_sql = "SELECT 1; SELECT 2"
        with pytest.raises(SecurityError):
            validate_single_statement(multi_sql)


class TestCreateTempTestTool:
    """Test suite for CreateTempTestTool enhancements."""
    
    def test_run_rejects_limit_clause(self):
        """Test that supplying LIMIT clause is rejected."""
        tool = CreateTempTestTool(None, {'persona': 'default'}, None)
        tool.log = MagicMock()
        
        # Mock runtime imports inside the function to avoid side effects
        with patch('runtime.TEMP_TOOL_REGISTRY', {}), patch('runtime.TEMP_CODE_VAULT', {}):
            args = {
                "tool_name": "limit_test",
                "description": "Testing limit",
                "sql_query": "SELECT * FROM sales LIMIT 5",
                "parameters": {}
            }
            
            result = tool.run(args)
            assert "Error" in result
            assert "LIMIT" in result
            assert "limit" in result.lower()

    def test_run_appends_limit_automatically(self):
        """Test that LIMIT 3 is appended automatically."""
        tool = CreateTempTestTool(None, {'persona': 'default'}, None)
        tool.log = MagicMock()
        
        mock_registry = {}
        mock_vault = {}
        
        # We need to capture the sql_query that gets stored
        with patch('runtime.TEMP_TOOL_REGISTRY', mock_registry), \
             patch('runtime.TEMP_CODE_VAULT', mock_vault):
            
            args = {
                "tool_name": "auto_limit_test",
                "description": "Testing auto limit",
                "sql_query": "SELECT * FROM sales",  # No LIMIT
                "parameters": {}
            }
            
            result = tool.run(args)
            
            assert "Success" in result
            assert "LIMIT 3" in result
            
            # Verify code stored in vault has LIMIT 3
            # We need to find the hash
            assert len(mock_vault) == 1
            stored_code = list(mock_vault.values())[0]['code_blob']
            
            assert stored_code.endswith(" LIMIT 3")
            assert "SELECT * FROM sales LIMIT 3" in stored_code


class TestHashUtils:
    """Test the computed hash utility."""
    def test_compute_hash(self):
        from common.hash_utils import compute_hash
        import hashlib
        
        test_str = "test string"
        expected = hashlib.sha256(test_str.encode('utf-8')).hexdigest()
        assert compute_hash(test_str) == expected

