"""
Validation Pipeline for CodeFusion

Responsible for validating claims, checking line numbers, and ensuring grounding.
All validation logic is config-driven and language-agnostic.
"""

from typing import Dict, List, Any, Optional
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

    def __init__(self, repo_path: str, config: Dict[str, Any], repo_tools, llm_client=None):
        self.repo_path = repo_path
        self.config = config
        self.repo_tools = repo_tools
        self.llm = llm_client  # Optional LLM for claim verification

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

            # 4. Verify facts against actual code (anti-hallucination)
            fact_issues = self._verify_facts(answer, file_summaries)
            issues.extend(fact_issues)

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

    def _verify_facts(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """
        Verify claims in the answer against actual code (anti-hallucination).

        This addresses the main weakness identified in the dry run:
        LLM may generate plausible but incorrect narratives.

        Strategy:
        1. Extract specific claims with line references
        2. Read actual code at those lines
        3. Verify claims match code reality
        4. Cross-check with file summaries
        5. Verify architectural/pattern claims without line refs (NEW)
        """
        issues = []

        # Get fact verification config
        validation_config = self.config.get('agents', {}).get('validation', {})
        enable_fact_check = validation_config.get('enable_fact_verification', True)
        max_claims_to_verify = validation_config.get('max_claims_to_verify', 20)

        if not enable_fact_check:
            return issues

        print("🔍 [VALIDATION] Verifying facts against actual code...")

        # Verify claims WITH line references
        line_ref_issues = self._verify_line_referenced_claims(answer, file_summaries, max_claims_to_verify)
        issues.extend(line_ref_issues)

        # Verify architectural/pattern claims WITHOUT line references (NEW)
        arch_issues = self._verify_architectural_claims(answer, file_summaries)
        issues.extend(arch_issues)

        return issues

    def _verify_line_referenced_claims(self, answer: str, file_summaries: Dict[str, Any], max_claims: int) -> List[ValidationIssue]:
        """Verify claims that have line references"""
        issues = []

        # Extract claims with line references (format: "text mentioning line X")
        claim_pattern = r'([^.!?]+(?:line[s]?\s+\d+|L\d+|at\s+line\s+\d+)[^.!?]*[.!?])'
        claims_with_lines = re.findall(claim_pattern, answer, re.IGNORECASE)

        # Limit claims to verify (performance consideration)
        claims_to_verify = claims_with_lines[:max_claims]

        verified_count = 0
        failed_count = 0

        for claim in claims_to_verify:
            # Extract file path from claim (if present)
            path_match = re.search(r'([\w/.-]+\.py)', claim)
            if not path_match:
                continue

            file_path = path_match.group(1)

            # Check if this file was analyzed
            if file_path not in file_summaries:
                # Try partial match
                matching_files = [f for f in file_summaries.keys() if file_path in f or f in file_path]
                if not matching_files:
                    continue
                file_path = matching_files[0]

            # Extract line number from claim
            line_match = re.search(r'(?:line[s]?\s+|L)(\d+)', claim, re.IGNORECASE)
            if not line_match:
                continue

            line_num = int(line_match.group(1))

            # Read actual code at that line (with context)
            code_context = self._read_code_at_line(file_path, line_num, context_lines=3)

            if not code_context:
                issues.append(ValidationIssue(
                    severity='warning',
                    issue_type='unverifiable_claim',
                    message=f'Cannot verify claim - unable to read {file_path}:{line_num}',
                    file_path=file_path,
                    line_number=line_num
                ))
                failed_count += 1
                continue

            # Verify claim against code (using heuristics + optional LLM)
            is_valid = self._verify_claim_against_code(claim, code_context, file_summaries.get(file_path, {}))

            if not is_valid:
                issues.append(ValidationIssue(
                    severity='error',
                    issue_type='fact_check_failed',
                    message=f'Claim may be inaccurate: "{claim[:100]}..." at {file_path}:{line_num}',
                    file_path=file_path,
                    line_number=line_num
                ))
                failed_count += 1
            else:
                verified_count += 1

        if verified_count > 0:
            print(f"   ✅ Verified {verified_count} claims against actual code")
        if failed_count > 0:
            print(f"   ⚠️  {failed_count} claims failed verification")

        return issues

    def _verify_architectural_claims(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """
        Verify architectural and pattern claims WITHOUT line references.

        NEW: Addresses limitation where claims like "The system uses singleton pattern"
        weren't verified because they lack line numbers.

        Strategy:
        1. Extract architectural claims (patterns, design, architecture)
        2. Verify against file summaries (architectural_insights)
        3. Cross-check with known patterns from code
        """
        issues = []

        # Architectural claim patterns
        arch_patterns = [
            r'(system|architecture|design|codebase)[^.!?]*(?:uses?|implements?|follows?|employs?)[^.!?]*[.!?]',
            r'(?:uses?|implements?|follows?|employs?)[^.!?]*(?:pattern|principle|architecture)[^.!?]*[.!?]',
            r'(?:singleton|factory|observer|strategy|decorator|adapter|mvc|microservice)[^.!?]*[.!?]'
        ]

        arch_claims = []
        for pattern in arch_patterns:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            arch_claims.extend(matches)

        # Remove duplicates
        arch_claims = list(set(arch_claims))[:10]  # Limit to 10 architectural claims

        if not arch_claims:
            return issues

        print(f"   🏗️  Verifying {len(arch_claims)} architectural claims...")

        # Collect all architectural insights from file summaries
        all_insights = []
        all_patterns = set()

        for file_path, summary in file_summaries.items():
            if isinstance(summary, dict):
                # Get architectural insights
                insights = summary.get('architectural_insights', '')
                if insights:
                    all_insights.append(insights.lower())

                # Get key features that might mention patterns
                features = summary.get('key_features', [])
                if isinstance(features, list):
                    all_insights.extend([f.lower() for f in features if isinstance(f, str)])

        # Common pattern keywords to detect
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

        # Detect patterns mentioned in summaries
        insights_text = ' '.join(all_insights)
        for pattern_name, keywords in pattern_keywords.items():
            if any(keyword in insights_text for keyword in keywords):
                all_patterns.add(pattern_name)

        # Verify each architectural claim
        verified = 0
        failed = 0

        for claim in arch_claims:
            claim_lower = claim.lower()

            # Check if claim mentions a pattern
            mentioned_patterns = [p for p in pattern_keywords.keys() if p in claim_lower]

            if not mentioned_patterns:
                # Not a pattern claim, skip
                continue

            # Verify if mentioned patterns are actually detected in code
            verified_patterns = [p for p in mentioned_patterns if p in all_patterns]
            unverified_patterns = [p for p in mentioned_patterns if p not in all_patterns]

            if unverified_patterns:
                # Claim mentions patterns not found in code
                issues.append(ValidationIssue(
                    severity='warning',
                    issue_type='unverified_architectural_claim',
                    message=f'Architectural claim not verified in summaries: "{claim[:100]}..." (patterns: {unverified_patterns})'
                ))
                failed += 1
            else:
                verified += 1

        if verified > 0:
            print(f"   ✅ Verified {verified} architectural claims")
        if failed > 0:
            print(f"   ⚠️  {failed} architectural claims couldn't be verified")

        return issues

    def _read_code_at_line(self, file_path: str, line_num: int, context_lines: int = 3) -> Optional[str]:
        """Read code at specific line with surrounding context"""
        try:
            # Use repo tools to read file
            result = self.repo_tools.execute('read_file', file_path=file_path)

            if not result.get('success'):
                return None

            content = result.get('content', '')
            lines = content.split('\n')

            # Get line with context
            start = max(0, line_num - context_lines - 1)
            end = min(len(lines), line_num + context_lines)

            context_lines_text = '\n'.join(lines[start:end])
            return context_lines_text

        except Exception as e:
            print(f"⚠️ [VALIDATION] Failed to read {file_path}:{line_num}: {e}")
            return None

    def _verify_claim_against_code(self, claim: str, code_context: str, file_summary: Dict[str, Any]) -> bool:
        """
        Verify a claim against actual code context.

        Uses heuristic checks + optional LLM verification for complex claims.
        """
        # Heuristic 1: Check for function/class name mentions
        # Extract potential entity names from claim
        words = claim.split()
        code_words = code_context.lower().split()

        # If claim mentions specific identifiers, they should exist in code
        identifiers_in_claim = [w.strip('`"\'()') for w in words if w and w[0].isupper() or '_' in w]

        if identifiers_in_claim:
            # Check if at least some identifiers are in the code
            matches = sum(1 for identifier in identifiers_in_claim if identifier.lower() in ' '.join(code_words))
            match_ratio = matches / len(identifiers_in_claim) if identifiers_in_claim else 0

            # Require at least 30% of mentioned identifiers to be in code
            min_match_ratio = self.config.get('agents', {}).get('validation', {}).get('min_identifier_match', 0.3)
            if match_ratio < min_match_ratio:
                return False

        # Heuristic 2: Check for contradictions with file summary
        # If claim says "function X calls Y", verify against summary
        if 'calls' in claim.lower() or 'invokes' in claim.lower():
            functions = file_summary.get('functions', [])
            function_names = [f.get('name', '') for f in functions if isinstance(f, dict)]

            # Check if mentioned functions exist in summary
            for func_name in function_names:
                if func_name and func_name in claim:
                    # Function exists, claim is likely valid
                    return True

        # Heuristic 3: Check for inheritance/class relationships
        if 'inherits' in claim.lower() or 'extends' in claim.lower() or 'subclass' in claim.lower():
            classes = file_summary.get('classes', [])
            class_names = [c.get('name', '') for c in classes if isinstance(c, dict)]

            # Check if mentioned classes exist
            for class_name in class_names:
                if class_name and class_name in claim:
                    return True

        # If we have LLM available, use it for complex verification
        if self.llm and self.config.get('agents', {}).get('validation', {}).get('use_llm_verification', False):
            return self._llm_verify_claim(claim, code_context)

        # Default: assume valid if no clear contradictions found
        # (Conservative approach - only flag obvious hallucinations)
        return True

    def _llm_verify_claim(self, claim: str, code_context: str) -> bool:
        """Use LLM to verify complex claims against code (optional, cost consideration)"""
        try:
            prompt = f"""Verify if this claim about code is accurate.

CLAIM: {claim}

ACTUAL CODE:
```
{code_context}
```

Is the claim consistent with the actual code shown above?
Respond with just "TRUE" if accurate, "FALSE" if inaccurate or contradictory.

Response:"""

            response = self.llm.generate_fast(
                prompt=prompt,
                system_prompt="You are a code fact-checker. Respond with only TRUE or FALSE.",
                temperature=0.0,
                max_tokens=10
            )

            if response.get('success'):
                content = response.get('content', '').strip().upper()
                return 'TRUE' in content

        except Exception as e:
            print(f"⚠️ [VALIDATION] LLM verification failed: {e}")

        # Default to True if verification fails (avoid false positives)
        return True

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

        # Count correct paths with fuzzy matching
        correct = 0
        for mentioned_path in mentioned_paths:
            # Normalize path (remove leading ./ and normalize separators)
            normalized_mention = mentioned_path.lstrip('./')

            # Check exact match first
            if normalized_mention in valid_paths:
                correct += 1
                continue

            # Check if mentioned path is a suffix of any valid path
            # (handles cases where LLM omits repo prefix)
            if any(vp.endswith(normalized_mention) for vp in valid_paths):
                correct += 1
                continue

            # Check if any valid path is a suffix of mentioned path
            # (handles cases where LLM adds extra prefix)
            if any(normalized_mention.endswith(vp) for vp in valid_paths):
                correct += 1
                continue

        return correct / len(mentioned_paths)
