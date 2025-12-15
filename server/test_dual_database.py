#!/usr/bin/env python3
"""
Test suite for dual-database architecture.

This test validates:
1. Metadata and data databases are separate
2. Metadata models go to metadata DB
3. Data models go to data DB
4. Tools can query data DB when available
5. Tools fail gracefully when data DB is offline
6. Server can start without data DB
"""

import sys
from datetime import date
from sqlmodel import Session, create_engine, SQLModel, select
from models import (
    CodeVault, ToolRegistry, SalesPerDay,
    get_engine, create_db_and_tables,
    METADATA_MODELS, DATA_MODELS
)
from runtime import execute_tool, ToolNotFoundError
import hashlib


def _compute_hash(code: str) -> str:
    """Compute SHA-256 hash of code."""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def test_separate_databases():
    """Test that metadata and data models are in separate databases."""
    print("\n🧪 Test 1: Metadata and data models in separate databases...")
    
    # Create two separate in-memory databases
    meta_engine = create_engine("sqlite:///:memory:", echo=False)
    data_engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Create tables in respective databases
    create_db_and_tables(meta_engine, METADATA_MODELS)
    create_db_and_tables(data_engine, DATA_MODELS)
    
    # Verify metadata tables exist in meta_engine
    with Session(meta_engine) as session:
        # Should be able to query metadata tables
        tools = session.exec(select(ToolRegistry)).all()
        print(f"  ✅ Metadata DB has ToolRegistry table (count: {len(tools)})")
    
    # Verify data tables exist in data_engine
    with Session(data_engine) as session:
        # Should be able to query data tables
        sales = session.exec(select(SalesPerDay)).all()
        print(f"  ✅ Data DB has SalesPerDay table (count: {len(sales)})")
    
    return True


def test_select_tool_with_data_db():
    """Test that SELECT tools work with separate data database."""
    print("\n🧪 Test 2: SELECT tools work with separate data database...")
    
    # Create two separate databases
    meta_engine = create_engine("sqlite:///:memory:", echo=False)
    data_engine = create_engine("sqlite:///:memory:", echo=False)
    
    create_db_and_tables(meta_engine, METADATA_MODELS)
    create_db_and_tables(data_engine, DATA_MODELS)
    
    # Add sample data to data DB
    with Session(data_engine) as data_session:
        sales = SalesPerDay(
            business_date=date(2024, 1, 1),
            store_name="Store A",
            department="Electronics",
            sales_amount=1000.0
        )
        data_session.add(sales)
        data_session.commit()
    
    # Create a SELECT tool in metadata DB
    with Session(meta_engine) as meta_session:
        sql_code = """SELECT store_name, SUM(sales_amount) as total
FROM sales_per_day
GROUP BY store_name"""
        sql_hash = _compute_hash(sql_code)
        
        code_vault = CodeVault(
            hash=sql_hash,
            code_blob=sql_code,
            code_type="select"
        )
        meta_session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_sales",
            target_persona="default",
            description="Test sales query",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=sql_hash
        )
        meta_session.add(tool)
        meta_session.commit()
        
        # Execute the tool with both sessions
        with Session(data_engine) as data_session:
            result = execute_tool("test_sales", "default", {}, meta_session, data_session)
            
            if result and len(result) > 0:
                print(f"  ✅ SELECT tool executed successfully: {result}")
                return True
            else:
                print(f"  ❌ No results returned: {result}")
                return False


def test_select_tool_without_data_db():
    """Test that SELECT tools fail gracefully without data database."""
    print("\n🧪 Test 3: SELECT tools fail gracefully without data database...")
    
    # Create only metadata database
    meta_engine = create_engine("sqlite:///:memory:", echo=False)
    create_db_and_tables(meta_engine, METADATA_MODELS)
    
    # Create a SELECT tool in metadata DB
    with Session(meta_engine) as meta_session:
        sql_code = """SELECT * FROM sales_per_day"""
        sql_hash = _compute_hash(sql_code)
        
        code_vault = CodeVault(
            hash=sql_hash,
            code_blob=sql_code,
            code_type="select"
        )
        meta_session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_sales",
            target_persona="default",
            description="Test sales query",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=sql_hash
        )
        meta_session.add(tool)
        meta_session.commit()
        
        # Execute the tool WITHOUT data_session (offline mode)
        try:
            result = execute_tool("test_sales", "default", {}, meta_session, None)
            print(f"  ❌ Should have raised RuntimeError, got: {result}")
            return False
        except RuntimeError as e:
            if "offline" in str(e).lower():
                print(f"  ✅ Correctly raised RuntimeError: {e}")
                return True
            else:
                print(f"  ❌ Wrong error message: {e}")
                return False


