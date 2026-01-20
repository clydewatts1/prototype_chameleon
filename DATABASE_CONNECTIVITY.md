# Database Connectivity Guide

This guide provides comprehensive information on connecting Chameleon MCP Server to various database systems including MySQL, PostgreSQL, Neo4j, Teradata, Snowflake, and Databricks.

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
- **Teradata** (requires `teradatasql` driver)
- **Snowflake** (requires `snowflake-sqlalchemy` and `snowflake-connector-python` drivers)
- **Databricks** (requires `databricks-sql-connector` driver)

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

# Teradata
pip install teradatasql

# Snowflake
pip install snowflake-sqlalchemy snowflake-connector-python

# Databricks
pip install databricks-sql-connector

# Or install all drivers at once
pip install psycopg2-binary pymysql neo4j teradatasql snowflake-sqlalchemy snowflake-connector-python databricks-sql-connector
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

### Teradata

**Format:**
```
teradatasql://username:password@host/database
```

**Examples:**

```yaml
# Basic connection
metadata_database:
  url: "teradatasql://dbc:dbc@localhost/chameleon_meta"

# Production connection with schema
metadata_database:
  url: "teradatasql://chameleon_user:secure_password@tdprod.example.com/analytics_db"
  schema: "chameleon"

# Connection with additional parameters
metadata_database:
  url: "teradatasql://user:pass@host/database?tmode=TERA&charset=UTF8"

# Different databases for metadata and data
metadata_database:
  url: "teradatasql://user:pass@tdprod.example.com/system_db"
  schema: "chameleon_meta"

data_database:
  url: "teradatasql://user:pass@tdprod.example.com/edw"
  schema: "retail_data"
```

**Characteristics:**
- Enterprise data warehouse platform
- Excellent for large-scale analytics workloads
- Supports advanced SQL features
- Schema support for organization
- Parallel processing architecture
- Optimized for complex queries on large datasets

**Setup Steps:**

1. Install Teradata driver:
```bash
pip install teradatasql
```

2. Create database and user in Teradata:
```sql
-- Connect as DBC or privileged user
CREATE DATABASE chameleon_meta AS PERMANENT = 100e6;
CREATE DATABASE chameleon_data AS PERMANENT = 500e6;

CREATE USER chameleon_user AS PASSWORD = "secure_password"
    PERM = 10e6;

GRANT ALL ON chameleon_meta TO chameleon_user;
GRANT ALL ON chameleon_data TO chameleon_user;
```

3. Test connection:
```bash
python test_database_connectivity.py
```

**Connection Parameters:**

Common query string parameters:
- `tmode=TERA` - Teradata mode (default: ANSI)
- `charset=UTF8` - Character set
- `account=myaccount` - Account string for logging
- `logmech=LDAP` - Authentication mechanism (TD2, LDAP, KRB5, etc.)

### Snowflake

**Format:**
```
snowflake://username:password@account/database/schema?warehouse=warehouse_name
```

**Examples:**

```yaml
# Basic connection
metadata_database:
  url: "snowflake://chameleon_user:secure_password@xy12345.us-east-1/CHAMELEON_DB/PUBLIC?warehouse=COMPUTE_WH"

# With role specification
metadata_database:
  url: "snowflake://user:pass@account.region/database/schema?warehouse=wh&role=CHAMELEON_ROLE"

# Using different databases and warehouses
metadata_database:
  url: "snowflake://user:pass@account/METADATA_DB/CHAMELEON_SCHEMA?warehouse=SMALL_WH"

data_database:
  url: "snowflake://user:pass@account/ANALYTICS_DB/RETAIL_SCHEMA?warehouse=LARGE_WH"

# With additional connection parameters
metadata_database:
  url: "snowflake://user:pass@account/database/schema?warehouse=wh&role=role1&authenticator=externalbrowser"
```

**Characteristics:**
- Cloud-native data warehouse (AWS, Azure, GCP)
- Automatic scaling and concurrency
- Separation of storage and compute
- Support for semi-structured data (JSON, Avro, Parquet)
- Time travel and data sharing capabilities
- Pay-per-use pricing model

**Setup Steps:**

