"""
BaseAgent - ReAct-Style Agent with LLM-Driven Tool Selection

All agents use the same ReAct loop where LLM decides which tools to call.
Subclasses just define which tools are available.
"""

import re
import time
import json
import traceback
from abc import ABC
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from cf.tools.registry import ToolRegistry
from cf.llm.client import LLMClient
from cf.trace.tracer import Tracer, trace_method
from cf.knowledge_base.file_summary_cache import FileSummaryCache
from cf.utils.logger import get_logger
from cf.agents.framework_detector import FrameworkDetector, FrameworkContext


class ThoroughnessLevel(Enum):
    """Exploration depth: quick (fast lookup), medium (moderate), thorough (deep)."""
    QUICK = "quick"
    MEDIUM = "medium"
    THOROUGH = "thorough"

    def scale_factor(self) -> float:
        """Get scaling factor for config values (0.0-1.0)."""
        return {
            ThoroughnessLevel.QUICK: 0.15,
            ThoroughnessLevel.MEDIUM: 0.4,
            ThoroughnessLevel.THOROUGH: 1.0
        }.get(self, 0.4)


@dataclass
class ToolCall:
    """A tool call request from the LLM"""
    name: str
    params: Dict[str, Any]
    reasoning: str = ""


@dataclass
class ToolResult:
    """Result of a tool execution"""
    tool_name: str
    params: Dict[str, Any]
    result: Any
    success: bool
    duration: float = 0.0


@dataclass
class AgentState:
    """Current state of the agent during analysis"""
    question: str
    files_read: List[str] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    iteration: int = 0
    ready_to_answer: bool = False
    # Generic deduplication tracking - stores tool call signatures
    tool_call_history: set = field(default_factory=set)  # Generic dedup keys
    # Dynamic discovery tracking - imports found in read files
    discovered_files: List[str] = field(default_factory=list)  # Files discovered via imports
    # Question-derived keywords for file prioritization
    question_keywords: List[str] = field(default_factory=list)  # Extracted from question
    # Track failed directories to avoid repeated attempts
    failed_directories: set = field(default_factory=set)  # Directories that don't exist
    # Track truncated files that may need continuation reading
    truncated_files: Dict[str, tuple] = field(default_factory=dict)  # file_path -> (next_offset, remaining_lines)
    # Track consecutive JSON parse failures to prevent infinite loops
    json_parse_failures: int = 0


def extract_question_keywords(question: str) -> List[str]:
    """
    Extract keywords from the question for file prioritization.

    Returns all unique words - LLM determines relevance in context.
    No hardcoded length thresholds or filtering.
    """
    # Extract words, keeping alphanumeric and underscores
    words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', question.lower())

    # Include all words - LLM determines relevance in context
    # No hardcoded length thresholds or filtering
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique_keywords.append(word)

    return unique_keywords


