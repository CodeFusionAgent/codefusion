"""
BaseAgent - ReAct-Style Agent with LLM-Driven Tool Selection

All agents use the same ReAct loop where LLM decides which tools to call.
Subclasses just define which tools are available.
"""

import time
import json
import traceback
from abc import ABC
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from cf.tools.registry import ToolRegistry
from cf.llm.client import LLMClient
from cf.trace.tracer import Tracer, trace_method
from cf.knowledge_base.file_summary_cache import FileSummaryCache
from cf.utils.logger import get_logger


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
                 tool_registry: Optional[ToolRegistry] = None):
        self.repo_path = repo_path
        self.config = config

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

        # Configuration
        self.max_iterations = config.get('agents', {}).get('max_iterations', 15)
        self.max_files = config.get('agents', {}).get('max_files', 30)

        # Start tracing session
        self.session_id = self.tracer.start_session(f"{self.agent_name}_analysis")

    def get_system_prompt(self) -> str:
        """
        Get system prompt for this agent. Override in subclasses.
        """
        return f"""You are a {self.agent_name} analysis agent. Your job is to analyze code to answer questions.
Use the available tools strategically to gather information, then provide a comprehensive answer."""

    @trace_method("analysis")
    def analyze(self, question: str) -> Dict[str, Any]:
        """
        Main analysis method using ReAct loop.

        LLM decides which tools to call at each step.
        """
        start_time = time.time()
        state = AgentState(question=question)

        print(f"\n{'='*70}")
        print(f"🤖 [{self.agent_name.upper()}] Question: {question}")
        print(f"{'='*70}\n")

        try:
            # Main ReAct loop
            while state.iteration < self.max_iterations and not state.ready_to_answer:
                state.iteration += 1
                print(f"\n🔄 [{self.agent_name}] Iteration {state.iteration}/{self.max_iterations}")

                # THINK: LLM decides what tools to call
                tool_calls = self._think(state)

                if not tool_calls:
                    # LLM decided we have enough info
                    state.ready_to_answer = True
                    break

                # ACT: Execute tool calls
                for tool_call in tool_calls:
                    result = self._execute_tool(tool_call)
                    state.tool_results.append(result)

                    # Track files read
                    if result.tool_name == 'read_file' and result.success:
                        file_path = tool_call.params.get('file_path', '')
                        if file_path and file_path not in state.files_read:
                            state.files_read.append(file_path)

                # Check if we've read enough files
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

        context = "\n".join(context_parts)

        # Build tool descriptions
        tool_descriptions = self._get_tool_descriptions()

        prompt = f"""You are analyzing a codebase to answer a question.

{context}

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

IMPORTANT:
- Start by scanning the directory or searching for relevant files
- Read specific files that seem relevant to the question
- Be efficient - don't read files that aren't relevant
- You can make multiple tool calls at once
"""

        response = self.llm.generate(prompt, self.get_system_prompt(), max_tokens=2000)

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
                for tc in data.get('tool_calls', []):
                    tool_name = tc.get('name', '')
                    # Validate tool is in available_tools
                    if tool_name in self.available_tools or tool_name in self.tools.tools:
                        tool_calls.append(ToolCall(
                            name=tool_name,
                            params=tc.get('params', {}),
                            reasoning=data.get('reasoning', '')
                        ))
                    else:
                        self.logger.warning(f"Tool '{tool_name}' not available, skipping")

                if tool_calls:
                    print(f"💭 [{self.agent_name}] Reasoning: {data.get('reasoning', '')[:100]}")

                return tool_calls
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse LLM response: {e}")

        # Fallback: start with directory scan if first iteration
        if state.iteration == 1 and 'scan_directory' in self.available_tools:
            return [ToolCall(
                name='scan_directory',
                params={'max_depth': 3},
                reasoning='Initial directory scan'
            )]

        return []

    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """ACT phase: Execute a single tool call"""
        start_time = time.time()

        # Format params for display
        param_str = ', '.join(f"{k}={str(v)[:50]}" for k, v in tool_call.params.items())
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

            # Execute tool
            result = self.tools.execute(tool_call.name, **tool_call.params)
            success = not result.get('error') if isinstance(result, dict) else True

            duration = time.time() - start_time
            status = "✅" if success else "❌"
            print(f"   {status} Completed in {duration:.2f}s")

            return ToolResult(
                tool_name=tool_call.name,
                params=tool_call.params,
                result=result,
                success=success,
                duration=duration
            )

        except Exception as e:
            self.logger.error(f"Tool execution failed: {e}")
            return ToolResult(
                tool_name=tool_call.name,
                params=tool_call.params,
                result={'error': str(e)},
                success=False,
                duration=time.time() - start_time
            )

    def _generate_answer(self, state: AgentState) -> str:
        """Generate final answer based on gathered information"""
        print(f"\n📝 [{self.agent_name}] Generating answer from {len(state.files_read)} files...")

        # Collect file contents
        file_contents = []
        for result in state.tool_results:
            if result.tool_name == 'read_file' and result.success:
                content = result.result.get('content', '') if isinstance(result.result, dict) else str(result.result)
                file_path = result.params.get('file_path', 'unknown')
                # Truncate very long files
                if len(content) > 5000:
                    content = content[:5000] + "\n... (truncated)"
                file_contents.append(f"### {file_path}\n```\n{content}\n```")

        # Also collect search results
        search_results = []
        for result in state.tool_results:
            if result.tool_name in ['search_files', 'scan_directory', 'list_files', 'web_search', 'search_documentation'] and result.success:
                search_results.append(f"- {result.tool_name}: {str(result.result)[:1000]}")

        prompt = f"""Based on analyzing the codebase, answer this question:

Question: {state.question}

Files analyzed ({len(state.files_read)}):
{chr(10).join(state.files_read[:20])}

Search/scan results:
{chr(10).join(search_results[:5]) if search_results else 'None'}

File contents:
{chr(10).join(file_contents[:10]) if file_contents else 'No file contents available'}

Provide a comprehensive answer that:
1. Directly addresses the question
2. References specific files and code when relevant
3. Explains how the components work together
4. Uses clear technical language

If the information gathered is insufficient, explain what you were able to find and what's missing.
"""

        response = self.llm.generate(prompt, self.get_system_prompt(), max_tokens=4000)

        if response.get('success'):
            return response.get('content', 'Failed to generate answer')
        else:
            return f"Answer generation failed: {response.get('error', 'unknown error')}"

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
