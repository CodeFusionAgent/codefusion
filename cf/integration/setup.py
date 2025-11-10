"""
Integration Setup Module

Wires together all pluggable components:
- AgentRegistry
- ToolRegistry
- StructuralKBAgent
- Experiment framework

This module provides the integration layer between the new pluggable architecture
and the existing StructuralPipeline.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from cf.agents.kb_agents import AgentRegistry, get_global_registry
from cf.agents.structural_kb_agent import StructuralKBAgent
from cf.agents.pipelines.structural import StructuralPipeline
from cf.tools.registry import ToolRegistry
from cf.trace.tracer import Tracer
from cf.trace.langfuse_plugin import LangfusePlugin
from cf.llm.task import LlmTask
from cf.llm.client import LLMClient


def create_integrated_system(
    repo_path: str,
    config: Dict[str, Any],
    enable_langfuse: bool = False,
    langfuse_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a fully integrated CodeFusion system with all pluggable components.

    Args:
        repo_path: Path to repository root
        config: Configuration dictionary
        enable_langfuse: Whether to enable Langfuse tracing
        langfuse_config: Langfuse configuration (public_key, secret_key, host)

    Returns:
        Dictionary with all system components

    Example:
        >>> system = create_integrated_system(
        ...     repo_path="/path/to/repo",
        ...     config=load_config(),
        ...     enable_langfuse=True,
        ...     langfuse_config={
        ...         'public_key': 'pk-...',
        ...         'secret_key': 'sk-...'
        ...     }
        ... )
        >>> tools = system['tool_registry']
        >>> pipeline = system['pipeline']
        >>> agent_registry = system['agent_registry']
    """
    # 1. Create Agent Registry
    agent_registry = get_global_registry()

    # 2. Create ToolRegistry with agent registry support
    tool_registry = ToolRegistry(repo_path, agent_registry=agent_registry)

    # 3. Create StructuralPipeline (KB backend)
    pipeline = StructuralPipeline(repo_path, config)

    # 4. Create and register StructuralKBAgent (exposes all KB query tools)
    kb_agent = StructuralKBAgent(pipeline, config.get('knowledge_base', {}))
    agent_registry.register(kb_agent)

    # Initialize the KB agent
    kb_agent.initialize()

    # 5. Set up Tracer with optional Langfuse plugin
    tracer_plugins = []
    if enable_langfuse and langfuse_config:
        langfuse_plugin = LangfusePlugin(
            public_key=langfuse_config.get('public_key'),
            secret_key=langfuse_config.get('secret_key'),
            host=langfuse_config.get('host', 'https://cloud.langfuse.com'),
            enabled=True
        )
        tracer_plugins.append(langfuse_plugin)

    tracer = Tracer(
        agent_name="integrated_system",
        trace_config=config.get('trace', {}),
        plugins=tracer_plugins
    )

    # 6. Create LLM client and task interface
    llm_client = LLMClient(config.get('llm', {}))
    llm_task = LlmTask(llm_client, max_history=10)

    return {
        'agent_registry': agent_registry,
        'tool_registry': tool_registry,
        'pipeline': pipeline,
        'kb_agent': kb_agent,
        'tracer': tracer,
        'llm_client': llm_client,
        'llm_task': llm_task,
        'config': config
    }


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
        Dictionary with experiment-ready components

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
        >>> results = runner.run_experiment(
        ...     query="Find all singleton patterns",
        ...     variants=[variant_a, variant_b],
        ...     analyzer_factory=create_analyzer
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


def create_analyzer_factory(repo_path: str, base_config: Dict[str, Any]):
    """
    Create a factory function for analyzers with different configurations.

    This is used by ExperimentRunner to create analyzers with variant configs.

    Args:
        repo_path: Repository path
        base_config: Base configuration

    Returns:
        Factory function

    Example:
        >>> factory = create_analyzer_factory("/path/to/repo", config)
        >>>
        >>> # Create analyzer with variant config
        >>> variant_config = {'knowledge_base': {'patterns': {'enabled': False}}}
        >>> analyzer = factory(variant_config)
    """
    def factory(variant_config: Dict[str, Any]):
        """Create analyzer with merged configuration"""
        # Deep merge variant config into base config
        merged_config = _deep_merge(base_config.copy(), variant_config)

        # Create integrated system with merged config
        system = create_integrated_system(repo_path, merged_config)

        # Return a wrapper that has analyze() method
        class AnalyzerWrapper:
            def __init__(self, system):
                self.system = system
                self.pipeline = system['pipeline']
                self.tool_registry = system['tool_registry']

            def analyze(self, query: str) -> Dict[str, Any]:
                """Analyze query using the configured pipeline"""
                # Use pipeline's find_files_for_question as the analysis method
                files = self.pipeline.find_files_for_question(query, max_results=50)

                return {
                    'success': True,
                    'query': query,
                    'files_found': len(files),
                    'files': files,
                    'answer': f"Found {len(files)} relevant files using this configuration",
                    'confidence': 0.8 if files else 0.3
                }

            def get_metrics(self) -> Dict[str, Any]:
                """Get metrics from tool registry"""
                return self.tool_registry.get_metrics()

        return AnalyzerWrapper(system)

    return factory


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries"""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


# Convenience function for quick setup
def quick_setup(repo_path: str, config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick setup with sensible defaults.

    Args:
        repo_path: Path to repository
        config_path: Optional path to config file (defaults to cf/configs/config.yaml)

    Returns:
        Integrated system dictionary

    Example:
        >>> system = quick_setup("/path/to/my/repo")
        >>> tools = system['tool_registry']
        >>> result = tools.execute('search_by_semantics', query="find authentication code")
    """
    import yaml
    from pathlib import Path

    # Load config
    if config_path is None:
        config_path = Path(__file__).parent.parent / "configs" / "config.yaml"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Create integrated system
    return create_integrated_system(repo_path, config)
