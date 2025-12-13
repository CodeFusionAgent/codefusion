"""
Narrative Scoring - Quality Assessment for Generated Narratives
"""

import re
from typing import Dict, Any, Tuple

from cf.agents.validation import ValidationResult
from .types import NarrativeContext


class QualityScorer:
    """Scores narrative quality"""

    # Quality criteria weights
    CRITERIA_WEIGHTS = {
        'grounding': 0.3,  # File/line references
        'completeness': 0.2,  # Coverage of question
        'coherence': 0.2,  # Logical flow
        'code_evidence': 0.2,  # Code snippets
        'accuracy': 0.1,  # Factual correctness
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def score(
        self,
        narrative: str,
        context: NarrativeContext,
        validation: ValidationResult
    ) -> Tuple[float, Dict[str, float]]:
        """Score narrative quality"""
        scores = {}

        # Grounding score - file/line references
        scores['grounding'] = self._score_grounding(narrative, context)

        # Completeness score
        scores['completeness'] = self._score_completeness(narrative, context)

        # Coherence score
        scores['coherence'] = self._score_coherence(narrative)

        # Code evidence score
        scores['code_evidence'] = self._score_code_evidence(narrative)

        # Accuracy from validation
        scores['accuracy'] = validation.grounding_score if validation else 0.5

        # Weighted total
        total = sum(
            scores[criterion] * weight
            for criterion, weight in self.CRITERIA_WEIGHTS.items()
        )

        return total, scores

    def _score_grounding(self, narrative: str, context: NarrativeContext) -> float:
        """Score based on file/line references"""
        # Count file references
        file_patterns = [
            r'`[^`]+\.(py|js|ts|java|go|rs|cpp|c|h)`',
            r'\b\w+\.(py|js|ts|java|go|rs|cpp|c|h)\b',
        ]

        references = 0
        for pattern in file_patterns:
            references += len(re.findall(pattern, narrative))

        # Count line number references
        line_patterns = [
            r'line\s+\d+',
            r':\d+\b',
            r'lines?\s+\d+[-–]\d+',
        ]

        line_refs = 0
        for pattern in line_patterns:
            line_refs += len(re.findall(pattern, narrative, re.IGNORECASE))

        # Score based on reference density
        word_count = len(narrative.split())
        ref_density = (references + line_refs) / max(word_count / 100, 1)

        return min(1.0, ref_density * 0.5)

    def _score_completeness(self, narrative: str, context: NarrativeContext) -> float:
        """Score based on coverage of the question"""
        question_words = set(context.question.lower().split())
        question_words -= {'how', 'what', 'where', 'when', 'why', 'the', 'a', 'an', 'is', 'are', 'does'}

        narrative_words = set(narrative.lower().split())

        if not question_words:
            return 0.5

        coverage = len(question_words & narrative_words) / len(question_words)
        return min(1.0, coverage * 1.2)

    def _score_coherence(self, narrative: str) -> float:
        """Score based on logical structure"""
        # Check for section headers
        headers = len(re.findall(r'^#{1,3}\s+\w+', narrative, re.MULTILINE))

        # Check for lists
        lists = len(re.findall(r'^\s*[-*]\s+\w+', narrative, re.MULTILINE))

        # Check for code blocks
        code_blocks = len(re.findall(r'```', narrative))

        # Structural elements suggest coherence
        structural_score = min(1.0, (headers * 0.2 + lists * 0.1 + code_blocks * 0.15))

        # Check paragraph structure
        paragraphs = narrative.split('\n\n')
        avg_paragraph_length = sum(len(p.split()) for p in paragraphs) / max(len(paragraphs), 1)

        # Reasonable paragraph length (20-100 words)
        length_score = 1.0 if 20 <= avg_paragraph_length <= 100 else 0.5

        return (structural_score + length_score) / 2

    def _score_code_evidence(self, narrative: str) -> float:
        """Score based on code snippets included"""
        # Count code blocks
        code_blocks = re.findall(r'```[\s\S]*?```', narrative)
        num_blocks = len(code_blocks)

        # Check code block quality
        quality_score = 0
        for block in code_blocks:
            # Has language specified
            if re.match(r'```\w+', block):
                quality_score += 0.2
            # Has reasonable length
            lines = block.count('\n')
            if 3 <= lines <= 30:
                quality_score += 0.2

        return min(1.0, num_blocks * 0.2 + quality_score * 0.5)
