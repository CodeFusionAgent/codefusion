"""System Access for CodeFusion Agent Computer Interface."""

import os
from pathlib import Path
from typing import Dict, Optional


class SystemAccess:
    """Loads environment variables from .env files and system environment."""

    def __init__(self, env_file_path: Optional[str] = None):
        self.env_file_path = env_file_path or ".env"
        self.env_vars: dict[str, str] = {}
        self._load_env_file()

    def _load_env_file(self) -> None:
        """Load environment variables from .env file."""
        env_path = Path(self.env_file_path)

        if not env_path.exists():
            print(f"No .env file found at {env_path}")
            return

        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        self.env_vars[key] = value
                        # Also set in os.environ for immediate use
                        os.environ[key] = value

            print(f"Loaded {len(self.env_vars)} environment variables from {env_path}")
        except Exception as e:
            print(f"Error loading .env file: {e}")

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable value."""
        # Check system environment first, then .env file
        return os.environ.get(key, self.env_vars.get(key, default))

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a specific service."""
        # Try multiple common patterns
        patterns = [
            f"{service.upper()}_API_KEY",
            f"{service.upper()}_KEY",
            f"{service}_API_KEY",
            f"{service}_KEY",
            "OPENAI_API_KEY",  # Common fallback
            "API_KEY",
        ]

        for pattern in patterns:
            value = self.get(pattern)
            if value:
                return value

        return None

    def get_llm_config(self) -> Dict[str, Optional[str]]:
        """Get LLM configuration from environment."""
        return {
            "api_key": self.get_api_key("openai")
            or self.get_api_key("anthropic")
            or self.get("LLM_API_KEY"),
            "base_url": self.get("OPENAI_BASE_URL") or self.get("LLM_BASE_URL"),
            "model": self.get("LLM_MODEL") or self.get("OPENAI_MODEL"),
        }

    def has_llm_config(self) -> bool:
        """Check if LLM configuration is available."""
        config = self.get_llm_config()
        return config["api_key"] is not None

    def list_available_keys(self) -> Dict[str, str]:
        """List all available environment variables (masking sensitive values)."""
        result = {}
        for key, value in self.env_vars.items():
            if any(
                sensitive in key.lower()
                for sensitive in ["key", "password", "token", "secret"]
            ):
                result[key] = f"{'*' * min(len(value), 8)}" if value else "None"
            else:
                result[key] = value
        return result
