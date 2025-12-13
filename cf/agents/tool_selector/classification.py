"""
Tool Selector Classification - Question Classification Logic
"""

import re
from typing import Dict, List, Any, Optional, Callable

from cf.utils.llm_parser import LLMResponseParser

from .types import QuestionCategory, Complexity, QuestionClassification


class QuestionClassifier:
    """
    Classifies questions to determine analysis approach.

    Uses both LLM and heuristic classification.
    """

    # Question patterns for heuristic classification
    QUESTION_PATTERNS = {
        QuestionCategory.LOOKUP: [
            r'where is', r'find', r'which file', r'locate', r'what file',
            r'show me', r'get me', r'list all', r'what is the.*path'
        ],
        QuestionCategory.FLOW: [
            r'how does', r'what calls', r'trace', r'flow', r'lifecycle',
            r'execution path', r'when is.*called', r'what triggers',
            r'what happens when', r'order of', r'sequence of'
        ],
        QuestionCategory.ARCHITECTURE: [
            r'architecture', r'structure', r'design', r'pattern',
            r'organization', r'how.*organized', r'module.*layout',
            r'dependency.*graph', r'system.*overview'
        ],
        QuestionCategory.EXPLANATION: [
            r'why', r'explain', r'purpose', r'what does.*do',
            r'how.*work', r'reason for', r'meaning of'
        ],
        QuestionCategory.COMPARISON: [
            r'difference', r'compare', r'versus', r'vs\b', r'between',
            r'which is better', r'pros.*cons', r'trade.?off'
        ],
        QuestionCategory.DEBUGGING: [
            r'bug', r'error', r'issue', r'not working', r'broken',
            r'fix', r'wrong', r'fail', r'crash', r'exception'
        ],
        QuestionCategory.DOCUMENTATION: [
            r'document', r'readme', r'guide', r'tutorial', r'api doc',
            r'usage', r'example', r'how to use'
        ],
        QuestionCategory.PERFORMANCE: [
            r'performance', r'slow', r'optimize', r'speed', r'memory',
            r'efficient', r'bottleneck', r'profil'
        ],
        QuestionCategory.SECURITY: [
            r'security', r'vulnerab', r'auth', r'permission', r'access',
            r'injection', r'xss', r'csrf', r'encrypt'
        ],
        QuestionCategory.REFACTORING: [
            r'refactor', r'improve', r'clean.?up', r'simplif',
            r'better way', r'restructure', r'technical debt'
        ]
    }

    def __init__(self, llm_callback: Callable, config: Dict[str, Any]):
        """
        Initialize classifier.

        Args:
            llm_callback: Callable(prompt, system_prompt) -> response dict
            config: Configuration dictionary
        """
        self.llm = llm_callback
        self.config = config
        self._classification_cache: Dict[str, QuestionClassification] = {}

    def classify(self, question: str) -> QuestionClassification:
        """
        Classify a question to determine analysis approach.

        Args:
            question: User question

        Returns:
            QuestionClassification with category, complexity, etc.
        """
        # Check cache
        cache_key = question.strip().lower()[:100]
        if cache_key in self._classification_cache:
            return self._classification_cache[cache_key]

        # Try LLM classification first
        classification = self._classify_with_llm(question)
        if classification and classification.confidence > 0.7:
            self._classification_cache[cache_key] = classification
            return classification

        # Fallback to heuristic
        classification = self._classify_heuristic(question)
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

    def _classify_heuristic(self, question: str) -> QuestionClassification:
        """Fallback heuristic classification"""
        q = question.lower()

        # Find matching category
        category = QuestionCategory.EXPLANATION  # default
        max_matches = 0

        for cat, patterns in self.QUESTION_PATTERNS.items():
            matches = sum(1 for p in patterns if re.search(p, q))
            if matches > max_matches:
                max_matches = matches
                category = cat

        # Determine complexity
        word_count = len(question.split())
        has_multiple_concepts = len(re.findall(r'\b(?:and|or|also|with|between)\b', q)) > 0

        if word_count < 10 and not has_multiple_concepts:
            complexity = Complexity.SIMPLE
        elif word_count < 25 or has_multiple_concepts:
            complexity = Complexity.MODERATE
        elif word_count < 50:
            complexity = Complexity.COMPLEX
        else:
            complexity = Complexity.EXPERT

        # Extract key concepts
        key_concepts = self._extract_concepts(question)

        # Determine needs
        needs_kb = category in [
            QuestionCategory.FLOW,
            QuestionCategory.ARCHITECTURE,
            QuestionCategory.REFACTORING
        ]
        needs_web = category in [
            QuestionCategory.DOCUMENTATION,
            QuestionCategory.SECURITY
        ]

        # Suggest agents
        suggested_agents = ['code']
        if needs_kb:
            suggested_agents.append('kb')
        if needs_web:
            suggested_agents.append('web')
        if category == QuestionCategory.DOCUMENTATION:
            suggested_agents.append('docs')

        return QuestionClassification(
            category=category,
            complexity=complexity,
            needs_kb=needs_kb,
            needs_llm=True,
            needs_web=needs_web,
            suggested_agents=suggested_agents,
            key_concepts=key_concepts,
            reasoning=f'Heuristic classification: {category.value} question, {complexity.value} complexity',
            confidence=0.6
        )

    def _extract_concepts(self, question: str) -> List[str]:
        """Extract technical concepts from question"""
        # Common technical terms
        tech_patterns = [
            r'\b(?:class|function|method|module|package|file)\s+(\w+)',
            r'\b(\w+)(?:Agent|Manager|Handler|Service|Controller|Factory|Builder)',
            r'\b(\w+)\.py\b',
            r'`([^`]+)`',
            r'"([^"]+)"',
        ]

        concepts = []
        for pattern in tech_patterns:
            matches = re.findall(pattern, question, re.IGNORECASE)
            concepts.extend(matches)

        # Also get CamelCase words
        camel_case = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', question)
        concepts.extend(camel_case)

        # Deduplicate and limit
        return list(set(concepts))[:10]
