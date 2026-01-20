# Database Connectivity Guide

This guide provides comprehensive information on connecting Chameleon MCP Server to various database systems including MySQL, PostgreSQL, and Neo4j.

## Overview

Chameleon uses a **dual database architecture**:

1. **Metadata Database**: Stores system configuration, tools, resources, prompts, and code
2. **Data Database**: Stores business/application data (e.g., sales, inventory)

Both databases can be configured independently and can use different database systems.

## Supported Database Systems

### Relational Databases (Fully Supported)

- **SQLite** (default, no additional drivers required)
- **PostgreSQL** (requires `psycopg2-binary` driver)
- **MySQL** (requires `pymysql` driver)

### Graph Databases (Experimental)

- **Neo4j** (requires `neo4j` driver)
  - Note: Neo4j support is experimental and best suited for the data database
  - Metadata database should use a relational database for optimal performance

## Installation

### Installing Database Drivers

Install the required drivers for your chosen database:

```bash
# PostgreSQL
pip install psycopg2-binary

# MySQL
pip install pymysql

# Neo4j
pip install neo4j

# Or install all drivers at once
pip install psycopg2-binary pymysql neo4j
```

These drivers are optional and only needed if you plan to use the corresponding database.

## Connection String Format

### SQLite

**Format:**
```
sqlite:///database_name.db
```

**Examples:**

```yaml
# Relative path (creates file in current directory)
metadata_database:
  url: "sqlite:///chameleon_meta.db"

# Absolute path
metadata_database:
  url: "sqlite:////home/user/data/chameleon_meta.db"

# In-memory database (useful for testing)
metadata_database:
  url: "sqlite:///:memory:"
```

**Characteristics:**
- No server required
- Single file per database
- Great for development and testing
- Limited concurrency support
- No schema support

### PostgreSQL

**Format:**
```
postgresql://username:password@host:port/database_name
```

**Examples:**

```yaml
# Basic connection
metadata_database:
  url: "postgresql://chameleon_user:secure_password@localhost:5432/chameleon_meta"

# With schema
metadata_database:
  url: "postgresql://chameleon_user:secure_password@localhost:5432/chameleon_meta"
  schema: "chameleon"

# Remote server
metadata_database:
  url: "postgresql://user:pass@db.example.com:5432/chameleon_meta"

# With SSL
metadata_database:
  url: "postgresql://user:pass@db.example.com:5432/chameleon_meta?sslmode=require"

# Different databases for metadata and data
metadata_database:
  url: "postgresql://user:pass@db-meta.example.com:5432/chameleon_meta"
  schema: "system"

data_database:
  url: "postgresql://user:pass@db-data.example.com:5432/business_data"
  schema: "retail"
```

**Characteristics:**
- Enterprise-grade reliability
- Full ACID compliance
- Excellent concurrency support
- Schema support for organization
- Advanced features (JSON types, full-text search)

**Setup Steps:**

1. Create the database:
```sql
CREATE DATABASE chameleon_meta;
CREATE DATABASE chameleon_data;
```

2. Create a user and grant permissions:
```sql
CREATE USER chameleon_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE chameleon_meta TO chameleon_user;
GRANT ALL PRIVILEGES ON DATABASE chameleon_data TO chameleon_user;
```

3. (Optional) Create schemas:
```sql
\c chameleon_meta
CREATE SCHEMA chameleon;
GRANT ALL ON SCHEMA chameleon TO chameleon_user;

\c chameleon_data
CREATE SCHEMA retail;
GRANT ALL ON SCHEMA retail TO chameleon_user;
```

### MySQL

**Format:**
```
mysql+pymysql://username:password@host:port/database_name
```

**Examples:**

```yaml
# Basic connection
metadata_database:
  url: "mysql+pymysql://chameleon_user:secure_password@localhost:3306/chameleon_meta"

# With character set
metadata_database:
  url: "mysql+pymysql://chameleon_user:secure_password@localhost:3306/chameleon_meta?charset=utf8mb4"

# With timezone handling
metadata_database:
  url: "mysql+pymysql://chameleon_user:secure_password@localhost:3306/chameleon_meta?charset=utf8mb4&time_zone=%2B00:00"

# Remote server with SSL
metadata_database:
  url: "mysql+pymysql://user:pass@db.example.com:3306/chameleon_meta?ssl_ca=/path/to/ca.pem"

# Different databases for metadata and data
metadata_database:
  url: "mysql+pymysql://user:pass@localhost:3306/chameleon_meta?charset=utf8mb4"

data_database:
  url: "mysql+pymysql://user:pass@localhost:3306/business_data?charset=utf8mb4"
```

