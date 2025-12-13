"""
Code Embedding Generation

Generates vector embeddings for code elements (functions, classes) for semantic search.

Supports multiple embedding providers:
- OpenAI (text-embedding-3-small, text-embedding-3-large)
- Local models (sentence-transformers)
- LiteLLM (unified interface)
"""

import hashlib
import os
import pickle
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import numpy as np

from cf.metrics import get_global_collector

# Optional dependencies - try to import but don't fail if missing
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class EmbeddingModel(Enum):
    """Available embedding models"""
    OPENAI_SMALL = "text-embedding-3-small"  # 1536 dims, $0.02/1M tokens
    OPENAI_LARGE = "text-embedding-3-large"  # 3072 dims, $0.13/1M tokens
    LOCAL_MINILM = "all-MiniLM-L6-v2"        # 384 dims, free, local
    LOCAL_MPNET = "all-mpnet-base-v2"        # 768 dims, free, local


@dataclass
class CodeEmbedding:
    """Represents a code element embedding"""
    element_id: str  # Qualified name (e.g., "module.Class.method")
    element_type: str  # "function", "class", "file"
    embedding: np.ndarray  # Vector embedding
    text: str  # Original text that was embedded
    metadata: Dict[str, Any]  # Additional metadata

    def cosine_similarity(self, other: 'CodeEmbedding') -> float:
        """Calculate cosine similarity with another embedding"""
        dot_product = np.dot(self.embedding, other.embedding)
        norm_a = np.linalg.norm(self.embedding)
        norm_b = np.linalg.norm(other.embedding)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class CodeEmbedder:
    """
    Generates embeddings for code elements.

    Converts functions, classes, and code snippets into vector representations
    for semantic similarity search.
    """

    def __init__(self, model: EmbeddingModel = EmbeddingModel.OPENAI_SMALL, config: Dict[str, Any] = None, llm_client: Any = None):
        """
        Initialize code embedder.

        Args:
            model: Embedding model to use
            config: Configuration (API keys, etc.)
        """
        # Initialize metrics tracking
        self.metrics_collector = get_global_collector()
        self.component_name = 'semantic_embeddings'

        self.model = model
        self.config = config or {}
        self.llm_client = llm_client
        self.embedding_dim = self._get_embedding_dim()

        # Backend selection precedence:
        # 1) Explicit LLM client if requested via config (use_llm_client: true)
        # 2) Local embeddings (default)
        # 3) OpenAI via LiteLLM only if explicitly requested
        if self.config.get('use_llm_client', False) and self.llm_client is not None:
            self.backend = "llm_client"
            print("✅ Initialized embeddings via LLMClient backend")
        else:
            # Prefer local embeddings by default unless explicitly disabled
            use_local = self.config.get('use_local_model', True)

            if use_local or model in (EmbeddingModel.LOCAL_MINILM, EmbeddingModel.LOCAL_MPNET):
                self._init_local()
            else:
                # Only initialize OpenAI path if explicitly requested
                self._init_openai()

    def _get_embedding_dim(self) -> int:
        """Get embedding dimension for the model"""
        dims = {
            EmbeddingModel.OPENAI_SMALL: 1536,
            EmbeddingModel.OPENAI_LARGE: 3072,
            EmbeddingModel.LOCAL_MINILM: 384,
            EmbeddingModel.LOCAL_MPNET: 768
        }
        return dims[self.model]

    def _init_openai(self):
        """Initialize OpenAI embeddings via LiteLLM"""
        if not LITELLM_AVAILABLE:
            raise RuntimeError("litellm not available. Install with: pip install litellm")

        self.litellm = litellm
        self.backend = "openai"
        print(f"✅ Initialized OpenAI embeddings: {self.model.value}")

    def _init_local(self):
        """Initialize local sentence-transformers"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers not available. "
                "Install with: pip install sentence-transformers"
            )

        self.local_model = SentenceTransformer(self.model.value)
        self.backend = "local"
        print(f"✅ Initialized local embeddings: {self.model.value}")

    def embed_function(self, function_node: Any) -> CodeEmbedding:
        """
        Generate embedding for a function.

        Creates a text representation including:
        - Function name
        - Parameters
        - Return type
        - Docstring

        Args:
            function_node: FunctionNode from AST parser

        Returns:
            CodeEmbedding with vector representation
        """
        # Build text representation
        parts = []

        # Function signature
        params = ", ".join(function_node.parameters)
        signature = f"def {function_node.name}({params})"
        if function_node.return_type:
            signature += f" -> {function_node.return_type}"
        parts.append(signature)

        # Docstring
        if function_node.docstring:
            parts.append(function_node.docstring)

        # Combine
        text = "\n".join(parts)

        # Generate embedding
        embedding_vector = self._embed_text(text)

        return CodeEmbedding(
            element_id=function_node.qualified_name,
            element_type="function",
            embedding=embedding_vector,
            text=text,
            metadata={
                'name': function_node.name,
                'file_path': function_node.file_path,
                'parameters': function_node.parameters,
                'is_async': function_node.is_async,
                'complexity': function_node.cyclomatic_complexity
            }
        )

    def embed_class(self, class_node: Any) -> CodeEmbedding:
        """
        Generate embedding for a class.

        Creates a text representation including:
        - Class name
        - Base classes
        - Docstring

        Args:
            class_node: ClassNode from AST parser

        Returns:
            CodeEmbedding with vector representation
        """
        # Build text representation
        parts = []

        # Class signature
        bases = ", ".join(class_node.base_classes) if class_node.base_classes else ""
        signature = f"class {class_node.name}"
        if bases:
            signature += f"({bases})"
        parts.append(signature)

        # Docstring
        if class_node.docstring:
            parts.append(class_node.docstring)

        # Combine
        text = "\n".join(parts)

        # Generate embedding
        embedding_vector = self._embed_text(text)

        return CodeEmbedding(
            element_id=class_node.qualified_name,
            element_type="class",
            embedding=embedding_vector,
            text=text,
            metadata={
                'name': class_node.name,
                'file_path': class_node.file_path,
                'base_classes': class_node.base_classes,
                'num_methods': class_node.num_methods
            }
        )

    def embed_code_snippet(self, code: str, element_id: str = None) -> CodeEmbedding:
        """
        Generate embedding for arbitrary code snippet.

        Args:
            code: Code snippet to embed
            element_id: Optional identifier

        Returns:
            CodeEmbedding with vector representation
        """
        if element_id is None:
            element_id = hashlib.md5(code.encode()).hexdigest()

        embedding_vector = self._embed_text(code)

        return CodeEmbedding(
            element_id=element_id,
            element_type="snippet",
            embedding=embedding_vector,
            text=code,
            metadata={}
        )

    def embed_natural_language(self, query: str) -> np.ndarray:
        """
        Generate embedding for natural language query.

        Used for semantic search: "Find functions that validate user input"

        Args:
            query: Natural language query

        Returns:
            Embedding vector
        """
        return self._embed_text(query)

    def _embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for text using configured backend.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array
        """
        # Estimate tokens and cost
        tokens = len(text) // 4  # Rough estimate
        cost = 0.0

        if self.backend == "openai":
            # OpenAI pricing
            if self.model == EmbeddingModel.OPENAI_SMALL:
                cost = (tokens / 1_000_000) * 0.02  # $0.02 per 1M tokens
            elif self.model == EmbeddingModel.OPENAI_LARGE:
                cost = (tokens / 1_000_000) * 0.13  # $0.13 per 1M tokens
        # Local models have zero cost

        # Track the operation
        with self.metrics_collector.track_operation(self.component_name, tokens=tokens, cost=cost):
            if self.backend == "llm_client":
                return self._embed_with_llm_client(text)
            elif self.backend == "openai":
                return self._embed_with_openai(text)
            else:
                return self._embed_with_local(text)

    def _embed_with_llm_client(self, text: str) -> np.ndarray:
        """Generate embedding using provided LLMClient (provider/model defined in config)."""
        try:
            # Allow config to specify embedding model name to pass through
            model_override = self.config.get('embedding_model', None)
            resp = self.llm_client.embed_text(text, model=model_override)
            if isinstance(resp, dict) and resp.get('success') and isinstance(resp.get('embedding'), list):
                return np.array(resp['embedding'], dtype=np.float32)
            # Fallback to zero vector on failure
            return np.zeros(self.embedding_dim, dtype=np.float32)
        except Exception as e:
            print(f"❌ LLMClient embedding failed: {e}")
            return np.zeros(self.embedding_dim, dtype=np.float32)

    def _embed_with_openai(self, text: str) -> np.ndarray:
        """Generate embedding using OpenAI via LiteLLM"""
        try:
            response = self.litellm.embedding(
                model=self.model.value,
                input=[text]
            )

            # Extract embedding from response
            embedding = response.data[0]['embedding']
            return np.array(embedding, dtype=np.float32)

        except Exception as e:
            print(f"❌ OpenAI embedding failed: {e}")
            # Return zero vector as fallback
            return np.zeros(self.embedding_dim, dtype=np.float32)

    def _embed_with_local(self, text: str) -> np.ndarray:
        """Generate embedding using local sentence-transformers"""
        try:
            embedding = self.local_model.encode(text, convert_to_numpy=True)
            return embedding.astype(np.float32)
        except Exception as e:
            print(f"❌ Local embedding failed: {e}")
            # Return zero vector as fallback
            return np.zeros(self.embedding_dim, dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts (more efficient).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if self.backend == "openai":
            # OpenAI supports batch embedding
            try:
                response = self.litellm.embedding(
                    model=self.model.value,
                    input=texts
                )

                embeddings = [
                    np.array(item['embedding'], dtype=np.float32)
                    for item in response.data
                ]
                return embeddings

            except Exception as e:
                print(f"❌ Batch OpenAI embedding failed: {e}")
                return [np.zeros(self.embedding_dim, dtype=np.float32) for _ in texts]
        else:
            # Local model batch encoding
            try:
                embeddings = self.local_model.encode(texts, convert_to_numpy=True, show_progress_bar=len(texts) > 100)
                return [emb.astype(np.float32) for emb in embeddings]
            except Exception as e:
                print(f"❌ Batch local embedding failed: {e}")
                return [np.zeros(self.embedding_dim, dtype=np.float32) for _ in texts]

    def benchmark_quality(self, test_pairs: List[tuple] = None) -> Dict[str, Any]:
        """
        Benchmark embedding quality using test code pairs.

        NEW: Helps detect when semantic search is missing relevant files
        due to poor embedding quality.

        Args:
            test_pairs: List of (similar_code1, similar_code2) tuples.
                       If None, uses default test pairs.

        Returns:
            Dict with quality metrics:
            - average_similarity: Mean similarity for similar pairs
            - quality_score: 0-1 score (higher is better)
            - recommendation: "good", "acceptable", or "poor"
        """
        if test_pairs is None:
            # Default test pairs: semantically similar code snippets
            test_pairs = [
                (
                    "def calculate_total(items): return sum(item.price for item in items)",
                    "def compute_sum(elements): return sum(e.value for e in elements)"
                ),
                (
                    "class User: def __init__(self, name): self.name = name",
                    "class Person: def __init__(self, full_name): self.full_name = full_name"
                ),
                (
                    "async def fetch_data(url): response = await http.get(url); return response.json()",
                    "async def get_resource(endpoint): result = await client.get(endpoint); return result.data"
                )
            ]

        similarities = []

        for code1, code2 in test_pairs:
            emb1 = self._embed_text(code1)
            emb2 = self._embed_text(code2)

            # Calculate cosine similarity
            dot_product = np.dot(emb1, emb2)
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)

            if norm1 > 0 and norm2 > 0:
                similarity = dot_product / (norm1 * norm2)
                similarities.append(similarity)

        avg_similarity = np.mean(similarities) if similarities else 0.0

        # Quality scoring
        # Good embeddings should show >0.7 similarity for similar code
        # Acceptable: 0.5-0.7
        # Poor: <0.5
        if avg_similarity >= 0.7:
            recommendation = "good"
            quality_score = min(1.0, avg_similarity / 0.85)
        elif avg_similarity >= 0.5:
            recommendation = "acceptable"
            quality_score = 0.5 + (avg_similarity - 0.5) / 0.4
        else:
            recommendation = "poor"
            quality_score = avg_similarity / 0.5

        return {
            'model': self.model.value,
            'backend': self.backend,
            'average_similarity': float(avg_similarity),
            'quality_score': float(quality_score),
            'recommendation': recommendation,
            'tested_pairs': len(similarities),
            'message': self._get_quality_message(recommendation, avg_similarity)
        }

    def _get_quality_message(self, recommendation: str, similarity: float) -> str:
        """Get human-readable message about embedding quality"""
        if recommendation == "good":
            return f"✅ Embedding quality is good (similarity: {similarity:.2f}). Semantic search should work well."
        elif recommendation == "acceptable":
            return f"⚠️ Embedding quality is acceptable (similarity: {similarity:.2f}). Consider using OpenAI embeddings for better results."
        else:
            return f"❌ Embedding quality is poor (similarity: {similarity:.2f}). Recommend switching to OpenAI embeddings or using a different local model."


