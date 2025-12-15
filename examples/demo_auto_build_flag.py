import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

#!/usr/bin/env python3
"""
Demo script to showcase the is_auto_created flag feature.

This script demonstrates:
1. Loading system tools from YAML (is_auto_created=False)
2. Creating auto-built tools via the SQL Creator meta-tool (is_auto_created=True)
3. Listing tools to see the [AUTO-BUILD] prefix on auto-created tools
"""

import os
import sys
import tempfile
from pathlib import Path

from sqlmodel import Session

from add_sql_creator_tool import register_sql_creator_tool
from load_specs import load_specs_from_yaml
from models import get_engine, create_db_and_tables
from runtime import execute_tool, list_tools_for_persona


def main():
    """Main demo function."""
    print("=" * 70)
    print("DEMO: Auto-Build Flag Feature")
    print("=" * 70)
    print("\nThis demo shows how the system distinguishes between:")
    print("  • SYSTEM TOOLS (loaded from YAML) - no prefix")
    print("  • AUTO-BUILT TOOLS (created by LLM) - [AUTO-BUILD] prefix")
    print()
    
    # Create temporary database and YAML file
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    db_url = f"sqlite:///{temp_db.name}"
    
    temp_yaml = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml_content = """
tools:
  - name: get_sales_total
    description: Get total sales amount across all stores
    persona: default
    code_type: select
    code: |
      SELECT SUM(sales_amount) as total_sales
      FROM sales_per_day
    input_schema:
      type: object
      properties: {}
      
  - name: get_sales_by_department
    description: Get sales filtered by department
    persona: default
    code_type: select
    code: |
      SELECT business_date, store_name, sales_amount
      FROM sales_per_day
      WHERE department = :department
    input_schema:
      type: object
      properties:
        department:
          type: string
          description: Department name
      required:
        - department
"""
    temp_yaml.write(yaml_content)
    temp_yaml.close()
    
    try:
        print("\n" + "=" * 70)
        print("STEP 1: Loading System Tools from YAML")
        print("=" * 70)
        
        # Load specs from YAML
        success = load_specs_from_yaml(temp_yaml.name, db_url, clean=True)
        
        if not success:
            print("❌ Failed to load specs from YAML")
            return 1
        
        print("\n✅ Two system tools loaded from YAML")
        
        print("\n" + "=" * 70)
        print("STEP 2: Register SQL Creator Meta-Tool")
        print("=" * 70)
        
        # Register the SQL creator meta-tool
        register_sql_creator_tool(database_url=db_url)
        
        print("\n✅ SQL Creator Meta-Tool registered")
        
        print("\n" + "=" * 70)
        print("STEP 3: Create Auto-Built Tools using Meta-Tool")
        print("=" * 70)
        
        engine = get_engine(db_url)
        with Session(engine) as session:
            # Create first auto-built tool
            print("\nCreating auto-built tool #1...")
            result1 = execute_tool(
                'create_new_sql_tool',
                'default',
                {
                    'tool_name': 'get_high_value_sales',
                    'description': 'Get sales records above a specified threshold',
                    'sql_query': 'SELECT * FROM sales_per_day WHERE sales_amount > :threshold',
                    'parameters': {
                        'threshold': {
                            'type': 'number',
                            'description': 'Minimum sales amount',
                            'required': True
                        }
                    }
                },
                session
            )
            print(f"  {result1}")
            
            # Create second auto-built tool
            print("\nCreating auto-built tool #2...")
            result2 = execute_tool(
                'create_new_sql_tool',
                'default',
                {
                    'tool_name': 'get_sales_by_date_range',
                    'description': 'Get sales within a date range',
                    'sql_query': 'SELECT * FROM sales_per_day WHERE business_date BETWEEN :start_date AND :end_date',
                    'parameters': {
                        'start_date': {
                            'type': 'string',
                            'description': 'Start date (YYYY-MM-DD)',
                            'required': True
                        },
                        'end_date': {
                            'type': 'string',
                            'description': 'End date (YYYY-MM-DD)',
                            'required': True
                        }
                    }
                },
                session
            )
            print(f"  {result2}")
            
            print("\n✅ Two auto-built tools created")
            
            print("\n" + "=" * 70)
            print("STEP 4: List All Tools for 'default' Persona")
            print("=" * 70)
            print("\nNotice the [AUTO-BUILD] prefix on LLM-created tools:\n")
            
            # List all tools
            tools = list_tools_for_persona('default', session)
            
            system_tools = []
            auto_tools = []
            
            for tool in tools:
                is_auto = tool['description'].startswith('[AUTO-BUILD]')
                
                if tool['name'] == 'create_new_sql_tool':
                    # Skip the meta-tool from display
                    continue
                
                if is_auto:
                    auto_tools.append(tool)
                else:
                    system_tools.append(tool)
            
            print("🔧 SYSTEM TOOLS (Prebuilt):")
            print("-" * 70)
            for i, tool in enumerate(system_tools, 1):
                print(f"{i}. {tool['name']}")
                print(f"   Description: {tool['description']}")
                print(f"   Parameters: {list(tool['input_schema'].get('properties', {}).keys())}")
                print()
            
            print("🤖 AUTO-BUILT TOOLS (LLM-Created):")
            print("-" * 70)
            for i, tool in enumerate(auto_tools, 1):
                print(f"{i}. {tool['name']}")
                print(f"   Description: {tool['description']}")
                print(f"   Parameters: {list(tool['input_schema'].get('properties', {}).keys())}")
                print()
            
            print("=" * 70)
            print("SUMMARY")
            print("=" * 70)
            print(f"✅ System Tools: {len(system_tools)} (loaded from YAML)")
            print(f"✅ Auto-Built Tools: {len(auto_tools)} (created by LLM)")
            print(f"✅ Total Tools: {len(system_tools) + len(auto_tools)}")
            print(f"\n✅ Auto-built tools are clearly marked with [AUTO-BUILD] prefix")
            print(f"✅ System tools have no prefix")
            print()
            
            return 0
            
    finally:
        os.unlink(temp_db.name)
        os.unlink(temp_yaml.name)


if __name__ == '__main__':
    sys.exit(main())
