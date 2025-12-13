"""
CodeAgent - Code Analysis Agent with ReAct Loop

Analyzes source code using all available file, KB, and LLM tools.
LLM decides which tools to call at each step.
"""

from typing import Dict, Any, List, Optional
from cf.agents.base import BaseAgent
from cf.tools.registry import ToolRegistry
from cf.agents.framework_detector import FrameworkDetector, FrameworkContext


class CodeAgent(BaseAgent):
    """
    Code analysis specialist with access to all file, KB, and LLM tools.

    This is the primary agent for analyzing source code. It uses the ReAct
    loop from BaseAgent where LLM decides which tools to call.
    """

    agent_name = "code"

    # All tools available to CodeAgent
    available_tools = [
        # File Tools (12)
        'scan_directory',       # Recursively scan directory structure
        'list_files',           # List files matching pattern
        'read_file',            # Read file contents
        'search_files',         # Search for pattern across files (grep)
        'get_file_info',        # Get file metadata
        'head_file',            # Read first N lines
        'tail_file',            # Read last N lines
        'cat_file',             # Read entire file
        'word_count',           # Count lines, words, chars
        'regex_replace',        # Preview/apply regex substitution
        'get_file_stat',        # Comprehensive file statistics
        'bash_exec',            # Execute whitelisted shell commands

        # KB Tools (8) - with grep/AST fallbacks when KB unavailable
        'find_callers',             # Find functions that call a function
        'find_callees',             # Find functions called by a function
        'find_usages',              # Find all usages of a symbol
        'search_by_semantics',      # Search code by semantic meaning
        'search_by_functionality',  # Find code implementing functionality
        'find_dependencies',        # Find what a module/function depends on
        'find_files_for_question',  # Find relevant files for a question
        'find_related_tests',       # Find test files related to source files

        # LLM Tools (5)
        'analyze_code_structure',   # Analyze code architecture using LLM
        'extract_functions',        # Extract function signatures and docs
        'extract_classes',          # Extract class definitions and methods
        'detect_patterns',          # Detect design/architectural patterns
        'summarize_code',           # Generate code summary
    ]

    def __init__(self, repo_path: str, config: Dict[str, Any],
                 tool_registry: Optional[ToolRegistry] = None):
        super().__init__(repo_path, config, tool_registry)
        self._framework_context: Optional[FrameworkContext] = None
        self._framework_detector: Optional[FrameworkDetector] = None

    def _get_framework_context(self) -> FrameworkContext:
        """Get or detect framework context for this repository."""
        if self._framework_context is not None:
            return self._framework_context

        try:
            if self._framework_detector is None:
                self._framework_detector = FrameworkDetector(
                    repo_path=self.repo_path,
                    llm_callback=self._llm_callback_for_detection
                )
            self._framework_context = self._framework_detector.detect()
        except Exception as e:
            self.logger.debug(f"Framework detection failed: {e}")
            self._framework_context = FrameworkContext()

        return self._framework_context

    def _llm_callback_for_detection(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """LLM callback wrapper for framework detection."""
        try:
            return self.llm.generate(prompt=prompt, system_prompt=system_prompt)
        except Exception as e:
            return {'success': False, 'error': str(e), 'content': ''}

    def get_system_prompt(self) -> str:
        """System prompt for code analysis with dynamic framework context."""
        # Get framework-specific context (cached after first detection)
        framework_context = self._get_framework_context()
        framework_section = framework_context.to_prompt_section()

        # Build the complete prompt with generic base + dynamic framework context
        base_prompt = """You are a code analysis specialist. Your job is to analyze source code to answer questions about how the codebase works.

Key capabilities:
- Scan directories to understand project structure
- Read and analyze source code files
- Search for patterns and specific code
- Find function callers, callees, and usages
- Analyze dependencies and code flow
- Detect architectural patterns

Process:
1. Start by scanning the directory or searching for relevant files
2. Read specific files that seem relevant to the question
3. Use KB tools to trace code flow (find_callers, find_callees, etc.)
4. Analyze code structure and patterns as needed
5. When you have enough information, synthesize a comprehensive answer

IMPORTANT - Import Following Strategy:
When you read a file, PAY ATTENTION TO ITS IMPORTS. Imports reveal:
- Related modules you should also read (from app.models import X -> read models.py)
- External dependencies that define behavior
- Constants and configs imported from other files
If a file imports STATUS constants, MAPPING dicts, or utility functions, READ THOSE SOURCE FILES
to understand the actual values and behavior.

IMPORTANT - Look for Constants and Configurations:
- Look for UPPERCASE variables (STATUS_PENDING, APPLICATION_STATUS_MAPPING, etc.)
- These often define state machines, workflows, and business rules
- When you see a constant used but not defined, search for where it's defined

Be strategic and efficient - don't read files that aren't relevant to the question.
Focus on understanding how components work together to answer the user's question."""

        # Append framework-specific context if detected
        if framework_section:
            return f"{base_prompt}\n\n{framework_section}"

        return base_prompt
