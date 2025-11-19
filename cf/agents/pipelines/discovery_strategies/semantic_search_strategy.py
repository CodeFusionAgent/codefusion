"""
Discovery Strategies for CodeFusion
"""

from typing import Dict, List, Any, Optional
from cf.agents.pipelines.discovery import FileCandidate
from cf.agents.pipelines.discovery_strategies.discovery_strategy import DiscoveryStrategy
import traceback


class SemanticSearchStrategy(DiscoveryStrategy):
    """
    Semantic similarity search strategy using code embeddings.

    NEW: Finds files based on semantic similarity rather than just keywords.
    Example: "authentication" will find "login", "credentials", "session" files.
    """

    def __init__(self, config: Dict[str, Any], kb_client=None):
        super().__init__(config)
        self.kb = kb_client

        # Load discovery config
        discovery_config = config.get('agents', {}).get('discovery', {})
        self.similarity_to_relevance_factor = discovery_config.get('similarity_to_relevance_factor', 100)

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Find files using semantic similarity search"""
        try:
            if not self.kb:
                print("⚠️ [SEMANTIC_SEARCH] KB not available, skipping")
                return []

            # Check if KB has semantic search capability
            if not hasattr(self.kb, 'semantic_search'):
                print("⚠️ [SEMANTIC_SEARCH] KB does not support semantic search")
                return []

            print("🔍 [SEMANTIC_SEARCH] Finding semantically similar files...")

            # Perform semantic search
            top_k = self.config.get('agents', {}).get('semantic_search_top_k', 20)
            results = self.kb.semantic_search(question, top_k=top_k)

            if not results:
                print("⚠️ [SEMANTIC_SEARCH] No results found")
                return []

            # Convert to FileCandidate objects
            candidates = []
            thresholds = self.config.get('agents', {}).get('thresholds', {})

            for result in results:
                # Result format: {'file_path': str, 'similarity': float, 'snippet': str}
                file_path = result.get('file_path', '')
                similarity = result.get('similarity', 0.0)

                if not file_path:
                    continue

                # Map similarity (0-1) to relevance score (0-100)
                relevance = similarity * self.similarity_to_relevance_factor

                # Only include if above minimum threshold
                min_similarity = self.config.get('agents', {}).get('min_semantic_similarity', 0.5)
                if similarity >= min_similarity:
                    candidates.append(FileCandidate(
                        path=file_path,
                        relevance_score=relevance,
                        discovery_method="semantic_search",
                        metadata={
                            'similarity': similarity,
                            'snippet': result.get('snippet', '')[:200]
                        }
                    ))

            print(f"✅ [SEMANTIC_SEARCH] Found {len(candidates)} semantically similar files")
            return candidates

        except Exception as e:
            print(f"⚠️ [SEMANTIC_SEARCH] Failed: {e}")
            traceback.print_exc()
            return []


