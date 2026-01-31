"""Agents module for CodeFusion Pipeline Architecture."""

# Core Agents with ReAct Loop
from cf.agents.supervisor import SupervisorAgent
from cf.agents.base import BaseAgent, AgentState, ToolCall, ToolResult, ThoroughnessLevel
from cf.agents.code import CodeAgent
from cf.agents.docs import DocsAgent
from cf.agents.web import WebAgent

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
from cf.agents.analyzer import (
    FileAnalyzer,
    FileInfo,
    FileSummary,
)
from cf.agents.scorer import create_file_analyzer

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
    "ThoroughnessLevel",
    "CodeAgent",
    "DocsAgent",
    "WebAgent",

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
    "create_file_analyzer",

    # Protocols
    "KnowledgeBaseProtocol",
    "LLMClientProtocol",
    "ToolRegistryProtocol",
    "TracerProtocol",
    "AgentRegistry",
    "get_global_registry",
]
