from base import ChameleonTool
from common.hash_utils import compute_hash


class CreateTempResourceTool(ChameleonTool):
    """
    Create a temporary resource that is not persisted to the database.
    
    Temporary resources are stored in memory only and are useful for:
    - Testing and debugging resource structures
    - Experimenting with dynamic resource generation
    - Rapid iteration without cluttering the permanent resource registry
    
    Key features:
    - Can be static (text content) or dynamic (executable code)
    - Not persisted to database
    - Available during runtime only
    - Supports persona-based filtering
    """
    
    def run(self, arguments):
        """
        Create a new temporary resource.
        
        Args:
            uri: URI of the resource (e.g., "memo://test", "data://sample")
            name: Human-readable name of the resource
            description: Description of what the resource provides
            content: The static content (for static resources) or code (for dynamic resources)
            is_dynamic: Boolean flag - True for code-based resources, False for static text (default: False)
            mime_type: MIME type of the content (default: "text/plain")
        
        Returns:
            Success message confirming the temporary resource is registered
        """
        # Import here to avoid circular imports
        # runtime module is in the same search path due to how tools are loaded
        from runtime import TEMP_RESOURCE_REGISTRY, TEMP_CODE_VAULT
        
        # Extract arguments
        uri = arguments.get('uri')
        name = arguments.get('name')
        description = arguments.get('description')
        content = arguments.get('content')
        is_dynamic = arguments.get('is_dynamic', False)
        mime_type = arguments.get('mime_type', 'text/plain')
        
        # Validation 1: Check all required arguments are provided
        if not uri:
            return "Error: uri is required"
        if not name:
            return "Error: name is required"
        if not description:
            return "Error: description is required"
        if not content:
            return "Error: content is required"
        
        # Validation 2: Check URI format (basic validation)
        if '://' not in uri:
            return f"Error: uri must contain '://' scheme separator. Got: {uri}"
        
        # Validation 3: Ensure is_dynamic is boolean
        if not isinstance(is_dynamic, bool):
            return f"Error: is_dynamic must be a boolean (true/false). Got: {type(is_dynamic).__name__}"
        
        self.log(f"Creating temporary resource: {uri}")
        self.log(f"Dynamic: {is_dynamic}, MIME type: {mime_type}")
        
        # Get persona from context
        persona = self.context.get('persona', 'default')
        
        # Store resource metadata
        temp_key = f"{uri}:{persona}"
        
        if is_dynamic:
            # For dynamic resources, compute hash and store code
            code_hash = compute_hash(content)
            
            try:
                # Store code in TEMP_CODE_VAULT
                TEMP_CODE_VAULT[code_hash] = {
                    'code_blob': content,
                    'code_type': 'python'  # Default to python for dynamic resources
                }
                self.log(f"Code stored in temporary vault (hash: {code_hash[:16]}...)")
                
                # Store resource metadata in TEMP_RESOURCE_REGISTRY
                TEMP_RESOURCE_REGISTRY[temp_key] = {
                    'name': name,
                    'description': description,
                    'mime_type': mime_type,
                    'is_dynamic': True,
                    'static_content': None,
                    'code_hash': code_hash,
                    'is_temp': True
                }
                self.log(f"Temporary dynamic resource '{name}' registered for persona '{persona}'")
                
                return (
                    f"Success: Temporary dynamic resource '{name}' has been registered and is ready to use.\n"
                    f"URI: {uri}\n"
                    f"NOTE: This is a TEMPORARY resource that executes code and is not persisted to the database."
                )
                
            except Exception as e:
                return f"Error: Failed to register temporary dynamic resource - {type(e).__name__}: {str(e)}"
        else:
            # For static resources, store content directly
            try:
                # Store resource metadata in TEMP_RESOURCE_REGISTRY
                TEMP_RESOURCE_REGISTRY[temp_key] = {
                    'name': name,
                    'description': description,
                    'mime_type': mime_type,
                    'is_dynamic': False,
                    'static_content': content,
                    'code_hash': None,
                    'is_temp': True
                }
                self.log(f"Temporary static resource '{name}' registered for persona '{persona}'")
                
                return (
                    f"Success: Temporary static resource '{name}' has been registered and is ready to use.\n"
                    f"URI: {uri}\n"
                    f"Content length: {len(content)} characters\n"
                    f"NOTE: This is a TEMPORARY resource that is not persisted to the database."
                )
                
            except Exception as e:
                return f"Error: Failed to register temporary static resource - {type(e).__name__}: {str(e)}"
