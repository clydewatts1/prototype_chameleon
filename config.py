"""
Configuration module for Chameleon MCP Server.

Loads configuration from YAML file with sensible defaults.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any


def get_default_config() -> Dict[str, Any]:
    """
    Return default configuration values.
    
    Returns:
        Dictionary with default configuration
    """
    return {
        'server': {
            'transport': 'stdio',
            'host': '0.0.0.0',
            'port': 8000,
            'log_level': 'INFO',
            'logs_dir': 'logs'
        },
        'database': {
            'url': 'sqlite:///chameleon.db'
        }
    }


def load_config() -> Dict[str, Any]:
    """
    Load configuration from YAML file or return defaults.
    
    Looks for config file at ~/.chameleon/config/config.yaml.
    If file doesn't exist, returns default configuration.
    
    Returns:
        Dictionary with configuration values
    """
    # Get default configuration
    config = get_default_config()
    
    # Construct config file path
    config_path = Path(os.path.expanduser('~/.chameleon/config/config.yaml'))
    
    # If config file doesn't exist, return defaults
    if not config_path.exists():
        return config
    
    # Try to load YAML file
    try:
        import yaml
        
        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        # Merge YAML config with defaults (YAML values override defaults)
        if yaml_config:
            # Update server settings
            if 'server' in yaml_config:
                config['server'].update(yaml_config['server'])
            
            # Update database settings
            if 'database' in yaml_config:
                config['database'].update(yaml_config['database'])
        
        return config
    
    except ImportError:
        # PyYAML not installed, return defaults
        print("Warning: PyYAML not installed. Using default configuration.", file=sys.stderr)
        return config
    
    except Exception as e:
        # Error loading config file, return defaults
        print(f"Warning: Error loading config file: {e}. Using default configuration.", file=sys.stderr)
        return config