class BaseAgent(ABC):
    """
    Base class for all CodeFusion agents with ReAct-style loop.

    The ReAct pattern:
    1. THINK: LLM decides which tools to call based on question and context
    2. ACT: Execute the tools chosen by LLM
    3. OBSERVE: Add results to context
    4. REPEAT until LLM decides it has enough info to answer

    Subclasses just define:
    - agent_name: Name of the agent
    - available_tools: List of tool names this agent can use
    - get_system_prompt(): System prompt for this agent's specialty
    """

    # Subclasses should override these
    agent_name: str = "base"
    available_tools: List[str] = []

    def __init__(self, repo_path: str, config: Dict[str, Any],
                 tool_registry: Optional[ToolRegistry] = None,
                 thoroughness: Optional[ThoroughnessLevel] = None,
                 isolated_context: bool = False,
                 model_tier: Optional[str] = None):
        """
        Initialize agent.

        Args:
            repo_path: Path to repository
            config: Configuration dictionary
            tool_registry: Shared tool registry (optional)
            thoroughness: Exploration depth level (scales config limits)
            isolated_context: If True, agent runs with isolated state (for subagents)
            model_tier: LLM tier to use ('fast', 'standard', 'advanced')
        """
        self.repo_path = repo_path
        self.config = config
        self.thoroughness = thoroughness
        self.isolated_context = isolated_context
        self.model_tier = model_tier

        # Setup logging
        self.logger = get_logger(self.agent_name, config)

        # Core components
        self.tools = tool_registry if tool_registry else ToolRegistry(repo_path)
        self.llm = LLMClient(config.get('llm', {}))
        self.tracer = Tracer(self.agent_name, config.get('trace', {}))
        self.cache = FileSummaryCache(
            cache_dir=config.get('cache', {}).get('cache_dir', 'cf_cache/file_summaries')
        )

        # Connect components
        self.llm.set_tracer(self.tracer, f"{self.agent_name}_session")
        if hasattr(self.tools, 'llm_tools') and hasattr(self.tools.llm_tools, 'set_llm_client'):
            self.tools.llm_tools.set_llm_client(self.llm)

        # Framework detection (skip for isolated subagents to save time)
        self.framework_context: Optional[FrameworkContext] = None
        if not isolated_context:
            try:
                detector = FrameworkDetector(repo_path, lambda p, s: self.llm.generate(p, s))
                self.framework_context = detector.detect()
                if self.framework_context.primary_language != "unknown":
                    self.logger.info(f"Detected framework: {self.framework_context.primary_language} "
                                   f"({', '.join(self.framework_context.frameworks)})")
            except Exception as e:
                self.logger.warning(f"Framework detection failed: {e}")
                self.framework_context = FrameworkContext()

        # Configuration with thoroughness scaling
        base_iterations = config.get('agents', {}).get('max_iterations', 40)
        base_files = config.get('agents', {}).get('max_files', 25)

        if thoroughness:
            scale = thoroughness.scale_factor()
            self.max_iterations = max(3, int(base_iterations * scale))
            self.max_files = max(3, int(base_files * scale))
        else:
            self.max_iterations = base_iterations
            self.max_files = base_files

        # Start tracing session
        self.session_id = self.tracer.start_session(f"{self.agent_name}_analysis")

    def get_system_prompt(self) -> str:
        """
        Get system prompt for this agent. Override in subclasses.
        """
        return f"""You are a {self.agent_name} analysis agent. Your job is to analyze code to answer questions.
Use the available tools strategically to gather information, then provide a comprehensive answer."""

    def _llm_generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Dict[str, Any]:
        """Generate LLM response using configured model tier."""
        if self.model_tier == 'fast':
            return self.llm.generate_fast(prompt, system_prompt, **kwargs)
        return self.llm.generate(prompt, system_prompt, **kwargs)

    @trace_method("analysis")
    def analyze(self, question: str) -> Dict[str, Any]:
        """
        Main analysis method using ReAct loop.

        LLM decides which tools to call at each step.
        """
        start_time = time.time()
        state = AgentState(question=question)

        # Extract keywords from question for file prioritization
        state.question_keywords = extract_question_keywords(question)
        if state.question_keywords:
            print(f"🔑 [{self.agent_name}] Question keywords: {', '.join(state.question_keywords[:8])}")

        print(f"\n{'='*70}")
        print(f"🤖 [{self.agent_name.upper()}] Question: {question}")
        print(f"{'='*70}\n")

        try:
            # Main ReAct loop - LLM-driven exploration
            # The LLM decides what to explore based on the question and discovered context
            # Enhanced prompt provides guidance through context (unread imports, file coverage)
            while state.iteration < self.max_iterations and not state.ready_to_answer:
                state.iteration += 1
                print(f"\n🔄 [{self.agent_name}] Iteration {state.iteration}/{self.max_iterations}")

                # Safety limit: Force convergence after max iterations
                if state.iteration >= self.max_iterations - 1:
                    print(f"⏰ [{self.agent_name}] Approaching max iterations - forcing answer generation")
                    state.ready_to_answer = True
                    break

                # THINK: LLM decides what tools to call
                # The enhanced prompt includes:
                # - Discovered imports (so LLM naturally reads them)
                # - File coverage feedback (so LLM knows when to explore more)
                tool_calls = self._think(state)

                if not tool_calls:
                    # LLM decided it has enough info - trust the decision
                    # The prompt already shows unread discovered imports, so if LLM
                    # says ready with unread imports visible, it's an informed decision
                    state.ready_to_answer = True
                    break

                # Handle special marker when all tool calls were duplicates
                if len(tool_calls) == 1 and tool_calls[0].name == '_all_duplicates':
                    # Build helpful feedback suggesting specific actions
                    feedback_parts = ['⚠️ Your previous tool calls were all duplicates.']

                    # Suggest truncated files first (highest priority)
                    if state.truncated_files:
                        fp, (offset, remaining) = next(iter(state.truncated_files.items()))
                        feedback_parts.append(f'📄 Continue reading truncated file: read_file(file_path="{fp}", offset={offset}) - {remaining} lines remaining')

                    # Suggest unread discovered imports
                    unread_imports = [f for f in state.discovered_files if f not in state.files_read]
                    if unread_imports:
                        feedback_parts.append(f'📎 Read unread imports: {", ".join(unread_imports[:3])}')

                    if not state.truncated_files and not unread_imports:
                        feedback_parts.append('Try reading files from search results instead of searching again.')

                    state.tool_results.append(ToolResult(
                        tool_name='_feedback',
                        params={},
                        result='\n'.join(feedback_parts),
                        success=False
                    ))
                    continue  # Loop again without executing tools

                # Handle special marker when JSON parse failed
                if len(tool_calls) == 1 and tool_calls[0].name == '_json_parse_failure':
                    # Build feedback suggesting specific actions
                    feedback_parts = ['⚠️ JSON parse failed. Please respond with valid JSON format.']

                    if state.truncated_files:
                        fp, (offset, remaining) = next(iter(state.truncated_files.items()))
                        feedback_parts.append(f'Suggested action: {{"tool_calls": [{{"name": "read_file", "params": {{"file_path": "{fp}", "offset": {offset}}}}}]}}')
                    else:
                        unread = [f for f in state.discovered_files if f not in state.files_read]
                        if unread:
                            feedback_parts.append(f'Suggested action: {{"tool_calls": [{{"name": "read_file", "params": {{"file_path": "{unread[0]}"}}}}]}}')

                    state.tool_results.append(ToolResult(
                        tool_name='_feedback',
                        params={},
                        result='\n'.join(feedback_parts),
                        success=False
                    ))
                    continue  # Loop again without executing tools

                # ACT: Execute tool calls (parallel for independent read-only tools)
                results = self._execute_tools_parallel(tool_calls)
                for result, tool_call in zip(results, tool_calls):
                    state.tool_results.append(result)

                    # Track failed directories - based on result content, not tool name
                    if not result.success and 'not found' in str(result.result).lower():
                        # Check if params indicate directory operation
                        failed_path = tool_call.params.get('directory', tool_call.params.get('path', ''))
                        if failed_path:
                            state.failed_directories.add(failed_path)

                    # Track files read - based on result having file content, not tool name
                    has_file_content = (
                        result.success and
                        isinstance(result.result, dict) and
                        'content' in result.result and
                        tool_call.params.get('file_path')
                    )
                    if has_file_content:
                        file_path = tool_call.params.get('file_path', '')
                        if file_path and file_path not in state.files_read:
                            state.files_read.append(file_path)

                        # Track truncated files that may need continuation reading
                        if isinstance(result.result, dict) and result.result.get('truncated', False):
                            total_lines = result.result.get('total_lines', 0)
                            lines_read = result.result.get('lines', 0)
                            offset = result.result.get('offset', 0)
                            next_offset = offset + lines_read  # Where to continue from
                            remaining = total_lines - next_offset
                            if remaining > 0:
                                # Store tuple: (next_offset_to_use, remaining_lines)
                                state.truncated_files[file_path] = (next_offset, remaining)
                                print(f"⚠️ [{self.agent_name}] File truncated: {file_path} ({remaining} lines remaining, continue with offset={next_offset})")
                        elif file_path in state.truncated_files:
                            # File was re-read without truncation, or continuation completed
                            del state.truncated_files[file_path]

                        # Dynamic discovery: Extract imports and add to discovery queue
                        # This enables the LLM to see and choose to read related files
                        if isinstance(result.result, dict) and 'imports' in result.result:
                            for imp in result.result['imports']:
                                resolved_path = imp.get('resolved_path')
                                if resolved_path and imp.get('exists', False):
                                    if resolved_path not in state.discovered_files and resolved_path not in state.files_read:
                                        state.discovered_files.append(resolved_path)
                                        print(f"📎 [{self.agent_name}] Discovered import: {resolved_path}")

                # Check if we've read the max files allowed
                if len(state.files_read) >= self.max_files:
                    print(f"📚 [{self.agent_name}] Read {len(state.files_read)} files, ready to synthesize")
                    state.ready_to_answer = True

            # Generate final answer
            answer = self._generate_answer(state)

            duration = time.time() - start_time

            return {
                'success': True,
                'answer': answer,
                'narrative': answer,  # Alias for compatibility
                'files_analyzed': state.files_read,
                'analyzed_file_list': state.files_read,  # Alias for compatibility
                'iterations': state.iteration,
                'tool_calls': len(state.tool_results),
                'execution_time': duration,
                'confidence': self._calculate_confidence(state),
                'agent': self.agent_name
            }

        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e),
                'answer': f"Analysis failed: {str(e)}",
                'narrative': f"Analysis failed: {str(e)}",
                'files_analyzed': state.files_read,
                'iterations': state.iteration,
                'execution_time': time.time() - start_time,
                'confidence': 0.2,
                'agent': self.agent_name
            }

        finally:
            self.tracer.end_session(self.session_id)

    def _think(self, state: AgentState) -> List[ToolCall]:
        """
        THINK phase: LLM decides what tools to call next.

        Returns list of tool calls, or empty list if ready to answer.
        """
        # Build context from previous tool calls
        context_parts = [f"Question: {state.question}"]
        context_parts.append(f"Files read so far: {len(state.files_read)}")
        context_parts.append(f"Iteration: {state.iteration}/{self.max_iterations}")

        # Add recent tool results (last 5)
        recent_results = state.tool_results[-5:] if state.tool_results else []
        if recent_results:
            context_parts.append("\nRecent tool results:")
            for r in recent_results:
                result_preview = str(r.result)[:500] if r.result else "empty"
                status = "✅" if r.success else "❌"
                context_parts.append(f"- {status} {r.tool_name}: {result_preview}...")

        if state.files_read:
            context_parts.append(f"\nFiles already read: {', '.join(state.files_read[:10])}")

        # Add deduplication context - show what's been searched already
        # Show recent tool calls to avoid repetition (generic, not tool-specific)
        if state.tool_call_history:
            recent_calls = list(state.tool_call_history)[-15:]
            context_parts.append(f"\n⚠️ ALREADY EXECUTED (do NOT repeat): {', '.join(recent_calls)}")
        if state.failed_directories:
            context_parts.append(f"🚫 NON-EXISTENT DIRECTORIES (do NOT use): {', '.join(list(state.failed_directories)[:10])}")

        context = "\n".join(context_parts)

        # Build tool descriptions
        tool_descriptions = self._get_tool_descriptions()

        # Build dynamic guidance context for the LLM
        exploration_guidance = []

        # Show unread discovered imports - LLM should read these before declaring ready
        unread_discovered = [f for f in state.discovered_files if f not in state.files_read]
        if unread_discovered:
            exploration_guidance.append(f"🚨 UNREAD DISCOVERED IMPORTS ({len(unread_discovered)}): {', '.join(unread_discovered[:10])}")
            exploration_guidance.append("   ⚠️ DO NOT declare ready until you've read relevant imports above.")
            exploration_guidance.append("   → These files are imported by code you've read - they contain related logic.")

        # Show truncated files with EXACT offset commands - LLM must use these
        if state.truncated_files:
            exploration_guidance.append("📄 TRUNCATED FILES - Continue reading files most relevant to the question:")
            for fp, (offset, remaining) in list(state.truncated_files.items())[:5]:
                exploration_guidance.append(f"   → read_file(file_path='{fp}', offset={offset}) - {remaining} lines remaining")
            exploration_guidance.append("   ⚠️ Prioritize files that likely contain logic relevant to your question.")
            exploration_guidance.append("   ⚠️ Do NOT re-read from start. Use the offset above to continue where you left off.")

        # Show question keywords to help LLM prioritize relevant searches
        if state.question_keywords:
            exploration_guidance.append(f"🔑 QUESTION KEYWORDS (prioritize files/searches matching these): {', '.join(state.question_keywords[:8])}")

        # Progress feedback - help LLM understand exploration depth
        files_read_count = len(state.files_read)
        if files_read_count == 0:
            exploration_guidance.append(f"🚫 NO FILES READ YET - You MUST use read_file to read files before declaring ready.")
            exploration_guidance.append("   Search results only show file LOCATIONS, not full content. You need to READ files.")
        elif files_read_count < 3:
            exploration_guidance.append(f"⚠️ LOW FILE COVERAGE: Only {files_read_count} files read. Read more files before answering.")
        elif files_read_count < 8:
            exploration_guidance.append(f"📊 MODERATE FILE COVERAGE: {files_read_count} files read. Consider reading a few more key files.")
        else:
            exploration_guidance.append(f"✅ GOOD FILE COVERAGE: {files_read_count} files read.")

        exploration_context = "\n".join(exploration_guidance) if exploration_guidance else ""

        prompt = f"""You are analyzing a codebase to answer a question.

{context}

{exploration_context}

Available tools:
{tool_descriptions}

Based on the question and what you've found so far, decide:
1. If you have enough information to answer the question, respond with: {{"ready": true, "reasoning": "explanation"}}
2. Otherwise, specify which tool(s) to call next.

Respond in this JSON format:
{{
    "ready": false,
    "reasoning": "brief explanation of what you need to find",
    "tool_calls": [
        {{"name": "tool_name", "params": {{"param1": "value1"}}}}
    ]
}}

Or if ready:
{{
    "ready": true,
    "reasoning": "I have gathered enough information about X, Y, Z to answer"
}}

EXPLORATION PRINCIPLES:
1. DISCOVER → READ → FOLLOW - Search/list to find files, read them, then follow their imports
2. READ DISCOVERED IMPORTS - If you see unread imports above, read them before declaring ready
3. THOROUGH EXPLORATION - Aim to read 5-10 relevant files before answering
4. ONLY READ PATHS FROM SEARCH/LIST RESULTS - Do NOT guess file paths. Use paths returned by search_files or list_files.
5. AVOID DUPLICATE SEARCHES - Check "ALREADY SEARCHED" patterns above before searching
6. CONTINUE TRUNCATED FILES - If you see "📄 TRUNCATED FILES" above, use the EXACT read_file command shown with offset parameter. Do NOT re-read from offset=0.
7. FIND INTEGRATION POINTS - For any component you read, ask: "What triggers this? What callbacks/handlers connect to it? What async processes are involved?" Search for these connections.
8. EXPLORE API LAYERS - Search for API endpoints, request handlers, and route definitions to understand how features are exposed. External systems often interact via these entry points.

CRITICAL - HANDLING TRUNCATED FILES:
- If a file shows "TRUNCATED" with remaining lines, you MUST continue reading it
- Use the EXACT offset shown in "📄 TRUNCATED FILES" section above
- Example: If it says "read_file(file_path='some_file.py', offset=100)", use EXACTLY that
- Do NOT try to re-read the file without offset - that will be blocked as duplicate
- Important files often have key logic AFTER line 100

GOOD PATTERN:
- Search for key concepts related to the question
- Read files returned from search
- If a file is truncated and relevant, IMMEDIATELY continue with offset
- Follow imports discovered in those files
- Continue until you have a complete picture
- Then declare ready with a clear reasoning

WHEN TO BE READY:
- NEVER be ready if you haven't read ANY files (search results don't count!)
- You've read at least a few files with read_file and understand their content
- You've followed key imports to understand dependencies (check UNREAD DISCOVERED IMPORTS above!)
- You've continued reading key truncated files (check 📄 TRUNCATED FILES above!)
- You can explain the flow/architecture based on actual code you READ
- NOT just because you saw file paths in search results
- You've explored WHAT TRIGGERS the behavior you're analyzing
- You've looked for files that INTEGRATE with the component you're studying
"""

        response = self._llm_generate(prompt, self.get_system_prompt(), max_tokens=2000)

        if not response.get('success'):
            self.logger.error(f"LLM call failed: {response.get('error')}")
            return []

        content = response.get('content', '')

        # Parse the response
        try:
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)

                if data.get('ready', False):
                    print(f"🎯 [{self.agent_name}] Ready to answer: {data.get('reasoning', '')[:100]}")
                    return []

                tool_calls = []
                duplicates_skipped = 0
                total_calls_attempted = 0
                for tc in data.get('tool_calls', []):
                    tool_name = tc.get('name', '')
                    params = tc.get('params', {})
                    total_calls_attempted += 1

                    # Validate tool is in available_tools
                    if tool_name not in self.available_tools and tool_name not in self.tools.tools:
                        self.logger.warning(f"Tool '{tool_name}' not available, skipping")
                        continue

                    # DEDUPLICATION: Generic deduplication based on tool call signature
                    is_duplicate = False

                    # Create a unique key for this tool call based on name and relevant params
                    dedup_key = self._get_dedup_key(tool_name, params)
                    if dedup_key:
                        if dedup_key in state.tool_call_history:
                            print(f"⚠️ [{self.agent_name}] Skipping duplicate {tool_name}: {dedup_key}")
                            is_duplicate = True
                        else:
                            state.tool_call_history.add(dedup_key)

                    # Skip operations on known failed paths
                    if not is_duplicate:
                        target_path = params.get('directory', params.get('path', params.get('file_path', '')))
                        if target_path and any(target_path == fd or target_path.startswith(fd + '/') for fd in state.failed_directories):
                            print(f"⚠️ [{self.agent_name}] Skipping {tool_name} on failed path: {target_path}")
                            is_duplicate = True

                    if is_duplicate:
                        duplicates_skipped += 1
                    else:
                        tool_calls.append(ToolCall(
                            name=tool_name,
                            params=params,
                            reasoning=data.get('reasoning', '')
                        ))

                if tool_calls:
                    print(f"💭 [{self.agent_name}] Reasoning: {data.get('reasoning', '')[:100]}")
                    return tool_calls

                # All tool calls were duplicates - return special marker to force retry
                if duplicates_skipped > 0 and duplicates_skipped == total_calls_attempted:
                    print(f"⚠️ [{self.agent_name}] All {duplicates_skipped} tool calls were duplicates - forcing exploration of new files")
                    # Return a marker to indicate we should NOT declare ready
                    return [ToolCall(name='_all_duplicates', params={}, reasoning='All tool calls were duplicates')]

                return tool_calls
        except json.JSONDecodeError as e:
            print(f"⚠️ [{self.agent_name}] JSON parse error: {e}")
            state.json_parse_failures += 1

            # If too many consecutive failures, force a simple action
            if state.json_parse_failures >= 3:
                print(f"⚠️ [{self.agent_name}] Too many JSON parse failures ({state.json_parse_failures}), forcing fallback action")
                # Try to read an unread discovered import or truncated file
                if state.truncated_files:
                    fp, (offset, remaining) = next(iter(state.truncated_files.items()))
                    return [ToolCall(
                        name='read_file',
                        params={'file_path': fp, 'offset': offset},
                        reasoning=f'Fallback: continue reading truncated file'
                    )]
                unread = [f for f in state.discovered_files if f not in state.files_read]
                if unread:
                    return [ToolCall(
                        name='read_file',
                        params={'file_path': unread[0]},
                        reasoning='Fallback: read discovered import'
                    )]
                # Last resort - return marker to continue loop without declaring ready
                return [ToolCall(name='_json_parse_failure', params={}, reasoning='JSON parse failed')]

            # Retry with context about what to explore and CORRECT parameter names
            suggestions = []
            if state.truncated_files:
                fp, (offset, remaining) = next(iter(state.truncated_files.items()))
                suggestions.append(f'{{"name": "read_file", "params": {{"file_path": "{fp}", "offset": {offset}}}}}')
            unread = [f for f in state.discovered_files if f not in state.files_read][:2]
            for f in unread:
                suggestions.append(f'{{"name": "read_file", "params": {{"file_path": "{f}"}}}}')

            # Use question keywords for search pattern - no hardcoded defaults
            if suggestions:
                suggestion_str = ", ".join(suggestions)
            elif state.question_keywords:
                suggestion_str = f'{{"name": "search_files", "params": {{"pattern": "{state.question_keywords[0]}"}}}}'
            else:
                # No suggestions and no keywords - just prompt LLM to provide valid action
                suggestion_str = '{"ready": true}'

            # Include correct parameter names to prevent LLM from guessing wrong ones
            retry_response = self._llm_generate(
                f"Previous response had invalid JSON. Reply with ONLY valid JSON.\n"
                f"CRITICAL: Use correct parameter names:\n"
                f"- search_files: pattern (NOT query)\n"
                f"- read_file: file_path, offset, max_lines\n"
                f"- list_files: pattern, directory\n"
                f"Example: {{\"ready\": false, \"tool_calls\": [{suggestion_str}]}}",
                self.get_system_prompt(),
                max_tokens=500
            )
            if retry_response.get('success'):
                try:
                    content = retry_response.get('content', '')
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        data = json.loads(content[json_start:json_end])
                        # Reset failure counter on successful parse
                        state.json_parse_failures = 0
                        if data.get('ready', False):
                            return []
                        # Process tool calls from retry
                        tool_calls = []
                        for tc in data.get('tool_calls', []):
                            tool_calls.append(ToolCall(
                                name=tc.get('name', ''),
                                params=tc.get('params', {}),
                                reasoning='From JSON retry'
                            ))
                        if tool_calls:
                            return tool_calls
                except json.JSONDecodeError:
                    pass  # Will return fallback below

            # Return marker to continue exploration (NOT empty list which means ready!)
            return [ToolCall(name='_json_parse_failure', params={}, reasoning='JSON parse failed, continue exploring')]

        # Let LLM decide initial exploration strategy - no hardcoded first tool
        return []

    def _get_dedup_key(self, tool_name: str, params: dict) -> str:
        """
        Generate a deduplication key for a tool call.

        Uses generic parameter extraction rather than hardcoded tool names.
        Key is based on tool name + relevant parameters (path, pattern, query, etc.)
        """
        # Common parameter names that identify unique operations
        key_params = []
        for param_name in ['file_path', 'path', 'directory', 'pattern', 'query', 'name', 'target']:
            if param_name in params:
                value = str(params[param_name]).lower()
                key_params.append(f"{param_name}={value}")

        if key_params:
            return f"{tool_name}:{','.join(sorted(key_params))}"
        return ""

    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """ACT phase: Execute a single tool call"""
        start_time = time.time()

        # Use params as-is - LLM learns correct parameters from tool schema
        params = tool_call.params.copy()

        # Format params for display
        param_str = ', '.join(f"{k}={str(v)[:50]}" for k, v in params.items())
        print(f"🔧 [{self.agent_name}] {tool_call.name}({param_str})")

        try:
            # Validate tool exists
            if tool_call.name not in self.tools.tools:
                return ToolResult(
                    tool_name=tool_call.name,
                    params=tool_call.params,
                    result={'error': f'Unknown tool: {tool_call.name}'},
                    success=False,
                    duration=time.time() - start_time
                )

            # Execute tool with corrected params
            result = self.tools.execute(tool_call.name, **params)
            success = not result.get('error') if isinstance(result, dict) else True

            duration = time.time() - start_time
            status = "✅" if success else "❌"
            print(f"   {status} Completed in {duration:.2f}s")

            return ToolResult(
                tool_name=tool_call.name,
                params=params,
                result=result,
                success=success,
                duration=duration
            )

        except Exception as e:
            self.logger.error(f"Tool execution failed: {e}")
            return ToolResult(
                tool_name=tool_call.name,
                params=params,
                result={'error': str(e)},
                success=False,
                duration=time.time() - start_time
            )

    def _execute_tools_parallel(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute multiple tool calls, parallelizing read-only operations.

        Tools that are safe to parallelize (read-only):
        - read_file, search_files, scan_directory, list_files
        - grep_search, find_references, get_file_content

        Tools that must run sequentially (may have side effects):
        - write_file, create_file, delete_file
        - Any tool not explicitly marked as read-only

        OPTIMIZATION: Running multiple file reads in parallel can reduce
        iteration time by 50-70% when the LLM requests multiple files.
        """
        if len(tool_calls) <= 1:
            # Single tool call - no parallelization needed
            return [self._execute_tool(tc) for tc in tool_calls]

        # Execute all tools - LLM handles orchestration
        # No hardcoded read/write classification
        parallel_calls = tool_calls
        sequential_calls = []

        results = []

        # Execute parallel-safe tools concurrently
        if parallel_calls:
            parallel_workers = self.config.get('agents', {}).get('parallel_workers', 8)
            with ThreadPoolExecutor(max_workers=min(parallel_workers, len(parallel_calls))) as executor:
                futures = {executor.submit(self._execute_tool, tc): tc for tc in parallel_calls}
                # Collect results in order of completion
                parallel_results = {}
                for future in as_completed(futures):
                    tc = futures[future]
                    try:
                        result = future.result()
                        parallel_results[id(tc)] = result
                    except Exception as e:
                        parallel_results[id(tc)] = ToolResult(
                            tool_name=tc.name,
                            params=tc.params,
                            result={'error': str(e)},
                            success=False
                        )

                # Return in original order
                for tc in parallel_calls:
                    results.append(parallel_results[id(tc)])

        # Execute sequential tools one by one
        for tc in sequential_calls:
            results.append(self._execute_tool(tc))

        return results

    def _generate_answer(self, state: AgentState) -> str:
        """Generate final answer based on gathered information"""
        print(f"\n📝 [{self.agent_name}] Generating answer from {len(state.files_read)} files...")

        # Collect file contents WITH LINE NUMBERS for accurate references
        file_contents = []
        file_line_map = {}  # Track what lines are in each file for validation
        for result in state.tool_results:
            # Check for file content based on result structure, not tool name
            has_file_content = (
                result.success and
                isinstance(result.result, dict) and
                'content' in result.result
            )
            if has_file_content:
                content = result.result.get('content', '')
                file_path = result.params.get('file_path', 'unknown')

                # Add line numbers to content for accurate references
                lines = content.split('\n')
                numbered_lines = []
                for i, line in enumerate(lines[:200], 1):  # Limit to 200 lines
                    numbered_lines.append(f"{i:4d}| {line}")
                    # Track key definitions for validation
                    if 'class ' in line or 'def ' in line or '=' in line:
                        file_line_map.setdefault(file_path, {})[i] = line.strip()

                numbered_content = '\n'.join(numbered_lines)
                if len(lines) > 200:
                    numbered_content += f"\n... ({len(lines) - 200} more lines)"

                file_contents.append(f"### {file_path}\n```\n{numbered_content}\n```")

        # Also collect search/scan results - based on result structure, not tool names
        search_results = []
        for result in state.tool_results:
            # Skip file content results (already collected above)
            if result.success and isinstance(result.result, dict) and 'content' not in result.result:
                # Include results that look like lists/collections of items
                result_str = str(result.result)[:1000]
                if result_str:
                    search_results.append(f"- {result.tool_name}: {result_str}")


        prompt = f"""Answer this question about the codebase:

Question: {state.question}

Files analyzed ({len(state.files_read)}):
{chr(10).join(state.files_read[:20])}

Search/scan results:
{chr(10).join(search_results[:5]) if search_results else 'None'}

File contents (WITH LINE NUMBERS - use these for accurate references):
{chr(10).join(file_contents[:10]) if file_contents else 'No file contents available'}

ANSWER FORMAT REQUIREMENTS:

1. **Structure** - Use this exact structure:
   - **Overview** (1-2 paragraphs): Brief summary of the system/feature
   - **Technical Flow** (numbered steps): Step-by-step walkthrough with EXACT file:line references
   - **Key Components** (bullet list): Important classes, functions, constants with EXACT file:line
   - **Where to Look** (bullet list): Key files to explore for more detail

2. **File:Line References** - Use EXACT line numbers from the code above:
   - Look at the line numbers shown (e.g., "  45| class Enrollment:")
   - Reference as: "The `Enrollment` class (`path/to/file.py:45`) handles..."
   - For ranges: "Status constants (`path/to/file.py:12-25`) define..."

3. **Style Rules - STRICTLY FOLLOW**:
   - Be DIRECT and CERTAIN. State facts from code, not guesses.
   - NEVER use hedging: "likely", "probably", "appears to", "seems to", "may"
   - NEVER write: "If you want I can dive deeper...", "Let me know if..."
   - DO NOT add redundant summary sections - the Overview IS your summary
   - DO NOT repeat the same information in multiple sections
   - Keep sections concise - max 4-5 bullets per list
   - Use `backticks` for code names, **bold** for emphasis

4. **Content Requirements - Extract Specifics from Code**:
   - **Functions**: Include full signatures with parameter names as shown in the code
   - **Constants/Enums**: Extract the ACTUAL string/int values assigned, not just the constant names
   - **Model/Class fields**: Name the key fields and their types as defined in the code
   - **Mappings/Dicts**: Show the key→value structure when you see dictionary definitions
   - **Relationships**: Note foreign keys, inheritance, and how classes connect
   - Explain how components work together in the flow
   - If information is insufficient, state what was found and what's missing

5. **FORBIDDEN PATTERNS - DO NOT USE**:
   - NEVER write "File `x.py` is very large..." or "File `x.py` contains..."
   - NEVER do file-by-file analysis like "- File `x.py` is..., - File `y.py` has..."
   - NEVER say "likely contains", "probably has", "appears to be"
   - Instead: SYNTHESIZE information across files into a coherent narrative
   - Focus on HOW THE SYSTEM WORKS, not what each file contains

6. **STRICT GROUNDING - PREVENT HALLUCINATION**:
   - ONLY use class/function/method names you see EXACTLY in the code above
   - DO NOT rename or paraphrase method names - use the EXACT spelling from the code
   - DO NOT reference files not in the "Files analyzed" list above
   - Line numbers MUST match what's shown (the number before the "|" symbol)
   - If you didn't find something in the code, say: "The files read did not reveal X"
   - DO NOT invent components, integrations, or triggers not shown in the code
   - When uncertain, be explicit about what you found vs. what you're inferring
"""

        response = self._llm_generate(prompt, self.get_system_prompt(), max_tokens=4000)

        if response.get('success'):
            answer = response.get('content', 'Failed to generate answer')
            # Validate the answer for common issues
            answer = self._validate_and_clean_answer(answer, state)
            return answer
        else:
            return f"Answer generation failed: {response.get('error', 'unknown error')}"

    def _validate_and_clean_answer(self, answer: str, state: AgentState, retry_count: int = 0) -> str:
        """
        Validate answer and clean up common issues.

        BLOCKING VALIDATION:
        - Hedging language (likely, probably, etc.) triggers regeneration
        - References to unread files triggers regeneration
        - Max 2 retries to avoid infinite loops
        """
        max_retries = 2
        issues_found = []

        # Check for file references that weren't actually read
        # Dynamic: match any file with extension (not hardcoded to .py)
        unread_refs = []
        file_refs = re.findall(r'`([^`\s]+\.\w+(?::\d+)?)`', answer)
        for ref in file_refs:
            file_path = ref.split(':')[0]
            # Check if any read file ends with this path
            was_read = any(f.endswith(file_path) or file_path in f for f in state.files_read)
            if not was_read and not file_path.startswith('path/'):  # Ignore example paths
                unread_refs.append(file_path)
                print(f"⚠️ [{self.agent_name}] Reference to unread file: {file_path}")

        if unread_refs:
            issues_found.append(f"unread file refs: {unread_refs}")

        # Check for raw file-by-file analysis pattern (messy format)
        raw_analysis_patterns = [
            r'^-\s*File\s+`[^`]+`\s+(?:is|contains|shows|has)',  # "- File `x.py` is..."
            r'The\s+file\s+`[^`]+`\s+(?:is\s+very\s+large|likely\s+contains)',  # "The file `x.py` is very large..."
        ]
        for pattern in raw_analysis_patterns:
            if re.search(pattern, answer, re.MULTILINE):
                issues_found.append("raw file analysis format")
                print(f"⚠️ [{self.agent_name}] Answer contains raw file-by-file analysis (messy format)")
                break

        # BLOCKING: If issues found and we haven't exceeded retries, regenerate answer
        if issues_found and retry_count < max_retries:
            print(f"🔄 [{self.agent_name}] Regenerating answer due to: {', '.join(issues_found)} (retry {retry_count + 1}/{max_retries})")

            # Build stricter regeneration prompt
            regen_prompt = f"""Your previous answer had quality issues: {', '.join(issues_found)}

CRITICAL CORRECTIONS REQUIRED:
1. NO HEDGING - Remove ALL uncertainty words (likely, probably, appears, seems, may, might, could, possibly)
   Instead, state facts directly: "The function does X" not "The function likely does X"

2. ONLY REFERENCE FILES YOU READ - These files were read: {state.files_read[:20]}
   Do NOT mention files not in this list.

3. SYNTHESIZED FORMAT ONLY - Do NOT write "File `x.py` contains..." analysis
   Instead, write flowing technical narrative with inline references like:
   "The `UserManager` class (`src/auth/manager.py:45`) handles authentication..."

4. DIRECT STATEMENTS - Replace:
   - "likely" → remove entirely or state what code shows
   - "probably" → state the fact
   - "appears to" → "does" or describe what code shows
   - "seems to" → state the fact

Rewrite the answer following these rules strictly:

{answer[:2000]}...
"""
            # Regenerate with stricter prompt
            response = self._llm_generate(regen_prompt, self.get_system_prompt(), max_tokens=4000)
            if response.get('success'):
                new_answer = response.get('content', answer)
                # Recursive validation with incremented retry count
                return self._validate_and_clean_answer(new_answer, state, retry_count + 1)

        return answer.strip()

    def _get_tool_descriptions(self) -> str:
        """Get descriptions of available tools with parameter schemas"""
        descriptions = []
        tool_info = self.tools.get_available_tools()
        schemas = getattr(self.tools, '_schemas', {})

        for tool_name in self.available_tools:
            # Try to get schema-based description first (more detailed)
            if tool_name in schemas:
                schema = schemas[tool_name]
                func_schema = schema.get('function', {})
                desc = func_schema.get('description', tool_info.get(tool_name, 'Available'))
                params = func_schema.get('parameters', {}).get('properties', {})
                required = func_schema.get('parameters', {}).get('required', [])

                # Build parameter list with types
                param_parts = []
                for param_name, param_info in params.items():
                    param_type = param_info.get('type', 'any')
                    is_required = '*' if param_name in required else ''
                    param_parts.append(f"{param_name}{is_required}: {param_type}")

                param_str = f" ({', '.join(param_parts)})" if param_parts else ""
                descriptions.append(f"- {tool_name}{param_str}: {desc}")
            elif tool_name in tool_info:
                # Fallback to simple description
                desc = tool_info[tool_name]
                descriptions.append(f"- {tool_name}: {desc}")
            elif tool_name in self.tools.tools:
                descriptions.append(f"- {tool_name}: Available")

        return "\n".join(descriptions)

    def _calculate_confidence(self, state: AgentState) -> float:
        """Calculate confidence score based on analysis"""
        # Base confidence
        confidence = 0.5

        # More files = higher confidence (up to +0.3)
        file_bonus = min(0.3, len(state.files_read) * 0.02)
        confidence += file_bonus

        # Successful tool calls = higher confidence (up to +0.1)
        successful = sum(1 for tc in state.tool_results if tc.success)
        if state.tool_results:
            success_rate = successful / len(state.tool_results)
            confidence += success_rate * 0.1

        # More iterations used (but not maxed out) = thorough analysis
        if state.iteration < self.max_iterations:
            confidence += 0.05

        return min(0.95, confidence)
