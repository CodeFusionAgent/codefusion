"""
Validation Scorer

Calculates validation scores for generated answers:
- Grounding score (how well referenced)
- Line coverage (percentage with line refs)
- Path accuracy (correctness of file paths)
"""

from typing import Dict, List, Any
import re


class ValidationScorer:
    """
    Calculates validation scores for answer quality assessment.

    Uses various metrics to quantify how well-grounded and accurate
    the generated answer is.
    """

    def __init__(self, config: Dict[str, Any], structural_validator):
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

        Counts line numbers, file paths, and code entity mentions.

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            Grounding score (0.0 to 1.0)
        """
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

    def calculate_line_coverage(self, answer: str) -> float:
        """
        Calculate percentage of sentences with line number references.

        Measures how well the answer is grounded with specific line references.

        Args:
            answer: Generated answer text

        Returns:
            Line coverage ratio (0.0 to 1.0)
        """
        # Split answer into sentences
        sentences = re.split(r'[.!?]+', answer)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.0

        # Find all file+line pairs in the entire answer (may span sentences due to markdown formatting)
        # Use same pattern as validation for consistency
        path_pattern = self.structural_validator._get_file_path_pattern()
        max_gap = self.structural_validator._get_max_file_line_gap()
        file_line_pattern = rf'{path_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt).{{0,{max_gap}}}?(?:line[s]?\s+|L|at\s+line\s+)(\d+)'
        file_line_matches = list(re.finditer(file_line_pattern, answer, re.IGNORECASE | re.DOTALL))

        if not file_line_matches:
            return 0.0

        # Build sentence boundaries (character positions in answer)
        sentence_boundaries = []
        pos = 0
        for sentence in sentences:
            start = answer.find(sentence, pos)
            if start != -1:
                end = start + len(sentence)
                sentence_boundaries.append((start, end))
                pos = end

        # Count how many sentences contain at least one file+line reference
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

        Checks how many referenced paths are actually valid.

        Args:
            answer: Generated answer text
            file_summaries: File summaries from code analysis

        Returns:
            Path accuracy ratio (0.0 to 1.0)
        """
        # Extract paths from answer - use restrictive pattern to avoid false positives
        prefix_pattern = self.structural_validator._get_file_path_pattern()
        path_pattern = rf'\b{prefix_pattern}/[\w/.-]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|rb|php|swift|kt)\b'
        mentioned_paths = re.findall(path_pattern, answer)

        if mentioned_paths:
            print(f"   Mentioned paths (first 10): {mentioned_paths[:10]}")

        if not mentioned_paths:
            print(f"   ℹ️  No paths found in narrative - returning 1.0 (perfect accuracy)")
            return 1.0  # No paths = perfect accuracy (nothing to be wrong)

        valid_paths = set(file_summaries.keys())
        print(f"   Valid paths from file_summaries: {list(valid_paths)}")

        # Count correct paths with fuzzy matching
        correct = 0
        incorrect_paths = []
        for mentioned_path in mentioned_paths:
            # Normalize path (remove leading ./ and normalize separators)
            normalized_mention = mentioned_path.lstrip('./')

            matched = False

            # Check exact match first
            if normalized_mention in valid_paths:
                correct += 1
                matched = True
                continue

            # Check if mentioned path is a suffix of any valid path
            # (handles cases where LLM omits repo prefix)
            if any(vp.endswith(normalized_mention) for vp in valid_paths):
                correct += 1
                matched = True
                continue

            # Check if any valid path is a suffix of mentioned path
            # (handles cases where LLM adds extra prefix)
            if any(normalized_mention.endswith(vp) for vp in valid_paths):
                correct += 1
                matched = True
                continue

            if not matched:
                incorrect_paths.append(mentioned_path)

        accuracy = correct / len(mentioned_paths)
        print(f"   ✅ Matched paths: {correct}/{len(mentioned_paths)} ({accuracy:.2%})")
        if incorrect_paths:
            print(f"   ❌ Unmatched paths (first 5): {incorrect_paths[:5]}")

        return accuracy
