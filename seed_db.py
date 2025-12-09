"""
Database seeder script for inserting sample tools.

This script populates the database with sample tools for testing the MCP server.
"""

import hashlib
from sqlmodel import Session
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables


def _compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def seed_database(database_url: str = "sqlite:///chameleon.db"):
    """
    Seed the database with sample tools.
    
    Args:
        database_url: Database connection string
    """
    # Create engine and tables
    engine = get_engine(database_url)
    create_db_and_tables(engine)
    
    print("=" * 60)
    print("Seeding Database with Sample Tools")
    print("=" * 60)
    
    with Session(engine) as session:
        # Sample Tool 1: Greeting function
        greeting_code = """def run(args, db):
    return f'Hello {args.get("name")}! I am running from the database.'

result = run(arguments, db_session)
"""
        greeting_hash = _compute_hash(greeting_code)
        
        print("\n[1] Adding greeting tool...")
        greeting_vault = CodeVault(
            hash=greeting_hash,
            python_blob=greeting_code
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
            python_blob=add_code
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
            python_blob=multiply_code
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
            python_blob=uppercase_code
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
        print("\nYou can now run the MCP server with: python server.py")


if __name__ == "__main__":
    seed_database()
