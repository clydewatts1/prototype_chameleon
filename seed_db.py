"""
Database seeder script for inserting sample tools.

This script populates the database with sample tools for testing the MCP server.
"""

import hashlib
from datetime import date, timedelta
from sqlmodel import Session, select
from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry, SalesPerDay, get_engine, create_db_and_tables


def _compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def _clear_database(session: Session) -> None:
    """
    Clear all existing data from the database.
    
    Args:
        session: SQLModel session
    """
    # Delete in order of dependencies
    session.exec(ToolRegistry.__table__.delete())
    session.exec(ResourceRegistry.__table__.delete())
    session.exec(PromptRegistry.__table__.delete())
    session.exec(CodeVault.__table__.delete())
    session.exec(SalesPerDay.__table__.delete())
    session.commit()


def seed_database(database_url: str = "sqlite:///chameleon.db", clear_existing: bool = True):
    """
    Seed the database with sample tools.
    
    Args:
        database_url: Database connection string
        clear_existing: If True, clear existing data before seeding
    """
    # Create engine and tables
    engine = get_engine(database_url)
    create_db_and_tables(engine)
    
    print("=" * 60)
    print("Seeding Database with Sample Tools")
    print("=" * 60)
    
    with Session(engine) as session:
        # Clear existing data if requested
        if clear_existing:
            existing_tools = session.exec(select(ToolRegistry)).first()
            if existing_tools:
                print("\n⚠️  Clearing existing data...")
                _clear_database(session)
                print("✅ Database cleared")
        
        # Sample Tool 1: Greeting function
        greeting_code = """name = arguments.get('name', 'Guest')
result = f'Hello {name}! I am running from the database.'
"""
        greeting_hash = _compute_hash(greeting_code)
        
        print("\n[1] Adding greeting tool...")
        greeting_vault = CodeVault(
            hash=greeting_hash,
            code_blob=greeting_code,
            code_type="python"
        )
        session.add(greeting_vault)
        
        greeting_tool = ToolRegistry(
            tool_name="greet",
            target_persona="default",
            description="Greets a person by name",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the person to greet"
                    }
                },
                "required": ["name"]
            },
            active_hash_ref=greeting_hash
        )
        session.add(greeting_tool)
        print(f"   ✅ Tool 'greet' added (hash: {greeting_hash[:16]}...)")
        
        # Sample Tool 2: Calculator - Add
        add_code = """a = arguments.get('a', 0)
b = arguments.get('b', 0)
result = a + b
"""
        add_hash = _compute_hash(add_code)
        
        print("\n[2] Adding calculator (add) tool...")
        add_vault = CodeVault(
            hash=add_hash,
            code_blob=add_code,
            code_type="python"
        )
        session.add(add_vault)
        
        add_tool = ToolRegistry(
            tool_name="add",
            target_persona="default",
            description="Add two numbers together",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "First number"
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number"
                    }
                },
                "required": ["a", "b"]
            },
            active_hash_ref=add_hash
        )
        session.add(add_tool)
        print(f"   ✅ Tool 'add' added (hash: {add_hash[:16]}...)")
        
        # Sample Tool 3: Calculator - Multiply (for assistant persona)
        multiply_code = """a = arguments.get('a', 1)
b = arguments.get('b', 1)
result = a * b
"""
        multiply_hash = _compute_hash(multiply_code)
        
        print("\n[3] Adding calculator (multiply) tool for assistant persona...")
        multiply_vault = CodeVault(
            hash=multiply_hash,
            code_blob=multiply_code,
            code_type="python"
        )
        session.add(multiply_vault)
        
        multiply_tool = ToolRegistry(
            tool_name="multiply",
            target_persona="assistant",
            description="Multiply two numbers together",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "First number"
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number"
                    }
                },
                "required": ["a", "b"]
            },
            active_hash_ref=multiply_hash
        )
        session.add(multiply_tool)
        print(f"   ✅ Tool 'multiply' added (hash: {multiply_hash[:16]}...)")
        
        # Sample Tool 4: String manipulation - Uppercase
        uppercase_code = """text = arguments.get('text', '')
result = text.upper()
"""
        uppercase_hash = _compute_hash(uppercase_code)
        
        print("\n[4] Adding uppercase tool...")
        uppercase_vault = CodeVault(
            hash=uppercase_hash,
            code_blob=uppercase_code,
            code_type="python"
        )
        session.add(uppercase_vault)
        
        uppercase_tool = ToolRegistry(
            tool_name="uppercase",
            target_persona="default",
            description="Convert text to uppercase",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to convert to uppercase"
                    }
                },
                "required": ["text"]
            },
            active_hash_ref=uppercase_hash
        )
        session.add(uppercase_tool)
        print(f"   ✅ Tool 'uppercase' added (hash: {uppercase_hash[:16]}...)")
        
        # Sample Resource 1: Static welcome message
        print("\n[5] Adding static resource 'welcome_message'...")
        welcome_resource = ResourceRegistry(
            uri_schema="memo://welcome",
            name="welcome_message",
            description="A welcome message for the Chameleon MCP server",
            mime_type="text/plain",
            is_dynamic=False,
            static_content="Welcome to Chameleon!",
            active_hash_ref=None,
            target_persona="default"
        )
        session.add(welcome_resource)
        print(f"   ✅ Resource 'welcome_message' added")
        
        # Sample Prompt 1: Code review prompt
        print("\n[6] Adding prompt 'review_code'...")
        review_code_prompt = PromptRegistry(
            name="review_code",
            description="Generates a code review request prompt",
            template="Please review this code:\n\n{code}",
            arguments_schema={
                "arguments": [
                    {
                        "name": "code",
                        "description": "The code to review",
                        "required": True
                    }
                ]
            },
            target_persona="default"
        )
        session.add(review_code_prompt)
        print(f"   ✅ Prompt 'review_code' added")
        
        # Sample Resource 2: Dynamic resource that generates current timestamp
        print("\n[7] Adding dynamic resource 'server_time'...")
        server_time_code = """from datetime import datetime
result = f"Current server time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
"""
        server_time_hash = _compute_hash(server_time_code)
        
        server_time_vault = CodeVault(
            hash=server_time_hash,
            code_blob=server_time_code,
            code_type="python"
        )
        session.add(server_time_vault)
        
        server_time_resource = ResourceRegistry(
            uri_schema="system://time",
            name="server_time",
            description="Returns the current server time dynamically",
            mime_type="text/plain",
            is_dynamic=True,
            static_content=None,
            active_hash_ref=server_time_hash,
            target_persona="default"
        )
        session.add(server_time_resource)
        print(f"   ✅ Resource 'server_time' added (dynamic, hash: {server_time_hash[:16]}...)")
        
        # Sample Data: sales_per_day table
        print("\n[8] Populating sales_per_day table with sample data...")
        stores = ["Store A", "Store B", "Store C", "Store D"]
        departments = ["Electronics", "Clothing", "Groceries", "Home & Garden", "Sports"]
        
        # Create 20 rows of sales data
        base_date = date(2024, 1, 1)
        for i in range(20):
            sales_record = SalesPerDay(
                business_date=base_date + timedelta(days=i),
                store_name=stores[i % len(stores)],
                department=departments[i % len(departments)],
                sales_amount=round(1000 + (i * 150.75) + ((i % 3) * 500), 2)
            )
            session.add(sales_record)
        print(f"   ✅ Added 20 rows to sales_per_day table")
        
        # Sample Tool using SELECT code_type
        print("\n[9] Adding 'get_sales_summary' tool with SELECT code_type...")
        sales_query_code = """SELECT 
    store_name,
    department,
    SUM(sales_amount) as total_sales,
    COUNT(*) as transaction_count
FROM salesperday
GROUP BY store_name, department
ORDER BY total_sales DESC"""
        sales_query_hash = _compute_hash(sales_query_code)
        
        sales_query_vault = CodeVault(
            hash=sales_query_hash,
            code_blob=sales_query_code,
            code_type="select"
        )
        session.add(sales_query_vault)
        
        sales_tool = ToolRegistry(
            tool_name="get_sales_summary",
            target_persona="default",
            description="Get sales summary grouped by store and department using SQL SELECT",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            active_hash_ref=sales_query_hash
        )
        session.add(sales_tool)
        print(f"   ✅ Tool 'get_sales_summary' added (hash: {sales_query_hash[:16]}...)")
        
        # Sample Resource using SELECT code_type
        print("\n[10] Adding 'sales_report' resource with SELECT code_type...")
        sales_report_code = """SELECT 
    business_date,
    store_name,
    SUM(sales_amount) as daily_total
FROM salesperday
GROUP BY business_date, store_name
ORDER BY business_date DESC
LIMIT 10"""
        sales_report_hash = _compute_hash(sales_report_code)
        
        sales_report_vault = CodeVault(
            hash=sales_report_hash,
            code_blob=sales_report_code,
            code_type="select"
        )
        session.add(sales_report_vault)
        
        sales_report_resource = ResourceRegistry(
            uri_schema="data://sales/recent",
            name="sales_report",
            description="Recent sales report showing daily totals by store (last 10 days)",
            mime_type="text/plain",
            is_dynamic=True,
            static_content=None,
            active_hash_ref=sales_report_hash,
            target_persona="default"
        )
        session.add(sales_report_resource)
        print(f"   ✅ Resource 'sales_report' added (dynamic, hash: {sales_report_hash[:16]}...)")
        
        # Commit all changes
        session.commit()
        
        print("\n" + "=" * 60)
        print("Database seeding completed successfully!")
        print("=" * 60)
        
        # Show summary
        print("\nTools added:")
        print("  - greet (persona: default)")
        print("  - add (persona: default)")
        print("  - multiply (persona: assistant)")
        print("  - uppercase (persona: default)")
        print("  - get_sales_summary (persona: default, code_type: select)")
        print("\nResources added:")
        print("  - welcome_message (static, URI: memo://welcome)")
        print("  - server_time (dynamic, URI: system://time, code_type: python)")
        print("  - sales_report (dynamic, URI: data://sales/recent, code_type: select)")
        print("\nPrompts added:")
        print("  - review_code")
        print("\nSample Data:")
        print("  - sales_per_day table: 20 rows")
        print("\nYou can now run the MCP server with: python server.py")


if __name__ == "__main__":
    seed_database()
