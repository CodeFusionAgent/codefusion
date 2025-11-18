"""
Structural Validator

Validates structural aspects of generated answers:
- Line number references
- File path accuracy
- File hallucination detection
"""

from typing import Dict, List, Any
import re

from cf.agents.pipelines.validators.base import ValidationIssue


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
        # Build pattern: (?:apps|src|lib|...)
        prefix_pattern = '|'.join(re.escape(p) for p in prefixes)
        return f'(?:{prefix_pattern})'

    def _get_max_file_line_gap(self) -> int:
        """Get max characters allowed between file path and line number reference."""
        validation_config = self.config.get('agents', {}).get('validation', {})
        return validation_config.get('max_file_line_gap_chars', 100)

    def validate_line_numbers(self, answer: str) -> List[ValidationIssue]:
        """
        Validate line number references in answer.

        Checks if line numbers are within valid ranges for their files.

        Args:
            answer: Generated answer text

        Returns:
            List of validation issues
        """
        issues = []

        # Extract file path + line number pairs from the narrative
        # Pattern matches: "apps/foo/bar.py ... line 123" (can span multiple lines/paragraphs)
        # Gap length configured to prevent cross-paragraph pairing
        path_pattern = self._get_file_path_pattern()
        max_gap = self._get_max_file_line_gap()
        file_line_pattern = rf'({path_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt)).{{0,{max_gap}}}?(?:line[s]?\s+|L|at\s+line\s+)(\d+)'

        file_line_refs = re.findall(file_line_pattern, answer, re.IGNORECASE | re.DOTALL)

        if file_line_refs:
            print(f"   First 5 references: {file_line_refs[:5]}")

        if not file_line_refs:
            # Fall back to checking if there are ANY line references (even without files)
            line_pattern = r'line[s]?\s+\d+|L\d+|at\s+line\s+\d+'
            if not re.search(line_pattern, answer, re.IGNORECASE):
                issues.append(ValidationIssue(
                    severity='warning',
                    issue_type='missing_line_numbers',
                    message='Answer contains no line number references for grounding'
                ))
            return issues

        # Check if line numbers are within valid ranges for their specific files
        invalid_count = 0
        for file_path, line_num_str in file_line_refs:
            line_num = int(line_num_str)

            # Find the matching file in summaries (exact or partial match)
            matching_file = None
            if file_path in self.file_summaries:
                matching_file = file_path
            else:
                # Try partial match
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

        if invalid_count > 0:
            print(f"   ❌ Found {invalid_count} invalid line numbers")

        return issues

    def validate_file_paths(self, answer: str) -> List[ValidationIssue]:
        """
        Validate file path references in answer.

        Checks if referenced paths exist in analyzed files.

        Args:
            answer: Generated answer text

        Returns:
            List of validation issues
        """
        issues = []

        # Extract file paths from answer - more restrictive pattern to avoid false positives
        # Only match paths that look like actual file paths (start with directory, end with extension)
        prefix_pattern = self._get_file_path_pattern()
        path_pattern = rf'\b{prefix_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt)\b'
        potential_paths = re.findall(path_pattern, answer)

        print(f"   Extracted paths: {potential_paths[:5]}{'...' if len(potential_paths) > 5 else ''}")

        valid_paths = set(self.file_summaries.keys())

        unverified_count = 0
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
                    unverified_count += 1

        if unverified_count > 0:
            print(f"   ⚠️  Found {unverified_count} unverified paths")

        return issues

    def check_file_hallucination(self, answer: str) -> List[ValidationIssue]:
        """
        Check if narrative mentions files that were NOT analyzed (hallucination detection).

        This is stricter than validate_file_paths - it flags ANY file reference that's not
        in the analyzed set as a critical error, especially common hallucinated names like
        "ApplicationController.py", "ApplicationService.py", etc.

        Args:
            answer: Generated answer text

        Returns:
            List of validation issues
        """
        issues = []

        # Extract ALL file references from narrative (simple pattern)
        # This catches files mentioned in text like "ApplicationController.py does X"
        all_file_refs = re.findall(r'\b(\w+(?:/\w+)*\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt))\b', answer)

        # Also catch files with full paths
        prefix_pattern = self._get_file_path_pattern()
        full_path_refs = re.findall(
            rf'\b({prefix_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt))\b',
            answer
        )

        # Combine both patterns
        all_mentioned_files = set(all_file_refs + full_path_refs)

        # Get the set of actually analyzed files
        analyzed_files = set(self.file_summaries.keys())

        # Common hallucinated file names (these should NEVER appear unless actually analyzed)
        common_hallucinations = {
            'ApplicationController.py', 'ApplicationService.py', 'ApplicationRepository.py',
            'UserController.py', 'UserService.py', 'UserRepository.py',
            'AuthController.py', 'AuthService.py',
            'BaseController.py', 'BaseService.py',
            'models.py', 'views.py', 'controllers.py', 'services.py', 'repositories.py'
        }

        print(f"   Analyzed files: {len(analyzed_files)}")

        hallucinated_count = 0
        for mentioned_file in all_mentioned_files:
            # Check if this file was actually analyzed
            is_analyzed = mentioned_file in analyzed_files

            # Also check if it's a basename of an analyzed file
            if not is_analyzed:
                basenames = [fp.split('/')[-1] for fp in analyzed_files]
                is_analyzed = mentioned_file in basenames or any(mentioned_file in fp for fp in analyzed_files)

            if not is_analyzed:
                # This file was NOT analyzed - hallucination detected
                # All non-analyzed files are marked as errors (not warnings)
                issues.append(ValidationIssue(
                    severity='error',
                    issue_type='file_hallucination',
                    message=f'Narrative references "{mentioned_file}" which was NOT analyzed. This is likely a hallucination. Only reference files from the analyzed set.',
                    file_path=mentioned_file
                ))
                hallucinated_count += 1

                # Special logging for known common hallucinations
                if mentioned_file in common_hallucinations:
                    print(f"   🚨 [HALLUCINATION] Common hallucinated file: {mentioned_file}")
                else:
                    print(f"   🚨 [HALLUCINATION] Found reference to non-analyzed file: {mentioned_file}")

        if hallucinated_count > 0:
            print(f"   ❌ Found {hallucinated_count} hallucinated file references")
        else:
            print(f"   ✅ No file hallucinations detected")

        return issues
