# Agent Notebook - Long-Term Memory System

The Agent Notebook is a long-term memory ecosystem for the Chameleon MCP server that enables persistent storage of knowledge, self-correction, and memory portability.

## Features

### 1. 🧠 Visual Cortex (UI Integration)

A Streamlit-based UI for managing the agent's memory.

**Access:**
```bash
cd server
streamlit run admin_gui.py
```

Then navigate to the **"Agent Notebook"** tab.

**Features:**
- **Domain Filter:** Filter entries by domain (namespace) from the sidebar
- **Memory Editor:** View and edit notebook entries with inline editing
- **History Viewer:** See all past changes for each entry with old/new value diffs
- **Add Entries:** Create new memory entries directly from the UI
- **Soft Delete:** Deactivate entries without permanently removing them

### 2. 🔄 Reflexive Learning (Self-Correction)

Automatic logging of tool failures for agent self-improvement.

**How it Works:**
When any tool crashes during execution, the system automatically:
1. Captures the error type and message
2. Records the failing arguments
3. Stores the lesson in the `self_correction` domain
4. Appends multiple failures to track patterns

**Example:**
```python
# Tool fails automatically
execute_tool("sql_query_tool", "default", {"query": "SELECT bad_column"}, session)

# System automatically creates:
# Domain: "self_correction"
# Key: "sql_query_tool_error"
# Value: "[2026-01-19T10:30:00] ValueError: Column 'bad_column' not found | Failed with args: query=SELECT bad_column"
```

**Benefits:**
- Agent can query past mistakes before attempting similar operations
- Patterns emerge when the same tool fails multiple times
- Human operators can review and enhance error lessons via UI

### 3. 💾 Memory Portability (Backup)

Export memory to YAML for backup, migration, or review.

**Usage:**
```bash
cd server
python export_memory.py [output_file]
```

**Example:**
```bash
# Export to default file (memory_dump.yaml)
python export_memory.py

# Export to custom path
python export_memory.py /backups/memory_2026-01-19.yaml
```

**Output Format:**
```yaml
domains:
  user_prefs:
    theme: "dark"
    language: "en"
    font_size: "14"
  self_correction:
    sql_query_tool_error: "[2026-01-19] ValueError: Column not found..."
  project_alpha:
    status: "active"
    last_build: "2026-01-19"
```

## Database Models

### AgentNotebook

Main table for storing long-term memory entries.

**Schema:**
- `domain` (PK): Namespace for grouping related memories
- `key` (PK): Unique identifier within the domain
- `value`: The stored memory value (text)
- `created_at`: When the entry was first created (UTC)
- `updated_at`: When the entry was last modified (UTC)
- `updated_by`: Who/what made the last update
- `is_active`: Soft delete flag (true = active, false = deleted)

**Example Domains:**
- `user_prefs` - User preferences (theme, language, settings)
- `self_correction` - Tool failure lessons
- `project_*` - Project-specific state and context
- `system` - System configuration and metadata

### NotebookHistory

Tracks all changes to notebook entries.

**Schema:**
- `id`: Auto-incrementing primary key
- `domain`: Domain of the changed entry
- `key`: Key of the changed entry
- `old_value`: Previous value before the change
- `new_value`: New value after the change
- `changed_at`: When the change occurred (UTC)
- `changed_by`: Who/what made the change

### NotebookAudit

Optional audit trail for access patterns.

**Schema:**
- `id`: Auto-incrementing primary key
- `domain`: Domain of the accessed entry
- `key`: Key of the accessed entry
- `access_type`: Type of access ('read', 'write', 'delete')
- `accessed_at`: When the access occurred (UTC)
- `accessed_by`: Who/what accessed the entry
- `context_data`: Additional context as JSON

## Usage Examples

### Reading Memory

```python
from sqlmodel import Session, select
from models import AgentNotebook, get_engine

config = load_config()
engine = get_engine(config['metadata_database']['url'])

with Session(engine) as session:
    # Read a specific entry
    statement = select(AgentNotebook).where(
        AgentNotebook.domain == "user_prefs",
        AgentNotebook.key == "theme"
    )
    entry = session.exec(statement).first()
    
    if entry:
        print(f"Theme: {entry.value}")
```

