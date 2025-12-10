"""
Test script for configurable logs directory functionality.
"""

import os
import shutil
import tempfile
from pathlib import Path

# Import the setup_logging function
import sys
sys.path.insert(0, os.path.dirname(__file__))
from server import setup_logging
from config import load_config


def test_default_logs_directory():
    """Test that default logs directory is used when not configured."""
    print("\n🧪 Testing default logs directory...\n")
    
    # Clean up default logs directory
    logs_dir = Path("logs")
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
    
    try:
        # Call setup_logging without arguments (should use default)
        setup_logging()
        
        # Check that default logs/ directory was created
        if logs_dir.exists() and logs_dir.is_dir():
            print("   ✅ Default logs/ directory created")
        else:
            print("   ❌ Default logs/ directory not created")
            return False
        
        # Check that log file exists in default directory
        log_files = list(logs_dir.glob("mcp_server_*.log"))
        if len(log_files) == 1:
            print(f"   ✅ Log file created in default directory: {log_files[0].name}")
        else:
            print(f"   ❌ Expected 1 log file in default directory, found {len(log_files)}")
            return False
        
        print("\n✅ Default logs directory test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if logs_dir.exists():
            shutil.rmtree(logs_dir)


def test_custom_logs_directory():
    """Test that custom logs directory is used when specified."""
    print("\n🧪 Testing custom logs directory...\n")
    
    # Create a temporary directory for custom logs
    with tempfile.TemporaryDirectory() as tmpdir:
        custom_logs_dir = Path(tmpdir) / "custom_logs"
        
        try:
            # Call setup_logging with custom directory
            setup_logging(logs_dir=str(custom_logs_dir))
            
            # Check that custom logs directory was created
            if custom_logs_dir.exists() and custom_logs_dir.is_dir():
                print(f"   ✅ Custom logs directory created: {custom_logs_dir}")
            else:
                print(f"   ❌ Custom logs directory not created: {custom_logs_dir}")
                return False
            
            # Check that log file exists in custom directory
            log_files = list(custom_logs_dir.glob("mcp_server_*.log"))
            if len(log_files) == 1:
                print(f"   ✅ Log file created in custom directory: {log_files[0].name}")
            else:
                print(f"   ❌ Expected 1 log file in custom directory, found {len(log_files)}")
                return False
            
            print("\n✅ Custom logs directory test passed!")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_nested_logs_directory():
    """Test that nested logs directory paths are created properly."""
    print("\n🧪 Testing nested logs directory path...\n")
    
    # Create a temporary directory for nested logs
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_logs_dir = Path(tmpdir) / "path" / "to" / "nested" / "logs"
        
        try:
            # Call setup_logging with nested directory path
            setup_logging(logs_dir=str(nested_logs_dir))
            
            # Check that nested logs directory was created
            if nested_logs_dir.exists() and nested_logs_dir.is_dir():
                print(f"   ✅ Nested logs directory created: {nested_logs_dir}")
            else:
                print(f"   ❌ Nested logs directory not created: {nested_logs_dir}")
                return False
            
            # Check that log file exists in nested directory
            log_files = list(nested_logs_dir.glob("mcp_server_*.log"))
            if len(log_files) == 1:
                print(f"   ✅ Log file created in nested directory: {log_files[0].name}")
            else:
                print(f"   ❌ Expected 1 log file in nested directory, found {len(log_files)}")
                return False
            
            print("\n✅ Nested logs directory test passed!")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_config_logs_dir():
    """Test that logs_dir is properly included in configuration."""
    print("\n🧪 Testing logs_dir in configuration...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = tmpdir
        
        try:
            # Test 1: Default config should have logs_dir
            config = load_config()
            assert 'logs_dir' in config['server'], "❌ Missing 'logs_dir' in server config"
            assert config['server']['logs_dir'] == 'logs', "❌ Wrong default logs_dir value"
            print("   ✅ Default config has logs_dir field with correct value")
            
            # Test 2: YAML config should override logs_dir
            config_dir = Path(tmpdir) / '.chameleon' / 'config'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.yaml'
            
            yaml_content = """
server:
  logs_dir: "/var/log/chameleon"
"""
            config_file.write_text(yaml_content)
            
            # Reload config
            config = load_config()
            assert config['server']['logs_dir'] == '/var/log/chameleon', "❌ YAML logs_dir not loaded"
            print("   ✅ YAML config properly overrides logs_dir")
            
            print("\n✅ Configuration logs_dir test passed!")
            return True
            
        finally:
            # Restore original HOME
            if original_home:
                os.environ['HOME'] = original_home
            else:
                os.environ.pop('HOME', None)


if __name__ == "__main__":
    print("=" * 60)
    print("Running logs directory configuration tests")
    print("=" * 60)
    
    try:
        success = True
        success = test_default_logs_directory() and success
        success = test_custom_logs_directory() and success
        success = test_nested_logs_directory() and success
        success = test_config_logs_dir() and success
        
        if success:
            print("\n" + "=" * 60)
            print("✅ All logs directory configuration tests passed!")
            print("=" * 60)
            exit(0)
        else:
            print("\n" + "=" * 60)
            print("❌ Some tests failed!")
            print("=" * 60)
            exit(1)
            
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
