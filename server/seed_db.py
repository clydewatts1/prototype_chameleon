"""
Database seeder script for inserting sample tools.

This script populates the database with sample tools for testing the MCP server.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from common.hash_utils import compute_hash
from datetime import date, timedelta
from sqlmodel import Session, select
from models import CodeVault, ToolRegistry, ResourceRegistry, PromptRegistry, SalesPerDay, get_engine, create_db_and_tables, METADATA_MODELS, DATA_MODELS
from config import load_config




def _clear_metadata_database(session: Session) -> None:
    """
    Clear all existing metadata from the database.
    
    Args:
        session: SQLModel session for metadata database
    """
    # Delete in order of dependencies
    session.exec(ToolRegistry.__table__.delete())
    session.exec(ResourceRegistry.__table__.delete())
    session.exec(PromptRegistry.__table__.delete())
    session.exec(CodeVault.__table__.delete())
    session.commit()


def _clear_data_database(session: Session) -> None:
    """
    Clear all existing data from the data database.
    
    Args:
        session: SQLModel session for data database
    """
    # Delete in order of dependencies
    session.exec(SalesPerDay.__table__.delete())
    session.commit()


def seed_database(metadata_database_url: str = None, data_database_url: str = None, clear_existing: bool = True):
    """
    Seed the databases with sample tools and data.
    
    Args:
        metadata_database_url: Metadata database connection string. If None, loads from config.
        data_database_url: Data database connection string. If None, loads from config.
        clear_existing: If True, clear existing data before seeding
    """
    # Load configuration if URLs not provided
    config = load_config()
    if metadata_database_url is None:
        metadata_database_url = config.get('metadata_database', {}).get('url', 'sqlite:///chameleon_meta.db')
    if data_database_url is None:
        data_database_url = config.get('data_database', {}).get('url', 'sqlite:///chameleon_data.db')
    
    # Create engines and tables
    meta_engine = get_engine(metadata_database_url)
    create_db_and_tables(meta_engine, METADATA_MODELS)
    
    # Try to create data engine, but allow failure
    data_engine = None
    try:
        data_engine = get_engine(data_database_url)
        create_db_and_tables(data_engine, DATA_MODELS)
    except Exception as e:
        print(f"⚠️  Warning: Could not connect to data database: {e}")
        print("⚠️  Continuing with metadata seeding only...")
    
    print("=" * 60)
    print("Seeding Databases with Sample Tools and Data")
    print("=" * 60)
    print(f"Metadata DB: {metadata_database_url}")
    print(f"Data DB: {data_database_url}")
    print("=" * 60)
    
    # Seed metadata database
    with Session(meta_engine) as session:
        # Clear existing data if requested
        if clear_existing:
            existing_tools = session.exec(select(ToolRegistry)).first()
            if existing_tools:
                print("\n⚠️  Clearing existing metadata...")
                _clear_metadata_database(session)
                print("✅ Metadata cleared")
        
        # Sample Tool 1: Greeting function
        greeting_code = """from base import ChameleonTool

class GreetingTool(ChameleonTool):
    def run(self, arguments):
        name = arguments.get('name', 'Guest')
        self.log(f"Greeting {name}")
        return f'Hello {name}! I am running from the database.'

    def complete(self, argument, value):
        if argument != 'name':
            return []
        prefix = (value or '').lower()
        candidates = [
            'Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank',
            'Grace', 'Heidi', 'Ivan', 'Judy'
        ]
        return [c for c in candidates if c.lower().startswith(prefix)]
"""
        greeting_hash = compute_hash(greeting_code)
        
        print("\n[1] Adding greeting tool...")
        greeting_vault = CodeVault(
            hash=greeting_hash,
            code_blob=greeting_code,
            code_type="python"
        )
        session.add(greeting_vault)
        
        greeting_tool = ToolRegistry(
            tool_name="utility_greet",
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
            active_hash_ref=greeting_hash,
            group="utility"
        )
        session.add(greeting_tool)
        print(f"   OK Tool 'utility_greet' added (hash: {greeting_hash[:16]}...)")
        
        # Sample Tool 2: Calculator - Add
        add_code = """from base import ChameleonTool

class AddTool(ChameleonTool):
    def run(self, arguments):
        a = arguments.get('a', 0)
        b = arguments.get('b', 0)
        self.log(f"Adding {a} + {b}")
        return a + b
