"""Knowledge base module for CodeFusion."""

from .knowledge_base import CodeKB, CodeEntity, CodeRelationship, C4Level, create_knowledge_base
from .relationship_detector import RelationshipDetector
from .content_analyzer import ContentAnalyzer, AnalyzedAnswer

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