### Writing Memory

```python
from datetime import datetime, timezone
from models import AgentNotebook, NotebookHistory

with Session(engine) as session:
    # Check if entry exists
    statement = select(AgentNotebook).where(
        AgentNotebook.domain == "user_prefs",
        AgentNotebook.key == "theme"
    )
    entry = session.exec(statement).first()
    
    if entry:
        # Update existing entry with history
        old_value = entry.value
        entry.value = "light"
        entry.updated_at = datetime.now(timezone.utc)
        entry.updated_by = "user"
        
        # Record history
        history = NotebookHistory(
            domain=entry.domain,
            key=entry.key,
            old_value=old_value,
            new_value=entry.value,
            changed_by="user"
        )
        session.add(history)
    else:
        # Create new entry
        entry = AgentNotebook(
            domain="user_prefs",
            key="theme",
            value="light",
            updated_by="user"
        )
        session.add(entry)
    
    session.commit()
```

### Querying Self-Correction History

```python
# Get all tool errors
statement = select(AgentNotebook).where(
    AgentNotebook.domain == "self_correction",
    AgentNotebook.is_active == True
)
errors = session.exec(statement).all()

for error in errors:
    tool_name = error.key.replace("_error", "")
    print(f"Tool: {tool_name}")
    print(f"Lessons learned: {error.value[:100]}...")
    print()
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Server                           │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Runtime (runtime.py)                             │  │
│  │                                                  │  │
│  │  Tool Execution → Catches Exceptions →          │  │
│  │  log_self_correction() →                        │  │
│  │  Writes to AgentNotebook                        │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Database Models (models.py)                      │  │
│  │  • AgentNotebook (main storage)                  │  │
│  │  • NotebookHistory (change tracking)             │  │
│  │  • NotebookAudit (access logging)                │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │ UI (ui_components/notebook_view.py)              │  │
│  │  • View/Edit entries                             │  │
│  │  • Domain filtering                              │  │
│  │  • History viewer                                │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Export (export_memory.py)                        │  │
│  │  • YAML backup generation                        │  │
│  │  • Domain-organized output                       │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Testing

Comprehensive test suite included in `tests/test_agent_notebook.py`:

```bash
# Run all Agent Notebook tests
pytest tests/test_agent_notebook.py -v

# Run specific test
pytest tests/test_agent_notebook.py::test_self_correction_logging -v
```

**Test Coverage:**
- ✅ Model creation and validation
- ✅ History tracking
- ✅ Audit logging
- ✅ Soft delete functionality
- ✅ Self-correction logging
- ✅ Domain filtering
- ✅ Memory export
- ✅ Composite primary key constraints

## Best Practices

### Domain Naming

Use clear, hierarchical domain names:
- `user_prefs` - User preferences
- `self_correction` - Tool failure lessons (reserved)
- `project_{name}` - Project-specific data
- `system` - System configuration
- `persona_{name}` - Persona-specific memory

### Value Storage

- Keep values concise but informative
- Use JSON for structured data
- Use multiline strings for detailed descriptions
- Include timestamps when logging events

### History Management

- Always record history when updating values
- Include meaningful `changed_by` identifiers
- Review history before making destructive changes

### Export Frequency

- Export after significant changes
- Include exports in backup schedules
- Use dated filenames for version control

## Security Considerations

- **Sensitive Data:** Do not store credentials or secrets in notebook entries
- **Access Control:** UI access requires server access permissions
- **Audit Trail:** Use NotebookAudit for compliance requirements
- **Backup Security:** Protect exported YAML files appropriately

## Future Enhancements

Potential additions to the Agent Notebook system:

1. **Import from YAML:** Restore memory from backup files
2. **Search/Query UI:** Full-text search across all entries
3. **Visualization:** Timeline view of memory evolution
4. **API Endpoints:** REST API for external access
5. **Encryption:** Optional encryption for sensitive entries
6. **Versioning:** Git-like branching for memory states

## Support

For issues or questions:
1. Check the test suite for usage examples
2. Review the inline code documentation
3. Open an issue on the GitHub repository

---

**Version:** 1.0.0  
**Last Updated:** 2026-01-19  
**Status:** Production Ready ✅
