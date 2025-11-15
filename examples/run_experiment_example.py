"""
Example: Running Knowledge Base Experiments

Shows how to use the experiment framework to answer questions like:
- Does pattern detection help?
- Which embedding model is best?
- What's the cost/accuracy tradeoff?
"""

import sys
import yaml
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cf.experiments.integration import (
    test_layer_contribution,
    compare_embedding_models,
    run_knowledge_layer_experiment
)


def load_config() -> dict:
    """Load base configuration"""
    config_path = Path(__file__).parent.parent / 'cf' / 'configs' / 'config.yaml'
    with open(config_path) as f:
        return yaml.safe_load(f)


def example_1_does_pattern_detection_help():
    """
    Example 1: Does pattern detection help for pattern-related questions?
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Does Pattern Detection Help?")
    print("="*80)

    # Setup
    repo_path = "/path/to/your/repo"  # Change this
    question = "Find all singleton patterns in the codebase"
    base_config = load_config()

    # Define variants
    variants = [
        {
            'name': 'with_patterns',
            'config': {
                'knowledge_base': {
                    'patterns': {'enabled': True}
                }
            }
        },
        {
            'name': 'without_patterns',
            'config': {
                'knowledge_base': {
                    'patterns': {'enabled': False}
                }
            }
        }
    ]

    # Run experiment
    results = run_knowledge_layer_experiment(
        repo_path=repo_path,
        question=question,
        base_config=base_config,
        variants=variants
    )

    # Analyze results
    print("\n📊 Results:")
    for result in results:
        print(f"\n{result['variant_name']}:")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  Success: {result['success']}")

        # Cost analysis
        metrics = result.get('layer_metrics', {})
        total_cost = sum(m['total_cost'] for m in metrics.values())
        print(f"  Total Cost: ${total_cost:.4f}")

    # Conclusion
    with_patterns = next(r for r in results if r['variant_name'] == 'with_patterns')
    without_patterns = next(r for r in results if r['variant_name'] == 'without_patterns')

    confidence_diff = with_patterns['confidence'] - without_patterns['confidence']

    print(f"\n💡 Conclusion:")
    if confidence_diff > 0.1:
        print(f"   Pattern detection HELPS (+{confidence_diff:.2f} confidence)")
    elif confidence_diff < -0.1:
        print(f"   Pattern detection HURTS ({confidence_diff:.2f} confidence)")
    else:
        print(f"   Pattern detection has MINIMAL IMPACT ({confidence_diff:.2f} confidence)")


def example_2_compare_embedding_models():
    """
    Example 2: Which embedding model performs best?
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Compare Embedding Models")
    print("="*80)

    repo_path = "/path/to/your/repo"  # Change this
    question = "Find code similar to user authentication flow"
    base_config = load_config()

    # Run comparison
    results = compare_embedding_models(repo_path, question, base_config)

    # Analyze results
    print("\n📊 Embedding Model Comparison:")
    for result in results:
        print(f"\n{result['variant_name']}:")
        print(f"  Confidence: {result['confidence']:.2f}")

        # Get semantic layer metrics
        metrics = result.get('layer_metrics', {}).get('semantic_embeddings', {})
        if metrics:
            print(f"  Duration: {metrics['total_duration']:.2f}s")
            print(f"  Cost: ${metrics['total_cost']:.4f}")

    # Find best
    best = max(results, key=lambda r: r['confidence'])
    print(f"\n🏆 Best Model: {best['variant_name']}")
    print(f"   Confidence: {best['confidence']:.2f}")


def example_3_layer_contribution_analysis():
    """
    Example 3: Which layers contribute most to answer quality?
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Layer Contribution Analysis")
    print("="*80)

    repo_path = "/path/to/your/repo"  # Change this
    question = "How does user authentication work?"
    base_config = load_config()

    # Analyze layer contributions
    analysis = test_layer_contribution(repo_path, question, base_config)

    if 'error' in analysis:
        print(f"Error: {analysis['error']}")
        return

    print(f"\nBaseline (all layers): {analysis['baseline_confidence']:.2f} confidence")

    print("\n📊 Layer Impact Analysis:")
    for layer, data in analysis['layer_impacts'].items():
        print(f"\n{layer}:")
        print(f"  Confidence: {data['confidence']:.2f}")
        print(f"  Drop: {data['confidence_drop']:.2f} ({data['impact_percentage']:.1f}%)")

        if data['impact_percentage'] > 20:
            print(f"  ⚠️ HIGH IMPACT - This layer is critical!")
        elif data['impact_percentage'] > 10:
            print(f"  📌 MODERATE IMPACT - This layer helps")
        else:
            print(f"  ℹ️ LOW IMPACT - Layer has minimal effect")


def example_4_cost_vs_accuracy_tradeoff():
    """
    Example 4: Analyze cost vs accuracy tradeoff
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Cost vs Accuracy Tradeoff")
    print("="*80)

    repo_path = "/path/to/your/repo"  # Change this
    question = "Explain the request handling architecture"
    base_config = load_config()

    # Test different configurations
    variants = [
        {
            'name': 'full_features',
            'config': {
                'knowledge_base': {
                    'semantic': {'enabled': True, 'use_local_model': False},
                    'patterns': {'enabled': True},
                    'lifeofx': {'enabled': True}
                }
            }
        },
        {
            'name': 'cost_optimized',
            'config': {
                'knowledge_base': {
                    'semantic': {'enabled': True, 'use_local_model': True},  # Free local model
                    'patterns': {'enabled': True},
                    'lifeofx': {'enabled': True}
                }
            }
        },
        {
            'name': 'minimal',
            'config': {
                'knowledge_base': {
                    'semantic': {'enabled': False},
                    'patterns': {'enabled': False},
                    'lifeofx': {'enabled': False}
                }
            }
        }
    ]

    results = run_knowledge_layer_experiment(repo_path, question, base_config, variants)

    # Analyze cost vs accuracy
    print("\n📊 Cost vs Accuracy:")
    for result in results:
        metrics = result.get('layer_metrics', {})
        total_cost = sum(m['total_cost'] for m in metrics.values())

        print(f"\n{result['variant_name']}:")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  Total Cost: ${total_cost:.4f}")
        print(f"  Cost/Confidence: ${total_cost/result['confidence']:.4f}" if result['confidence'] > 0 else "  N/A")


if __name__ == '__main__':
    print("CodeFusion Knowledge Base Experiments")
    print("=" * 80)

    # Run examples (uncomment to run)

    # Example 1: Pattern detection value
    # example_1_does_pattern_detection_help()

    # Example 2: Embedding model comparison
    # example_2_compare_embedding_models()

    # Example 3: Layer contribution analysis
    # example_3_layer_contribution_analysis()

    # Example 4: Cost vs accuracy tradeoff
    # example_4_cost_vs_accuracy_tradeoff()

    print("\n✅ Examples completed!")
    print("\nTo run examples, uncomment the example calls in __main__")
    print("and update repo_path to point to your repository.")
