"""
Test script for dynamic table names and schema in models.
Verifies that models correctly apply configuration to table definitions.
"""

import os
import sys
import tempfile
from pathlib import Path


def test_models_with_default_config():
    """Test that models use default table names when no config exists."""
    print("\n🧪 Testing models with default configuration...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Import models after setting HOME (to force config reload)
            import importlib
            if 'models' in sys.modules:
                importlib.reload(sys.modules['models'])
            from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry, SalesPerDay
            
            # Verify table names
            assert CodeVault.__tablename__ == 'codevault', f"❌ CodeVault table name is {CodeVault.__tablename__}"
            print(f"✅ CodeVault uses default table name: {CodeVault.__tablename__}")
            
            assert ToolRegistry.__tablename__ == 'toolregistry', f"❌ ToolRegistry table name is {ToolRegistry.__tablename__}"
            print(f"✅ ToolRegistry uses default table name: {ToolRegistry.__tablename__}")
            
            assert ResourceRegistry.__tablename__ == 'resourceregistry', f"❌ ResourceRegistry table name is {ResourceRegistry.__tablename__}"
            print(f"✅ ResourceRegistry uses default table name: {ResourceRegistry.__tablename__}")
            
            assert PromptRegistry.__tablename__ == 'promptregistry', f"❌ PromptRegistry table name is {PromptRegistry.__tablename__}"
            print(f"✅ PromptRegistry uses default table name: {PromptRegistry.__tablename__}")
            
            assert SalesPerDay.__tablename__ == 'sales_per_day', f"❌ SalesPerDay table name is {SalesPerDay.__tablename__}"
            print(f"✅ SalesPerDay uses default table name: {SalesPerDay.__tablename__}")
            
            # Verify schema is None by default
            assert CodeVault.__table_args__ is None, "❌ Schema should be None by default"
            print("✅ Schema is None by default (correct for SQLite)")
            
            print("\n✅ Models with default configuration test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_models_with_custom_table_names():
    """Test that models use custom table names from configuration."""
    print("\n🧪 Testing models with custom table names...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config directory and file
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            # Write config with custom table names
            yaml_content = """
tables:
  code_vault: "custom_code"
  tool_registry: "custom_tools"
  resource_registry: "custom_resources"
  prompt_registry: "custom_prompts"
  sales_per_day: "custom_sales"
"""
            config_file.write_text(yaml_content)
            
            # Import models fresh with new config
            import importlib
            if 'models' in sys.modules:
                # Clear config module first to force reload
                if 'config' in sys.modules:
                    importlib.reload(sys.modules['config'])
                importlib.reload(sys.modules['models'])
            from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry, SalesPerDay
            
            # Verify custom table names are used
            assert CodeVault.__tablename__ == 'custom_code', f"❌ CodeVault table name is {CodeVault.__tablename__}"
            print(f"✅ CodeVault uses custom table name: {CodeVault.__tablename__}")
            
            assert ToolRegistry.__tablename__ == 'custom_tools', f"❌ ToolRegistry table name is {ToolRegistry.__tablename__}"
            print(f"✅ ToolRegistry uses custom table name: {ToolRegistry.__tablename__}")
            
            assert ResourceRegistry.__tablename__ == 'custom_resources', f"❌ ResourceRegistry table name is {ResourceRegistry.__tablename__}"
            print(f"✅ ResourceRegistry uses custom table name: {ResourceRegistry.__tablename__}")
            
            assert PromptRegistry.__tablename__ == 'custom_prompts', f"❌ PromptRegistry table name is {PromptRegistry.__tablename__}"
            print(f"✅ PromptRegistry uses custom table name: {PromptRegistry.__tablename__}")
            
            assert SalesPerDay.__tablename__ == 'custom_sales', f"❌ SalesPerDay table name is {SalesPerDay.__tablename__}"
            print(f"✅ SalesPerDay uses custom table name: {SalesPerDay.__tablename__}")
            
            print("\n✅ Models with custom table names test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_models_with_schema():
    """Test that models correctly apply schema configuration."""
    print("\n🧪 Testing models with schema configuration...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config directory and file
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            # Write config with schema
            yaml_content = """
database:
  url: "postgresql://user:pass@localhost/db"
  schema: "my_schema"
"""
            config_file.write_text(yaml_content)
            
            # Import models fresh with new config
            import importlib
            if 'models' in sys.modules:
                if 'config' in sys.modules:
                    importlib.reload(sys.modules['config'])
                importlib.reload(sys.modules['models'])
            from models import CodeVault, ToolRegistry
            
            # Verify schema is set
            assert CodeVault.__table_args__ is not None, "❌ Schema args should not be None"
            assert CodeVault.__table_args__ == {"schema": "my_schema"}, f"❌ Schema is {CodeVault.__table_args__}"
            print(f"✅ CodeVault has correct schema: {CodeVault.__table_args__}")
            
            assert ToolRegistry.__table_args__ == {"schema": "my_schema"}, f"❌ Schema is {ToolRegistry.__table_args__}"
            print(f"✅ ToolRegistry has correct schema: {ToolRegistry.__table_args__}")
            
            print("\n✅ Models with schema configuration test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_foreign_key_references():
    """Test that foreign key references use dynamic table names."""
    print("\n🧪 Testing foreign key references...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Test 1: No schema, default table names
            # First clear the module cache to ensure fresh import
            for mod in ['models', 'config']:
                if mod in sys.modules:
                    del sys.modules[mod]
            
            from models import ToolRegistry, ResourceRegistry
            
            # Check ToolRegistry foreign key
            tool_fk = str(ToolRegistry.__fields__['active_hash_ref'].field_info.foreign_key)
            assert 'codevault.hash' in tool_fk, f"❌ ToolRegistry FK is {tool_fk}"
            print(f"✅ ToolRegistry FK references correct table (no schema): {tool_fk}")
            
            # Check ResourceRegistry foreign key
            resource_fk = str(ResourceRegistry.__fields__['active_hash_ref'].field_info.foreign_key)
            assert 'codevault.hash' in resource_fk, f"❌ ResourceRegistry FK is {resource_fk}"
            print(f"✅ ResourceRegistry FK references correct table (no schema): {resource_fk}")
            
            print("\n✅ Foreign key references test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_foreign_key_with_schema():
    """Test that foreign key references include schema when configured."""
    print("\n🧪 Testing foreign key references with schema...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config with schema
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            yaml_content = """
database:
  schema: "test_schema"
"""
            config_file.write_text(yaml_content)
            
            # Clear module cache and import fresh
            for mod in ['models', 'config']:
                if mod in sys.modules:
                    del sys.modules[mod]
            
            from models import ToolRegistry, ResourceRegistry
            
            # Check that schema is included in FK
            tool_fk = str(ToolRegistry.__fields__['active_hash_ref'].field_info.foreign_key)
            assert 'test_schema.codevault.hash' in tool_fk, f"❌ ToolRegistry FK with schema is {tool_fk}"
            print(f"✅ ToolRegistry FK includes schema: {tool_fk}")
            
            resource_fk = str(ResourceRegistry.__fields__['active_hash_ref'].field_info.foreign_key)
            assert 'test_schema.codevault.hash' in resource_fk, f"❌ ResourceRegistry FK with schema is {resource_fk}"
            print(f"✅ ResourceRegistry FK includes schema: {resource_fk}")
            
            print("\n✅ Foreign key with schema test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


if __name__ == "__main__":
    print("=" * 60)
    print("Running Dynamic Models Configuration Tests")
    print("=" * 60)
    
    try:
        test_models_with_default_config()
        test_models_with_custom_table_names()
        test_models_with_schema()
        test_foreign_key_references()
        test_foreign_key_with_schema()
        
        print("\n" + "=" * 60)
        print("✅ All models configuration tests passed!")
        print("=" * 60)
        exit(0)
        
    except AssertionError as e:
        print(f"\n{e}")
        print("\n" + "=" * 60)
        print("❌ Models configuration tests failed!")
        print("=" * 60)
        exit(1)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
