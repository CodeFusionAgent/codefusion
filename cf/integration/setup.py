"""
Integration Setup Module

Main entry point for setting up integrated CodeFusion systems.
Provides convenience functions that import from specialized modules.

Updated to enforce tool-first design:
- No direct pipeline access exposed
- All KB operations through tools
- Clean separation of concerns
"""

import yaml
from typing import Dict, Any, Optional
from pathlib import Path

from cf.integration.wiring import create_integrated_system
from cf.integration.factory import create_analyzer_factory
from cf.integration.config_utils import deep_merge


def setup_for_experiments(
    repo_path: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Set up system specifically for A/B testing experiments.

    Creates multiple configurations with different agent combinations
    to enable comparative analysis.

    Args:
        repo_path: Path to repository
        config: Base configuration

    Returns:
        Dictionary with experiment-ready components:
        - All components from create_integrated_system()
        - 'experiment_runner': ExperimentRunner instance
        - 'metrics_aggregator': MetricsAggregator instance

    Example:
        >>> exp_system = setup_for_experiments("/path/to/repo", config)
        >>> runner = exp_system['experiment_runner']
        >>>
        >>> # Define variants
        >>> variant_a = ExperimentConfig(
        ...     name="with_ast",
        ...     config={'knowledge_base': {'patterns': {'enabled': True}}}
        ... )
        >>> variant_b = ExperimentConfig(
        ...     name="without_ast",
        ...     config={'knowledge_base': {'patterns': {'enabled': False}}}
        ... )
        >>>
        >>> # Run experiment
        >>> factory = create_analyzer_factory(repo_path, config)
        >>> results = runner.run_experiment(
        ...     query="Find all singleton patterns",
        ...     variants=[variant_a, variant_b],
        ...     analyzer_factory=factory
        ... )
    """
    from cf.experiments.experiment_runner import ExperimentRunner, MetricsAggregator

    # Create base system
    system = create_integrated_system(repo_path, config)

    # Create experiment runner
    experiment_runner = ExperimentRunner(output_dir="cf_experiments")

    # Create metrics aggregator
    metrics_aggregator = MetricsAggregator()

    return {
        **system,
        'experiment_runner': experiment_runner,
        'metrics_aggregator': metrics_aggregator
    }


def quick_setup(repo_path: str, config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick setup with sensible defaults.

    Loads configuration and creates integrated system in one call.

    Args:
        repo_path: Path to repository
        config_path: Optional path to config file (defaults to cf/configs/config.yaml)

    Returns:
        Integrated system dictionary (see create_integrated_system)

    Example:
        >>> system = quick_setup("/path/to/my/repo")
        >>> tools = system['tool_registry']
        >>> result = tools.execute('structural_kb_search_by_semantics',
        ...                         query="find authentication code")
    """
    # Load config
    if config_path is None:
        config_path = Path(__file__).parent.parent / "configs" / "config.yaml"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Create integrated system
    return create_integrated_system(repo_path, config)


# Re-export for backward compatibility
__all__ = [
    'create_integrated_system',
    'setup_for_experiments',
    'create_analyzer_factory',
    'quick_setup',
    'deep_merge'
]