**Characteristics:**
- Wide deployment and hosting support
- Good performance for read-heavy workloads
- Easy replication setup
- Note: MySQL doesn't have schema support like PostgreSQL

**Setup Steps:**

1. Create the databases:
```sql
CREATE DATABASE chameleon_meta CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE chameleon_data CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Create a user and grant permissions:
```sql
CREATE USER 'chameleon_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON chameleon_meta.* TO 'chameleon_user'@'localhost';
GRANT ALL PRIVILEGES ON chameleon_data.* TO 'chameleon_user'@'localhost';
FLUSH PRIVILEGES;
```

### Neo4j (Experimental)

**Format:**
```
bolt://username:password@host:port
neo4j://username:password@host:port
neo4j+s://username:password@host:port  # Secure connection
```

**Examples:**

```yaml
# Basic connection (Bolt protocol)
data_database:
  url: "bolt://neo4j:password@localhost:7687"

# Neo4j protocol
data_database:
  url: "neo4j://neo4j:password@localhost:7687"

# Secure connection
data_database:
  url: "neo4j+s://neo4j:password@db.example.com:7687"

# Neo4j Aura (cloud)
data_database:
  url: "neo4j+s://username:password@xxxxx.databases.neo4j.io:7687"
```

**⚠️ Important Notes:**

- **Neo4j is a graph database**, not a relational database
- **Best practice**: Use Neo4j only for the **data database**, not the metadata database
- **Recommended**: Use PostgreSQL or MySQL for metadata, Neo4j for graph-based business data
- Neo4j requires custom query handling (Cypher instead of SQL)
- Limited support in current version (experimental feature)

**Characteristics:**
- Excellent for graph data (relationships, networks, hierarchies)
- Uses Cypher query language (not SQL)
- High performance for relationship queries
- Not suitable for traditional relational data

**Setup Steps:**

1. Install and start Neo4j:
```bash
# Using Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:latest
```

2. Access Neo4j Browser at `http://localhost:7474`

3. Set password and verify connection

**Example Use Case:**

```yaml
# Optimal configuration: PostgreSQL for metadata, Neo4j for graph data
metadata_database:
  url: "postgresql://user:pass@localhost:5432/chameleon_meta"

data_database:
  url: "bolt://neo4j:password@localhost:7687"
```

## Configuration Examples

### Development Setup (SQLite)

```yaml
server:
  transport: "stdio"
  log_level: "DEBUG"

metadata_database:
  url: "sqlite:///chameleon_meta.db"

data_database:
  url: "sqlite:///chameleon_data.db"
```

### Production Setup (PostgreSQL)

```yaml
server:
  transport: "sse"
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"

metadata_database:
  url: "postgresql://chameleon:secure_pass@db-server:5432/chameleon_meta"
  schema: "chameleon"

data_database:
  url: "postgresql://chameleon:secure_pass@db-server:5432/business_data"
  schema: "retail"
```

### Hybrid Setup (PostgreSQL + Neo4j)

```yaml
server:
  transport: "sse"
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"

metadata_database:
  url: "postgresql://user:pass@localhost:5432/chameleon_meta"
  schema: "system"

data_database:
  url: "bolt://neo4j:password@localhost:7687"
```

### Multi-Environment Setup

```yaml
# Development
metadata_database:
  url: "sqlite:///dev_meta.db"
data_database:
  url: "sqlite:///dev_data.db"

# Staging
# metadata_database:
#   url: "postgresql://user:pass@staging-db:5432/chameleon_meta"
# data_database:
#   url: "postgresql://user:pass@staging-db:5432/chameleon_data"

# Production
# metadata_database:
#   url: "postgresql://user:pass@prod-db:5432/chameleon_meta"
#   schema: "chameleon"
# data_database:
#   url: "postgresql://user:pass@prod-db:5432/business_data"
#   schema: "retail"
```

## Connection String Parameters

### Common Parameters

All database URLs support additional parameters via query strings:

**PostgreSQL:**
- `sslmode=require` - Require SSL connection
- `connect_timeout=10` - Connection timeout in seconds
- `application_name=chameleon` - Application name for logging

**MySQL:**
- `charset=utf8mb4` - Character set
- `time_zone=%2B00:00` - Timezone (URL encoded)
- `ssl_ca=/path/to/ca.pem` - SSL certificate

**Neo4j:**
- `encrypted=true` - Enable encryption
- `max_connection_lifetime=3600` - Max connection lifetime
- `max_connection_pool_size=50` - Connection pool size

## Testing Database Connectivity

### Quick Test Script

Create a test file `test_db_connection.py`:

