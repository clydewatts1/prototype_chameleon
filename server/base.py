"""
Base classes for the Chameleon MCP Server plugin architecture.

This module defines the abstract base class that all dynamic tools must inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class ChameleonTool(ABC):
    """
    Abstract base class for all Chameleon tools.
    
    All tools stored in CodeVault with code_type='python' must define a class
    that inherits from this base class.
    
    Attributes:
        meta_session: SQLModel Session for metadata database access (tools, logs, resources)
        data_session: SQLModel Session for data database access (business data) - may be None
        db_session: Legacy alias for meta_session (for backward compatibility)
        context: Dictionary containing execution context (persona, etc.)
    """
    
    def __init__(self, meta_session, context: Dict[str, Any], data_session=None):
        """
        Initialize the tool with database sessions and context.
        
        Args:
            meta_session: SQLModel Session for metadata database access
            context: Dictionary containing execution context information
            data_session: SQLModel Session for data database access (optional, may be None)
        """
        self.meta_session = meta_session
        self.data_session = data_session
        # Legacy alias for backward compatibility
        self.db_session = meta_session
        self.context = context
    
    @abstractmethod
    def run(self, arguments: Dict[str, Any]) -> Any:
        """
        Execute the tool with the provided arguments.
        
        This method must be implemented by all subclasses.
        
        Args:
            arguments: Dictionary of arguments passed to the tool
            
        Returns:
            The result of the tool execution
        """
        pass
    
    def log(self, msg: str) -> None:
        """
        Log a message (standardized output helper).
        
        Args:
            msg: The message to log
        """
        print(f"[ChameleonTool] {msg}")

    def complete(self, argument: str, value: str) -> list[str]:
        """
        Provide completion suggestions for a given argument.

        Subclasses can override to supply context-aware completions.
        Defaults to no suggestions.

        Args:
            argument: Argument name being completed
            value: Current value/prefix typed by the user

        Returns:
            List of suggestion strings
        """
        return []
