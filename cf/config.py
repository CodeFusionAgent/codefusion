"""Configuration management for CodeFusion."""

import json
import os
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
    
    # LLM settings
    llm: Dict[str, Any] = field(default_factory=lambda: {
        "model": "claude-3-sonnet-20240229",
        "api_key": "",
        "max_tokens": 1000,
        "temperature": 0.7,
        "provider": "anthropic"
    })
    
    # Error recovery settings
    error_recovery: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "max_retries": 3,
        "circuit_breaker_threshold": 5,
        "loop_detection_window": 10
    })
    
    # Logging settings
    logging: Dict[str, Any] = field(default_factory=lambda: {
        "enable_execution_logs": False,  # Main toggle for execution flow logging
        "enable_llm_logs": False,        # LLM API call logging
        "enable_tool_logs": False,       # Tool execution logging
        "enable_agent_logs": False,      # Agent reasoning/action logging
        "log_level": "INFO",             # Standard logging level
        "show_progress": True            # Show progress indicators
    })
    
    def __post_init__(self):
        """Load environment overrides after initialization."""
        self._load_env_overrides()

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
            "llm": self.llm,
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
        # LLM environment variable overrides
        if os.getenv('CF_LLM_MODEL'):
            self.llm['model'] = os.getenv('CF_LLM_MODEL')
        
        if os.getenv('CF_LLM_API_KEY'):
            self.llm['api_key'] = os.getenv('CF_LLM_API_KEY')
        
        # Also check standard API key environment variables
        if not self.llm['api_key']:
            if os.getenv('ANTHROPIC_API_KEY'):
                self.llm['api_key'] = os.getenv('ANTHROPIC_API_KEY')
                self.llm['provider'] = 'anthropic'
            elif os.getenv('OPENAI_API_KEY'):
                self.llm['api_key'] = os.getenv('OPENAI_API_KEY')
                self.llm['provider'] = 'openai'
        
        # Temperature and max_tokens overrides
        if os.getenv('CF_LLM_TEMPERATURE'):
            try:
                self.llm['temperature'] = float(os.getenv('CF_LLM_TEMPERATURE'))
            except ValueError:
                pass
        
        if os.getenv('CF_LLM_MAX_TOKENS'):
            try:
                self.llm['max_tokens'] = int(os.getenv('CF_LLM_MAX_TOKENS'))
            except ValueError:
                pass
        
        # Logging environment overrides
        if os.getenv('CF_ENABLE_LOGS'):
            enable_logs = os.getenv('CF_ENABLE_LOGS').lower() in ['true', '1', 'yes', 'on']
            self.logging['enable_execution_logs'] = enable_logs
            self.logging['enable_llm_logs'] = enable_logs
            self.logging['enable_tool_logs'] = enable_logs
            self.logging['enable_agent_logs'] = enable_logs
        
        # Individual logging toggles
        if os.getenv('CF_ENABLE_EXECUTION_LOGS'):
            self.logging['enable_execution_logs'] = os.getenv('CF_ENABLE_EXECUTION_LOGS').lower() in ['true', '1', 'yes', 'on']
        
        if os.getenv('CF_ENABLE_LLM_LOGS'):
            self.logging['enable_llm_logs'] = os.getenv('CF_ENABLE_LLM_LOGS').lower() in ['true', '1', 'yes', 'on']
        
        if os.getenv('CF_ENABLE_TOOL_LOGS'):
            self.logging['enable_tool_logs'] = os.getenv('CF_ENABLE_TOOL_LOGS').lower() in ['true', '1', 'yes', 'on']
        
        if os.getenv('CF_ENABLE_AGENT_LOGS'):
            self.logging['enable_agent_logs'] = os.getenv('CF_ENABLE_AGENT_LOGS').lower() in ['true', '1', 'yes', 'on']
        
        if os.getenv('CF_SHOW_PROGRESS'):
            self.logging['show_progress'] = os.getenv('CF_SHOW_PROGRESS').lower() in ['true', '1', 'yes', 'on']
