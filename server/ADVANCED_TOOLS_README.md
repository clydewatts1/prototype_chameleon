# Advanced Data Tools for Chameleon MCP Server

This document describes the Advanced Data Tools (MERGE and DDL) that enable sophisticated data and schema manipulation in the Chameleon MCP Server.

## Overview

The Advanced Data Tools consist of two powerful tools that allow LLMs to perform write operations and schema changes:

1. **`general_merge_tool`** - Upsert data (Insert or Update) with dialect-specific SQL
2. **`execute_ddl_tool`** - Execute DDL commands with safety checks

Both tools are manually defined (not auto-generated) and use Jinja2 templates to handle dialect differences between SQLite, PostgreSQL, and standard SQL databases (Teradata, Databricks).

## Installation

Register the tools in your metadata database:

```bash
cd server
python add_advanced_tools.py
```

This will:
- Create entries in `CodeVault` for both tool implementations
- Register tools in `ToolRegistry` for the `default` persona
- Display usage examples

## Tool 1: `general_merge_tool`

### Purpose
Perform upsert operations (Insert or Update) based on a key column. Automatically detects the database dialect and uses the appropriate SQL syntax.

### Dialect-Specific SQL

**SQLite:**
```sql
INSERT OR REPLACE INTO table_name (columns)
VALUES (values)
```

**PostgreSQL:**
```sql
INSERT INTO table_name (columns)
VALUES (values)
ON CONFLICT (key_column) DO UPDATE SET
  column1 = EXCLUDED.column1,
  column2 = EXCLUDED.column2
```

**Standard SQL (Teradata/Databricks):**
```sql
MERGE INTO table_name AS target
USING (SELECT :col1 AS col1, :col2 AS col2) AS source
ON target.key_column = source.key_column
WHEN MATCHED THEN
  UPDATE SET column1 = source.column1
WHEN NOT MATCHED THEN
  INSERT (columns) VALUES (source.values)
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `table_name` | string | Yes | Name of the table to merge data into |
| `key_column` | string | Yes | Name of the key column for matching (e.g., 'id') |
| `key_value` | string | Yes | Value of the key to match/insert |
| `data` | string | Yes | JSON string of columns to update/insert |

### Example Usage

**Insert a new record:**
```json
{
  "table_name": "product_catalog",
  "key_column": "product_id",
  "key_value": "123",
  "data": "{\"product_name\": \"Laptop Pro\", \"category\": \"Electronics\", \"price\": 1299.99, \"stock_quantity\": 50}"
}
```

**Update an existing record:**
```json
{
  "table_name": "product_catalog",
  "key_column": "product_id",
  "key_value": "123",
  "data": "{\"product_name\": \"Laptop Pro\", \"category\": \"Electronics\", \"price\": 1199.99, \"stock_quantity\": 45}"
}
```

The tool automatically:
- Detects if the record exists based on the key
- Inserts if not found
- Updates if found
- Uses the appropriate SQL syntax for the database dialect

### Implementation Details

- **Type**: Python tool (`code_type='python'`)
- **Inherits from**: `ChameleonTool`
- **Database**: Executes against `data_session` (business data)
- **Dialect Detection**: Automatically detects SQLite, PostgreSQL, or standard SQL
- **Parameter Binding**: Uses SQLAlchemy parameter binding for all values
- **Error Handling**: Comprehensive validation and error messages

## Tool 2: `execute_ddl_tool`

### Purpose
Execute Data Definition Language (DDL) commands to modify database schema. Includes multiple safety checks to prevent accidental schema changes.

### Allowed DDL Commands

- `CREATE` - Create new tables, indexes, views, etc.
- `ALTER` - Modify existing table structures
- `DROP` - Remove tables, indexes, views, etc.
- `TRUNCATE` - Remove all rows from a table

### Safety Features

1. **Explicit Confirmation Required**: Must set `confirmation = "YES"` (all caps)
2. **DDL Keyword Validation**: Only allows DDL commands (rejects SELECT, INSERT, UPDATE, DELETE)
3. **Single Statement Only**: Prevents SQL injection via statement chaining
4. **Comment Removal**: Removes SQL comments before validation

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ddl_command` | string | Yes | DDL command to execute |
| `confirmation` | string | Yes | Must be "YES" (all caps) to confirm execution |

### Example Usage

**Create a table:**
```json
{
  "ddl_command": "CREATE TABLE product_catalog (product_id INTEGER PRIMARY KEY, product_name TEXT NOT NULL, price REAL)",
  "confirmation": "YES"
}
```

**Add a column:**
```json
{
  "ddl_command": "ALTER TABLE product_catalog ADD COLUMN supplier TEXT",
  "confirmation": "YES"
}
```

**Drop a table:**
```json
{
  "ddl_command": "DROP TABLE old_table",
  "confirmation": "YES"
}
```

### Security Validations

The tool performs the following security checks:

1. **Confirmation Check**: Requires `confirmation == "YES"`
   ```python
   if confirmation != 'YES':
       raise ValueError("DDL execution requires explicit confirmation")
   ```

2. **DDL Keyword Validation**: Ensures command starts with allowed keywords
   ```python
   allowed_ddl_keywords = ['CREATE', 'ALTER', 'DROP', 'TRUNCATE']
   is_valid_ddl = any(sql_cleaned.startswith(keyword) for keyword in allowed_ddl_keywords)
   ```

3. **Single Statement Check**: Prevents multiple statements
   ```python
   sql_stripped = ddl_command.rstrip().rstrip(';').rstrip()
   if ';' in sql_stripped:
       raise ValueError("Multiple SQL statements detected")
   ```

### Implementation Details

