# Dynamic Meta-Tools for Prompts and Resources

This document describes the two new meta-tools that enable the LLM to dynamically create and update Prompts and Resources in the Chameleon MCP Server.

## Overview

The Chameleon MCP Server now supports "Self-Modifying" capabilities for Prompts and Resources, similar to the existing `create_new_sql_tool` meta-tool for dynamic tool creation.

## Installation

Run the registration script to add the meta-tools to your database:

```bash
python add_dynamic_meta_tools.py
```

This will register both `create_new_prompt` and `create_new_resource` tools.

## Meta-Tool 1: create_new_prompt

### Purpose
Create or update a prompt in the PromptRegistry. This allows the LLM to define new prompt templates dynamically.

### Input Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | The prompt name (e.g., 'review_code') |
| `description` | string | Yes | What the prompt does |
| `template` | string | Yes | The Jinja2/f-string template content |
| `arguments` | array | No | List of argument definitions (name, description, required) |
| `persona` | string | No | Target persona (default: 'default') |

### Example Usage

```json
{
  "tool": "create_new_prompt",
  "arguments": {
    "name": "review_code",
    "description": "Review code for quality and best practices",
    "template": "Please review this code:\n\n{code}\n\nFocus on: {focus_area}",
    "arguments": [
      {
        "name": "code",
        "description": "The code to review",
        "required": true
      },
      {
        "name": "focus_area",
        "description": "What aspect to focus on",
        "required": true
      }
    ]
  }
}
```

### Behavior
- **Upsert Operation**: If a prompt with the same name and persona exists, it will be updated. Otherwise, a new prompt is created.
- **Arguments Schema**: The `arguments` list is automatically converted to a JSON schema for validation.
- **Template Format**: Supports Python f-string style placeholders (e.g., `{variable_name}`).

## Meta-Tool 2: create_new_resource

### Purpose
Create or update a **STATIC** resource in the ResourceRegistry. This allows the LLM to store text content that can be retrieved later.

### Input Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `uri` | string | Yes | The resource URI (e.g., 'memo://project_notes') |
| `name` | string | Yes | Human-readable name |
| `description` | string | Yes | Description of content |
| `content` | string | Yes | The static text content of the resource |
| `mime_type` | string | No | MIME type (default: 'text/plain') |
| `persona` | string | No | Target persona (default: 'default') |

### Example Usage

```json
{
  "tool": "create_new_resource",
  "arguments": {
    "uri": "memo://project_notes",
    "name": "Project Notes",
    "description": "Important notes about the project",
    "content": "Project started on 2024-01-01.\n\nKey goals:\n- Achieve excellence\n- Maintain quality\n- Ship on time"
  }
}
```

### Behavior
- **Upsert Operation**: If a resource with the same URI and persona exists, it will be updated. Otherwise, a new resource is created.
- **Static Only**: Resources created by this tool are explicitly static (`is_dynamic=False`, `active_hash_ref=None`). This is a security precaution to prevent arbitrary code execution.
- **MIME Type**: Defaults to 'text/plain' but can be customized (e.g., 'text/markdown', 'application/json').

## Security Considerations

### Resource Security
- **Static Resources Only**: The `create_new_resource` meta-tool creates STATIC resources only. Dynamic resources (with code execution) must be manually configured by administrators for security reasons.
- **No Code Execution**: Resources created through this tool cannot execute arbitrary code.

### General Security
- Both meta-tools follow the same security model as the existing `create_new_sql_tool`:
  - Code is stored in CodeVault with SHA-256 hash verification
  - Tools inherit from the secure ChameleonTool base class
  - Database transactions are rolled back on errors

## Testing

Run the comprehensive test suite:

```bash
python test_dynamic_meta_tools.py
```

The test suite includes:
1. Meta-tool registration validation
2. Simple prompt creation
3. Simple resource creation
4. Input validation for required fields
5. Idempotency verification (upsert behavior)

## Use Cases

### Prompts
- Define code review templates
- Create documentation generation prompts
- Store reusable instruction templates
- Create context-specific prompts for different personas

### Resources
- Store project notes and documentation
- Cache frequently accessed information
- Create knowledge bases for specific domains
- Store configuration snippets or examples

## Integration with MCP

Once registered, these tools are available through the MCP protocol:

```python
# List available tools
tools = mcp_server.list_tools()

# Execute a tool
result = mcp_server.call_tool(
    "create_new_prompt",
    arguments={
        "name": "my_prompt",
        "description": "My custom prompt",
        "template": "Hello {name}!",
        "arguments": [{"name": "name", "required": true}]
    }
)
```

## Comparison with SQL Creator Tool

| Feature | SQL Creator | Prompt Creator | Resource Creator |
|---------|-------------|----------------|------------------|
| Purpose | Create SQL tools | Create prompts | Create resources |
| Security | SELECT-only queries | No code execution | Static content only |
| Validation | SQL syntax checks | Template validation | Content validation |
| Dynamic | No (SQL queries) | No (templates) | No (static text) |
| Use Case | Data querying | Instruction templates | Information storage |

## Troubleshooting

### "Error: name is required"
Ensure all required fields are provided in the arguments.

### "Prompt not found" after creation
Check that you're using the correct persona when retrieving the prompt. Default is 'default'.

### Resource is not returning content
Verify the URI matches exactly (case-sensitive). Use `list_resources_for_persona()` to see all available resources.

## Future Enhancements

Potential future improvements:
- Dynamic resource support (with proper sandboxing)
- Template validation and testing
- Versioning support for prompts
- Import/export functionality
- Prompt composition and inheritance

## Related Files

- **Script**: `add_dynamic_meta_tools.py` - Registration script
- **Tests**: `test_dynamic_meta_tools.py` - Test suite
- **Models**: `models.py` - PromptRegistry and ResourceRegistry definitions
- **Runtime**: `runtime.py` - Execution logic for prompts and resources
- **Reference**: `add_sql_creator_tool.py` - Similar pattern for SQL tools
