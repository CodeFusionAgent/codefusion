"""
Validation Module - Anti-hallucination and Grounding Validation

This module provides comprehensive validation for generated answers:
- Structural validation (line numbers, file paths)
- Content validation (grounding, word count)
- Fact verification (claims against actual code)
- Scoring (grounding score, line coverage, path accuracy)
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re

from cf.agents.utils import calculate_word_count_targets


# =============================================================================
# Data Structures
# =============================================================================

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


# =============================================================================
# Structural Validator
# =============================================================================

class StructuralValidator:
    """
    Validates structural references in generated answers.

    Ensures line numbers are valid, file paths are accurate,
    and detects hallucinated file references.
    """

    def __init__(self, config: Dict[str, Any], file_summaries: Dict[str, Any]):
        """
        Initialize structural validator.

        Args:
            config: Configuration dictionary
            file_summaries: File summaries from code analysis
        """
        self.config = config
        self.file_summaries = file_summaries

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
        prefix_pattern = '|'.join(re.escape(p) for p in prefixes)
        return f'(?:{prefix_pattern})'

    def _get_max_file_line_gap(self) -> int:
        """Get max characters allowed between file path and line number reference."""
        validation_config = self.config.get('agents', {}).get('validation', {})
        return validation_config.get('max_file_line_gap_chars', 100)

    def validate_line_numbers(self, answer: str) -> List[ValidationIssue]:
        """
        Validate line number references in answer.

        Args:
            answer: Generated answer text

        Returns:
            List of validation issues
        """
        issues = []

        path_pattern = self._get_file_path_pattern()
        max_gap = self._get_max_file_line_gap()
        file_line_pattern = rf'({path_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt)).{{0,{max_gap}}}?(?:line[s]?\s+|L|at\s+line\s+)(\d+)'

        file_line_refs = re.findall(file_line_pattern, answer, re.IGNORECASE | re.DOTALL)

        if not file_line_refs:
            line_pattern = r'line[s]?\s+\d+|L\d+|at\s+line\s+\d+'
            if not re.search(line_pattern, answer, re.IGNORECASE):
                issues.append(ValidationIssue(
                    severity='warning',
                    issue_type='missing_line_numbers',
                    message='Answer contains no line number references for grounding'
                ))
            return issues

        invalid_count = 0
        for file_path, line_num_str in file_line_refs:
            line_num = int(line_num_str)

            matching_file = None
            if file_path in self.file_summaries:
                matching_file = file_path
            else:
                for summary_path in self.file_summaries.keys():
                    if file_path in summary_path or summary_path in file_path:
                        matching_file = summary_path
                        break

            if matching_file:
                summary = self.file_summaries[matching_file]
                max_lines = summary.get('line_count', 0)

                if max_lines > 0 and line_num > max_lines:
                    issues.append(ValidationIssue(
                        severity='error',
                        issue_type='invalid_line_number',
                        message=f'Line {line_num} exceeds file length ({max_lines} lines)',
                        file_path=matching_file,
                        line_number=line_num
                    ))
                    invalid_count += 1

        return issues

    def validate_file_paths(self, answer: str) -> List[ValidationIssue]:
        """
        Validate file path references in answer.

        Args:
            answer: Generated answer text

        Returns:
            List of validation issues
        """
        issues = []

        prefix_pattern = self._get_file_path_pattern()
        path_pattern = rf'\b{prefix_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt)\b'
        potential_paths = re.findall(path_pattern, answer)

        valid_paths = set(self.file_summaries.keys())

        for path in potential_paths:
            if path not in valid_paths:
                matches = [vp for vp in valid_paths if path in vp or vp in path]
                if not matches:
                    issues.append(ValidationIssue(
                        severity='warning',
                        issue_type='unverified_path',
                        message=f'Path "{path}" not found in analyzed files',
                        file_path=path
                    ))

        return issues

    def check_file_hallucination(self, answer: str) -> List[ValidationIssue]:
        """
        Check if narrative mentions files that were NOT analyzed (hallucination detection).

        Args:
            answer: Generated answer text

        Returns:
            List of validation issues
        """
        issues = []

        all_file_refs = re.findall(r'\b(\w+(?:/\w+)*\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt))\b', answer)

        prefix_pattern = self._get_file_path_pattern()
        full_path_refs = re.findall(
            rf'\b({prefix_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt))\b',
            answer
        )

        all_mentioned_files = set(all_file_refs + full_path_refs)
        analyzed_files = set(self.file_summaries.keys())

        for mentioned_file in all_mentioned_files:
            is_analyzed = mentioned_file in analyzed_files

            if not is_analyzed:
                basenames = [fp.split('/')[-1] for fp in analyzed_files]
                is_analyzed = mentioned_file in basenames or any(mentioned_file in fp for fp in analyzed_files)

            if not is_analyzed:
                issues.append(ValidationIssue(
                    severity='error',
                    issue_type='file_hallucination',
                    message=f'Narrative references "{mentioned_file}" which was NOT analyzed.',
                    file_path=mentioned_file
                ))

        return issues


# =============================================================================
# Content Validator
# =============================================================================

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

        Args:
            answer: Generated answer text

        Returns:
            List of validation issues
        """
        issues = []

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
        Validate narrative meets minimum word count requirement.

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            List of validation issues
        """
        issues = []

        file_count = len(file_summaries)
        target_min, target_max = calculate_word_count_targets(file_count, self.config)

        word_count = len(answer.split())

        synthesis_thresholds = self.config.get('agents', {}).get('synthesis_thresholds', {})
        word_count_tolerance = synthesis_thresholds.get('word_count_tolerance', 0.83)
        min_acceptable = int(target_min * word_count_tolerance)

        if word_count < min_acceptable:
            issues.append(ValidationIssue(
                severity='error',
                issue_type='insufficient_word_count',
                message=f'Narrative too short: {word_count} words (minimum: {min_acceptable}, target: {target_min} for {file_count} files)'
            ))
        elif word_count < target_min:
            issues.append(ValidationIssue(
                severity='warning',
                issue_type='below_target_word_count',
                message=f'Narrative shorter than target: {word_count} words (target: {target_min} for {file_count} files)'
            ))

        return issues


# =============================================================================
# Fact Verifier
# =============================================================================

class FactVerifier:
    """
    Verifies factual claims against actual code (anti-hallucination).

    Reads actual code and cross-checks claims to prevent LLM hallucinations.
    """

    def __init__(self, config: Dict[str, Any], repo_tools, llm_client=None):
        """
        Initialize fact verifier.

        Args:
            config: Configuration dictionary
            repo_tools: Repository tools for reading files
            llm_client: Optional LLM client for complex verification
        """
        self.config = config
        self.repo_tools = repo_tools
        self.llm = llm_client

    def verify_facts(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """
        Verify claims in the answer against actual code.

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            List of validation issues
        """
        issues = []

        validation_config = self.config.get('agents', {}).get('validation', {})
        enable_fact_check = validation_config.get('enable_fact_verification', True)
        max_claims_to_verify = validation_config.get('max_claims_to_verify', 20)

        if not enable_fact_check:
            return issues

        line_ref_issues = self._verify_line_referenced_claims(answer, file_summaries, max_claims_to_verify)
        issues.extend(line_ref_issues)

        arch_issues = self._verify_architectural_claims(answer, file_summaries)
        issues.extend(arch_issues)

        return issues

    def _verify_line_referenced_claims(self, answer: str, file_summaries: Dict[str, Any], max_claims: int) -> List[ValidationIssue]:
        """Verify claims that have line references."""
        issues = []

        claim_pattern = r'([^.!?]+(?:line[s]?\s+\d+|L\d+|at\s+line\s+\d+)[^.!?]*[.!?])'
        claims_with_lines = re.findall(claim_pattern, answer, re.IGNORECASE)

        claims_to_verify = claims_with_lines[:max_claims]

        for claim in claims_to_verify:
            path_match = re.search(r'([\w/.-]+\.py)', claim)

            if not path_match:
                claim_start = answer.find(claim)
                if claim_start > 0:
                    validation_config = self.config.get('agents', {}).get('validation', {})
                    context_chars = validation_config.get('claim_context_chars', 200)
                    context_start = max(0, claim_start - context_chars)
                    context = answer[context_start:claim_start]
                    path_match = re.search(r'([\w/.-]+\.py)', context)

            if not path_match:
                continue

            file_path = path_match.group(1)

            if file_path not in file_summaries:
                matching_files = [f for f in file_summaries.keys() if file_path in f or f in file_path]
                if not matching_files:
                    continue
                file_path = matching_files[0]

            line_match = re.search(r'(?:line[s]?\s+|L)(\d+)', claim, re.IGNORECASE)
            if not line_match:
                continue

            line_num = int(line_match.group(1))

            validation_config = self.config.get('agents', {}).get('validation', {})
            context_lines = validation_config.get('line_verification_context', 5)
            code_context = self._read_code_at_line(file_path, line_num, context_lines=context_lines)

            if not code_context:
                issues.append(ValidationIssue(
                    severity='warning',
                    issue_type='unverifiable_claim',
                    message=f'Cannot verify claim - unable to read {file_path}:{line_num}',
                    file_path=file_path,
                    line_number=line_num
                ))
                continue

            is_valid = self._verify_claim_against_code(claim, code_context, file_summaries.get(file_path, {}))

            if not is_valid:
                issues.append(ValidationIssue(
                    severity='error',
                    issue_type='fact_check_failed',
                    message=f'Claim may be inaccurate: "{claim[:100]}..." at {file_path}:{line_num}',
                    file_path=file_path,
                    line_number=line_num
                ))

        return issues

    def _verify_architectural_claims(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """Verify architectural and pattern claims WITHOUT line references."""
        issues = []

        arch_patterns = [
            r'(system|architecture|design|codebase)[^.!?]*(?:uses?|implements?|follows?|employs?)[^.!?]*[.!?]',
            r'(?:uses?|implements?|follows?|employs?)[^.!?]*(?:pattern|principle|architecture)[^.!?]*[.!?]',
            r'(?:singleton|factory|observer|strategy|decorator|adapter|mvc|microservice)[^.!?]*[.!?]'
        ]

        arch_claims = []
        for pattern in arch_patterns:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            arch_claims.extend(matches)

        validation_config = self.config.get('agents', {}).get('validation', {})
        max_claims = validation_config.get('max_architectural_claims', 10)
        arch_claims = list(set(arch_claims))[:max_claims]

        if not arch_claims:
            return issues

        all_insights = []
        all_patterns = set()

        for file_path, summary in file_summaries.items():
            if isinstance(summary, dict):
                insights = summary.get('architectural_insights', '')
                if insights:
                    all_insights.append(insights.lower())

                features = summary.get('key_features', [])
                if isinstance(features, list):
                    all_insights.extend([f.lower() for f in features if isinstance(f, str)])

        pattern_keywords = {
            'singleton': ['singleton', 'single instance', 'global instance'],
            'factory': ['factory', 'creates', 'builder', 'constructor'],
            'observer': ['observer', 'listener', 'subscriber', 'event', 'callback'],
            'strategy': ['strategy', 'algorithm', 'policy'],
            'decorator': ['decorator', 'wrapper', 'enhance'],
            'adapter': ['adapter', 'wrapper', 'interface'],
            'mvc': ['model', 'view', 'controller', 'mvc'],
            'microservice': ['microservice', 'service', 'api'],
            'repository': ['repository', 'data access', 'dao'],
            'dependency injection': ['injection', 'dependency', 'inject']
        }

        insights_text = ' '.join(all_insights)
        for pattern_name, keywords in pattern_keywords.items():
            if any(keyword in insights_text for keyword in keywords):
                all_patterns.add(pattern_name)

        for claim in arch_claims:
            claim_lower = claim.lower()
            mentioned_patterns = [p for p in pattern_keywords.keys() if p in claim_lower]

            if not mentioned_patterns:
                continue

            unverified_patterns = [p for p in mentioned_patterns if p not in all_patterns]

            if unverified_patterns:
                issues.append(ValidationIssue(
                    severity='warning',
                    issue_type='unverified_architectural_claim',
                    message=f'Architectural claim not verified: "{claim[:100]}..." (patterns: {unverified_patterns})'
                ))

        return issues

    def _read_code_at_line(self, file_path: str, line_num: int, context_lines: Optional[int] = None) -> Optional[str]:
        """Read code at specific line with surrounding context."""
        try:
            if context_lines is None:
                validation_config = self.config.get('agents', {}).get('validation', {})
                context_lines = validation_config.get('read_code_context_lines', 3)

            result = self.repo_tools.execute('read_file', file_path=file_path)

            if 'error' in result or 'content' not in result:
                return None

            content = result.get('content', '')
            lines = content.split('\n')

            start = max(0, line_num - context_lines - 1)
            end = min(len(lines), line_num + context_lines)

            context_lines_text = '\n'.join(lines[start:end])
            return context_lines_text

        except Exception:
            return None

    def _verify_claim_against_code(self, claim: str, code_context: str, file_summary: Dict[str, Any]) -> bool:
        """Verify a claim against actual code context."""
        words = claim.split()
        code_words = code_context.lower().split()

        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
                        'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                        'key', 'similar', 'after', 'finally', 'starting', 'three', 'model', 'pattern',
                        'url', 'ui', 'orm', 'mvc', 'component', 'interactions', 'detailed', 'together'}
        identifiers_in_claim = []
        for w in words:
            cleaned = w.strip('`"\'()*_#[]')
            if cleaned and len(cleaned) >= 2:
                cleaned_lower = cleaned.lower()
                if ('_' in cleaned or
                    (any(c.isupper() for c in cleaned[1:]) and any(c.islower() for c in cleaned)) or
                    (cleaned[0].isupper() and len(cleaned) > 3 and cleaned_lower not in common_words)):
                    identifiers_in_claim.append(cleaned)

        if identifiers_in_claim:
            matches = sum(1 for identifier in identifiers_in_claim if identifier.lower() in ' '.join(code_words))
            match_ratio = matches / len(identifiers_in_claim) if identifiers_in_claim else 0

            min_match_ratio = self.config.get('agents', {}).get('validation', {}).get('min_identifier_match', 0.3)
            if match_ratio < min_match_ratio:
                return False

        if 'calls' in claim.lower() or 'invokes' in claim.lower():
            functions = file_summary.get('functions', [])
            function_names = [f.get('name', '') for f in functions if isinstance(f, dict)]

            for func_name in function_names:
                if func_name and func_name in claim:
                    return True

        if 'inherits' in claim.lower() or 'extends' in claim.lower() or 'subclass' in claim.lower():
            classes = file_summary.get('classes', [])
            class_names = [c.get('name', '') for c in classes if isinstance(c, dict)]

            for class_name in class_names:
                if class_name and class_name in claim:
                    return True

        return True


# =============================================================================
# Validation Scorer
# =============================================================================

class ValidationScorer:
    """
    Calculates validation scores for answer quality assessment.
    """

    def __init__(self, config: Dict[str, Any], structural_validator: StructuralValidator):
        """
        Initialize validation scorer.

        Args:
            config: Configuration dictionary
            structural_validator: StructuralValidator instance for path patterns
        """
        self.config = config
        self.structural_validator = structural_validator

    def calculate_grounding_score(self, answer: str, file_summaries: Dict[str, Any]) -> float:
        """
        Calculate how well grounded the answer is in code references.

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            Grounding score (0.0 to 1.0)
        """
        line_refs = len(re.findall(r'line[s]?\s+\d+|L\d+', answer, re.IGNORECASE))
        path_refs = len(re.findall(r'[\w/.-]+\.\w+', answer))

        code_entities = set()
        for summary in file_summaries.values():
            if isinstance(summary, dict):
                functions = summary.get('functions', [])
                classes = summary.get('classes', [])
                code_entities.update([f.get('name', '') for f in functions if isinstance(f, dict)])
                code_entities.update([c.get('name', '') for c in classes if isinstance(c, dict)])

        entity_refs = sum(1 for entity in code_entities if entity and entity in answer)

        total_refs = line_refs + path_refs + entity_refs

        thresholds = self.config.get('agents', {}).get('thresholds', {})
        no_refs_score = thresholds.get('validation_no_refs_score', 0.3)
        refs_base_score = thresholds.get('validation_refs_base', 0.5)
        refs_increment = thresholds.get('validation_refs_increment', 0.05)

        if total_refs == 0:
            return no_refs_score

        score = min(refs_base_score + (total_refs * refs_increment), 1.0)
        return score

    def calculate_line_coverage(self, answer: str) -> float:
        """
        Calculate percentage of sentences with line number references.

        Args:
            answer: Generated answer text

        Returns:
            Line coverage ratio (0.0 to 1.0)
        """
        sentences = re.split(r'[.!?]+', answer)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.0

        path_pattern = self.structural_validator._get_file_path_pattern()
        max_gap = self.structural_validator._get_max_file_line_gap()
        file_line_pattern = rf'{path_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt).{{0,{max_gap}}}?(?:line[s]?\s+|L|at\s+line\s+)(\d+)'
        file_line_matches = list(re.finditer(file_line_pattern, answer, re.IGNORECASE | re.DOTALL))

        if not file_line_matches:
            return 0.0

        sentence_boundaries = []
        pos = 0
        for sentence in sentences:
            start = answer.find(sentence, pos)
            if start != -1:
                end = start + len(sentence)
                sentence_boundaries.append((start, end))
                pos = end

        sentences_with_lines = set()
        for match in file_line_matches:
            match_pos = match.start()
            for i, (start, end) in enumerate(sentence_boundaries):
                if start <= match_pos < end:
                    sentences_with_lines.add(i)
                    break

        return len(sentences_with_lines) / len(sentences)

    def calculate_path_accuracy(self, answer: str, file_summaries: Dict[str, Any]) -> float:
        """
        Calculate accuracy of file path references.

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            Path accuracy ratio (0.0 to 1.0)
        """
        prefix_pattern = self.structural_validator._get_file_path_pattern()
        path_pattern = rf'\b{prefix_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt)\b'
        mentioned_paths = re.findall(path_pattern, answer)

        if not mentioned_paths:
            return 1.0

        valid_paths = set(file_summaries.keys())

        correct = 0
        for mentioned_path in mentioned_paths:
            normalized_mention = mentioned_path.lstrip('./')

            if normalized_mention in valid_paths:
                correct += 1
                continue

            if any(vp.endswith(normalized_mention) for vp in valid_paths):
                correct += 1
                continue

            if any(normalized_mention.endswith(vp) for vp in valid_paths):
                correct += 1
                continue

        return correct / len(mentioned_paths)


# =============================================================================
# Convenience function for quick validation
# =============================================================================

def validate_answer(
    answer: str,
    file_summaries: Dict[str, Any],
    config: Dict[str, Any],
    repo_tools=None,
    llm_client=None
) -> ValidationResult:
    """
    Convenience function to run full validation on an answer.

    Args:
        answer: Generated answer text
        file_summaries: File summaries from code analysis
        config: Configuration dictionary
        repo_tools: Optional repository tools for fact verification
        llm_client: Optional LLM client for complex verification

    Returns:
        ValidationResult with all issues and scores
    """
    all_issues = []

    # Structural validation
    structural = StructuralValidator(config, file_summaries)
    all_issues.extend(structural.validate_line_numbers(answer))
    all_issues.extend(structural.validate_file_paths(answer))
    all_issues.extend(structural.check_file_hallucination(answer))

    # Content validation
    content = ContentValidator(config)
    all_issues.extend(content.validate_grounding(answer))
    all_issues.extend(content.validate_word_count(answer, file_summaries))

    # Fact verification (if tools available)
    if repo_tools:
        fact_verifier = FactVerifier(config, repo_tools, llm_client)
        all_issues.extend(fact_verifier.verify_facts(answer, file_summaries))

    # Calculate scores
    scorer = ValidationScorer(config, structural)
    grounding_score = scorer.calculate_grounding_score(answer, file_summaries)
    line_coverage = scorer.calculate_line_coverage(answer)
    path_accuracy = scorer.calculate_path_accuracy(answer, file_summaries)

    # Determine overall validity (no errors = valid)
    has_errors = any(issue.severity == 'error' for issue in all_issues)

    return ValidationResult(
        valid=not has_errors,
        issues=all_issues,
        grounding_score=grounding_score,
        line_number_coverage=line_coverage,
        path_accuracy=path_accuracy
    )
