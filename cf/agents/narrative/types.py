"""
Narrative Types - Enums and Data Classes for Narrative Generation
"""

from enum import Enum
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field

from cf.agents.validation import ValidationResult


class NarrativeStyle(Enum):
    """Supported narrative styles"""
    LIFE_OF_X = "life_of_x"  # Trace execution lifecycle
    ARCHITECTURE = "architecture"  # System structure overview
    EXPLANATION = "explanation"  # How something works
    COMPARISON = "comparison"  # Compare implementations
    TUTORIAL = "tutorial"  # Step-by-step guide
    DEBUG_TRACE = "debug_trace"  # Debugging walkthrough
    API_REFERENCE = "api_reference"  # API documentation style


class QualityLevel(Enum):
    """Quality levels for narrative output"""
    DRAFT = "draft"  # Quick, minimal validation
    STANDARD = "standard"  # Normal quality checks
    HIGH = "high"  # Comprehensive validation
    PUBLICATION = "publication"  # Maximum quality, multiple passes


@dataclass
class NarrativeContext:
    """Context for narrative generation"""
    question: str
    files_analyzed: List[str] = field(default_factory=list)
    file_summaries: Dict[str, Any] = field(default_factory=dict)
    agent_results: Dict[str, Any] = field(default_factory=dict)
    kb_insights: Dict[str, Any] = field(default_factory=dict)
    execution_traces: List[Dict[str, Any]] = field(default_factory=list)
    code_snippets: Dict[str, str] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    execution_time: float = 0.0


@dataclass
class NarrativeSection:
    """A section of the narrative"""
    title: str
    content: str
    file_references: List[str] = field(default_factory=list)
    code_snippets: List[Tuple[str, str]] = field(default_factory=list)  # (file, code)
    confidence: float = 0.8


@dataclass
class NarrativeResult:
    """Result of narrative generation"""
    narrative: str
    title: str
    summary: str
    sections: List[NarrativeSection]
    confidence: float
    validation: ValidationResult
    word_count: int
    files_referenced: List[str]
    code_references: List[Tuple[str, int]]  # (file, line_number)
    generation_time: float
    style: NarrativeStyle
    quality_score: float


@dataclass
class NarrativeTemplate:
    """Template for narrative generation"""
    style: NarrativeStyle
    prompt_template: str
    section_templates: Dict[str, str]
    required_sections: List[str]
    optional_sections: List[str]
    grounding_rules: List[str]
    min_code_references: int
    example_format: str
