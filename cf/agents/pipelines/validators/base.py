"""
Base types for validation

Defines data structures used across all validators.
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    severity: str  # 'error', 'warning', 'info'
    issue_type: str  # 'missing_line_numbers', 'invalid_path', 'ungrounded_claim'
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class ValidationResult:
    """Result of validation process"""
    valid: bool
    issues: List[ValidationIssue]
    grounding_score: float
    line_number_coverage: float
    path_accuracy: float
