"""
File Summary Cache

Provides persistent caching of LLM-generated file summaries for warm starts.
Uses file path + content hash as key to detect when files change.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class FileSummaryCache:
    """Cache for file summaries to avoid redundant LLM analysis"""

    # Cache version - increment this when prompt format changes to invalidate old cache
    # Version 1: Initial implementation
    # Version 2: Added line number requirements to file analysis prompt
    # Version 3: Added external system detection, async/background task detection
    # Version 4: Enhanced domain detection with pattern hints, few-shot examples, validation
    # Version 5: Enhanced external system detection (SDK imports, client classes, service abstractions, background task integrations)
    #            Added lifecycle/flow question pattern (tasks/ + integrations/ + signals/)
    # Version 6: Added async_task_calls field + guaranteed task-following logic
    #            System now automatically analyzes task files when task calls detected
    # Version 7: Major evaluation-driven improvements (Phase 1-3 fixes):
    #            - Module structure validation (Priority 1): Re-ranks directories by file sampling + keyword matching
    #            - Auto-include companion files (Priority 2): Automatically includes utils.py/tasks.py when models.py analyzed
    #            - Enhanced integration detection (Priority 3): Proactively scans integrations/ directories for external questions
    #            - Question clarification (Priority 5): Classifies question intent before domain detection
    #            - Keyword-to-directory matching: Extracts keywords from questions and finds exact directory name matches
    #            Expected improvement: 1.4/5 → 3.4/5 grounding score
    # Version 8: Deep implementation analysis + Anti-hallucination (Post-eval improvements):
    #            PHASE 1: Deep Implementation Tracing
    #            - Read FULL file content (no 4000 char truncation) - critical for finding actual implementations
    #            - Enhanced prompt: Extract WHAT functions DO (implementation logic), not just signatures
    #            - New field: implementation_notes captures HOW the file works (algorithms, control flow)
    #            - Synthesis: Use implementation details in answers, cite actual logic from file bodies
    #            PHASE 2: Anti-hallucination Validation
    #            - Validate cited line numbers are within file bounds
    #            - Verify component names (classes/functions/constants) exist in actual content
    #            - Mark summaries with hallucination warnings if issues detected
    #            - Prevents inventing non-existent functions/classes/line numbers
    #            Target: Fix shallow analysis + hallucination causing 72% low scores (1.5-2.25/5)
    #            Expected improvement: 2.28/5 → 3.5+/5 (match Claude Code performance)
    CACHE_VERSION = 8

    def __init__(self, cache_dir: str = "cf_cache/file_summaries", ttl: int = 86400):
        """Initialize file summary cache

        Args:
            cache_dir: Directory to store cache files
            ttl: Time-to-live in seconds (default 24 hours)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0
        self.expired = 0
        self.enabled = True
        self.ttl = ttl  # Cache TTL in seconds

    def _get_file_hash(self, content: str) -> str:
        """Generate hash of file content"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _get_cache_key(self, file_path: str, content_hash: str) -> str:
        """Generate cache key from file path and content hash"""
        # Use path hash to avoid filesystem issues with long paths
        path_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
        return f"{path_hash}_{content_hash}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get path to cache file"""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, file_path: str, content: str) -> Optional[Tuple[Dict[str, Any], Dict[str, int]]]:
        """Get cached summary for file if available

        Args:
            file_path: Path to file
            content: Current file content

        Returns:
            Tuple of (summary, metrics) if cached, None otherwise
        """
        if not self.enabled:
            return None

        try:
            content_hash = self._get_file_hash(content)
            cache_key = self._get_cache_key(file_path, content_hash)
            cache_path = self._get_cache_path(cache_key)

            # Ensure cache directory exists (in case it was deleted)
            if not cache_path.parent.exists():
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.misses += 1
                return None

            if cache_path.exists():
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)

                # Verify file path matches (collision check)
                if cached_data.get('file_path') == file_path:
                    # Check cache version - invalidate if version mismatch
                    cached_version = cached_data.get('cache_version', 1)
                    if cached_version != self.CACHE_VERSION:
                        self.expired += 1
                        print(f"🔄 [FILE_CACHE] Cache version mismatch for {file_path} (cached: v{cached_version}, current: v{self.CACHE_VERSION}) - invalidating")
                        cache_path.unlink()
                        return None

                    # Check TTL - if cache entry is too old, treat as miss
                    cached_at = cached_data.get('cached_at_timestamp', 0)
                    age = time.time() - cached_at

                    if self.ttl > 0 and age > self.ttl:
                        self.expired += 1
                        print(f"⏰ [FILE_CACHE] Cache expired for {file_path} (age: {age/3600:.1f}h, TTL: {self.ttl/3600:.1f}h)")
                        # Delete expired cache file
                        cache_path.unlink()
                        return None

                    # Check if this is a fallback entry (low quality summary)
                    is_fallback = cached_data.get('is_fallback', False)
                    if is_fallback:
                        # Check if we should retry fallback entries after some time
                        fallback_retry_period = 3600  # Retry fallback entries after 1 hour
                        if age > fallback_retry_period:
                            self.expired += 1
                            print(f"🔄 [FILE_CACHE] Retrying fallback entry for {file_path} (age: {age/60:.1f}m)")
                            return None

                    self.hits += 1
                    return (cached_data.get('summary'), cached_data.get('metrics', {}))

            self.misses += 1
            return None

        except Exception as e:
            print(f"⚠️ [FILE_CACHE] Error reading cache for {file_path}: {e}")
            self.misses += 1
            return None

    def put(self, file_path: str, content: str, summary: Dict[str, Any], metrics: Dict[str, int], is_fallback: bool = False):
        """Store file summary in cache

        Args:
            file_path: Path to file
            content: File content
            summary: LLM-generated summary
            metrics: Token usage metrics
            is_fallback: True if this is a fallback summary (low quality)
        """
        if not self.enabled:
            return

        try:
            content_hash = self._get_file_hash(content)
            cache_key = self._get_cache_key(file_path, content_hash)
            cache_path = self._get_cache_path(cache_key)

            # Ensure cache directory exists before writing
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            current_time = time.time()

            cache_data = {
                'file_path': file_path,
                'content_hash': content_hash,
                'cache_version': self.CACHE_VERSION,  # Store cache version
                'summary': summary,
                'metrics': metrics,
                'cached_at_timestamp': current_time,
                'cached_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time)),
                'is_fallback': is_fallback,
                'file_mtime': str(Path(file_path).stat().st_mtime) if Path(file_path).exists() else None
            }

            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            print(f"⚠️ [FILE_CACHE] Error writing cache for {file_path}: {e}")

    def clear(self):
        """Clear all cached summaries"""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            print(f"✅ [FILE_CACHE] Cleared {len(list(self.cache_dir.glob('*.json')))} cached summaries")
        except Exception as e:
            print(f"⚠️ [FILE_CACHE] Error clearing cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hits + self.misses + self.expired
        hit_rate = self.hits / total_requests if total_requests > 0 else 0

        return {
            'hits': self.hits,
            'misses': self.misses,
            'expired': self.expired,
            'total_requests': total_requests,
            'hit_rate': hit_rate,
            'cache_size': len(list(self.cache_dir.glob("*.json")))
        }

    def enable(self):
        """Enable caching"""
        self.enabled = True

    def disable(self):
        """Disable caching"""
        self.enabled = False