"""
        add_hash = compute_hash(add_code)
        
        print("\n[2] Adding calculator (add) tool...")
        add_vault = CodeVault(
            hash=add_hash,
            code_blob=add_code,
            code_type="python"
        )
        session.add(add_vault)
        
        add_tool = ToolRegistry(
            tool_name="math_add",
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
            active_hash_ref=add_hash,
            group="math"
        )
        session.add(add_tool)
        print(f"   OK Tool 'math_add' added (hash: {add_hash[:16]}...)")
        
        # Sample Tool 3: Calculator - Multiply (for assistant persona)
        multiply_code = """from base import ChameleonTool

class MultiplyTool(ChameleonTool):
    def run(self, arguments):
        a = arguments.get('a', 1)
        b = arguments.get('b', 1)
        self.log(f"Multiplying {a} * {b}")
        return a * b
"""
        multiply_hash = compute_hash(multiply_code)
        
        print("\n[3] Adding calculator (multiply) tool for assistant persona...")
        multiply_vault = CodeVault(
            hash=multiply_hash,
            code_blob=multiply_code,
            code_type="python"
        )
        session.add(multiply_vault)
        
        multiply_tool = ToolRegistry(
            tool_name="math_multiply",
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
            active_hash_ref=multiply_hash,
            group="math"
        )
        session.add(multiply_tool)
        print(f"   OK Tool 'math_multiply' added (hash: {multiply_hash[:16]}...)")
        
        # Sample Tool 4: String manipulation - Uppercase
        uppercase_code = """from base import ChameleonTool

class UppercaseTool(ChameleonTool):
    def run(self, arguments):
        text = arguments.get('text', '')
        self.log(f"Converting to uppercase: {text}")
        return text.upper()
"""
        uppercase_hash = compute_hash(uppercase_code)
        
        print("\n[4] Adding uppercase tool...")
        uppercase_vault = CodeVault(
            hash=uppercase_hash,
            code_blob=uppercase_code,
            code_type="python"
        )
        session.add(uppercase_vault)
        
        uppercase_tool = ToolRegistry(
            tool_name="utility_uppercase",
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
            active_hash_ref=uppercase_hash,
            group="utility"
        )
        session.add(uppercase_tool)
        print(f"   OK Tool 'utility_uppercase' added (hash: {uppercase_hash[:16]}...)")
        
        # Sample Resource 1: Static welcome message
        print("\n[5] Adding static resource 'general_welcome_message'...")
        welcome_resource = ResourceRegistry(
            uri_schema="memo://welcome",
            name="general_welcome_message",
            description="A welcome message for the Chameleon MCP server",
            mime_type="text/plain",
            is_dynamic=False,
            static_content="Welcome to Chameleon!",
            active_hash_ref=None,
            target_persona="default",
            group="general"
        )
        session.add(welcome_resource)
        print(f"   OK Resource 'general_welcome_message' added")
        
        # Sample Prompt 1: Code review prompt
        print("\n[6] Adding prompt 'developer_review_code'...")
        review_code_prompt = PromptRegistry(
            name="developer_review_code",
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
            target_persona="default",
            group="developer"
        )
        session.add(review_code_prompt)
        print(f"   OK Prompt 'developer_review_code' added")
        
        # Sample Resource 2: Dynamic resource that generates current timestamp
        print("\n[7] Adding dynamic resource 'server_time'...")
        server_time_code = """from base import ChameleonTool
from datetime import datetime

class ServerTimeTool(ChameleonTool):
    def run(self, arguments):
        self.log("Getting current server time")
        return f"Current server time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
"""
        server_time_hash = compute_hash(server_time_code)
        
        server_time_vault = CodeVault(
            hash=server_time_hash,
            code_blob=server_time_code,
            code_type="python"
        )
        session.add(server_time_vault)
        
        server_time_resource = ResourceRegistry(
            uri_schema="system://time",
            name="system_server_time",
            description="Returns the current server time dynamically",
            mime_type="text/plain",
            is_dynamic=True,
            static_content=None,
            active_hash_ref=server_time_hash,
            target_persona="default",
            group="system"
        )
        session.add(server_time_resource)
        print(f"   OK Resource 'system_server_time' added (dynamic, hash: {server_time_hash[:16]}...)")
        
        # Sample Tool using SELECT code_type with Jinja2 + SQLAlchemy binding
        print("\n[9] Adding 'get_sales_summary' tool with SELECT code_type (hybrid approach)...")
        sales_query_code = """SELECT 
    store_name,
    department,
    SUM(sales_amount) as total_sales,
    COUNT(*) as transaction_count
