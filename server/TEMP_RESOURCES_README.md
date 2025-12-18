# Temporary Resources Feature

## Overview

The Temporary Resources feature allows LLMs to create temporary, in-memory resources for testing and development purposes. These resources are:

- **Not persisted** to the database (exist only in memory)
- **Static or dynamic** (text content or executable code)
- **Persona-based** (filtered by persona like standard resources)
- **Perfect for testing** resource structures without cluttering the permanent resource registry

## Key Components

### 1. In-Memory Storage (`server/runtime.py`)

Two global dictionaries store temporary resources:

```python
TEMP_RESOURCE_REGISTRY: Dict[str, Dict[str, Any]] = {}
# Key: "uri:persona" (e.g., "memo://test:default")
# Value: {name, description, mime_type, is_dynamic, static_content, code_hash, is_temp}

TEMP_CODE_VAULT: Dict[str, Dict[str, Any]] = {}
# Key: code_hash (SHA-256)
# Value: {code_blob, code_type}
```

### 2. Resource Creator (`tools/system/temp_resource_creator.py`)

The `CreateTempResourceTool` class provides the meta-tool that LLMs use to create temporary resources:

```python
class CreateTempResourceTool(ChameleonTool):
    """Create temporary resources (static or dynamic) with no database persistence."""
```

### 3. Registration Script (`server/add_temp_resource_creator.py`)

Registers the `create_temp_resource` meta-tool in the database:

```bash
python server/add_temp_resource_creator.py
```

## Usage

### Creating a Static Temporary Resource

Use the `create_temp_resource` meta-tool via MCP:

```json
{
  "tool": "create_temp_resource",
  "arguments": {
    "uri": "memo://test_note",
    "name": "Test Note",
    "description": "A test note for development",
    "content": "This is the content of my test note.",
    "is_dynamic": false,
    "mime_type": "text/plain"
  }
}
```

**Response:**
```
Success: Temporary static resource 'Test Note' has been registered and is ready to use.
URI: memo://test_note
Content length: 41 characters
NOTE: This is a TEMPORARY resource that is not persisted to the database.
```

### Creating a Dynamic Temporary Resource

For resources that execute code when accessed:

```json
{
  "tool": "create_temp_resource",
  "arguments": {
    "uri": "data://sales_summary",
    "name": "Sales Summary",
    "description": "Dynamic sales summary resource",
    "content": "class SalesSummary(ChameleonTool):\n    def run(self, arguments):\n        # Access data_session to query database\n        from sqlmodel import select\n        from models import SalesPerDay\n        stmt = select(SalesPerDay)\n        results = self.data_session.exec(stmt).all()\n        return f'Total records: {len(results)}'",
    "is_dynamic": true,
    "mime_type": "text/plain"
  }
}
```

**Note:** Dynamic resource code:
- Must define a class inheriting from `ChameleonTool`
- ChameleonTool is automatically injected into the namespace (no import needed)
- Can access `self.meta_session` (metadata DB) and `self.data_session` (business data DB)
- Receives `arguments` dict containing `uri` and `persona`

### Listing Resources

Temporary resources appear in resource listings with a `[TEMP]` prefix:

```json
{
  "tool": "list_resources",
  "arguments": {
    "persona": "default"
  }
}
```

**Response includes:**
```json
[
  {
    "uri": "memo://test_note",
    "name": "Test Note",
    "description": "[TEMP] A test note for development",
    "mimeType": "text/plain"
  }
]
```

### Retrieving Resources

Use the standard MCP Resources API or the `read_resource` tool:

```json
{
  "tool": "read_resource",
  "arguments": {
    "uri": "memo://test_note"
  }
}
```

**Response:**
```
This is the content of my test note.
```

For dynamic resources, the code is executed when the resource is accessed.

## Architecture Details

### Runtime Flow

