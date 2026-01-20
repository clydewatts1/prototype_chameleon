# Quick Reference: Database Connection Strings

This document provides a quick reference for all supported database connection strings.
For detailed documentation, see [DATABASE_CONNECTIVITY.md](DATABASE_CONNECTIVITY.md).

## SQLite (Default)

### Metadata Database
```yaml
metadata_database:
  url: "sqlite:///chameleon_meta.db"
```

### Data Database
```yaml
data_database:
  url: "sqlite:///chameleon_data.db"
```

### Other SQLite Formats
```yaml
# Absolute path
url: "sqlite:////absolute/path/to/database.db"

# In-memory (testing)
url: "sqlite:///:memory:"
```

---

## PostgreSQL

### Basic Connection
```yaml
metadata_database:
  url: "postgresql://username:password@localhost:5432/chameleon_meta"

data_database:
  url: "postgresql://username:password@localhost:5432/chameleon_data"
```

### With Schema
```yaml
metadata_database:
  url: "postgresql://username:password@localhost:5432/chameleon_meta"
  schema: "chameleon"

data_database:
  url: "postgresql://username:password@localhost:5432/chameleon_data"
  schema: "retail"
```

### With SSL
```yaml
metadata_database:
  url: "postgresql://username:password@db.example.com:5432/chameleon_meta?sslmode=require"
```

### Remote Server
```yaml
metadata_database:
  url: "postgresql://user:pass@db-server.example.com:5432/chameleon_meta"
```

---

## MySQL

### Basic Connection
```yaml
metadata_database:
  url: "mysql+pymysql://username:password@localhost:3306/chameleon_meta"

data_database:
  url: "mysql+pymysql://username:password@localhost:3306/chameleon_data"
```

### With Character Set
```yaml
metadata_database:
  url: "mysql+pymysql://username:password@localhost:3306/chameleon_meta?charset=utf8mb4"
```

### With Timezone
```yaml
metadata_database:
  url: "mysql+pymysql://username:password@localhost:3306/chameleon_meta?charset=utf8mb4&time_zone=%2B00:00"
```

### With SSL
```yaml
metadata_database:
  url: "mysql+pymysql://username:password@db.example.com:3306/chameleon_meta?ssl_ca=/path/to/ca.pem"
```

---

## Neo4j (Experimental - Data Database Only)

### Bolt Protocol
```yaml
data_database:
  url: "bolt://neo4j:password@localhost:7687"
```

### Neo4j Protocol
```yaml
data_database:
  url: "neo4j://neo4j:password@localhost:7687"
```

### Secure Connection
```yaml
data_database:
  url: "neo4j+s://neo4j:password@db.example.com:7687"
```

### Neo4j Aura (Cloud)
```yaml
data_database:
  url: "neo4j+s://username:password@xxxxx.databases.neo4j.io:7687"
```

⚠️ **Important**: Neo4j is a graph database and should only be used for the data database.
Use PostgreSQL or MySQL for the metadata database.

---

## Complete Configuration Examples

### Development (SQLite)
```yaml
server:
  transport: "stdio"
  log_level: "DEBUG"

metadata_database:
  url: "sqlite:///chameleon_meta.db"

data_database:
  url: "sqlite:///chameleon_data.db"
```

### Production (PostgreSQL)
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

### Hybrid (PostgreSQL + Neo4j)
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

---

## Installation Requirements

### PostgreSQL
```bash
pip install psycopg2-binary
```

### MySQL
```bash
pip install pymysql
```

### Neo4j
```bash
pip install neo4j
```

### All Drivers
```bash
pip install psycopg2-binary pymysql neo4j
```

---

## Testing Connectivity

Run the database connectivity test script:

```bash
python test_database_connectivity.py
```

This will test connections to all configured databases and provide detailed feedback.

---

## See Also

- [DATABASE_CONNECTIVITY.md](DATABASE_CONNECTIVITY.md) - Comprehensive documentation
- [server/config.yaml.sample](server/config.yaml.sample) - Configuration template
- [README.md](README.md) - Main project documentation
