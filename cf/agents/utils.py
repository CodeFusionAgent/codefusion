"""
Agent Utility Functions

Shared utilities used across multiple agent pipelines.
"""

from typing import Dict, Tuple, Any


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
