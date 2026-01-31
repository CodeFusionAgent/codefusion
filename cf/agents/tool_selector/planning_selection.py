"""
Tool Selector - LLM-Driven Tool Selection

Simplified wrapper around QuestionClassifier.
Tool selection is handled by the ReAct loop in BaseAgent, not here.
"""

from typing import Dict, Any, Callable

from .classification import QuestionClassifier


class LLMToolSelector:
    """
    LLM-based tool selector.

    This is a thin wrapper around QuestionClassifier.
    The actual tool selection happens in the ReAct loop (BaseAgent._think).
    """

    def __init__(self, llm_callback: Callable, config: Dict[str, Any]):
        self.llm = llm_callback
        self.config = config
        self.classifier = QuestionClassifier(llm_callback, config)

    def classify_question(self, question: str):
        """Classify question using LLM."""
        return self.classifier.classify(question)
