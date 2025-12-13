# SQL Creator Meta-Tool

## Overview

The SQL Creator Meta-Tool is a "self-modifying" feature for the Chameleon MCP Server that allows an LLM to dynamically create new SQL-based tools at runtime. This enables the LLM to extend its own capabilities while maintaining strict security constraints.

## Key Features

- **Dynamic Tool Creation**: LLM can create new SQL query tools without manual code deployment
- **Security-First Design**: Only SELECT queries are allowed (read-only operations)
- **Injection Prevention**: Validates queries to prevent SQL injection attacks
- **Immediate Availability**: Created tools are instantly available for use
- **Parameterized Queries**: Supports dynamic parameters with proper schema validation

## Installation

1. Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

2. Run the bootstrap script to register the meta-tool:
```bash
python add_sql_creator_tool.py
```

This will register the `create_new_sql_tool` meta-tool in your database.

## Usage

### Creating a Simple SQL Tool

The LLM can call the `create_new_sql_tool` meta-tool with the following parameters:

```json
{
  "tool_name": "get_all_stores",
  "description": "Get all unique store names from sales data",
  "sql_query": "SELECT DISTINCT store_name FROM sales_per_day ORDER BY store_name",
  "parameters": {}
}
```

### Creating a Parameterized SQL Tool

For tools that need parameters:

```json
{
  "tool_name": "get_sales_by_store",
  "description": "Get sales records filtered by store name",
  "sql_query": "SELECT * FROM sales_per_day WHERE store_name = :store_name",
  "parameters": {
    "store_name": {
      "type": "string",
      "description": "Name of the store to filter by",
      "required": true
    }
  }
}
```

### Complex Example with Multiple Parameters

```json
{
  "tool_name": "get_sales_report",
  "description": "Get sales report for a date range",
  "sql_query": "SELECT business_date, SUM(sales_amount) as total FROM sales_per_day WHERE business_date >= :start_date AND business_date <= :end_date GROUP BY business_date",
  "parameters": {
    "start_date": {
      "type": "string",
      "description": "Start date in YYYY-MM-DD format",
      "required": true
    },
    "end_date": {
      "type": "string",
      "description": "End date in YYYY-MM-DD format",
      "required": true
    }
  }
}
```

### Advanced: Using Jinja2 Conditionals for Optional Filters

Created SQL tools support Jinja2 templates for conditional SQL structure. This allows you to make filters optional:

**Important:** Use Jinja2 for SQL **structure** only (e.g., optional WHERE clauses). Always use SQLAlchemy parameter binding (`:param_name`) for **values**.

```json
{
  "tool_name": "search_sales",
  "description": "Search sales with optional filters for store, department, and minimum amount",
  "sql_query": "SELECT * FROM sales_per_day WHERE 1=1 {% if arguments.store_name %} AND store_name = :store_name {% endif %} {% if arguments.department %} AND department = :department {% endif %} {% if arguments.min_amount %} AND sales_amount >= :min_amount {% endif %} ORDER BY business_date DESC",
  "parameters": {
    "store_name": {
      "type": "string",
      "description": "Optional filter by store name",
      "required": false
    },
    "department": {
      "type": "string",
      "description": "Optional filter by department",
      "required": false
    },
    "min_amount": {
      "type": "number",
      "description": "Optional minimum sales amount filter",
      "required": false
    }
  }
}
```

**How Jinja2 Works in SQL Tools:**

1. **Template Rendering**: Jinja2 renders the SQL structure first
   - `{% if arguments.field %}` checks if the argument was provided
   - Jinja2 conditionally includes or excludes parts of the SQL

2. **Parameter Binding**: After rendering, SQLAlchemy binds values safely
   - `:param_name` syntax in SQL refers to parameters
   - Values are passed separately to prevent SQL injection

**Example Flow:**

When called with `{"store_name": "Store A"}`:
```sql
-- After Jinja2 rendering:
SELECT * FROM sales_per_day WHERE 1=1 
  AND store_name = :store_name 
ORDER BY business_date DESC

-- After SQLAlchemy binding with {"store_name": "Store A"}:
-- Safely executes with proper parameter binding
```

When called with `{}` (no parameters):
```sql
-- After Jinja2 rendering (conditionals removed):
SELECT * FROM sales_per_day WHERE 1=1 
ORDER BY business_date DESC

-- No parameters to bind
```

**Security Rules:**
- ✅ **CORRECT**: `{% if arguments.category %} AND category = :category {% endif %}`
- ❌ **WRONG**: `AND category = '{{ arguments.category }}'` (SQL injection risk!)
- ✅ **CORRECT**: Use `:param_name` for all values
- ❌ **WRONG**: String interpolation or Jinja2 for values

## Security Features

### 1. SELECT-Only Validation

The meta-tool validates that all SQL queries start with `SELECT` (case-insensitive, after removing comments). Any attempt to use INSERT, UPDATE, DELETE, DROP, ALTER, or other write operations will be rejected.

**Blocked Examples:**
- `INSERT INTO users ...`
- `UPDATE products SET ...`
- `DELETE FROM orders ...`
- `DROP TABLE ...`

