"""
Agent Utility Functions

Shared utilities used across multiple agent pipelines.
"""

import re
from typing import Dict, Tuple, Any, List


def calculate_word_count_targets(file_count: int, config: Dict[str, Any]) -> Tuple[int, int]:
    """
    Calculate word count targets based on number of files analyzed.

    This ensures synthesis and validation use identical calculations,
    preventing target mismatches.

    Args:
        file_count: Number of files analyzed
        config: Configuration dict

    Returns:
        Tuple of (target_min, target_max) word counts

    Formula:
        1. Proportional calculation: file_count * words_per_file
        2. Apply absolute limits (min/max caps)
        3. Ensure target_min <= target_max

    Example:
        50 files × 400 words/file = 20,000 words (proportional)
        → Capped at 5,000 words (absolute max)
        → Returns (5000, 5000)
    """
    synthesis_config = config.get('agents', {}).get('synthesis', {})

    # Per-file word counts
    words_per_file_min = synthesis_config.get('words_per_file_min', 400)
    words_per_file_max = synthesis_config.get('words_per_file_max', 700)

    # Proportional calculation
    calculated_min = file_count * words_per_file_min
    calculated_max = file_count * words_per_file_max

    # Absolute limits (caps for very large/small file counts)
    absolute_min = synthesis_config.get('target_narrative_min', 1200)
    absolute_max = synthesis_config.get('target_narrative_max', 5000)

    # Apply limits
    target_min = max(absolute_min, min(calculated_min, absolute_max))
    target_max = min(absolute_max, max(calculated_max, absolute_min))

    return target_min, target_max


def trim_narrative_to_word_limit(
    narrative: str,
    max_words: int,
    preserve_structure: bool = True
) -> str:
    """
    Trim a narrative to a maximum word count while preserving markdown structure.

    This is a post-generation safety net to enforce hard word limits when
    the LLM exceeds the requested word count.

    Args:
        narrative: The narrative text to trim
        max_words: Maximum allowed word count
        preserve_structure: If True, try to cut at section boundaries

    Returns:
        Trimmed narrative that fits within word limit

    Strategy:
        1. If under limit, return unchanged
        2. If preserve_structure=True, try to cut at last complete section
        3. Otherwise, cut at last complete sentence/paragraph
        4. Add truncation indicator if content was cut
    """
    words = narrative.split()
    current_count = len(words)

    # Already under limit
    if current_count <= max_words:
        return narrative

    if preserve_structure:
        # Try to find a good cut point at section boundaries
        trimmed = _trim_at_section_boundary(narrative, max_words)
        if trimmed:
            return trimmed

    # Fallback: cut at sentence boundary near max_words
    return _trim_at_sentence_boundary(narrative, max_words)


def _trim_at_section_boundary(narrative: str, max_words: int) -> str:
    """Try to trim at a markdown section boundary (## heading)."""
    # Split into sections by ## headers
    sections = re.split(r'(^##\s+.+$)', narrative, flags=re.MULTILINE)

    result_parts = []
    word_count = 0
    last_complete_section_end = 0

    i = 0
    while i < len(sections):
        part = sections[i]
        part_words = len(part.split())

        # Check if adding this part would exceed limit
        if word_count + part_words > max_words:
            # Stop here, use last complete section
            break

        result_parts.append(part)
        word_count += part_words

        # Track complete sections (header + content pairs)
        if part.startswith('##'):
            # This is a header, next part is content
            if i + 1 < len(sections):
                content = sections[i + 1]
                content_words = len(content.split())
                if word_count + content_words <= max_words:
                    result_parts.append(content)
                    word_count += content_words
                    last_complete_section_end = len(result_parts)
                    i += 2
                    continue
                else:
                    # Can't fit content, revert header
                    result_parts.pop()
                    break
        else:
            last_complete_section_end = len(result_parts)

        i += 1

    if last_complete_section_end > 0:
        trimmed = ''.join(result_parts[:last_complete_section_end])
        if len(trimmed.split()) < len(narrative.split()):
            trimmed = trimmed.rstrip() + '\n\n---\n*[Content trimmed for length]*'
        return trimmed

    return None


def _trim_at_sentence_boundary(narrative: str, max_words: int) -> str:
    """Trim at the last complete sentence that fits within word limit."""
    words = narrative.split()

    # Take max_words and find last sentence boundary
    truncated_text = ' '.join(words[:max_words])

    # Find last sentence ending (., !, ?, or code block end)
    sentence_endings = [
        truncated_text.rfind('. '),
        truncated_text.rfind('.\n'),
        truncated_text.rfind('! '),
        truncated_text.rfind('!\n'),
        truncated_text.rfind('? '),
        truncated_text.rfind('?\n'),
        truncated_text.rfind('```\n'),  # End of code block
    ]

    best_end = max(pos for pos in sentence_endings if pos > 0) if any(pos > 0 for pos in sentence_endings) else -1

    if best_end > len(truncated_text) * 0.5:  # Only use if we keep at least 50%
        trimmed = truncated_text[:best_end + 1].rstrip()
    else:
        # Just cut at word boundary
        trimmed = truncated_text.rstrip()

    # Close any unclosed code blocks
    open_blocks = trimmed.count('```')
    if open_blocks % 2 == 1:
        trimmed += '\n```'

    trimmed += '\n\n---\n*[Content trimmed for length]*'
    return trimmed
