from base import ChameleonTool
from sqlmodel import select

class MacroCreatorTool(ChameleonTool):
    def run(self, arguments):
        '''
        Create a new Jinja2 macro for reuse in SQL tools.
        
        Args:
            name: Name of the macro (e.g., "safe_div")
            description: Description of what the macro does
            template: The Jinja2 macro definition (must start with {% macro and end with {% endmacro %})
        
        Returns:
            Success message confirming the macro is registered
        '''
        from models import MacroRegistry
        
        # Extract arguments
        name = arguments.get('name')
        description = arguments.get('description')
        template = arguments.get('template')
        
        # Validation 1: Check all required arguments are provided
        if not name:
            return "Error: name is required"
        if not description:
            return "Error: description is required"
        if not template:
            return "Error: template is required"
        
        # Validation 2: Ensure template starts with {% macro
        template_stripped = template.strip()
        if not template_stripped.startswith('{% macro'):
            return "Error: template must start with '{% macro'"
        
        # Validation 3: Ensure template ends with {% endmacro %}
        if not template_stripped.endswith('{% endmacro %}'):
            return "Error: template must end with '{% endmacro %}'"
        
        self.log(f"Creating macro: {name}")
        self.log(f"Macro validation passed")
        
        try:
            # Upsert into MacroRegistry
            statement = select(MacroRegistry).where(MacroRegistry.name == name)
            existing_macro = self.db_session.exec(statement).first()
            
            if existing_macro:
                # Update existing macro
                existing_macro.description = description
                existing_macro.template = template
                existing_macro.is_active = True
                self.db_session.add(existing_macro)
                self.log(f"Macro '{name}' updated in MacroRegistry")
            else:
                # Create new macro
                macro = MacroRegistry(
                    name=name,
                    description=description,
                    template=template,
                    is_active=True
                )
                self.db_session.add(macro)
                self.log(f"Macro '{name}' created in MacroRegistry")
            
            # Commit changes
            self.db_session.commit()
            
            return f"Success: Macro '{name}' has been registered and is ready to use in SQL tools."
            
        except Exception as e:
            self.db_session.rollback()
            return f"Error: Failed to register macro - {type(e).__name__}: {str(e)}"
