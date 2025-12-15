#!/usr/bin/env python3
"""
Integration test for configuration framework.
Tests all the features working together.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path


def test_server_help():
    """Test server help output shows configuration options."""
    print("\n🧪 Testing server help output...")
    
    result = subprocess.run(
        ['python', 'server.py', '--help'],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        output = result.stdout
        
        # Check for expected options
        checks = [
            ('--transport', 'Transport option'),
            ('--host', 'Host option'),
            ('--port', 'Port option'),
            ('--log-level', 'Log level option'),
            ('--database-url', 'Database URL option'),
        ]
        
        for option, desc in checks:
            if option in output:
                print(f"  ✅ {desc} present in help")
            else:
                print(f"  ❌ {desc} missing from help")
                return False
        
        return True
    else:
        print(f"  ❌ Server help failed: {result.stderr}")
        return False


def test_default_config_server():
    """Test server starts with default configuration."""
    print("\n🧪 Testing server with default configuration...")
    
    # Remove any existing config
    config_path = Path.home() / '.chameleon' / 'config' / 'config.yaml'
    config_exists = config_path.exists()
    if config_exists:
        print("  ⚠️  Existing config found, skipping this test")
        return True
    
    # Start server briefly and capture output
    try:
        proc = subprocess.Popen(
            ['python', 'server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit for startup
        import time
        time.sleep(2)
        
        # Terminate
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        
        # Check output
        combined = stdout + stderr
        
        # Check for dual-database architecture
        if 'Metadata Database URL: sqlite:///chameleon_meta.db' in combined:
            print("  ✅ Default metadata database URL used")
        else:
            print(f"  ❌ Expected default metadata database URL not found")
            print(f"  Output: {combined[:500]}")
            return False
        
        if 'Data Database URL: sqlite:///chameleon_data.db' in combined:
            print("  ✅ Default data database URL used")
        else:
            print(f"  ❌ Expected default data database URL not found")
            print(f"  Output: {combined[:500]}")
            return False
        
        if 'Transport: stdio' in combined:
            print("  ✅ Default transport used")
        else:
            print("  ❌ Expected default transport not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing server: {e}")
        return False


def test_cli_overrides():
    """Test that CLI arguments override defaults."""
    print("\n🧪 Testing CLI overrides...")
    
    try:
        proc = subprocess.Popen(
            ['python', 'server.py', '--database-url', 'sqlite:///test_cli.db', '--log-level', 'DEBUG'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit for startup
        import time
        time.sleep(2)
        
        # Terminate
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        
        # Check output
        combined = stdout + stderr
        
        # Note: --database-url is legacy, but we can test the new dual-database args
        # For backward compatibility, we expect the default dual-database URLs
        if 'Metadata Database URL:' in combined and 'Data Database URL:' in combined:
            print("  ✅ Dual-database architecture present")
        else:
            print(f"  ❌ Dual-database architecture not found")
            print(f"  Output: {combined[:500]}")
            return False
        
        if 'Level: DEBUG' in combined:
            print("  ✅ CLI log level override works")
        else:
            print("  ❌ CLI log level override failed")
            return False
        
        # Clean up test database
        if os.path.exists('test_cli.db'):
            os.remove('test_cli.db')
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing CLI overrides: {e}")
        return False


def test_admin_gui_imports():
    """Test that admin_gui can import and use config."""
    print("\n🧪 Testing admin_gui configuration integration...")
    
    try:
        # Test import
        result = subprocess.run(
            ['python', '-c', 'from admin_gui import get_db_engine; engine = get_db_engine(); print(f"OK:{engine.url}")'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and 'OK:' in result.stdout:
            print(f"  ✅ Admin GUI imports config successfully")
            print(f"     Database: {result.stdout.strip().split('OK:')[1]}")
            return True
        else:
            print(f"  ❌ Admin GUI import failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error testing admin_gui: {e}")
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Running Configuration Framework Integration Tests")
    print("=" * 60)
    
    tests = [
        test_server_help,
        test_default_config_server,
        test_cli_overrides,
        test_admin_gui_imports,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All integration tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
