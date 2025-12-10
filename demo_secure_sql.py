#!/usr/bin/env python3
"""
Demonstration script showing the new secure SQL execution with Jinja2 + SQLAlchemy.

This script demonstrates:
1. How to use the get_sales_summary tool with optional filters
2. How to use the get_sales_by_category tool with date filters
3. The security features in action
"""

from sqlmodel import Session
from models import get_engine, create_db_and_tables
from runtime import execute_tool
from seed_db import seed_database


def demo_sales_summary():
    """Demonstrate the get_sales_summary tool."""
    print("\n" + "=" * 60)
    print("DEMO 1: Sales Summary with Optional Filtering")
    print("=" * 60)
    
    engine = get_engine("sqlite:///chameleon.db")
    
    with Session(engine) as session:
        # Test 1: Get all sales summary
        print("\n📊 Getting sales summary for all stores and departments...")
        result = execute_tool("get_sales_summary", "default", {}, session)
        print(f"   Found {len(result)} store/department combinations")
        for row in result[:3]:  # Show first 3
            print(f"   - {row[0]}, {row[1]}: ${row[2]:.2f} ({row[3]} transactions)")
        
        # Test 2: Filter by store
        print("\n📊 Getting sales summary for 'Store A' only...")
        result = execute_tool("get_sales_summary", "default", 
                            {"store_name": "Store A"}, session)
        print(f"   Found {len(result)} departments in Store A")
        for row in result:
            print(f"   - {row[1]}: ${row[2]:.2f} ({row[3]} transactions)")
        
        # Test 3: Filter by department
        print("\n📊 Getting sales summary for 'Electronics' department only...")
        result = execute_tool("get_sales_summary", "default", 
                            {"department": "Electronics"}, session)
        print(f"   Found {len(result)} stores selling Electronics")
        for row in result:
            print(f"   - {row[0]}: ${row[2]:.2f} ({row[3]} transactions)")
        
        # Test 4: Filter by both
        print("\n📊 Getting sales summary for 'Store B' and 'Clothing' department...")
        result = execute_tool("get_sales_summary", "default", 
                            {"store_name": "Store B", "department": "Clothing"}, 
                            session)
        print(f"   Found {len(result)} matching combination(s)")
        for row in result:
            print(f"   - {row[0]}, {row[1]}: ${row[2]:.2f} ({row[3]} transactions)")


def demo_sales_by_category():
    """Demonstrate the get_sales_by_category tool with date filtering."""
    print("\n" + "=" * 60)
    print("DEMO 2: Sales by Category with Date Filtering")
    print("=" * 60)
    
    engine = get_engine("sqlite:///chameleon.db")
    
    with Session(engine) as session:
        # Test 1: Get all sales by category
        print("\n📊 Getting sales by category (all dates)...")
        result = execute_tool("get_sales_by_category", "default", {}, session)
        print(f"   Found {len(result)} categories")
        for row in result:
            print(f"   - {row[0]}: Total=${row[1]:.2f}, Avg=${row[2]:.2f}")
        
        # Test 2: Filter by date range
        print("\n📊 Getting sales by category for dates 2024-01-05 to 2024-01-10...")
        result = execute_tool("get_sales_by_category", "default", 
                            {"start_date": "2024-01-05", "end_date": "2024-01-10"}, 
                            session)
        print(f"   Found {len(result)} categories")
        for row in result:
            print(f"   - {row[0]}: Total=${row[1]:.2f}, Avg=${row[2]:.2f}")
        
        # Test 3: Filter by minimum amount
        print("\n📊 Getting sales by category with min amount >= $2000...")
        result = execute_tool("get_sales_by_category", "default", 
                            {"min_amount": 2000}, session)
        if result:
            print(f"   Found {len(result)} categories meeting criteria")
            for row in result:
                print(f"   - {row[0]}: Total=${row[1]:.2f}, Avg=${row[2]:.2f}")
        else:
            print("   No categories found with sales >= $2000 per transaction")


def demo_security_features():
    """Demonstrate security features."""
    print("\n" + "=" * 60)
    print("DEMO 3: Security Features")
    print("=" * 60)
    
    print("\n🔒 Security Features Implemented:")
    print("   1. Jinja2 templates for SQL STRUCTURE only")
    print("      - Optional WHERE clauses")
    print("      - Conditional table joins")
    print("      - Dynamic ORDER BY")
    print("")
    print("   2. SQLAlchemy parameter binding for VALUES")
    print("      - All user inputs use :param_name syntax")
    print("      - Values are passed separately from query")
    print("      - Prevents SQL injection attacks")
    print("")
    print("   3. Single statement validation")
    print("      - Only one SQL statement allowed")
    print("      - Prevents chaining attacks (e.g., SELECT...; DROP TABLE...)")
    print("")
    print("   4. Read-only validation")
    print("      - Only SELECT statements allowed")
    print("      - Blocks INSERT, UPDATE, DELETE, DROP, ALTER, etc.")
    print("")
    print("✅ Example secure SQL template:")
    print("""
    SELECT * FROM items
    WHERE 1=1
    {% if arguments.category %}
      AND category = :category
    {% endif %}
    {% if arguments.min_price %}
      AND price >= :min_price
    {% endif %}
    """)
    print("\n   Notice:")
    print("   - Jinja2 {% if %} controls query STRUCTURE")
    print("   - :category and :min_price are SQLAlchemy PARAMETERS")
    print("   - Values never directly interpolated into SQL string")


def main():
    """Run all demonstrations."""
    print("=" * 60)
    print("Chameleon MCP Server - Secure SQL Execution Demo")
    print("=" * 60)
    
    # Ensure database is seeded (will skip if already seeded)
    print("\n🔄 Ensuring database is populated...")
    try:
        seed_database(clear_existing=False)
    except Exception as e:
        # Database might already be seeded, that's okay
        print(f"   ℹ️  Database already seeded: {str(e)[:100]}")
    
    try:
        demo_sales_summary()
        demo_sales_by_category()
        demo_security_features()
        
        print("\n" + "=" * 60)
        print("✅ All demonstrations completed successfully!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
