"""Configuration management for CodeFusion."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class CfConfig:
    """Configuration class for CodeFusion that loads from YAML/JSON files."""

    # Core settings
    repo_path: Optional[str] = None
    output_dir: str = "./output"

    # Simple exploration settings
    max_file_size: int = 1024 * 1024  # 1MB
    excluded_dirs: list = field(
        default_factory=lambda: [".git", "__pycache__", "node_modules", ".venv", "venv"]
    )
    excluded_extensions: list = field(
        default_factory=lambda: [".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".env"]
    )
    max_exploration_depth: int = 5
    
    # Multi-agent settings
    agents: Dict[str, Any] = field(default_factory=lambda: {
        "supervisor": {"enabled": True, "max_agents": 4, "timeout": 300},
        "documentation": {"enabled": True, "file_types": [".md", ".rst", ".txt", ".adoc"], "max_files": 50},
        "codebase": {"enabled": True, "languages": ["python", "javascript", "typescript", "java", "go", "rust", "c", "cpp"], "max_files": 200},
        "architecture": {"enabled": True, "diagram_types": ["mermaid", "plantuml", "graphviz"], "max_components": 100},
        "summary": {"enabled": True, "max_sections": 10, "cheat_sheet_format": "markdown"}
    })
    
    # Error recovery settings
    error_recovery: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "max_retries": 3,
        "circuit_breaker_threshold": 5,
        "loop_detection_window": 10
    })

    @classmethod
    def from_file(cls, config_path: str) -> "CfConfig":
        """Load configuration from a YAML or JSON file."""
        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            if path.suffix.lower() in [".yaml", ".yml"]:
                data = yaml.safe_load(f)
            elif path.suffix.lower() == ".json":
                data = json.load(f)
            else:
                raise ValueError(
                    f"Unsupported configuration file format: {path.suffix}"
                )

        # Load environment variables to override config
        config = cls(**data)
        config._load_env_overrides()
        return config

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CfConfig":
        """Create configuration from dictionary."""
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "repo_path": self.repo_path,
            "output_dir": self.output_dir,
            "max_file_size": self.max_file_size,
            "excluded_dirs": self.excluded_dirs,
            "excluded_extensions": self.excluded_extensions,
            "max_exploration_depth": self.max_exploration_depth,
            "agents": self.agents,
            "error_recovery": self.error_recovery,
        }

    def save(self, config_path: str) -> None:
        """Save configuration to a YAML or JSON file."""
        path = Path(config_path)
        data = self.to_dict()

        with open(path, "w", encoding="utf-8") as f:
            if path.suffix.lower() in [".yaml", ".yml"]:
                yaml.dump(data, f, default_flow_style=False, indent=2)
            elif path.suffix.lower() == ".json":
                json.dump(data, f, indent=2)
            else:
                raise ValueError(
                    f"Unsupported configuration file format: {path.suffix}"
                )

    def validate(self) -> None:
        """Validate configuration settings."""
        if self.max_exploration_depth < 1:
            raise ValueError("max_exploration_depth must be at least 1")

        if self.max_file_size < 1:
            raise ValueError("max_file_size must be at least 1")

    def _load_env_overrides(self) -> None:
        """Load environment variable overrides."""
        # Simple configuration - no environment overrides needed for basic exploration
        pass
