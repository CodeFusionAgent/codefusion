"""
Discovery Module for CodeFusion

Consolidated file discovery strategies organized by approach:
- Semantic: Graph queries and embedding-based search
- Syntactic: Keyword and content-based search
- LLM-based: AI-powered domain detection and fallback
"""

from cf.agents.discovery.base import DiscoveryStrategy
from cf.agents.discovery.semantic import GraphQueryStrategy, SemanticSearchStrategy
from cf.agents.discovery.syntactic import KeywordMatchingStrategy, GrepSearchStrategy
from cf.agents.discovery.llm_based import DomainDetectionStrategy, FallbackStrategy

__all__ = [
    'DiscoveryStrategy',
    'GraphQueryStrategy',
    'SemanticSearchStrategy',
    'KeywordMatchingStrategy',
    'GrepSearchStrategy',
    'DomainDetectionStrategy',
    'FallbackStrategy',
]
