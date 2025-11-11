"""
Code Embedding Generation

Generates vector embeddings for code elements (functions, classes) for semantic search.

Supports multiple embedding providers:
- OpenAI (text-embedding-3-small, text-embedding-3-large)
- Local models (sentence-transformers)
- LiteLLM (unified interface)
"""

import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import numpy as np


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

    def __init__(self, model: EmbeddingModel = EmbeddingModel.OPENAI_SMALL, config: Dict[str, Any] = None):
        """
        Initialize code embedder.

        Args:
            model: Embedding model to use
            config: Configuration (API keys, etc.)
        """
        self.model = model
        self.config = config or {}
        self.embedding_dim = self._get_embedding_dim()

        # Initialize backend based on model
        if model in (EmbeddingModel.OPENAI_SMALL, EmbeddingModel.OPENAI_LARGE):
            self._init_openai()
        else:
            self._init_local()

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
        try:
            import litellm
            self.litellm = litellm
            self.backend = "openai"
            print(f"✅ Initialized OpenAI embeddings: {self.model.value}")
        except ImportError:
            raise RuntimeError("litellm not available. Install with: pip install litellm")

    def _init_local(self):
        """Initialize local sentence-transformers"""
        try:
            from sentence_transformers import SentenceTransformer
            self.local_model = SentenceTransformer(self.model.value)
            self.backend = "local"
            print(f"✅ Initialized local embeddings: {self.model.value}")
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not available. "
                "Install with: pip install sentence-transformers"
            )

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
        if self.backend == "openai":
            return self._embed_with_openai(text)
        else:
            return self._embed_with_local(text)

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
            import pickle
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
            import pickle
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            print(f"✅ Saved {len(self.cache)} embeddings to cache")
        except Exception as e:
            print(f"❌ Failed to save embedding cache: {e}")
