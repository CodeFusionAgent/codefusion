#!/usr/bin/env python3
"""
Multi-Model LLM Manager with Tiered Model Support

Optimizes cost and latency by matching task complexity to model capability.

Example tier configuration:
- Fast tier: Simple tasks (file summaries, classification, coordination)
- Standard tier: Balanced tasks (general analysis)
- Advanced tier: Complex tasks (final synthesis, deep reasoning)

All models are fully configurable via config.yaml - no hardcoded defaults.
"""

from typing import Dict, Any, Optional, List
from enum import Enum
import time

from cf.llm.factory import LLMFactory


class ModelTier(Enum):
    """Model tier for different task complexities"""
    FAST = "fast"           # Fast models for simple tasks (summaries, classification)
    STANDARD = "standard"   # Balanced models for moderate tasks
    ADVANCED = "advanced"   # Advanced models for complex synthesis


class TieredLLMManager:
    """
    Manages multiple LLM models with different tiers for different tasks.

    Automatically routes tasks to appropriate models based on complexity:
    - File summaries → Fast tier (10x faster, 20x cheaper)
    - Question classification → Fast tier
    - Coordination decisions → Fast tier
    - Final synthesis → Advanced tier (best quality)

    All models are configured via config.yaml with no hardcoded defaults.
    Raises ValueError if required tier configuration is missing.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize tiered LLM manager.

        Args:
            config: Configuration with model tier settings
        """
        self.config = config
        self.llm_config = config.get('llm', {})
        self.tier_config = self.llm_config.get('tiers', {})

        # Initialize models for each tier
        self.models = {}
        self._initialize_models()

        # Track usage statistics
        self.usage_stats = {
            'fast': {'calls': 0, 'tokens': 0, 'time': 0.0},
            'standard': {'calls': 0, 'tokens': 0, 'time': 0.0},
            'advanced': {'calls': 0, 'tokens': 0, 'time': 0.0}
        }

    def _initialize_models(self):
        """Initialize LLM models for each tier"""
        # Validate configuration
        if not self.tier_config:
            raise ValueError(
                "No model tiers configured. Please add 'llm.tiers' section to config.yaml"
            )

        required_tiers = ['fast', 'standard', 'advanced']
        for tier in required_tiers:
            if tier not in self.tier_config:
                raise ValueError(
                    f"Missing '{tier}' tier in config. Please configure llm.tiers.{tier}.model"
                )
            if 'model' not in self.tier_config[tier]:
                raise ValueError(
                    f"Missing model name for '{tier}' tier. Please set llm.tiers.{tier}.model"
                )

        # Initialize models from config only (no hardcoded defaults)
        for tier_name in required_tiers:
            tier_config = self.tier_config[tier_name]
            model_name = tier_config['model']

            self.models[tier_name] = LLMFactory.create_llm(
                model_name=model_name,
                config=self.llm_config
            )

    def generate(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.STANDARD,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate completion using appropriate model tier.

        Args:
            prompt: Input prompt
            tier: Model tier to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments for LLM

        Returns:
            Generated text
        """
        start_time = time.time()

        # Get model for tier
        model = self.models.get(tier.value)
        if not model:
            # Fallback to standard if tier not available
            model = self.models['standard']
            tier_name = 'standard'
        else:
            tier_name = tier.value

        # Generate completion
        response = model.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        # Track usage
        elapsed = time.time() - start_time
        self.usage_stats[tier_name]['calls'] += 1
        self.usage_stats[tier_name]['time'] += elapsed

        # Estimate tokens (rough approximation) with safe coercion
        try:
            prompt_str = str(prompt)
            if isinstance(response, dict):
                # Prefer textual content if available; else serialize
                resp_raw = response.get('content') if 'content' in response else response
                response_str = resp_raw if isinstance(resp_raw, str) else str(resp_raw)
            else:
                response_str = str(response)
            estimated_tokens = len(prompt_str.split()) + len(response_str.split())
        except Exception:
            estimated_tokens = len(str(prompt).split())

        self.usage_stats[tier_name]['tokens'] += estimated_tokens

        return response

    def summarize_file(self, file_content: str, file_path: str, question: str) -> str:
        """
        Summarize file content using fast tier model.

        Fast, cheap operation suitable for batch processing.

        Args:
            file_content: File content to summarize (with or without line numbers)
            file_path: Path to file
            question: User question for context

        Returns:
            File summary with line number references
        """
        # Add line numbers if not already present
        if not file_content.startswith('    1'):
            lines = file_content.split('\n')
            numbered_content = '\n'.join(f'{i+1:5d}  {line}' for i, line in enumerate(lines))
        else:
            numbered_content = file_content

        prompt = f"""Analyze this file in context of the question: "{question}"

File: {file_path}

```
{numbered_content}
```

Extract key information and return as JSON:

{{
    "key_features": ["feature1", "feature2", "feature3"],
    "architectural_insights": "How this file fits into the architecture and what patterns it uses",
    "relevance": "How this file relates to the question"
}}

REQUIREMENTS:
1. key_features: 3-5 main features/responsibilities of this file
2. architectural_insights: Brief paragraph about architecture, patterns, and design
3. relevance: How this file relates to the user's question

Return ONLY valid JSON, no additional text."""

        return self.generate(
            prompt=prompt,
            tier=ModelTier.FAST,
            temperature=0.3,
            max_tokens=500
        )

    def classify_question(self, question: str) -> Dict[str, Any]:
        """
        Classify question type using fast tier model.

        Args:
            question: User question

        Returns:
            Classification result with type and metadata
        """
        prompt = f"""Classify this question into one of these types:

Question: "{question}"

Types:
- life_of_x: Trace execution flow (how does X work, lifecycle, what happens when)
- comparison: Compare two or more things (vs, versus, difference, compare)
- debugging: Root cause analysis (why, debug, broken, slow, error)
- refactoring: Improvement suggestions (refactor, improve, redesign, optimize)
- architecture: High-level design (architecture, patterns, structure)
- summary: General overview (what is, describe, overview)
- standard: Specific implementation questions

Return JSON only:
{{
    "type": "life_of_x|comparison|debugging|refactoring|architecture|summary|standard",
    "confidence": 0.0-1.0,
    "key_entities": ["entity1", "entity2"],
    "focus": "brief description"
}}"""

        response = self.generate(
            prompt=prompt,
            tier=ModelTier.FAST,
            temperature=0.1,
            max_tokens=200
        )

        # Parse JSON response (accept dict or string)
        import json
        if isinstance(response, dict):
            return response
        try:
            return json.loads(str(response))
        except Exception:
            # Fallback classification
            return {
                'type': 'standard',
                'confidence': 0.5,
                'key_entities': [],
                'focus': question[:100]
            }

    def decide_coordination(
        self,
        pass_num: int,
        insights: List[Dict],
        max_passes: int
    ) -> Dict[str, Any]:
        """
        Decide next step in multi-pass coordination using fast tier model.

        Args:
            pass_num: Current pass number
            insights: Insights gathered so far
            max_passes: Maximum allowed passes

        Returns:
            Decision with action and reasoning
        """
        prompt = f"""Analyze discovery pass results and decide next action.

Pass: {pass_num}/{max_passes}
Insights found: {len(insights)}

Insights summary:
{self._format_insights_summary(insights)}

Decide one of:
- retry: Current pass didn't find enough, try broader search
- next_pass: Good progress, move to next discovery pass
- complete: Sufficient insights gathered, proceed to analysis

Return JSON only:
{{
    "action": "retry|next_pass|complete",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

        response = self.generate(
            prompt=prompt,
            tier=ModelTier.FAST,
            temperature=0.2,
            max_tokens=150
        )

        # Parse JSON response (accept dict or string)
        import json
        if isinstance(response, dict):
            return response
        try:
            return json.loads(str(response))
        except Exception:
            # Fallback heuristics
            if len(insights) < 2 and pass_num < max_passes:
                return {'action': 'retry', 'confidence': 0.7, 'reasoning': 'Too few insights'}
            elif pass_num >= max_passes or len(insights) >= 5:
                return {'action': 'complete', 'confidence': 0.8, 'reasoning': 'Sufficient data'}
            else:
                return {'action': 'next_pass', 'confidence': 0.6, 'reasoning': 'Continue discovery'}

    def synthesize_answer(
        self,
        question: str,
        question_type: str,
        insights: List[Dict],
        context: Dict[str, Any]
    ) -> str:
        """
        Synthesize final answer using advanced tier model.

        This is the most complex task requiring deep reasoning.

        Args:
            question: User question
            question_type: Question classification
            insights: All gathered insights
            context: Additional context

        Returns:
            Synthesized narrative answer
        """
        # Use question-type-specific template
        template = self._get_synthesis_template(question_type)

        prompt = f"""{template}

Question: "{question}"
Type: {question_type}

Insights:
{self._format_insights_for_synthesis(insights)}

Context:
{self._format_context(context)}

Provide a comprehensive, well-structured answer that directly addresses the question."""

        response = self.generate(
            prompt=prompt,
            tier=ModelTier.ADVANCED,
            temperature=0.4,
            max_tokens=2000
        )
        # Coerce to string for downstream usage
        if isinstance(response, dict):
            content = response.get('content') if 'content' in response else None
            return content if isinstance(content, str) else str(response)
        return str(response)

    def _format_insights_summary(self, insights: List[Dict]) -> str:
        """Format insights for coordination decision"""
        if not insights:
            return "No insights yet"

        summary_lines = []
        for i, insight in enumerate(insights[:5], 1):  # First 5
            summary_lines.append(f"{i}. {insight.get('summary', 'N/A')[:100]}")

        if len(insights) > 5:
            summary_lines.append(f"... and {len(insights) - 5} more")

        return "\n".join(summary_lines)

    def _format_insights_for_synthesis(self, insights: List[Dict]) -> str:
        """Format insights for final synthesis"""
        sections = []
        for i, insight in enumerate(insights, 1):
            sections.append(f"""
Insight {i}:
Source: {insight.get('source', 'unknown')}
Summary: {insight.get('summary', 'N/A')}
Details: {insight.get('details', 'N/A')[:500]}
""")
        return "\n".join(sections)

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for synthesis"""
        lines = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                lines.append(f"{key}: {len(value)} items")
            else:
                lines.append(f"{key}: {str(value)[:100]}")
        return "\n".join(lines)

    def _get_synthesis_template(self, question_type: str) -> str:
        """Get question-type-specific synthesis template"""
        templates = {
            'life_of_x': """You are tracing execution flow through a codebase.
Structure your answer as:
1. **Entry Point**: Where the journey begins
2. **Execution Flow**: Step-by-step progression with code snippets
3. **Key Transformations**: Important data/state changes
4. **Exit Point**: Where the journey ends
5. **Summary**: High-level overview""",

            'comparison': """You are comparing multiple approaches/components.
Structure your answer as:
1. **Overview**: What's being compared
2. **Comparison Table**: Side-by-side analysis
3. **Trade-offs**: Pros and cons of each
4. **Recommendation**: Which to use when""",

            'debugging': """You are performing root cause analysis.
Structure your answer as:
1. **Symptoms**: What's wrong
2. **Investigation**: How to diagnose
3. **Root Cause**: Why it's happening
4. **Fix**: How to resolve it
5. **Prevention**: How to avoid in future""",

            'refactoring': """You are providing refactoring guidance.
Structure your answer as:
1. **Current State**: What exists now
2. **Issues**: What needs improvement
3. **Refactoring Plan**: Step-by-step approach
4. **Expected Benefits**: Why it's better""",

            'architecture': """You are analyzing architectural design.
Structure your answer as:
1. **Architecture Overview**: High-level design
2. **Key Patterns**: Design patterns used
3. **Component Relationships**: How pieces connect
4. **Quality Assessment**: Strengths and weaknesses""",

            'summary': """You are providing a codebase overview.
Structure your answer as:
1. **Purpose**: What the codebase does
2. **Architecture**: How it's organized
3. **Key Components**: Main building blocks
4. **Technologies**: Stack and dependencies""",

            'standard': """You are a senior software architect analyzing code.
Provide a comprehensive answer that:
1. Directly answers the question
2. Provides relevant code examples
3. Explains technical details
4. Offers actionable insights"""
        }

        return templates.get(question_type, templates['standard'])

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get usage statistics for all tiers"""
        total_calls = sum(stats['calls'] for stats in self.usage_stats.values())
        total_time = sum(stats['time'] for stats in self.usage_stats.values())

        return {
            'total_calls': total_calls,
            'total_time': total_time,
            'by_tier': self.usage_stats,
            'cost_estimate': self._estimate_cost()
        }

    def _estimate_cost(self) -> Dict[str, float]:
        """Estimate cost based on usage (reads from config)"""
        tier_costs = {}
        total = 0.0

        for tier, stats in self.usage_stats.items():
            tokens = stats['tokens']

            # Get cost from config (per 1M tokens)
            cost_per_1m = self.tier_config.get(tier, {}).get('cost_per_1m', 0.0)
            cost = (tokens / 1_000_000) * cost_per_1m

            tier_costs[tier] = cost
            total += cost

        return {
            'by_tier': tier_costs,
            'total': total
        }
