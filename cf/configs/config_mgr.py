"""
Configuration Manager for CodeFusion

Simple, clean configuration management with validation.
Includes schema validation to prevent runtime errors.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass


# ============================================================================
# Configuration Schema Validation (merged from config_schema.py)
# ============================================================================

@dataclass
class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    field: str
    message: str

    def __str__(self):
        return f"Config validation error in '{self.field}': {self.message}"


class ConfigSchema:
    """Validates configuration against expected schema"""

    @staticmethod
    def validate(config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration structure and values.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate top-level structure
        required_sections = ['agents', 'llm']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: '{section}'")

        if errors:
            return errors  # Return early if top-level structure invalid

        # Validate agents section
        errors.extend(ConfigSchema._validate_agents(config.get('agents', {})))

        # Validate LLM section
        errors.extend(ConfigSchema._validate_llm(config.get('llm', {})))

        return errors

    @staticmethod
    def _validate_agents(agents: Dict[str, Any]) -> List[str]:
        """Validate agents configuration section"""
        errors = []

        # Check required numeric fields
        numeric_fields = {
            'max_iterations': (1, 100),
            'timeout': (60, 3600),
            'max_files_to_analyze': (1, 200),
        }

        for field, (min_val, max_val) in numeric_fields.items():
            if field in agents:
                value = agents[field]
                if not isinstance(value, (int, float)):
                    errors.append(f"agents.{field} must be numeric, got {type(value).__name__}")
                elif value < min_val or value > max_val:
                    errors.append(f"agents.{field} must be between {min_val} and {max_val}, got {value}")

        # Validate discovery section
        if 'discovery' in agents:
            discovery = agents['discovery']
            if 'prioritize_test_files' in discovery:
                if not isinstance(discovery['prioritize_test_files'], bool):
                    errors.append("agents.discovery.prioritize_test_files must be boolean")

            if 'test_file_boost_factor' in discovery:
                boost = discovery['test_file_boost_factor']
                if not isinstance(boost, (int, float)):
                    errors.append("agents.discovery.test_file_boost_factor must be numeric")
                elif boost < 0 or boost > 1:
                    errors.append(f"agents.discovery.test_file_boost_factor must be between 0 and 1, got {boost}")

        # Validate synthesis section
        if 'synthesis' in agents:
            synthesis = agents['synthesis']
            if 'adaptive_targets' in synthesis:
                if not isinstance(synthesis['adaptive_targets'], bool):
                    errors.append("agents.synthesis.adaptive_targets must be boolean")

            if 'adaptive_scale_factor' in synthesis:
                factor = synthesis['adaptive_scale_factor']
                if not isinstance(factor, (int, float)):
                    errors.append("agents.synthesis.adaptive_scale_factor must be numeric")
                elif factor < 0 or factor > 1:
                    errors.append(f"agents.synthesis.adaptive_scale_factor must be between 0 and 1, got {factor}")

        # Validate synthesis_retries section
        if 'synthesis_retries' in agents:
            retries = agents['synthesis_retries']
            if 'max_attempts' in retries:
                attempts = retries['max_attempts']
                if not isinstance(attempts, int):
                    errors.append("agents.synthesis_retries.max_attempts must be integer")
                elif attempts < 0 or attempts > 5:
                    errors.append(f"agents.synthesis_retries.max_attempts must be between 0 and 5, got {attempts}")

        # Validate thresholds section
        if 'thresholds' in agents:
            thresholds = agents['thresholds']
            threshold_fields = [
                'high_confidence', 'medium_confidence', 'low_confidence',
                'min_path_accuracy', 'min_relevance_score'
            ]
            for field in threshold_fields:
                if field in thresholds:
                    value = thresholds[field]
                    if not isinstance(value, (int, float)):
                        errors.append(f"agents.thresholds.{field} must be numeric")
                    elif value < 0 or value > 1:
                        errors.append(f"agents.thresholds.{field} must be between 0 and 1, got {value}")

        return errors

    @staticmethod
    def _validate_llm(llm: Dict[str, Any]) -> List[str]:
        """Validate LLM configuration section"""
        errors = []

        # Model is optional (can be set via env var)
        if 'model' in llm and llm['model'] is not None:
            if not isinstance(llm['model'], str):
                errors.append(f"llm.model must be string, got {type(llm['model']).__name__}")

        # Temperature validation
        if 'temperature' in llm:
            temp = llm['temperature']
            if not isinstance(temp, (int, float)):
                errors.append(f"llm.temperature must be numeric, got {type(temp).__name__}")
            elif temp < 0 or temp > 2:
                errors.append(f"llm.temperature must be between 0 and 2, got {temp}")

        # Max tokens validation
        if 'max_tokens' in llm:
            tokens = llm['max_tokens']
            if not isinstance(tokens, int):
                errors.append(f"llm.max_tokens must be integer, got {type(tokens).__name__}")
            elif tokens < 1 or tokens > 100000:
                errors.append(f"llm.max_tokens must be between 1 and 100000, got {tokens}")

        return errors

    @staticmethod
    def validate_and_raise(config: Dict[str, Any]) -> None:
        """
        Validate configuration and raise exception if invalid.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ConfigValidationError: If configuration is invalid
        """
        errors = ConfigSchema.validate(config)
        if errors:
            error_msg = "Configuration validation failed:\n  - " + "\n  - ".join(errors)
            raise ConfigValidationError("config", error_msg)


# ============================================================================
# Configuration Manager
# ============================================================================


class ConfigManager:
    """
    Configuration manager for CodeFusion.

    Loads configuration from a single config.yaml file.
    Falls back to sensible defaults if config file is not found.
    """

    def __init__(self, config_path: str = "cf/configs/config.yaml"):
        self.config_path = Path(config_path)
        self.config_dir = self.config_path.parent
        self._config = None
        self._load_config()

    def _load_config(self):
        """Load configuration from config.yaml and validate it"""
        try:
            if self.config_path.exists():
                # Load single config.yaml file
                with open(self.config_path, 'r') as f:
                    self._config = yaml.safe_load(f)
                print(f"✅ [CONFIG] Loaded configuration from {self.config_path}")
            else:
                # Use default config if file doesn't exist
                self._config = self._get_default_config()
                print(f"⚠️  [CONFIG] Config file not found, using defaults")

            # Validate configuration
            self._validate_config()

        except ConfigValidationError as e:
            print(f"❌ [CONFIG] Configuration validation failed: {e}")
            raise
        except Exception as e:
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            self._config = self._get_default_config()

    def _validate_config(self):
        """Validate loaded configuration against schema"""
        errors = ConfigSchema.validate(self._config)
        if errors:
            print(f"⚠️  [CONFIG] Found {len(errors)} validation errors:")
            for error in errors:
                print(f"   - {error}")
            raise ConfigValidationError("config", f"Found {len(errors)} validation errors")
        else:
            print(f"✅ [CONFIG] Configuration validated successfully")

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
                # No hardcoded exclusions - track all files, let LLM filter by relevance
                'excluded_dirs': [],
                'excluded_extensions': []
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
