"""
WebAgent - Web Research Agent with ReAct Loop

Searches web and external documentation using the ReAct loop.
LLM decides which tools to call at each step.

Note:
    This agent is currently DISABLED by default. The system is testing a code-only
    approach using CodeAgent to build comprehensive understanding from source code
    and test files alone. To enable WebAgent, set `agents.web_enabled: true` in
    cf/configs/config.yaml. See cf/agents/supervisor.py for orchestration logic.
"""

from typing import Dict, Any, List, Optional
from cf.agents.base import BaseAgent
from cf.tools.registry import ToolRegistry


class WebAgent(BaseAgent):
    """
    Web research specialist.

    Uses the ReAct loop from BaseAgent where LLM decides which tools to call.
    Focuses on web search and external documentation retrieval.
    """

    agent_name = "web"

    # Tools available to WebAgent - focused on web search
    available_tools = [
        # Web Tools for external research
        'web_search',           # Search web for information
        'search_documentation', # Search for official documentation

        # LLM Tools for analysis
        'summarize_code',           # Summarize content
        'analyze_code_structure',   # Analyze structure of results
    ]

    def __init__(self, repo_path: str, config: Dict[str, Any],
                 tool_registry: Optional[ToolRegistry] = None):
        super().__init__(repo_path, config, tool_registry)

    def get_system_prompt(self) -> str:
        """System prompt for web research"""
        return """You are a web research specialist. Your job is to search the web for external information to answer questions.

Focus on:
- Finding relevant documentation
- Searching for best practices
- Looking up library/framework documentation
- Finding related discussions (Stack Overflow, GitHub issues)
- Getting up-to-date information about technologies

Process:
1. Start by searching the web for the main topic
2. Search for official documentation when relevant
3. Gather information from multiple sources if needed
4. When you have enough information, synthesize a comprehensive answer

Be efficient - focus on finding accurate, up-to-date information from reliable sources.
Prefer official documentation, Stack Overflow, and GitHub over random blogs."""
