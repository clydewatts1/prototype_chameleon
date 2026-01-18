# Quality Control Protocol

The Quality Control Protocol ensures that all tools in the Chameleon MCP Server are functional, verifiable, and safe. It relies on a "Verifier" system tool (`system_verify_tool`) that runs examples defined in a tool's manual (`extended_metadata`) as live unit tests.

## The Verifier (`system_verify_tool`)

The `system_verify_tool` is a meta-tool that:
1.  Dynamically loads the target tool's code from the database.
2.  Reads the `examples` from the target tool's `extended_metadata`.
3.  Executes each example against the tool instance.
4.  Reports PASS/FAIL status.
5.  Updates the `verified` flag in the target tool's metadata upon success.

### Usage

To verify a tool (e.g., `utility_greet`), run:

```json
{
  "tool_name": "system_verify_tool",
  "arguments": {
    "tool_name": "utility_greet"
  }
}
```

### Self-Verification

The Verifier can verify itself:

```json
{
  "tool_name": "system_verify_tool",
  "arguments": {
    "tool_name": "system_verify_tool"
  }
}
```

## Adding Verification Examples

To make a tool verifiable, you must add an `extended_metadata` dictionary to its `ToolRegistry` entry. This usually happens in the registration script (e.g., `add_my_tool.py`) or via `update_tool_manuals.py`.

### Schema

```python
extended_metadata={
    "usage_guide": "Brief description of how to use the tool.",
    "examples": [
        {
            "input": {"arg1": "value1"},
            "expected_output_summary": "Optional description of expected result",
            "verified": False  # System updates this to True automatically
        }
    ],
    "pitfalls": ["List of common mistakes."]
}
```

### Example

```python
# In add_math_tool.py
tool = ToolRegistry(
    tool_name='math_add',
    # ...
    extended_metadata={
        "usage_guide": "Adds two numbers together.",
        "examples": [
            {
                "input": {"a": 10, "b": 5},
                "expected_output_summary": "15"
            }
        ]
    }
)
```

## Running Verification

You can run verification manually using the server's CLI or by creating a script.

### Using `run_verification.py` (Recommended)

Ideally, create a script like `server/run_verification.py` that batches verification for critical tools:

```python
# ... (setup code) ...
verifier.run({"tool_name": "utility_greet"})
verifier.run({"tool_name": "math_add"})
# ...
```

This ensures a baseline of functionality before deployment.
