"""Knowledge base module for CodeFusion."""

from .content_analyzer import AnalyzedAnswer, ContentAnalyzer
from .knowledge_base import (
    C4Level,
    CodeEntity,
    CodeKB,
    CodeRelationship,
    create_knowledge_base,
)
from .relationship_detector import RelationshipDetector

__all__ = [
    "CodeKB",
    "CodeEntity",
    "CodeRelationship",
    "C4Level",
    "create_knowledge_base",
    "RelationshipDetector",
    "ContentAnalyzer",
    "AnalyzedAnswer"
]

# Vector KB is imported dynamically to avoid dependency issues
