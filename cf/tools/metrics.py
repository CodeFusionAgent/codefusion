"""
Tool Metrics Tracking

Per-tool token and cost tracking for experimentation.
Enables answering: "What's the cost breakdown per tool for this query?"
"""

import time
from typing import Dict, Any, List
from dataclasses import dataclass, field
from collections import defaultdict


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
