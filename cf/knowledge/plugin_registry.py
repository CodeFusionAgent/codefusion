"""
Plugin Registry for Knowledge Layers

Enables registering custom implementations of knowledge layers:
- Custom embedding models
- Custom pattern detectors
- Custom analysis strategies

This allows experimentation without modifying core code.
"""

from typing import Dict, Any, Type, Callable, Optional
from enum import Enum


class LayerType(Enum):
    """Types of knowledge layers that can be plugged in"""
    SEMANTIC = "semantic"  # Embedding and similarity search
    PATTERNS = "patterns"  # Pattern detection
    LIFEOFX = "lifeofx"  # Execution tracing
    DATAFLOW = "dataflow"  # Data flow analysis


class KnowledgeLayerRegistry:
    """
    Registry for pluggable knowledge layer implementations.

    Allows registering custom implementations that will be used instead of defaults.

    Example usage:
        >>> # Register custom embedder
        >>> registry = KnowledgeLayerRegistry()
        >>> registry.register(LayerType.SEMANTIC, 'custom_embedder', MyCustomEmbedder)
        >>>
        >>> # Use in StructuralPipeline
        >>> pipeline = StructuralPipeline(repo_path, config, layer_registry=registry)
        >>> embedder = registry.create(LayerType.SEMANTIC, 'custom_embedder', config)
    """

    def __init__(self):
        """Initialize empty registry"""
        self._registry: Dict[LayerType, Dict[str, Type]] = {
            LayerType.SEMANTIC: {},
            LayerType.PATTERNS: {},
            LayerType.LIFEOFX: {},
            LayerType.DATAFLOW: {}
        }
        self._factories: Dict[LayerType, Dict[str, Callable]] = {
            LayerType.SEMANTIC: {},
            LayerType.PATTERNS: {},
            LayerType.LIFEOFX: {},
            LayerType.DATAFLOW: {}
        }

    def register_class(
        self,
        layer_type: LayerType,
        name: str,
        implementation: Type
    ) -> bool:
        """
        Register a class implementation for a layer type.

        Args:
            layer_type: Type of layer (semantic, patterns, etc.)
            name: Name for this implementation
            implementation: Class to instantiate

        Returns:
            True if registered, False if name already exists

        Example:
            >>> class MyEmbedder(CodeEmbedder):
            ...     def embed(self, text):
            ...         # Custom embedding logic
            ...         pass
            >>>
            >>> registry.register_class(LayerType.SEMANTIC, 'my_embedder', MyEmbedder)
        """
        if name in self._registry[layer_type]:
            print(f"⚠️ {layer_type.value}/{name} already registered")
            return False

        self._registry[layer_type][name] = implementation
        print(f"✅ Registered {layer_type.value}/{name}")
        return True

    def register_factory(
        self,
        layer_type: LayerType,
        name: str,
        factory: Callable
    ) -> bool:
        """
        Register a factory function for a layer type.

        Args:
            layer_type: Type of layer
            name: Name for this implementation
            factory: Callable that creates instance

        Returns:
            True if registered, False if name already exists

        Example:
            >>> def create_custom_embedder(config):
            ...     return CustomEmbedder(config['model'], config['api_key'])
            >>>
            >>> registry.register_factory(LayerType.SEMANTIC, 'custom', create_custom_embedder)
        """
        if name in self._factories[layer_type]:
            print(f"⚠️ {layer_type.value}/{name} factory already registered")
            return False

        self._factories[layer_type][name] = factory
        print(f"✅ Registered {layer_type.value}/{name} factory")
        return True

    def create(
        self,
        layer_type: LayerType,
        name: str,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        Create an instance using registered implementation.

        Args:
            layer_type: Type of layer
            name: Name of implementation to use
            *args, **kwargs: Arguments to pass to constructor/factory

        Returns:
            Instance or None if not found

        Example:
            >>> embedder = registry.create(LayerType.SEMANTIC, 'my_embedder', config=config)
        """
        # Try factory first
        if name in self._factories[layer_type]:
            factory = self._factories[layer_type][name]
            return factory(*args, **kwargs)

        # Try class
        if name in self._registry[layer_type]:
            implementation = self._registry[layer_type][name]
            return implementation(*args, **kwargs)

        print(f"⚠️ {layer_type.value}/{name} not found in registry")
        return None

    def has_implementation(self, layer_type: LayerType, name: str) -> bool:
        """
        Check if an implementation is registered.

        Args:
            layer_type: Type of layer
            name: Name of implementation

        Returns:
            True if registered
        """
        return (name in self._registry[layer_type] or
                name in self._factories[layer_type])

    def list_implementations(self, layer_type: LayerType) -> list[str]:
        """
        List all registered implementations for a layer type.

        Args:
            layer_type: Type of layer

        Returns:
            List of implementation names
        """
        classes = list(self._registry[layer_type].keys())
        factories = list(self._factories[layer_type].keys())
        return sorted(set(classes + factories))

    def get_default(self, layer_type: LayerType) -> Optional[str]:
        """
        Get default implementation name for a layer type.

        Returns first registered implementation or None.

        Args:
            layer_type: Type of layer

        Returns:
            Default implementation name or None
        """
        implementations = self.list_implementations(layer_type)
        return implementations[0] if implementations else None


# Global registry instance
_global_registry = KnowledgeLayerRegistry()


def get_global_registry() -> KnowledgeLayerRegistry:
    """Get the global knowledge layer registry"""
    return _global_registry


def register_semantic_layer(name: str, implementation: Type = None, factory: Callable = None):
    """
    Convenience function to register a semantic layer implementation.

    Args:
        name: Implementation name
        implementation: Class to register (or None if using factory)
        factory: Factory function (or None if using implementation)
    """
    registry = get_global_registry()
    if implementation:
        registry.register_class(LayerType.SEMANTIC, name, implementation)
    elif factory:
        registry.register_factory(LayerType.SEMANTIC, name, factory)


def register_pattern_layer(name: str, implementation: Type = None, factory: Callable = None):
    """Register a pattern detection layer implementation"""
    registry = get_global_registry()
    if implementation:
        registry.register_class(LayerType.PATTERNS, name, implementation)
    elif factory:
        registry.register_factory(LayerType.PATTERNS, name, factory)


def register_lifeofx_layer(name: str, implementation: Type = None, factory: Callable = None):
    """Register a life-of-x tracing layer implementation"""
    registry = get_global_registry()
    if implementation:
        registry.register_class(LayerType.LIFEOFX, name, implementation)
    elif factory:
        registry.register_factory(LayerType.LIFEOFX, name, factory)
