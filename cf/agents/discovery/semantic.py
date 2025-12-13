"""
Semantic Discovery Strategies

Combines graph-based and embedding-based semantic search for file discovery.
- GraphQueryStrategy: Uses knowledge base graph queries
- SemanticSearchStrategy: Uses code embeddings for similarity search
"""

from typing import Dict, List, Any, Optional
from cf.agents.pipelines.discovery import FileCandidate
from cf.agents.discovery.base import DiscoveryStrategy
import traceback

# Import KB tool constants for robust tool resolution
try:
    from cf.agents.kb.structural_kb_agent import StructuralKBAgent, StructuralKBTools
    KB_TOOLS_AVAILABLE = True
except ImportError:
    KB_TOOLS_AVAILABLE = False
    StructuralKBTools = None


class GraphQueryStrategy(DiscoveryStrategy):
    """
    Uses structural knowledge base graph queries for file discovery.

    UPDATED: Now uses tool_registry instead of direct pipeline access.
    Enforces tool-first design pattern.
    """

    def __init__(self, config: Dict[str, Any], tool_registry):
        super().__init__(config)
        self.tool_registry = tool_registry

        # Load discovery config
        discovery_config = config.get('agents', {}).get('discovery', {})
        self.truncate_tools_display = discovery_config.get('truncate_tools_display', 30)
        self.kb_query_max_results = discovery_config.get('kb_query_max_results', 100)

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Query KB graph for relevant files using tool registry"""
        try:
            if not self.tool_registry:
                print("⚠️ [GRAPH_QUERY] Tool registry not available, skipping")
                return []

            print("🔍 [GRAPH_QUERY] Querying knowledge base via tools...")

            # Extract LLM question classification from supervisor (if available)
            question_context = context.get('question_context', {})

            # Resolve KB tool name using explicit constant (eliminates fragile dynamic resolution)
            kb_tool_name = None

            # Method 1: Use explicit constant (preferred - robust to renaming)
            if KB_TOOLS_AVAILABLE and StructuralKBTools:
                # Get prefixed tool name from StructuralKBAgent
                try:
                    # Find the KB agent instance to get proper prefix
                    agent_name = 'structural_kb'  # Default KB agent name
                    kb_tool_name = f"{agent_name}_{StructuralKBTools.FIND_FILES_FOR_QUESTION}"
                except Exception as e:
                    print(f"⚠️ [GRAPH_QUERY] Failed to resolve tool name from constant: {e}")
                    kb_tool_name = None

            # Method 2: Fallback to dynamic resolution (backward compatibility)
            if not kb_tool_name:
                try:
                    available = list(getattr(self.tool_registry, 'tools', {}).keys())
                    # Preferred exact suffix
                    candidates = [n for n in available if n.endswith('_find_files_for_question')]
                    kb_tool_name = candidates[0] if candidates else None
                except Exception:
                    kb_tool_name = None

            if not kb_tool_name:
                available = list(getattr(self.tool_registry, 'tools', {}).keys())
                print(f"⚠️ [GRAPH_QUERY] KB tool not registered. Available tools: {available[:self.truncate_tools_display]}")
                return []

            # Use resolved tool name
            result = self.tool_registry.execute(
                kb_tool_name,
                question=question,
                max_results=self.kb_query_max_results,
                question_context=question_context  # Pass LLM classification
            )

            if not result.get('success'):
                error = result.get('error', 'Unknown error')
                print(f"⚠️ [GRAPH_QUERY] KB tool failed: {error}")
                return []

            file_paths = result.get('file_paths', [])

            if not file_paths:
                print("⚠️ [GRAPH_QUERY] No files found via graph queries")
                return []

            # Convert to FileCandidate objects
            candidates = []
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            high_relevance = thresholds.get('high_relevance', 0.95)

            for file_path in file_paths:
                candidates.append(FileCandidate(
                    path=file_path,
                    relevance_score=high_relevance,  # KB queries are highly relevant
                    discovery_method="graph_query_tool",  # Updated to indicate tool usage
                    metadata={'query_type': 'structural_kb', 'via_tools': True}
                ))

            print(f"✅ [GRAPH_QUERY] Found {len(candidates)} files via KB tools")
            return candidates

        except Exception as e:
            print(f"⚠️ [GRAPH_QUERY] Failed: {e}")
            traceback.print_exc()
            return []





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



