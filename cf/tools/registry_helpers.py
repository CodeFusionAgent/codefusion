"""
Registry Support Utilities for CodeFusion

This module provides helper utilities for the ToolRegistry:
1. ToolNameResolver - Dynamic tool name resolution with fallback strategies
2. ToolMetricsTracker - Per-tool token and cost tracking for experimentation

Both utilities support the ToolRegistry's core functionality.
"""

import time
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict


# ============================================================================
# Metrics Tracking (from metrics.py)
# ============================================================================

@dataclass
class ToolCall:
    """Record of a single tool call"""
    tool_name: str
    timestamp: float
    duration: float
    success: bool
    tokens_used: int = 0
    cost_estimate: float = 0.0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolMetricsTracker:
    """
    Track per-tool metrics for cost and performance analysis.

    Enables A/B testing by tracking:
    - Tokens used per tool
    - Cost per tool
    - Call frequency
    - Success rate
    """

    def __init__(self):
        self.tool_calls: List[ToolCall] = []
        self._metrics_by_tool: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'calls': 0,
            'successes': 0,
            'failures': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'total_time': 0.0
        })

    def record_call(
        self,
        tool_name: str,
        duration: float,
        success: bool,
        tokens: int = 0,
        cost: float = 0.0,
        error: str = "",
        metadata: Dict[str, Any] = None
    ):
        """
        Record a tool call.

        Args:
            tool_name: Name of tool called
            duration: Time taken in seconds
            success: Whether call succeeded
            tokens: Tokens used (if LLM tool)
            cost: Estimated cost in dollars
            error: Error message if failed
            metadata: Additional metadata
        """
        call = ToolCall(
            tool_name=tool_name,
            timestamp=time.time(),
            duration=duration,
            success=success,
            tokens_used=tokens,
            cost_estimate=cost,
            error=error,
            metadata=metadata or {}
        )

        self.tool_calls.append(call)

        # Update aggregates
        metrics = self._metrics_by_tool[tool_name]
        metrics['calls'] += 1
        metrics['total_time'] += duration
        metrics['total_tokens'] += tokens
        metrics['total_cost'] += cost

        if success:
            metrics['successes'] += 1
        else:
            metrics['failures'] += 1

    def get_tool_metrics(self, tool_name: str) -> Dict[str, Any]:
        """
        Get metrics for a specific tool.

        Args:
            tool_name: Tool to get metrics for

        Returns:
            Dictionary with metrics
        """
        if tool_name not in self._metrics_by_tool:
            return {'error': 'Tool not found'}

        metrics = self._metrics_by_tool[tool_name]

        return {
            'tool_name': tool_name,
            'total_calls': metrics['calls'],
            'success_rate': metrics['successes'] / metrics['calls'] if metrics['calls'] > 0 else 0,
            'total_tokens': metrics['total_tokens'],
            'total_cost': metrics['total_cost'],
            'total_time': metrics['total_time'],
            'avg_time_per_call': metrics['total_time'] / metrics['calls'] if metrics['calls'] > 0 else 0,
            'avg_tokens_per_call': metrics['total_tokens'] / metrics['calls'] if metrics['calls'] > 0 else 0,
            'avg_cost_per_call': metrics['total_cost'] / metrics['calls'] if metrics['calls'] > 0 else 0
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for all tools.

        Returns:
            Dictionary mapping tool names to their metrics
        """
        return {
            tool_name: self.get_tool_metrics(tool_name)
            for tool_name in self._metrics_by_tool.keys()
        }

    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall summary across all tools.

        Returns:
            Summary dictionary
        """
        total_calls = sum(m['calls'] for m in self._metrics_by_tool.values())
        total_tokens = sum(m['total_tokens'] for m in self._metrics_by_tool.values())
        total_cost = sum(m['total_cost'] for m in self._metrics_by_tool.values())
        total_time = sum(m['total_time'] for m in self._metrics_by_tool.values())

        # Find most expensive tools
        tools_by_cost = sorted(
            [(name, m['total_cost']) for name, m in self._metrics_by_tool.items()],
            key=lambda x: x[1],
            reverse=True
        )

        # Find most used tools
        tools_by_calls = sorted(
            [(name, m['calls']) for name, m in self._metrics_by_tool.items()],
            key=lambda x: x[1],
            reverse=True
        )

        return {
            'total_tool_calls': total_calls,
            'unique_tools_used': len(self._metrics_by_tool),
            'total_tokens_used': total_tokens,
            'total_cost': total_cost,
            'total_time': total_time,
            'most_expensive_tools': tools_by_cost[:5],
            'most_used_tools': tools_by_calls[:5]
        }

    def get_cost_breakdown(self) -> List[Dict[str, Any]]:
        """
        Get cost breakdown by tool.

        Returns:
            List of tools sorted by cost
        """
        breakdown = []

        for tool_name, metrics in self._metrics_by_tool.items():
            breakdown.append({
                'tool_name': tool_name,
                'total_cost': metrics['total_cost'],
                'calls': metrics['calls'],
                'cost_per_call': metrics['total_cost'] / metrics['calls'] if metrics['calls'] > 0 else 0,
                'tokens': metrics['total_tokens']
            })

        # Sort by cost descending
        breakdown.sort(key=lambda x: x['total_cost'], reverse=True)

        return breakdown

    def reset(self):
        """Reset all metrics"""
        self.tool_calls = []
        self._metrics_by_tool = defaultdict(lambda: {
            'calls': 0,
            'successes': 0,
            'failures': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'total_time': 0.0
        })

    def export_for_eval(self) -> Dict[str, Any]:
        """
        Export metrics in format suitable for evaluation.

        Returns:
            Dictionary with metrics for evaluation
        """
        return {
            'summary': self.get_summary(),
            'by_tool': self.get_all_metrics(),
            'cost_breakdown': self.get_cost_breakdown(),
            'total_calls': len(self.tool_calls)
        }


# ============================================================================
# Tool Name Resolution (from resolver.py)
# ============================================================================

class ToolNameResolver:
    """
    Resolves tool names using multiple fallback strategies.

    Handles:
    - Exact name matches
    - Suffix matches (e.g., 'find_files' → 'kb_find_files')
    - Substring matches
    - Special case handling for common patterns
    """

    def resolve(self, tool_name: str, available_tools: Dict[str, Callable]) -> Optional[str]:
        """
        Resolve tool name to actual registered name.

        Args:
            tool_name: Tool name to resolve
            available_tools: Dictionary of available tools

        Returns:
            Resolved tool name if found, None otherwise

        Resolution Strategy:
        1. Exact match (fastest path)
        2. Suffix match (handles agent-prefixed tools)
        3. Special case matching (e.g., KB discovery suffix)
        4. Substring match (fallback)
        """
        # Fast path: exact match
        if tool_name in available_tools:
            return tool_name

        # Try resolution strategies
        try:
            keys = list(available_tools.keys())
            candidates = self._find_candidates(tool_name, keys)

            # Return if we found exactly one match
            if len(candidates) == 1:
                return candidates[0]

            # Multiple candidates or no candidates - return None
            return None

        except (KeyError, AttributeError, TypeError) as e:
            print(f"⚠️ [RESOLVER] Tool resolution error for '{tool_name}': {e}")
            return None
        except Exception as e:
            print(f"⚠️ [RESOLVER] Unexpected error resolving tool '{tool_name}': {e}")
            return None

    def _find_candidates(self, tool_name: str, available_keys: List[str]) -> List[str]:
        """
        Find candidate tool names using multiple strategies.

        Args:
            tool_name: Tool name to search for
            available_keys: List of available tool names

        Returns:
            List of candidate matches
        """
        candidates = []

        # Strategy 1: Exact suffix match (common pattern for agent-prefixed tools)
        # E.g., 'semantic_search' → 'structural_kb_semantic_search'
        candidates = [n for n in available_keys if n.endswith(tool_name)]
        if candidates:
            return candidates

        # Strategy 2: Special case for common KB discovery tool suffix
        # Handles the pattern where multiple agents might have 'find_files_for_question'
        if tool_name.endswith('_find_files_for_question'):
            suffix = '_find_files_for_question'
            candidates = [n for n in available_keys if n.endswith(suffix)]
            if candidates:
                return candidates

        # Strategy 3: Substring match (fallback)
        # E.g., 'find_files' matches 'kb_find_files_for_question'
        candidates = [n for n in available_keys if tool_name in n]

        return candidates

    def get_resolution_error(self, tool_name: str, available_tools: Dict[str, Callable]) -> Dict:
        """
        Generate helpful error message for unresolved tool.

        Args:
            tool_name: Tool name that failed to resolve
            available_tools: Dictionary of available tools

        Returns:
            Error dictionary with helpful information
        """
        # Find similar tool names for suggestions
        similar_tools = self._find_similar_tools(tool_name, list(available_tools.keys()))

        error_msg = f'Tool "{tool_name}" not found'

        if similar_tools:
            error_msg += f'. Did you mean: {", ".join(similar_tools[:3])}?'

        return {
            'error': error_msg,
            'similar_tools': similar_tools[:5],
            'available_tools': list(available_tools.keys())
        }

    def _find_similar_tools(self, tool_name: str, available_keys: List[str]) -> List[str]:
        """
        Find tool names similar to the requested name.

        Uses simple substring matching for suggestions.

        Args:
            tool_name: Tool name to search for
            available_keys: List of available tool names

        Returns:
            List of similar tool names
        """
        # Split tool_name into words and find tools containing those words
        words = tool_name.replace('_', ' ').split()

        similar = []
        for key in available_keys:
            # Check if any word from tool_name is in the available key
            if any(word in key for word in words if len(word) > 2):
                similar.append(key)

        return sorted(similar)  # Sort for consistency
