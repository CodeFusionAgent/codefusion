"""
Analyzer Factory for A/B Testing

Provides factory functions for creating analyzers with different configurations.
Used by ExperimentRunner for variant testing.
"""

from typing import Dict, Any, Callable

from cf.integration.wiring import create_integrated_system
from cf.integration.config_utils import deep_merge


def create_analyzer_factory(repo_path: str, base_config: Dict[str, Any]) -> Callable:
    """
    Create a factory function for analyzers with different configurations.

    This is used by ExperimentRunner to create analyzers with variant configs.
    Each variant can override specific configuration options while preserving
    the base config.

    Args:
        repo_path: Repository path
        base_config: Base configuration

    Returns:
        Factory function that takes variant_config and returns analyzer

    Example:
        >>> factory = create_analyzer_factory("/path/to/repo", base_config)
        >>>
        >>> # Create analyzer with AST enabled
        >>> variant_config = {'knowledge_base': {'patterns': {'enabled': True}}}
        >>> analyzer = factory(variant_config)
        >>>
        >>> # Create analyzer with AST disabled
        >>> variant_config = {'knowledge_base': {'patterns': {'enabled': False}}}
        >>> analyzer = factory(variant_config)
    """
    def factory(variant_config: Dict[str, Any]):
        """
        Create analyzer with merged configuration.

        Args:
            variant_config: Variant-specific configuration overrides

        Returns:
            AnalyzerWrapper with analyze() and get_metrics() methods
        """
        # Deep merge variant config into base config
        merged_config = deep_merge(base_config.copy(), variant_config)

        # Create integrated system with merged config
        system = create_integrated_system(repo_path, merged_config)

        # Return a wrapper that has analyze() method
        class AnalyzerWrapper:
            """Wrapper providing standard analyzer interface"""

            def __init__(self, system):
                self.system = system
                self.tool_registry = system['tool_registry']

            def analyze(self, query: str) -> Dict[str, Any]:
                """
                Analyze query using the configured system.

                Args:
                    query: Query to analyze

                Returns:
                    Analysis results
                """
                # Use a KB tool to analyze the query
                # This ensures we're using tools, not direct pipeline access
                result = self.tool_registry.execute(
                    'structural_kb_search_by_semantics',
                    query=query,
                    limit=50
                )

                if result.get('success'):
                    return {
                        'success': True,
                        'query': query,
                        'results_found': result.get('count', 0),
                        'results': result.get('results', []),
                        'answer': f"Found {result.get('count', 0)} relevant items using this configuration",
                        'confidence': 0.8 if result.get('count', 0) > 0 else 0.3
                    }
                else:
                    return {
                        'success': False,
                        'query': query,
                        'error': result.get('error', 'Unknown error'),
                        'confidence': 0.0
                    }

            def get_metrics(self) -> Dict[str, Any]:
                """
                Get metrics from tool registry.

                Returns:
                    Tool usage metrics
                """
                return self.tool_registry.get_metrics()

        return AnalyzerWrapper(system)

    return factory
