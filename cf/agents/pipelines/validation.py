"""
Validation Pipeline for CodeFusion

Responsible for validating claims, checking line numbers, and ensuring grounding.
All validation logic is config-driven and language-agnostic.
"""

from typing import Dict, List, Any, Optional, Optional
from dataclasses import dataclass
import re


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


class ValidationPipeline:
    """
    Main validation pipeline that ensures answer quality.
    Validates claims, line numbers, and file paths.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], repo_tools):
        self.repo_path = repo_path
        self.config = config
        self.repo_tools = repo_tools

    def validate(self, answer: str, file_summaries: Dict[str, Any]) -> ValidationResult:
        """
        Validate generated answer for grounding and accuracy

        Args:
            answer: Generated answer text
            file_summaries: File summaries used to generate answer

        Returns:
            ValidationResult with issues and scores
        """
        try:
            print("✅ [VALIDATION] Validating answer...")

            issues = []

            # 1. Check line number references
            line_number_issues = self._validate_line_numbers(answer, file_summaries)
            issues.extend(line_number_issues)

            # 2. Check file path accuracy
            path_issues = self._validate_file_paths(answer, file_summaries)
            issues.extend(path_issues)

            # 3. Check grounding (claims backed by code)
            grounding_issues = self._validate_grounding(answer, file_summaries)
            issues.extend(grounding_issues)

            # Calculate scores
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            min_certainty = thresholds.get('min_analysis_certainty', 0.7)
            min_line_coverage = thresholds.get('min_line_coverage', 0.5)
            min_path_accuracy = thresholds.get('min_path_accuracy', 0.9)

            grounding_score = self._calculate_grounding_score(answer, file_summaries)
            line_coverage = self._calculate_line_coverage(answer)
            path_accuracy = self._calculate_path_accuracy(answer, file_summaries)

            # Determine if valid
            error_count = len([i for i in issues if i.severity == 'error'])
            valid = (error_count == 0 and
                    grounding_score >= min_certainty and
                    line_coverage >= min_line_coverage and
                    path_accuracy >= min_path_accuracy)

            print(f"📊 [VALIDATION] Scores:")
            print(f"   Grounding: {grounding_score:.2f}")
            print(f"   Line coverage: {line_coverage:.2f}")
            print(f"   Path accuracy: {path_accuracy:.2f}")
            print(f"   Issues: {len(issues)} ({error_count} errors)")

            return ValidationResult(
                valid=valid,
                issues=issues,
                grounding_score=grounding_score,
                line_number_coverage=line_coverage,
                path_accuracy=path_accuracy
            )

        except Exception as e:
            print(f"❌ [VALIDATION] Failed: {e}")
            return ValidationResult(
                valid=False,
                issues=[ValidationIssue('error', 'validation_failed', str(e))],
                grounding_score=0.0,
                line_number_coverage=0.0,
                path_accuracy=0.0
            )

    def _validate_line_numbers(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate line number references in answer"""
        issues = []

        # Extract line number references (e.g., "line 123", "lines 45-67", "L123")
        line_patterns = [
            r'line[s]?\s+(\d+)',
            r'L(\d+)',
            r'lines?\s+(\d+)-(\d+)',
            r'at\s+line\s+(\d+)'
        ]

        line_refs = []
        for pattern in line_patterns:
            matches = re.finditer(pattern, answer, re.IGNORECASE)
            for match in matches:
                if match.group(1):
                    line_refs.append(int(match.group(1)))

        if not line_refs:
            issues.append(ValidationIssue(
                severity='warning',
                issue_type='missing_line_numbers',
                message='Answer contains no line number references for grounding'
            ))

        # Check if line numbers are within valid ranges
        for file_path, summary in file_summaries.items():
            max_lines = summary.get('line_count', 0)
            for line_num in line_refs:
                if line_num > max_lines:
                    issues.append(ValidationIssue(
                        severity='error',
                        issue_type='invalid_line_number',
                        message=f'Line {line_num} exceeds file length ({max_lines} lines)',
                        file_path=file_path,
                        line_number=line_num
                    ))

        return issues

    def _validate_file_paths(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate file path references in answer"""
        issues = []

        # Extract file paths from answer (basic pattern matching)
        path_pattern = r'[\w/.-]+\.\w+'
        potential_paths = re.findall(path_pattern, answer)

        valid_paths = set(file_summaries.keys())

        for path in potential_paths:
            # Check if it's a real path mentioned in file_summaries
            if path not in valid_paths:
                # Check if it's a partial match
                matches = [vp for vp in valid_paths if path in vp or vp in path]
                if not matches:
                    issues.append(ValidationIssue(
                        severity='warning',
                        issue_type='unverified_path',
                        message=f'Path "{path}" not found in analyzed files',
                        file_path=path
                    ))

        return issues

    def _validate_grounding(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate that claims are grounded in code"""
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

    def _calculate_grounding_score(self, answer: str, file_summaries: Dict[str, Any]) -> float:
        """Calculate how well grounded the answer is"""
        # Count code references (line numbers, file paths, function names)
        line_refs = len(re.findall(r'line[s]?\s+\d+|L\d+', answer, re.IGNORECASE))
        path_refs = len(re.findall(r'[\w/.-]+\.\w+', answer))

        # Extract function/class names from summaries
        code_entities = set()
        for summary in file_summaries.values():
            if isinstance(summary, dict):
                functions = summary.get('functions', [])
                classes = summary.get('classes', [])
                code_entities.update([f.get('name', '') for f in functions if isinstance(f, dict)])
                code_entities.update([c.get('name', '') for c in classes if isinstance(c, dict)])

        # Count mentions of code entities
        entity_refs = sum(1 for entity in code_entities if entity and entity in answer)

        # Score based on references
        total_refs = line_refs + path_refs + entity_refs

        # Get thresholds from config
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        no_refs_score = thresholds.get('validation_no_refs_score', 0.3)
        refs_base_score = thresholds.get('validation_refs_base', 0.5)
        refs_increment = thresholds.get('validation_refs_increment', 0.05)

        if total_refs == 0:
            return no_refs_score  # Low score for no references

        # Normalize to 0-1 scale
        score = min(refs_base_score + (total_refs * refs_increment), 1.0)
        return score

    def _calculate_line_coverage(self, answer: str) -> float:
        """Calculate percentage of statements with line number references"""
        # Split answer into sentences
        sentences = re.split(r'[.!?]+', answer)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.0

        # Count sentences with line references
        line_pattern = r'line[s]?\s+\d+|L\d+|lines?\s+\d+-\d+'
        sentences_with_lines = sum(1 for s in sentences if re.search(line_pattern, s, re.IGNORECASE))

        return sentences_with_lines / len(sentences)

    def _calculate_path_accuracy(self, answer: str, file_summaries: Dict[str, Any]) -> float:
        """Calculate accuracy of file path references"""
        # Extract paths from answer
        path_pattern = r'[\w/.-]+\.\w+'
        mentioned_paths = re.findall(path_pattern, answer)

        if not mentioned_paths:
            return 1.0  # No paths = perfect accuracy (nothing to be wrong)

        valid_paths = set(file_summaries.keys())

        # Count correct paths
        correct = sum(1 for p in mentioned_paths if p in valid_paths)

        return correct / len(mentioned_paths)
