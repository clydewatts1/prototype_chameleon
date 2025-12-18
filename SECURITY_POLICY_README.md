# Security Policy System

## Overview

The Chameleon MCP Server now supports a **database-driven security policy system** for Python code validation. This system allows you to dynamically configure which modules, functions, and attributes are allowed or denied without modifying code.

## Key Features

- **Dynamic Configuration**: Security policies are stored in the database and can be updated without code changes
- **Allow/Deny Lists**: Support for both whitelist (allow) and blacklist (deny) rules
- **Strict Precedence**: Deny rules always override allow rules (blacklist precedence)
- **Category-Based**: Policies can target modules, functions, or attributes
- **Active/Inactive**: Policies can be temporarily disabled without deletion
- **Backward Compatible**: Existing code continues to work with hardcoded defaults

## Database Schema

The `SecurityPolicy` model includes:

```python
class SecurityPolicy(SQLModel, table=True):
    id: int | None              # Auto-incrementing primary key
    rule_type: str              # 'allow' or 'deny'
    category: str               # 'module', 'function', or 'attribute'
    pattern: str                # Name to match (e.g., 'subprocess', 'eval', 'os.system')
    description: str | None     # Optional description
    is_active: bool             # Whether policy is currently enforced (default: True)
```

## Precedence Rules

The security system follows strict precedence rules:

1. **Deny Always Wins**: If a pattern appears in any active `deny` rule, it is blocked regardless of `allow` rules
2. **Explicit Allow**: If a pattern appears only in `allow` rules (and no `deny` rules), it is permitted
3. **Default Behavior**: With an empty policy list, all imports are allowed; with `None` (hardcoded defaults), known dangerous patterns are blocked

## Usage Examples

### 1. Adding Security Policies to Database

```python
from sqlmodel import Session
from models import SecurityPolicy, get_engine, create_db_and_tables

# Setup database
engine = get_engine("sqlite:///chameleon.db")
create_db_and_tables(engine)

with Session(engine) as session:
    # Deny dangerous modules
    deny_subprocess = SecurityPolicy(
        rule_type="deny",
        category="module",
        pattern="subprocess",
        description="Subprocess module can execute system commands",
        is_active=True
    )
    
    deny_eval = SecurityPolicy(
        rule_type="deny",
        category="function",
        pattern="eval",
        description="eval() can execute arbitrary code",
        is_active=True
    )
    
    deny_os_system = SecurityPolicy(
        rule_type="deny",
        category="attribute",
        pattern="os.system",
        description="os.system() can execute shell commands",
        is_active=True
    )
    
    # Allow specific safe module
    allow_requests = SecurityPolicy(
        rule_type="allow",
        category="module",
        pattern="requests",
        description="Requests library is safe for HTTP operations",
        is_active=True
    )
    
    session.add_all([deny_subprocess, deny_eval, deny_os_system, allow_requests])
    session.commit()
```

### 2. Using Policies for Code Validation

```python
from sqlmodel import Session
from models import get_engine
from common.security import load_security_policies, validate_code_structure

engine = get_engine("sqlite:///chameleon.db")

with Session(engine) as session:
    # Load active policies from database
    policies = load_security_policies(session)
    
    # Test code to validate
    code = """
import requests

class MyTool:
    def run(self, args):
        response = requests.get(args['url'])
        return response.text
"""
    
    # This will pass - requests is allowed
    validate_code_structure(code, policies=policies)
    
    # This code would fail - subprocess is denied
    dangerous_code = """
import subprocess

class BadTool:
    def run(self, args):
        subprocess.run(['ls', '-la'])
"""
    
    try:
        validate_code_structure(dangerous_code, policies=policies)
    except SecurityError as e:
        print(f"Security validation failed: {e}")
```

### 3. Blacklist Precedence Example

```python
with Session(engine) as session:
    # Add both allow and deny for the same module
    allow_subprocess = SecurityPolicy(
        rule_type="allow",
        category="module",
        pattern="subprocess",
        is_active=True
    )
    
    deny_subprocess = SecurityPolicy(
        rule_type="deny",
        category="module",
        pattern="subprocess",
        is_active=True
    )
    
    session.add_all([allow_subprocess, deny_subprocess])
    session.commit()
    
    # Load policies and validate
    policies = load_security_policies(session)
    
    code_with_subprocess = """
import subprocess

class MyTool:
    pass
"""
    
    # This will FAIL - deny always overrides allow
    try:
        validate_code_structure(code_with_subprocess, policies=policies)
    except SecurityError as e:
        print(f"Blocked by deny rule: {e}")
```

### 4. Temporarily Disabling Policies

