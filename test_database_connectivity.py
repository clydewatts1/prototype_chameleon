#!/usr/bin/env python3
"""
Test script to validate database connectivity for Chameleon MCP Server.

This script tests connections to configured databases and validates
that the system can connect to MySQL, PostgreSQL, and Neo4j.
"""

import sys
from pathlib import Path

# Add server directory to path
server_path = Path(__file__).parent / "server"
sys.path.insert(0, str(server_path))

# Import server modules directly (avoid importing server.py which has dependencies)
import config
import models
from sqlmodel import Session, text


def test_connection(db_name: str, db_url: str) -> bool:
    """
    Test connection to a database.
    
    Args:
        db_name: Name of the database (for display)
        db_url: Database connection URL
        
    Returns:
        True if connection successful, False otherwise
    """
    print(f"\nTesting {db_name} database...")
    print(f"URL: {db_url}")
    
    try:
        # Special handling for Neo4j
        if db_url.startswith(('bolt://', 'neo4j://', 'neo4j+s://', 'neo4j+ssc://')):
            try:
                from neo4j import GraphDatabase
                
                # Extract credentials from URL
                # Format: protocol://username:password@host:port
                protocol = db_url.split('://')[0]
                rest = db_url.split('://')[1]
                
                if '@' in rest:
                    creds, host_port = rest.split('@')
                    username, password = creds.split(':')
                    host = host_port.split(':')[0] if ':' in host_port else host_port
                    port = host_port.split(':')[1] if ':' in host_port else '7687'
                    
                    # Reconstruct URI
                    uri = f"{protocol}://{host}:{port}"
                    
                    driver = GraphDatabase.driver(uri, auth=(username, password))
                    
                    # Test connection
                    with driver.session() as session:
                        result = session.run("RETURN 1 as num")
                        record = result.single()
                        if record and record["num"] == 1:
                            print(f"✅ {db_name} connection successful!")
                            print(f"   Database type: Neo4j (Graph Database)")
                            driver.close()
                            return True
                    
                    driver.close()
                    
            except ImportError:
                print(f"❌ {db_name} connection failed: neo4j driver not installed")
                print(f"   Install with: pip install neo4j")
                return False
            except Exception as e:
                print(f"❌ {db_name} connection failed: {e}")
                return False
        
        # Special handling for Databricks
        if db_url.startswith('databricks://'):
            try:
                from databricks import sql
                from urllib.parse import urlparse, parse_qs
                
                # Parse Databricks URL using urllib
                parsed = urlparse(db_url)
                
                # Extract token from password field
                token = parsed.password if parsed.password else ''
                host = parsed.hostname if parsed.hostname else ''
                
                # Extract HTTP path from URL path
                http_path = parsed.path if parsed.path else ''
                
                # Extract query parameters
                params = parse_qs(parsed.query)
                catalog = params.get('catalog', ['main'])[0]
                schema = params.get('schema', ['default'])[0]
                
                # Connect to Databricks with timeout
                connection = sql.connect(
                    server_hostname=host,
                    http_path=http_path,
                    access_token=token,
                    _connect_timeout=30  # 30 second connection timeout
                )
                
                cursor = connection.cursor()
                cursor.execute("SELECT 1 as num")
                result = cursor.fetchone()
                
                if result and result[0] == 1:
                    print(f"✅ {db_name} connection successful!")
                    print(f"   Database type: Databricks (Lakehouse)")
                    print(f"   Catalog: {catalog}, Schema: {schema}")
                    cursor.close()
                    connection.close()
                    return True
                
                cursor.close()
                connection.close()
                
            except ImportError:
                print(f"❌ {db_name} connection failed: databricks-sql-connector not installed")
                print(f"   Install with: pip install databricks-sql-connector")
                return False
            except Exception as e:
                print(f"❌ {db_name} connection failed: {e}")
                return False
        
        # Standard SQLAlchemy databases (including Teradata and Snowflake)
        engine = models.get_engine(db_url)
        
        with Session(engine) as session:
            # Test connection with a simple query
            result = session.exec(text("SELECT 1")).first()
            
            if result:
                print(f"✅ {db_name} connection successful!")
                
                # Identify database type
                dialect = engine.dialect.name
                print(f"   Database type: {dialect}")
                
                # Get version info if available
                try:
                    if dialect == 'sqlite':
                        version_result = session.exec(text("SELECT sqlite_version()")).first()
                        print(f"   Version: SQLite {version_result}")
                    elif dialect == 'postgresql':
                        version_result = session.exec(text("SELECT version()")).first()
                        version = version_result.split(' ')[1] if version_result else 'unknown'
                        print(f"   Version: PostgreSQL {version}")
                    elif dialect == 'mysql':
                        version_result = session.exec(text("SELECT VERSION()")).first()
                        print(f"   Version: MySQL {version_result}")
                    elif dialect == 'teradata':
                        try:
                            version_result = session.exec(text("SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'VERSION'")).first()
                            print(f"   Version: Teradata {version_result}")
                        except Exception:
                            # Fallback if DBC.DBCInfoV is not accessible
                            print(f"   Version: Teradata (version info not accessible)")
                    elif dialect == 'snowflake':
                        version_result = session.exec(text("SELECT CURRENT_VERSION()")).first()
                        print(f"   Version: Snowflake {version_result}")
                except Exception as ve:
                    print(f"   Version: Unable to determine ({ve})")
                
                return True
            else:
                print(f"❌ {db_name} connection failed: No result from test query")
                return False
                
    except ImportError as ie:
        print(f"❌ {db_name} connection failed: Missing driver")
        print(f"   Error: {ie}")
        
        # Suggest driver installation
        if 'pymysql' in str(ie):
            print(f"   Install with: pip install pymysql")
        elif 'psycopg2' in str(ie):
            print(f"   Install with: pip install psycopg2-binary")
        elif 'neo4j' in str(ie):
            print(f"   Install with: pip install neo4j")
        elif 'teradatasql' in str(ie):
            print(f"   Install with: pip install teradatasql")
        elif 'snowflake' in str(ie):
            print(f"   Install with: pip install snowflake-sqlalchemy snowflake-connector-python")
        elif 'databricks' in str(ie):
            print(f"   Install with: pip install databricks-sql-connector")
        
        return False
        
    except Exception as e:
        print(f"❌ {db_name} connection failed: {e}")
        return False


