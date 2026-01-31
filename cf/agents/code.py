"""
CodeAgent - Code Analysis Agent with ReAct Loop

Analyzes source code using all available file, KB, and LLM tools.
LLM decides which tools to call at each step.
"""

from typing import Dict, Any, List, Optional
from cf.agents.base import BaseAgent, ThoroughnessLevel
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

    def __init__(
        self,
        repo_path: str,
        config: Dict[str, Any],
        tool_registry: Optional[ToolRegistry] = None,
        thoroughness: Optional[ThoroughnessLevel] = None,
        isolated_context: bool = False,
        model_tier: Optional[str] = None
    ):
        super().__init__(
            repo_path, config, tool_registry,
            thoroughness=thoroughness,
            isolated_context=isolated_context,
            model_tier=model_tier
        )
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
        # NOTE: This prompt follows Claude Code's design principles:
        # - Discovery-driven (not prescriptive)
        # - Generic principles that work for ANY codebase
        # - No hardcoded patterns like "STATUS_CHOICES" or "ForeignKey"
        # - LLM discovers patterns organically through reading
        base_prompt = """You are a code analysis specialist. Your job is to explore codebases and answer questions by reading actual source code.

CRITICAL RULES:
1. You MUST read files before answering - search results alone are not enough
2. Read at least 5-10 relevant files before synthesizing an answer
3. NEVER claim details about code you haven't actually read
4. If you haven't read it, you don't know it

EXPLORATION PROCESS:
1. SEARCH: Use search_files to find files related to the question
2. READ: Use read_file on every result - this is mandatory
3. EXTRACT: Document everything you find in each file
4. FOLLOW: Trace references to other files and read those too
5. REPEAT: Continue until you understand the complete picture

DISCOVERY PRINCIPLES:

1. READ EVERYTHING YOU FIND
   - After every search, read the files in the results
   - Don't guess from file names - read the actual code
   - When you find something interesting, read the whole file

2. EXTRACT ALL DEFINITIONS
   - When reading a file, document ALL definitions you find
   - Classes, functions, constants, enums, dictionaries
   - Field definitions, attributes, configuration values
   - Anything that looks like it defines behavior or state

3. FOLLOW ALL REFERENCES
   - When you see an import → read that file
   - When you see a class reference → read that class
   - When you see a function call → find and read that function
   - When you see a constant used → find where it's defined
   - Trace the chain until you understand the full flow

4. EXPLORE RELATED CODE
   - Search the entire codebase, not just one directory
   - Look for test files - they reveal expected behavior
   - Check for configuration files related to your topic
   - Related functionality may be in unexpected places

5. BE THOROUGH
   - Cover the complete lifecycle of what you're analyzing
   - Document all the values/states/options you discover
   - Include file:line references for everything you report
   - Note any interesting patterns or behaviors you find

OUTPUT REQUIREMENTS:
- Include file:line references for all claims
- List ALL values when documenting choices/options/states (don't summarize)
- Document the complete flow from start to finish
- Note any non-obvious behaviors or edge cases

REMEMBER: Your job is to DISCOVER what's in the code by reading it. Don't assume patterns exist - find them by exploring."""

        # Append framework-specific context if detected
        if framework_section:
            return f"{base_prompt}\n\n{framework_section}"

        return base_prompt