class EmbeddingCache:
    """
    Cache for code embeddings to avoid recomputation.

    Stores embeddings in memory with optional persistence.
    """

    def __init__(self, cache_file: Optional[str] = None):
        """
        Initialize embedding cache.

        Args:
            cache_file: Optional path to persist cache
        """
        self.cache: Dict[str, CodeEmbedding] = {}
        self.cache_file = cache_file

        if cache_file:
            self._load_cache()

    def get(self, element_id: str) -> Optional[CodeEmbedding]:
        """Get cached embedding"""
        return self.cache.get(element_id)

    def put(self, embedding: CodeEmbedding):
        """Store embedding in cache"""
        self.cache[embedding.element_id] = embedding

    def has(self, element_id: str) -> bool:
        """Check if embedding is cached"""
        return element_id in self.cache

    def clear(self):
        """Clear cache"""
        self.cache.clear()

    def _load_cache(self):
        """Load cache from disk"""
        if not self.cache_file:
            return

        try:
            with open(self.cache_file, 'rb') as f:
                self.cache = pickle.load(f)
            print(f"✅ Loaded {len(self.cache)} embeddings from cache")
        except FileNotFoundError:
            print("ℹ️ No embedding cache found")
        except Exception as e:
            print(f"⚠️ Failed to load embedding cache: {e}")

    def save(self):
        """Save cache to disk"""
        if not self.cache_file:
            return

        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            print(f"✅ Saved {len(self.cache)} embeddings to cache")
        except Exception as e:
            print(f"❌ Failed to save embedding cache: {e}")


