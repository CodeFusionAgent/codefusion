"""
DocsAgent - Documentation Analysis Agent with ReAct Loop

Analyzes documentation files (README, docs/, etc.) using the ReAct loop.
LLM decides which tools to call at each step.

Note:
    This agent is currently DISABLED by default. The system is testing a code-only
    approach using CodeAgent to build comprehensive understanding from source code
    and test files alone. To enable DocsAgent, set `agents.docs_enabled: true` in
    cf/configs/config.yaml. See cf/agents/supervisor.py for orchestration logic.
"""

from typing import Dict, Any, List, Optional
from cf.agents.base import BaseAgent
from cf.tools.registry import ToolRegistry


class DocsAgent(BaseAgent):
    """
    Documentation analysis specialist.

    Uses the ReAct loop from BaseAgent where LLM decides which tools to call.
    Focuses on documentation files like README, docs/, guides, tutorials, etc.
    """

    agent_name = "docs"

    # Tools available to DocsAgent - focused on file reading
    available_tools = [
        # File Tools for reading documentation
        'scan_directory',       # Find documentation files
        'list_files',           # List files matching pattern
        'read_file',            # Read documentation content
        'search_files',         # Search for terms in documentation
        'get_file_info',        # Get file metadata
        'head_file',            # Read first N lines
        'tail_file',            # Read last N lines
        'cat_file',             # Read entire file

        # LLM Tools for analysis
        'summarize_code',           # Summarize documentation content
        'analyze_code_structure',   # Analyze structure of docs
    ]

    def __init__(self, repo_path: str, config: Dict[str, Any],
                 tool_registry: Optional[ToolRegistry] = None):
        super().__init__(repo_path, config, tool_registry)

    def get_system_prompt(self) -> str:
        """System prompt for documentation analysis"""
        return """You are a documentation analysis specialist. Your job is to analyze documentation files to answer questions.

Focus on:
- README files (README.md, README.txt, README.rst)
- docs/ directories
- Guides and tutorials
- API documentation
- Configuration documentation
- Markdown files (.md)
- Text documentation (.txt, .rst)

Process:
1. Start by scanning for documentation files (look for README, docs/, guides)
2. Search for terms related to the question
3. Read the most relevant documentation files
4. Focus on README files first - they often contain key information
5. When you have enough information, synthesize a comprehensive answer

Be efficient - focus on documentation files, not source code files.
Look for patterns like: docs/, README, GUIDE, TUTORIAL, MANUAL, HELP, GETTING_STARTED."""
