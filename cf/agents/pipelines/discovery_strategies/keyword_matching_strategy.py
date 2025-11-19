"""
Discovery Strategies for CodeFusion
"""

from typing import Dict, List, Any, Optional
from cf.agents.pipelines.discovery import FileCandidate
from cf.agents.pipelines.discovery_strategies.discovery_strategy import DiscoveryStrategy


class KeywordMatchingStrategy(DiscoveryStrategy):
    """Finds directories by keyword matching"""

    def __init__(self, config: Dict[str, Any], path_map: Dict[str, Any]):
        super().__init__(config)
        self.path_map = path_map

        # Load discovery config
        discovery_config = config.get('agents', {}).get('discovery', {})
        self.max_matched_dirs_return = discovery_config.get('max_matched_dirs_return', 5)

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Match keywords from question to directory names"""
        try:
            # Extract keywords from question
            question_lower = question.lower()
            words = [w.strip('?.,!:;') for w in question_lower.split()]
            min_len = self.config.get('agents', {}).get('thresholds', {}).get('min_keyword_length', 4)
            keywords = [w for w in words if len(w) > min_len]

            if not keywords:
                return []

            # Get all directories
            all_dirs = set()
            for path, metadata in self.path_map.items():
                if metadata.get('is_dir'):
                    all_dirs.add(path)

            # Score directories by keyword match quality
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            score_exact = thresholds.get('score_exact_match', 100)
            score_partial = thresholds.get('score_partial_match', 50)
            score_plural = thresholds.get('score_plural_match', 80)
            score_substring = thresholds.get('score_substring_match', 30)

            scored_dirs = []
            for dir_path in all_dirs:
                dir_name = dir_path.rstrip('/').split('/')[-1].lower()
                score = 0

                # Check each keyword
                for keyword in keywords:
                    # Exact match (highest score)
                    if keyword == dir_name:
                        score += score_exact
                    # Directory name contains keyword
                    elif keyword in dir_name:
                        score += score_partial
                    # Keyword is pluralized version or vice versa
                    elif (keyword + 's' == dir_name or keyword + 'es' == dir_name or
                          dir_name + 's' == keyword or dir_name + 'es' == keyword):
                        score += score_plural
                    # Partial match (keyword is substring)
                    elif keyword in dir_name or dir_name in keyword:
                        score += score_substring

                if score > 0:
                    scored_dirs.append((dir_path, score))

            # Sort by score descending
            scored_dirs.sort(key=lambda x: x[1], reverse=True)

            # Return top matches
            matched = [d[0] for d in scored_dirs[:self.max_matched_dirs_return]]

            if matched:
                print(f"🔍 [KEYWORD_MATCH] Found directories for keywords {keywords}: {matched}")
                # Store in context for domain detection
                context['keyword_matched_dirs'] = matched

            # Get files from matched directories
            candidates = []
            medium_relevance = thresholds.get('medium_relevance', 0.9)

            for dir_path in matched:
                dir_files = [path for path, meta in self.path_map.items()
                            if path.startswith(dir_path) and not meta.get('is_dir')]

                for file_path in dir_files:
                    candidates.append(FileCandidate(
                        path=file_path,
                        relevance_score=medium_relevance,
                        discovery_method="keyword_matching",
                        metadata={'directory': dir_path, 'keywords': keywords}
                    ))

            return candidates

        except Exception as e:
            print(f"⚠️ [KEYWORD_MATCH] Failed: {e}")
            return []


