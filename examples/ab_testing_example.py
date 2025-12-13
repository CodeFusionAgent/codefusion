"""
A/B Testing Examples for CodeFusion

Demonstrates how to use the experiment framework to answer questions like:
- "Does AST-based pattern detection help or hinder certain queries?"
- "Which embedding model performs best for semantic search?"
- "What's the cost/performance tradeoff between strategies?"
"""

import yaml
from pathlib import Path

from cf.integration.setup import setup_for_experiments, create_analyzer_factory
from cf.experiments.experiment_runner import ExperimentConfig


def example_1_ast_vs_keywords():
    """
    Example 1: Compare AST-based analysis vs keyword-based search

    Question: Does AST parsing help or hinder pattern detection queries?
    """
    print("\n" + "="*80)
    print("Example 1: AST-Based vs Keyword-Based Pattern Detection")
    print("="*80)

    # Load config
    config_path = Path(__file__).parent.parent / "cf" / "configs" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Setup experiment system
    repo_path = "/path/to/your/repo"  # Change this
    exp_system = setup_for_experiments(repo_path, config)

    runner = exp_system['experiment_runner']
    aggregator = exp_system['metrics_aggregator']
    factory = create_analyzer_factory(repo_path, config)

    # Define variants
    variant_with_ast = ExperimentConfig(
        name="with_ast_patterns",
        description="Uses AST-based pattern detection from KB",
        config={
            'knowledge_base': {
                'patterns': {'enabled': True, 'detect_design_patterns': True}
            }
        }
    )

    variant_without_ast = ExperimentConfig(
        name="keyword_only",
        description="Uses only keyword matching (patterns disabled)",
        config={
            'knowledge_base': {
                'patterns': {'enabled': False}
            }
        }
    )

    # Define test queries
    pattern_queries = [
        "Find all singleton patterns in the codebase",
        "Where are factory patterns used?",
        "Identify observer pattern implementations",
        "Find decorator patterns",
        "Show me all strategy pattern usages"
    ]

    # Run experiment
    print("\n=, Running experiment with 5 queries across 2 variants...\n")

    results = runner.run_batch_experiment(
        queries=pattern_queries,
        variants=[variant_with_ast, variant_without_ast],
        analyzer_factory=factory
    )

    # Analyze results
    for comparison in results:
        aggregator.add_experiment(comparison, query_type="pattern_detection")

    # Get statistics
    print("\n== Variant Statistics:")
    print("-" * 80)

    with_ast_stats = aggregator.get_variant_statistics("with_ast_patterns")
    without_ast_stats = aggregator.get_variant_statistics("keyword_only")

    print(f"\nWith AST Patterns:")
    print(f"  Success Rate: {with_ast_stats['success_rate']:.1%}")
    print(f"  Avg Confidence: {with_ast_stats['average_confidence']:.2f}")
    print(f"  Avg Execution Time: {with_ast_stats['average_execution_time']:.2f}s")
    print(f"  Total Cost: ${with_ast_stats['total_cost']:.4f}")

    print(f"\nKeyword Only:")
    print(f"  Success Rate: {without_ast_stats['success_rate']:.1%}")
    print(f"  Avg Confidence: {without_ast_stats['average_confidence']:.2f}")
    print(f"  Avg Execution Time: {without_ast_stats['average_execution_time']:.2f}s")
    print(f"  Total Cost: ${without_ast_stats['total_cost']:.4f}")

    # Head-to-head comparison
    comparison = aggregator.compare_variants("with_ast_patterns", "keyword_only")

    print("\n<= Head-to-Head Comparison:")
    print("-" * 80)
    print(f"Winner by Confidence: {comparison['winner_by_confidence']}")
    print(f"Winner by Speed: {comparison['winner_by_speed']}")
    print(f"Winner by Cost: {comparison['winner_by_cost']}")
    print(f"\nConfidence Difference: {comparison['confidence_difference']:+.2f}")
    print(f"Time Difference: {comparison['time_difference']:+.2f}s")
    print(f"Cost Difference: ${comparison['cost_difference']:+.4f}")

    # Save results
    results_file = runner.save_results("ast_vs_keywords_experiment.json")
    print(f"\n== Results saved to: {results_file}")

    print("\n Conclusion:")
    if comparison['confidence_difference'] > 0.1:
        print("   AST-based pattern detection significantly improves accuracy")
    elif comparison['confidence_difference'] < -0.1:
        print("   Keyword-based search performs better (AST may be overkill)")
    else:
        print("   Both approaches perform similarly for pattern detection")


