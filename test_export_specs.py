"""
Test script for export_specs.py to validate database export functionality.
"""

import os
import yaml
from sqlmodel import Session, select
from models import get_engine, create_db_and_tables, ToolRegistry, ResourceRegistry, PromptRegistry, CodeVault
from load_specs import load_specs_from_yaml
from export_specs import export_specs, LiteralString


def convert_literal_strings(obj):
    """Recursively convert LiteralString instances to regular strings."""
    if isinstance(obj, LiteralString):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_literal_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_literal_strings(item) for item in obj]
    else:
        return obj


def test_export_specs():
    """Test the export process and validate exported data."""
    test_db_url = "sqlite:///test_export_chameleon.db"
    test_yaml = "specs.yaml"
    
    # Clean up any existing test database
    if os.path.exists("test_export_chameleon.db"):
        os.remove("test_export_chameleon.db")
    
    print("\n🧪 Running export_specs.py tests...\n")
    
    try:
        # Step 1: Load test data from specs.yaml
        print("1️⃣  Loading test data from specs.yaml...")
        success = load_specs_from_yaml(test_yaml, test_db_url, clean=True)
        if not success:
            print("❌ Failed to load specs.yaml")
            return False
        
        # Step 2: Export the data
        print("\n2️⃣  Exporting specs from database...")
        exported_specs = export_specs(test_db_url)
        
        if not exported_specs:
            print("❌ Export returned empty specs")
            return False
        
        print(f"✅ Exported specs contains {len(exported_specs.get('tools', []))} tools, " +
              f"{len(exported_specs.get('resources', []))} resources, " +
              f"{len(exported_specs.get('prompts', []))} prompts")
        
        # Step 3: Validate exported tools
        print("\n3️⃣  Validating exported tools...")
        tools = exported_specs.get('tools', [])
        expected_tool_names = ['greet', 'add', 'list_all_tools']
        found_tool_names = [t['name'] for t in tools]
        
        for tool_name in expected_tool_names:
            if tool_name in found_tool_names:
                print(f"   ✅ Tool '{tool_name}' found")
            else:
                print(f"   ❌ Tool '{tool_name}' not found")
                return False
        
        # Validate tool structure
        for tool in tools:
            required_fields = ['name', 'persona', 'description', 'code_type', 'code', 'input_schema']
            for field in required_fields:
                if field not in tool:
                    print(f"   ❌ Tool '{tool['name']}' missing field '{field}'")
                    return False
            
            # Check that code is a string with content
            if not isinstance(tool['code'], str) or len(tool['code']) == 0:
                print(f"   ❌ Tool '{tool['name']}' has invalid code")
                return False
            
            # Check that input_schema is a dict
            if not isinstance(tool['input_schema'], dict):
                print(f"   ❌ Tool '{tool['name']}' has invalid input_schema")
                return False
        
        print("   ✅ All tools have correct structure")
        
        # Step 4: Validate exported resources
        print("\n4️⃣  Validating exported resources...")
        resources = exported_specs.get('resources', [])
        expected_resource_names = ['welcome_message', 'server_time']
        found_resource_names = [r['name'] for r in resources]
        
        for resource_name in expected_resource_names:
            if resource_name in found_resource_names:
                print(f"   ✅ Resource '{resource_name}' found")
            else:
                print(f"   ❌ Resource '{resource_name}' not found")
                return False
        
        # Validate resource structure
        for resource in resources:
            required_fields = ['uri', 'name', 'persona', 'description', 'mime_type', 'is_dynamic']
            for field in required_fields:
                if field not in resource:
                    print(f"   ❌ Resource '{resource['name']}' missing field '{field}'")
                    return False
            
            # Check dynamic vs static content
            if resource['is_dynamic']:
                if 'code' not in resource:
                    print(f"   ❌ Dynamic resource '{resource['name']}' missing code")
                    return False
            else:
                if 'static_content' not in resource:
                    print(f"   ❌ Static resource '{resource['name']}' missing static_content")
                    return False
        
        print("   ✅ All resources have correct structure")
        
        # Step 5: Validate exported prompts
        print("\n5️⃣  Validating exported prompts...")
        prompts = exported_specs.get('prompts', [])
        expected_prompt_names = ['review_code']
        found_prompt_names = [p['name'] for p in prompts]
        
        for prompt_name in expected_prompt_names:
            if prompt_name in found_prompt_names:
                print(f"   ✅ Prompt '{prompt_name}' found")
            else:
                print(f"   ❌ Prompt '{prompt_name}' not found")
                return False
        
        # Validate prompt structure
        for prompt in prompts:
            required_fields = ['name', 'persona', 'description', 'template', 'arguments_schema']
            for field in required_fields:
                if field not in prompt:
                    print(f"   ❌ Prompt '{prompt['name']}' missing field '{field}'")
                    return False
        
        print("   ✅ All prompts have correct structure")
        
        # Step 6: Test persona filtering
        print("\n6️⃣  Testing persona filtering...")
        filtered_specs = export_specs(test_db_url, persona='default')
        
        filtered_tools = filtered_specs.get('tools', [])
        if all(t['persona'] == 'default' for t in filtered_tools):
            print(f"   ✅ Persona filter works ({len(filtered_tools)} tools with 'default' persona)")
        else:
            print("   ❌ Persona filter not working correctly")
            return False
        
        # Step 7: Validate YAML serialization
        print("\n7️⃣  Validating YAML serialization...")
        try:
            # Convert LiteralString instances to regular strings for safe_dump
            converted_specs = convert_literal_strings(exported_specs)
            yaml_str = yaml.safe_dump(converted_specs, default_flow_style=False, sort_keys=False)
            # Try to parse it back
            parsed = yaml.safe_load(yaml_str)
            if parsed:
                print("   ✅ Exported specs can be serialized and parsed as YAML")
            else:
                print("   ❌ Parsed YAML is empty")
                return False
        except Exception as e:
            print(f"   ❌ YAML serialization failed: {e}")
            return False
        
        # Step 8: Test round-trip (export -> save -> load -> export)
        print("\n8️⃣  Testing round-trip export...")
        temp_yaml = "temp_export_test.yaml"
        try:
            # Save exported specs to YAML using safe_dump, converting LiteralStrings
            converted_specs = convert_literal_strings(exported_specs)
            with open(temp_yaml, 'w') as f:
                yaml.safe_dump(converted_specs, f, default_flow_style=False, sort_keys=False)
            
            # Load into a new database
            test_db_url2 = "sqlite:///test_export_chameleon2.db"
            if os.path.exists("test_export_chameleon2.db"):
                os.remove("test_export_chameleon2.db")
            
            success = load_specs_from_yaml(temp_yaml, test_db_url2, clean=True)
            if not success:
                print("   ❌ Failed to load exported YAML")
                return False
            
            # Export again
            re_exported_specs = export_specs(test_db_url2)
            
            # Compare counts
            if (len(re_exported_specs.get('tools', [])) == len(exported_specs.get('tools', [])) and
                len(re_exported_specs.get('resources', [])) == len(exported_specs.get('resources', [])) and
                len(re_exported_specs.get('prompts', [])) == len(exported_specs.get('prompts', []))):
                print("   ✅ Round-trip successful - data preserved")
            else:
                print("   ❌ Round-trip failed - data mismatch")
                return False
            
        finally:
            # Clean up
            if os.path.exists(temp_yaml):
                os.remove(temp_yaml)
            if os.path.exists("test_export_chameleon2.db"):
                os.remove("test_export_chameleon2.db")
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! export_specs.py is working correctly.")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test database
        if os.path.exists("test_export_chameleon.db"):
            try:
                os.remove("test_export_chameleon.db")
            except PermissionError:
                print("⚠️  Could not delete test database (file in use)")


if __name__ == "__main__":
    success = test_export_specs()
    exit(0 if success else 1)