```python
from sqlmodel import Session
from server.models import get_engine
from server.config import load_config

# Load configuration
config = load_config()

# Test metadata database
try:
    meta_url = config['metadata_database']['url']
    print(f"Testing metadata database: {meta_url}")
    meta_engine = get_engine(meta_url)
    with Session(meta_engine) as session:
        result = session.exec("SELECT 1").first()
        print(f"✅ Metadata database connection successful!")
except Exception as e:
    print(f"❌ Metadata database connection failed: {e}")

# Test data database
try:
    data_url = config['data_database']['url']
    print(f"Testing data database: {data_url}")
    data_engine = get_engine(data_url)
    with Session(data_engine) as session:
        result = session.exec("SELECT 1").first()
        print(f"✅ Data database connection successful!")
except Exception as e:
    print(f"❌ Data database connection failed: {e}")
```

Run with:
```bash
cd /home/runner/work/prototype_chameleon/prototype_chameleon
python test_db_connection.py
```

## Security Best Practices

### 1. Never Hardcode Credentials

❌ **Bad:**
```yaml
metadata_database:
  url: "postgresql://admin:password123@localhost:5432/chameleon"
```

✅ **Good:**
```yaml
metadata_database:
  url: "${DATABASE_URL}"  # Use environment variables
```

### 2. Use Environment Variables

```bash
export METADATA_DB_URL="postgresql://user:pass@host/db"
export DATA_DB_URL="postgresql://user:pass@host/db"
```

### 3. Restrict Database Permissions

- Create dedicated database users for Chameleon
- Grant only necessary permissions
- Use different users for development and production

### 4. Use SSL/TLS Connections

For production deployments, always use encrypted connections:

**PostgreSQL:**
```yaml
metadata_database:
  url: "postgresql://user:pass@host/db?sslmode=require"
```

**MySQL:**
```yaml
metadata_database:
  url: "mysql+pymysql://user:pass@host/db?ssl_ca=/path/to/ca.pem"
```

**Neo4j:**
```yaml
data_database:
  url: "neo4j+s://user:pass@host:7687"
```

## Troubleshooting

### Connection Refused

**Problem:** Cannot connect to database server

**Solutions:**
1. Verify database server is running
2. Check firewall rules
3. Verify host and port are correct
4. Test connectivity with `telnet host port`

### Authentication Failed

**Problem:** Username or password rejected

**Solutions:**
1. Verify credentials are correct
2. Check user has proper permissions
3. Ensure user can connect from your host
4. For MySQL: Check user@host combination

### Table Creation Errors

**Problem:** Cannot create tables

**Solutions:**
1. Verify user has CREATE TABLE permissions
2. Check schema exists (PostgreSQL)
3. Verify character set supports required data (MySQL)

### Driver Not Found

**Problem:** `ModuleNotFoundError: No module named 'pymysql'`

**Solutions:**
```bash
# Install missing driver
pip install pymysql        # For MySQL
pip install psycopg2-binary  # For PostgreSQL
pip install neo4j          # For Neo4j
```

## Migration Between Databases

### SQLite to PostgreSQL

1. Export data from SQLite:
```bash
python server/export_specs.py > backup.yaml
```

2. Configure PostgreSQL connection in config.yaml

3. Initialize new database:
```bash
python server/load_specs.py backup.yaml
```

### MySQL to PostgreSQL

Use standard database migration tools like:
- `pgloader`
- `AWS Database Migration Service`
- Custom scripts

## Performance Considerations

### Connection Pooling

SQLAlchemy automatically manages connection pools. Adjust as needed:

```python
from server.models import get_engine

engine = get_engine(
    database_url="postgresql://user:pass@host/db",
    pool_size=10,
    max_overflow=20
)
```

### Database-Specific Optimizations

**PostgreSQL:**
- Use schemas to organize tables
- Enable query logging for optimization
- Consider table partitioning for large datasets

**MySQL:**
- Use utf8mb4 for full Unicode support
- Enable query cache
- Consider InnoDB for ACID compliance

**Neo4j:**
- Create indexes on frequently queried properties
- Use parameters in queries to enable query caching
- Monitor memory usage and adjust heap size

## Additional Resources

- [SQLAlchemy Database URLs](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls)
- [PostgreSQL Connection Strings](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)
- [MySQL Connection Parameters](https://dev.mysql.com/doc/connector-python/en/connector-python-connectargs.html)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)

## Getting Help

If you encounter issues:

1. Check the logs in the `logs/` directory
2. Verify your connection string format
3. Test database connectivity independently
4. Review the error messages carefully
5. Consult database-specific documentation

For Chameleon-specific issues, please file an issue on the GitHub repository.
