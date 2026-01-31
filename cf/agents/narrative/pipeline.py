"""
Narrative Pipeline - Synthesis and Result Aggregation for Multi-Agent Analysis
"""

import time
from typing import Dict, List, Any, Optional, Callable

from .types import NarrativeStyle, QualityLevel, NarrativeContext
from .generator import NarrativeGenerator


class SynthesisPipeline:
    """
    Pipeline for synthesizing results from multiple agents.

    Combines results from code, docs, web, and KB agents into
    a coherent, validated narrative.
    """

    def __init__(self, llm_callback: Callable, config: Dict[str, Any], repo_tools=None):
        """
        Initialize synthesis pipeline.

        Args:
            llm_callback: LLM callback function
            config: Configuration dictionary
            repo_tools: Repository tools for validation
        """
        self.llm = llm_callback
        self.config = config
        self.repo_tools = repo_tools
        self.generator = NarrativeGenerator(llm_callback, config, repo_tools)

    def synthesize(
        self,
        question: str,
        agent_results: Dict[str, Any],
        file_summaries: Dict[str, Any],
        kb_insights: Optional[Dict[str, Any]] = None,
        style: Optional[NarrativeStyle] = None,
        quality: QualityLevel = QualityLevel.STANDARD
    ) -> Dict[str, Any]:
        """
        Synthesize results from multiple agents.

        Args:
            question: Original question
            agent_results: Results from each agent
            file_summaries: File summaries from analysis
            kb_insights: Optional KB insights
            style: Optional narrative style override
            quality: Quality level for generation

        Returns:
            Synthesized result dictionary
        """
        start_time = time.time()

        # Collect all files analyzed
        all_files = set()
        all_snippets = {}
        all_traces = []

        for result in agent_results.values():
            if isinstance(result, dict):
                files = result.get('files_analyzed', [])
                all_files.update(files)

                # Collect code snippets
                snippets = result.get('code_snippets', {})
                all_snippets.update(snippets)

                # Collect execution traces
                traces = result.get('execution_traces', [])
                all_traces.extend(traces)

        # Create context
        context = NarrativeContext(
            question=question,
            files_analyzed=list(all_files),
            file_summaries=file_summaries,
            agent_results=agent_results,
            kb_insights=kb_insights or {},
            execution_traces=all_traces,
            code_snippets=all_snippets,
            execution_time=time.time() - start_time
        )

        # Determine style if not specified
        if style is None:
            style = self._detect_style(question)

        # Generate narrative
        result = self.generator.generate(context, style, quality)

        return {
            'success': True,
            'narrative': result.narrative,
            'title': result.title,
            'summary': result.summary,
            'confidence': result.confidence,
            'validation': {
                'valid': result.validation.valid,
                'grounding_score': result.validation.grounding_score,
                'issues_count': len(result.validation.issues),
            },
            'quality_score': result.quality_score,
            'word_count': result.word_count,
            'files_referenced': result.files_referenced,
            'code_references': result.code_references,
            'analyzed_file_list': context.files_analyzed,
            'execution_time': time.time() - start_time,
            'style': result.style.value,
            'sections': [
                {'title': s.title, 'confidence': s.confidence}
                for s in result.sections
            ],
        }

    def _detect_style(self, question: str) -> NarrativeStyle:
        """Use LLM to detect appropriate narrative style from question."""
        import json

        # Get available styles dynamically from enum
        style_options = [s.value for s in NarrativeStyle]

        system_prompt = """You are a narrative style classifier. Given a question about code,
determine the most appropriate narrative style for the response.

Respond with ONLY a JSON object: {"style": "<style_value>"}"""

        user_prompt = f"""Question: {question}

Available styles:
{chr(10).join(f'- {s}' for s in style_options)}

Which style best fits this question? Respond with ONLY the JSON object."""

        try:
            response = self.llm(user_prompt, system_prompt)
            if response.get('success'):
                content = response.get('content', '')
                # Parse JSON from response
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0]
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0]

                data = json.loads(content.strip())
                style_value = data.get('style', 'explanation')

                # Map to enum
                for s in NarrativeStyle:
                    if s.value == style_value:
                        return s
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

        # Default fallback
        return NarrativeStyle.EXPLANATION


class ResultAggregator:
    """Aggregates and reconciles results from multiple agents"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def aggregate(
        self,
        agent_results: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Aggregate results from multiple agents.

        Args:
            agent_results: Results keyed by agent name
            weights: Optional weights for each agent

        Returns:
            Aggregated result
        """
        weights = weights or {
            'code': 0.4,
            'kb': 0.3,
            'docs': 0.2,
            'web': 0.1,
        }

        # Collect all files
        all_files = set()
        file_scores = {}

        for agent_name, result in agent_results.items():
            if not isinstance(result, dict):
                continue

            agent_weight = weights.get(agent_name, 0.1)
            files = result.get('files_analyzed', [])

            for f in files:
                all_files.add(f)
                file_scores[f] = file_scores.get(f, 0) + agent_weight

        # Rank files by aggregate score
        ranked_files = sorted(
            all_files,
            key=lambda f: file_scores.get(f, 0),
            reverse=True
        )

        # Combine insights
        combined_insights = {}
        for agent_name, result in agent_results.items():
            if isinstance(result, dict):
                insights = result.get('insights', {})
                if insights:
                    combined_insights[agent_name] = insights

        # Calculate aggregate confidence
        confidences = []
        for agent_name, result in agent_results.items():
            if isinstance(result, dict):
                conf = result.get('confidence', 0.5)
                weight = weights.get(agent_name, 0.1)
                confidences.append(conf * weight)

        aggregate_confidence = sum(confidences) / sum(weights.values()) if weights else 0.5

        return {
            'ranked_files': ranked_files,
            'file_scores': file_scores,
            'combined_insights': combined_insights,
            'confidence': aggregate_confidence,
            'agent_count': len(agent_results),
        }
