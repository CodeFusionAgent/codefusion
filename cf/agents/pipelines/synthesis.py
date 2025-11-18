"""
Synthesis Pipeline for CodeFusion

Responsible for generating final technical narratives from analyzed data.
All parameters are config-driven for maximum flexibility.
"""

import json
import re
import time
import traceback
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from cf.llm.model_tiers import ModelTier
from cf.agents.utils import calculate_word_count_targets
from cf.utils.llm_parser import LLMResponseParser
from cf.agents.pipelines.synthesis_components.prompt_builder import PromptBuilder
from cf.agents.pipelines.synthesis_components.cross_file_analyzer import CrossFileAnalyzer
from cf.agents.pipelines.synthesis_components.pattern_detector import PatternDetector
from cf.agents.pipelines.synthesis_components.execution_tracer import ExecutionTracer


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

    def __init__(self, repo_path: str, config: Dict[str, Any], llm_client, tiered_llm=None, kb_client=None):
        self.repo_path = repo_path
        self.config = config
        self.llm = llm_client
        self.tiered_llm = tiered_llm  # Optional tiered LLM manager
        self.kb = kb_client  # Optional KB for pattern detection

        # Initialize extracted components
        self.prompt_builder = PromptBuilder(config)
        self.cross_file_analyzer = CrossFileAnalyzer(config)
        self.pattern_detector = PatternDetector(config, kb_client)
        self.execution_tracer = ExecutionTracer(config, kb_client)

        # Compile regex patterns for validation performance (ISSUE #9 fix)
        # Single pass through narrative instead of multiple findall() calls
        self.validation_pattern = re.compile(
            r'(?P<line_ref>line[s]?\s+\d+|L\d+)|'  # Line references
            r'(?P<path_ref>[\w/.-]+\.\w+)|'        # File paths
            r'(?P<code_block>```)|'                # Code blocks
            r'(?P<section>^#+\s+)',                # Section headers
            re.IGNORECASE | re.MULTILINE
        )

    def synthesize(self, question: str, file_summaries: Dict[str, Any], insights: List[Dict[str, Any]],
                   architectural_analysis=None, validation_issues: List[Dict[str, Any]] = None) -> SynthesisResult:
        """
        Generate final technical narrative

        Args:
            question: User's question
            file_summaries: Analyzed file summaries
            insights: List of insights collected during analysis
            architectural_analysis: Optional architectural analysis
            validation_issues: Optional list of validation issues from previous attempt (for retry)

        Returns:
            SynthesisResult with narrative and metadata
        """
        try:
            if validation_issues:
                print(f"📝 [SYNTHESIS] Generating narrative (RETRY with {len(validation_issues)} validation issues)...")
            else:
                print("📝 [SYNTHESIS] Generating narrative...")

            start_time = time.time()

            # Get synthesis parameters from config
            synthesis_config = self.config.get('agents', {}).get('synthesis', {})
            max_files = synthesis_config.get('max_key_files_cited', 7)
            min_files = synthesis_config.get('min_key_files_cited', 3)

            # Select key files to cite (highest relevance)
            key_files = self._select_key_files(file_summaries, max_files)

            # Calculate word count targets proportional to file count (NEW)
            # Use total files analyzed, not just key files, to align with validation
            file_count = len(file_summaries)
            target_min, target_max = calculate_word_count_targets(file_count, self.config)

            # Get words per file for logging
            words_per_file_min = synthesis_config.get('words_per_file_min', 400)
            words_per_file_max = synthesis_config.get('words_per_file_max', 700)

            print(f"   Target word count: {target_min}-{target_max} words (for {file_count} files)")
            print(f"   ({words_per_file_min}-{words_per_file_max} words per file)")

            # Classify question type for appropriate synthesis strategy
            question_type = 'standard'
            if self.tiered_llm:
                classification = self.tiered_llm.classify_question(question)
                question_type = classification.get('type', 'standard')
                print(f"   Question type: {question_type} (confidence: {classification.get('confidence', 0):.2f})")

            # Analyze cross-file relationships (delegate to CrossFileAnalyzer)
            cross_file_relationships = self.cross_file_analyzer.analyze_cross_file_relationships(file_summaries)

            # Detect patterns from KB (delegate to PatternDetector)
            detected_patterns = self.pattern_detector.detect_patterns_from_kb(file_summaries)

            # Trace execution paths for "how" questions (delegate to ExecutionTracer)
            execution_paths = None
            if question_type in ['how_it_works', 'explain', 'flow']:
                execution_paths = self.execution_tracer.trace_execution_paths(question, file_summaries, architectural_analysis)

            # Build synthesis prompt (delegate to PromptBuilder)
            prompt = self.prompt_builder.build_synthesis_prompt(
                question,
                key_files,
                file_summaries,
                insights,
                target_min,
                target_max,
                detected_patterns,
                architectural_analysis,
                execution_paths,
                validation_issues,
                cross_file_relationships
            )

            # Use tiered LLM for synthesis (advanced tier for quality)
            if self.tiered_llm:
                # Use the detailed prompt we built with line number requirements
                # instead of letting synthesize_answer create its own generic prompt
                synthesis_config = self.config.get('agents', {}).get('synthesis', {})
                max_tokens = synthesis_config.get('narrative_max_tokens', 2000)
                response = self.tiered_llm.generate(
                    prompt=prompt,
                    tier=ModelTier.ADVANCED,
                    max_tokens=max_tokens
                )
                # Coerce response to string
                if isinstance(response, dict):
                    narrative = response.get('content', str(response))
                else:
                    narrative = str(response)
                narrative = narrative.strip()
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
            print(traceback.format_exc())

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
        """
        Select most relevant files to cite, prioritizing production files.

        Args:
            file_summaries: Dict mapping file_path -> FileSummary (or dict with 'file_type')
            max_files: Maximum files to select

        Returns:
            List of file paths, prioritized: production > test > utility
        """
        # Separate files by type
        production_files = []
        test_files = []
        utility_files = []

        for path, summary in file_summaries.items():
            # Handle both FileSummary objects and dict representations
            file_type = summary.get('file_type', 'production') if isinstance(summary, dict) else getattr(summary, 'file_type', 'production')

            if file_type == 'production':
                production_files.append(path)
            elif file_type == 'test':
                test_files.append(path)
            else:  # utility
                utility_files.append(path)

        # Combine prioritized: production first, then test, then utility
        prioritized = production_files + test_files + utility_files

        return prioritized[:max_files]


    def _calculate_synthesis_confidence(self,
                                       narrative: str,
                                       file_summaries: Dict[str, Any],
                                       target_min: int,
                                       target_max: int) -> float:
        """Calculate confidence score for synthesis"""
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        base_confidence = thresholds.get('base_confidence', 0.6)
        confidence_increment = thresholds.get('confidence_increment', 0.05)
        max_confidence = thresholds.get('max_confidence', 0.9)

        confidence = base_confidence

        # Check word count (±20% of target)
        word_count = len(narrative.split())
        # Get synthesis quality thresholds from config
        synthesis_thresholds = self.config.get('agents', {}).get('synthesis_thresholds', {})
        word_count_tolerance = synthesis_thresholds.get('word_count_tolerance', 0.8)
        line_refs_high = synthesis_thresholds.get('line_refs_high', 5)
        line_refs_medium = synthesis_thresholds.get('line_refs_medium', 3)
        path_refs_high = synthesis_thresholds.get('path_refs_high', 5)
        path_refs_medium = synthesis_thresholds.get('path_refs_medium', 3)
        code_blocks_min = synthesis_thresholds.get('code_blocks_min', 4)
        sections_min = synthesis_thresholds.get('sections_min', 3)

        target_mid = (target_min + target_max) / 2
        if target_min <= word_count <= target_max:
            confidence += confidence_increment * 2
        elif word_count >= target_mid * word_count_tolerance:
            confidence += confidence_increment

        # Single-pass regex matching for performance (optimized for large narratives)
        # Count all pattern types in one iteration instead of multiple findall() calls
        line_refs = 0
        path_refs = 0
        code_blocks = 0
        sections = 0

        for match in self.validation_pattern.finditer(narrative):
            if match.group('line_ref'):
                line_refs += 1
            elif match.group('path_ref'):
                path_refs += 1
            elif match.group('code_block'):
                code_blocks += 1
            elif match.group('section'):
                sections += 1

        # Evaluate line references
        if line_refs >= line_refs_high:
            confidence += confidence_increment * 2
        elif line_refs >= line_refs_medium:
            confidence += confidence_increment

        # Evaluate file path references
        if path_refs >= path_refs_high:
            confidence += confidence_increment * 2
        elif path_refs >= path_refs_medium:
            confidence += confidence_increment

        # Evaluate code examples
        if code_blocks >= code_blocks_min:
            confidence += confidence_increment

        # Evaluate structural markers
        if sections >= sections_min:
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

            synthesis_config = self.config.get('agents', {}).get('synthesis', {})
            eval_chars = synthesis_config.get('completeness_eval_chars', 2000)

            prompt = f"""Evaluate if this technical narrative fully answers the question.

QUESTION: "{question}"

NARRATIVE:
{narrative[:eval_chars]}

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
                result = LLMResponseParser.extract_json(
                    content,
                    fallback={'completeness_score': 0.6, 'fully_answers': True, 'missing_components': []}
                )
                if result:
                    print(f"✅ [SYNTHESIS] Completeness: {result.get('completeness_score', 0):.2f}")
                    return result

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

