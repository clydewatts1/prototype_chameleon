# Teradata, Snowflake, and Databricks Quick Reference

This guide provides quick reference information for connecting Chameleon MCP Server to Teradata, Snowflake, and Databricks databases.

## Quick Setup

### Teradata

**1. Install Driver:**
```bash
pip install teradatasql
```

**2. Connection String:**
```yaml
metadata_database:
  url: "teradatasql://user:password@host/database"
  schema: "schema_name"  # Optional
```

**3. Example:**
```yaml
metadata_database:
  url: "teradatasql://chameleon_user:pass@tdprod.example.com/analytics_db"
  schema: "chameleon"
```

**Key Features:**
- Enterprise data warehouse
- Parallel processing
- Schema support
- Advanced SQL features

---

### Snowflake

**1. Install Drivers:**
```bash
pip install snowflake-sqlalchemy snowflake-connector-python
```

**2. Connection String:**
```yaml
metadata_database:
  url: "snowflake://user:password@account/database/schema?warehouse=warehouse_name"
```

**3. Example:**
```yaml
metadata_database:
  url: "snowflake://chameleon:pass@xy12345.us-east-1/CHAMELEON_DB/PUBLIC?warehouse=COMPUTE_WH"
```

**Key Features:**
- Cloud-native data warehouse
- Automatic scaling
- Separation of storage and compute
- Pay-per-use pricing

**Important Notes:**
- Schema must be in URL path (not config.yaml schema field)
- Warehouse parameter is required
- Account includes region (e.g., xy12345.us-east-1)

---

### Databricks

**1. Install Driver:**
```bash
pip install databricks-sql-connector
```

**2. Connection String:**
```yaml
metadata_database:
  url: "databricks://token:ACCESS_TOKEN@workspace_host/http_path?catalog=catalog_name&schema=schema_name"
```

**3. Example:**
```yaml
metadata_database:
  url: "databricks://token:dapi123abc@adb-xxx.azuredatabricks.net/sql/1.0/warehouses/abc123?catalog=main&schema=chameleon"
```

**Key Features:**
- Lakehouse architecture
- Unity Catalog
- Delta Lake support
- Built on Apache Spark

**Important Notes:**
- Use Personal Access Token (PAT) for authentication
- Requires SQL Warehouse
- Catalog and schema are query parameters
- Never hardcode tokens (use environment variables)

**Getting Your Connection Details:**
1. **Access Token**: Profile → User Settings → Access Tokens → Generate New Token
2. **Workspace Host**: Your Databricks URL (e.g., adb-xxx.azuredatabricks.net)
3. **HTTP Path**: SQL Warehouses → Your Warehouse → Connection Details → HTTP Path
4. **Catalog/Schema**: Unity Catalog name and schema (default: main/default)

---

## Connection String Comparison

| Database | Protocol | Authentication | Example |
|----------|----------|----------------|---------|
| Teradata | `teradatasql://` | Username/Password | `teradatasql://user:pass@host/db` |
| Snowflake | `snowflake://` | Username/Password or SSO | `snowflake://user:pass@account/db/schema?warehouse=wh` |
| Databricks | `databricks://` | Personal Access Token | `databricks://token:PAT@host/path?catalog=cat&schema=sch` |

## Configuration File Locations

1. Project root: `./config.yaml` (takes precedence)
2. User home: `~/.chameleon/config/config.yaml`
3. Example configs: `./examples/config_*.yaml`

## Testing Connection

After configuring, test your connection:

```bash
python test_database_connectivity.py
```

Expected output:
```
Testing Metadata database...
URL: <your-connection-string>
✅ Metadata connection successful!
   Database type: <database-type>
```

## Common Parameters

### Teradata
- `tmode=TERA` - Teradata SQL mode
- `charset=UTF8` - Character encoding
- `logmech=LDAP` - Authentication mechanism

### Snowflake
- `warehouse=name` - Required for queries
- `role=name` - Session role
- `authenticator=externalbrowser` - SSO login

### Databricks
- `catalog=name` - Unity Catalog (required)
- `schema=name` - Schema/database (required)
- `http_path=path` - Usually in main URL

## Security Best Practices

### ❌ Bad - Hardcoded Credentials
```yaml
metadata_database:
  url: "snowflake://admin:password123@account/db/schema?warehouse=wh"
```

### ✅ Good - Environment Variables
```yaml
metadata_database:
  url: "${DATABASE_URL}"
```

```bash
export DATABASE_URL="snowflake://user:pass@account/db/schema?warehouse=wh"
```

### ✅ Best - Environment Variable for Token Only (Databricks)
```yaml
metadata_database:
  url: "databricks://token:${DATABRICKS_TOKEN}@host/path?catalog=main&schema=chameleon"
```

```bash
export DATABRICKS_TOKEN="dapi1234567890abcdef"
```

## Troubleshooting

### Driver Not Found
```bash
# Install the appropriate driver
pip install teradatasql                          # Teradata
pip install snowflake-sqlalchemy snowflake-connector-python  # Snowflake
pip install databricks-sql-connector             # Databricks
```

### Connection Refused
1. Verify database server is accessible
2. Check firewall rules
3. Verify host and port are correct
4. Test network connectivity

### Authentication Failed
1. Verify credentials are correct
2. Check user permissions
3. For Databricks: Verify token is valid and not expired
4. For Snowflake: Verify warehouse access

### Schema/Catalog Not Found
1. Verify schema/catalog exists
2. Check user has access permissions
3. For Snowflake: Schema must be in connection URL
4. For Databricks: Catalog and schema must be query parameters

## Full Documentation

For comprehensive documentation, see:
- [DATABASE_CONNECTIVITY.md](DATABASE_CONNECTIVITY.md) - Complete database connectivity guide
- [ENTERPRISE_DATABASE_CONFIG.md](server/ENTERPRISE_DATABASE_CONFIG.md) - Enterprise configuration
- Example configs: `examples/config_*.yaml`

## Example Configurations

Full example configuration files are available:
- `examples/config_teradata.yaml` - Teradata setup
- `examples/config_snowflake.yaml` - Snowflake setup
- `examples/config_databricks.yaml` - Databricks setup

Copy and customize these files for your environment.
