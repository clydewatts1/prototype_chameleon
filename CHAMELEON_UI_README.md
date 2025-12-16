# Chameleon UI Feature

## Overview

The Chameleon UI feature enables LLMs to dynamically create and host interactive Streamlit dashboards. This allows AI agents to generate data visualizations, interactive reports, and user interfaces on-demand.

## Architecture

### Components

1. **Configuration** (`server/config.py`)
   - Adds `features.chameleon_ui` section to configuration
   - Fields: `enabled` (bool), `apps_dir` (string, default: "ui_apps")

2. **Data Model** (`server/models.py`)
   - Extended `CodeVault.code_type` to support `'streamlit'` in addition to `'python'` and `'select'`

3. **Dashboard Creator Tool** (`tools/system/ui_creator.py`)
   - Core logic for creating Streamlit dashboards
   - Validates code imports streamlit
   - Sanitizes dashboard names
   - Saves code to both CodeVault (database) and physical file

4. **Meta-Tool Registration** (`server/add_ui_tool.py`)
   - Registers the `create_dashboard` meta-tool
   - Provides the interface for LLMs to create dashboards

5. **Runtime Execution** (`server/runtime.py`)
   - Handles execution of `code_type='streamlit'` tools
   - Returns dashboard URL instead of executing code
   - Validates feature is enabled

6. **Launcher Scripts**
   - `run_ui.sh` - Bash script to start Streamlit server
   - `run_ui.py` - Python script with configuration integration

## Configuration

### YAML Configuration

Add to `~/.chameleon/config/config.yaml`:

```yaml
features:
  chameleon_ui:
    enabled: true
    apps_dir: ui_apps  # Directory to store dashboard files
```

### Default Configuration

If no configuration file exists, the feature is **enabled by default** with `apps_dir: "ui_apps"`.

## Usage

### 1. Register the Meta-Tool

```bash
cd server
python add_ui_tool.py
```

This registers the `create_dashboard` tool in the database.

### 2. Create a Dashboard

Using the MCP protocol, call the `create_dashboard` tool:

```json
{
  "tool": "create_dashboard",
  "arguments": {
    "dashboard_name": "sales_analytics",
    "python_code": "import streamlit as st\n\nst.title('Sales Dashboard')\nst.write('Hello, World!')"
  }
}
```

**Requirements:**
- `dashboard_name`: Alphanumeric characters, underscores, or dashes only
- `python_code`: Must import streamlit (either `import streamlit` or `from streamlit`)

### 3. Start the Streamlit Server

**Option A: Python Script (Recommended)**
```bash
python run_ui.py [apps_dir] [port]
```

**Option B: Bash Script**
```bash
./run_ui.sh [apps_dir] [port]
```

**Defaults:**
- `apps_dir`: Value from config or "ui_apps"
- `port`: 8501 (Streamlit default)

### 4. Access the Dashboard

Once the Streamlit server is running, call the dashboard tool to get the URL:

```json
{
  "tool": "sales_analytics",
  "arguments": {}
}
```

**Response:**
```
Dashboard is ready! Access it at: http://localhost:8501/?page=sales_analytics
```

## Example: Creating a Sales Dashboard

### Step 1: Create the Dashboard

```python
dashboard_code = """
import streamlit as st
import pandas as pd
import numpy as np

st.title('Sales Analytics Dashboard')
st.write('Welcome to the Sales Analytics Dashboard!')

# Generate sample data
data = pd.DataFrame({
    'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
    'Sales': [10000, 15000, 12000, 18000, 20000, 22000]
})

st.subheader('Monthly Sales')
st.bar_chart(data.set_index('Month'))

st.subheader('Sales Summary')
st.metric(label='Total Sales', value=f'${data["Sales"].sum():,}')
st.metric(label='Average Sales', value=f'${data["Sales"].mean():,.0f}')
"""

# Call create_dashboard via MCP
result = create_dashboard(
    dashboard_name="sales_analytics",
    python_code=dashboard_code
)
```

### Step 2: Launch Streamlit

```bash
python run_ui.py
```

### Step 3: Access Dashboard

Navigate to `http://localhost:8501` or call the `sales_analytics` tool to get the URL.

## Security Features

### 1. Import Validation
- Dashboard code **must** import streamlit
- Ensures the code is intended for Streamlit execution

### 2. Name Sanitization
- Dashboard names are restricted to alphanumeric characters, underscores, and dashes
- Prevents directory traversal and injection attacks

### 3. Feature Toggle
- Can be disabled via configuration: `features.chameleon_ui.enabled: false`
- Runtime checks ensure feature is enabled before execution

### 4. Physical File Storage
- Dashboard code is saved to physical files in the `apps_dir`
- Streamlit requires physical files to run applications

