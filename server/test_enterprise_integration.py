"""
Simple integration test for enterprise database configuration.

This test demonstrates the new configuration capabilities in separate processes
to avoid SQLAlchemy metadata conflicts.
"""

import subprocess
import sys


def run_test_script(script_code, description):
    """Run a test script in a subprocess."""
    print(f"\n🧪 {description}")
    print("=" * 60)
    
    result = subprocess.run(
        [sys.executable, '-c', script_code],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise AssertionError(f"Test failed: {description}")
    
    print(result.stdout)
    print(f"✅ {description} PASSED\n")


def main():
    print("\n" + "=" * 60)
    print("ENTERPRISE DATABASE CONFIGURATION - INTEGRATION TESTS")
    print("=" * 60)
    
    # Test 1: Default configuration
    test1 = '''
import os
import sys
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    os.environ["HOME"] = tmpdir
    sys.path.insert(0, "/home/runner/work/prototype_chameleon/prototype_chameleon")
    from models import CodeVault, ToolRegistry
    from config import load_config
    
    config = load_config()
    assert CodeVault.__tablename__ == "codevault", f"Expected codevault, got {CodeVault.__tablename__}"
    assert ToolRegistry.__tablename__ == "toolregistry", f"Expected toolregistry, got {ToolRegistry.__tablename__}"
    assert CodeVault.__table_args__ is None, "Schema should be None for default config"
    print("✅ Default table names: codevault, toolregistry")
    print("✅ No schema (SQLite default)")
'''
    run_test_script(test1, "Test 1: Default Configuration")
    
    # Test 2: Custom table names
    test2 = '''
import os
import sys
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as tmpdir:
    os.environ["HOME"] = tmpdir
    config_dir = Path(tmpdir) / ".chameleon" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("""
tables:
  code_vault: "my_code"
  tool_registry: "my_tools"
""")
    sys.path.insert(0, "/home/runner/work/prototype_chameleon/prototype_chameleon")
    from models import CodeVault, ToolRegistry
    
    assert CodeVault.__tablename__ == "my_code", f"Expected my_code, got {CodeVault.__tablename__}"
    assert ToolRegistry.__tablename__ == "my_tools", f"Expected my_tools, got {ToolRegistry.__tablename__}"
    print("✅ Custom table names: my_code, my_tools")
'''
    run_test_script(test2, "Test 2: Custom Table Names")
    
    # Test 3: Schema configuration
    test3 = '''
import os
import sys
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as tmpdir:
    os.environ["HOME"] = tmpdir
    config_dir = Path(tmpdir) / ".chameleon" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("""
database:
  schema: "retail_data"
""")
    sys.path.insert(0, "/home/runner/work/prototype_chameleon/prototype_chameleon")
    from models import CodeVault, ToolRegistry
    
    assert CodeVault.__table_args__ == {"schema": "retail_data"}, f"Expected schema retail_data, got {CodeVault.__table_args__}"
    assert ToolRegistry.__table_args__ == {"schema": "retail_data"}, f"Expected schema retail_data, got {ToolRegistry.__table_args__}"
    print("✅ Schema configured: retail_data")
'''
    run_test_script(test3, "Test 3: Schema Configuration")
    
    # Test 4: Full enterprise config
    test4 = '''
import os
import sys
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as tmpdir:
    os.environ["HOME"] = tmpdir
    config_dir = Path(tmpdir) / ".chameleon" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("""
database:
  url: "postgresql://user:pass@host/db"
  schema: "mcp_prod"

tables:
  code_vault: "chameleon_code"
  tool_registry: "chameleon_tools"
  resource_registry: "chameleon_resources"
  prompt_registry: "chameleon_prompts"
  sales_per_day: "fact_sales_daily"
""")
    sys.path.insert(0, "/home/runner/work/prototype_chameleon/prototype_chameleon")
    from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry, SalesPerDay
    from config import load_config
    
    config = load_config()
    assert config["database"]["url"] == "postgresql://user:pass@host/db"
    assert config["database"]["schema"] == "mcp_prod"
    assert CodeVault.__tablename__ == "chameleon_code"
    assert ToolRegistry.__tablename__ == "chameleon_tools"
    assert ResourceRegistry.__tablename__ == "chameleon_resources"
    assert PromptRegistry.__tablename__ == "chameleon_prompts"
    assert SalesPerDay.__tablename__ == "fact_sales_daily"
    assert CodeVault.__table_args__ == {"schema": "mcp_prod"}
    print("✅ Database: postgresql://user:pass@host/db")
    print("✅ Schema: mcp_prod")
    print("✅ All custom table names configured")
'''
    run_test_script(test4, "Test 4: Full Enterprise Configuration")
    
    # Test 5: Database creation with custom names
    test5 = '''
import os
import sys
import tempfile
import sqlite3
from pathlib import Path
with tempfile.TemporaryDirectory() as tmpdir:
    os.environ["HOME"] = tmpdir
    config_dir = Path(tmpdir) / ".chameleon" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("""
database:
  url: "sqlite:///test_enterprise.db"

tables:
  code_vault: "enterprise_code"
  tool_registry: "enterprise_tools"
""")
    sys.path.insert(0, "/home/runner/work/prototype_chameleon/prototype_chameleon")
    from models import get_engine, create_db_and_tables
    
    engine = get_engine("sqlite:///test_enterprise.db")
    create_db_and_tables(engine)
    
    conn = sqlite3.connect("test_enterprise.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'enterprise%' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    assert "enterprise_code" in tables, f"Expected enterprise_code in {tables}"
    assert "enterprise_tools" in tables, f"Expected enterprise_tools in {tables}"
    print(f"✅ Created tables with custom names: {tables}")
'''
    run_test_script(test5, "Test 5: Database Creation with Custom Names")
    
    print("\n" + "=" * 60)
    print("✅ ALL INTEGRATION TESTS PASSED!")
    print("=" * 60)
    print("\nFeatures verified:")
    print("  ✅ Backward compatibility with default SQLite")
    print("  ✅ Custom table name configuration")
    print("  ✅ Schema prefix configuration")
    print("  ✅ Full enterprise database configuration")
    print("  ✅ Actual database creation with custom names")
    print("\nReady for enterprise deployment!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
