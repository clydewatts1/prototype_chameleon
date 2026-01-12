# Database-Stored Jinja Macros

## Overview

The Macro Registry feature allows you to define reusable SQL logic as Jinja2 macros in the database. These macros are automatically injected into every SQL tool's template context, enabling code reuse and consistent business logic across multiple tools.

## Key Features

- **Database-Stored**: Macros are stored in the `MacroRegistry` table
- **Automatic Injection**: Active macros are automatically prepended to all SQL tools
- **Validation**: Macros must be valid Jinja2 macro definitions
- **Active/Inactive**: Control which macros are loaded with the `is_active` flag
- **Meta-Tool**: Create macros dynamically via the `create_new_macro` tool

## Architecture

### Database Model

The `MacroRegistry` model (in `server/models.py`) has the following fields:

```python
class MacroRegistry(SQLModel, table=True):
    name: str              # Primary Key, e.g., 'safe_div'
    description: str       # Description of what the macro does
    template: str          # The Jinja2 macro definition (Text field)
    is_active: bool        # Whether the macro is currently active
```

### Runtime Integration

The macro loading is integrated into `server/runtime.py`:

1. **`_load_macros(meta_session)`**: Helper function that queries all active macros and concatenates their templates
2. **`execute_tool()`**: For SQL tools (`code_type='select'`), macros are loaded and prepended before template rendering

```python
# Step 1: Load active macros and prepend to SQL template
macro_block = _load_macros(meta_session)
if macro_block:
    code_blob_with_macros = f"{macro_block}\n\n{code_blob}"
else:
    code_blob_with_macros = code_blob

# Step 2: Render SQL template with Jinja2
template = Template(code_blob_with_macros)
rendered_sql = template.render(arguments=arguments)
```

## Usage

### 1. Register the Meta-Tool

First, register the macro creator meta-tool:

```bash
cd server
python add_macro_tool.py
```

### 2. Create a Macro

Use the `create_new_macro` tool to create a new macro:

```python
# Via MCP client
tool: create_new_macro
arguments:
  name: "safe_div"
  description: "Safely divide two numbers, returning NULL if divisor is zero"
  template: "{% macro safe_div(a, b) %}CASE WHEN {{ b }} = 0 THEN NULL ELSE {{ a }} / {{ b }} END{% endmacro %}"
```

### 3. Use the Macro in SQL Tools

Once created, the macro is automatically available in all SQL tools:

```sql
-- Create a SQL tool that uses the macro
SELECT 
  store_name,
  department,
  sales_amount,
  {{ safe_div("sales_amount", "100") }} as ratio
FROM sales_per_day
```

## Example: Fiscal Year Calculation

### Create a Fiscal Year Macro

```python
tool: create_new_macro
arguments:
  name: "fiscal_year"
  description: "Calculate fiscal year from a date (fiscal year starts July 1)"
  template: |
    {% macro fiscal_year(date_col) %}
    CASE 
      WHEN CAST(strftime('%m', {{ date_col }}) AS INTEGER) >= 7 
      THEN CAST(strftime('%Y', {{ date_col }}) AS INTEGER) + 1
      ELSE CAST(strftime('%Y', {{ date_col }}) AS INTEGER)
    END
    {% endmacro %}
```

### Use in Multiple SQL Tools

```sql
-- Tool 1: Sales by fiscal year
SELECT 
  {{ fiscal_year("business_date") }} as fiscal_year,
  SUM(sales_amount) as total_sales
FROM sales_per_day
GROUP BY {{ fiscal_year("business_date") }}

-- Tool 2: Top stores by fiscal year
SELECT 
  {{ fiscal_year("business_date") }} as fiscal_year,
  store_name,
  SUM(sales_amount) as total_sales
FROM sales_per_day
WHERE {{ fiscal_year("business_date") }} = :target_year
GROUP BY {{ fiscal_year("business_date") }}, store_name
ORDER BY total_sales DESC
```

## Validation Rules

The `create_new_macro` tool enforces the following validation:

1. **Required Fields**: `name`, `description`, and `template` are required
2. **Start Tag**: Template must start with `{% macro`
3. **End Tag**: Template must end with `{% endmacro %}`

Example of valid macro:

```jinja2
{% macro safe_div(a, b) %}
CASE WHEN {{ b }} = 0 THEN NULL ELSE {{ a }} / {{ b }} END
{% endmacro %}
```

## Security Considerations

### Macro Creation

- Macros are Jinja2 templates and can contain any valid Jinja2 syntax
- SQL security checks (SELECT-only, single statement, etc.) are enforced at **tool execution time**, not macro creation time
- This design allows flexible macro definitions while maintaining security at the execution boundary

### Execution Security

When a SQL tool using macros is executed:

1. Macros are prepended to the SQL template
2. Jinja2 renders the combined template
3. **Security validation** runs on the rendered SQL:
   - Single statement validation
   - Read-only validation (SELECT only)
   - SQLAlchemy parameter binding for values

### Example: Safe vs Unsafe