# ============================================================================
# SEMANTIC SEARCH
# ============================================================================



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

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
        llm_client: Any = None
    ) -> Optional['SemanticSearch']:
        """
        Create SemanticSearch instance from configuration.

        Factory method that handles initialization, configuration parsing,
        and returns None if semantic search is disabled.

        Args:
            config: Full configuration dictionary
            llm_client: Optional LLM client for embeddings

        Returns:
            SemanticSearch instance or None if disabled
        """
        semantic_config = config.get('knowledge_base', {}).get('semantic', {})

        # Check if semantic search is enabled
        if not semantic_config.get('enabled', False):
            return None

        # Initialize embedder
        model_name = semantic_config.get('embedding_model', 'all-MiniLM-L6-v2')
        use_local = semantic_config.get('use_local_model', True)

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

        # Create embedder
        try:
            embedder = CodeEmbedder(
                model=model,
                config=semantic_config,
                llm_client=llm_client
            )
        except Exception as e:
            print(f"⚠️ Failed to initialize semantic search embedder: {e}")
            return None

        # Create and return search instance
        return cls(embedder=embedder, config=config)

    def initialize_from_structural_data(
        self,
        structural_data_list: List[Any],
        cache_file: Optional[str] = None
    ):
        """
        Build semantic search index from structural data and optionally save to cache.

        Args:
            structural_data_list: List of StructuralData from AST parsing
            cache_file: Optional path to save embeddings cache
        """
        print("   🧠 Building semantic search index...")

        # Build index
        self.build_index(structural_data_list)

        # Save to cache if requested
        if cache_file:
            try:
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                self.save_index(cache_file)
                print(f"   💾 Saved embeddings to {cache_file}")
            except Exception as e:
                print(f"   ⚠️ Failed to save embeddings cache: {e}")

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
