"""
Experiment Integration for Knowledge Base Testing

Wires up ExperimentRunner with the existing architecture to enable easy A/B testing:
- Does AST help/hinder certain types of queries?
- Does pattern detection improve accuracy?
- Which embedding model performs best?
- Does life-of-x tracing add value?
"""

from typing import Dict, Any, List
from pathlib import Path

from cf.experiments.experiment_runner import ExperimentRunner, ExperimentConfig
from cf.agents.supervisor import SupervisorAgent
from cf.knowledge.metrics import get_all_layer_metrics, reset_all_metrics


def create_supervisor_with_config(repo_path: str, config: Dict[str, Any]) -> SupervisorAgent:
    """
    Create a SupervisorAgent with specific configuration.

    Args:
        repo_path: Path to repository
        config: Configuration dictionary

    Returns:
        SupervisorAgent instance
    """
    return SupervisorAgent(repo_path, config)


def analyze_with_supervisor(supervisor: SupervisorAgent, question: str) -> Dict[str, Any]:
    """
    Analyze a question with SupervisorAgent and extract results.

    Args:
        supervisor: SupervisorAgent instance
        question: Question to analyze

    Returns:
        Dictionary with answer, confidence, and metrics
    """
    # Reset metrics before analysis
    reset_all_metrics()

    # Run analysis
    result = supervisor.analyze(question)

    # Collect layer metrics
    layer_metrics = get_all_layer_metrics()

    return {
        'success': result.get('success', False),
        'answer': result.get('answer', ''),
        'confidence': result.get('confidence', 0.0),
        'layer_metrics': layer_metrics,
        'error': result.get('error')
    }


def run_knowledge_layer_experiment(
    repo_path: str,
    question: str,
    base_config: Dict[str, Any],
    variants: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Run experiment comparing different knowledge layer configurations.

    Args:
        repo_path: Path to repository
        question: Question to analyze
        base_config: Base configuration
        variants: List of variant configs (will be merged with base_config)

    Returns:
        List of results with metrics

    Example:
        >>> base_config = load_config('cf/configs/config.yaml')
        >>> variants = [
        ...     {'name': 'with_patterns', 'config': {'knowledge_base': {'patterns': {'enabled': True}}}},
        ...     {'name': 'without_patterns', 'config': {'knowledge_base': {'patterns': {'enabled': False}}}}
        ... ]
        >>> results = run_knowledge_layer_experiment('/path/to/repo', 'Find singletons', base_config, variants)
    """
    results = []

    for variant in variants:
        variant_name = variant['name']
        variant_config = variant['config']

        print(f"\n{'='*80}")
        print(f"Running variant: {variant_name}")
        print(f"{'='*80}")

        # Merge variant config with base config
        config = _merge_configs(base_config, variant_config)

        # Create supervisor with variant config
        supervisor = create_supervisor_with_config(repo_path, config)

        # Analyze
        result = analyze_with_supervisor(supervisor, question)

        # Add variant name
        result['variant_name'] = variant_name
        result['variant_config'] = variant_config

        results.append(result)

        # Print summary
        print(f"\n✅ Variant {variant_name} completed:")
        print(f"   Success: {result['success']}")
        print(f"   Confidence: {result['confidence']:.2f}")

        # Print layer metrics
        if result.get('layer_metrics'):
            print(f"\n   Layer Metrics:")
            for layer_name, metrics in result['layer_metrics'].items():
                print(f"     {layer_name}:")
                print(f"       Calls: {metrics['total_calls']}")
                print(f"       Duration: {metrics['total_duration']:.2f}s")
                print(f"       Tokens: {metrics['total_tokens']}")
                print(f"       Cost: ${metrics['total_cost']:.4f}")

    return results


def compare_embedding_models(
    repo_path: str,
    question: str,
    base_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Compare different embedding models.

    Args:
        repo_path: Path to repository
        question: Question to analyze
        base_config: Base configuration

    Returns:
        Comparison results
    """
    variants = [
        {
            'name': 'local_minilm',
            'config': {
                'knowledge_base': {
                    'semantic': {
                        'enabled': True,
                        'use_local_model': True,
                        'embedding_model': 'all-MiniLM-L6-v2'
                    }
                }
            }
        },
        {
            'name': 'local_mpnet',
            'config': {
                'knowledge_base': {
                    'semantic': {
                        'enabled': True,
                        'use_local_model': True,
                        'embedding_model': 'all-mpnet-base-v2'
                    }
                }
            }
        },
        {
            'name': 'openai_small',
            'config': {
                'knowledge_base': {
                    'semantic': {
                        'enabled': True,
                        'use_local_model': False,
                        'embedding_model': 'text-embedding-3-small'
                    }
                }
            }
        }
    ]

    return run_knowledge_layer_experiment(repo_path, question, base_config, variants)


def test_layer_contribution(
    repo_path: str,
    question: str,
    base_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Test which knowledge layers contribute most to answer quality.

    Runs experiments with each layer disabled to measure impact.

    Args:
        repo_path: Path to repository
        question: Question to analyze
        base_config: Base configuration

    Returns:
        Analysis of layer contributions
    """
    variants = [
        {
            'name': 'all_layers',
            'config': {
                'knowledge_base': {
                    'semantic': {'enabled': True},
                    'patterns': {'enabled': True},
                    'lifeofx': {'enabled': True}
                }
            }
        },
        {
            'name': 'no_semantic',
            'config': {
                'knowledge_base': {
                    'semantic': {'enabled': False},
                    'patterns': {'enabled': True},
                    'lifeofx': {'enabled': True}
                }
            }
        },
        {
            'name': 'no_patterns',
            'config': {
                'knowledge_base': {
                    'semantic': {'enabled': True},
                    'patterns': {'enabled': False},
                    'lifeofx': {'enabled': True}
                }
            }
        },
        {
            'name': 'no_lifeofx',
            'config': {
                'knowledge_base': {
                    'semantic': {'enabled': True},
                    'patterns': {'enabled': True},
                    'lifeofx': {'enabled': False}
                }
            }
        },
        {
            'name': 'structural_only',
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

    # Analyze contributions
    baseline = next((r for r in results if r['variant_name'] == 'all_layers'), None)
    if not baseline:
        return {'error': 'Baseline (all_layers) not found'}

    baseline_confidence = baseline['confidence']

    analysis = {
        'baseline_confidence': baseline_confidence,
        'layer_impacts': {}
    }

    for result in results:
        if result['variant_name'] == 'all_layers':
            continue

        variant_name = result['variant_name']
        confidence_drop = baseline_confidence - result['confidence']

        analysis['layer_impacts'][variant_name] = {
            'confidence': result['confidence'],
            'confidence_drop': confidence_drop,
            'impact_percentage': (confidence_drop / baseline_confidence * 100) if baseline_confidence > 0 else 0,
            'metrics': result.get('layer_metrics', {})
        }

    return analysis


def _merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two configuration dictionaries.

    Args:
        base: Base configuration
        override: Configuration to override

    Returns:
        Merged configuration
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_configs(result[key], value)
        else:
            result[key] = value

    return result
