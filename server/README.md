# Prototype Chameleon MCP Server

A dynamic Model Context Protocol (MCP) server that allows execution of tools, resources, and prompts stored in a database with persona-based filtering. This is version 2 of the Chameleon MCP server.

## Overview

Chameleon is an innovative MCP server implementation that stores executable code in a database and dynamically serves tools, resources, and prompts based on personas. It provides:

- **Class-Based Plugin Architecture**: Tools inherit from `ChameleonTool` base class for safety and standardization
- **Dynamic Tool Registry**: Tools are stored in a database and can be added/modified without server code changes
- **Self-Modifying Capabilities**: LLMs can create new SQL tools dynamically via meta-tool
- **YAML Configuration**: Define tools, resources, and prompts in human-readable YAML format
- **Jinja2 + SQLAlchemy SQL**: Secure dynamic SQL with Jinja2 for structure and parameter binding for values
- **Deep Execution Audit**: Comprehensive execution logging with full traceback capture for self-healing
- **Resource Management**: Support for both static and dynamic resources with code execution
- **Prompt Templates**: Store and format prompt templates with argument substitution
- **Persona-Based Filtering**: Different tools can be exposed to different personas
- **Code Integrity**: SHA-256 hashing ensures code hasn't been tampered with
- **Enhanced Security**: AST-based code validation prevents arbitrary top-level code execution

## Architecture

The project consists of the following main components:

1. **base.py**: Abstract base class for plugins
   - `ChameleonTool`: Abstract base class that all Python tools must inherit from
   - Provides `run(arguments)` abstract method
   - Provides `log(msg)` helper for standardized output
   - Enforces strict inheritance model for safety

2. **models.py**: Database schema using SQLModel
   - `CodeVault`: Stores executable code with SHA-256 hash as primary key
   - `ToolRegistry`: Maps tools to personas with JSON schema definitions
   - `ResourceRegistry`: Defines resources with static or dynamic content
   - `PromptRegistry`: Stores prompt templates with argument schemas

3. **runtime.py**: Secure code execution engine
   - AST-based code validation (only allows imports and class definitions at top level)
   - Validates code integrity via hash checking
   - Finds and instantiates classes inheriting from `ChameleonTool`
   - Provides tool, resource, and prompt listing and execution functions
   - Supports both Python (class-based) and SQL execution

4. **server.py**: MCP server implementation
   - Implements MCP protocol using low-level Server class
   - Handles tool, resource, and prompt listing and execution requests
   - Manages database lifecycle

5. **load_specs.py**: YAML-based configuration loader
   - Loads tool, resource, and prompt definitions from YAML files
   - Idempotent upsert operations (safe to run multiple times)
   - Computes hashes and syncs to database
   - Supports `--clean` flag for resetting database

6. **export_specs.py**: Database export utility
   - Exports the current state of the database to YAML format
   - Serializes tools, resources, and prompts with their associated code
   - Uses block-style YAML for readable multiline code blocks
   - Supports `--persona` flag for filtering by persona
   - Enables "snapshotting" the AI agent's learned capabilities

7. **seed_db.py**: Legacy Python-based seeding utility (deprecated)
   - Populates database with hardcoded sample tools, resources, and prompts
   - Retained for backward compatibility

## Installation

### Prerequisites

- Python 3.12 or higher
- pip (Python package installer)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd prototype_chameleon
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Configuration (Optional)

The server uses a YAML-based configuration system. You can configure the server by creating a config file at `~/.chameleon/config/config.yaml`.

**Create Configuration:**

```bash
# Create the config directory
mkdir -p ~/.chameleon/config

# Copy the sample config file
cp config.yaml.sample ~/.chameleon/config/config.yaml

# Edit the config file with your preferred settings
nano ~/.chameleon/config/config.yaml
```

**Configuration Structure:**

```yaml
server:
  transport: "stdio"  # or "sse" for HTTP Server-Sent Events
  host: "0.0.0.0"     # Host for SSE transport
  port: 8000          # Port for SSE transport
  log_level: "INFO"   # DEBUG, INFO, WARNING, ERROR, or CRITICAL
  logs_dir: "logs"    # Directory for log files (relative or absolute path)

database:
  url: "sqlite:///chameleon.db"  # Database connection URL
```

**Default Behavior:**

If no config file exists, the server uses these defaults:
- Transport: stdio
- Host: 0.0.0.0
- Port: 8000
- Log Level: INFO
- Logs Directory: logs
- Database: sqlite:///chameleon.db

**Command-Line Overrides:**

You can override any config value using command-line arguments:

```bash
# Override transport and port
python server.py --transport sse --port 9000

# Override database URL
python server.py --database-url postgresql://user:pass@localhost/mydb

# Override log level
python server.py --log-level DEBUG

# Override logs directory
python server.py --logs-dir /var/log/chameleon

# See all options
python server.py --help
```

