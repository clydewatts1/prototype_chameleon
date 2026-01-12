# Deep Execution Audit System - ExecutionLog

## Overview

The Deep Execution Audit System implements the "Black Box" Recorder pattern for the Chameleon MCP Server. This is **the single most important feature for an autonomous "Self-Healing" agent**.

When an LLM creates a broken tool, it typically receives only a generic "Error" message. The ExecutionLog system changes this by:

1. **Recording** every tool execution (inputs, outputs, and full error tracebacks)
2. **Storing** execution details in a queryable database table
3. **Providing** a tool (`get_last_error`) to retrieve detailed error information
4. **Enabling** AI agents to self-diagnose and patch broken code

## Architecture

### Components

1. **ExecutionLog Model** (`models.py`)
   - SQLModel table that stores execution records
   - Captures timestamp, tool name, persona, arguments, status, result, and traceback

2. **Logging Infrastructure** (`runtime.py`)
   - `log_execution()`: Helper function that safely writes to ExecutionLog
   - Modified `execute_tool()`: Wraps execution in try-except to capture all failures
   - Uses independent commits to persist logs even when execution fails

3. **Debug Tool** (`get_last_error`)
   - Query tool that retrieves the most recent error from ExecutionLog
   - Optionally filter by tool name
   - Returns formatted error information with full Python traceback

## Database Schema

```sql
CREATE TABLE executionlog (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,           -- UTC timestamp
    tool_name VARCHAR NOT NULL,            -- Name of executed tool
    persona VARCHAR NOT NULL,              -- Persona context
    arguments JSON,                        -- Input arguments (JSON)
    status VARCHAR NOT NULL,               -- 'SUCCESS' or 'FAILURE'
    result_summary VARCHAR NOT NULL,       -- Output (truncated to ~2000 chars)
    error_traceback TEXT                   -- Full Python traceback (failures only)
);
```

## Usage

### For AI Self-Healing Workflow

```python
# 1. AI creates a tool with a bug
# (Tool gets registered in the database)

# 2. AI tests the tool
result = execute_tool("fibonacci", "default", {"n": 10}, session)
# -> Error: Execution failed (ZeroDivisionError)

# 3. AI queries for detailed error information
error_info = execute_tool("get_last_error", "default", {"tool_name": "fibonacci"}, session)
# Returns:
# Last error for tool 'fibonacci':
# Time: 2025-12-11 22:07:07.885424
# Persona: default
# Input: {'n': 10}
# 
# Traceback:
# Traceback (most recent call last):
#   File "runtime.py", line 361, in execute_tool
#     result = tool_instance.run(arguments)
#   File "<string>", line 7, in run
# ZeroDivisionError: division by zero

# 4. AI analyzes traceback and identifies the bug
# - Error type: ZeroDivisionError
# - Location: line 7 in run() method
# - Fix: Remove division by zero

# 5. AI patches the code in CodeVault

# 6. AI tests again - tool now works!
```

### get_last_error Tool API

**Tool Name:** `get_last_error`

**Arguments:**
- `tool_name` (optional string): Filter errors by specific tool name

**Returns:** Formatted string with:
- Tool name
- Timestamp
- Persona
- Input arguments
- Full Python traceback

**Examples:**

```python
# Get the most recent error from any tool
execute_tool("get_last_error", "default", {}, session)

# Get the most recent error from a specific tool
execute_tool("get_last_error", "default", {"tool_name": "fibonacci"}, session)
```

## Key Features

### Automatic Logging

All tool executions are automatically logged:
- **Success Path**: Logs status="SUCCESS" with result
- **Failure Path**: Logs status="FAILURE" with full traceback using `traceback.format_exc()`

### Independent Persistence

Logs use independent commits to ensure they persist even if:
- The main tool execution fails
- The transaction is rolled back
- The session crashes

### JSON Serialization

Arguments are safely serialized to JSON:
- Handles standard Python types
- Falls back to string representation if serialization fails
- Stores as JSON column for easy querying

### Result Truncation

Results are truncated to ~2000 characters to prevent database bloat while retaining enough information for debugging.

## Installation

### 1. Database Setup

The ExecutionLog table is automatically created when you run:

```bash
python seed_db.py
```

This will:
- Create the executionlog table
- Register the get_last_error debugging tool
- Set up sample tools and data

### 2. Standalone Tool Registration

If you need to add just the debug tool to an existing database:

```bash
python add_debug_tool.py
```

## Demo

Run the self-healing workflow demonstration:

```bash
python demo_self_healing.py
```

This demonstrates:
1. Creating a broken fibonacci tool
2. Executing it and seeing it fail
3. Using get_last_error to retrieve the traceback
4. Fixing the code
5. Verifying the fix works
6. Viewing the execution log history

## Testing

Run the test suite:

```bash
python test_execution_log.py
```

Tests cover:
- ExecutionLog model creation
- Successful execution logging
- Failed execution logging with traceback
- get_last_error tool functionality

## Security Considerations

### Safe Exception Handling

The logging system:
- Catches all exceptions
- Logs them safely
- Re-raises the original exception
- Doesn't mask or modify errors

### Transaction Isolation

Each log entry:
- Uses its own commit
- Won't interfere with main transaction
- Persists even on failure
- Has error handling for logging failures

### Privacy

Execution logs contain:
- Tool input arguments (may contain sensitive data)
- Full tracebacks (may reveal code structure)
- Results (may contain sensitive output)

**Recommendation:** Implement access controls on the ExecutionLog table in production environments.

## Performance

### Impact

Minimal performance impact:
- Single INSERT per tool execution
- Async-friendly (logs after execution completes)
- Truncates large results automatically
- No impact on successful fast paths

### Optimization

For high-volume production systems:
- Consider partitioning ExecutionLog by date
- Implement automatic log rotation/archiving
- Add indexes on (tool_name, timestamp) for faster queries
- Optionally disable logging for specific high-frequency tools

## Integration with MCP Server

The ExecutionLog system is fully integrated:
- Works with both Python and SQL tools
- Compatible with persona system
- Handles class-based and legacy tools
- No changes needed to existing tool code

## Troubleshooting

### Logs Not Appearing

1. Check that ExecutionLog table exists:
   ```bash
   sqlite3 chameleon_meta.db ".schema executionlog"
   ```

2. Verify database was seeded (server auto-seeds on first run)

3. Check for database write permissions

### get_last_error Returns "No errors found"

1. Verify a tool has actually failed
2. Check the tool_name filter matches exactly
3. Query ExecutionLog directly:
   ```sql
   SELECT * FROM executionlog WHERE status='FAILURE' ORDER BY timestamp DESC LIMIT 1;
   ```

## Future Enhancements

Potential improvements:
- [ ] Web UI for browsing execution logs
- [ ] Automatic retry mechanism using log data
- [ ] Performance metrics and analytics
- [ ] Log export/import functionality
- [ ] Integration with external monitoring systems
- [ ] Advanced filtering options (date ranges, status, etc.)
- [ ] Execution log cleanup/archival automation

## References

- **Problem Statement**: See original requirements document
- **Models**: `models.py` - ExecutionLog class
- **Runtime**: `runtime.py` - log_execution() and execute_tool()
- **Tests**: `test_execution_log.py`
- **Demo**: `demo_self_healing.py`
- **Tool Registration**: `add_debug_tool.py`
