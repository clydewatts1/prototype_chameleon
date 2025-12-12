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
        db_session: SQLModel Session for database access
        context: Dictionary containing execution context (persona, etc.)
    """
    
    def __init__(self, db_session, context: Dict[str, Any]):
        """
        Initialize the tool with database session and context.
        
        Args:
            db_session: SQLModel Session for database access
            context: Dictionary containing execution context information
        """
        self.db_session = db_session
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
