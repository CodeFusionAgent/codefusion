"""
Semantic Search Manager

Handles embeddings generation and semantic similarity search.
Extracted from StructuralPipeline to improve maintainability.
"""

import os
from typing import Dict, List, Any, Optional

from cf.knowledge.semantic.embeddings import CodeEmbedder, EmbeddingModel
from cf.knowledge.semantic.similarity import SemanticSearch


class SemanticSearchManager:
    """
    Manages semantic search operations.

    Responsibilities:
    - Code embeddings generation
    - Semantic similarity search
    - Embedding cache management
    """

    def __init__(self, config: Dict[str, Any], llm_client=None):
        self.config = config
        self.semantic_config = config.get('knowledge_base', {}).get('semantic', {})
        self._embedder = None
        self._search = None
        self._llm_client = llm_client

    def is_enabled(self) -> bool:
        """Check if semantic search is enabled"""
        return self.semantic_config.get('enabled', False)

    def initialize(self, structural_data_list: List[Any] = None):
        """
        Initialize semantic search with embeddings.

        Args:
            structural_data_list: Optional structural data to build index from
        """
        if not self.is_enabled():
            return

        print("   🧠 Initializing semantic search...")

        # Initialize embedder via property (lazy initialization)
        if self.embedder is None:
            print("   ⚠️ Failed to initialize embedder")
            return

        # Initialize search via property
        if self.search is None:
            print("   ⚠️ Failed to initialize search")
            return

        # Build index if data provided
        if structural_data_list:
            self.search.build_index(structural_data_list)

            # Save to cache if enabled
            if self.semantic_config.get('cache_embeddings', False):
                cache_file = self.semantic_config.get('cache_file', '.codefusion/embeddings.pkl')
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                self.search.save_index(cache_file)
                print(f"   💾 Saved embeddings to {cache_file}")

    def load_from_cache(self, cache_file: str) -> bool:
        """
        Load embeddings from cache file.

        Returns:
            True if loaded successfully
        """
        if not self.is_enabled():
            return False

        try:
            if not os.path.exists(cache_file):
                return False

            # Initialize embedder via property if needed
            if self.embedder is None:
                print(f"   ⚠️ Failed to initialize embedder")
                return False

            # Initialize search via property and load index
            if self.search is None:
                print(f"   ⚠️ Failed to initialize search")
                return False

            self.search.load_index(cache_file)

            print(f"   ✅ Loaded embeddings from cache: {cache_file}")
            return True

        except Exception as e:
            print(f"   ⚠️ Failed to load embeddings from cache: {e}")
            return False

    @property
    def embedder(self) -> Optional[CodeEmbedder]:
        """Get code embedder (lazy initialization)"""
        if not self.is_enabled():
            return None

        if self._embedder is None:
            model_name = self.semantic_config.get('embedding_model', 'all-MiniLM-L6-v2')
            use_local = self.semantic_config.get('use_local_model', True)

            # Map config to EmbeddingModel enum
            if use_local:
                if 'mpnet' in model_name.lower():
                    model = EmbeddingModel.LOCAL_MPNET
                else:
                    model = EmbeddingModel.LOCAL_MINILM
            else:
                if 'large' in model_name:
                    model = EmbeddingModel.OPENAI_LARGE
                else:
                    model = EmbeddingModel.OPENAI_SMALL

            # Use LLM client if available and configured
            llm_client = None
            if self.semantic_config.get('use_llm_client', False):
                llm_client = self._llm_client
                if llm_client is None:
                    print(f"⚠️ [SEMANTIC] LLM client not available, using local embeddings")

            # Initialize CodeEmbedder with proper parameters
            self._embedder = CodeEmbedder(
                model=model,
                config=self.semantic_config,
                llm_client=llm_client
            )

        return self._embedder

    @property
    def search(self) -> Optional[SemanticSearch]:
        """Get semantic search (lazy initialization)"""
        if not self.is_enabled():
            return None

        if self._search is None:
            # Initialize embedder first
            if self.embedder is None:
                return None

            self._search = SemanticSearch(embedder=self.embedder)

        return self._search