### 5. Database Integrity
- Code is stored in `CodeVault` with SHA-256 hash
- Maintains consistency between database and physical files

## Workflow

### Dashboard Creation Flow

```
LLM Request
    ↓
create_dashboard tool
    ↓
UiCreatorTool.run()
    ↓
├─ Validate feature enabled
├─ Validate streamlit import
├─ Sanitize dashboard_name
├─ Compute SHA-256 hash
├─ Write to physical file (apps_dir/{name}.py)
├─ Upsert to CodeVault (code_type='streamlit')
└─ Upsert to ToolRegistry
    ↓
Return success message
```

### Dashboard Execution Flow

```
LLM Request
    ↓
execute_tool(dashboard_name, ...)
    ↓
runtime.execute_tool()
    ↓
├─ Fetch tool from ToolRegistry
├─ Check code_type == 'streamlit'
├─ Validate feature enabled
└─ Return dashboard URL
    ↓
Return: "Dashboard is ready! Access it at: http://localhost:8501/..."
```

## File Structure

```
prototype_chameleon/
├── server/
│   ├── config.py              # Configuration with chameleon_ui settings
│   ├── models.py              # CodeVault with 'streamlit' code_type
│   ├── runtime.py             # Handles streamlit execution
│   ├── add_ui_tool.py         # Meta-tool registration script
│   └── ui_apps/               # Generated dashboard files (gitignored)
│       └── {dashboard_name}.py
├── tools/
│   └── system/
│       └── ui_creator.py      # Dashboard creation logic
├── run_ui.py                  # Python launcher script
├── run_ui.sh                  # Bash launcher script
├── tests/
│   └── test_chameleon_ui_pytest.py  # Test suite
└── CHAMELEON_UI_README.md     # This file
```

## Testing

### Run Tests

```bash
cd /home/runner/work/prototype_chameleon/prototype_chameleon
python -m pytest tests/test_chameleon_ui_pytest.py -v
```

### Test Coverage

- Configuration loading and defaults
- Meta-tool registration
- Dashboard creation with validation
- Streamlit import requirement
- Dashboard name sanitization
- Dashboard execution (URL return)
- Tool updates (idempotency)
- Error handling (missing arguments)

## Limitations

### Current Implementation

1. **Single Dashboard Launch**
   - The launcher scripts currently launch only the first dashboard found
   - For multiple dashboards, consider Streamlit's multipage app structure

2. **Separate Streamlit Process**
   - Streamlit server must be started manually via launcher scripts
   - Not automatically started by the MCP server

3. **No Dashboard Deletion**
   - Dashboards can be updated but not deleted via the tool
   - Physical files must be manually removed if needed

4. **Port Management**
   - Default port is 8501
   - No automatic port conflict resolution

### Future Enhancements

1. **Multipage App Support**
   - Automatically organize multiple dashboards as pages
   - Dynamic page navigation

2. **Auto-Launch Integration**
   - Start Streamlit server automatically with MCP server
   - Process management and health checking

3. **Dashboard Management**
   - Delete dashboard tool
   - List available dashboards tool
   - Dashboard versioning

4. **Enhanced Security**
   - Code sandboxing for dashboard execution
   - Resource limits (CPU, memory, execution time)
   - User authentication/authorization

## Troubleshooting

### Dashboard Not Found

**Issue:** Error when calling dashboard tool
**Solution:** Ensure you've run `python add_ui_tool.py` to register the meta-tool

### Streamlit Import Error

**Issue:** "Error: python_code must import streamlit"
**Solution:** Add `import streamlit as st` to the beginning of your code

### Invalid Dashboard Name

**Issue:** "Error: dashboard_name must contain only alphanumeric..."
**Solution:** Use only letters, numbers, underscores, or dashes in the name

### Feature Disabled

**Issue:** "Error: Chameleon UI feature is disabled"
**Solution:** Check `~/.chameleon/config/config.yaml` and set `features.chameleon_ui.enabled: true`

### No Dashboard Files Found

**Issue:** Launcher script reports no dashboards
**Solution:** Create a dashboard first using the `create_dashboard` tool

## Contributing

When extending the Chameleon UI feature:

1. **Follow Security Best Practices**
   - Always validate user input
   - Sanitize file paths
   - Check feature flags

2. **Maintain Test Coverage**
   - Add tests for new functionality
   - Follow existing test patterns in `test_chameleon_ui_pytest.py`

3. **Update Documentation**
   - Keep this README up to date
   - Document configuration changes
   - Provide usage examples

4. **Consider Backward Compatibility**
   - Don't break existing dashboards
   - Version configuration changes appropriately

## License

Same as the main Prototype Chameleon project.
