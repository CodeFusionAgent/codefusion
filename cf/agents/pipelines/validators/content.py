"""
Content Validator

Validates content quality of generated answers:
- Grounding in code (no uncertain language)
- Word count requirements
"""

from typing import Dict, List, Any
import re

from cf.agents.pipelines.validators.base import ValidationIssue
from cf.agents.utils import calculate_word_count_targets


class ContentValidator:
    """
    Validates content quality of generated answers.

    Ensures answers are properly grounded and meet length requirements.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize content validator.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def validate_grounding(self, answer: str) -> List[ValidationIssue]:
        """
        Validate that claims are grounded in code (no uncertain language).

        Checks for phrases like "probably", "might be", "I think", etc.

        Args:
            answer: Generated answer text

        Returns:
            List of validation issues
        """
        issues = []

        # Check for common ungrounded phrases
        ungrounded_patterns = [
            r'probably',
            r'might be',
            r'could be',
            r'I think',
            r'possibly',
            r'not sure'
        ]

        for pattern in ungrounded_patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                issues.append(ValidationIssue(
                    severity='warning',
                    issue_type='ungrounded_claim',
                    message=f'Answer contains uncertain language: "{pattern}"'
                ))

        return issues

    def validate_word_count(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """
        Validate narrative meets minimum word count requirement (proportional to file count).

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            List of validation issues
        """
        issues = []

        # Calculate word count targets using shared utility (ensures alignment with synthesis)
        file_count = len(file_summaries)
        target_min, target_max = calculate_word_count_targets(file_count, self.config)

        # Count words
        word_count = len(answer.split())

        # Get tolerance from config (default 0.83 = require at least 83% of minimum target)
        synthesis_thresholds = self.config.get('agents', {}).get('synthesis_thresholds', {})
        word_count_tolerance = synthesis_thresholds.get('word_count_tolerance', 0.83)
        min_acceptable = int(target_min * word_count_tolerance)

        if word_count < min_acceptable:
            issues.append(ValidationIssue(
                severity='error',
                issue_type='insufficient_word_count',
                message=f'Narrative too short: {word_count} words (minimum: {min_acceptable}, target: {target_min} for {file_count} files)'
            ))
            print(f"\n⚠️  [VALIDATION] Word count below minimum: {word_count} < {min_acceptable} (for {file_count} files)")
        elif word_count < target_min:
            # Warning if below target but above minimum threshold
            issues.append(ValidationIssue(
                severity='warning',
                issue_type='below_target_word_count',
                message=f'Narrative shorter than target: {word_count} words (target: {target_min} for {file_count} files)'
            ))

        return issues
