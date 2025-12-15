#!/usr/bin/env python3
"""
Quick integration test to verify the runtime works correctly with actual database.
"""

from sqlmodel import Session
from models import get_engine
from runtime import execute_tool
from seed_db import seed_database
from config import load_config


def test_integration():
    """Test that runtime works correctly with seeded database."""
    print("\n" + "=" * 60)
    print("Integration Test: Runtime with Seeded Database")
    print("=" * 60)
    
    # Seed the database
    print("\n1. Seeding database...")
    seed_database(clear_existing=True)
    
    # Load database URL from config
    config = load_config()
    database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    engine = get_engine(database_url)
    
    with Session(engine) as session:
        # Test 1: Python tool execution (existing functionality)
        print("\n2. Testing Python tool execution (greet)...")
        result = execute_tool("greet", "default", {"name": "Alice"}, session)
        assert "Alice" in result, f"Expected 'Alice' in result, got: {result}"
        print(f"   ✅ Result: {result}")
        
        # Test 2: SQL tool without parameters (get_sales_summary)
        print("\n3. Testing SQL tool without parameters (get_sales_summary)...")
        result = execute_tool("get_sales_summary", "default", {}, session)
        assert len(result) > 0, "Expected results from get_sales_summary"
        print(f"   ✅ Found {len(result)} store/department combinations")
        
        # Test 3: SQL tool with filter (get_sales_summary with store)
        print("\n4. Testing SQL tool with filter (get_sales_summary with store_name)...")
        result = execute_tool("get_sales_summary", "default", 
                            {"store_name": "Store A"}, session)
        assert len(result) > 0, "Expected results for Store A"
        for row in result:
            assert row[0] == "Store A", f"Expected Store A, got {row[0]}"
        print(f"   ✅ Found {len(result)} departments in Store A")
        
        # Test 4: SQL tool with date filter (get_sales_by_category)
        print("\n5. Testing SQL tool with date filter (get_sales_by_category)...")
        result = execute_tool("get_sales_by_category", "default", 
                            {"start_date": "2024-01-05", "end_date": "2024-01-10"}, 
                            session)
        assert len(result) > 0, "Expected results for date range"
        print(f"   ✅ Found {len(result)} categories in date range")
        
        # Test 5: Python tool with calculation (add)
        print("\n6. Testing Python tool with calculation (add)...")
        result = execute_tool("add", "default", {"a": 15, "b": 27}, session)
        assert result == 42, f"Expected 42, got {result}"
        print(f"   ✅ Result: 15 + 27 = {result}")
        
    print("\n" + "=" * 60)
    print("✅ All integration tests passed!")
    print("=" * 60)
    return 0


if __name__ == '__main__':
    import sys
    try:
        sys.exit(test_integration())
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
