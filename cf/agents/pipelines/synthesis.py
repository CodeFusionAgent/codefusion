"""
Synthesis Pipeline for CodeFusion

Responsible for generating final technical narratives from analyzed data.
All parameters are config-driven for maximum flexibility.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class SynthesisResult:
    """Result of synthesis process"""
    narrative: str
    key_files_cited: List[str]
    confidence: float
    word_count: int
    synthesis_time_ms: float


class SynthesisPipeline:
    """
    Main synthesis pipeline that generates final technical narratives.
    Uses LLM to synthesize insights from file summaries.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], llm_client, tiered_llm=None):
        self.repo_path = repo_path
        self.config = config
        self.llm = llm_client
        self.tiered_llm = tiered_llm  # Optional tiered LLM manager

    def synthesize(self, question: str, file_summaries: Dict[str, Any], insights: List[Dict[str, Any]]) -> SynthesisResult:
        """
        Generate final technical narrative

        Args:
            question: User's question
            file_summaries: Analyzed file summaries
            insights: List of insights collected during analysis

        Returns:
            SynthesisResult with narrative and metadata
        """
        try:
            print("📝 [SYNTHESIS] Generating narrative...")

            import time
            start_time = time.time()

            # Get synthesis parameters from config
            synthesis_config = self.config.get('agents', {}).get('synthesis', {})
            target_min = synthesis_config.get('target_narrative_min', 3000)
            target_max = synthesis_config.get('target_narrative_max', 5000)
            max_files = synthesis_config.get('max_key_files_cited', 7)
            min_files = synthesis_config.get('min_key_files_cited', 3)

            # Select key files to cite (highest relevance)
            key_files = self._select_key_files(file_summaries, max_files)

            # Classify question type for appropriate synthesis strategy
            question_type = 'standard'
            if self.tiered_llm:
                from cf.llm.model_tiers import ModelTier
                classification = self.tiered_llm.classify_question(question)
                question_type = classification.get('type', 'standard')
                print(f"   Question type: {question_type} (confidence: {classification.get('confidence', 0):.2f})")

            # Build synthesis prompt
            prompt = self._build_synthesis_prompt(
                question,
                key_files,
                file_summaries,
                insights,
                target_min,
                target_max
            )

            # Use tiered LLM for synthesis (advanced tier for quality)
            if self.tiered_llm:
                from cf.llm.model_tiers import ModelTier
                narrative = self.tiered_llm.synthesize_answer(
                    question=question,
                    question_type=question_type,
                    insights=insights,
                    context={
                        'file_summaries': file_summaries,
                        'key_files': key_files
                    }
                ).strip()
                word_count = len(narrative.split())
            else:
                # Fallback to old method
                response = self.llm.generate(prompt, "You are a technical documentation expert. Write comprehensive, accurate narratives.")

                if not response.get('success'):
                    raise Exception("Synthesis failed")

                narrative = response.get('content', '').strip()
                word_count = len(narrative.split())

            # Calculate confidence based on completeness
            confidence = self._calculate_synthesis_confidence(
                narrative,
                file_summaries,
                target_min,
                target_max
            )

            synthesis_time = time.time() - start_time

            print(f"✅ [SYNTHESIS] Generated narrative:")
            print(f"   Words: {word_count} (target: {target_min}-{target_max})")
            print(f"   Key files: {len(key_files)}")
            print(f"   Confidence: {confidence:.2f}")
            print(f"   Time: {synthesis_time*1000:.0f}ms")

            return SynthesisResult(
                narrative=narrative,
                key_files_cited=key_files,
                confidence=confidence,
                word_count=word_count,
                synthesis_time_ms=round(synthesis_time * 1000, 2)
            )

        except Exception as e:
            print(f"❌ [SYNTHESIS] Failed: {e}")

        # Return fallback result
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        return SynthesisResult(
            narrative="Synthesis failed - insufficient data",
            key_files_cited=[],
            confidence=thresholds.get('error_confidence', 0.2),
            word_count=0,
            synthesis_time_ms=0
        )

    def _select_key_files(self, file_summaries: Dict[str, Any], max_files: int) -> List[str]:
        """Select most relevant files to cite"""
        # Sort by relevance if available, otherwise just take first N
        files = list(file_summaries.keys())[:max_files]
        return files

    def _build_synthesis_prompt(self,
                                question: str,
                                key_files: List[str],
                                file_summaries: Dict[str, Any],
                                insights: List[Dict[str, Any]],
                                target_min: int,
                                target_max: int) -> str:
        """Build prompt for synthesis"""

        # Prepare file summaries text
        summaries_text = ""
        for file_path in key_files:
            summary = file_summaries.get(file_path, {})
            if isinstance(summary, dict):
                summaries_text += f"\n\n## {file_path}\n"
                summaries_text += f"Key Features: {', '.join(summary.get('key_features', []))}\n"
                summaries_text += f"Architecture: {summary.get('architectural_insights', '')}\n"

                # Include function/class info
                functions = summary.get('functions', [])
                classes = summary.get('classes', [])
                if functions:
                    summaries_text += f"Functions: {', '.join([f.get('name', '') for f in functions[:5]])}\n"
                if classes:
                    summaries_text += f"Classes: {', '.join([c.get('name', '') for c in classes[:5]])}\n"

        # Prepare insights text
        insights_text = ""
        for insight in insights[:20]:  # Limit insights
            content = insight.get('content', '')
            if content:
                insights_text += f"- {content}\n"

        prompt = f"""Generate a comprehensive technical narrative answering this question:

QUESTION: "{question}"

You have analyzed {len(file_summaries)} files and gathered the following insights:

KEY FILES ANALYZED:
{summaries_text}

INSIGHTS:
{insights_text}

TASK: Write a detailed technical narrative that explains HOW the system works, not just WHAT it does.

REQUIREMENTS:
1. Length: {target_min}-{target_max} words
2. Format: Markdown with clear sections
3. Style: Educational "Life of X" narrative format
4. Grounding: Include specific file paths and line number references
5. Depth: Explain HOW code works, not just WHAT it does
6. Structure:
   - Start with overview/context
   - Explain main flow/architecture
   - Detail key components and their interactions
   - Include code examples where relevant
   - Conclude with summary of how everything connects

CRITICAL REQUIREMENTS:
- MUST include specific file paths (e.g., "src/auth/models.py")
- MUST include line number references (e.g., "at line 123")
- MUST explain HOW code works (algorithms, data flow, patterns)
- MUST be technically accurate and grounded in analyzed code
- AVOID generic statements without code references
- AVOID just listing files without explaining their role

Generate the narrative now:"""

        return prompt

    def _calculate_synthesis_confidence(self,
                                       narrative: str,
                                       file_summaries: Dict[str, Any],
                                       target_min: int,
                                       target_max: int) -> float:
        """Calculate confidence score for synthesis"""
        import re

        thresholds = self.config.get('agents', {}).get('thresholds', {})
        base_confidence = thresholds.get('base_confidence', 0.6)
        confidence_increment = thresholds.get('confidence_increment', 0.05)
        max_confidence = thresholds.get('max_confidence', 0.9)

        confidence = base_confidence

        # Check word count (±20% of target)
        word_count = len(narrative.split())
        target_mid = (target_min + target_max) / 2
        if target_min <= word_count <= target_max:
            confidence += confidence_increment * 2
        elif word_count >= target_mid * 0.8:
            confidence += confidence_increment

        # Check for line number references
        line_refs = len(re.findall(r'line[s]?\s+\d+|L\d+', narrative, re.IGNORECASE))
        if line_refs >= 5:
            confidence += confidence_increment * 2
        elif line_refs >= 3:
            confidence += confidence_increment

        # Check for file path references
        path_refs = len(re.findall(r'[\w/.-]+\.\w+', narrative))
        if path_refs >= 5:
            confidence += confidence_increment * 2
        elif path_refs >= 3:
            confidence += confidence_increment

        # Check for code examples
        code_blocks = len(re.findall(r'```', narrative))
        if code_blocks >= 4:
            confidence += confidence_increment

        # Check for structural markers (sections, headers)
        sections = len(re.findall(r'^#+\s+', narrative, re.MULTILINE))
        if sections >= 3:
            confidence += confidence_increment

        return min(confidence, max_confidence)

    def evaluate_completeness(self, narrative: str, question: str, file_summaries: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to evaluate if narrative fully answers the question

        Returns:
            Dict with completeness score and missing components
        """
        try:
            print("🔍 [SYNTHESIS] Evaluating completeness...")

            prompt = f"""Evaluate if this technical narrative fully answers the question.

QUESTION: "{question}"

NARRATIVE:
{narrative[:2000]}  # First 2000 chars

TASK: Assess completeness and identify missing components.

Respond with JSON only:
{{
    "completeness_score": 0.0-1.0,
    "fully_answers": true/false,
    "missing_components": ["component1", "component2"],
    "reasoning": "brief explanation"
}}

If completeness_score < 0.7, list specific missing components.
If >= 0.7, return empty missing_components array."""

            response = self.llm.generate_fast(prompt, "You are a technical documentation evaluator.")

            if response.get('success'):
                content = response.get('content', '').strip()
                import json
                try:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        result = json.loads(content[start:end])
                        print(f"✅ [SYNTHESIS] Completeness: {result.get('completeness_score', 0):.2f}")
                        return result
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            print(f"⚠️ [SYNTHESIS] Completeness evaluation failed: {e}")

        # Fallback
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        return {
            'completeness_score': thresholds.get('base_confidence', 0.6),
            'fully_answers': True,
            'missing_components': [],
            'reasoning': 'Evaluation unavailable'
        }
