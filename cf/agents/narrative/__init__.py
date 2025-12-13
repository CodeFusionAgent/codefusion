"""
Narrative Package - Synthesis Pipeline for Code Analysis

This package provides comprehensive narrative generation from code analysis:
- Synthesizes information from multiple agents
- Generates grounded technical narratives
- Validates and scores output quality
- Supports different narrative styles (life-of-X, architecture, etc.)
- Uses templates for consistent, high-quality output
"""

from .types import (
    NarrativeStyle,
    QualityLevel,
    NarrativeContext,
    NarrativeSection,
    NarrativeResult,
    NarrativeTemplate,
)
from .templates import NarrativeTemplates
from .builders import SectionBuilder, CrossFileAnalyzer
from .scoring import QualityScorer
from .generator import NarrativeGenerator
from .pipeline import SynthesisPipeline, ResultAggregator

__all__ = [
    # Types
    'NarrativeStyle',
    'QualityLevel',
    'NarrativeContext',
    'NarrativeSection',
    'NarrativeResult',
    'NarrativeTemplate',
    # Templates
    'NarrativeTemplates',
    # Builders
    'SectionBuilder',
    'CrossFileAnalyzer',
    # Scoring
    'QualityScorer',
    # Generator
    'NarrativeGenerator',
    # Pipeline
    'SynthesisPipeline',
    'ResultAggregator',
]
