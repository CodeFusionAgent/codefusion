"""
Configuration Utilities

Utilities for configuration management and merging.
"""

from typing import Dict, Any


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge two dictionaries.

    Args:
        base: Base configuration
        override: Override configuration (takes precedence)

    Returns:
        Merged dictionary

    Example:
        >>> base = {'a': {'b': 1, 'c': 2}, 'd': 3}
        >>> override = {'a': {'b': 10}, 'e': 4}
        >>> deep_merge(base, override)
        {'a': {'b': 10, 'c': 2}, 'd': 3, 'e': 4}
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result
