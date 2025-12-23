"""
ChainTool - Workflow Engine with DAG Validation

This tool allows chaining multiple tool calls together in a single workflow.
It validates dependencies to ensure a Directed Acyclic Graph (DAG) structure,
preventing infinite loops and circular dependencies.
"""

import re
import json
from typing import Any, Dict, List, Set
from base import ChameleonTool


class DAGViolationError(Exception):
    """Raised when a chain violates DAG constraints (e.g., forward references)."""
    pass


class ChainTool(ChameleonTool):
    """
    Execute a chain of tool calls with variable substitution and DAG validation.
    
    Features:
    - DAG validation: Ensures steps only reference earlier steps
    - Variable substitution: Supports ${step_id.key} syntax
    - Error monitoring: Returns detailed reports on partial execution
    """
    
    def run(self, arguments: Dict[str, Any]) -> Any:
        """
        Execute a chain of tool calls.
        
        Args:
            arguments: Dict containing 'steps' - list of step definitions
            
        Each step should have:
            - id: Unique identifier for this step
            - tool: Name of the tool to execute
            - args: Arguments to pass to the tool (supports ${step_id.key} references)
            
        Returns:
            Final state dictionary or formatted output
            
        Raises:
            DAGViolationError: If a step references a future step
            ValueError: If steps are malformed
        """
        steps = arguments.get('steps', [])
        
        if not steps:
            return "Error: No steps provided in chain"
        
        if not isinstance(steps, list):
            return "Error: 'steps' must be a list"
        
        # Validate all steps have required fields
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                return f"Error: Step {i} is not a dictionary"
            if 'id' not in step:
                return f"Error: Step {i} missing required field 'id'"
            if 'tool' not in step:
                return f"Error: Step {i} (id='{step.get('id', 'unknown')}') missing required field 'tool'"
            if 'args' not in step:
                return f"Error: Step {i} (id='{step.get('id', 'unknown')}') missing required field 'args'"
        
        # Step 1: DAG Validation - Check that all variable references are to previous steps
        try:
            self._validate_dag(steps)
        except DAGViolationError as e:
            return f"DAG Validation Error: {str(e)}"
        
        # Step 2: Execute the chain
        state = {}
        executed_steps = []
        
        for i, step in enumerate(steps):
            step_id = step['id']
            tool_name = step['tool']
            step_args = step['args']
            
            try:
                # Resolve variables in arguments
                resolved_args = self._resolve_variables(step_args, state)
                
                # Get executor from context
                executor = self.context.get('executor')
                if not executor:
                    raise RuntimeError("No executor available in context. ChainTool requires runtime injection.")
                
                # Execute the tool
                result = executor(tool_name, resolved_args)
                
                # Store result in state
                state[step_id] = result
                executed_steps.append({
                    'step': i + 1,
                    'id': step_id,
                    'tool': tool_name,
                    'status': 'SUCCESS',
                    'result': result
                })
                
            except Exception as e:
                # Step failed - return detailed breakdown
                error_report = self._format_error_report(
                    failed_step=i + 1,
                    failed_step_id=step_id,
                    failed_tool=tool_name,
                    error=e,
                    executed_steps=executed_steps,
                    total_steps=len(steps)
                )
                return error_report
        
        # All steps succeeded - return formatted output
        return self._format_success_report(executed_steps, state)
    
    def _validate_dag(self, steps: List[Dict[str, Any]]) -> None:
        """
        Validate that the chain forms a Directed Acyclic Graph (DAG).
        
        Rules:
        - A step can only reference step IDs that appear before it in the list
        - No forward references allowed
        
        Args:
            steps: List of step definitions
            
        Raises:
            DAGViolationError: If validation fails
        """
        # Build set of valid step IDs seen so far
        seen_ids = set()
        
        for i, step in enumerate(steps):
            step_id = step['id']
            step_args = step['args']
            
            # Check for duplicate step IDs
            if step_id in seen_ids:
                raise DAGViolationError(
                    f"Duplicate step ID '{step_id}' at position {i + 1}"
                )
            
            # Extract all variable references from this step's arguments
            referenced_ids = self._extract_variable_refs(step_args)
            
            # Check that all referenced IDs have been seen (are from earlier steps)
            invalid_refs = referenced_ids - seen_ids
            
            if invalid_refs:
                raise DAGViolationError(
                    f"Step {i + 1} (id='{step_id}') references future/unknown step(s): {sorted(invalid_refs)}. "
                    f"Only steps that appear earlier in the chain can be referenced."
                )
            
            # Add this step ID to the seen set
            seen_ids.add(step_id)
    
    def _extract_variable_refs(self, obj: Any) -> Set[str]:
        """
        Recursively extract all ${step_id.key} or ${step_id} references from an object.
        
        Args:
            obj: Object to scan (dict, list, str, or primitive)
            
        Returns:
            Set of step IDs referenced
        """
        refs = set()
        
        if isinstance(obj, str):
            # Find all ${...} patterns
            pattern = r'\$\{([^.}]+)(?:\.[^}]+)?\}'
            matches = re.findall(pattern, obj)
            refs.update(matches)
        elif isinstance(obj, dict):
            for value in obj.values():
                refs.update(self._extract_variable_refs(value))
        elif isinstance(obj, list):
            for item in obj:
                refs.update(self._extract_variable_refs(item))
        
        return refs
    
    def _resolve_variables(self, obj: Any, state: Dict[str, Any]) -> Any:
        """
        Recursively resolve ${step_id.key} or ${step_id} references in an object.
        
        Args:
            obj: Object to resolve (dict, list, str, or primitive)
            state: Current state containing results from executed steps
            
        Returns:
            Object with all variables resolved
        """
        if isinstance(obj, str):
            # Replace all ${...} patterns
            def replacer(match):
                ref = match.group(1)
                # Parse step_id and optional key path
                parts = ref.split('.', 1)
                step_id = parts[0]
                
                if step_id not in state:
                    return f"<ERROR: step '{step_id}' not found>"
                
                value = state[step_id]
                
                # If there's a key path, try to traverse it
                if len(parts) > 1:
                    key_path = parts[1]
                    try:
                        # Try dict access
                        if isinstance(value, dict):
                            return str(value.get(key_path, f"<ERROR: key '{key_path}' not found>"))
                        # Try attribute access
                        elif hasattr(value, key_path):
                            return str(getattr(value, key_path))
                        # Try list/tuple index
                        elif isinstance(value, (list, tuple)) and key_path.isdigit():
                            idx = int(key_path)
                            if 0 <= idx < len(value):
                                return str(value[idx])
                            return f"<ERROR: index {idx} out of range>"
                        else:
                            return f"<ERROR: cannot access '{key_path}' on {type(value).__name__}>"
                    except Exception as e:
                        return f"<ERROR: {str(e)}>"
                
                # No key path - return the whole value as string
                return str(value)
            
            pattern = r'\$\{([^}]+)\}'
            return re.sub(pattern, replacer, obj)
        elif isinstance(obj, dict):
            return {k: self._resolve_variables(v, state) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_variables(item, state) for item in obj]
        else:
            # Primitive value - return as-is
            return obj
    
    def _format_error_report(
        self,
        failed_step: int,
        failed_step_id: str,
        failed_tool: str,
        error: Exception,
        executed_steps: List[Dict],
        total_steps: int
    ) -> str:
        """
        Format a detailed error report for a failed chain execution.
        
        Args:
            failed_step: Step number that failed (1-indexed)
            failed_step_id: ID of the failed step
            failed_tool: Name of the tool that failed
            error: The exception that occurred
            executed_steps: List of successfully executed steps
            total_steps: Total number of steps in the chain
            
        Returns:
            Formatted error report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("❌ CHAIN EXECUTION FAILED")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Failed at: Step {failed_step}/{total_steps} (id='{failed_step_id}')")
        lines.append(f"Tool: '{failed_tool}'")
        lines.append(f"Error: {str(error)}")
        lines.append("")
        
        if executed_steps:
            lines.append(f"✅ Successfully executed steps: {len(executed_steps)}/{total_steps}")
            lines.append("")
            for step_info in executed_steps:
                lines.append(f"  Step {step_info['step']}: {step_info['tool']} (id='{step_info['id']}') → SUCCESS")
                # Truncate result for readability
                result_str = str(step_info['result'])
                if len(result_str) > 100:
                    result_str = result_str[:100] + "..."
                lines.append(f"    Result: {result_str}")
            lines.append("")
        
        lines.append("💡 Suggestion:")
        lines.append(f"  Fix the '{failed_tool}' tool call or its arguments and try again.")
        lines.append(f"  The first {len(executed_steps)} step(s) completed successfully.")
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def _format_success_report(self, executed_steps: List[Dict], state: Dict[str, Any]) -> str:
        """
        Format a success report for a completed chain execution.
        
        Args:
            executed_steps: List of all executed steps
            state: Final state dictionary
            
        Returns:
            Formatted success report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("✅ CHAIN EXECUTION COMPLETED")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Total steps executed: {len(executed_steps)}")
        lines.append("")
        lines.append("Results:")
        lines.append("")
        
        for step_info in executed_steps:
            lines.append(f"  Step {step_info['step']}: {step_info['tool']} (id='{step_info['id']}')")
            # Truncate result for readability
            result_str = str(step_info['result'])
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            lines.append(f"    → {result_str}")
            lines.append("")
        
        lines.append("=" * 70)
        lines.append("")
        lines.append("Final State:")
        lines.append(json.dumps(state, indent=2, default=str))
        
        return "\n".join(lines)
