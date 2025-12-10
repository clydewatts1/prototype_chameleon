# Enterprise Database Configuration

This document describes the enterprise database configuration features added to the Chameleon MCP Server.

## Overview

The Chameleon MCP Server now supports flexible database configuration for enterprise environments, including:

- **Custom Table Names**: Rename any table to comply with organizational naming conventions
- **Schema Prefixes**: Use database schemas for multi-tenant or organized deployments
- **Multiple Database Engines**: Support for PostgreSQL, Teradata, MySQL, and other SQLAlchemy-compatible databases
- **Backward Compatibility**: Works seamlessly with existing SQLite configurations

## Configuration

Configuration is managed through `~/.chameleon/config/config.yaml`.

### Basic Configuration (SQLite)

The default configuration uses SQLite with standard table names:

```yaml
database:
  url: "sqlite:///chameleon.db"
```

### Custom Table Names

Rename tables to match your naming conventions:

```yaml
database:
  url: "sqlite:///chameleon.db"

tables:
  code_vault: "mcp_code_storage"
  tool_registry: "mcp_tools_v1"
  resource_registry: "mcp_resources"
  prompt_registry: "mcp_prompts"
  sales_per_day: "fact_sales_daily"
```

### Schema Prefix (Enterprise Databases)

Use a schema prefix for PostgreSQL, Teradata, or other enterprise databases:

```yaml
database:
  url: "postgresql://user:password@host:5432/database"
  schema: "retail_data"

tables:
  tool_registry: "chameleon_tools"
  # Other tables use defaults
```

This creates tables like `retail_data.chameleon_tools` in your database.

### Full Enterprise Configuration

Complete example for Teradata deployment:

```yaml
server:
  transport: "sse"
  port: 9000
  log_level: "INFO"

database:
  url: "teradata://admin:secret@prod-db.example.com/analytics"
  schema: "mcp_prod"

tables:
  code_vault: "chameleon_code"
  tool_registry: "chameleon_tools"
  resource_registry: "chameleon_resources"
  prompt_registry: "chameleon_prompts"
  sales_per_day: "fact_sales_daily"
```

## Table Name Mappings

| Logical Name | Default Table Name | Description |
|--------------|-------------------|-------------|
| `code_vault` | `codevault` | Stores executable code with hash keys |
| `tool_registry` | `toolregistry` | Tool definitions and configurations |
| `resource_registry` | `resourceregistry` | Resource definitions |
| `prompt_registry` | `promptregistry` | Prompt templates |
| `sales_per_day` | `sales_per_day` | Sample sales data table |

## Backward Compatibility

If no configuration file exists or if the new fields are omitted, the system uses defaults:

- Database: `sqlite:///chameleon.db`
- Schema: None (SQLite default)
- Table names: Original defaults (codevault, toolregistry, etc.)

All existing code, scripts, and deployments continue to work without any changes.

## Foreign Key Handling

Foreign keys automatically include schema prefixes when configured:

- **Without schema**: `codevault.hash`
- **With schema**: `retail_data.codevault.hash`

This is handled transparently by the models.

## Testing

Run the test suites to verify configuration:

```bash
# Test basic configuration
python test_config.py

# Test dynamic configuration features
python test_dynamic_config.py

# Test enterprise integration scenarios
python test_enterprise_integration.py

# Test database seeding
python test_seed_db.py
```

## Examples

### Example 1: PostgreSQL with Custom Names

```yaml
database:
  url: "postgresql://chameleon:pass@db.company.com:5432/apps"
  schema: "chameleon_prod"

tables:
  tool_registry: "app_tools"
  code_vault: "app_code"
```

### Example 2: Teradata with Standard Names

```yaml
database:
  url: "teradata://user:pass@teradata.company.com/EDW"
  schema: "MCP_APPS"
  # Uses default table names with schema prefix
```

### Example 3: MySQL with Partial Customization

```yaml
database:
  url: "mysql://root:password@localhost:3306/chameleon"

tables:
  tool_registry: "custom_tools"
  # Other tables use defaults
```

## Migration from Default SQLite

To migrate an existing SQLite deployment to an enterprise database:

1. Create your configuration file with the new database URL
2. Optionally add schema and table name customizations
3. Run the database initialization: `python seed_db.py`
4. Migrate data from SQLite if needed (use standard database migration tools)

## Implementation Details

The configuration is loaded at module import time in `models.py`:

- Table names are applied via `__tablename__` attributes
- Schema prefixes are applied via `__table_args__`
- Foreign keys use the `_get_foreign_key()` helper to construct references

This design ensures all database operations use the configured names and schemas automatically.
