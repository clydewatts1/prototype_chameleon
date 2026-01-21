# System Tools and Meta-Tools Reference

This document provides a comprehensive reference for all system tools and meta-tools available in the Chameleon MCP Server.

## Overview

System tools are built-in tools that provide core functionality for managing, debugging, and extending the Chameleon MCP Server. These tools enable autonomous AI agents to:
- **Create new tools dynamically** (meta-tools)
- **Inspect and debug** existing tools
- **Update documentation** automatically
- **Verify functionality** through automated testing
- **Manage database connections** and configurations

## Meta-Tools (Tool Creation)

Meta-tools enable the server to modify itself by creating new tools at runtime.

### 1. `create_new_sql_tool` - SQL Creator

**Purpose:** Create new SQL SELECT query tools dynamically

**Registration:** `python add_sql_creator_tool.py`

**Key Features:**
- SELECT-only enforcement for security
- Jinja2 template support for conditional SQL
- SQLAlchemy parameter binding for values
- Automatic hash computation and validation
- Tools marked with `is_auto_created=true`

**Documentation:** [SQL_CREATOR_TOOL_README.md](SQL_CREATOR_TOOL_README.md)

**Example Usage:**
```json
{
  "tool_name": "search_sales",
  "description": "Search sales by store and date range",
  "sql_query": "SELECT * FROM sales WHERE 1=1 {% if arguments.store %} AND store = :store {% endif %}",
  "parameters": {
    "store": {"type": "string", "required": false}
  }
}
```

---

### 2. `create_new_prompt` - Prompt Creator

**Purpose:** Create new prompt templates dynamically

**Registration:** `python add_dynamic_meta_tools.py`

**Key Features:**
- Jinja2 template support
- Argument schema validation
- Immediate availability after creation

**Documentation:** [DYNAMIC_META_TOOLS_README.md](DYNAMIC_META_TOOLS_README.md)

**Example Usage:**
```json
{
  "prompt_name": "summarize_data",
  "description": "Summarize data analysis results",
  "template": "Please summarize the following data: {{data}}",
  "arguments": {
    "data": {"type": "string", "required": true}
  }
}
```

---

### 3. `create_new_resource` - Resource Creator

**Purpose:** Create new static or dynamic resources

**Registration:** `python add_dynamic_meta_tools.py`

**Key Features:**
- Static resources (text content)
- Dynamic resources (executable code)
- MIME type configuration
- Persona-based filtering

**Documentation:** [DYNAMIC_META_TOOLS_README.md](DYNAMIC_META_TOOLS_README.md)

---

### 4. `create_temp_tool` - Temporary Tool Creator

**Purpose:** Create temporary in-memory tools for testing

**Registration:** `python add_temp_tool_creator.py`

**Key Features:**
- No database persistence (memory-only)
- Perfect for prototyping
- Automatic cleanup on server restart
- Supports Python and SQL tools

**Documentation:** [TEMP_TEST_TOOLS_README.md](TEMP_TEST_TOOLS_README.md)

---

### 5. `create_temp_resource` - Temporary Resource Creator

**Purpose:** Create temporary in-memory resources for testing

**Registration:** `python add_temp_resource_creator.py`

**Key Features:**
- No database persistence
- Static or dynamic resources
- Persona support
- Testing-focused

**Documentation:** [TEMP_RESOURCES_README.md](TEMP_RESOURCES_README.md)

---

### 6. `create_dashboard` - Chameleon UI Creator

**Purpose:** Create interactive Streamlit dashboards dynamically

**Registration:** `python add_ui_tool.py`

**Key Features:**
- LLMs can write Streamlit code
- Automatic file creation
- URL generation for dashboard access
- Saves to CodeVault with `code_type='streamlit'`

**Documentation:** [../CHAMELEON_UI_README.md](../CHAMELEON_UI_README.md)

---

### 7. `register_macro` - Macro Registry Tool

**Purpose:** Register reusable Jinja2 macros for SQL tools

**Registration:** `python add_macro_tool.py`

**Key Features:**
- Create reusable SQL snippets
- Available in all SQL tools via Jinja2
- Example: fiscal year calculations, safe division

**Documentation:** [MACRO_REGISTRY_README.md](MACRO_REGISTRY_README.md)

---

## Documentation & Quality Control Tools

These tools help maintain and verify the integrity of other tools.

### 8. `system_update_manual` - Librarian Tool

**Purpose:** Update tool documentation and manuals

**Registration:** `python add_librarian_tool.py`