1. Install Snowflake drivers:
```bash
pip install snowflake-sqlalchemy snowflake-connector-python
```

2. Create database and user in Snowflake:
```sql
-- As ACCOUNTADMIN or privileged user
CREATE DATABASE CHAMELEON_DB;
CREATE DATABASE ANALYTICS_DB;

CREATE WAREHOUSE CHAMELEON_WH WITH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 300
    AUTO_RESUME = TRUE;

CREATE USER chameleon_user
    PASSWORD = 'secure_password'
    DEFAULT_WAREHOUSE = CHAMELEON_WH
    DEFAULT_ROLE = CHAMELEON_ROLE;

CREATE ROLE CHAMELEON_ROLE;

GRANT USAGE ON WAREHOUSE CHAMELEON_WH TO ROLE CHAMELEON_ROLE;
GRANT ALL ON DATABASE CHAMELEON_DB TO ROLE CHAMELEON_ROLE;
GRANT ALL ON DATABASE ANALYTICS_DB TO ROLE CHAMELEON_ROLE;
GRANT ROLE CHAMELEON_ROLE TO USER chameleon_user;
```

3. Test connection:
```bash
python test_database_connectivity.py
```

**Connection Parameters:**

Common query string parameters:
- `warehouse=name` - Virtual warehouse to use (required)
- `role=name` - Role to use for session
- `authenticator=externalbrowser` - Use browser-based SSO
- `account=account_name` - Full account name
- `region=region_name` - Cloud region

**Important Notes:**
- Snowflake URLs use your account identifier (e.g., `xy12345.us-east-1`)
- Schema must be specified in the connection string
- Warehouse parameter is required for query execution
- Case sensitivity: Snowflake identifiers are case-insensitive by default

### Databricks

**Format:**
```
databricks://token:<access_token>@<workspace_host>/<http_path>?catalog=<catalog>&schema=<schema>
```

**Examples:**

```yaml
# Basic connection (Unity Catalog)
metadata_database:
  url: "databricks://token:dapi1234567890abcdef@adb-1234567890123456.7.azuredatabricks.net/sql/1.0/warehouses/abc123def456?catalog=main&schema=chameleon"

# Using different catalogs and schemas
metadata_database:
  url: "databricks://token:dapi111@company.cloud.databricks.com/sql/1.0/warehouses/wh123?catalog=main&schema=metadata"

data_database:
  url: "databricks://token:dapi111@company.cloud.databricks.com/sql/1.0/warehouses/wh456?catalog=analytics&schema=retail"

# With additional parameters
metadata_database:
  url: "databricks://token:dapi111@workspace.databricks.com/sql/1.0/warehouses/wh123?catalog=main&schema=default&http_path_override=/sql/1.0/warehouses/wh123"
```

**Characteristics:**
- Unified analytics platform built on Apache Spark
- Supports SQL, Python, R, and Scala
- Unity Catalog for data governance
- Delta Lake for ACID transactions
- Lakehouse architecture (combines data warehouse and data lake)
- Optimized for machine learning and data science workloads

**Setup Steps:**

1. Install Databricks driver:
```bash
pip install databricks-sql-connector
```

