"""
Tool Selector Types - Enums and Data Classes for Tool Selection
"""

from enum import Enum
from typing import Dict, List, Any, Set
from dataclasses import dataclass, field


class QuestionCategory(Enum):
    """Categories of code analysis questions"""
    LOOKUP = "lookup"  # Finding specific code/files
    FLOW = "flow"  # Understanding execution flow
    ARCHITECTURE = "architecture"  # System structure
    EXPLANATION = "explanation"  # How/why something works
    COMPARISON = "comparison"  # Differences between things
    DEBUGGING = "debugging"  # Finding/fixing issues
    DOCUMENTATION = "documentation"  # API/usage docs
    PERFORMANCE = "performance"  # Optimization questions
    SECURITY = "security"  # Security-related queries
    REFACTORING = "refactoring"  # Code improvement


class Complexity(Enum):
    """Question complexity levels"""
    SIMPLE = "simple"  # Single file, direct answer
    MODERATE = "moderate"  # Multiple files, some reasoning
    COMPLEX = "complex"  # Cross-cutting, deep analysis
    EXPERT = "expert"  # Architecture-level, requires synthesis


@dataclass
class ToolRecommendation:
    """Recommendation for which tool to use"""
    tool_name: str
    confidence: float
    reason: str
    params: Dict[str, Any]
    priority: int = 0  # Execution order priority
    depends_on: List[str] = field(default_factory=list)  # Tool dependencies
    expected_output: str = ""  # What we expect to learn


@dataclass
class QuestionClassification:
    """Classification of a user question"""
    category: QuestionCategory
    complexity: Complexity
    needs_kb: bool  # Whether KB queries would be helpful
    needs_llm: bool  # Whether LLM analysis is needed
    needs_web: bool  # Whether external docs needed
    suggested_agents: List[str]
    key_concepts: List[str]  # Extracted technical concepts
    reasoning: str
    confidence: float = 0.8


@dataclass
class ToolChainPlan:
    """Plan for executing multiple tools in sequence"""
    tools: List[ToolRecommendation]
    strategy: str  # 'sequential', 'parallel', 'conditional'
    max_iterations: int
    stop_conditions: List[str]
    fallback_tools: List[str]
    estimated_complexity: Complexity


@dataclass
class ExecutionContext:
    """Context accumulated during tool execution"""
    question: str
    executed_tools: List[Dict[str, Any]] = field(default_factory=list)
    discovered_files: Set[str] = field(default_factory=set)
    discovered_functions: Set[str] = field(default_factory=set)
    discovered_classes: Set[str] = field(default_factory=set)
    key_findings: List[str] = field(default_factory=list)
    remaining_unknowns: List[str] = field(default_factory=list)
    confidence_level: float = 0.0
