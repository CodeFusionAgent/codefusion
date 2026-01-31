"""
Tool Selector Routing - Simplified Factory Functions

Most routing/execution logic is now handled by the ReAct loop in BaseAgent.
This module provides factory functions for backward compatibility.
"""

from typing import Dict, Any, Callable

from .planning_selection import LLMToolSelector


# Factory function for backward compatibility
def create_tool_selector(llm_callback: Callable, config: Dict[str, Any]) -> LLMToolSelector:
    """Create a tool selector instance."""
    return LLMToolSelector(llm_callback, config)


# Kept for backward compatibility but deprecated
class AgentRouter:
    """Deprecated: Agent routing is now handled by ReAct loop."""

    def __init__(self, llm_callback: Callable, config: Dict[str, Any]):
        self.selector = LLMToolSelector(llm_callback, config)

    def route_question(self, question: str) -> Dict[str, Any]:
        """Route question - returns classification as routing info."""
        classification = self.selector.classify_question(question)
        return {
            'agents': classification.suggested_agents,
            'classification': {
                'category': classification.category.value,
                'complexity': classification.complexity.value,
                'key_concepts': classification.key_concepts,
            },
            'confidence': classification.confidence,
        }


class ToolExecutionPlanner:
    """Deprecated: Execution planning is now handled by ReAct loop."""

    def __init__(self, tool_selector: LLMToolSelector):
        self.selector = tool_selector

    def create_execution_plan(self, question: str, available_tools: list, max_parallel: int = 3):
        """Returns minimal plan - actual planning done by ReAct loop."""
        classification = self.selector.classify_question(question)
        return {
            'phases': [],
            'strategy': 'react_loop',
            'complexity': classification.complexity.value,
        }


def create_agent_router(llm_callback: Callable, config: Dict[str, Any]) -> AgentRouter:
    """Create an agent router instance."""
    return AgentRouter(llm_callback, config)


def create_execution_planner(llm_callback: Callable, config: Dict[str, Any]) -> ToolExecutionPlanner:
    """Create an execution planner instance."""
    return ToolExecutionPlanner(LLMToolSelector(llm_callback, config))
