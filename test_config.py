"""
Test script for config.py to validate configuration loading.
"""

import os
import tempfile
from pathlib import Path
from config import load_config, get_default_config


def test_default_config():
    """Test that default configuration is returned when no file exists."""
    print("\n🧪 Testing default configuration...\n")
    
    # Temporarily set HOME to a temp directory to ensure no config file exists
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            config = load_config()
            
            # Validate structure
            assert 'server' in config, "❌ Missing 'server' in config"
            assert 'database' in config, "❌ Missing 'database' in config"
            print("✅ Config has required top-level keys")
            
            # Validate server defaults
            assert config['server']['transport'] == 'stdio', "❌ Wrong default transport"
            assert config['server']['host'] == '0.0.0.0', "❌ Wrong default host"
            assert config['server']['port'] == 8000, "❌ Wrong default port"
            assert config['server']['log_level'] == 'INFO', "❌ Wrong default log_level"
            print("✅ Server defaults are correct")
            
            # Validate database defaults
            assert config['database']['url'] == 'sqlite:///chameleon.db', "❌ Wrong default database URL"
            print("✅ Database defaults are correct")
            
            print("\n✅ Default configuration test passed!")
            return True
            
        finally:
            # Restore original HOME
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_yaml_config():
    """Test that YAML configuration is loaded and merged with defaults."""
    print("\n🧪 Testing YAML configuration loading...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config directory and file
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            # Write sample YAML config
            yaml_content = """
server:
  transport: "sse"
  port: 9000
  log_level: "DEBUG"
database:
  url: "postgresql://user:pass@localhost/db"
"""
            config_file.write_text(yaml_content)
            
            # Load config
            config = load_config()
            
            # Validate that YAML values override defaults
            assert config['server']['transport'] == 'sse', "❌ YAML transport not loaded"
            assert config['server']['port'] == 9000, "❌ YAML port not loaded"
            assert config['server']['log_level'] == 'DEBUG', "❌ YAML log_level not loaded"
            print("✅ Server YAML values loaded correctly")
            
            # Validate that default values are preserved when not in YAML
            assert config['server']['host'] == '0.0.0.0', "❌ Default host not preserved"
            print("✅ Default values preserved when not in YAML")
            
            # Validate database YAML value
            assert config['database']['url'] == 'postgresql://user:pass@localhost/db', "❌ YAML database URL not loaded"
            print("✅ Database YAML value loaded correctly")
            
            print("\n✅ YAML configuration test passed!")
            return True
            
        finally:
            # Restore original HOME
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


def test_partial_yaml_config():
    """Test that partial YAML config merges properly with defaults."""
    print("\n🧪 Testing partial YAML configuration...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Create config directory and file
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            # Write partial YAML config (only database URL)
            yaml_content = """
database:
  url: "sqlite:///custom.db"
"""
            config_file.write_text(yaml_content)
            
            # Load config
            config = load_config()
            
            # Validate that YAML database value is used
            assert config['database']['url'] == 'sqlite:///custom.db', "❌ YAML database URL not loaded"
            print("✅ YAML database value loaded")
            
            # Validate that all server defaults are preserved
            assert config['server']['transport'] == 'stdio', "❌ Server defaults not preserved"
            assert config['server']['host'] == '0.0.0.0', "❌ Server defaults not preserved"
            assert config['server']['port'] == 8000, "❌ Server defaults not preserved"
            assert config['server']['log_level'] == 'INFO', "❌ Server defaults not preserved"
            print("✅ All server defaults preserved")
            
            print("\n✅ Partial YAML configuration test passed!")
            return True
            
        finally:
            # Restore original HOME
            if original_home:
                os.environ['HOME'] = original_home
            else:
                del os.environ['HOME']


if __name__ == "__main__":
    print("=" * 60)
    print("Running config.py tests")
    print("=" * 60)
    
    try:
        test_default_config()
        test_yaml_config()
        test_partial_yaml_config()
        
        print("\n" + "=" * 60)
        print("✅ All config tests passed!")
        print("=" * 60)
        exit(0)
        
    except AssertionError as e:
        print(f"\n{e}")
        print("\n" + "=" * 60)
        print("❌ Config tests failed!")
        print("=" * 60)
        exit(1)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