**Key Features:**
- Update `extended_metadata` for any tool
- Merge or replace mode
- Automatic verification flag for new examples
- Enforces allowed metadata keys

**Allowed Metadata Keys:**
- `usage_guide` - How to use the tool
- `examples` - Usage examples with expected outputs
- `pitfalls` - Common mistakes to avoid
- `error_codes` - Error messages and meanings

**Example Usage:**
```json
{
  "tool_name": "utility_greet",
  "manual_content": {
    "usage_guide": "Greets a user by name",
    "examples": [
      {
        "input": {"name": "Alice"},
        "expected_output_summary": "Hello, Alice!"
      }
    ]
  },
  "mode": "merge"
}
```

---

### 9. `system_inspect_tool` - Inspect Tool

**Purpose:** Inspect metadata and documentation of other tools

**Registration:** `python add_inspect_tool.py`

**Key Features:**
- View tool schema and metadata
- Read documentation and examples
- Check verification status
- Inspect input parameters

**Example Usage:**
```json
{
  "tool_name": "utility_greet"
}
```

**Returns:**
```json
{
  "tool_name": "utility_greet",
  "description": "Greets a user",
  "target_persona": "default",
  "input_schema": {...},
  "manual": {
    "usage_guide": "...",
    "examples": [...]
  },
  "verified": true
}
```

---

### 10. `system_verify_tool` - Verifier Tool

**Purpose:** Run verification examples from tool manuals

**Registration:** `python add_verifier_tool.py`

**Key Features:**
- Executes examples from `extended_metadata`
- Reports PASS/FAIL status
- Updates `verified` flag on success
- Self-verification capable

**Documentation:** [QUALITY_CONTROL.md](QUALITY_CONTROL.md)

**Example Usage:**
```json
{
  "tool_name": "utility_greet"
}
```

**Output:**
```
Verifying tool: utility_greet
Example 1: PASS ✓
Example 2: PASS ✓
All 2 examples passed. Tool verified successfully.
```

---

## Debugging & Diagnostics Tools

Tools for troubleshooting and error analysis.

### 11. `get_last_error` - Debug Tool

**Purpose:** Retrieve detailed error information from execution logs

**Registration:** `python add_debug_tool.py`

**Key Features:**
- Full Python traceback with line numbers
- Query by tool name or persona
- Time-based filtering
- Enables AI self-healing

**Documentation:** [EXECUTION_LOG_README.md](EXECUTION_LOG_README.md)

**Example Usage:**
```json
{
  "tool_name": "broken_tool"
}
```

**Returns:**
```
Last error for 'broken_tool':
Timestamp: 2026-01-21 10:30:00
Status: FAILURE
Arguments: {"x": 0}
Traceback:
  File "runtime.py", line 361, in execute_tool
    result = tool_instance.run(arguments)
  File "<string>", line 7, in run
ZeroDivisionError: division by zero
```

---

## Database & Connection Tools

Tools for managing database connections and testing.

### 12. `reconnect_db` - Database Reconnection Tool

**Purpose:** Reconnect to data database after connection loss

**Registration:** `python add_reconnect_tool.py`

**Key Features:**
- Reconnect after timeout or network issues
- Validates connection before returning
- Graceful error handling

**Example Usage:**
```json
{} 
```
_(No parameters required)_

---

### 13. `test_db_connection` - Database Test Tool

**Purpose:** Test database connectivity and configuration

**Registration:** `python add_db_test_tool.py`

**Key Features:**
- Tests both metadata and data databases
- Returns connection status
- Helpful for diagnostics

**Example Usage:**
```json
{}
```
_(No parameters required)_

---

## Icon & Visual Tools

Tools for managing tool icons and visual elements.

### 14. `save_icon` - Icon Management Tool

**Purpose:** Save icons for tools (SVG or PNG)

**Registration:** `python add_icon_tools.py`

**Key Features:**
- Store base64-encoded icons
- SVG and PNG support
- Associate icons with tool names
- Update existing icons

**Example Usage:**
```json
{
  "name": "greet_tool",
  "content": "<svg>...</svg>",
  "format": "svg"
}
```

---

### 15. `get_icon` - Icon Retrieval Tool

**Purpose:** Retrieve stored icons by name

**Registration:** `python add_icon_tools.py`

**Example Usage:**
```json
{
  "name": "greet_tool"
}
```

---

## Workflow & Advanced Tools

Advanced tools for complex operations.

### 16. `execute_workflow` - Chain Tool

