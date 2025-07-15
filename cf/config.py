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

    # LLM settings
    llm_model: str = "gpt-3.5-turbo"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None

    # Knowledge base settings
    kb_type: str = "text"  # "text", "neo4j", or "vector"
    kb_path: str = "./kb"
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None
    embedding_model: str = "all-MiniLM-L6-v2"

    # Indexing settings
    max_file_size: int = 1024 * 1024  # 1MB
    excluded_dirs: list = field(
        default_factory=lambda: [".git", "__pycache__", "node_modules", ".venv", "venv"]
    )
    excluded_extensions: list = field(
        default_factory=lambda: [".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".env"]
    )

    # Exploration settings
    exploration_strategy: str = "react"  # "react", "plan_act", "sense_act"
    max_exploration_depth: int = 5

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
            "llm_model": self.llm_model,
            "llm_api_key": self.llm_api_key,
            "llm_base_url": self.llm_base_url,
            "kb_type": self.kb_type,
            "kb_path": self.kb_path,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "neo4j_password": self.neo4j_password,
            "embedding_model": self.embedding_model,
            "max_file_size": self.max_file_size,
            "excluded_dirs": self.excluded_dirs,
            "excluded_extensions": self.excluded_extensions,
            "exploration_strategy": self.exploration_strategy,
            "max_exploration_depth": self.max_exploration_depth,
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
        if self.kb_type not in ["text", "neo4j", "vector"]:
            raise ValueError(f"Invalid kb_type: {self.kb_type}")

        if self.exploration_strategy not in ["react", "plan_act", "sense_act"]:
            raise ValueError(
                f"Invalid exploration_strategy: {self.exploration_strategy}"
            )

        if self.kb_type == "neo4j":
            if not all([self.neo4j_uri, self.neo4j_user, self.neo4j_password]):
                raise ValueError("Neo4j configuration requires uri, user, and password")

        if self.max_exploration_depth < 1:
            raise ValueError("max_exploration_depth must be at least 1")

        if self.max_file_size < 1:
            raise ValueError("max_file_size must be at least 1")

    def _load_env_overrides(self) -> None:
        """Load environment variable overrides."""
        from .aci.system_access import SystemAccess

        system_access = SystemAccess()

        # Override LLM configuration from environment
        llm_config = system_access.get_llm_config()
        if llm_config["api_key"]:
            self.llm_api_key = llm_config["api_key"]
        if llm_config["base_url"]:
            self.llm_base_url = llm_config["base_url"]
        if llm_config["model"]:
            self.llm_model = llm_config["model"]

        # Override Neo4j configuration from environment
        if system_access.get("NEO4J_URI"):
            self.neo4j_uri = system_access.get("NEO4J_URI")
        if system_access.get("NEO4J_USER"):
            self.neo4j_user = system_access.get("NEO4J_USER")
        if system_access.get("NEO4J_PASSWORD"):
            self.neo4j_password = system_access.get("NEO4J_PASSWORD")