- **Type**: Python tool (`code_type='python'`)
- **Inherits from**: `ChameleonTool`
- **Database**: Executes against `data_session` (business data)
- **Comment Handling**: Removes both single-line (`--`) and multi-line (`/* */`) comments
- **Error Handling**: Rolls back on failure with detailed error messages

## Integration with Chameleon MCP Server

Both tools integrate seamlessly with the Chameleon architecture:

### Database Sessions
- Use `data_session` for business data operations
- Require `data_session` to be available (check before execution)
- Log executions to `ExecutionLog` table in metadata DB

### Error Handling
- Raise descriptive errors for validation failures
- Roll back transactions on failure
- Log all executions (success and failure) for audit trail

### Execution Logging
All tool executions are logged to the `ExecutionLog` table with:
- Timestamp
- Tool name and persona
- Input arguments
- Success/failure status
- Result summary or error traceback

## Testing

Comprehensive test suite included in `tests/test_advanced_tools_pytest.py`:

### MERGE Tool Tests
- ✅ Insert new records
- ✅ Update existing records
- ✅ Invalid JSON validation
- ✅ Missing arguments validation
- ✅ Integration with SalesPerDay table

### DDL Tool Tests
- ✅ CREATE TABLE operations
- ✅ ALTER TABLE operations
- ✅ DROP TABLE operations
- ✅ Confirmation requirement validation
- ✅ DDL keyword validation
- ✅ Multiple statement prevention
- ✅ SELECT statement rejection

Run tests:
```bash
pytest tests/test_advanced_tools_pytest.py -v
```

## Workflow Example

Here's a complete workflow demonstrating both tools:

```python
# 1. Create a new table
execute_tool(
    tool_name='execute_ddl_tool',
    persona='default',
    arguments={
        'ddl_command': '''
            CREATE TABLE product_catalog (
                product_id INTEGER PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT,
                price REAL,
                stock_quantity INTEGER
            )
        ''',
        'confirmation': 'YES'
    }
)

# 2. Insert a product
execute_tool(
    tool_name='general_merge_tool',
    persona='default',
    arguments={
        'table_name': 'product_catalog',
        'key_column': 'product_id',
        'key_value': '1',
        'data': json.dumps({
            'product_name': 'Laptop Pro',
            'category': 'Electronics',
            'price': 1299.99,
            'stock_quantity': 50
        })
    }
)

# 3. Update the product (price change)
execute_tool(
    tool_name='general_merge_tool',
    persona='default',
    arguments={
        'table_name': 'product_catalog',
        'key_column': 'product_id',
        'key_value': '1',
        'data': json.dumps({
            'product_name': 'Laptop Pro',
            'category': 'Electronics',
            'price': 1199.99,  # Price reduced
            'stock_quantity': 45
        })
    }
)

# 4. Add a new column
execute_tool(
    tool_name='execute_ddl_tool',
    persona='default',
    arguments={
        'ddl_command': 'ALTER TABLE product_catalog ADD COLUMN supplier TEXT',
        'confirmation': 'YES'
    }
)

# 5. Insert another product with the new column
execute_tool(
    tool_name='general_merge_tool',
    persona='default',
    arguments={
        'table_name': 'product_catalog',
        'key_column': 'product_id',
        'key_value': '2',
        'data': json.dumps({
            'product_name': 'Wireless Mouse',
            'category': 'Accessories',
            'price': 29.99,
            'stock_quantity': 200,
            'supplier': 'TechSupplies Inc.'
        })
    }
)
```

## Security Considerations

⚠️ **Important Security Notes:**

1. **Trust Model**: These tools execute write operations and schema changes. Only use with trusted LLM agents.

2. **Confirmation Requirement**: DDL tool requires explicit "YES" confirmation to prevent accidental changes.

3. **Database Permissions**: Ensure the database user has appropriate permissions for the operations.

4. **Audit Trail**: All operations are logged in `ExecutionLog` table for accountability.

5. **Parameter Binding**: All values use SQLAlchemy parameter binding to prevent SQL injection.

6. **Statement Validation**: Both tools prevent multiple statement execution.

## Troubleshooting

### "Business database is currently offline"
- Ensure `data_session` is configured and available
- Use `reconnect_db` tool to reconnect to the database

### "DDL execution requires explicit confirmation"
- Set `confirmation` parameter to "YES" (all uppercase)

### "Invalid DDL command"
- Ensure command starts with CREATE, ALTER, DROP, or TRUNCATE
- Remove any non-DDL statements

### "Invalid JSON in 'data' argument"
- Ensure `data` parameter is a valid JSON string
- Use `json.dumps()` to create valid JSON

### "Multiple SQL statements detected"
- Remove semicolons from the middle of the statement
- Only one statement allowed per execution

## Maintenance

### Updating Tool Code

If you need to update the tool implementations:

1. Modify the code in `server/add_advanced_tools.py`
2. Run the registration script again: `python add_advanced_tools.py`
3. The script will update the hash and re-register the tools

### Monitoring Usage

Query the `ExecutionLog` table to monitor tool usage:

```python
from sqlmodel import select
from models import ExecutionLog

# Get recent DDL operations
recent_ddl = session.exec(
    select(ExecutionLog)
    .where(ExecutionLog.tool_name == 'execute_ddl_tool')
    .order_by(ExecutionLog.timestamp.desc())
    .limit(10)
).all()

# Get failed merge operations
failed_merges = session.exec(
    select(ExecutionLog)
    .where(
        ExecutionLog.tool_name == 'general_merge_tool',
        ExecutionLog.status == 'FAILURE'
    )
).all()
```

## License

These tools are part of the Chameleon MCP Server project.
