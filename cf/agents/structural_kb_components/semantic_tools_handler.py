"""
Semantic Tools Handler for StructuralKBAgent

Handles all semantic search tools using vector embeddings.
"""

import time
from typing import Dict, Any, Callable
from cf.agents.protocols import KnowledgeBaseProtocol


class SemanticToolsHandler:
    """Handles semantic search tools (vector embeddings)."""

    def __init__(self, kb: KnowledgeBaseProtocol, config: Dict[str, Any], record_call_fn: Callable):
        self.kb = kb
        self.config = config
        self._record_call = record_call_fn

        # Load config defaults
        semantic_config = config.get('knowledge_base', {}).get('semantic', {})
        kb_agent_config = config.get('agents', {}).get('structural_kb_agent', {})

        self.semantic_config = semantic_config
        self.default_search_limit = kb_agent_config.get('default_search_limit', 10)
        self.default_similar_components_limit = kb_agent_config.get('default_similar_components_limit', 10)
        self.default_example_search_limit = kb_agent_config.get('default_example_search_limit', 10)
        self.duplicate_code_similarity_threshold = kb_agent_config.get('duplicate_code_similarity_threshold', 0.8)
        self.snippet_preview_length = kb_agent_config.get('snippet_preview_length', 100)

    def search_by_semantics(self, query: str, scope: str = 'all', limit: int = None) -> Dict[str, Any]:
        """Search using semantic/vector search"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            limit = limit if limit is not None else self.default_search_limit
            min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
            raw_results = self.kb.semantic_search.search_by_natural_language(
                query, top_k=limit, min_similarity=min_similarity
            )

            # Convert SimilarityResult objects to dicts
            results = [
                {
                    'element_id': r.element_id,
                    'similarity_score': r.similarity_score,
                    'element_type': r.element_type,
                    'text': r.text,
                    'metadata': r.metadata
                }
                for r in raw_results
            ]

            self._record_call(
                tokens=0,  # Would need to track embedding tokens
                time_taken=time.time() - start_time,
                error=False
            )

            return {
                'success': True,
                'results': results,
                'count': len(results),
                'query': query
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def search_by_functionality(self, description: str, limit: int = None) -> Dict[str, Any]:
        """Search by functional description (alias for semantic search)"""
        limit = limit if limit is not None else self.default_search_limit
        return self.search_by_semantics(description, scope='all', limit=limit)

    def find_similar_components(self, component_id: str, limit: int = None) -> Dict[str, Any]:
        """Find similar code components"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            limit = limit if limit is not None else self.default_similar_components_limit
            raw_results = self.kb.semantic_search.find_similar_functions(component_id, top_k=limit)

            # Convert SimilarityResult objects to dicts
            results = [
                {
                    'element_id': r.element_id,
                    'similarity_score': r.similarity_score,
                    'element_type': r.element_type,
                    'text': r.text,
                    'metadata': r.metadata
                }
                for r in raw_results
            ]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'results': results,
                'count': len(results),
                'reference_component': component_id
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def detect_duplicate_code(self, similarity_threshold: float = None) -> Dict[str, Any]:
        """Detect duplicate code"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            similarity_threshold = similarity_threshold if similarity_threshold is not None else self.duplicate_code_similarity_threshold
            clusters = self.kb.semantic_search.cluster_similar_code(similarity_threshold)

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'clusters': clusters,
                'count': len(clusters),
                'threshold': similarity_threshold
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def search_by_example(self, code_snippet: str, limit: int = None) -> Dict[str, Any]:
        """Find code similar to a given example snippet using semantic search"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            limit = limit if limit is not None else self.default_example_search_limit
            min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
            raw_results = self.kb.semantic_search.search_by_natural_language(
                code_snippet, top_k=limit, min_similarity=min_similarity
            )

            # Convert SimilarityResult objects to dicts
            results = [
                {
                    'element_id': r.element_id,
                    'similarity_score': r.similarity_score,
                    'element_type': r.element_type,
                    'text': r.text,
                    'metadata': r.metadata
                }
                for r in raw_results
            ]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'results': results,
                'count': len(results),
                'snippet': code_snippet[:self.snippet_preview_length] + '...' if len(code_snippet) > 100 else code_snippet
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}
