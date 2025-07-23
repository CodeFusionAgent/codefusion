"""
Semantic Cache for CodeFusion

Simple JSON-based caching with semantic similarity search.
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np


class SemanticCache:
    """Simple semantic cache using JSON storage and cosine similarity"""
    
    def __init__(self, agent_name: str, cache_config: Dict[str, Any]):
        self.agent_name = agent_name
        self.enabled = cache_config.get('enabled', True)
        self.ttl = cache_config.get('ttl', 3600)  # 1 hour default
        self.similarity_threshold = cache_config.get('similarity_threshold', 0.85)
        self.max_cache_size = cache_config.get('max_size', 1000)
        
        # Cache directory
        self.cache_dir = Path(cache_config.get('cache_dir', 'cf_cache'))
        self.cache_file = self.cache_dir / f"{agent_name}_cache.json"
        
        # In-memory cache
        self.cache_data = {}
        self.embeddings_cache = {}
        
        # LLM client for embeddings (will be set by agent)
        self.llm_client = None
        
        # Initialize
        if self.enabled:
            self.cache_dir.mkdir(exist_ok=True)
            self._load_cache()
    
    def set_llm_client(self, llm_client):
        """Set LLM client for generating embeddings"""
        self.llm_client = llm_client
    
    def get(self, key: str, semantic_query: str = "") -> Optional[Dict[str, Any]]:
        """Get cached result by key or semantic similarity"""
        if not self.enabled:
            return None
        
        # Clean expired entries first
        self._clean_expired()
        
        # Try exact key match first
        if key in self.cache_data:
            entry = self.cache_data[key]
            if not self._is_expired(entry):
                entry['hits'] = entry.get('hits', 0) + 1
                entry['last_accessed'] = time.time()
                return entry['result']
        
        # If semantic query provided, try semantic search
        if semantic_query and self.llm_client:
            similar_entry = self._find_similar(semantic_query)
            if similar_entry:
                similar_entry['hits'] = similar_entry.get('hits', 0) + 1
                similar_entry['last_accessed'] = time.time()
                return similar_entry['result']
        
        return None
    
    def set(self, key: str, result: Dict[str, Any], semantic_key: str = "", metadata: Dict[str, Any] = None):
        """Cache a result with optional semantic key"""
        if not self.enabled:
            return
        
        # Clean cache if too large
        if len(self.cache_data) >= self.max_cache_size:
            self._evict_old_entries()
        
        entry = {
            'result': result,
            'timestamp': time.time(),
            'last_accessed': time.time(),
            'hits': 0,
            'metadata': metadata or {},
            'semantic_key': semantic_key
        }
        
        # Generate embedding for semantic search
        if semantic_key and self.llm_client:
            embedding_result = self.llm_client.embed_text(semantic_key)
            if embedding_result.get('success'):
                entry['embedding'] = embedding_result['embedding']
        
        self.cache_data[key] = entry
        self._save_cache()
    
    def _find_similar(self, query: str) -> Optional[Dict[str, Any]]:
        """Find semantically similar cached entry"""
        if not self.llm_client:
            return None
        
        # Get query embedding
        query_embedding_result = self.llm_client.embed_text(query)
        if not query_embedding_result.get('success'):
            return None
        
        query_embedding = np.array(query_embedding_result['embedding'])
        best_similarity = 0
        best_entry = None
        
        for key, entry in self.cache_data.items():
            if 'embedding' not in entry or self._is_expired(entry):
                continue
            
            # Calculate cosine similarity
            cached_embedding = np.array(entry['embedding'])
            similarity = self._cosine_similarity(query_embedding, cached_embedding)
            
            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_entry = entry
        
        return best_entry
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0
            
            return dot_product / (norm_a * norm_b)
        except:
            return 0
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired"""
        if self.ttl <= 0:  # Never expire if TTL is 0 or negative
            return False
        return time.time() - entry['timestamp'] > self.ttl
    
    def _clean_expired(self):
        """Remove expired entries from cache"""
        expired_keys = [
            key for key, entry in self.cache_data.items()
            if self._is_expired(entry)
        ]
        
        for key in expired_keys:
            del self.cache_data[key]
        
        if expired_keys:
            self._save_cache()
    
    def _evict_old_entries(self):
        """Evict least recently used entries to make space"""
        # Keep only the most recently accessed entries
        sorted_entries = sorted(
            self.cache_data.items(),
            key=lambda x: x[1].get('last_accessed', 0),
            reverse=True
        )
        
        # Keep top 80% of max cache size
        keep_count = int(self.max_cache_size * 0.8)
        self.cache_data = dict(sorted_entries[:keep_count])
        self._save_cache()
    
    def _load_cache(self):
        """Load cache from disk"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.cache_data = data.get('entries', {})
        except Exception as e:
            # If cache file is corrupted, start fresh
            self.cache_data = {}
    
    def _save_cache(self):
        """Save cache to disk"""
        try:
            cache_export = {
                'agent_name': self.agent_name,
                'created': time.time(),
                'entries': self.cache_data
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_export, f, indent=2)
        except Exception:
            # Fail silently - caching is not critical
            pass
    
    def clear(self):
        """Clear all cache entries"""
        self.cache_data = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.enabled:
            return {'enabled': False}
        
        total_hits = sum(entry.get('hits', 0) for entry in self.cache_data.values())
        semantic_entries = sum(1 for entry in self.cache_data.values() if 'embedding' in entry)
        
        return {
            'enabled': True,
            'total_entries': len(self.cache_data),
            'semantic_entries': semantic_entries,
            'total_hits': total_hits,
            'cache_size_mb': self._get_cache_size_mb(),
            'oldest_entry': min(
                (entry['timestamp'] for entry in self.cache_data.values()),
                default=time.time()
            ),
            'hit_rate': total_hits / max(len(self.cache_data), 1)
        }
    
    def _get_cache_size_mb(self) -> float:
        """Get approximate cache size in MB"""
        try:
            if self.cache_file.exists():
                return self.cache_file.stat().st_size / (1024 * 1024)
            return 0
        except:
            return 0
    
    def search_cache(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search cache entries for debugging/inspection"""
        if not self.enabled:
            return []
        
        results = []
        query_lower = query.lower()
        
        for key, entry in self.cache_data.items():
            # Search in key, semantic_key, and metadata
            if (query_lower in key.lower() or
                query_lower in entry.get('semantic_key', '').lower() or
                any(query_lower in str(v).lower() for v in entry.get('metadata', {}).values())):
                
                results.append({
                    'key': key,
                    'semantic_key': entry.get('semantic_key', ''),
                    'timestamp': entry['timestamp'],
                    'hits': entry.get('hits', 0),
                    'metadata': entry.get('metadata', {}),
                    'has_embedding': 'embedding' in entry
                })
        
        # Sort by hits and recency
        results.sort(key=lambda x: (x['hits'], x['timestamp']), reverse=True)
        return results[:limit]