FROM sales_per_day
WHERE 1=1
{% if arguments.store_name %}
  AND store_name = :store_name
{% endif %}
{% if arguments.department %}
  AND department = :department
{% endif %}
GROUP BY store_name, department
ORDER BY total_sales DESC"""
        sales_query_hash = compute_hash(sales_query_code)
        
        sales_query_vault = CodeVault(
            hash=sales_query_hash,
            code_blob=sales_query_code,
            code_type="select"
        )
        session.add(sales_query_vault)
        
        sales_tool = ToolRegistry(
            tool_name="data_get_sales_summary",
            target_persona="default",
            description="Get sales summary grouped by store and department. Supports optional filtering by store_name and/or department using secure SQL parameter binding.",
            input_schema={
                "type": "object",
                "properties": {
                    "store_name": {
                        "type": "string",
                        "description": "Optional: Filter by store name"
                    },
                    "department": {
                        "type": "string",
                        "description": "Optional: Filter by department"
                    }
                },
                "required": []
            },
            active_hash_ref=sales_query_hash,
            group="data"
        )
        session.add(sales_tool)
        print(f"   OK Tool 'data_get_sales_summary' added (hash: {sales_query_hash[:16]}...)")
        
        # Sample Resource using SELECT code_type
        print("\n[10] Adding 'sales_report' resource with SELECT code_type...")
        sales_report_code = """SELECT 
    business_date,
    store_name,
    SUM(sales_amount) as daily_total
FROM sales_per_day
GROUP BY business_date, store_name
ORDER BY business_date DESC
LIMIT 10"""
        sales_report_hash = compute_hash(sales_report_code)
        
        sales_report_vault = CodeVault(
            hash=sales_report_hash,
            code_blob=sales_report_code,
            code_type="select"
        )
        session.add(sales_report_vault)
        
        sales_report_resource = ResourceRegistry(
            uri_schema="data://sales/recent",
            name="data_sales_report",
            description="Recent sales report showing daily totals by store (last 10 days)",
            mime_type="text/plain",
            is_dynamic=True,
            static_content=None,
            active_hash_ref=sales_report_hash,
            target_persona="default",
            group="data"
        )
        session.add(sales_report_resource)
        print(f"   OK Resource 'data_sales_report' added (dynamic, hash: {sales_report_hash[:16]}...)")
        
        # Sample Tool demonstrating date filtering with Jinja2 + SQLAlchemy
        print("\n[11] Adding 'get_sales_by_category' tool with date filtering...")
        sales_by_category_code = """SELECT 
    department,
    SUM(sales_amount) as total_sales,
    AVG(sales_amount) as avg_sales
FROM sales_per_day
WHERE 1=1
{% if arguments.start_date %}
  AND business_date >= :start_date
{% endif %}
{% if arguments.end_date %}
  AND business_date <= :end_date
{% endif %}
{% if arguments.min_amount %}
  AND sales_amount >= :min_amount
{% endif %}
GROUP BY department
ORDER BY total_sales DESC"""
        sales_by_category_hash = compute_hash(sales_by_category_code)
        
        sales_by_category_vault = CodeVault(
            hash=sales_by_category_hash,
            code_blob=sales_by_category_code,
            code_type="select"
        )
        session.add(sales_by_category_vault)
        
        sales_by_category_tool = ToolRegistry(
            tool_name="data_get_sales_by_category",
            target_persona="default",
            description="Get sales summary by category/department with optional date range and minimum amount filtering. Demonstrates secure dynamic SQL with Jinja2 structure + SQLAlchemy parameter binding.",
            input_schema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Optional: Start date (YYYY-MM-DD format)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Optional: End date (YYYY-MM-DD format)"
                    },
                    "min_amount": {
                        "type": "number",
                        "description": "Optional: Minimum sales amount filter"
                    }
                },
                "required": []
            },
            active_hash_ref=sales_by_category_hash,
            group="data"
        )
        session.add(sales_by_category_tool)
        print(f"   OK Tool 'data_get_sales_by_category' added (hash: {sales_by_category_hash[:16]}...)")
        
        # Sample Tool: get_last_error debugging tool
        print("\n[12] Adding 'get_last_error' debugging tool...")
        get_last_error_code = """from base import ChameleonTool
from sqlmodel import select
from models import ExecutionLog

