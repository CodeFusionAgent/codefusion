"""
Experiment Runner for A/B Testing

Enables comparing different analysis strategies:
- AST-based vs LLM-based
- Different embedding models
- Graph queries vs semantic search

Goal: Answer questions like "Does AST help/hinder certain queries?"
"""

import time
import json
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment variant"""
    name: str
    description: str
    config: Dict[str, Any]
    enabled_agents: List[str] = field(default_factory=list)
    disabled_features: List[str] = field(default_factory=list)


@dataclass
class ExperimentResult:
    """Results from a single experiment run"""
    variant_name: str
    query: str
    success: bool
    answer: str = ""
    confidence: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ComparisonResult:
    """Comparison between multiple experiment variants"""
    query: str
    variants: List[ExperimentResult]
    winner: Optional[str] = None
    comparison_metrics: Dict[str, Any] = field(default_factory=dict)


class ExperimentRunner:
    """
    Run A/B tests comparing different analysis strategies.

    Example usage:
        runner = ExperimentRunner()

        # Define variants
        variant_a = ExperimentConfig(
            name="with_ast",
            description="Using AST-based pattern detection",
            config={'knowledge_base': {'patterns': {'enabled': True}}}
        )
        variant_b = ExperimentConfig(
            name="without_ast",
            description="Using only semantic search",
            config={'knowledge_base': {'patterns': {'enabled': False}}}
        )

        # Run experiment
        results = runner.run_experiment(
            query="Find all singleton patterns",
            variants=[variant_a, variant_b],
            analyzer_factory=create_analyzer
        )

        # Compare
        comparison = runner.compare_results(results)
    """

    def __init__(self, output_dir: str = "cf_experiments"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.experiments: List[ComparisonResult] = []

    def run_experiment(
        self,
        query: str,
        variants: List[ExperimentConfig],
        analyzer_factory: Callable[[Dict[str, Any]], Any],
        metrics_extractor: Optional[Callable[[Any], Dict[str, Any]]] = None
    ) -> List[ExperimentResult]:
        """
        Run the same query with multiple strategy variants.

        Args:
            query: Question to analyze
            variants: List of experiment configurations to test
            analyzer_factory: Function that creates analyzer from config
            metrics_extractor: Optional function to extract metrics from analyzer

        Returns:
            List of results, one per variant
        """
        results = []

        for variant in variants:
            print(f"\n=, Running experiment variant: {variant.name}")
            print(f"   Description: {variant.description}")

            start_time = time.time()

            try:
                # Create analyzer with variant config
                analyzer = analyzer_factory(variant.config)

                # Run analysis
                analysis_result = analyzer.analyze(query)

                # Extract metrics
                metrics = {}
                if metrics_extractor:
                    metrics = metrics_extractor(analyzer)
                else:
                    # Default metrics extraction
                    if hasattr(analyzer, 'get_metrics'):
                        metrics = analyzer.get_metrics()
                    if hasattr(analyzer, 'iteration'):
                        metrics['iterations'] = analyzer.iteration

                # Record execution time
                metrics['execution_time'] = time.time() - start_time

                # Create result
                result = ExperimentResult(
                    variant_name=variant.name,
                    query=query,
                    success=analysis_result.get('success', True),
                    answer=analysis_result.get('answer', ''),
                    confidence=analysis_result.get('confidence', 0.0),
                    metrics=metrics,
                    error=analysis_result.get('error')
                )

                results.append(result)

                print(f"    Completed in {metrics['execution_time']:.2f}s")
                print(f"   Confidence: {result.confidence:.2f}")

            except Exception as e:
                print(f"   L Error: {e}")
                result = ExperimentResult(
                    variant_name=variant.name,
                    query=query,
                    success=False,
                    error=str(e),
                    metrics={'execution_time': time.time() - start_time}
                )
                results.append(result)

        return results

    def compare_results(self, results: List[ExperimentResult]) -> ComparisonResult:
        """
        Compare results from different variants.

        Args:
            results: List of experiment results to compare

        Returns:
            Comparison with winner and metrics
        """
        if not results:
            return ComparisonResult(query="", variants=[])

        query = results[0].query

        # Calculate comparison metrics
        comparison_metrics = {
            'total_variants': len(results),
            'successful_variants': sum(1 for r in results if r.success),
            'average_confidence': sum(r.confidence for r in results) / len(results),
            'average_execution_time': sum(
                r.metrics.get('execution_time', 0) for r in results
            ) / len(results)
        }

        # Determine winner (highest confidence among successful variants)
        successful_results = [r for r in results if r.success]
        winner = None
        if successful_results:
            winner_result = max(successful_results, key=lambda r: r.confidence)
            winner = winner_result.variant_name
            comparison_metrics['winner_confidence'] = winner_result.confidence
            comparison_metrics['winner_execution_time'] = winner_result.metrics.get('execution_time', 0)

        # Add per-variant breakdown
        comparison_metrics['variants'] = {}
        for result in results:
            comparison_metrics['variants'][result.variant_name] = {
                'success': result.success,
                'confidence': result.confidence,
                'execution_time': result.metrics.get('execution_time', 0),
                'tokens': result.metrics.get('tokens', 0),
                'cost_estimate': result.metrics.get('cost', 0)
            }

        comparison = ComparisonResult(
            query=query,
            variants=results,
            winner=winner,
            comparison_metrics=comparison_metrics
        )

        self.experiments.append(comparison)

        return comparison

    def run_batch_experiment(
        self,
        queries: List[str],
        variants: List[ExperimentConfig],
        analyzer_factory: Callable[[Dict[str, Any]], Any],
        metrics_extractor: Optional[Callable[[Any], Dict[str, Any]]] = None
    ) -> List[ComparisonResult]:
        """
        Run multiple queries with all variants.

        Args:
            queries: List of questions to analyze
            variants: List of experiment configurations
            analyzer_factory: Function that creates analyzer from config
            metrics_extractor: Optional function to extract metrics

        Returns:
            List of comparisons, one per query
        """
        comparisons = []

        print(f"\n=, Running batch experiment")
        print(f"   Queries: {len(queries)}")
        print(f"   Variants: {len(variants)}")
        print(f"   Total runs: {len(queries) * len(variants)}")

        for i, query in enumerate(queries, 1):
            print(f"\n{'='*80}")
            print(f"Query {i}/{len(queries)}: {query}")
            print(f"{'='*80}")

            results = self.run_experiment(query, variants, analyzer_factory, metrics_extractor)
            comparison = self.compare_results(results)
            comparisons.append(comparison)

            print(f"\n=Ê Comparison for query {i}:")
            print(f"   Winner: {comparison.winner or 'None'}")
            print(f"   Avg Confidence: {comparison.comparison_metrics['average_confidence']:.2f}")
            print(f"   Avg Time: {comparison.comparison_metrics['average_execution_time']:.2f}s")

        return comparisons

    def save_results(self, filename: str = None):
        """
        Save all experiment results to file.

        Args:
            filename: Optional filename (defaults to timestamp)
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"experiment_results_{timestamp}.json"

        filepath = self.output_dir / filename

        # Convert to serializable format
        data = {
            'total_experiments': len(self.experiments),
            'timestamp': datetime.now().isoformat(),
            'experiments': [
                {
                    'query': exp.query,
                    'winner': exp.winner,
                    'metrics': exp.comparison_metrics,
                    'variants': [
                        {
                            'name': r.variant_name,
                            'success': r.success,
                            'confidence': r.confidence,
                            'answer': r.answer[:500] if r.answer else '',  # Truncate
                            'metrics': r.metrics,
                            'error': r.error
                        }
                        for r in exp.variants
                    ]
                }
                for exp in self.experiments
            ]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n=¾ Saved experiment results to: {filepath}")

        return filepath

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics across all experiments.

        Returns:
            Dictionary with aggregate statistics
        """
        if not self.experiments:
            return {'total_experiments': 0}

        # Count wins per variant
        variant_wins = {}
        for exp in self.experiments:
            if exp.winner:
                variant_wins[exp.winner] = variant_wins.get(exp.winner, 0) + 1

        # Average metrics
        total_confidence = 0
        total_time = 0
        total_variants = 0

        for exp in self.experiments:
            total_confidence += exp.comparison_metrics.get('average_confidence', 0)
            total_time += exp.comparison_metrics.get('average_execution_time', 0)
            total_variants += exp.comparison_metrics.get('total_variants', 0)

        num_experiments = len(self.experiments)

        return {
            'total_experiments': num_experiments,
            'variant_wins': variant_wins,
            'average_confidence': total_confidence / num_experiments if num_experiments > 0 else 0,
            'average_execution_time': total_time / num_experiments if num_experiments > 0 else 0,
            'total_variant_runs': total_variants
        }


class MetricsAggregator:
    """
    Aggregate and analyze metrics from experiments.

    Provides statistical analysis to answer questions like:
    - Does AST help for pattern detection queries?
    - Which embedding model performs best?
    - What's the cost/benefit tradeoff?
    """

    def __init__(self):
        self.metrics_by_variant = {}
        self.metrics_by_query_type = {}

    def add_experiment(self, comparison: ComparisonResult, query_type: str = "general"):
        """
        Add experiment results to aggregator.

        Args:
            comparison: Comparison result from experiment
            query_type: Type of query (e.g., "pattern_detection", "semantic_search")
        """
        # Aggregate by variant
        for result in comparison.variants:
            if result.variant_name not in self.metrics_by_variant:
                self.metrics_by_variant[result.variant_name] = []

            self.metrics_by_variant[result.variant_name].append({
                'query': comparison.query,
                'query_type': query_type,
                'success': result.success,
                'confidence': result.confidence,
                'execution_time': result.metrics.get('execution_time', 0),
                'tokens': result.metrics.get('tokens', 0),
                'cost': result.metrics.get('cost', 0)
            })

        # Aggregate by query type
        if query_type not in self.metrics_by_query_type:
            self.metrics_by_query_type[query_type] = []

        self.metrics_by_query_type[query_type].append(comparison)

    def get_variant_statistics(self, variant_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific variant.

        Args:
            variant_name: Name of the variant

        Returns:
            Dictionary with statistics
        """
        if variant_name not in self.metrics_by_variant:
            return {'error': 'Variant not found'}

        metrics = self.metrics_by_variant[variant_name]

        if not metrics:
            return {'error': 'No metrics available'}

        return {
            'variant_name': variant_name,
            'total_queries': len(metrics),
            'success_rate': sum(1 for m in metrics if m['success']) / len(metrics),
            'average_confidence': sum(m['confidence'] for m in metrics) / len(metrics),
            'average_execution_time': sum(m['execution_time'] for m in metrics) / len(metrics),
            'total_tokens': sum(m.get('tokens', 0) for m in metrics),
            'total_cost': sum(m.get('cost', 0) for m in metrics),
            'cost_per_query': sum(m.get('cost', 0) for m in metrics) / len(metrics)
        }

    def compare_variants(self, variant_a: str, variant_b: str) -> Dict[str, Any]:
        """
        Compare two variants head-to-head.

        Args:
            variant_a: First variant name
            variant_b: Second variant name

        Returns:
            Comparison dictionary
        """
        stats_a = self.get_variant_statistics(variant_a)
        stats_b = self.get_variant_statistics(variant_b)

        if 'error' in stats_a or 'error' in stats_b:
            return {'error': 'One or both variants not found'}

        return {
            'variant_a': variant_a,
            'variant_b': variant_b,
            'confidence_difference': stats_a['average_confidence'] - stats_b['average_confidence'],
            'time_difference': stats_a['average_execution_time'] - stats_b['average_execution_time'],
            'cost_difference': stats_a['total_cost'] - stats_b['total_cost'],
            'success_rate_difference': stats_a['success_rate'] - stats_b['success_rate'],
            'winner_by_confidence': variant_a if stats_a['average_confidence'] > stats_b['average_confidence'] else variant_b,
            'winner_by_speed': variant_a if stats_a['average_execution_time'] < stats_b['average_execution_time'] else variant_b,
            'winner_by_cost': variant_a if stats_a['total_cost'] < stats_b['total_cost'] else variant_b
        }

    def get_query_type_analysis(self, query_type: str) -> Dict[str, Any]:
        """
        Analyze performance for a specific query type.

        Args:
            query_type: Type of query to analyze

        Returns:
            Analysis dictionary
        """
        if query_type not in self.metrics_by_query_type:
            return {'error': 'Query type not found'}

        comparisons = self.metrics_by_query_type[query_type]

        # Find best variant for this query type
        variant_performance = {}
        for comparison in comparisons:
            for result in comparison.variants:
                if result.success:
                    if result.variant_name not in variant_performance:
                        variant_performance[result.variant_name] = []
                    variant_performance[result.variant_name].append(result.confidence)

        # Calculate average confidence per variant
        variant_avg = {
            name: sum(scores) / len(scores)
            for name, scores in variant_performance.items()
        }

        best_variant = max(variant_avg.items(), key=lambda x: x[1])[0] if variant_avg else None

        return {
            'query_type': query_type,
            'total_queries': len(comparisons),
            'best_variant': best_variant,
            'variant_performance': variant_avg,
            'recommendation': f"Use '{best_variant}' for {query_type} queries" if best_variant else "Insufficient data"
        }