**Purpose:** Execute multi-step workflows with DAG validation

**Registration:** `python add_chain_tool.py`

**Key Features:**
- DAG validation (prevents circular dependencies)
- Variable substitution between steps (`${step_id.key}`)
- Partial execution reporting on failure
- Atomic workflow execution

**Documentation:** [../CHAIN_TOOL_IMPLEMENTATION.md](../CHAIN_TOOL_IMPLEMENTATION.md)

**Example Usage:**
```json
{
  "steps": [
    {
      "id": "fetch",
      "tool": "get_sales",
      "arguments": {"store": "Store A"}
    },
    {
      "id": "summarize",
      "tool": "calculate_total",
      "arguments": {"data": "${fetch.result}"}
    }
  ]
}
```

---

### 17. `general_merge_tool` - Data Upsert Tool

**Purpose:** Insert or update data with dialect-specific SQL

**Registration:** `python add_advanced_tools.py`

**Key Features:**
- Automatic INSERT or UPDATE based on key
- Supports SQLite, PostgreSQL, Teradata, Databricks
- Parameter binding for security
- JSON data input

**Documentation:** [ADVANCED_TOOLS_README.md](ADVANCED_TOOLS_README.md)

---

### 18. `execute_ddl_tool` - DDL Execution Tool

**Purpose:** Execute schema changes (CREATE, ALTER, DROP, TRUNCATE)

**Registration:** `python add_advanced_tools.py`

**Key Features:**
- Requires explicit "YES" confirmation
- DDL-only validation
- Single statement enforcement
- Comprehensive safety checks

**Documentation:** [ADVANCED_TOOLS_README.md](ADVANCED_TOOLS_README.md)

---

## Registration Scripts

All system tools are registered using bootstrap scripts in the `server/` directory:

| Script | Tools Registered |
|--------|------------------|
| `add_sql_creator_tool.py` | create_new_sql_tool |
| `add_dynamic_meta_tools.py` | create_new_prompt, create_new_resource |
| `add_temp_tool_creator.py` | create_temp_tool |
| `add_temp_resource_creator.py` | create_temp_resource |
| `add_ui_tool.py` | create_dashboard |
| `add_macro_tool.py` | register_macro |
| `add_librarian_tool.py` | system_update_manual |
| `add_inspect_tool.py` | system_inspect_tool |
| `add_verifier_tool.py` | system_verify_tool |
| `add_debug_tool.py` | get_last_error |
| `add_reconnect_tool.py` | reconnect_db |
| `add_db_test_tool.py` | test_db_connection |
| `add_icon_tools.py` | save_icon, get_icon |
| `add_chain_tool.py` | execute_workflow |
| `add_advanced_tools.py` | general_merge_tool, execute_ddl_tool |
| `add_resource_bridge.py` | Resource bridge functionality |

## Batch Registration

To register all system tools at once, you can create a batch script:

```bash
#!/bin/bash
# Register all system tools

cd server

python add_sql_creator_tool.py
python add_dynamic_meta_tools.py
python add_temp_tool_creator.py
python add_temp_resource_creator.py
python add_ui_tool.py
python add_macro_tool.py
python add_librarian_tool.py
python add_inspect_tool.py
python add_verifier_tool.py
python add_debug_tool.py
python add_reconnect_tool.py
python add_db_test_tool.py
python add_icon_tools.py
python add_chain_tool.py
python add_advanced_tools.py
python add_resource_bridge.py

echo "All system tools registered successfully!"
```

## Tool Categories Summary

- **Meta-Tools (7):** Create new tools, prompts, resources, dashboards, macros
- **Documentation (3):** Update manuals, inspect tools, verify functionality
- **Debugging (1):** Get error details and tracebacks
- **Database (2):** Reconnect, test connections
- **Icons (2):** Save and retrieve tool icons
- **Workflow (1):** Execute multi-step workflows
- **Advanced (2):** Upsert data, execute DDL

**Total: 18 system tools**

## See Also

- [README.md](README.md) - Main server documentation
- [SQL_CREATOR_TOOL_README.md](SQL_CREATOR_TOOL_README.md) - SQL creator details
- [EXECUTION_LOG_README.md](EXECUTION_LOG_README.md) - Execution logging and debugging
- [QUALITY_CONTROL.md](QUALITY_CONTROL.md) - Verification system
- [DYNAMIC_META_TOOLS_README.md](DYNAMIC_META_TOOLS_README.md) - Dynamic tool creation
