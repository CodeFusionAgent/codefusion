"""
Configuration Manager for CodeFusion

Simple, clean configuration management.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigManager:
    """Simple configuration manager"""
    
    def __init__(self, config_path: str = "cf/configs/config.yaml"):
        self.config_path = Path(config_path)
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = yaml.safe_load(f)
            else:
                # Use default config if file doesn't exist
                self._config = self._get_default_config()
        except Exception as e:
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'llm': {
                'model': 'gpt-4o',
                'api_key': os.environ.get('OPENAI_API_KEY'),  # Set via environment variable or config file
                'max_tokens': 2000,
                'temperature': 0.7
            },
            'agents': {
                'max_iterations': 10,
                'timeout': 300
            },
            'cache': {
                'enabled': True,
                'ttl': 3600
            },
            'trace': {
                'enabled': True,
                'output_dir': 'cf_trace'
            },
            'repo': {
                'max_files': 1000,
                'max_file_size': 1048576,  # 1MB
                'excluded_dirs': ['.git', '__pycache__', 'node_modules', '.venv'],
                'excluded_extensions': ['.pyc', '.pyo', '.so', '.dll']
            }
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return self._config.copy()
    
    def get(self, key: str, default=None):
        """Get configuration value by key (dot notation supported)"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def reload(self):
        """Reload configuration from file"""
        self._load_config()
