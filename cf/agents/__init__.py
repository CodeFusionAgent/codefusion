"""Agents module for CodeFusion Pipeline Architecture."""

# Core Agents with ReAct Loop
from cf.agents.supervisor import SupervisorAgent
from cf.agents.base import BaseAgent, AgentState, ToolCall, ToolResult
from cf.agents.code import CodeAgent
from cf.agents.docs import DocsAgent
from cf.agents.web import WebAgent

# Session Management
from cf.agents.session import InteractiveSession, ContextManager

# Validation (anti-hallucination)
from cf.agents.validation import (
    ValidationIssue,
    ValidationResult,
    StructuralValidator,
    ContentValidator,
    FactVerifier,
    ValidationScorer,
    validate_answer,
)

# Tool Selection
from cf.agents.tool_selector import (
    LLMToolSelector,
    AgentRouter,
    QuestionClassification,
    ToolRecommendation,
    create_tool_selector,
    create_agent_router,
)

# Narrative Generation
from cf.agents.narrative import (
    NarrativeGenerator,
    SynthesisPipeline,
    NarrativeContext,
    NarrativeResult,
)

# File Analysis
from cf.agents.file_analyzer import (
    FileAnalyzer,
    FileInfo,
    FileSummary,
    FileRelevanceScorer,
    create_file_analyzer,
    create_relevance_scorer,
)

# Protocols (interfaces for loose coupling)
from cf.agents.protocols import (
    KnowledgeBaseProtocol,
    LLMClientProtocol,
    ToolRegistryProtocol,
    TracerProtocol,
    AgentRegistry,
    get_global_registry,
)

__all__ = [
    # Core Agents
    "SupervisorAgent",
    "BaseAgent",
    "AgentState",
    "ToolCall",
    "ToolResult",
    "CodeAgent",
    "DocsAgent",
    "WebAgent",

    # Session Management
    "InteractiveSession",
    "ContextManager",

    # Validation
    "ValidationIssue",
    "ValidationResult",
    "StructuralValidator",
    "ContentValidator",
    "FactVerifier",
    "ValidationScorer",
    "validate_answer",

    # Tool Selection
    "LLMToolSelector",
    "AgentRouter",
    "QuestionClassification",
    "ToolRecommendation",
    "create_tool_selector",
    "create_agent_router",

    # Narrative Generation
    "NarrativeGenerator",
    "SynthesisPipeline",
    "NarrativeContext",
    "NarrativeResult",

    # File Analysis
    "FileAnalyzer",
    "FileInfo",
    "FileSummary",
    "FileRelevanceScorer",
    "create_file_analyzer",
    "create_relevance_scorer",

    # Protocols
    "KnowledgeBaseProtocol",
    "LLMClientProtocol",
    "ToolRegistryProtocol",
    "TracerProtocol",
    "AgentRegistry",
    "get_global_registry",
]
