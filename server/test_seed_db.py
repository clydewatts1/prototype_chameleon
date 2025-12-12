"""
Test script for seed_db.py to validate database seeding.
"""

import os
from sqlmodel import Session, select
from models import get_engine, create_db_and_tables, ToolRegistry, ResourceRegistry, PromptRegistry, CodeVault
from seed_db import seed_database


def test_seed_database():
    """Test the seeding process and validate inserted data."""
    test_db_url = "sqlite:///test_chameleon.db"
    
    # Clean up any existing test database
    if os.path.exists("test_chameleon.db"):
        os.remove("test_chameleon.db")
    
    print("\n🧪 Running seed_db.py tests...\n")
    
    try:
        # Run the seeding function
        print("1️⃣  Running seed_database()...")
        seed_database(test_db_url)
        
        # Verify the database was created
        if os.path.exists("test_chameleon.db"):
            print("✅ Database file created successfully")
        else:
            print("❌ Database file not found")
            return False
        
        # Query and validate data
        engine = get_engine(test_db_url)
        
        with Session(engine) as session:
            # Check tools
            print("\n2️⃣  Validating Tools...")
            tools = session.exec(select(ToolRegistry)).all()
            expected_tools = ["greet", "add", "multiply", "uppercase"]
            found_tools = [t.tool_name for t in tools]
            
            for tool in expected_tools:
                if tool in found_tools:
                    print(f"   ✅ Tool '{tool}' found")
                else:
                    print(f"   ❌ Tool '{tool}' not found")
                    return False
            
            # Check resources
            print("\n3️⃣  Validating Resources...")
            resources = session.exec(select(ResourceRegistry)).all()
            expected_resources = ["welcome_message", "server_time"]
            found_resources = [r.name for r in resources]
            
            for resource in expected_resources:
                if resource in found_resources:
                    print(f"   ✅ Resource '{resource}' found")
                else:
                    print(f"   ❌ Resource '{resource}' not found")
                    return False
            
            # Check prompts
            print("\n4️⃣  Validating Prompts...")
            prompts = session.exec(select(PromptRegistry)).all()
            if any(p.name == "review_code" for p in prompts):
                print(f"   ✅ Prompt 'review_code' found")
            else:
                print(f"   ❌ Prompt 'review_code' not found")
                return False
            
            # Check code vaults
            print("\n5️⃣  Validating Code Vaults...")
            vaults = session.exec(select(CodeVault)).all()
            print(f"   ✅ {len(vaults)} code blob(s) stored in vault")
        
        # Close engine to release database connection
        engine.dispose()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! seed_db.py is working correctly.")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test database
        if os.path.exists("test_chameleon.db"):
            try:
                os.remove("test_chameleon.db")
            except PermissionError:
                print("⚠️  Could not delete test database (file in use)")


if __name__ == "__main__":
    success = test_seed_database()
    exit(0 if success else 1)