def example_2_embedding_models():
    """
    Example 2: Compare different embedding models for semantic search

    Question: Which embedding model performs best?
    """
    print("\n" + "="*80)
    print("Example 2: Compare Embedding Models")
    print("="*80)

    config_path = Path(__file__).parent.parent / "cf" / "configs" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    repo_path = "/path/to/your/repo"
    exp_system = setup_for_experiments(repo_path, config)

    runner = exp_system['experiment_runner']
    aggregator = exp_system['metrics_aggregator']
    factory = create_analyzer_factory(repo_path, config)

    # Define variants with different embedding models
    variant_openai_small = ExperimentConfig(
        name="openai_small",
        description="OpenAI text-embedding-3-small",
        config={
            'knowledge_base': {
                'semantic': {
                    'enabled': True,
                    'embedding_model': 'text-embedding-3-small',
                    'use_local_model': False
                }
            }
        }
    )

    variant_local_minilm = ExperimentConfig(
        name="local_minilm",
        description="Local all-MiniLM-L6-v2 (free)",
        config={
            'knowledge_base': {
                'semantic': {
                    'enabled': True,
                    'embedding_model': 'all-MiniLM-L6-v2',
                    'use_local_model': True
                }
            }
        }
    )

    # Semantic search queries
    semantic_queries = [
        "Find code that validates user input",
        "Where is authentication handled?",
        "Show me database connection logic",
        "Find error handling code",
        "Locate API rate limiting implementation"
    ]

    print("\n=, Running experiment...")

    results = runner.run_batch_experiment(
        queries=semantic_queries,
        variants=[variant_openai_small, variant_local_minilm],
        analyzer_factory=factory
    )

    for comparison in results:
        aggregator.add_experiment(comparison, query_type="semantic_search")

    # Analyze by query type
    analysis = aggregator.get_query_type_analysis("semantic_search")

    print("\n== Query Type Analysis:")
    print("-" * 80)
    print(f"Best variant for semantic search: {analysis['best_variant']}")
    print(f"Recommendation: {analysis['recommendation']}")

    runner.save_results("embedding_comparison.json")


def example_3_cost_benefit_analysis():
    """
    Example 3: Cost-Benefit Analysis of Different Configurations

    Question: What's the best cost/performance tradeoff?
    """
    print("\n" + "="*80)
    print("Example 3: Cost-Benefit Analysis")
    print("="*80)

    config_path = Path(__file__).parent.parent / "cf" / "configs" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    repo_path = "/path/to/your/repo"
    exp_system = setup_for_experiments(repo_path, config)

    runner = exp_system['experiment_runner']
    factory = create_analyzer_factory(repo_path, config)

    # Define variants with different feature combinations
    variant_full = ExperimentConfig(
        name="full_features",
        description="All KB layers enabled",
        config={
            'knowledge_base': {
                'semantic': {'enabled': True},
                'patterns': {'enabled': True},
                'lifeofx': {'enabled': True}
            }
        }
    )

    variant_minimal = ExperimentConfig(
        name="minimal",
        description="Only structural layer (cheapest)",
        config={
            'knowledge_base': {
                'semantic': {'enabled': False},
                'patterns': {'enabled': False},
                'lifeofx': {'enabled': False}
            }
        }
    )

    variant_balanced = ExperimentConfig(
        name="balanced",
        description="Structural + Semantic only",
        config={
            'knowledge_base': {
                'semantic': {'enabled': True},
                'patterns': {'enabled': False},
                'lifeofx': {'enabled': False}
            }
        }
    )

    # Mixed queries (different types)
    mixed_queries = [
        "How does the authentication system work?",
        "Find all singleton patterns",
        "Where is the database configured?",
        "Show me the data flow for user registration",
        "What architectural patterns are used?"
    ]

    print("\n=, Running cost-benefit experiment...")

    results = runner.run_batch_experiment(
        queries=mixed_queries,
        variants=[variant_full, variant_minimal, variant_balanced],
        analyzer_factory=factory
    )

    # Print cost summary
    print("\n== Cost Summary:")
    print("-" * 80)

    summary = runner.get_summary()
    print(f"Total experiments: {summary['total_experiments']}")
    print(f"Average execution time: {summary['average_execution_time']:.2f}s")

    print(f"\nVariant wins:")
    for variant, wins in summary['variant_wins'].items():
        print(f"  {variant}: {wins} wins")

    runner.save_results("cost_benefit_analysis.json")


def example_4_custom_metrics():
    """
    Example 4: Custom Metrics and Advanced Analysis

    Shows how to track custom metrics beyond the defaults
    """
    print("\n" + "="*80)
    print("Example 4: Custom Metrics")
    print("="*80)

    from cf.experiments.experiment_runner import ExperimentRunner

    runner = ExperimentRunner()

    # Custom metrics extractor
    def extract_custom_metrics(analyzer):
        """Extract custom metrics from analyzer"""
        base_metrics = analyzer.get_metrics()

        # Add custom metrics
        summary = base_metrics.get('summary', {})

        return {
            **base_metrics,
            'custom_metrics': {
                'tools_used': summary.get('unique_tools_used', 0),
                'most_expensive_tool': summary.get('most_expensive_tools', [[None, 0]])[0][0],
                'kb_queries': sum(
                    1 for tool in summary.get('most_used_tools', [])
                    if 'kb' in tool[0] or 'semantic' in tool[0]
                )
            }
        }

    print("\n Custom metrics can be extracted for detailed analysis")
    print("   - Tools used per query")
    print("   - Most expensive tool")
    print("   - KB query count")


if __name__ == "__main__":
    """
    Run all examples.

    NOTE: Update repo_path in each example before running!
    """
    print("\n" + "="*80)
    print("CodeFusion A/B Testing Examples")
    print("="*80)
    print("\nThese examples demonstrate how to:")
    print("1. Compare AST-based vs keyword-based analysis")
    print("2. Compare different embedding models")
    print("3. Analyze cost/performance tradeoffs")
    print("4. Use custom metrics")

    print("\n=  NOTE: Update repo_path in each example before running!")
    print("="*80)

    # Uncomment to run examples:
    # example_1_ast_vs_keywords()
    # example_2_embedding_models()
    # example_3_cost_benefit_analysis()
    # example_4_custom_metrics()
