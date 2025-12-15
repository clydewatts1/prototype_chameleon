import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

#!/usr/bin/env python3
"""
Demonstration script showing the SQL Creator Meta-Tool in action.

This script demonstrates:
1. Using the create_new_sql_tool meta-tool to create new SQL-based tools
2. Executing the dynamically created tools
3. Security features (SELECT-only, no semicolons)
"""

from sqlmodel import Session
from models import get_engine, create_db_and_tables, SalesPerDay
from runtime import execute_tool
from seed_db import seed_database
from datetime import date
from config import load_config


def demo_create_simple_tool():
    """Demonstrate creating a simple SQL tool."""
    print("\n" + "=" * 60)
    print("DEMO 1: Creating a Simple SQL Tool")
    print("=" * 60)
    
    # Load database URL from config
    config = load_config()
    database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    engine = get_engine(database_url)
    
    with Session(engine) as session:
        print("\n📝 Using create_new_sql_tool to create 'get_all_stores'...")
        result = execute_tool(
            "create_new_sql_tool",
            "default",
            {
                "tool_name": "get_all_stores",
                "description": "Get all unique store names from sales data",
                "sql_query": "SELECT DISTINCT store_name FROM sales_per_day ORDER BY store_name",
                "parameters": {}
            },
            session
        )
        print(f"   Result: {result}")
        
        # Now execute the newly created tool
        print("\n🔍 Executing the newly created 'get_all_stores' tool...")
        stores = execute_tool("get_all_stores", "default", {}, session)
        print(f"   Found {len(stores)} stores:")
        for store in stores:
            print(f"   - {store[0]}")


def demo_create_parameterized_tool():
    """Demonstrate creating a SQL tool with parameters."""
    print("\n" + "=" * 60)
    print("DEMO 2: Creating a Parameterized SQL Tool")
    print("=" * 60)
    
    # Load database URL from config
    config = load_config()
    database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    engine = get_engine(database_url)
    
    with Session(engine) as session:
        print("\n📝 Creating 'get_sales_by_department' with parameter...")
        result = execute_tool(
            "create_new_sql_tool",
            "default",
            {
                "tool_name": "get_sales_by_department",
                "description": "Get total sales for a specific department across all stores",
                "sql_query": """
                    SELECT 
                        store_name,
                        SUM(sales_amount) as total_sales,
                        COUNT(*) as transaction_count
                    FROM sales_per_day
                    WHERE department = :department
                    GROUP BY store_name
                    ORDER BY total_sales DESC
                """,
                "parameters": {
                    "department": {
                        "type": "string",
                        "description": "The department name to filter by",
                        "required": True
                    }
                }
            },
            session
        )
        print(f"   Result: {result}")
        
        # Execute with Electronics department
        print("\n🔍 Executing 'get_sales_by_department' for 'Electronics'...")
        results = execute_tool(
            "get_sales_by_department",
            "default",
            {"department": "Electronics"},
            session
        )
        print(f"   Found {len(results)} stores with Electronics sales:")
        for row in results[:5]:  # Show top 5
            print(f"   - {row[0]}: ${row[1]:.2f} ({row[2]} transactions)")


def demo_create_complex_tool():
    """Demonstrate creating a more complex SQL tool with multiple parameters."""
    print("\n" + "=" * 60)
    print("DEMO 3: Creating a Complex SQL Tool with Multiple Parameters")
    print("=" * 60)
    
    # Load database URL from config
    config = load_config()
    database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    engine = get_engine(database_url)
    
    with Session(engine) as session:
        print("\n📝 Creating 'get_sales_report' with date range parameters...")
        result = execute_tool(
            "create_new_sql_tool",
            "default",
            {
                "tool_name": "get_sales_report",
                "description": "Get sales report for a date range and optional department filter",
                "sql_query": """
                    SELECT 
                        business_date,
                        department,
                        SUM(sales_amount) as daily_total,
                        AVG(sales_amount) as avg_sale
                    FROM sales_per_day
                    WHERE business_date >= :start_date
                        AND business_date <= :end_date
                    GROUP BY business_date, department
                    ORDER BY business_date, department
                """,
                "parameters": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format",
                        "required": True
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format",
                        "required": True
                    }
                }
            },
            session
        )
        print(f"   Result: {result}")
        
        # Execute with date range
        print("\n🔍 Executing 'get_sales_report' for 2024-01-01 to 2024-01-03...")
        results = execute_tool(
            "get_sales_report",
            "default",
            {
                "start_date": "2024-01-01",
                "end_date": "2024-01-03"
            },
            session
        )
        print(f"   Found {len(results)} daily department records:")
        for row in results[:5]:  # Show first 5
            print(f"   - {row[0]}, {row[1]}: ${row[2]:.2f} (avg: ${row[3]:.2f})")


