"""
Unified Metrics Collector

Aggregates metrics from all system components:
- Supervisor (multi-pass coordination)
- Orchestrator (pipeline execution)
- Pipelines (discovery, analysis, synthesis, validation)
- Tools (tool calls, LLM calls, KB queries)
- Agents (KB agents, specialist agents)

Provides hierarchical aggregation and export for analysis.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import time


@dataclass
class MetricSnapshot:
    """Single metric snapshot"""
    timestamp: float
    component: str  # supervisor, orchestrator, discovery, analysis, etc.
    metric_type: str  # call, token, duration, error, etc.
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentMetrics:
    """Metrics for a single component"""
    component_name: str
    total_calls: int = 0
    total_tokens: int = 0
    total_duration: float = 0.0
    total_errors: int = 0
    success_rate: float = 0.0
    avg_duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class MetricsCollector:
    """
    Unified metrics collector for CodeFusion.

    Hierarchical structure:
    - System level (entire analysis session)
      - Supervisor level (multi-pass coordination)
        - Orchestrator level (pipeline execution)
          - Pipeline level (discovery, analysis, synthesis, validation)
            - Tool level (individual tool calls)

    Usage:
        >>> collector = MetricsCollector()
        >>> collector.record_call('discovery', duration=1.5, success=True)
        >>> collector.record_tokens('analysis', tokens=1500)
        >>> metrics = collector.get_aggregated_metrics()
    """

    def __init__(self):
        """Initialize collector"""
        self.session_start = time.time()
        self.snapshots: List[MetricSnapshot] = []
        self.component_metrics: Dict[str, ComponentMetrics] = {}

    def record_call(
        self,
        component: str,
        duration: float = 0.0,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record a component call.

        Args:
            component: Component name (supervisor, orchestrator, discovery, etc.)
            duration: Call duration in seconds
            success: Whether call succeeded
            metadata: Additional context
        """
        # Record snapshot
        self.snapshots.append(MetricSnapshot(
            timestamp=time.time(),
            component=component,
            metric_type='call',
            value=1.0,
            metadata=metadata or {}
        ))

        # Update component metrics
        if component not in self.component_metrics:
            self.component_metrics[component] = ComponentMetrics(component_name=component)

        metrics = self.component_metrics[component]
        metrics.total_calls += 1
        metrics.total_duration += duration

        if not success:
            metrics.total_errors += 1

        # Recalculate derived metrics
        self._update_derived_metrics(component)

    def record_tokens(
        self,
        component: str,
        tokens: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record token usage.

        Args:
            component: Component name
            tokens: Number of tokens used
            metadata: Additional context (model, prompt type, etc.)
        """
        self.snapshots.append(MetricSnapshot(
            timestamp=time.time(),
            component=component,
            metric_type='tokens',
            value=float(tokens),
            metadata=metadata or {}
        ))

        if component not in self.component_metrics:
            self.component_metrics[component] = ComponentMetrics(component_name=component)

        self.component_metrics[component].total_tokens += tokens

    def record_error(
        self,
        component: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record an error.

        Args:
            component: Component name
            error_message: Error description
            metadata: Additional context
        """
        self.snapshots.append(MetricSnapshot(
            timestamp=time.time(),
            component=component,
            metric_type='error',
            value=1.0,
            metadata={'error': error_message, **(metadata or {})}
        ))

        if component not in self.component_metrics:
            self.component_metrics[component] = ComponentMetrics(component_name=component)

        self.component_metrics[component].total_errors += 1
        self._update_derived_metrics(component)

    def _update_derived_metrics(self, component: str):
        """Update derived metrics (success_rate, avg_duration)"""
        metrics = self.component_metrics[component]

        if metrics.total_calls > 0:
            metrics.success_rate = (metrics.total_calls - metrics.total_errors) / metrics.total_calls
            metrics.avg_duration = metrics.total_duration / metrics.total_calls

    def get_component_metrics(self, component: str) -> Optional[ComponentMetrics]:
        """
        Get metrics for specific component.

        Args:
            component: Component name

        Returns:
            ComponentMetrics or None if not found
        """
        return self.component_metrics.get(component)

    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics across all components.

        Returns:
            Dictionary with hierarchical metrics
        """
        total_calls = sum(m.total_calls for m in self.component_metrics.values())
        total_tokens = sum(m.total_tokens for m in self.component_metrics.values())
        total_duration = sum(m.total_duration for m in self.component_metrics.values())
        total_errors = sum(m.total_errors for m in self.component_metrics.values())

        return {
            'session_duration': time.time() - self.session_start,
            'total_calls': total_calls,
            'total_tokens': total_tokens,
            'total_duration': total_duration,
            'total_errors': total_errors,
            'overall_success_rate': (total_calls - total_errors) / total_calls if total_calls > 0 else 0.0,
            'components': {
                name: metrics.to_dict()
                for name, metrics in self.component_metrics.items()
            },
            'snapshot_count': len(self.snapshots)
        }

    def get_hierarchical_metrics(self) -> Dict[str, Any]:
        """
        Get metrics organized hierarchically.

        Returns:
            Nested dictionary with hierarchy:
            - supervisor
              - orchestrator
                - discovery
                - analysis
                - synthesis
                - validation
              - tools
                - KB tools
                - LLM tools
        """
        # Group components by hierarchy
        supervisor_components = [c for c in self.component_metrics.keys() if 'supervisor' in c]
        orchestrator_components = [c for c in self.component_metrics.keys() if 'orchestrator' in c]
        pipeline_components = [c for c in self.component_metrics.keys()
                             if any(p in c for p in ['discovery', 'analysis', 'synthesis', 'validation'])]
        tool_components = [c for c in self.component_metrics.keys()
                         if any(t in c for t in ['tool', 'llm', 'kb'])]

        return {
            'supervisor': {
                name: self.component_metrics[name].to_dict()
                for name in supervisor_components
            },
            'orchestrator': {
                name: self.component_metrics[name].to_dict()
                for name in orchestrator_components
            },
            'pipelines': {
                name: self.component_metrics[name].to_dict()
                for name in pipeline_components
            },
            'tools': {
                name: self.component_metrics[name].to_dict()
                for name in tool_components
            }
        }

    def get_timeline(self, component: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get timeline of events.

        Args:
            component: Optional filter by component

        Returns:
            List of events sorted by timestamp
        """
        snapshots = self.snapshots
        if component:
            snapshots = [s for s in snapshots if s.component == component]

        return [
            {
                'timestamp': s.timestamp,
                'relative_time': s.timestamp - self.session_start,
                'component': s.component,
                'metric_type': s.metric_type,
                'value': s.value,
                'metadata': s.metadata
            }
            for s in sorted(snapshots, key=lambda x: x.timestamp)
        ]

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary with insights.

        Returns:
            Dictionary with:
            - Slowest components
            - Most token-intensive components
            - Error-prone components
            - Efficiency metrics
        """
        components = list(self.component_metrics.values())

        # Sort by different metrics
        slowest = sorted(components, key=lambda c: c.total_duration, reverse=True)[:5]
        most_tokens = sorted(components, key=lambda c: c.total_tokens, reverse=True)[:5]
        most_errors = sorted([c for c in components if c.total_errors > 0],
                           key=lambda c: c.total_errors, reverse=True)[:5]

        return {
            'slowest_components': [
                {'component': c.component_name, 'duration': c.total_duration, 'avg': c.avg_duration}
                for c in slowest
            ],
            'most_token_intensive': [
                {'component': c.component_name, 'tokens': c.total_tokens}
                for c in most_tokens
            ],
            'error_prone_components': [
                {'component': c.component_name, 'errors': c.total_errors, 'success_rate': c.success_rate}
                for c in most_errors
            ],
            'efficiency': {
                'tokens_per_second': sum(c.total_tokens for c in components) / (time.time() - self.session_start)
                                    if (time.time() - self.session_start) > 0 else 0,
                'calls_per_second': sum(c.total_calls for c in components) / (time.time() - self.session_start)
                                   if (time.time() - self.session_start) > 0 else 0
            }
        }

    def export_for_analysis(self, format: str = 'json') -> Dict[str, Any]:
        """
        Export all metrics for external analysis.

        Args:
            format: Export format ('json', 'summary', 'timeline')

        Returns:
            Comprehensive metrics export
        """
        if format == 'summary':
            return self.get_performance_summary()
        elif format == 'timeline':
            return {'timeline': self.get_timeline()}
        else:  # json (default)
            return {
                'session_start': self.session_start,
                'session_duration': time.time() - self.session_start,
                'aggregated': self.get_aggregated_metrics(),
                'hierarchical': self.get_hierarchical_metrics(),
                'performance': self.get_performance_summary(),
                'timeline': self.get_timeline()
            }

    def reset(self):
        """Reset all metrics"""
        self.session_start = time.time()
        self.snapshots = []
        self.component_metrics = {}


# Global collector instance
_global_collector = MetricsCollector()


def get_global_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return _global_collector
