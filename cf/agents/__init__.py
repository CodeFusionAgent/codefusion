"""Agents module for CodeFusion Pipeline Architecture."""

# Pipeline Architecture Agents
from cf.agents.supervisor import SupervisorAgent
from cf.agents.docs import DocsAgent
from cf.agents.code_orchestrator import CodeOrchestrator
from cf.agents.web import WebAgent

__all__ = [
    "SupervisorAgent",
    "DocsAgent",
    "CodeOrchestrator",
    "WebAgent"
]
