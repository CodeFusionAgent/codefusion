"""
Semantic Knowledge Layer

Provides vector embeddings and semantic search for code:
- Function/class embedding generation
- Semantic similarity search
- Code-to-code similarity
- Natural language to code search
"""

from cf.knowledge.semantic.embeddings import CodeEmbedder, EmbeddingModel
from cf.knowledge.semantic.similarity import SemanticSearch

__all__ = [
    "CodeEmbedder",
    "EmbeddingModel",
    "SemanticSearch"
]
