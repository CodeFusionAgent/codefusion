"""
Tool Selector Package - Intelligent Tool Selection for Agents

This package provides LLM-based tool selection capabilities:
- Classifies questions to determine optimal tool sets
- Plans multi-step tool chains for complex queries
- Selects relevant tools based on question context
- Routes questions to appropriate agents
- Provides tool recommendation with confidence scores
- Tracks tool execution context for informed decisions
"""

from .types import (
    QuestionCategory,
    Complexity,
    ToolRecommendation,
    QuestionClassification,
    ToolChainPlan,
    ExecutionContext,
)
from .classification import QuestionClassifier
from .planning_selection import LLMToolSelector
from .routing_execution import (
    AgentRouter,
    ToolExecutionPlanner,
    create_tool_selector,
    create_agent_router,
    create_execution_planner,
)

__all__ = [
    # Types
    'QuestionCategory',
    'Complexity',
    'ToolRecommendation',
    'QuestionClassification',
    'ToolChainPlan',
    'ExecutionContext',
    # Classification
    'QuestionClassifier',
    # Planning and Selection
    'LLMToolSelector',
    # Routing and Execution
    'AgentRouter',
    'ToolExecutionPlanner',
    # Factory functions
    'create_tool_selector',
    'create_agent_router',
    'create_execution_planner',
]
