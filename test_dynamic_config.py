"""
Test script for dynamic database configuration (schema and table names).
Tests the new enterprise database configuration features.
"""

import os
import tempfile
from pathlib import Path
from config import load_config


def test_default_table_config():
    """Test that default table configuration is returned when no file exists."""
    print("\n🧪 Testing default table configuration...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            config = load_config()
            
            # Validate tables section exists
            assert 'tables' in config, "❌ Missing 'tables' in config"
            print("✅ Config has 'tables' section")
            
            # Validate table defaults
            tables = config['tables']
            assert tables['code_vault'] == 'codevault', "❌ Wrong default for code_vault"
            assert tables['tool_registry'] == 'toolregistry', "❌ Wrong default for tool_registry"
            assert tables['resource_registry'] == 'resourceregistry', "❌ Wrong default for resource_registry"
            assert tables['prompt_registry'] == 'promptregistry', "❌ Wrong default for prompt_registry"
            assert tables['sales_per_day'] == 'sales_per_day', "❌ Wrong default for sales_per_day"
            print("✅ All table name defaults are correct")
            
            # Validate schema default is None
            assert config['database']['schema'] is None, "❌ Schema should be None by default"
            print("✅ Schema default is None (correct for SQLite)")
            
            print("\n✅ Default table configuration test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_custom_table_names():
    """Test that custom table names can be configured via YAML."""
    print("\n🧪 Testing custom table names...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config directory and file
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            # Write YAML config with custom table names
            yaml_content = """
database:
  url: "postgresql://user:pass@localhost/db"

tables:
  tool_registry: "mcp_tools_v1"
  code_vault: "mcp_code_storage"
  resource_registry: "custom_resources"
"""
            config_file.write_text(yaml_content)
            
            # Load config
            config = load_config()
            
            # Validate custom table names are loaded
            tables = config['tables']
            assert tables['tool_registry'] == 'mcp_tools_v1', "❌ Custom tool_registry not loaded"
            assert tables['code_vault'] == 'mcp_code_storage', "❌ Custom code_vault not loaded"
            assert tables['resource_registry'] == 'custom_resources', "❌ Custom resource_registry not loaded"
            print("✅ Custom table names loaded correctly")
            
            # Validate that unspecified tables use defaults
            assert tables['prompt_registry'] == 'promptregistry', "❌ Default not preserved for prompt_registry"
            assert tables['sales_per_day'] == 'sales_per_day', "❌ Default not preserved for sales_per_day"
            print("✅ Defaults preserved for unspecified tables")
            
            print("\n✅ Custom table names test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_schema_configuration():
    """Test that database schema can be configured."""
    print("\n🧪 Testing schema configuration...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config directory and file
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            # Write YAML config with schema
            yaml_content = """
database:
  url: "teradata://user:pass@host/db"
  schema: "retail_data"
"""
            config_file.write_text(yaml_content)
            
            # Load config
            config = load_config()
            
            # Validate schema is loaded
            assert config['database']['schema'] == 'retail_data', "❌ Schema not loaded"
            print("✅ Schema loaded correctly")
            
            print("\n✅ Schema configuration test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_enterprise_full_config():
    """Test a complete enterprise configuration with both schema and custom table names."""
    print("\n🧪 Testing full enterprise configuration...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config directory and file
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            # Write complete enterprise config
            yaml_content = """
server:
  transport: "sse"
  port: 9000

database:
  url: "postgresql://admin:secret@prod-db.example.com:5432/analytics"
  schema: "mcp_prod"

tables:
  code_vault: "chameleon_code"
  tool_registry: "chameleon_tools"
  resource_registry: "chameleon_resources"
  prompt_registry: "chameleon_prompts"
  sales_per_day: "fact_sales_daily"
"""
            config_file.write_text(yaml_content)
            
            # Load config
            config = load_config()
            
            # Validate database settings
            assert config['database']['url'] == 'postgresql://admin:secret@prod-db.example.com:5432/analytics'
            assert config['database']['schema'] == 'mcp_prod'
            print("✅ Database settings loaded correctly")
            
            # Validate all custom table names
            tables = config['tables']
            assert tables['code_vault'] == 'chameleon_code'
            assert tables['tool_registry'] == 'chameleon_tools'
            assert tables['resource_registry'] == 'chameleon_resources'
            assert tables['prompt_registry'] == 'chameleon_prompts'
            assert tables['sales_per_day'] == 'fact_sales_daily'
            print("✅ All custom table names loaded correctly")
            
            # Validate server settings also loaded
            assert config['server']['transport'] == 'sse'
            assert config['server']['port'] == 9000
            print("✅ Server settings also loaded correctly")
            
            print("\n✅ Full enterprise configuration test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_partial_table_config():
    """Test that partial table configuration merges properly with defaults."""
    print("\n🧪 Testing partial table configuration...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config directory and file
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            # Write config with only one custom table name
            yaml_content = """
tables:
  tool_registry: "custom_tools"
"""
            config_file.write_text(yaml_content)
            
            # Load config
            config = load_config()
            
            # Validate custom value is used
            assert config['tables']['tool_registry'] == 'custom_tools', "❌ Custom table name not loaded"
            print("✅ Custom table name loaded")
            
            # Validate all other defaults are preserved
            tables = config['tables']
            assert tables['code_vault'] == 'codevault', "❌ Default not preserved"
            assert tables['resource_registry'] == 'resourceregistry', "❌ Default not preserved"
            assert tables['prompt_registry'] == 'promptregistry', "❌ Default not preserved"
            assert tables['sales_per_day'] == 'sales_per_day', "❌ Default not preserved"
            print("✅ All other defaults preserved")
            
            print("\n✅ Partial table configuration test passed!")
            return True
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


if __name__ == "__main__":
    print("=" * 60)
    print("Running Dynamic Database Configuration Tests")
    print("=" * 60)
    
    try:
        test_default_table_config()
        test_custom_table_names()
        test_schema_configuration()
        test_enterprise_full_config()
        test_partial_table_config()
        
        print("\n" + "=" * 60)
        print("✅ All dynamic configuration tests passed!")
        print("=" * 60)
        exit(0)
        
    except AssertionError as e:
        print(f"\n{e}")
        print("\n" + "=" * 60)
        print("❌ Dynamic configuration tests failed!")
        print("=" * 60)
        exit(1)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