```sql
-- Safe macro (generates valid SQL)
{% macro safe_div(a, b) %}
CASE WHEN {{ b }} = 0 THEN NULL ELSE {{ a }} / {{ b }} END
{% endmacro %}

-- Using the macro (rendered SQL is validated)
SELECT {{ safe_div("col_a", "col_b") }} FROM table_name
-- Renders to: SELECT CASE WHEN col_b = 0 THEN NULL ELSE col_a / col_b END FROM table_name
-- ✅ Passes validation (single SELECT statement)

-- If a macro generates dangerous SQL, it will be caught at execution
{% macro dangerous() %}
DROP TABLE users; SELECT *
{% endmacro %}

-- Using this macro
SELECT {{ dangerous() }} FROM table_name
-- Renders to: SELECT DROP TABLE users; SELECT * FROM table_name
-- ❌ Fails validation (multiple statements)
```

## Managing Macros

### Deactivate a Macro

To temporarily disable a macro without deleting it, set `is_active = False`:

```python
# Direct database update
from sqlmodel import Session, select
from models import MacroRegistry, get_engine

meta_engine = get_engine("sqlite:///chameleon_meta.db")
with Session(meta_engine) as session:
    statement = select(MacroRegistry).where(MacroRegistry.name == "safe_div")
    macro = session.exec(statement).first()
    if macro:
        macro.is_active = False
        session.add(macro)
        session.commit()
```

### Update a Macro

Use the `create_new_macro` tool again with the same name to update:

```python
tool: create_new_macro
arguments:
  name: "safe_div"  # Same name
  description: "Updated description"
  template: "{% macro safe_div(a, b) %}COALESCE({{ a }} / NULLIF({{ b }}, 0), 0){% endmacro %}"
```

### List All Macros

```python
from sqlmodel import Session, select
from models import MacroRegistry, get_engine

meta_engine = get_engine("sqlite:///chameleon_meta.db")
with Session(meta_engine) as session:
    statement = select(MacroRegistry)
    macros = session.exec(statement).all()
    for macro in macros:
        status = "ACTIVE" if macro.is_active else "INACTIVE"
        print(f"[{status}] {macro.name}: {macro.description}")
```

## Best Practices

### 1. Naming Conventions

- Use descriptive, lowercase names with underscores: `safe_div`, `fiscal_year`, `rolling_avg`
- Avoid SQL keywords: Don't name a macro `select`, `from`, etc.

### 2. Documentation

- Write clear descriptions explaining what the macro does and when to use it
- Include parameter names in the description

### 3. Testing

- Test macros by creating simple SQL tools that use them
- Verify the rendered SQL is correct
- Test edge cases (zero division, NULL values, etc.)

### 4. Parameterization

Remember that macros generate SQL text. For dynamic values, use SQLAlchemy parameter binding:

```sql
-- ✅ Good: Use parameters for values
SELECT {{ safe_div("sales_amount", "100") }} FROM sales_per_day
WHERE store_name = :store_name

-- ❌ Bad: Don't use macros for value injection
SELECT {{ safe_div("sales_amount", "100") }} FROM sales_per_day
WHERE store_name = {{ some_value }}  -- This is SQL injection risk!
```

### 5. Keep Macros Simple

- Each macro should do one thing well
- Compose complex logic from multiple simple macros
- Avoid deeply nested macro calls

## Testing

Comprehensive tests are available in `tests/test_macro_registry_pytest.py`:

```bash
# Run macro tests
pytest tests/test_macro_registry_pytest.py -v

# Run all tests
pytest tests/ -v
```

## Troubleshooting

### Macro Not Available in SQL Tool

**Problem**: Created a macro but it's not available in SQL tools

**Solutions**:
1. Check if macro is active: `SELECT * FROM macroregistry WHERE name = 'your_macro'`
2. Verify macro syntax starts with `{% macro` and ends with `{% endmacro %}`
3. Check for Jinja2 syntax errors in the macro template

### SQL Syntax Error When Using Macro

**Problem**: SQL tool fails with syntax error

**Solutions**:
1. Test the macro in isolation with a simple SQL tool
2. Check the rendered SQL for syntax issues
3. Verify parameter names are correct
4. Make sure macro generates valid SQL for your database (SQLite vs PostgreSQL syntax)

### Macro Creates Security Error

**Problem**: SQL tool using macro fails security validation

**Solutions**:
1. Make sure macro generates only SELECT statements
2. Avoid semicolons in macro output
3. Don't use macros to bypass security - they're subject to the same validation

## Implementation Files

- **Model**: `server/models.py` - `MacroRegistry` class
- **Runtime**: `server/runtime.py` - `_load_macros()` function and integration
- **Meta-Tool Code**: `tools/system/macro_creator.py` - `MacroCreatorTool` class
- **Bootstrap Script**: `server/add_macro_tool.py` - Registration script
- **Tests**: `tests/test_macro_registry_pytest.py` - Comprehensive test suite

## Future Enhancements

Potential future improvements:

1. **Macro Dependencies**: Track which tools use which macros
2. **Macro Versioning**: Version control for macro definitions
3. **Macro Library**: Pre-built library of common macros
4. **Macro Validation**: Enhanced validation of generated SQL at macro creation time
5. **Macro Testing**: Built-in macro testing framework
6. **Macro Documentation**: Auto-generate documentation from macro definitions

## See Also

- [SQL Creator Tool README](SQL_CREATOR_TOOL_README.md) - Creating dynamic SQL tools
- [Execution Log README](EXECUTION_LOG_README.md) - Debugging tool execution
- [Main Server README](README.md) - Complete server documentation