def main():
    """Main test function."""
    print("=" * 60)
    print("Chameleon Database Connectivity Test")
    print("=" * 60)
    
    # Load configuration
    try:
        cfg = config.load_config()
    except Exception as e:
        print(f"\n❌ Failed to load configuration: {e}")
        return 1
    
    results = {}
    
    # Test metadata database
    if 'metadata_database' in cfg and 'url' in cfg['metadata_database']:
        meta_url = cfg['metadata_database']['url']
        results['metadata'] = test_connection("Metadata", meta_url)
    else:
        print("\n⚠️  No metadata database configured")
        results['metadata'] = False
    
    # Test data database
    if 'data_database' in cfg and 'url' in cfg['data_database']:
        data_url = cfg['data_database']['url']
        results['data'] = test_connection("Data", data_url)
    else:
        print("\n⚠️  No data database configured")
        results['data'] = False
    
    # Test legacy database (if configured)
    if 'database' in cfg and 'url' in cfg['database']:
        legacy_url = cfg['database']['url']
        results['legacy'] = test_connection("Legacy", legacy_url)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    total_tests = len(results)
    successful_tests = sum(1 for v in results.values() if v)
    
    print(f"\nTotal tests: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {total_tests - successful_tests}")
    
    if successful_tests == total_tests:
        print("\n✅ All database connections successful!")
        return 0
    else:
        print("\n⚠️  Some database connections failed")
        print("\nFor help with database connectivity, see:")
        print("  - DATABASE_CONNECTIVITY.md")
        print("  - server/config.yaml.sample")
        return 1


if __name__ == "__main__":
    sys.exit(main())
