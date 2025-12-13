"""
Metrics module for CodeFusion.

Provides unified metrics collection across all system components.
"""

from cf.metrics.collector import MetricsCollector, get_global_collector, ComponentMetrics, MetricSnapshot

__all__ = [
    'MetricsCollector',
    'get_global_collector',
    'ComponentMetrics',
    'MetricSnapshot',
]
