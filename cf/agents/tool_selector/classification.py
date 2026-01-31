"""
Tool Selector Classification - LLM-Driven Question Classification

Pure LLM-driven classification without hardcoded patterns.
The LLM determines question category, complexity, and key concepts.
"""

import re
from typing import Dict, List, Any, Optional, Callable

from cf.utils.llm_parser import LLMResponseParser

from .types import QuestionCategory, Complexity, QuestionClassification


class QuestionClassifier:
    """
    LLM-driven question classification.

    Uses LLM to classify questions without hardcoded patterns.
    Falls back to minimal defaults if LLM fails.
    """

    def __init__(self, llm_callback: Callable, config: Dict[str, Any]):
        self.llm = llm_callback
        self.config = config
        self._classification_cache: Dict[str, QuestionClassification] = {}

    def classify(self, question: str) -> QuestionClassification:
        """Classify question using LLM."""
        cache_key = question.strip().lower()[:100]
        if cache_key in self._classification_cache:
            return self._classification_cache[cache_key]

        classification = self._classify_with_llm(question)
        if classification:
            self._classification_cache[cache_key] = classification
            return classification

        # Minimal fallback - no hardcoded patterns
        classification = self._minimal_fallback(question)
        self._classification_cache[cache_key] = classification
        return classification

    def _classify_with_llm(self, question: str) -> Optional[QuestionClassification]:
        """Use LLM for sophisticated question classification"""
        prompt = f"""Analyze this code analysis question and classify it.

Question: "{question}"

Provide classification as JSON:
{{
    "category": "lookup|flow|architecture|explanation|comparison|debugging|documentation|performance|security|refactoring",
    "complexity": "simple|moderate|complex|expert",
    "needs_kb": true/false (needs structural code analysis like call graphs),
    "needs_llm": true/false (needs LLM reasoning beyond simple lookups),
    "needs_web": true/false (needs external documentation),
    "suggested_agents": ["code", "docs", "web", "kb"],
    "key_concepts": ["concept1", "concept2"],
    "reasoning": "brief explanation of classification"
}}

Classification guide:
- lookup: "where is X?", "find X", "which file contains X?"
- flow: "how does X work?", "what calls X?", "trace the execution"
- architecture: "what is the structure?", "how is it organized?"
- explanation: "why does X do Y?", "what is the purpose?"
- comparison: "difference between X and Y?"
- debugging: "why is X broken?", "what causes error?"
- documentation: "how to use X?", "API for X?"
- performance: "why is X slow?", "how to optimize?"
- security: "is X secure?", "vulnerability in X?"
- refactoring: "how to improve X?", "better way to do X?"

Complexity:
- simple: Single file, direct answer (1-2 tools)
- moderate: Multiple files, some reasoning (3-5 tools)
- complex: Cross-cutting concerns, deep analysis (5-10 tools)
- expert: Architecture-level, synthesis required (10+ tools)"""

        try:
            response = self.llm(
                prompt,
                system_prompt="You classify code analysis questions. Return valid JSON only, no markdown."
            )
            result = LLMResponseParser.safe_parse_llm_response(response, fallback=None)

            if result and 'category' in result:
                # Map string to enum
                category_str = result.get('category', 'explanation')
                try:
                    category = QuestionCategory(category_str)
                except ValueError:
                    category = QuestionCategory.EXPLANATION

                complexity_str = result.get('complexity', 'moderate')
                try:
                    complexity = Complexity(complexity_str)
                except ValueError:
                    complexity = Complexity.MODERATE

                return QuestionClassification(
                    category=category,
                    complexity=complexity,
                    needs_kb=result.get('needs_kb', True),
                    needs_llm=result.get('needs_llm', True),
                    needs_web=result.get('needs_web', False),
                    suggested_agents=result.get('suggested_agents', ['code']),
                    key_concepts=result.get('key_concepts', []),
                    reasoning=result.get('reasoning', ''),
                    confidence=0.85
                )
        except Exception:
            pass

        return None

    def _minimal_fallback(self, question: str) -> QuestionClassification:
        """Minimal fallback when LLM classification fails - no hardcoded patterns."""
        # Use MODERATE as safe default - no arbitrary word count thresholds
        complexity = Complexity.MODERATE

        # Extract concepts structurally (quoted strings, backticks, CamelCase)
        concepts = []
        concepts.extend(re.findall(r'`([^`]+)`', question))
        concepts.extend(re.findall(r'"([^"]+)"', question))
        concepts.extend(re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', question))
        concepts = list(set(concepts))[:10]

        return QuestionClassification(
            category=QuestionCategory.EXPLANATION,
            complexity=complexity,
            needs_kb=True,
            needs_llm=True,
            needs_web=False,
            suggested_agents=['code'],
            key_concepts=concepts,
            reasoning='LLM classification failed, using minimal defaults',
            confidence=0.5
        )
