"""
Discovery Strategies for CodeFusion
"""

from typing import Dict, List, Any, Optional
from cf.agents.pipelines.discovery import FileCandidate
from cf.agents.pipelines.discovery_strategies.discovery_strategy import DiscoveryStrategy


class FallbackStrategy(DiscoveryStrategy):
    """Fallback strategy when other strategies find nothing"""

    def __init__(self, config: Dict[str, Any], repo_tools, path_map: Dict[str, Any]):
        super().__init__(config)
        self.repo_tools = repo_tools
        self.path_map = path_map

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Use generic patterns to find files"""
        try:
            print("🔄 [FALLBACK] Using generic file discovery")

            # Get all source files from path_map
            candidates = []
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            minimal_relevance = thresholds.get('minimal_relevance', 0.5)

            # Get source code extensions from config and normalize (strip leading dot)
            repo_config = self.config.get('repo', {})
            cfg_exts = repo_config.get('source_code_extensions', [])
            source_extensions = set(e.lstrip('.').lower() for e in cfg_exts)

            for path, metadata in self.path_map.items():
                if metadata.get('is_dir'):
                    continue

                # Check if it's a source file (normalize ext without leading dot)
                ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
                if ext in source_extensions:
                    candidates.append(FileCandidate(
                        path=path,
                        relevance_score=minimal_relevance,
                        discovery_method="fallback",
                        metadata={'extension': ext}
                    ))

            # Limit to prevent overwhelming analysis
            max_fallback_files = self.config.get('agents', {}).get('max_fallback_files', 100)
            if len(candidates) > max_fallback_files:
                print(f"⚠️ [FALLBACK] Limiting to {max_fallback_files} files (found {len(candidates)})")
                candidates = candidates[:max_fallback_files]

            print(f"✅ [FALLBACK] Found {len(candidates)} source files")
            return candidates

        except Exception as e:
            print(f"⚠️ [FALLBACK] Failed: {e}")
            return []


class DiscoveryPipeline:
    """
    Main discovery pipeline that orchestrates multiple strategies
    to find relevant files for a question.

    UPDATED: Now uses tool_registry instead of direct structural_pipeline access.
    Enforces tool-first design pattern.
    """

