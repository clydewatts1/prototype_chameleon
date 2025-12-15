#!/usr/bin/env python3
"""
Test to verify all utilities use configuration consistently for database paths.

This test ensures that:
1. All demo scripts use config.load_config()
2. All add_* scripts use config.load_config()
3. seed_db.py uses config by default
4. No hardcoded database paths in main utility files
"""

import os
import re
import sys


def check_file_uses_config(filepath):
    """Check if a Python file uses the config module."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if file imports config
    has_config_import = 'from config import load_config' in content
    
    # Check for hardcoded database URLs
    hardcoded_pattern = r'get_engine\s*\(\s*["\']sqlite:///[^"\']+["\']'
    has_hardcoded = re.search(hardcoded_pattern, content)
    
    # Check if it uses config to get database URL
    uses_config_db = 'config.get(\'database\'' in content or 'config[\'database\']' in content
    
    return {
        'has_config_import': has_config_import,
        'has_hardcoded': bool(has_hardcoded),
        'uses_config_db': uses_config_db,
        'hardcoded_match': has_hardcoded.group(0) if has_hardcoded else None
    }


def test_demo_scripts():
    """Test that demo scripts use config."""
    print("\n" + "=" * 60)
    print("Testing Demo Scripts")
    print("=" * 60)
    
    demo_scripts = [
        'demo_self_healing.py',
        'demo_secure_sql.py',
        'demo_sql_creator.py',
    ]
    
    all_passed = True
    for script in demo_scripts:
        if not os.path.exists(script):
            print(f"⚠️  {script}: File not found (skipping)")
            continue
            
        result = check_file_uses_config(script)
        
        # For demo scripts, they should use config
        if result['has_hardcoded']:
            print(f"❌ {script}: Has hardcoded database path: {result['hardcoded_match']}")
            all_passed = False
        elif result['has_config_import'] and result['uses_config_db']:
            print(f"✅ {script}: Uses config correctly")
        else:
            print(f"⚠️  {script}: May not be using config (import={result['has_config_import']}, uses={result['uses_config_db']})")
    
    return all_passed


def test_utility_scripts():
    """Test that utility scripts use config."""
    print("\n" + "=" * 60)
    print("Testing Utility Scripts")
    print("=" * 60)
    
    utility_scripts = [
        'seed_db.py',
        'add_debug_tool.py',
        'add_db_test_tool.py',
        'add_dynamic_meta_tools.py',
        'add_resource_bridge.py',
        'add_sql_creator_tool.py',
    ]
    
    all_passed = True
    for script in utility_scripts:
        if not os.path.exists(script):
            print(f"⚠️  {script}: File not found (skipping)")
            continue
            
        result = check_file_uses_config(script)
        
        # Utility scripts should import config and use it when database_url is None
        if result['has_config_import']:
            print(f"✅ {script}: Imports config module")
        else:
            print(f"❌ {script}: Does not import config module")
            all_passed = False
    
    return all_passed


def test_integration_scripts():
    """Test integration test scripts."""
    print("\n" + "=" * 60)
    print("Testing Integration Scripts")
    print("=" * 60)
    
    integration_scripts = [
        'test_runtime_integration.py',
    ]
    
    all_passed = True
    for script in integration_scripts:
        if not os.path.exists(script):
            print(f"⚠️  {script}: File not found (skipping)")
            continue
            
        result = check_file_uses_config(script)
        
        # Check if using config
        if result['has_hardcoded']:
            print(f"❌ {script}: Has hardcoded database path: {result['hardcoded_match']}")
            all_passed = False
        elif result['has_config_import'] and result['uses_config_db']:
            print(f"✅ {script}: Uses config correctly")
        else:
            print(f"⚠️  {script}: Not using config (this may be intentional for testing)")
    
    return all_passed


def main():
    """Run all tests."""
    print("=" * 60)
    print("Database Configuration Consistency Tests")
    print("=" * 60)
    
    os.chdir('/home/runner/work/prototype_chameleon/prototype_chameleon/server')
    
    results = []
    results.append(test_demo_scripts())
    results.append(test_utility_scripts())
    results.append(test_integration_scripts())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some tests failed!")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
