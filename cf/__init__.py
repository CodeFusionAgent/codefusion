"""CodeFusion: Clean, LLM-driven code analysis framework."""

from cf.configs.config_mgr import ConfigManager
from cf.agents.supervisor import SupervisorAgent
from cf.agents.base import BaseAgent
from cf.agents.code import CodeAgent
from cf.agents.docs import DocsAgent
from cf.agents.web import WebAgent
from cf.llm.client import LLMClient
from cf.tools.registry import ToolRegistry

__version__ = "0.1.0"
__author__ = "CodeFusion Team"
__description__ = (
    "Clean LLM-driven framework for intelligent code analysis. "
    "Multi-agent system with function calling loops for comprehensive codebase understanding."
)

__all__ = [
    "ConfigManager",
    "SupervisorAgent",
    "BaseAgent",
    "CodeAgent",
    "DocsAgent", 
    "WebAgent",
    "LLMClient",
    "ToolRegistry",
]