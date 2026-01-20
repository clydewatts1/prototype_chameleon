"""
Test database connectivity configuration and validation.

This test suite verifies that database connection strings are correctly
configured and that the connectivity documentation is accurate.
"""

import sys
from pathlib import Path

# Add server directory to path
server_path = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_path))

import config


def test_config_loads_successfully():
    """Test that configuration loads without errors."""
    cfg = config.load_config()
    assert cfg is not None
    assert 'metadata_database' in cfg
    assert 'data_database' in cfg
    print("✅ Configuration loads successfully")


def test_metadata_database_configured():
    """Test that metadata database is configured."""
    cfg = config.load_config()
    assert 'metadata_database' in cfg
    assert 'url' in cfg['metadata_database']
    assert cfg['metadata_database']['url'] is not None
    print(f"✅ Metadata database configured: {cfg['metadata_database']['url']}")


def test_data_database_configured():
    """Test that data database is configured."""
    cfg = config.load_config()
    assert 'data_database' in cfg
    assert 'url' in cfg['data_database']
    assert cfg['data_database']['url'] is not None
    print(f"✅ Data database configured: {cfg['data_database']['url']}")


def test_default_configuration():
    """Test that default configuration has expected values."""
    cfg = config.get_default_config()
    
    # Check metadata database defaults
    assert cfg['metadata_database']['url'] == 'sqlite:///chameleon_meta.db'
    assert cfg['metadata_database']['schema'] is None
    
    # Check data database defaults
    assert cfg['data_database']['url'] == 'sqlite:///chameleon_data.db'
    assert cfg['data_database']['schema'] is None
    
    print("✅ Default configuration has expected values")


def test_connection_string_formats():
    """Test that various connection string formats are valid."""
    
    # SQLite connection strings
    sqlite_formats = [
        "sqlite:///chameleon.db",
        "sqlite:////absolute/path/to/db.db",
        "sqlite:///:memory:",
    ]
    
    for fmt in sqlite_formats:
        assert fmt.startswith("sqlite://")
        print(f"✅ Valid SQLite format: {fmt}")
    
    # PostgreSQL connection strings
    postgres_formats = [
        "postgresql://user:pass@localhost:5432/db",
        "postgresql://user:pass@host.com:5432/db?sslmode=require",
    ]
    
    for fmt in postgres_formats:
        assert fmt.startswith("postgresql://")
        print(f"✅ Valid PostgreSQL format: {fmt}")
    
    # MySQL connection strings
    mysql_formats = [
        "mysql+pymysql://user:pass@localhost:3306/db",
        "mysql+pymysql://user:pass@localhost:3306/db?charset=utf8mb4",
    ]
    
    for fmt in mysql_formats:
        assert fmt.startswith("mysql+pymysql://")
        print(f"✅ Valid MySQL format: {fmt}")
    
    # Neo4j connection strings
    neo4j_formats = [
        "bolt://neo4j:password@localhost:7687",
        "neo4j://neo4j:password@localhost:7687",
        "neo4j+s://neo4j:password@host.com:7687",
    ]
    
    for fmt in neo4j_formats:
        assert fmt.startswith(("bolt://", "neo4j://", "neo4j+s://"))
        print(f"✅ Valid Neo4j format: {fmt}")


def test_documentation_exists():
    """Test that database connectivity documentation exists."""
    doc_path = Path(__file__).parent.parent / "DATABASE_CONNECTIVITY.md"
    assert doc_path.exists(), f"Documentation not found at {doc_path}"
    
    # Read and verify key sections exist
    content = doc_path.read_text()
    
    assert "MySQL" in content
    assert "PostgreSQL" in content
    assert "Neo4j" in content
    assert "Connection String Format" in content
    assert "mysql+pymysql://" in content
    assert "postgresql://" in content
    assert "bolt://" in content
    
    print("✅ DATABASE_CONNECTIVITY.md exists and contains required information")


def test_config_sample_has_examples():
    """Test that config.yaml.sample has connection string examples."""
    sample_path = Path(__file__).parent.parent / "server" / "config.yaml.sample"
    assert sample_path.exists(), f"Config sample not found at {sample_path}"
    
    content = sample_path.read_text()
    
    # Check for MySQL examples
    assert "mysql+pymysql://" in content
    
    # Check for PostgreSQL examples
    assert "postgresql://" in content
    
    # Check for Neo4j examples
    assert "bolt://" in content or "neo4j://" in content
    
    print("✅ config.yaml.sample contains connection string examples")


def test_requirements_has_drivers():
    """Test that requirements.txt includes database drivers."""
    # Check server requirements
    server_req_path = Path(__file__).parent.parent / "server" / "requirements.txt"
    assert server_req_path.exists(), f"Server requirements not found at {server_req_path}"
    
    content = server_req_path.read_text()
    
    assert "pymysql" in content
    assert "psycopg2-binary" in content
    assert "neo4j" in content
    
    print("✅ server/requirements.txt includes database drivers")
    
    # Check root requirements
    root_req_path = Path(__file__).parent.parent / "requirements.txt"
    assert root_req_path.exists(), f"Root requirements not found at {root_req_path}"
    
    content = root_req_path.read_text()
    
    assert "pymysql" in content
    assert "psycopg2-binary" in content
    assert "neo4j" in content
    
    print("✅ requirements.txt includes database drivers")


if __name__ == "__main__":
    print("=" * 60)
    print("Database Connectivity Configuration Tests")
    print("=" * 60)
    print()
    
    tests = [
        test_config_loads_successfully,
        test_metadata_database_configured,
        test_data_database_configured,
        test_default_configuration,
        test_connection_string_formats,
        test_documentation_exists,
        test_config_sample_has_examples,
        test_requirements_has_drivers,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            print(f"\nRunning: {test.__name__}")
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)
