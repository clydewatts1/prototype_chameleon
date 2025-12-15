"""
Utility functions for the Chameleon MCP Server.

This module contains generic helper functions used throughout the codebase.
"""

import hashlib


def compute_hash(code: str) -> str:
    """
    Compute SHA-256 hash of code.
    
    Args:
        code: The code string to hash
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()