2. Get your Databricks access token:
   - Navigate to your Databricks workspace
   - Click on your profile → User Settings
   - Go to Access Tokens → Generate New Token
   - Copy the token (save it securely, it won't be shown again)

3. Get your SQL Warehouse HTTP path:
   - Navigate to SQL Warehouses in your Databricks workspace
   - Click on your warehouse
   - Go to Connection Details tab
   - Copy the HTTP Path (e.g., `/sql/1.0/warehouses/abc123def456`)

4. Create catalog and schema (Unity Catalog):
```sql
-- As admin user
CREATE CATALOG IF NOT EXISTS main;
CREATE SCHEMA IF NOT EXISTS main.chameleon;
CREATE SCHEMA IF NOT EXISTS main.analytics;

-- Grant permissions
GRANT ALL PRIVILEGES ON CATALOG main TO `chameleon_user@example.com`;
GRANT ALL PRIVILEGES ON SCHEMA main.chameleon TO `chameleon_user@example.com`;
GRANT ALL PRIVILEGES ON SCHEMA main.analytics TO `chameleon_user@example.com`;
```

5. Test connection:
```bash
python test_database_connectivity.py
```

**Connection Parameters:**

Key components of Databricks URL:
- `token:<access_token>` - Personal access token for authentication
- `<workspace_host>` - Your workspace URL (e.g., `adb-xxx.azuredatabricks.net`)
- `<http_path>` - SQL Warehouse HTTP path from connection details
- `catalog=<name>` - Unity Catalog name (required)
- `schema=<name>` - Schema/database name (required)

**Important Notes:**
- Use Personal Access Tokens (PAT) for authentication
- Requires a SQL Warehouse (formerly SQL Endpoints)
- Unity Catalog is recommended for production
- HTTP path identifies the SQL Warehouse
- Token should be kept secure (use environment variables)

**Security Best Practice for Databricks:**
```yaml
# Bad: Hardcoded token
metadata_database:
  url: "databricks://token:dapi1234@host/path?catalog=main&schema=default"

# Good: Use environment variable
metadata_database:
  url: "${DATABRICKS_URL}"
```

Then set environment variable:
```bash
export DATABRICKS_URL="databricks://token:dapi1234@host/path?catalog=main&schema=default"
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

### Enterprise Teradata Setup

```yaml
server:
  transport: "sse"
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"

metadata_database:
  url: "teradatasql://chameleon:secure_pass@tdprod.example.com/system_db"
  schema: "chameleon"

data_database:
  url: "teradatasql://chameleon:secure_pass@tdprod.example.com/edw"
  schema: "retail_analytics"
```

### Cloud Snowflake Setup

```yaml
server:
  transport: "sse"
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"

metadata_database:
  url: "snowflake://chameleon_user:pass@xy12345.us-east-1/CHAMELEON_META/PUBLIC?warehouse=SMALL_WH"

data_database:
  url: "snowflake://chameleon_user:pass@xy12345.us-east-1/ANALYTICS/RETAIL?warehouse=LARGE_WH&role=ANALYST_ROLE"
```

### Databricks Lakehouse Setup

```yaml
server:
  transport: "sse"
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"

metadata_database:
  url: "databricks://token:${DATABRICKS_TOKEN}@adb-xxx.azuredatabricks.net/sql/1.0/warehouses/wh123?catalog=main&schema=chameleon"

data_database:
  url: "databricks://token:${DATABRICKS_TOKEN}@adb-xxx.azuredatabricks.net/sql/1.0/warehouses/wh456?catalog=analytics&schema=retail"
```

### Multi-Cloud Hybrid Setup

```yaml
server:
  transport: "sse"
  host: "0.0.0.0"
  port: 8000
  log_level: "INFO"

# PostgreSQL for metadata (on-premises)
metadata_database:
  url: "postgresql://user:pass@onprem-db:5432/chameleon_meta"
  schema: "system"

# Snowflake for analytics data (cloud)
data_database:
  url: "snowflake://user:pass@account/ANALYTICS_DB/RETAIL?warehouse=ANALYTICS_WH"
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

**Teradata:**
- `tmode=TERA` or `tmode=ANSI` - SQL mode (TERA for Teradata extensions, ANSI for standard SQL)
- `charset=UTF8` - Character set encoding
- `account=myaccount` - Account string for resource tracking
- `logmech=TD2` or `logmech=LDAP` - Authentication mechanism

**Snowflake:**
- `warehouse=name` - Virtual warehouse (required for queries)
- `role=name` - Role for session access control
- `authenticator=externalbrowser` - Browser-based SSO authentication
- `application=chameleon` - Application identifier for tracking
- `client_session_keep_alive=true` - Keep connection alive

**Databricks:**
- `catalog=name` - Unity Catalog name (required)
- `schema=name` - Schema/database name (required)
- `http_path=path` - SQL Warehouse path (usually in main URL)
- `_user_agent_entry=chameleon` - User agent for tracking

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
pip install teradatasql    # For Teradata
pip install snowflake-sqlalchemy snowflake-connector-python  # For Snowflake
pip install databricks-sql-connector  # For Databricks
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