1. **Creation**: `create_temp_resource` tool validates inputs and stores metadata in `TEMP_RESOURCE_REGISTRY`
2. **Listing**: `list_resources_for_persona()` queries DB and appends temporary resources with `[TEMP]` prefix
3. **Retrieval**: `get_resource()` checks `TEMP_RESOURCE_REGISTRY` first, then falls back to database
4. **Execution** (dynamic): Code is fetched from `TEMP_CODE_VAULT` and executed securely

### Key Features

#### URI Parsing
- Uses `rsplit(':', 1)` to split URI from persona in the temp_key format
- Handles URIs with colons (e.g., "http://example.com:8080")
- Example: "http://api.example.com:8080:default" → URI="http://api.example.com:8080", persona="default"

#### Security
- Dynamic resources use the same security validation as standard resources
- Code structure validation (AST analysis)
- Class-based plugin architecture
- ChameleonTool injection (no dangerous imports needed)

#### Persona Support
- Resources are scoped to the persona they were created in
- Different personas cannot see each other's temporary resources
- Same URI can exist for different personas

## Testing

Comprehensive test suite in `tests/test_temp_resource_pytest.py`:

```bash
pytest tests/test_temp_resource_pytest.py -v
```

**Coverage:**
- ✅ Meta-tool registration
- ✅ Static resource creation
- ✅ Dynamic resource creation
- ✅ Resource retrieval (static and dynamic)
- ✅ Listing with `[TEMP]` prefix
- ✅ Non-persistence to database
- ✅ Persona-based filtering
- ✅ Input validation
- ✅ Error handling

## Use Cases

### 1. Testing Resource Structures
Quickly test resource URIs and content without polluting the database:
```json
{
  "uri": "test://structure",
  "name": "Structure Test",
  "description": "Testing URI structure",
  "content": "Test content",
  "is_dynamic": false
}
```

### 2. Prototyping Dynamic Resources
Experiment with dynamic resource code before committing to the database:
```json
{
  "uri": "proto://query",
  "name": "Query Prototype",
  "description": "Prototype dynamic query",
  "content": "class QueryProto(ChameleonTool):\n    def run(self, args):\n        return 'Testing'",
  "is_dynamic": true
}
```

### 3. Development and Debugging
Create temporary data sources for testing LLM workflows:
```json
{
  "uri": "memo://debug",
  "name": "Debug Info",
  "description": "Temporary debug information",
  "content": "Debug output: ...",
  "is_dynamic": false
}
```

## Comparison with Temporary Test Tools

| Feature | Temporary Resources | Temporary Test Tools |
|---------|-------------------|-------------------|
| Purpose | In-memory resources | In-memory SQL tools |
| Storage | `TEMP_RESOURCE_REGISTRY` | `TEMP_TOOL_REGISTRY` |
| Content Type | Static text or dynamic code | SQL queries only |
| Execution | Via `get_resource()` | Via `execute_tool()` |
| Constraints | None (validated by security) | Automatic LIMIT 3 |
| Use Case | Testing resource structures | Testing SQL queries |

## Best Practices

1. **Naming Convention**: Use descriptive URIs with clear schemes (e.g., `test://`, `memo://`, `data://`)
2. **Dynamic Code**: Keep dynamic resource code simple and focused
3. **Cleanup**: Clear `TEMP_RESOURCE_REGISTRY` when no longer needed (automatic on server restart)
4. **Documentation**: Document the purpose of temporary resources in their descriptions
5. **Security**: Follow the same security practices as standard dynamic resources

## Limitations

1. **No Persistence**: Resources are lost when the server restarts
2. **Memory Only**: Suitable for testing, not production use
3. **No Versioning**: No history or version control
4. **Limited Visibility**: Only visible to the creating persona

## See Also

- **TEMP_TEST_TOOLS_README.md**: Similar feature for temporary SQL tools
- **DYNAMIC_META_TOOLS_README.md**: Guide to meta-tools in general
- **server/README.md**: Main server documentation
- **models.py**: ResourceRegistry schema
