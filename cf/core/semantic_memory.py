"""
Semantic Memory System for CodeFusion

This module implements semantic similarity-based memory retrieval using LLM reasoning
and intelligent caching to avoid redundant work by agents.
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

from cf.config import CfConfig
from cf.llm.real_llm import get_real_llm, init_real_llm
from cf.utils.logging_utils import info_log, progress_log, error_log


@dataclass
class SemanticMemoryEntry:
    """Represents a single semantic memory entry."""
    id: str
    content: str
    content_type: str  # 'exploration_narrative', 'component_discovery', 'code_insight', 'web_search'
    source_file: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CacheEntry:
    """Represents a cached agent result."""
    cache_key: str
    agent_type: str  # 'code', 'docs', 'web'
    result_data: Dict[str, Any]
    context_summary: str = ""  # Brief summary for LLM comparison
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    hit_count: int = 0
    last_hit: str = field(default_factory=lambda: datetime.now().isoformat())


class SemanticMemorySystem:
    """
    Semantic memory system with LLM-based similarity and intelligent caching.
    
    Features:
    - LLM-based semantic similarity search for memory retrieval
    - Intelligent caching for code/docs/web agents
    - JSON file storage for persistence
    - Automatic cache invalidation and cleanup
    """
    
    def __init__(self, config: CfConfig, session_dir: Path):
        self.config = config
        self.session_dir = session_dir
        self.memory_entries: List[SemanticMemoryEntry] = []
        self.cache_entries: Dict[str, CacheEntry] = {}
        
        # Memory settings
        self.max_memory_entries = 500
        self.max_cache_entries = 100
        
        # Load existing memory and cache
        self._load_memory_from_disk()
        self._load_cache_from_disk()
    
    def calculate_llm_similarity(self, query: str, content: str) -> float:
        """Calculate semantic similarity using LLM reasoning."""
        try:
            llm = get_real_llm()
            if llm is None:
                return 0.0
            
            # Use LLM to determine semantic similarity
            similarity_result = llm.reasoning(
                context=f"""
                Query: {query[:500]}
                
                Content to compare: {content[:500]}
                """,
                question="Rate the semantic similarity between the query and content on a scale of 0.0 to 1.0, where 1.0 means highly relevant/similar and 0.0 means completely unrelated. Consider topics, concepts, technical terms, and intent. Return only a number between 0.0 and 1.0.",
                agent_type="similarity_analysis"
            )
            
            reasoning = similarity_result.get('reasoning', '0.0')
            
            # Extract numerical score from reasoning
            score_match = re.search(r'(\d*\.?\d+)', reasoning)
            if score_match:
                score = float(score_match.group(1))
                # Ensure score is between 0.0 and 1.0
                return max(0.0, min(1.0, score))
            
            return 0.0
            
        except Exception as e:
            error_log(f"❌ LLM similarity calculation failed: {e}")
            return 0.0
    
    def store_memory(self, content: str, content_type: str, source_file: Optional[str] = None, metadata: Dict[str, Any] = None) -> str:
        """Store content in semantic memory."""
        entry_id = f"{content_type}_{int(time.time() * 1000)}"
        
        # Create memory entry
        memory_entry = SemanticMemoryEntry(
            id=entry_id,
            content=content,
            content_type=content_type,
            source_file=source_file,
            metadata=metadata or {}
        )
        
        self.memory_entries.append(memory_entry)
        
        # Cleanup old entries if needed
        if len(self.memory_entries) > self.max_memory_entries:
            self.memory_entries = self.memory_entries[-self.max_memory_entries:]
        
        progress_log(f"🧠 Stored semantic memory: {content_type} ({len(content)} chars)")
        return entry_id
    
    def find_similar_memories(self, query: str, content_type: Optional[str] = None, top_k: int = 5) -> List[Tuple[SemanticMemoryEntry, float]]:
        """Find semantically similar memories using LLM."""
        if not self.memory_entries:
            return []
        
        # Calculate LLM-based similarities
        similarities = []
        for entry in self.memory_entries:
            if content_type and entry.content_type != content_type:
                continue
            
            # Use LLM to calculate semantic similarity
            similarity = self.calculate_llm_similarity(query, entry.content)
            
            # Only include if similarity is above threshold (0.3)
            if similarity >= 0.3:
                similarities.append((entry, similarity))
        
        # Sort by similarity and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Update access count for returned entries
        for entry, _ in similarities[:top_k]:
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
        
        progress_log(f"🔍 Found {len(similarities)} similar memories for query (LLM-based)")
        return similarities[:top_k]
    
    def check_cache(self, cache_key: str, agent_type: str) -> Optional[Dict[str, Any]]:
        """Check if result is cached and return if similar enough."""
        if cache_key not in self.cache_entries:
            return None
        
        cache_entry = self.cache_entries[cache_key]
        
        # Update hit statistics
        cache_entry.hit_count += 1
        cache_entry.last_hit = datetime.now().isoformat()
        
        progress_log(f"💾 Cache hit for {agent_type}: {cache_key}")
        return cache_entry.result_data
    
    def store_cache(self, cache_key: str, agent_type: str, result_data: Dict[str, Any], context: str = "") -> None:
        """Store agent result in cache with context summary."""
        cache_entry = CacheEntry(
            cache_key=cache_key,
            agent_type=agent_type,
            result_data=result_data,
            context_summary=context[:200] if context else ""  # Store brief context for comparison
        )
        
        self.cache_entries[cache_key] = cache_entry
        
        # Cleanup old cache entries if needed
        if len(self.cache_entries) > self.max_cache_entries:
            # Keep only the most recently used entries
            sorted_entries = sorted(self.cache_entries.items(), key=lambda x: x[1].last_hit)
            excess_count = len(self.cache_entries) - self.max_cache_entries
            for key, _ in sorted_entries[:excess_count]:
                del self.cache_entries[key]
        
        progress_log(f"💾 Cached {agent_type} result: {cache_key}")
    
    def find_similar_cache(self, query: str, agent_type: str) -> Optional[Dict[str, Any]]:
        """Find semantically similar cached results using LLM."""
        best_match = None
        best_similarity = 0.0
        
        for cache_entry in self.cache_entries.values():
            if cache_entry.agent_type != agent_type:
                continue
                
            if not cache_entry.context_summary:
                continue
            
            # Use LLM to calculate semantic similarity with cached context
            similarity = self.calculate_llm_similarity(query, cache_entry.context_summary)
            
            # Use higher threshold for cache hits (0.6) since we want precise matches
            if similarity >= 0.6 and similarity > best_similarity:
                best_similarity = similarity
                best_match = cache_entry
        
        if best_match:
            best_match.hit_count += 1
            best_match.last_hit = datetime.now().isoformat()
            progress_log(f"💾 Semantic cache hit for {agent_type} (similarity: {best_similarity:.2f})")
            return best_match.result_data
        
        return None
    
    def generate_cache_key(self, agent_type: str, context: Dict[str, Any]) -> str:
        """Generate cache key for agent context."""
        # Create a stable hash from the context
        context_str = json.dumps(context, sort_keys=True)
        hash_obj = hashlib.md5(context_str.encode())
        return f"{agent_type}_{hash_obj.hexdigest()[:12]}"
    
    
    def _load_memory_from_disk(self):
        """Load semantic memory from disk."""
        memory_file = self.session_dir / "semantic_memory.json"
        if memory_file.exists():
            try:
                with open(memory_file, 'r') as f:
                    memory_data = json.load(f)
                
                for entry_data in memory_data:
                    entry = SemanticMemoryEntry(**entry_data)
                    self.memory_entries.append(entry)
                
                progress_log(f"📚 Loaded {len(self.memory_entries)} semantic memories")
            except Exception as e:
                error_log(f"❌ Failed to load semantic memory: {e}")
    
    def _load_cache_from_disk(self):
        """Load cache from disk."""
        cache_file = self.session_dir / "semantic_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                for cache_key, entry_data in cache_data.items():
                    entry = CacheEntry(**entry_data)
                    self.cache_entries[cache_key] = entry
                
                progress_log(f"💾 Loaded {len(self.cache_entries)} cache entries")
            except Exception as e:
                error_log(f"❌ Failed to load cache: {e}")
    
    def save_to_disk(self):
        """Save memory and cache to disk."""
        try:
            # Save semantic memory
            memory_file = self.session_dir / "semantic_memory.json"
            memory_data = [asdict(entry) for entry in self.memory_entries]
            with open(memory_file, 'w') as f:
                json.dump(memory_data, f, indent=2)
            
            # Save cache
            cache_file = self.session_dir / "semantic_cache.json"
            cache_data = {key: asdict(entry) for key, entry in self.cache_entries.items()}
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            progress_log(f"💾 Saved semantic memory and cache to disk")
            
        except Exception as e:
            error_log(f"❌ Failed to save memory/cache: {e}")


def init_semantic_memory(config: CfConfig, session_dir: Path) -> SemanticMemorySystem:
    """Initialize semantic memory system."""
    return SemanticMemorySystem(config, session_dir)