class GetLastErrorTool(ChameleonTool):
    def run(self, arguments):
        tool_name = arguments.get('tool_name')
        
        # Build query for last error
        query = select(ExecutionLog).where(ExecutionLog.status == 'FAILURE')
        
        # Optional filter by tool_name
        if tool_name:
            query = query.where(ExecutionLog.tool_name == tool_name)
        
        # Order by timestamp descending and get the most recent
        query = query.order_by(ExecutionLog.timestamp.desc()).limit(1)
        
        # Execute query
        result = self.db_session.exec(query).first()
        
        if not result:
            if tool_name:
                return f"No errors found for tool '{tool_name}'"
            else:
                return "No errors found in execution log"
        
        # Format the result
        output = []
        output.append(f"Last error for tool '{result.tool_name}':")
        output.append(f"Time: {result.timestamp}")
        output.append(f"Persona: {result.persona}")
        output.append(f"Input: {result.arguments}")
        output.append(f"\\nTraceback:")
        output.append(result.error_traceback or "No traceback available")
        
        return "\\n".join(output)
"""
        get_last_error_hash = compute_hash(get_last_error_code)
        
        get_last_error_vault = CodeVault(
            hash=get_last_error_hash,
            code_blob=get_last_error_code,
            code_type="python"
        )
        session.add(get_last_error_vault)
        
        get_last_error_tool = ToolRegistry(
            tool_name="debug_get_last_error",
            target_persona="default",
            description="Get the last error from the execution log. Returns detailed error information including full Python traceback for AI self-debugging. Optionally filter by tool_name.",
            input_schema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Optional: Filter errors by specific tool name"
                    }
                },
                "required": []
            },
            active_hash_ref=get_last_error_hash,
            group="debug"
        )
        session.add(get_last_error_tool)
        print(f"   OK Tool 'debug_get_last_error' added (hash: {get_last_error_hash[:16]}...)")
        
        # Commit all metadata changes
        session.commit()
        
        print("\n" + "=" * 60)
        print("Metadata Database Seeding Completed!")
        print("=" * 60)
    
    # Seed data database (if available)
    if data_engine is not None:
        with Session(data_engine) as data_session:
            # Clear existing data if requested
            if clear_existing:
                existing_sales = data_session.exec(select(SalesPerDay)).first()
                if existing_sales:
                    print("\n⚠️  Clearing existing data...")
                    _clear_data_database(data_session)
                    print("✅ Data cleared")
            
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
                data_session.add(sales_record)
            data_session.commit()
            print(f"   ✅ Added 20 rows to sales_per_day table")
        
        print("\n" + "=" * 60)
        print("Data Database Seeding Completed!")
        print("=" * 60)
    else:
        print("\n⚠️  Data database not available - skipping data seeding")
    
    print("\n" + "=" * 60)
    print("All Database Seeding Completed Successfully!")
    print("=" * 60)
    
    # Show summary
    print("\nTools added:")
    print("  - utility_greet (persona: default)")
    print("  - math_add (persona: default)")
    print("  - math_multiply (persona: assistant)")
    print("  - utility_uppercase (persona: default)")
    print("  - data_get_sales_summary (persona: default, code_type: select, with filtering)")
    print("  - data_get_sales_by_category (persona: default, code_type: select, with date filtering)")
    print("  - debug_get_last_error (persona: default, debugging tool for AI self-healing)")
    print("\nResources added:")
    print("  - general_welcome_message (static, URI: memo://welcome)")
    print("  - system_server_time (dynamic, URI: system://time, code_type: python)")
    print("  - data_sales_report (dynamic, URI: data://sales/recent, code_type: select)")
    print("\nPrompts added:")
    print("  - developer_review_code")
    print("\nSample Data:")
    if data_engine is not None:
        print("  - sales_per_day table: 20 rows")
    else:
        print("  - sales_per_day table: NOT SEEDED (data database unavailable)")
    print("\n🔒 Security Features:")
    print("  - Jinja2 templates for SQL structure (optional WHERE clauses)")
    print("  - SQLAlchemy parameter binding (:param) for all values")
    print("  - Single statement validation (prevents SQL injection)")
    print("  - Read-only validation (only SELECT allowed)")
    print("\n🔧 AI Self-Debugging Features:")
    print("  - ExecutionLog table captures all tool executions")
    print("  - Full Python tracebacks logged for failures")
    print("  - get_last_error tool provides detailed error diagnostics")
    print("  - Enables AI self-healing workflow")
    print("\n🔄 Dual-Engine Architecture:")
    print("  - Metadata DB: System tools, logs, resources, prompts")
    print("  - Data DB: Business data (sales, inventory, etc.)")
    print("  - Server can start even if Data DB is offline")
    print("  - Use 'reconnect_db' tool to reconnect at runtime")
    print("\nYou can now run the MCP server with: python server.py")


if __name__ == "__main__":
    seed_database()