### 2. Semicolon Injection Prevention

The meta-tool checks for semicolons in the middle of queries to prevent statement chaining attacks. Only trailing semicolons are allowed.

**Blocked Example:**
```sql
SELECT * FROM users; DROP TABLE users;
```

### 3. Comment Removal Before Validation

SQL comments (both `--` single-line and `/* */` multi-line) are removed before validation to prevent comment-based bypasses.

### 4. Forced Code Type

All SQL tools created by the meta-tool are stored in CodeVault with `code_type='select'`, ensuring they are executed using the secure SQL runtime path.

## Architecture

### How It Works

1. **LLM calls `create_new_sql_tool`** with tool specification
2. **Validation Phase**:
   - Check all required fields are present
   - Validate query starts with SELECT
   - Check for semicolons (injection prevention)
3. **Database Operations**:
   - Compute SHA-256 hash of SQL query
   - Upsert code into CodeVault with `code_type='select'`
   - Construct input_schema from parameters
   - Upsert tool into ToolRegistry with default persona
4. **Tool Ready**: New tool is immediately available for execution

### Database Schema

**CodeVault Entry:**
- `hash`: SHA-256 hash of the SQL query
- `code_blob`: The SQL query text
- `code_type`: Always `'select'` for SQL creator tools

**ToolRegistry Entry:**
- `tool_name`: Name provided by LLM
- `target_persona`: Always `'default'`
- `description`: Description provided by LLM
- `input_schema`: JSON Schema constructed from parameters
- `active_hash_ref`: Reference to CodeVault hash

## Testing

Run the comprehensive test suite:

```bash
python test_sql_creator_tool.py
```

The test suite covers:
- Meta-tool registration
- Simple SQL tool creation
- Parameterized SQL tool creation
- Security validation (non-SELECT queries, semicolon injection)
- Execution of dynamically created tools
- Idempotency
- Missing required field validation

Run the demonstration:

```bash
python demo_sql_creator.py
```

## Example Workflow

```python
from sqlmodel import Session
from models import get_engine
from runtime import execute_tool

engine = get_engine("sqlite:///chameleon.db")

with Session(engine) as session:
    # Step 1: Create a new SQL tool
    result = execute_tool(
        "create_new_sql_tool",
        "default",
        {
            "tool_name": "get_electronics_sales",
            "description": "Get all electronics sales",
            "sql_query": "SELECT * FROM sales_per_day WHERE department = :department",
            "parameters": {
                "department": {
                    "type": "string",
                    "description": "Department name",
                    "required": True
                }
            }
        },
        session
    )
    print(result)  # Success: Tool 'get_electronics_sales' has been registered...
    
    # Step 2: Use the newly created tool
    sales = execute_tool(
        "get_electronics_sales",
        "default",
        {"department": "Electronics"},
        session
    )
    print(f"Found {len(sales)} electronics sales records")
```

## Limitations

1. **SELECT-Only**: Only read-only SELECT queries are allowed. Write operations require manual tool creation.
2. **Default Persona**: All SQL creator tools target the default persona.
3. **No Python Logic**: Created tools can only execute SQL queries, not custom Python code.
4. **Security Trade-offs**: While the meta-tool validates queries, it assumes the LLM is not actively malicious. Additional sandboxing may be needed for untrusted environments.

## Best Practices

1. **Descriptive Names**: Use clear, descriptive tool names (e.g., `get_sales_by_department` not `query1`)
2. **Good Descriptions**: Provide detailed descriptions so the LLM knows when to use the tool
3. **Parameter Documentation**: Document parameters with clear types and descriptions
4. **Use Parameters**: Always use `:param_name` syntax for values (SQLAlchemy parameter binding)
5. **Test Queries**: Test SQL queries manually before creating tools
6. **Idempotency**: It's safe to create the same tool multiple times (updates existing)

## Security Considerations

The SQL Creator Meta-Tool is designed with security as a primary concern, but users should be aware of the following:

1. **Trusted LLM Assumption**: The design assumes the LLM is not actively malicious. In highly sensitive environments, additional controls may be needed.

2. **Read-Only Enforcement**: Only SELECT queries are allowed, preventing data modification. However, complex SELECT queries can still:
   - Consume significant database resources
   - Access any table/column visible to the database user
   - Return large amounts of data

3. **Database Permissions**: The database user should have read-only permissions to limit exposure.

4. **Query Complexity**: There are no built-in limits on query complexity, which could lead to performance issues.

5. **Schema Exposure**: The LLM can create tools to query any accessible table, potentially exposing database schema information.

## Future Enhancements

Potential improvements for future versions:

- Query complexity limits (max rows, joins, etc.)
- Table/column allowlists
- Query cost estimation
- Multi-persona support
- Query templates with constrained parameters
- Audit logging of created tools
- Tool versioning and rollback

## Contributing

When contributing to the SQL Creator Tool:

1. All changes must maintain the security-first design
2. Add tests for any new validation logic
3. Update this README with new features or limitations
4. Consider backward compatibility with existing tools

## License

Same as the Chameleon MCP Server project.