def test_python_tool_with_dual_sessions():
    """Test that Python tools have access to both sessions."""
    print("\n🧪 Test 4: Python tools have access to both sessions...")
    
    # Create two separate databases
    meta_engine = create_engine("sqlite:///:memory:", echo=False)
    data_engine = create_engine("sqlite:///:memory:", echo=False)
    
    create_db_and_tables(meta_engine, METADATA_MODELS)
    create_db_and_tables(data_engine, DATA_MODELS)
    
    # Add sample data to data DB
    with Session(data_engine) as data_session:
        sales = SalesPerDay(
            business_date=date(2024, 1, 1),
            store_name="Store A",
            department="Electronics",
            sales_amount=1500.0
        )
        data_session.add(sales)
        data_session.commit()
    
    # Create a Python tool that uses both sessions
    with Session(meta_engine) as meta_session:
        tool_code = """from base import ChameleonTool
from sqlmodel import select
from models import ToolRegistry, SalesPerDay

class DualSessionTool(ChameleonTool):
    def run(self, arguments):
        # Count tools in metadata DB
        tools = self.meta_session.exec(select(ToolRegistry)).all()
        tool_count = len(tools)
        
        # Check if data_session is available
        if self.data_session is not None:
            # Count sales in data DB
            sales = self.data_session.exec(select(SalesPerDay)).all()
            sales_count = len(sales)
            return f"Tools: {tool_count}, Sales: {sales_count}"
        else:
            return f"Tools: {tool_count}, Sales: OFFLINE"
"""
        tool_hash = _compute_hash(tool_code)
        
        code_vault = CodeVault(
            hash=tool_hash,
            code_blob=tool_code,
            code_type="python"
        )
        meta_session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_dual",
            target_persona="default",
            description="Test dual session access",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=tool_hash
        )
        meta_session.add(tool)
        meta_session.commit()
        
        # Execute with both sessions
        with Session(data_engine) as data_session:
            result = execute_tool("test_dual", "default", {}, meta_session, data_session)
            
            if "Tools: 1, Sales: 1" == result:
                print(f"  ✅ Tool accessed both sessions: {result}")
                return True
            else:
                print(f"  ❌ Unexpected result: {result}")
                return False


def test_python_tool_without_data_db():
    """Test that Python tools work without data database (offline mode)."""
    print("\n🧪 Test 5: Python tools work in offline mode...")
    
    # Create only metadata database
    meta_engine = create_engine("sqlite:///:memory:", echo=False)
    create_db_and_tables(meta_engine, METADATA_MODELS)
    
    # Create a Python tool that checks for data_session
    with Session(meta_engine) as meta_session:
        tool_code = """from base import ChameleonTool

class OfflineTool(ChameleonTool):
    def run(self, arguments):
        if self.data_session is None:
            return "Running in OFFLINE mode"
        else:
            return "Running in ONLINE mode"
"""
        tool_hash = _compute_hash(tool_code)
        
        code_vault = CodeVault(
            hash=tool_hash,
            code_blob=tool_code,
            code_type="python"
        )
        meta_session.add(code_vault)
        
        tool = ToolRegistry(
            tool_name="test_offline",
            target_persona="default",
            description="Test offline mode",
            input_schema={"type": "object", "properties": {}, "required": []},
            active_hash_ref=tool_hash
        )
        meta_session.add(tool)
        meta_session.commit()
        
        # Execute WITHOUT data_session
        result = execute_tool("test_offline", "default", {}, meta_session, None)
        
        if result == "Running in OFFLINE mode":
            print(f"  ✅ Tool correctly detected offline mode: {result}")
            return True
        else:
            print(f"  ❌ Unexpected result: {result}")
            return False


def main():
    """Run all dual-database tests."""
    print("=" * 60)
    print("Dual-Database Architecture Tests")
    print("=" * 60)
    
    tests = [
        test_separate_databases,
        test_select_tool_with_data_db,
        test_select_tool_without_data_db,
        test_python_tool_with_dual_sessions,
        test_python_tool_without_data_db,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All dual-database tests passed!")
        print("=" * 60)
        return 0
    else:
        print(f"❌ {sum(not r for r in results)} test(s) failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
