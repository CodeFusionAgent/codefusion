"""
Discovery Strategies for CodeFusion
"""

from typing import Dict, List, Any, Optional
from cf.agents.pipelines.discovery import FileCandidate
from cf.agents.pipelines.discovery_strategies.discovery_strategy import DiscoveryStrategy


class GrepSearchStrategy(DiscoveryStrategy):
    """Uses grep to find files with relevant content"""

    def __init__(self, config: Dict[str, Any], repo_tools):
        super().__init__(config)
        self.repo_tools = repo_tools

        # Load discovery config
        discovery_config = config.get('agents', {}).get('discovery', {})
        self.top_keywords_for_grep = discovery_config.get('top_keywords_for_grep', 3)
        self.relevance_increment = discovery_config.get('relevance_increment', 0.01)
        self.max_relevance_score = discovery_config.get('max_relevance_score', 0.9)

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Search file contents for question keywords"""
        try:
            # Extract keywords from question
            question_lower = question.lower()
            words = [w.strip('?.,!:;') for w in question_lower.split()]
            min_len = self.config.get('agents', {}).get('thresholds', {}).get('min_keyword_length', 3)
            keywords = [w for w in words if len(w) > min_len]

            if not keywords:
                return []

            # Search for each keyword
            candidates = []
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            low_relevance = thresholds.get('low_relevance', 0.7)
            grep_multiplier = thresholds.get('score_grep_multiplier', 5)

            # Limit to top keywords to avoid too many searches
            top_keywords = keywords[:self.top_keywords_for_grep]

            for keyword in top_keywords:
                try:
                    # Use search_files tool to grep for keyword
                    search_result = self.repo_tools.execute('search_files', pattern=keyword)

                    if search_result.get('success') and search_result.get('matches'):
                        matches = search_result['matches']
                        print(f"🔍 [GREP_SEARCH] Found {len(matches)} matches for '{keyword}'")

                        for match in matches:
                            file_path = match.get('file')
                            match_count = match.get('count', 1)

                            # Score based on match count
                            relevance = min(low_relevance + (match_count * self.relevance_increment), self.max_relevance_score)

                            candidates.append(FileCandidate(
                                path=file_path,
                                relevance_score=relevance,
                                discovery_method="grep_search",
                                metadata={'keyword': keyword, 'match_count': match_count}
                            ))

                except Exception as e:
                    print(f"⚠️ [GREP_SEARCH] Failed for keyword '{keyword}': {e}")
                    continue

            return candidates

        except Exception as e:
            print(f"⚠️ [GREP_SEARCH] Failed: {e}")
            return []


