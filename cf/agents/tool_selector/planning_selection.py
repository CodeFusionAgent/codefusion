"""
Tool Selector Planning and Selection - Combined Planning and Selection Logic
"""

import json
from typing import Dict, List, Any, Optional, Callable, Tuple

from cf.utils.llm_parser import LLMResponseParser

from .types import (
    QuestionCategory, Complexity,
    ToolRecommendation, ToolChainPlan, ExecutionContext
)
from .classification import QuestionClassifier


class LLMToolSelector:
    """
    LLM-based intelligent tool selection.

    Uses LLM to classify questions and select optimal tools based on:
    - Question type (lookup, flow tracing, architecture, etc.)
    - Available tools and their capabilities
    - Previous context and gathered information
    - Tool execution history and results
    """

    # Tool capabilities mapping
    TOOL_CAPABILITIES = {
        'read_file': {
            'description': 'Read file contents',
            'best_for': ['explanation', 'debugging', 'documentation'],
            'provides': ['file_content', 'implementation_details'],
            'cost': 1,
        },
        'search_files': {
            'description': 'Search for patterns in files',
            'best_for': ['lookup', 'debugging', 'refactoring'],
            'provides': ['file_locations', 'pattern_matches'],
            'cost': 2,
        },
        'list_files': {
            'description': 'List files matching patterns',
            'best_for': ['lookup', 'architecture'],
            'provides': ['file_list', 'directory_structure'],
            'cost': 1,
        },
        'scan_directory': {
            'description': 'Scan directory structure',
            'best_for': ['architecture', 'lookup'],
            'provides': ['directory_tree', 'project_structure'],
            'cost': 1,
        },
        'find_callers': {
            'description': 'Find what calls a function',
            'best_for': ['flow', 'debugging', 'refactoring'],
            'provides': ['caller_list', 'usage_context'],
            'cost': 3,
        },
        'find_callees': {
            'description': 'Find what a function calls',
            'best_for': ['flow', 'architecture'],
            'provides': ['callee_list', 'dependency_info'],
            'cost': 3,
        },
        'find_usages': {
            'description': 'Find all usages of a symbol',
            'best_for': ['refactoring', 'flow', 'debugging'],
            'provides': ['usage_locations', 'impact_scope'],
            'cost': 3,
        },
        'find_dependencies': {
            'description': 'Find module dependencies',
            'best_for': ['architecture', 'refactoring'],
            'provides': ['dependency_graph', 'import_chain'],
            'cost': 2,
        },
        'search_by_semantics': {
            'description': 'Semantic code search',
            'best_for': ['explanation', 'lookup', 'documentation'],
            'provides': ['relevant_code', 'semantic_matches'],
            'cost': 4,
        },
        'search_by_functionality': {
            'description': 'Search by function purpose',
            'best_for': ['lookup', 'explanation'],
            'provides': ['functional_matches', 'similar_code'],
            'cost': 4,
        },
        'find_files_for_question': {
            'description': 'Find files relevant to question',
            'best_for': ['lookup', 'explanation', 'architecture'],
            'provides': ['relevant_files', 'entry_points'],
            'cost': 3,
        },
        'analyze_code_structure': {
            'description': 'LLM analysis of code structure',
            'best_for': ['architecture', 'explanation'],
            'provides': ['structural_analysis', 'patterns'],
            'cost': 5,
        },
        'detect_patterns': {
            'description': 'Detect design patterns',
            'best_for': ['architecture', 'refactoring'],
            'provides': ['pattern_list', 'design_insights'],
            'cost': 5,
        },
        'summarize_code': {
            'description': 'Generate code summary',
            'best_for': ['explanation', 'documentation'],
            'provides': ['code_summary', 'key_concepts'],
            'cost': 4,
        },
        'web_search': {
            'description': 'Search external documentation',
            'best_for': ['documentation', 'explanation'],
            'provides': ['external_docs', 'api_info'],
            'cost': 3,
        },
    }

    # Tool chains for different question types
    TOOL_CHAINS = {
        'lookup_simple': ['search_files', 'read_file'],
        'lookup_complex': ['find_files_for_question', 'scan_directory', 'search_files', 'read_file'],
        'flow_analysis': ['find_files_for_question', 'find_callers', 'find_callees', 'read_file'],
        'architecture_overview': ['scan_directory', 'find_dependencies', 'detect_patterns', 'analyze_code_structure'],
        'explanation_deep': ['find_files_for_question', 'read_file', 'find_callees', 'summarize_code'],
        'debugging': ['search_files', 'find_callers', 'read_file', 'find_usages'],
        'documentation': ['find_files_for_question', 'read_file', 'web_search', 'summarize_code'],
    }

    def __init__(self, llm_callback: Callable, config: Dict[str, Any]):
        """
        Initialize tool selector.

        Args:
            llm_callback: Callable(prompt, system_prompt) -> response dict
            config: Configuration dictionary
        """
        self.llm = llm_callback
        self.config = config
        self.classifier = QuestionClassifier(llm_callback, config)

    def classify_question(self, question: str):
        """Delegate to classifier."""
        return self.classifier.classify(question)

    def plan_tool_chain(
        self,
        question: str,
        available_tools: List[str],
        max_tools: int = 10
    ) -> ToolChainPlan:
        """
        Plan a sequence of tools to answer a question.

        Args:
            question: User question
            available_tools: List of available tool names
            max_tools: Maximum tools in chain

        Returns:
            ToolChainPlan with ordered tool recommendations
        """
        classification = self.classify_question(question)

        # Select base tool chain
        chain_key = self._select_chain_key(classification)
        base_chain = self.TOOL_CHAINS.get(chain_key, ['search_files', 'read_file'])

        # Filter to available tools
        chain = [t for t in base_chain if t in available_tools]

        # Build recommendations
        recommendations = []
        for i, tool_name in enumerate(chain[:max_tools]):
            cap = self.TOOL_CAPABILITIES.get(tool_name, {})
            recommendations.append(ToolRecommendation(
                tool_name=tool_name,
                confidence=0.9 - (i * 0.05),  # Decreasing confidence
                reason=cap.get('description', 'Useful for analysis'),
                params=self._suggest_params(tool_name, question, classification),
                priority=i,
                depends_on=chain[:i] if i > 0 else [],
                expected_output=', '.join(cap.get('provides', []))
            ))

        # Determine strategy
        if classification.complexity == Complexity.SIMPLE:
            strategy = 'sequential'
            max_iterations = 3
        elif classification.complexity == Complexity.MODERATE:
            strategy = 'sequential'
            max_iterations = 5
        else:
            strategy = 'conditional'
            max_iterations = 10

        return ToolChainPlan(
            tools=recommendations,
            strategy=strategy,
            max_iterations=max_iterations,
            stop_conditions=[
                'Found definitive answer',
                'Analyzed all relevant files',
                'Confidence above 0.9'
            ],
            fallback_tools=[t for t in ['search_files', 'read_file'] if t in available_tools],
            estimated_complexity=classification.complexity
        )

    def _select_chain_key(self, classification) -> str:
        """Select tool chain based on classification"""
        cat = classification.category

        if cat == QuestionCategory.LOOKUP:
            if classification.complexity == Complexity.SIMPLE:
                return 'lookup_simple'
            return 'lookup_complex'
        elif cat == QuestionCategory.FLOW:
            return 'flow_analysis'
        elif cat == QuestionCategory.ARCHITECTURE:
            return 'architecture_overview'
        elif cat == QuestionCategory.EXPLANATION:
            return 'explanation_deep'
        elif cat == QuestionCategory.DEBUGGING:
            return 'debugging'
        elif cat == QuestionCategory.DOCUMENTATION:
            return 'documentation'
        else:
            return 'explanation_deep'

    def _suggest_params(
        self,
        tool_name: str,
        question: str,
        classification
    ) -> Dict[str, Any]:
        """Suggest parameters for a tool based on question"""
        params = {}

        concepts = classification.key_concepts

        if tool_name in ['search_files', 'find_files_for_question']:
            if concepts:
                params['query'] = concepts[0]
            else:
                # Extract likely search term
                words = question.split()
                important = [w for w in words if len(w) > 4 and w.lower() not in
                            ['about', 'where', 'which', 'what', 'does', 'how', 'the']]
                if important:
                    params['query'] = important[0]

        elif tool_name in ['find_callers', 'find_callees', 'find_usages']:
            if concepts:
                params['symbol'] = concepts[0]

        elif tool_name == 'read_file':
            # Will be filled by previous tool results
            pass

        return params

    def select_tools_for_task(
        self,
        question: str,
        available_tools: List[str],
        context: Optional[ExecutionContext] = None
    ) -> List[ToolRecommendation]:
        """
        Select optimal tools for a given task.

        Args:
            question: User question or task
            available_tools: List of available tool names
            context: Optional context from previous tool calls

        Returns:
            List of ToolRecommendation in order of priority
        """
        classification = self.classify_question(question)

        # Get tool priorities based on category
        priorities = self._get_tool_priorities(classification.category)

        # Adjust based on context
        if context:
            priorities = self._adjust_for_context(priorities, context)

        # Build recommendations
        recommendations = []
        for tool_name in available_tools:
            if tool_name in priorities:
                priority, reason = priorities[tool_name]
                recommendations.append(ToolRecommendation(
                    tool_name=tool_name,
                    confidence=priority,
                    reason=reason,
                    params=self._suggest_params(tool_name, question, classification)
                ))

        # Sort by confidence
        recommendations.sort(key=lambda r: r.confidence, reverse=True)

        return recommendations[:7]

    def _get_tool_priorities(self, category: QuestionCategory) -> Dict[str, Tuple[float, str]]:
        """Get tool priorities based on question category"""
        # Base priorities
        base = {
            'scan_directory': (0.5, 'Understand project structure'),
            'search_files': (0.5, 'Find relevant code'),
            'read_file': (0.4, 'Read implementation details'),
        }

        category_priorities = {
            QuestionCategory.LOOKUP: {
                'search_files': (0.95, 'Primary: Find specific code'),
                'list_files': (0.9, 'Find files by pattern'),
                'find_files_for_question': (0.85, 'Semantic file discovery'),
                'read_file': (0.7, 'Read found files'),
            },
            QuestionCategory.FLOW: {
                'find_callers': (0.95, 'Primary: Trace who calls function'),
                'find_callees': (0.92, 'Trace what function calls'),
                'find_usages': (0.88, 'Find all usages'),
                'find_dependencies': (0.8, 'Understand module dependencies'),
                'read_file': (0.75, 'Read implementation'),
            },
            QuestionCategory.ARCHITECTURE: {
                'scan_directory': (0.95, 'Primary: Project structure'),
                'detect_patterns': (0.9, 'Identify design patterns'),
                'analyze_code_structure': (0.88, 'Structural analysis'),
                'find_dependencies': (0.85, 'Map dependencies'),
                'find_files_for_question': (0.7, 'Find key files'),
            },
            QuestionCategory.EXPLANATION: {
                'find_files_for_question': (0.92, 'Find relevant files'),
                'read_file': (0.9, 'Primary: Read implementation'),
                'summarize_code': (0.85, 'Generate summary'),
                'find_callees': (0.75, 'Understand dependencies'),
            },
            QuestionCategory.COMPARISON: {
                'find_files_for_question': (0.9, 'Find both items'),
                'read_file': (0.88, 'Read implementations'),
                'analyze_code_structure': (0.8, 'Compare structure'),
                'search_files': (0.75, 'Find similarities'),
            },
            QuestionCategory.DEBUGGING: {
                'search_files': (0.95, 'Primary: Find error location'),
                'find_callers': (0.9, 'Trace error path'),
                'read_file': (0.88, 'Read suspicious code'),
                'find_usages': (0.8, 'Find impact'),
            },
            QuestionCategory.DOCUMENTATION: {
                'find_files_for_question': (0.9, 'Find relevant files'),
                'read_file': (0.88, 'Read docs/code'),
                'web_search': (0.85, 'External documentation'),
                'summarize_code': (0.8, 'Generate summary'),
            },
            QuestionCategory.PERFORMANCE: {
                'find_files_for_question': (0.9, 'Find performance code'),
                'find_callers': (0.85, 'Find hot paths'),
                'read_file': (0.82, 'Read implementation'),
                'analyze_code_structure': (0.75, 'Structural analysis'),
            },
            QuestionCategory.SECURITY: {
                'search_files': (0.95, 'Find security code'),
                'read_file': (0.9, 'Analyze implementation'),
                'find_usages': (0.85, 'Find exposure'),
                'web_search': (0.8, 'Security best practices'),
            },
            QuestionCategory.REFACTORING: {
                'find_usages': (0.95, 'Primary: Find all usages'),
                'find_callers': (0.9, 'Find dependencies'),
                'read_file': (0.85, 'Read current code'),
                'detect_patterns': (0.8, 'Identify patterns'),
            },
        }

        return {**base, **category_priorities.get(category, {})}

    def _adjust_for_context(
        self,
        priorities: Dict[str, Tuple[float, str]],
        context: ExecutionContext
    ) -> Dict[str, Tuple[float, str]]:
        """Adjust priorities based on execution context"""
        adjusted = dict(priorities)

        executed_names = [t.get('name') for t in context.executed_tools]

        # Decrease priority for already executed tools
        for name in executed_names:
            if name in adjusted:
                old_priority, reason = adjusted[name]
                adjusted[name] = (old_priority * 0.3, f'{reason} (already used)')

        # Increase read_file priority if we have discovered files
        if context.discovered_files and 'read_file' in adjusted:
            old_priority, reason = adjusted['read_file']
            adjusted['read_file'] = (min(0.95, old_priority + 0.2), f'{reason} (files discovered)')

        # Increase caller/callee priority if we have functions
        if context.discovered_functions:
            for tool in ['find_callers', 'find_callees']:
                if tool in adjusted:
                    old_priority, reason = adjusted[tool]
                    adjusted[tool] = (min(0.95, old_priority + 0.15), f'{reason} (functions found)')

        return adjusted

    def suggest_next_tool(
        self,
        question: str,
        available_tools: List[str],
        context: ExecutionContext
    ) -> Optional[ToolRecommendation]:
        """
        Suggest next tool based on what has been done.

        Args:
            question: User question
            available_tools: Available tools
            context: Execution context with history

        Returns:
            Next tool recommendation or None if done
        """
        # Check if we have enough information
        if self._should_stop(context):
            return None

        executed_names = [t.get('name') for t in context.executed_tools]
        remaining = [t for t in available_tools if t not in executed_names]

        if not remaining:
            return None

        # Build context summary
        gathered_info = self._summarize_context(context)

        # Try LLM suggestion
        suggestion = self._suggest_next_with_llm(question, remaining, context, gathered_info)
        if suggestion:
            return suggestion

        # Fallback: use priorities
        recommendations = self.select_tools_for_task(question, remaining, context)
        return recommendations[0] if recommendations else None

    def _should_stop(self, context: ExecutionContext) -> bool:
        """Determine if we have gathered enough information"""
        # Stop if confidence is high
        if context.confidence_level > 0.9:
            return True

        # Stop if we've used many tools
        if len(context.executed_tools) >= 8:
            return True

        # Stop if no remaining unknowns
        if not context.remaining_unknowns and context.key_findings:
            return True

        return False

    def _summarize_context(self, context: ExecutionContext) -> str:
        """Summarize execution context"""
        parts = []

        if context.discovered_files:
            parts.append(f"Files found: {', '.join(list(context.discovered_files)[:5])}")

        if context.discovered_functions:
            parts.append(f"Functions: {', '.join(list(context.discovered_functions)[:5])}")

        if context.key_findings:
            parts.append(f"Key findings: {'; '.join(context.key_findings[:3])}")

        if context.remaining_unknowns:
            parts.append(f"Still need: {'; '.join(context.remaining_unknowns[:3])}")

        return '\n'.join(parts) if parts else "No significant findings yet."

    def _suggest_next_with_llm(
        self,
        question: str,
        remaining_tools: List[str],
        context: ExecutionContext,
        gathered_info: str
    ) -> Optional[ToolRecommendation]:
        """Use LLM to suggest next tool"""
        prompt = f"""Based on analysis progress, suggest the next tool to use.

Question: {question}

Tools already used ({len(context.executed_tools)}):
{json.dumps([t.get('name') for t in context.executed_tools], indent=2)}

Information gathered:
{gathered_info}

Remaining tools: {remaining_tools}

Respond with JSON:
{{
    "tool_name": "name" or null if we have enough info,
    "params": {{}},
    "reason": "why this tool or why we're done",
    "expected_value": "what we expect to learn"
}}"""

        try:
            response = self.llm(
                prompt,
                system_prompt="You are a code analysis assistant selecting tools."
            )
            result = LLMResponseParser.safe_parse_llm_response(response, fallback=None)

            if result and result.get('tool_name'):
                tool_name = result['tool_name']
                if tool_name in remaining_tools:
                    return ToolRecommendation(
                        tool_name=tool_name,
                        confidence=0.8,
                        reason=result.get('reason', ''),
                        params=result.get('params', {}),
                        expected_output=result.get('expected_value', '')
                    )
        except Exception:
            pass

        return None