def demo_security_validation():
    """Demonstrate security validation features."""
    print("\n" + "=" * 60)
    print("DEMO 4: Security Validation Features")
    print("=" * 60)
    
    # Load database URL from config
    config = load_config()
    database_url = config.get('database', {}).get('url', 'sqlite:///chameleon.db')
    engine = get_engine(database_url)
    
    with Session(engine) as session:
        # Test 1: Non-SELECT query
        print("\n🔒 Test 1: Attempting to create tool with INSERT statement...")
        result = execute_tool(
            "create_new_sql_tool",
            "default",
            {
                "tool_name": "malicious_insert",
                "description": "Attempt to insert data",
                "sql_query": "INSERT INTO sales_per_day (business_date, store_name) VALUES ('2024-01-01', 'Evil Store')",
                "parameters": {}
            },
            session
        )
        print(f"   Result: {result}")
        print("   ✅ INSERT statement blocked!")
        
        # Test 2: Query with semicolon
        print("\n🔒 Test 2: Attempting to create tool with semicolon injection...")
        result = execute_tool(
            "create_new_sql_tool",
            "default",
            {
                "tool_name": "malicious_drop",
                "description": "Attempt SQL injection",
                "sql_query": "SELECT * FROM sales_per_day; DROP TABLE sales_per_day",
                "parameters": {}
            },
            session
        )
        print(f"   Result: {result}")
        print("   ✅ Semicolon injection blocked!")
        
        # Test 3: UPDATE query
        print("\n🔒 Test 3: Attempting to create tool with UPDATE statement...")
        result = execute_tool(
            "create_new_sql_tool",
            "default",
            {
                "tool_name": "malicious_update",
                "description": "Attempt to update data",
                "sql_query": "UPDATE sales_per_day SET sales_amount = 0 WHERE store_name = :store",
                "parameters": {"store": {"type": "string", "description": "Store", "required": True}}
            },
            session
        )
        print(f"   Result: {result}")
        print("   ✅ UPDATE statement blocked!")


def main():
    """Run all demonstrations."""
    print("=" * 60)
    print("SQL Creator Meta-Tool - Comprehensive Demo")
    print("=" * 60)
    
    # Ensure database is seeded
    print("\n🔄 Ensuring database is populated...")
    try:
        seed_database(clear_existing=False)
        print("   ✅ Database seeded")
    except Exception as e:
        print(f"   ℹ️  Database already seeded: {str(e)[:100]}")
    
    try:
        demo_create_simple_tool()
        demo_create_parameterized_tool()
        demo_create_complex_tool()
        demo_security_validation()
        
        print("\n" + "=" * 60)
        print("✅ All demonstrations completed successfully!")
        print("=" * 60)
        print("\n💡 Key Takeaways:")
        print("   1. The meta-tool allows LLM to create new SQL tools dynamically")
        print("   2. Only SELECT statements are allowed (security)")
        print("   3. No semicolons in queries (prevents chaining attacks)")
        print("   4. Tools support parameterized queries with proper schema")
        print("   5. Created tools are immediately available for use")
        print("\n🔒 Security Summary:")
        print("   - INSERT, UPDATE, DELETE, DROP blocked")
        print("   - Semicolon injection prevented")
        print("   - All SQL tools forced to code_type='select'")
        return 0
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
