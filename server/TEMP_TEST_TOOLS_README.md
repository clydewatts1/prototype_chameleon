# Temporary Test Tools Feature

## Overview

The Temporary Test Tools feature allows LLMs to create temporary, dynamic SQL tools for testing and development purposes. These tools are:

- **Not persisted** to the database (exist only in memory)
- **Automatically limited** to 3 rows (LIMIT 3 constraint)
- **SELECT-only** (read-only, security validated)
- **Perfect for testing** SQL queries without cluttering the permanent tool registry

## Key Components

### 1. In-Memory Storage (`server/runtime.py`)

Two global dictionaries store temporary tools:

```python
TEMP_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}
# Key: "tool_name:persona"
# Value: {description, input_schema, target_persona, code_hash, is_temp}

TEMP_CODE_VAULT: Dict[str, Dict[str, Any]] = {}
# Key: code_hash (SHA-256)
# Value: {code_blob, code_type}
```

### 2. Tool Creator (`tools/system/test_tool_creator.py`)

The `CreateTempTestTool` class provides the meta-tool that LLMs use to create temporary tools:

```python
class CreateTempTestTool(ChameleonTool):
    """Create temporary test tools with automatic LIMIT 3 constraint."""
```

### 3. Registration Script (`server/add_temp_tool_creator.py`)

Registers the `create_temp_test_tool` meta-tool in the database:

```bash
python server/add_temp_tool_creator.py
```

## Usage

### Creating a Temporary Test Tool

Use the `create_temp_test_tool` meta-tool via MCP:

```json
{
  "tool": "create_temp_test_tool",
  "arguments": {
    "tool_name": "test_sales",
    "description": "Test query for sales data",
    "sql_query": "SELECT * FROM sales_per_day WHERE store_name = :store_name",
    "parameters": {
      "store_name": {
        "type": "string",
        "description": "Store name to filter by",
        "required": true
      }
    }
  }
}
```

### Executing a Temporary Tool

Once created, execute like any other tool:

```json
{
  "tool": "test_sales",
  "arguments": {
    "store_name": "Store A"
  }
}
```

**Result:** Returns at most 3 rows, even if more match the query.

## Features

### Automatic LIMIT 3 Constraint

All temporary SQL tools automatically have `LIMIT 3` injected into their queries:

- If the query has no LIMIT: `LIMIT 3` is added
- If the query has `LIMIT 10`: It's replaced with `LIMIT 3`
- This prevents large data retrieval during testing

Example:
```sql
-- Original query
SELECT * FROM sales_per_day ORDER BY business_date

-- Executed as
SELECT * FROM sales_per_day ORDER BY business_date LIMIT 3
```

### Security Validation

Temporary tools enforce the same security as permanent SQL tools:

1. **SELECT-only**: Only SELECT statements are allowed
2. **No semicolons**: Prevents SQL injection via statement chaining
3. **Single statement**: Only one statement per query
4. **Comment handling**: SQL comments are properly handled

### Execution Logging

Temporary tool executions are logged to the `ExecutionLog` table:

- Success/failure status
- Input arguments
- Result summary
- Full traceback for errors

This enables the `get_last_error` tool to retrieve errors from temporary tools.

### Tool Listing

Temporary tools appear in `list_tools_for_persona()` with a `[TEMP-TEST]` prefix:

```
[TEMP-TEST] Test query for sales data
```

## Workflow Example

```python
# 1. LLM creates temporary tool to test a query
create_temp_test_tool(
    tool_name="test_sales",
    sql_query="SELECT * FROM sales_per_day",
    description="Test sales query",
    parameters={}
)

# 2. LLM executes the temporary tool
result = test_sales()  # Returns max 3 rows

# 3. LLM checks for errors (if any)
error = get_last_error(tool_name="test_sales")

# 4. LLM refines the query and creates a new version
create_temp_test_tool(
    tool_name="test_sales",  # Overwrites previous
    sql_query="SELECT * FROM sales_per_day WHERE department = :dept",
    description="Test sales query by department",
    parameters={"dept": {"type": "string", "required": True}}
)

# 5. Once satisfied, LLM can create a permanent tool
create_new_sql_tool(
    tool_name="get_sales_by_department",
    sql_query="SELECT * FROM sales_per_day WHERE department = :dept",
    description="Get sales by department",
    parameters={"dept": {"type": "string", "required": True}}
)
```

## Implementation Details

### Modified Functions in `server/runtime.py`

#### `execute_tool()`

1. Checks `TEMP_TOOL_REGISTRY` first before querying database
2. Fetches code from `TEMP_CODE_VAULT` for temporary tools
3. Injects `LIMIT 3` for temporary SQL tools:
   ```python
   if is_temp_tool:
       sql_no_limit = re.sub(r'\s+LIMIT\s+\d+\s*$', '', sql_stripped, flags=re.IGNORECASE)
       rendered_sql = f"{sql_no_limit} LIMIT 3"
   ```
4. Logs execution normally (to database)

#### `list_tools_for_persona()`

Appends temporary tools to the result list with `[TEMP-TEST]` prefix:

```python
for key, tool_meta in TEMP_TOOL_REGISTRY.items():
    tool_name_from_key, tool_persona = key.split(':', 1)
    if tool_persona == persona:
        desc = f"[TEMP-TEST] {tool_meta['description']}"
        results.append({...})
```

## Testing

### Automated Tests (`tests/test_temp_test_tools_pytest.py`)

12 comprehensive tests covering:

- ✅ Meta-tool registration
- ✅ Temporary tool creation
- ✅ Tool creation with parameters
- ✅ Execution with LIMIT 3 constraint
- ✅ LIMIT override verification
- ✅ Security validation (non-SELECT rejection)
- ✅ Semicolon injection blocking
- ✅ Tool listing includes temporary tools
- ✅ Execution logging
- ✅ Error logging
- ✅ Non-persistence verification
- ✅ Missing field validation

Run tests:
```bash
pytest tests/test_temp_test_tools_pytest.py -v
```

### Manual Testing

See `/tmp/test_temp_tools_workflow.py` for a complete workflow demonstration.

## Benefits

1. **Rapid Iteration**: Test queries without database pollution
2. **Safety**: Automatic row limiting prevents large data retrieval
3. **Debugging**: Full execution logs for troubleshooting
4. **Clean Registry**: Keeps permanent tool registry focused
5. **Self-Healing**: LLMs can iterate on failed queries using error logs

## Limitations

1. **Memory-only**: Tools are lost when the server restarts
2. **No persistence**: Cannot be shared across sessions
3. **Fixed row limit**: Always returns max 3 rows (by design)
4. **SELECT-only**: Cannot test INSERT/UPDATE/DELETE (security feature)

## Future Enhancements

Possible future improvements:

- Configurable row limit (e.g., LIMIT 5, LIMIT 10)
- Temporary tool expiration (TTL)
- Export temporary tool to permanent tool
- Temporary tool analytics (usage stats)
- Multi-user temporary tool isolation
