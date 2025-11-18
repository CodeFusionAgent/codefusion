"""
Semantic Similarity Search

Provides semantic search capabilities for code:
- Find similar functions/classes
- Natural language to code search
- Code snippet similarity
"""

import pickle
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from cf.knowledge.semantic.embeddings import CodeEmbedding, CodeEmbedder


@dataclass
class SimilarityResult:
    """Result of similarity search"""
    element_id: str
    element_type: str
    similarity_score: float
    text: str
    metadata: Dict[str, Any]

    def __repr__(self):
        return f"SimilarityResult({self.element_id}, score={self.similarity_score:.3f})"


class SemanticSearch:
    """
    Semantic search engine for code.

    Uses vector embeddings to find semantically similar code elements.
    """

    def __init__(self, embedder: CodeEmbedder, config: Dict[str, Any] = None):
        """
        Initialize semantic search.

        Args:
            embedder: Code embedder instance
            config: Optional configuration dictionary
        """
        self.embedder = embedder
        self.index: List[CodeEmbedding] = []

        # Load semantic search defaults from config
        semantic_config = (config or {}).get('knowledge_base', {}).get('semantic', {})
        self.default_top_k = semantic_config.get('default_top_k', 10)
        self.default_min_similarity = semantic_config.get('default_min_similarity', 0.5)
        self.function_search_min_similarity = semantic_config.get('function_search_min_similarity', 0.7)
        self.class_search_min_similarity = semantic_config.get('class_search_min_similarity', 0.7)
        self.duplicate_code_threshold = semantic_config.get('duplicate_code_threshold', 0.8)

    def add_embedding(self, embedding: CodeEmbedding):
        """
        Add code embedding to search index.

        Args:
            embedding: CodeEmbedding to index
        """
        self.index.append(embedding)

    def add_embeddings(self, embeddings: List[CodeEmbedding]):
        """
        Add multiple embeddings to index.

        Args:
            embeddings: List of CodeEmbeddings
        """
        self.index.extend(embeddings)

    def build_index(self, structural_data_list: List[Any]):
        """
        Build search index from structural data.

        Generates embeddings for all functions and classes.

        Args:
            structural_data_list: List of StructuralData from AST parsing
        """
        print(f"🔍 Building semantic search index...")

        all_embeddings = []

        for structural_data in structural_data_list:
            # Embed functions
            for function in structural_data.functions:
                embedding = self.embedder.embed_function(function)
                all_embeddings.append(embedding)

            # Embed classes
            for class_node in structural_data.classes:
                embedding = self.embedder.embed_class(class_node)
                all_embeddings.append(embedding)

        self.add_embeddings(all_embeddings)

        print(f"✅ Built index with {len(self.index)} code elements")

    def search_by_code(
        self,
        code_snippet: str,
        top_k: int = None,
        min_similarity: float = None,
        element_type: Optional[str] = None
    ) -> List[SimilarityResult]:
        """
        Find code similar to a given snippet.

        Args:
            code_snippet: Code to search for
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            element_type: Filter by type ("function", "class", None for all)

        Returns:
            List of similar code elements, sorted by similarity
        """
        # Apply defaults from config
        top_k = top_k if top_k is not None else self.default_top_k
        min_similarity = min_similarity if min_similarity is not None else self.default_min_similarity

        # Generate embedding for query code
        query_embedding = self.embedder.embed_code_snippet(code_snippet)

        return self._search(query_embedding, top_k, min_similarity, element_type)

    def search_by_natural_language(
        self,
        query: str,
        top_k: int = None,
        min_similarity: float = None,
        element_type: Optional[str] = None
    ) -> List[SimilarityResult]:
        """
        Find code matching natural language description.

        Example queries:
        - "Functions that validate user input"
        - "Classes for database connection pooling"
        - "Code that sends HTTP requests"

        Args:
            query: Natural language description
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            element_type: Filter by type

        Returns:
            List of matching code elements
        """
        # Apply defaults from config
        top_k = top_k if top_k is not None else self.default_top_k
        min_similarity = min_similarity if min_similarity is not None else self.default_min_similarity

        # Generate embedding for natural language query
        query_vector = self.embedder.embed_natural_language(query)

        # Create temporary embedding for search
        query_embedding = CodeEmbedding(
            element_id="query",
            element_type="query",
            embedding=query_vector,
            text=query,
            metadata={}
        )

        return self._search(query_embedding, top_k, min_similarity, element_type)

    def find_similar_functions(
        self,
        function_id: str,
        top_k: int = None,
        min_similarity: float = None
    ) -> List[SimilarityResult]:
        """
        Find functions similar to a specific function.

        Args:
            function_id: Qualified name of function
            top_k: Number of results
            min_similarity: Minimum similarity

        Returns:
            List of similar functions
        """
        # Apply defaults from config
        top_k = top_k if top_k is not None else self.default_top_k
        min_similarity = min_similarity if min_similarity is not None else self.function_search_min_similarity

        # Find the function in index
        query_embedding = None
        for emb in self.index:
            if emb.element_id == function_id and emb.element_type == "function":
                query_embedding = emb
                break

        if query_embedding is None:
            print(f"⚠️ Function {function_id} not found in index")
            return []

        # Search excluding the query function itself
        results = self._search(query_embedding, top_k + 1, min_similarity, "function")

        # Remove the query function from results
        return [r for r in results if r.element_id != function_id][:top_k]

    def find_similar_classes(
        self,
        class_id: str,
        top_k: int = None,
        min_similarity: float = None
    ) -> List[SimilarityResult]:
        """
        Find classes similar to a specific class.

        Args:
            class_id: Qualified name of class
            top_k: Number of results
            min_similarity: Minimum similarity

        Returns:
            List of similar classes
        """
        # Apply defaults from config
        top_k = top_k if top_k is not None else self.default_top_k
        min_similarity = min_similarity if min_similarity is not None else self.class_search_min_similarity

        # Find the class in index
        query_embedding = None
        for emb in self.index:
            if emb.element_id == class_id and emb.element_type == "class":
                query_embedding = emb
                break

        if query_embedding is None:
            print(f"⚠️ Class {class_id} not found in index")
            return []

        # Search excluding the query class itself
        results = self._search(query_embedding, top_k + 1, min_similarity, "class")

        # Remove the query class from results
        return [r for r in results if r.element_id != class_id][:top_k]

    def cluster_similar_code(
        self,
        similarity_threshold: float = None
    ) -> List[List[str]]:
        """
        Find clusters of similar code (potential duplicates).

        Args:
            similarity_threshold: Threshold for considering code similar

        Returns:
            List of clusters (each cluster is a list of element IDs)
        """
        # Apply default from config
        similarity_threshold = similarity_threshold if similarity_threshold is not None else self.duplicate_code_threshold

        if len(self.index) == 0:
            return []

        # Build similarity matrix
        n = len(self.index)
        visited = set()
        clusters = []

        for i in range(n):
            if i in visited:
                continue

            # Start new cluster
            cluster = [self.index[i].element_id]
            visited.add(i)

            # Find similar elements
            for j in range(i + 1, n):
                if j in visited:
                    continue

                similarity = self.index[i].cosine_similarity(self.index[j])
                if similarity >= similarity_threshold:
                    cluster.append(self.index[j].element_id)
                    visited.add(j)

            # Only add clusters with multiple elements
            if len(cluster) > 1:
                clusters.append(cluster)

        return clusters

    def _search(
        self,
        query_embedding: CodeEmbedding,
        top_k: int,
        min_similarity: float,
        element_type: Optional[str]
    ) -> List[SimilarityResult]:
        """
        Internal search implementation.

        Args:
            query_embedding: Query embedding
            top_k: Number of results
            min_similarity: Minimum similarity threshold
            element_type: Filter by type

        Returns:
            List of similarity results
        """
        if len(self.index) == 0:
            return []

        # Calculate similarities
        results = []

        for candidate in self.index:
            # Filter by type if specified
            if element_type and candidate.element_type != element_type:
                continue

            # Calculate similarity
            similarity = query_embedding.cosine_similarity(candidate)

            # Filter by threshold
            if similarity >= min_similarity:
                results.append(SimilarityResult(
                    element_id=candidate.element_id,
                    element_type=candidate.element_type,
                    similarity_score=similarity,
                    text=candidate.text,
                    metadata=candidate.metadata
                ))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x.similarity_score, reverse=True)

        return results[:top_k]

    def get_embedding(self, element_id: str) -> Optional[CodeEmbedding]:
        """
        Get embedding for a specific element.

        Args:
            element_id: Qualified name of element

        Returns:
            CodeEmbedding if found, None otherwise
        """
        for emb in self.index:
            if emb.element_id == element_id:
                return emb
        return None

    def index_size(self) -> int:
        """Get number of indexed elements"""
        return len(self.index)

    def clear_index(self):
        """Clear search index"""
        self.index.clear()

    def save_index(self, file_path: str):
        """
        Save search index to disk.

        Args:
            file_path: Path to save index
        """
        try:
            with open(file_path, 'wb') as f:
                pickle.dump(self.index, f)
            print(f"✅ Saved semantic index ({len(self.index)} elements) to {file_path}")
        except Exception as e:
            print(f"❌ Failed to save semantic index: {e}")

    def load_index(self, file_path: str):
        """
        Load search index from disk.

        Args:
            file_path: Path to load index from
        """
        try:
            with open(file_path, 'rb') as f:
                self.index = pickle.load(f)
            print(f"✅ Loaded semantic index ({len(self.index)} elements) from {file_path}")
        except FileNotFoundError:
            print(f"⚠️ Index file not found: {file_path}")
        except Exception as e:
            print(f"❌ Failed to load semantic index: {e}")


class SemanticSearchStats:
    """Statistics for semantic search index"""

    def __init__(self, search: SemanticSearch):
        self.search = search

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        total = self.search.index_size()

        type_counts = {}
        for emb in self.search.index:
            t = emb.element_type
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            'total_elements': total,
            'by_type': type_counts,
            'embedding_dim': self.search.embedder.embedding_dim if self.search.index else 0
        }

    def print_stats(self):
        """Print index statistics"""
        stats = self.get_stats()

        print("\n📊 Semantic Search Index Statistics:")
        print(f"   Total elements: {stats['total_elements']}")
        print(f"   Embedding dimension: {stats['embedding_dim']}")
        print(f"   By type:")
        for element_type, count in stats['by_type'].items():
            print(f"     - {element_type}: {count}")
