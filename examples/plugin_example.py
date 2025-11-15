"""
Example: Using Plugin Registry for Custom Knowledge Layers

Shows how to register and use custom implementations without modifying core code.
"""

import sys
from pathlib import Path
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cf.knowledge.plugin_registry import (
    get_global_registry,
    LayerType,
    register_semantic_layer
)
from cf.knowledge.semantic.embeddings import CodeEmbedder, CodeEmbedding, EmbeddingModel
from cf.knowledge.patterns.design_patterns import DesignPatternDetector, PatternMatch, DesignPattern
from cf.knowledge.metrics import KnowledgeLayerMetrics


# ============================================================================
# Example 1: Custom Embedding Model
# ============================================================================

class CustomFastEmbedder(CodeEmbedder):
    """
    Custom embedder using a different approach.

    Example: Use sentence-transformers with custom preprocessing
    """

    def __init__(self, model: EmbeddingModel, config: dict, llm_client=None):
        super().__init__(model, config, llm_client)
        print("✅ CustomFastEmbedder initialized")

    def _embed_text(self, text: str) -> np.ndarray:
        """
        Custom embedding logic with special preprocessing.

        Example: Remove comments, normalize whitespace, etc.
        """
        # Track metrics
        tokens = len(text) // 4
        with self.track_operation(tokens=tokens, cost=0.0):
            # Custom preprocessing
            text = self._preprocess(text)

            # Use parent implementation
            return super()._embed_text(text)

    def _preprocess(self, text: str) -> str:
        """Custom preprocessing logic"""
        # Remove single-line comments
        lines = [line for line in text.split('\n')
                 if not line.strip().startswith('#')]
        return '\n'.join(lines)


# ============================================================================
# Example 2: Custom Pattern Detector
# ============================================================================

class MLPatternDetector(DesignPatternDetector):
    """
    Custom pattern detector using machine learning.

    Example: Use a trained ML model instead of heuristics
    """

    def __init__(self):
        super().__init__()
        # self.ml_model = load_trained_model('pattern_detector.pkl')
        print("✅ MLPatternDetector initialized")

    def _detect_singleton(self, class_node) -> list[PatternMatch]:
        """
        Detect singleton using ML model instead of heuristics.

        Example: Feed class features to ML model
        """
        # Extract features
        features = self._extract_features(class_node)

        # Use ML model to predict (example - would use real model)
        # confidence = self.ml_model.predict_proba(features)[0][1]
        confidence = 0.75  # Example

        if confidence > 0.7:
            return [PatternMatch(
                pattern=DesignPattern.SINGLETON,
                confidence=confidence,
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=["ML model prediction"],
                metadata={'model': 'trained_pattern_detector_v1'}
            )]

        return []

    def _extract_features(self, class_node) -> dict:
        """Extract features for ML model"""
        return {
            'num_methods': class_node.num_methods,
            'has_instance_var': '__instance' in [v.name for v in class_node.variables],
            'has_new_method': '__new__' in [m.name for m in class_node.methods]
        }


# ============================================================================
# Example 3: Using the Registry
# ============================================================================

def example_register_and_use_custom_embedder():
    """Example: Register and use custom embedder"""
    print("\n" + "="*80)
    print("Example: Custom Embedder via Plugin Registry")
    print("="*80)

    # Get global registry
    registry = get_global_registry()

    # Register custom implementation
    registry.register_class(
        LayerType.SEMANTIC,
        'custom_fast',
        CustomFastEmbedder
    )

    # Create instance via registry
    config = {'use_local_model': True}
    embedder = registry.create(
        LayerType.SEMANTIC,
        'custom_fast',
        EmbeddingModel.LOCAL_MINILM,
        config
    )

    print(f"✅ Created embedder: {type(embedder).__name__}")

    # Use it
    code = """
    def hello():
        # This is a comment
        print("Hello")
    """

    embedding = embedder.embed_code_snippet(code)
    print(f"✅ Generated embedding: {embedding.embedding.shape}")

    # Check metrics
    metrics = embedder.get_metrics()
    print(f"\n📊 Metrics:")
    print(f"   Calls: {metrics['total_calls']}")
    print(f"   Duration: {metrics['total_duration']:.4f}s")


def example_register_with_factory():
    """Example: Register using factory function"""
    print("\n" + "="*80)
    print("Example: Factory Function Registration")
    print("="*80)

    registry = get_global_registry()

    # Factory function for custom embedder
    def create_custom_embedder(model, config):
        print("   Factory: Creating custom embedder with special config")
        config['custom_option'] = True
        return CustomFastEmbedder(model, config)

    # Register factory
    registry.register_factory(
        LayerType.SEMANTIC,
        'factory_embedder',
        create_custom_embedder
    )

    # Create via factory
    embedder = registry.create(
        LayerType.SEMANTIC,
        'factory_embedder',
        EmbeddingModel.LOCAL_MINILM,
        {}
    )

    print(f"✅ Created via factory: {type(embedder).__name__}")


def example_list_implementations():
    """Example: List available implementations"""
    print("\n" + "="*80)
    print("Example: List Available Implementations")
    print("="*80)

    registry = get_global_registry()

    # Register some implementations
    registry.register_class(LayerType.SEMANTIC, 'impl_a', CustomFastEmbedder)
    registry.register_class(LayerType.SEMANTIC, 'impl_b', CustomFastEmbedder)
    registry.register_class(LayerType.PATTERNS, 'ml_detector', MLPatternDetector)

    # List implementations
    print("\n📋 Registered Implementations:")

    for layer_type in LayerType:
        implementations = registry.list_implementations(layer_type)
        if implementations:
            print(f"\n{layer_type.value}:")
            for impl in implementations:
                print(f"  - {impl}")


def example_use_in_experiment():
    """Example: Use custom implementation in experiment"""
    print("\n" + "="*80)
    print("Example: Custom Implementation in Experiment")
    print("="*80)

    # This shows how you would configure an experiment to use
    # a custom knowledge layer implementation

    experiment_config = {
        'name': 'custom_embedder_test',
        'config': {
            'knowledge_base': {
                'semantic': {
                    'enabled': True,
                    'use_plugin': True,  # Enable plugin system
                    'plugin_name': 'custom_fast',  # Use our custom embedder
                    'use_local_model': True
                }
            }
        }
    }

    print("Experiment configuration:")
    print(f"  Plugin: {experiment_config['config']['knowledge_base']['semantic']['plugin_name']}")
    print(f"  Would use: CustomFastEmbedder")

    # In StructuralPipeline, you would check:
    # if semantic_config.get('use_plugin'):
    #     plugin_name = semantic_config['plugin_name']
    #     embedder = registry.create(LayerType.SEMANTIC, plugin_name, model, config)


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("CodeFusion Plugin Registry Examples")
    print("="*80)

    # Run examples
    example_register_and_use_custom_embedder()
    example_register_with_factory()
    example_list_implementations()
    example_use_in_experiment()

    print("\n✅ All examples completed!")
