"""
Validation Pipeline for CodeFusion

Responsible for validating claims, checking line numbers, and ensuring grounding.
All validation logic is config-driven and language-agnostic.
"""

from typing import Dict, List, Any, Optional
import re

from cf.agents.utils import calculate_word_count_targets
from cf.agents.pipelines.validators.base import ValidationIssue, ValidationResult
from cf.agents.pipelines.validators.structural import StructuralValidator
from cf.agents.pipelines.validators.content import ContentValidator
from cf.agents.pipelines.validators.fact_verifier import FactVerifier
from cf.agents.pipelines.validators.scorer import ValidationScorer


class ValidationPipeline:
    """
    Main validation pipeline that ensures answer quality.
    Validates claims, line numbers, and file paths.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], repo_tools, llm_client=None):
        self.repo_path = repo_path
        self.config = config
        self.repo_tools = repo_tools
        self.llm = llm_client  # Optional LLM for claim verification
        self.structural_validator = None  # Initialized per validation call with file_summaries

    def _get_file_path_pattern(self) -> str:
        """
        Build file path pattern from config (configurable for different repo structures).
        Returns regex pattern for matching source file paths.
        """
        validation_config = self.config.get('agents', {}).get('validation', {})
        prefixes = validation_config.get('file_path_prefixes', [
            'apps', 'src', 'lib', 'test', 'tests', 'cf', 'backend', 'frontend',
            'server', 'client', 'pkg', 'internal', 'cmd', 'api', 'core', 'services', 'components', 'modules'
        ])
        # Build pattern: (?:apps|src|lib|...)
        prefix_pattern = '|'.join(re.escape(p) for p in prefixes)
        return f'(?:{prefix_pattern})'

    def _get_max_file_line_gap(self) -> int:
        """Get max characters allowed between file path and line number reference."""
        validation_config = self.config.get('agents', {}).get('validation', {})
        return validation_config.get('max_file_line_gap_chars', 100)

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

            print(f"   {answer[:500]}...")
            print(f"   Total length: {len(answer)} chars, {len(answer.split())} words\n")

            issues = []

            # Initialize validators
            structural_validator = StructuralValidator(self.config, file_summaries)
            content_validator = ContentValidator(self.config)
            fact_verifier = FactVerifier(self.config, self.repo_tools, self.llm)
            scorer = ValidationScorer(self.config, structural_validator)

            # 1. Check line number references
            line_number_issues = structural_validator.validate_line_numbers(answer)
            issues.extend(line_number_issues)

            # 2. Check file path accuracy
            path_issues = structural_validator.validate_file_paths(answer)
            issues.extend(path_issues)

            # 3. Check grounding (claims backed by code)
            grounding_issues = content_validator.validate_grounding(answer)
            issues.extend(grounding_issues)

            # 4. Check for file hallucinations (CRITICAL anti-hallucination check)
            hallucination_issues = structural_validator.check_file_hallucination(answer)
            issues.extend(hallucination_issues)

            # 5. Check word count (narrative length)
            word_count_issues = content_validator.validate_word_count(answer, file_summaries)
            issues.extend(word_count_issues)

            # 6. Verify facts against actual code (anti-hallucination)
            fact_issues = fact_verifier.verify_facts(answer, file_summaries)
            issues.extend(fact_issues)

            # Calculate scores
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            min_certainty = thresholds.get('min_analysis_certainty', 0.7)
            min_line_coverage = thresholds.get('min_line_coverage', 0.5)
            min_path_accuracy = thresholds.get('min_path_accuracy', 0.9)

            grounding_score = scorer.calculate_grounding_score(answer, file_summaries)
            line_coverage = scorer.calculate_line_coverage(answer)
            path_accuracy = scorer.calculate_path_accuracy(answer, file_summaries)

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

            # DEBUG: Print all validation issues
            if issues:
                error_issues = [i for i in issues if i.severity == 'error']
                warning_issues = [i for i in issues if i.severity == 'warning']

                if error_issues:
                    print(f"   ❌ ERRORS ({len(error_issues)}):")
                    for i, issue in enumerate(error_issues[:10], 1):  # Show first 10 errors
                        location = f" at {issue.file_path}:{issue.line_number}" if issue.file_path else ""
                        print(f"      {i}. [{issue.issue_type}]{location}")
                        print(f"         {issue.message[:150]}")

                if warning_issues:
                    print(f"   ⚠️  WARNINGS ({len(warning_issues)}):")
                    for i, issue in enumerate(warning_issues[:5], 1):  # Show first 5 warnings
                        location = f" at {issue.file_path}:{issue.line_number}" if issue.file_path else ""
                        print(f"      {i}. [{issue.issue_type}]{location}")
                        print(f"         {issue.message[:150]}")

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