**Priority:** Command-line arguments > YAML config > Defaults

### 2. Run the MCP Server

Start the server using stdio transport:

```bash
python server.py
```

Or with SSE transport:

```bash
python server.py --transport sse --port 8000
```

The server will:
- Load configuration from `~/.chameleon/config/config.yaml` (if it exists)
- Initialize the database connection
- Create tables if they don't exist
- **Automatically seed the database with sample data if empty** (new in this version!)
- Start listening for MCP requests on the configured transport

**Auto-Seeding**: On first run, the server automatically populates the database with sample tools, resources, and prompts. This means you can start using the server immediately without manually running `seed_db.py`.

**Sample Data Included:**

**Tools:**
- `greet` - Greets a person by name (persona: default)
- `add` - Adds two numbers (persona: default)
- `multiply` - Multiplies two numbers (persona: assistant)
- `uppercase` - Converts text to uppercase (persona: default)
- `get_sales_summary` - Get sales summary using SQL SELECT (persona: default)

**Resources:**
- `welcome_message` - Static welcome message (memo://welcome)
- `server_time` - Dynamic resource that returns current server time (system://time)
- `sales_report` - Recent sales report (data://sales/recent)

**Prompts:**
- `review_code` - Template for generating code review requests

### 3. Seed the Database

Chameleon provides two ways to populate your database with tools, resources, and prompts:

#### Option A: YAML-Based Seeding (Recommended)

The flexible YAML-based system allows you to define your specifications in a human-readable format:

```bash
# Load specifications from YAML (idempotent - safe to run multiple times)
python load_specs.py specs.yaml

# With custom database
python load_specs.py specs.yaml --database sqlite:///mydb.db

# Clear existing data before loading
python load_specs.py specs.yaml --clean
```

The YAML file format (`specs.yaml`):

```yaml
tools:
  - name: greet
    persona: default
    description: Greets a person by name
    code_type: python
    code: |
      from base import ChameleonTool
      
      class GreetingTool(ChameleonTool):
          def run(self, arguments):
              name = arguments.get('name', 'Guest')
              return f'Hello {name}!'
    input_schema:
      type: object
      properties:
        name:
          type: string
      required: [name]

resources:
  - uri: memo://welcome
    name: welcome_message
    persona: default
    is_dynamic: false
    static_content: "Welcome message here"

prompts:
  - name: review_code
    description: Code review prompt
    template: "Review this code: {code}"
    arguments_schema:
      arguments:
        - name: code
          required: true
```

**Benefits:**
- **Idempotent**: Safe to run multiple times - updates existing entries
- **Version Control**: Store specifications in Git
- **Flexible**: Easy to add, modify, or remove tools
- **Type Support**: Both Python (class-based) and SQL tools

#### Option B: Python Script Seeding

For backward compatibility, you can use the original Python script:

```bash
python seed_db.py
```

This will clear existing data and repopulate the database with hardcoded sample tools, resources, and prompts.

### 4. Export Database Specifications

You can export the current state of your database to a YAML file, enabling you to:
- Create snapshots of your AI agent's learned capabilities
- Back up your tool configurations
- Share tool definitions with others
- Migrate tools between environments

```bash
# Export all tools, resources, and prompts to stdout
python export_specs.py

# Save export to a file
python export_specs.py > my_agent_snapshot.yaml

# Export only tools for a specific persona
python export_specs.py --persona assistant > assistant_tools.yaml

# Export from a custom database
python export_specs.py --database sqlite:///mydb.db > export.yaml

# View help
python export_specs.py --help
```

The exported YAML file uses the same format as `specs.yaml`, so you can load it back using `load_specs.py`:

```bash
# Load an exported snapshot into a new database
python load_specs.py my_agent_snapshot.yaml --database sqlite:///restored.db
```

**Key Features:**
- Uses block-style (|) for multiline code blocks for readability
- Maintains JSON structure for input schemas
- Handles missing code hashes gracefully
- Outputs to stdout for easy redirection

### 5. Run the Admin GUI (Optional)

Manage your tools and database using the Streamlit admin interface:

```bash
streamlit run admin_gui.py
```

The admin GUI provides:
- **Dashboard**: View metrics (total tools, code blobs, unique personas)
- **Tool Registry**: Browse, filter by persona, and delete tools
- **Add New Tool**: Create or update tools with a user-friendly form

**Database Connection:**

The admin GUI uses the same configuration system as the server:

1. **CHAMELEON_DB_URL environment variable** (highest priority)
2. **~/.chameleon/config/config.yaml** config file
3. **Default:** `sqlite:///chameleon.db`

Examples:

```bash
# Use environment variable
export CHAMELEON_DB_URL="postgresql://user:pass@host/db"
streamlit run admin_gui.py

# Or use the config file (create ~/.chameleon/config/config.yaml)
streamlit run admin_gui.py
```

### 6. Interact with the Server

The server implements the MCP protocol and supports:

- **List Tools**: Returns available tools based on the current persona
- **Call Tool**: Executes a tool with provided arguments
- **List Resources**: Returns available resources
- **Read Resource**: Retrieves resource content (static or dynamic)
- **List Prompts**: Returns available prompt templates
- **Get Prompt**: Retrieves and formats a prompt with arguments

Example tool schemas are defined in the database with JSON Schema for validation.

## Creating Custom Tools

Chameleon supports two types of tools: **Python class-based tools** and **SQL-based tools**.

### Python Class-Based Tools

All Python tools must inherit from the `ChameleonTool` base class:

```python
from base import ChameleonTool

class MyCustomTool(ChameleonTool):
    def run(self, arguments):
        # Access arguments
        name = arguments.get('name', 'default')
        
        # Access database session
        # result = self.db_session.exec(statement).all()
        
        # Access context (persona, tool_name, etc.)
        persona = self.context.get('persona')
        
        # Use logging
        self.log(f"Processing request for {name}")
        
        # Return result
        return f"Processed: {name}"
```

**Security Features:**
- Only top-level imports and class definitions are allowed
- No arbitrary code execution at module level
- AST-based validation ensures safety

### SQL-Based Tools

SQL tools use Jinja2 templates for structure and SQLAlchemy parameter binding for values. This hybrid approach provides:
- **Jinja2 for SQL structure**: Control conditional WHERE clauses, JOINs, and other SQL logic
- **SQLAlchemy parameter binding**: Safely inject values using `:param_name` syntax

#### Basic SQL SELECT Tool

Simple SELECT queries without conditionals:

```sql
SELECT 
    store_name,
    department,
    SUM(sales_amount) as total_sales
FROM sales_per_day
GROUP BY store_name, department
ORDER BY total_sales DESC
```

#### SQL with Jinja2 Conditionals

Use Jinja2 to make parts of the query optional based on provided arguments:

```sql
SELECT 
    column1,
    column2,
    SUM(amount) as total
FROM my_table
WHERE 1=1
{% if arguments.filter_value %}
  AND column1 = :filter_value
{% endif %}
{% if arguments.min_amount %}
  AND amount >= :min_amount
{% endif %}
GROUP BY column1, column2
ORDER BY total DESC
```

**How It Works:**
1. **Structure Rendering (Jinja2)**: The template is rendered first with `arguments` dict available
   - `{% if arguments.field %}` checks if a field is present in the arguments
   - Jinja2 controls which parts of the SQL are included
   - **Never use Jinja2 for values** - only for structure!

2. **Value Binding (SQLAlchemy)**: After rendering, values are bound safely
   - Use `:param_name` syntax for all values (e.g., `:store_name`, `:min_amount`)
   - Arguments are passed to SQLAlchemy's `params` parameter
   - SQLAlchemy handles escaping and prevents SQL injection

#### Complete Example with Multiple Conditionals

```sql
SELECT 
    department,
    SUM(sales_amount) as total_sales,
    AVG(sales_amount) as avg_sales,
    COUNT(*) as transaction_count
FROM sales_per_day
WHERE 1=1
{% if arguments.start_date %}
  AND business_date >= :start_date
{% endif %}
{% if arguments.end_date %}
  AND business_date <= :end_date
{% endif %}
{% if arguments.department %}
  AND department = :department
{% endif %}
{% if arguments.min_amount %}
  AND sales_amount >= :min_amount
{% endif %}
GROUP BY department
ORDER BY total_sales DESC
```

With input_schema:
```yaml
input_schema:
  type: object
  properties:
    start_date:
      type: string
      description: Start date in YYYY-MM-DD format (optional)
    end_date:
      type: string
      description: End date in YYYY-MM-DD format (optional)
    department:
      type: string
      description: Filter by department name (optional)
    min_amount:
      type: number
      description: Minimum sales amount filter (optional)
  required: []
```

**IMPORTANT - Security Rules:**
- ✅ **CORRECT**: Use Jinja2 for structure: `{% if arguments.category %} AND category = :category {% endif %}`
- ❌ **WRONG**: Using Jinja2 for values: `WHERE category = '{{ arguments.category }}'` (SQL injection risk!)
- ✅ **CORRECT**: Use SQLAlchemy binding: `:category` in SQL, pass via `params` dict
- ❌ **WRONG**: String interpolation: `f"WHERE category = '{category}'"` (SQL injection risk!)

**Security Features:**
- Only SELECT statements allowed (read-only)
- Single statement validation (prevents SQL injection via statement chaining)
- Parameter binding for all values (prevents SQL injection via value injection)
- Comment-aware validation (strips SQL comments before security checks)
- Jinja2 used only for structural logic, never for values

### Adding Tools via YAML

Edit `specs.yaml` and run the loader. Tools support multiple options:

#### Tool Options

**Required Fields:**
- `name`: Unique tool name (string)
- `persona`: Target persona (usually "default")
- `description`: What the tool does (string)
- `code`: The executable code (Python class or SQL query)
- `input_schema`: JSON Schema defining the tool's input parameters

**Optional Fields:**
- `code_type`: Type of code - "python" (default) or "select" (SQL)
- `is_auto_created`: Automatically set by the system
  - `false` (default): System/prebuilt tool loaded from YAML
  - `true`: Tool created dynamically by LLM via `create_new_sql_tool`

#### Python Tool Example

```yaml
tools:
  - name: my_tool
    persona: default
    description: My custom Python tool
    code_type: python  # Optional, defaults to 'python'
    code: |
      from base import ChameleonTool
      
      class MyTool(ChameleonTool):
          def run(self, arguments):
              name = arguments.get('name', 'World')
              self.log(f"Processing {name}")
              return f"Hello {name}"
    input_schema:
      type: object
      properties:
        name:
          type: string
          description: Name to greet
      required: [name]
```

#### SQL Tool Example (Basic)

```yaml
tools:
  - name: get_all_stores
    persona: default
    description: Get all store locations
    code_type: select  # Must be 'select' for SQL tools
    code: |
      SELECT 
          store_name,
          location,
          store_type
      FROM stores
      ORDER BY store_name
    input_schema:
      type: object
      properties: {}
      required: []
```

#### SQL Tool with Jinja2 Conditionals

```yaml
tools:
  - name: search_sales
    persona: default
    description: Search sales records with optional filters
    code_type: select
    code: |
      SELECT 
          business_date,
          store_name,
          department,
          sales_amount
      FROM sales_per_day
      WHERE 1=1
      {% if arguments.store_name %}
        AND store_name = :store_name
      {% endif %}
      {% if arguments.department %}
        AND department = :department
      {% endif %}
      {% if arguments.min_amount %}
        AND sales_amount >= :min_amount
      {% endif %}
      ORDER BY business_date DESC
    input_schema:
      type: object
      properties:
        store_name:
          type: string
          description: Optional filter by store name
        department:
          type: string
          description: Optional filter by department
        min_amount:
          type: number
          description: Optional minimum sales amount
      required: []  # All parameters optional
```

Then load it:

```bash
python load_specs.py specs.yaml
```

## Dynamic Tool Creation and Self-Modification

Chameleon MCP Server includes a powerful meta-tool that allows AI agents to create new SQL-based tools dynamically at runtime. This enables "self-modifying" behavior where the LLM can extend its own capabilities.

### The SQL Creator Meta-Tool

**Tool Name:** `create_new_sql_tool`

**Purpose:** Allows an LLM to dynamically create new SQL SELECT query tools without manual code deployment.

**Key Features:**
- Creates tools that are immediately available for use
- Enforces strict security (SELECT-only, single statement)
- Supports parameterized queries with Jinja2 conditionals
- Tools are marked with `is_auto_created=true` flag for tracking

### Registering the Meta-Tool

```bash
python add_sql_creator_tool.py
```

This registers the `create_new_sql_tool` meta-tool in your database.

### Usage Examples

#### Creating a Simple SQL Tool

```json
{
  "tool_name": "get_all_departments",
  "description": "Get all unique departments from sales data",
  "sql_query": "SELECT DISTINCT department FROM sales_per_day ORDER BY department",
  "parameters": {}
}
```

#### Creating a Parameterized Tool

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

#### Creating a Tool with Jinja2 Conditionals

```json
{
  "tool_name": "search_inventory",
  "description": "Search inventory with optional filters",
  "sql_query": "SELECT * FROM inventory WHERE 1=1 {% if arguments.category %} AND category = :category {% endif %} {% if arguments.min_stock %} AND stock_level >= :min_stock {% endif %} ORDER BY item_name",
  "parameters": {
    "category": {
      "type": "string",
      "description": "Optional category filter",
      "required": false
    },
    "min_stock": {
      "type": "number",
      "description": "Optional minimum stock level",
      "required": false
    }
  }
}
```

#### Complete Workflow Example

```python
from sqlmodel import Session
from models import get_engine
from runtime import execute_tool

engine = get_engine("sqlite:///chameleon.db")

with Session(engine) as session:
    # Step 1: Create a new tool
    result = execute_tool(
        "create_new_sql_tool",
        "default",
        {
            "tool_name": "get_high_value_sales",
            "description": "Get sales records above a threshold",
            "sql_query": "SELECT * FROM sales_per_day WHERE sales_amount >= :threshold ORDER BY sales_amount DESC",
            "parameters": {
                "threshold": {
                    "type": "number",
                    "description": "Minimum sales amount",
                    "required": true
                }
            }
        },
        session
    )
    print(result)  # Success: Tool 'get_high_value_sales' has been registered...
    
    # Step 2: Use the newly created tool immediately
    sales = execute_tool(
        "get_high_value_sales",
        "default",
        {"threshold": 1000.0},
        session
    )
    print(f"Found {len(sales)} high-value sales")
```

### Security Constraints

The meta-tool enforces strict security:

1. **SELECT-Only**: Only read-only SELECT queries allowed
2. **Single Statement**: Prevents SQL injection via statement chaining (semicolon detection)
3. **Comment-Aware**: Strips SQL comments before validation to prevent bypasses
4. **Forced Code Type**: All created tools use `code_type='select'` for runtime validation
5. **Parameter Binding**: Values must use `:param_name` syntax (SQLAlchemy binding)

**Blocked Examples:**
- `INSERT INTO users ...` - Write operations not allowed
- `SELECT * FROM users; DROP TABLE users;` - Multiple statements blocked
- `UPDATE products SET ...` - Only SELECT allowed

### Tool Tracking: is_auto_created Flag

All tools have an `is_auto_created` flag to distinguish their origin:

- **`is_auto_created=false`**: System/prebuilt tools loaded from YAML files
- **`is_auto_created=true`**: Tools created dynamically by LLM via `create_new_sql_tool`

This allows you to:
- Track which tools were created by the AI vs. humans
- Implement different policies for auto-created tools
- Audit and review LLM-generated tools
- Clean up or archive AI-created tools separately

### Best Practices

1. **Descriptive Names**: Use clear tool names (e.g., `get_sales_by_region` not `query1`)
2. **Good Descriptions**: Detailed descriptions help the LLM know when to use the tool
3. **Parameter Documentation**: Document each parameter with type and description
4. **Use Parameters**: Always use `:param_name` syntax for values, never string interpolation
5. **Test Queries**: Test SQL queries manually before creating tools
6. **Idempotency**: Safe to create the same tool multiple times (updates existing)

### Limitations

1. **SELECT-Only**: Only read operations (write operations require manual Python tool creation)
2. **Default Persona**: All SQL creator tools use the "default" persona
3. **No Python Logic**: Created tools execute SQL only, not custom Python code
4. **Query Complexity**: No built-in limits on joins, aggregations, or result size

### Documentation

For complete documentation, see:
- [SQL_CREATOR_TOOL_README.md](SQL_CREATOR_TOOL_README.md) - Detailed usage guide
- [IMPLEMENTATION_SUMMARY_SQL_CREATOR.md](IMPLEMENTATION_SUMMARY_SQL_CREATOR.md) - Technical implementation details

## Deep Execution Audit and Self-Healing

Chameleon includes a comprehensive execution logging system that enables AI agents to self-diagnose and self-heal when tools fail. This is the **"Black Box" Recorder pattern** - the single most important feature for autonomous agent operation.

### The Problem

When an LLM creates a tool with a bug, it typically receives only a generic error message like "Error: Execution failed". This provides no information about:
- What went wrong
- Where in the code the error occurred
- What inputs caused the failure
- The exact error type and message

Without this information, the AI cannot fix the problem.

### The Solution: ExecutionLog

The ExecutionLog system automatically records every tool execution with:

1. **Timestamp**: When the execution occurred (UTC, timezone-aware)
2. **Tool Name**: Which tool was executed
3. **Persona**: The persona context
4. **Arguments**: Full input arguments (JSON)
5. **Status**: "SUCCESS" or "FAILURE"
6. **Result Summary**: Output (truncated to ~2000 chars for success)
7. **Error Traceback**: **Full Python traceback** with line numbers (for failures)

### Database Schema

```sql
CREATE TABLE executionlog (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    tool_name VARCHAR NOT NULL,
    persona VARCHAR NOT NULL,
    arguments JSON,
    status VARCHAR NOT NULL,
    result_summary VARCHAR NOT NULL,
    error_traceback TEXT
);
```

### The get_last_error Debug Tool

A special tool is provided to query error details:

**Tool Name:** `get_last_error`

**Arguments:**
- `tool_name` (optional string): Filter errors by specific tool name

**Returns:** Formatted string containing:
- Tool name
- Timestamp
- Persona
- Input arguments
- **Full Python traceback with exact line numbers**

### Self-Healing Workflow

```
1. AI creates a new tool (e.g., fibonacci calculator)
   ↓
2. AI tests the tool → Generic error received
   ↓
3. AI calls get_last_error(tool_name='fibonacci')
   ↓
4. AI receives detailed traceback:
   "Traceback (most recent call last):
     File "runtime.py", line 361, in execute_tool
       result = tool_instance.run(arguments)
     File "<string>", line 7, in run
   ZeroDivisionError: division by zero"
   ↓
5. AI analyzes the traceback:
   - Error type: ZeroDivisionError
   - Location: Line 7 in run() method
   - Cause: Division by zero in the code
   ↓
6. AI patches the code in CodeVault
   ↓
7. AI tests again → Tool works!
   ↓
8. Execution log shows complete audit trail
```

### Usage Examples

#### Get Most Recent Error (Any Tool)

```python
from sqlmodel import Session
from models import get_engine
from runtime import execute_tool

engine = get_engine("sqlite:///chameleon.db")

with Session(engine) as session:
    error_info = execute_tool(
        "get_last_error",
        "default",
        {},
        session
    )
    print(error_info)
```

#### Get Most Recent Error for Specific Tool

```python
with Session(engine) as session:
    error_info = execute_tool(
        "get_last_error",
        "default",
        {"tool_name": "my_broken_tool"},
        session
    )
    print(error_info)
```

#### Complete Self-Healing Example

```python
with Session(engine) as session:
    # Try to run a tool
    try:
        result = execute_tool("calculate", "default", {"x": 10}, session)
    except Exception as e:
        print(f"Tool failed: {e}")
        
        # Get detailed error information
        error_info = execute_tool(
            "get_last_error",
            "default",
            {"tool_name": "calculate"},
            session
        )
        
        # error_info contains full traceback with line numbers
        # AI can now analyze and fix the bug
        print(error_info)
```

### Key Features

#### Automatic Logging
- Every tool execution is automatically logged
- Zero changes required to existing tools
- Works with both Python and SQL tools
- Compatible with persona system

#### Robust Error Capture
- Full Python tracebacks using `traceback.format_exc()`
- Exact line numbers and error types preserved
- Original exceptions re-raised (no masking)
- Logs persist even if main transaction fails

#### Independent Persistence
- Logs use independent commits
- Persist even if main execution transaction fails
- Never crashes the main execution
- Critical for capturing failure information

#### Security and Privacy
- ✅ CodeQL security scan: 0 vulnerabilities
- Independent transaction commits
- Safe JSON serialization with error handling
- Timezone-aware datetime handling

**Note:** Execution logs may contain:
- Sensitive input arguments
- Internal code structure (from tracebacks)
- Sensitive output data

Implement appropriate access controls in production environments.

### Performance Impact

Minimal overhead:
- Single INSERT per tool execution
- Async-friendly (logs after execution completes)
- Automatic result truncation (~2000 chars)
- No impact on successful fast paths

### Registering the Debug Tool

The debug tool is automatically included when seeding the database:

```bash
python seed_db.py
```

Or register it separately:

```bash
python add_debug_tool.py
```

### Demo

Run the interactive self-healing demonstration:

```bash
python demo_self_healing.py
```

This demonstrates:
1. Creating a broken fibonacci tool
2. Executing it and seeing it fail
3. Using get_last_error to retrieve the traceback
4. Analyzing the error
5. Fixing the code
6. Verifying the fix works
7. Viewing the execution log history

### Documentation

For complete documentation, see:
- [EXECUTION_LOG_README.md](EXECUTION_LOG_README.md) - Detailed usage guide
- [IMPLEMENTATION_SUMMARY_EXECUTION_LOG.md](IMPLEMENTATION_SUMMARY_EXECUTION_LOG.md) - Technical implementation details

## Connecting AI Clients

Once your Chameleon MCP server is running, you can connect it to various AI clients that support the Model Context Protocol (MCP). Below are configuration instructions for popular AI CLI tools.

### Claude Desktop

Claude Desktop supports MCP servers through its configuration file.

1. **Locate the Claude Desktop configuration file:**
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Add the Chameleon server configuration:**

```json
{
  "mcpServers": {
    "chameleon": {
      "command": "python",
      "args": ["/absolute/path/to/prototype_chameleon/server.py"],
      "env": {
        "CHAMELEON_DB_URL": "sqlite:///chameleon.db"
      }
    }
  }
}
```

3. **Restart Claude Desktop** to load the new configuration.

4. **Verify connection**: The Chameleon tools should now appear in Claude Desktop's tool menu.

### VS Code with Cline Extension

The Cline extension for VS Code supports MCP servers.

1. **Install the Cline extension** from the VS Code marketplace.

2. **Open VS Code settings** (File → Preferences → Settings or `Cmd/Ctrl + ,`).

3. **Search for "MCP"** and add the Chameleon server to the MCP servers configuration:

```json
{
  "cline.mcpServers": {
    "chameleon": {
      "command": "python",
      "args": ["/absolute/path/to/prototype_chameleon/server.py"],
      "env": {
        "CHAMELEON_DB_URL": "sqlite:///chameleon.db"
      }
    }
  }
}
```

4. **Reload VS Code** to activate the configuration.

### Google Gemini CLI (Experimental)

**Note**: As of December 2025, Google's Gemini CLI does not have official MCP support. However, if/when support is added, the configuration pattern would likely be similar:

1. **Check Gemini CLI documentation** for MCP configuration instructions.

2. **Expected configuration pattern** (hypothetical):

```bash
# In your shell configuration (~/.bashrc, ~/.zshrc, etc.)
export GEMINI_MCP_SERVERS='{"chameleon": {"command": "python", "args": ["/absolute/path/to/prototype_chameleon/server.py"]}}'
```

Or via a configuration file (location TBD by Google):

```json
{
  "mcpServers": {
    "chameleon": {
      "command": "python",
      "args": ["/absolute/path/to/prototype_chameleon/server.py"]
    }
  }
}
```

3. **Monitor Google AI documentation** at [https://ai.google.dev/](https://ai.google.dev/) for official MCP support announcements.

### Generic MCP Client Configuration

For any MCP-compatible client, you'll need:

- **Command**: Path to your Python interpreter (e.g., `python`, `python3`, or `/path/to/venv/bin/python`)
- **Args**: `["/absolute/path/to/prototype_chameleon/server.py"]`
- **Environment Variables** (optional):
  - `CHAMELEON_DB_URL`: Database connection string (default: `sqlite:///chameleon.db`)

### Testing the Connection

After configuring your AI client:

1. **Start the client** (restart if already running)
2. **Look for available tools** in the client's interface
3. **Test a simple tool** like `greet` with the argument `{"name": "World"}`
4. **Expected result**: `"Hello World! I am running from the database."`

If tools don't appear, check:
- Server path is correct and absolute
- Python environment has required dependencies installed
- Server has write permissions to create the database file (auto-seeded on first run)
- Client logs for connection errors

### Using Virtual Environments

If you're using a virtual environment for Chameleon, specify the full path to the Python interpreter:

```json
{
  "mcpServers": {
    "chameleon": {
      "command": "/path/to/prototype_chameleon/venv/bin/python",
      "args": ["/path/to/prototype_chameleon/server.py"]
    }
  }
}
```

### Resource Bridge Tool for Clients Without Resource Support

Some MCP clients (like Gemini CLI) may only support Tools and not Resources. For these clients, Chameleon provides a `read_resource` tool that acts as a bridge to access resources.

#### What is the Resource Bridge?

The Resource Bridge is a tool that allows clients without native Resource support to fetch resource data by calling a tool instead. It provides the same functionality as the native `read_resource` MCP request, but accessible as a regular tool.

#### Registering the Resource Bridge Tool

The resource bridge tool can be registered by running:

```bash
python add_resource_bridge.py
```

Alternatively, it's automatically included when seeding the database:

```bash
python seed_db.py
```

#### Usage

Once registered, clients can call the `read_resource` tool with a URI:

```json
{
  "uri": "memo://welcome"
}
```

Expected result: `"Welcome to Chameleon!"`

#### Self-Discovery Feature

If a resource URI is not found, the tool automatically lists all available resources to help with self-correction:

```json
{
  "uri": "memo://invalid"
}
```

Expected result:
```
Resource not found: memo://invalid

Available resources are:
  - memo://welcome
  - system://time
  - data://sales/recent
```

This self-discovery feature enables LLMs to quickly identify and correct URI mistakes.

#### Supported Resource Types

The `read_resource` tool supports both:
- **Static resources**: Fixed text content stored in the database
- **Dynamic resources**: Content generated by executing Python code or SQL queries

## Adding Custom Tools

To add your own tools to the database:

1. Write your tool code as a Python snippet that:
   - Reads from `arguments` dict
   - Optionally uses `db_session` for database access
   - Sets a `result` variable to return a value

2. Compute the SHA-256 hash of your code

3. Insert into `CodeVault` table with the hash and code

4. Register in `ToolRegistry` with:
   - Tool name
   - Target persona
   - Description
   - JSON Schema for input validation
   - Reference to the code hash

Example:
```python
from models import CodeVault, ToolRegistry, get_engine, create_db_and_tables
from sqlmodel import Session
import hashlib

# Your tool code
code = """
result = arguments.get('value', 0) * 2
"""

# Compute hash
code_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()

# Insert into database
engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    # Add code
    vault = CodeVault(hash=code_hash, python_blob=code)
    session.add(vault)
    
    # Register tool
    tool = ToolRegistry(
        tool_name="double",
        target_persona="default",
        description="Doubles a number",
        input_schema={
            "type": "object",
            "properties": {
                "value": {"type": "number", "description": "Value to double"}
            },
            "required": ["value"]
        },
        active_hash_ref=code_hash
    )
    session.add(tool)
    session.commit()
```

## Adding Custom Resources

Resources can be either static or dynamic:

### Static Resource
```python
from models import ResourceRegistry, get_engine
from sqlmodel import Session

engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    resource = ResourceRegistry(
        name="my_static_resource",
        uri_schema="myapp://static/info",
        description="Static information resource",
        is_dynamic=False,
        static_content="This is static content that never changes."
    )
    session.add(resource)
    session.commit()
```

### Dynamic Resource
Dynamic resources execute code from CodeVault to generate content:

```python
from models import CodeVault, ResourceRegistry, get_engine
from sqlmodel import Session
import hashlib

# Code that generates dynamic content
code = """
from datetime import datetime
result = f"Generated at: {datetime.now()}"
"""

code_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()

engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    # Add code to vault
    vault = CodeVault(hash=code_hash, python_blob=code)
    session.add(vault)
    
    # Register dynamic resource
    resource = ResourceRegistry(
        name="my_dynamic_resource",
        uri_schema="myapp://dynamic/timestamp",
        description="Returns current timestamp",
        is_dynamic=True,
        active_hash_ref=code_hash
    )
    session.add(resource)
    session.commit()
```

## Adding Custom Prompts

Prompts are templates that can be formatted with arguments:

```python
from models import PromptRegistry, get_engine
from sqlmodel import Session

engine = get_engine("sqlite:///chameleon.db")
with Session(engine) as session:
    prompt = PromptRegistry(
        name="bug_report",
        description="Template for filing bug reports",
        template="Bug Report:\n\nTitle: {title}\n\nDescription: {description}\n\nSteps to reproduce:\n{steps}",
        arguments_schema={
            "arguments": [
                {
                    "name": "title",
                    "description": "Short title for the bug",
                    "required": True
                },
                {
                    "name": "description",
                    "description": "Detailed description of the bug",
                    "required": True
                },
                {
                    "name": "steps",
                    "description": "Steps to reproduce the bug",
                    "required": False
                }
            ]
        }
    )
    session.add(prompt)
    session.commit()
```

## Security Considerations

⚠️ **CRITICAL SECURITY WARNING**:

- The server uses `exec()` to run code from the database with full Python privileges
- **Malicious code could execute arbitrary system commands, access/modify files, make network requests, or compromise the host system**
- Code integrity is verified via SHA-256 hashing (detects tampering, not malicious intent)
- **This design assumes ALL code in CodeVault is from trusted sources**
- **DO NOT use in production with untrusted code without additional security measures**
- For production use with untrusted code, you MUST implement:
  - Additional sandboxing (e.g., RestrictedPython, Docker containers, VMs)
  - Restricted database interfaces with limited privileges
  - Process isolation and resource limits
  - Input validation and sanitization
  - Code review and approval workflows

## Database

The server uses SQLite by default (`chameleon.db`). The database file is automatically created on first run.

**Configuration Methods (in priority order):**

1. **Command-line argument:**
   ```bash
   python server.py --database-url "postgresql://user:pass@host/db"
   ```

2. **YAML configuration file** (`~/.chameleon/config/config.yaml`):
   ```yaml
   database:
     url: "postgresql://user:pass@host/db"
   ```

3. **Environment variable** (for Admin GUI backward compatibility):
   ```bash
   export CHAMELEON_DB_URL="postgresql://user:pass@host/db"
   streamlit run admin_gui.py
   ```

4. **Default:** `sqlite:///chameleon.db`

**Supported databases:** Any SQLAlchemy-compatible database (SQLite, PostgreSQL, MySQL, etc.)

**Examples:**

```yaml
# SQLite (default)
database:
  url: "sqlite:///chameleon.db"

# PostgreSQL
database:
  url: "postgresql://username:password@localhost:5432/chameleon"

# MySQL
database:
  url: "mysql://username:password@localhost:3306/chameleon"
```

## Development

### Project Structure
```
prototype_chameleon/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── config.py             # Configuration module (YAML config loading)
├── config.yaml.sample    # Sample configuration file
├── models.py             # Database models (CodeVault, ToolRegistry, etc.)
├── runtime.py            # Code execution engine
├── server.py             # MCP server implementation
├── seed_db.py            # Database seeding script
├── admin_gui.py          # Streamlit admin GUI
├── test_config.py        # Configuration module tests
├── test_seed_db.py       # Database seeding tests
├── test_logging.py       # Logging tests
└── .gitignore            # Git ignore patterns
```

### Running Tests

The project includes several test scripts:

1. **Configuration tests:** `python test_config.py`
2. **Database seeding tests:** `python test_seed_db.py`
3. **Server tests:** `python server.py` (database will be auto-seeded on first run)

## Personas

The persona system allows different tool sets for different contexts:
- `default`: Standard tools available to all users
- `assistant`: Specialized tools for assistant persona
- Custom personas can be added as needed

Currently, persona is determined by the `_get_persona_from_context()` function (defaults to 'default').

## License

[Add your license information here]

## Contributing

[Add contributing guidelines here]
