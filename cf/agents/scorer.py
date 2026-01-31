"""
File Analyzer Factory - Factory Functions for File Analysis

This module provides factory functions for creating file analyzers.
The FileAnalyzer is used for AST-based code structure extraction.

NOTE: FileRelevanceScorer was removed because:
1. It used hardcoded category keywords (model, view, controller, etc.)
2. This contradicts the LLM-driven discovery design
3. The ReAct loop dynamically discovers files without pre-ranking
4. Question keywords are extracted dynamically in base.py
"""

from typing import Optional, Callable

from .analyzer import FileAnalyzer


def create_file_analyzer(repo_path: str, llm_callback: Optional[Callable] = None) -> FileAnalyzer:
    """
    Factory function for file analyzer.

    Args:
        repo_path: Path to repository root
        llm_callback: Optional LLM callback for enhanced analysis

    Returns:
        FileAnalyzer instance
    """
    return FileAnalyzer(repo_path, llm_callback)
