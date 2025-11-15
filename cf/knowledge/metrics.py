"""
Knowledge Layer Metrics Collection

Provides metrics tracking for knowledge base components to enable:
- Cost attribution per layer
- Performance analysis
- A/B testing comparisons
"""

import time
from typing import Dict, Any
from dataclasses import dataclass, field


@dataclass
class LayerMetrics:
    """Metrics for a single knowledge layer"""
    layer_name: str
    total_calls: int = 0
    total_tokens: int = 0
    total_duration: float = 0.0
    total_cost: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'layer_name': self.layer_name,
            'total_calls': self.total_calls,
            'total_tokens': self.total_tokens,
            'total_duration': self.total_duration,
            'total_cost': self.total_cost,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'errors': self.errors,
            'avg_duration': self.total_duration / self.total_calls if self.total_calls > 0 else 0,
            'cache_hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0
        }


class KnowledgeLayerMetrics:
    """
    Base class for knowledge layers that need metrics tracking.

    Usage:
        class MyLayer(KnowledgeLayerMetrics):
            def __init__(self):
                super().__init__('my_layer')

            def process(self, data):
                with self.track_operation(tokens=len(data)):
                    result = self._do_work(data)
                    return result
    """

    def __init__(self, layer_name: str):
        """
        Initialize metrics tracking.

        Args:
            layer_name: Name of the layer (e.g., 'semantic', 'patterns', 'lifeofx')
        """
        self.metrics = LayerMetrics(layer_name=layer_name)

    def track_operation(self, tokens: int = 0, cost: float = 0.0):
        """
        Context manager for tracking an operation.

        Args:
            tokens: Number of tokens used
            cost: Cost in dollars

        Usage:
            with self.track_operation(tokens=100, cost=0.001):
                result = expensive_operation()
        """
        return _OperationTracker(self.metrics, tokens, cost)

    def record_cache_hit(self):
        """Record a cache hit"""
        self.metrics.cache_hits += 1

    def record_cache_miss(self):
        """Record a cache miss"""
        self.metrics.cache_misses += 1

    def record_error(self):
        """Record an error"""
        self.metrics.errors += 1

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for this layer.

        Returns:
            Dictionary with metrics data
        """
        return self.metrics.to_dict()

    def reset_metrics(self):
        """Reset all metrics to zero"""
        self.metrics = LayerMetrics(layer_name=self.metrics.layer_name)


class _OperationTracker:
    """Context manager for tracking individual operations"""

    def __init__(self, metrics: LayerMetrics, tokens: int, cost: float):
        self.metrics = metrics
        self.tokens = tokens
        self.cost = cost
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        # Update metrics
        self.metrics.total_calls += 1
        self.metrics.total_tokens += self.tokens
        self.metrics.total_duration += duration
        self.metrics.total_cost += self.cost

        # Don't suppress exceptions
        return False


# Global registry for all layer metrics
_metrics_registry: Dict[str, KnowledgeLayerMetrics] = {}


def register_layer_metrics(layer: KnowledgeLayerMetrics):
    """
    Register a layer for global metrics tracking.

    Args:
        layer: Layer instance with metrics
    """
    _metrics_registry[layer.metrics.layer_name] = layer


def get_all_layer_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Get metrics from all registered layers.

    Returns:
        Dictionary mapping layer names to their metrics
    """
    return {
        name: layer.get_metrics()
        for name, layer in _metrics_registry.items()
    }


def reset_all_metrics():
    """Reset metrics for all registered layers"""
    for layer in _metrics_registry.values():
        layer.reset_metrics()
