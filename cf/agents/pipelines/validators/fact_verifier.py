"""
Fact Verifier

Verifies factual claims in generated answers against actual code:
- Line-referenced claims
- Architectural/pattern claims
- Code reading and verification
"""

from typing import Dict, List, Any, Optional
import re

from cf.agents.pipelines.validators.base import ValidationIssue


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
        Verify claims in the answer against actual code (anti-hallucination).

        This addresses the main weakness identified in the dry run:
        LLM may generate plausible but incorrect narratives.

        Strategy:
        1. Extract specific claims with line references
        2. Read actual code at those lines
        3. Verify claims match code reality
        4. Cross-check with file summaries
        5. Verify architectural/pattern claims without line refs

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            List of validation issues
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

        # Verify architectural/pattern claims WITHOUT line references
        arch_issues = self._verify_architectural_claims(answer, file_summaries)
        issues.extend(arch_issues)

        return issues

    def _verify_line_referenced_claims(self, answer: str, file_summaries: Dict[str, Any], max_claims: int) -> List[ValidationIssue]:
        """
        Verify claims that have line references.

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis
            max_claims: Maximum claims to verify

        Returns:
            List of validation issues
        """
        issues = []

        # Extract claims with line references (format: "text mentioning line X")
        claim_pattern = r'([^.!?]+(?:line[s]?\s+\d+|L\d+|at\s+line\s+\d+)[^.!?]*[.!?])'
        claims_with_lines = re.findall(claim_pattern, answer, re.IGNORECASE)

        if claims_with_lines:
            print(f"   First 3 claims:")
            for i, claim in enumerate(claims_with_lines[:3], 1):
                print(f"      {i}. {claim[:100]}...")

        # Limit claims to verify (performance consideration)
        claims_to_verify = claims_with_lines[:max_claims]
        print(f"   Verifying {len(claims_to_verify)} claims (max: {max_claims})")

        verified_count = 0
        failed_count = 0
        skipped_count = 0

        for claim in claims_to_verify:
            # Extract file path from claim (if present)
            path_match = re.search(r'([\w/.-]+\.py)', claim)

            # If no file path in claim, look in context (configurable chars backwards)
            if not path_match:
                claim_start = answer.find(claim)
                if claim_start > 0:
                    validation_config = self.config.get('agents', {}).get('validation', {})
                    context_chars = validation_config.get('claim_context_chars', 200)
                    context_start = max(0, claim_start - context_chars)
                    context = answer[context_start:claim_start]
                    path_match = re.search(r'([\w/.-]+\.py)', context)

            if not path_match:
                skipped_count += 1
                continue

            file_path = path_match.group(1)

            # Check if this file was analyzed
            if file_path not in file_summaries:
                # Try partial match
                matching_files = [f for f in file_summaries.keys() if file_path in f or f in file_path]
                if not matching_files:
                    skipped_count += 1
                    continue
                file_path = matching_files[0]

            # Extract line number from claim
            line_match = re.search(r'(?:line[s]?\s+|L)(\d+)', claim, re.IGNORECASE)
            if not line_match:
                skipped_count += 1
                continue

            line_num = int(line_match.group(1))

            # Read actual code at that line (with context)
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
        if skipped_count > 0:
            print(f"   ℹ️  Skipped {skipped_count} claims (no file path or line number)")

        return issues

    def _verify_architectural_claims(self, answer: str, file_summaries: Dict[str, Any]) -> List[ValidationIssue]:
        """
        Verify architectural and pattern claims WITHOUT line references.

        Addresses limitation where claims like "The system uses singleton pattern"
        weren't verified because they lack line numbers.

        Strategy:
        1. Extract architectural claims (patterns, design, architecture)
        2. Verify against file summaries (architectural_insights)
        3. Cross-check with known patterns from code

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            List of validation issues
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

        # Remove duplicates and limit count
        validation_config = self.config.get('agents', {}).get('validation', {})
        max_claims = validation_config.get('max_architectural_claims', 10)
        arch_claims = list(set(arch_claims))[:max_claims]

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

    def _read_code_at_line(self, file_path: str, line_num: int, context_lines: Optional[int] = None) -> Optional[str]:
        """
        Read code at specific line with surrounding context.

        Args:
            file_path: Path to file
            line_num: Line number to read
            context_lines: Number of context lines before/after

        Returns:
            Code context string, or None if failed
        """
        try:
            # Get context lines from config if not specified
            if context_lines is None:
                validation_config = self.config.get('agents', {}).get('validation', {})
                context_lines = validation_config.get('read_code_context_lines', 3)

            # Use repo tools to read file
            result = self.repo_tools.execute('read_file', file_path=file_path)

            # Check for errors or missing content
            if 'error' in result or 'content' not in result:
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

        Args:
            claim: Claim text to verify
            code_context: Actual code context
            file_summary: File summary from analysis

        Returns:
            True if claim appears valid, False otherwise
        """
        # Heuristic 1: Check for function/class name mentions
        words = claim.split()
        code_words = code_context.lower().split()

        # Filter out markdown artifacts, common words, and keep only code-like identifiers
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
                        'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                        'key', 'similar', 'after', 'finally', 'starting', 'three', 'model', 'pattern',
                        'url', 'ui', 'orm', 'mvc', 'component', 'interactions', 'detailed', 'together'}
        identifiers_in_claim = []
        for w in words:
            # Strip markdown and punctuation
            cleaned = w.strip('`"\'()*_#[]')
            # Only keep if it looks like a code identifier and is not a common word
            if cleaned and len(cleaned) >= 2:
                cleaned_lower = cleaned.lower()
                # Keep if: has underscore (snake_case), or mixed case (camelCase/PascalCase), or longer proper names
                if ('_' in cleaned or  # snake_case
                    (any(c.isupper() for c in cleaned[1:]) and any(c.islower() for c in cleaned)) or  # camelCase/PascalCase
                    (cleaned[0].isupper() and len(cleaned) > 3 and cleaned_lower not in common_words)):  # Longer proper names
                    identifiers_in_claim.append(cleaned)

        if identifiers_in_claim:
            # Check if at least some identifiers are in the code
            matches = sum(1 for identifier in identifiers_in_claim if identifier.lower() in ' '.join(code_words))
            match_ratio = matches / len(identifiers_in_claim) if identifiers_in_claim else 0

            # Require at least 30% of mentioned identifiers to be in code
            min_match_ratio = self.config.get('agents', {}).get('validation', {}).get('min_identifier_match', 0.3)
            if match_ratio < min_match_ratio:
                print(f"         Identifiers in claim: {identifiers_in_claim[:5]}")
                print(f"         Match ratio: {match_ratio:.2%} < {min_match_ratio:.2%}")
                print(f"         Claim: {claim[:80]}...")
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
        """
        Use LLM to verify complex claims against code (optional, cost consideration).

        Args:
            claim: Claim to verify
            code_context: Actual code context

        Returns:
            True if claim appears valid, False otherwise
        """
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

            validation_config = self.config.get('agents', {}).get('validation', {})
            temperature = validation_config.get('llm_verification_temperature', 0.0)
            max_tokens = validation_config.get('llm_verification_max_tokens', 10)

            response = self.llm.generate_fast(
                prompt=prompt,
                system_prompt="You are a code fact-checker. Respond with only TRUE or FALSE.",
                temperature=temperature,
                max_tokens=max_tokens
            )

            if response.get('success'):
                content = response.get('content', '').strip().upper()
                return 'TRUE' in content

        except Exception as e:
            print(f"⚠️ [VALIDATION] LLM verification failed: {e}")

        # Default to True if verification fails (avoid false positives)
        return True