```python
from sqlmodel import select

with Session(engine) as session:
    # Find the subprocess deny policy
    statement = select(SecurityPolicy).where(
        SecurityPolicy.pattern == "subprocess",
        SecurityPolicy.rule_type == "deny"
    )
    policy = session.exec(statement).first()
    
    if policy:
        # Temporarily disable it
        policy.is_active = False
        session.commit()
    
    # Now subprocess imports would be allowed (if not blocked by other rules)
```

### 5. Backward Compatibility (No Policies)

```python
# When no policies are passed, the system uses hardcoded defaults
code_with_eval = """
class MyTool:
    def run(self, args):
        eval("1+1")
"""

# This uses hardcoded BANNED_FUNCTIONS
try:
    validate_code_structure(code_with_eval)  # No policies parameter
except SecurityError as e:
    print(f"Blocked by hardcoded defaults: {e}")
```

## Policy Categories

### Module Policies (`category='module'`)

Controls which Python modules can be imported:

```python
# Deny dangerous modules
patterns = ["subprocess", "sys", "importlib", "shutil", "pickle", "marshal"]

# Allow specific modules
patterns = ["requests", "json", "datetime", "typing"]
```

### Function Policies (`category='function'`)

Controls which built-in functions can be called:

```python
# Deny dangerous functions
patterns = ["eval", "exec", "compile", "open", "__import__", "input"]

# Allow specific functions (usually not needed as most are safe by default)
patterns = ["print", "len", "range"]
```

### Attribute Policies (`category='attribute'`)

Controls specific method calls on modules:

```python
# Deny dangerous method calls
patterns = ["os.system", "os.popen", "os.spawn", "os.exec", "os.fork"]

# Format: "module.method"
```

## Best Practices

1. **Start with Deny Rules**: Define what should be blocked first
2. **Use Descriptions**: Document why each policy exists
3. **Test Policies**: Validate policies work as expected before deploying
4. **Audit Active Policies**: Regularly review active policies for appropriateness
5. **Use is_active Flag**: Disable policies temporarily instead of deleting them
6. **Layer Security**: Policies are one layer - also use OS-level sandboxing in production

## Migration from Hardcoded Security

The system maintains backward compatibility. Existing code continues to work:

```python
# Old way (still works)
from common.security import validate_code_structure

validate_code_structure(code)  # Uses hardcoded BANNED_MODULES/BANNED_FUNCTIONS

# New way (database-driven)
from common.security import validate_code_structure, load_security_policies

policies = load_security_policies(session)
validate_code_structure(code, policies=policies)
```

## Default Hardcoded Policies

When `policies=None` (backward compatibility mode), these defaults apply:

**Banned Modules:**
- `importlib`
- `subprocess`
- `sys`
- `shutil`
- `marshal`
- `pickle`

**Banned Functions:**
- `exec`
- `eval`
- `compile`
- `open`
- `input`
- `exit`
- `quit`
- `help`
- `__import__`

**Banned Attributes (legacy checks):**
- `os.system`
- `os.popen`
- `os.spawn`
- `os.exec`
- `os.fork`
- `subprocess.*` (all subprocess module methods)

## Security Considerations

⚠️ **Important Security Notes:**

1. **Not a Complete Sandbox**: AST validation is one security layer but not a complete sandbox
2. **Trusted Code Only**: Only use with trusted code sources in the database
3. **Production Deployment**: Add OS-level sandboxing (containers, VMs) for production
4. **Regular Audits**: Review and update policies regularly
5. **Test Thoroughly**: Validate policies don't break legitimate functionality

## Querying Policies

```python
from sqlmodel import select

with Session(engine) as session:
    # Get all active deny rules
    statement = select(SecurityPolicy).where(
        SecurityPolicy.rule_type == "deny",
        SecurityPolicy.is_active == True
    )
    deny_policies = session.exec(statement).all()
    
    # Get policies for a specific category
    statement = select(SecurityPolicy).where(
        SecurityPolicy.category == "module"
    )
    module_policies = session.exec(statement).all()
    
    # Get a specific policy
    statement = select(SecurityPolicy).where(
        SecurityPolicy.pattern == "subprocess"
    )
    subprocess_policies = session.exec(statement).all()
```

## Testing

The test suite includes comprehensive coverage:

```bash
# Run security policy tests
pytest tests/test_security_policy.py -v

# Run all security tests
pytest tests/test_security*.py -v
```

Key test scenarios:
- Policy creation and storage
- Deny/allow rule enforcement
- Blacklist precedence over whitelist
- Inactive policy handling
- Backward compatibility
- Multiple policy interactions

## See Also

- `common/security.py` - Security validation implementation
- `server/models.py` - SecurityPolicy model definition
- `tests/test_security_policy.py` - Comprehensive test suite
