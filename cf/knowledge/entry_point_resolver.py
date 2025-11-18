"""
Entry Point Resolver

Extracted from StructuralPipeline to improve maintainability.
Handles intelligent entry point resolution with scoring and filtering.
"""

import traceback
from typing import Dict, List, Any, Tuple

from cf.knowledge.utils.file_classifier import FileClassifier


class EntryPointResolver:
    """
    Resolves high-level entry points to actual function names in KB.

    Responsibilities:
    - Entry point name resolution
    - Smart relevance scoring (entry points vs utilities)
    - Path-based filtering (views, APIs, handlers prioritized)
    - Domain matching and keyword scoring
    """

    def __init__(self, kb, repo_id: str, repo_path: str, config: Dict[str, Any]):
        """
        Initialize entry point resolver.

        Args:
            kb: Knowledge base instance
            repo_id: Repository ID
            repo_path: Repository root path
            config: Configuration dictionary
        """
        self.kb = kb
        self.repo_id = repo_id
        self.repo_path = repo_path
        self.config = config

        # Load scoring configuration
        scoring_config = config.get('knowledge_base', {}).get('lifeofx', {}).get('scoring', {})
        self.entry_point_bonus = scoring_config.get('entry_point_bonus', 100)
        self.utility_penalty = scoring_config.get('utility_penalty', -50)
        self.keyword_match_bonus = scoring_config.get('keyword_match_bonus', 10)
        self.all_keywords_bonus = scoring_config.get('all_keywords_bonus', 20)
        self.entry_point_name_bonus = scoring_config.get('entry_point_name_bonus', 15)
        self.domain_match_bonus = scoring_config.get('domain_match_bonus', 50)

        # File classifier for path-based filtering
        self.file_classifier = FileClassifier(repo_path)

    def resolve(
        self,
        entry_point: str,
        domain_info: Dict[str, Any] = None
    ) -> List[str]:
        """
        Resolve a high-level entry point name to actual qualified function names in KB.

        Uses intelligent filtering to prioritize actual entry points (views, APIs, handlers)
        over utility functions (managers, tasks, helpers).

        Args:
            entry_point: User-provided entry point (e.g., "student application", "user login")
            domain_info: Optional domain information from discovery

        Returns:
            List of qualified function names found in KB, sorted by relevance
        """
        if not self.kb:
            return []

        keywords = entry_point.lower().split()

        try:
            # Search for matching functions and classes
            candidates = self._search_candidates(keywords)

            # Remove duplicates
            unique_candidates = self._deduplicate(candidates)

            # Score and sort candidates
            unique_candidates.sort(
                key=lambda c: self._calculate_relevance_score(c, keywords, domain_info),
                reverse=True
            )

            # Debug logging
            if unique_candidates:
                print(f"   📊 [ENTRY_POINT] Scored {len(unique_candidates)} candidates:")
                for qname, fpath in unique_candidates[:5]:
                    score = self._calculate_relevance_score((qname, fpath), keywords, domain_info)
                    is_entry = "🎯 ENTRY" if self.file_classifier.is_entry_point_file(fpath) else ""
                    is_util = "⚠️ UTILITY" if self.file_classifier.is_utility_file(fpath) else ""
                    print(f"      {score:4d} {is_entry}{is_util} {fpath}")

            # Extract qualified names
            resolved = [qname for qname, _ in unique_candidates]

            # Quality check: reject if all results are utilities
            if resolved:
                top_score = self._calculate_relevance_score(unique_candidates[0], keywords, domain_info)

                if top_score < 0:
                    print(f"   ⚠️ [ENTRY_POINT] All matches are utilities (score: {top_score}). Rejecting.")
                    resolved = []
                elif top_score < 20:
                    print(f"   ⚠️ [ENTRY_POINT] Low confidence matches (score: {top_score}).")

            # Fallback: broader search if nothing found
            if not resolved:
                resolved = self._fallback_search(keywords, domain_info)

            return resolved[:10]  # Return top 10

        except Exception as e:
            print(f"⚠️ [ENTRY_POINT] Resolution failed: {e}")
            traceback.print_exc()
            return []

    def _search_candidates(self, keywords: List[str]) -> List[Tuple[str, str]]:
        """Search for candidate functions and classes"""
        candidates = []

        # Search functions
        for keyword in keywords:
            result = self.kb.search_by_name(keyword, self.repo_id, node_type='Function')
            for node in result.nodes:
                qualified_name = node.get('qualified_name')
                file_path = node.get('file_path', '')

                # Skip test files
                if self.file_classifier.is_test_file(file_path):
                    continue

                if qualified_name:
                    candidates.append((qualified_name, file_path))

        # Search classes
        for keyword in keywords:
            result = self.kb.search_by_name(keyword, self.repo_id, node_type='Class')
            for node in result.nodes:
                qualified_name = node.get('qualified_name')
                file_path = node.get('file_path', '')

                # Skip test files
                if self.file_classifier.is_test_file(file_path):
                    continue

                if qualified_name:
                    candidates.append((qualified_name, file_path))

        return candidates

    def _deduplicate(self, candidates: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Remove duplicate candidates"""
        seen = set()
        unique = []

        for qname, fpath in candidates:
            if qname not in seen:
                seen.add(qname)
                unique.append((qname, fpath))

        return unique

    def _calculate_relevance_score(
        self,
        candidate: Tuple[str, str],
        keywords: List[str],
        domain_info: Dict[str, Any] = None
    ) -> int:
        """
        Calculate relevance score for a candidate.

        Scoring factors:
        - Entry point files: +100
        - Utility files: -50
        - Keyword match: +10 per keyword
        - All keywords: +20
        - Entry point names (submit, handle, etc.): +15
        - Domain match: +50
        """
        qname, fpath = candidate
        name_lower = qname.lower()
        score = 0

        # Check file type
        is_utility = self.file_classifier.is_utility_file(fpath)
        is_entry_point = self.file_classifier.is_entry_point_file(fpath)

        # Entry point bonus (but not for utilities)
        if is_entry_point and not is_utility:
            score += self.entry_point_bonus

        # Utility penalty
        if is_utility:
            score += self.utility_penalty  # Already negative

        # Keyword matching
        if any(kw in name_lower for kw in keywords):
            score += self.keyword_match_bonus

        # All keywords present
        if all(kw in name_lower for kw in keywords):
            score += self.all_keywords_bonus

        # Common entry point function names
        entry_point_names = [
            'submit', 'create', 'register', 'process',
            'handle', 'view', 'endpoint', 'post', 'get'
        ]
        if any(ep_name in name_lower for ep_name in entry_point_names):
            score += self.entry_point_name_bonus

        # Domain matching
        if domain_info and fpath:
            target_dirs = domain_info.get('target_directories', [])
            fpath_lower = fpath.lower()

            for target_dir in target_dirs:
                dir_keyword = target_dir.rstrip('/').lower()
                if dir_keyword and dir_keyword in fpath_lower:
                    score += self.domain_match_bonus
                    break

        return score

    def _fallback_search(
        self,
        keywords: List[str],
        domain_info: Dict[str, Any] = None
    ) -> List[str]:
        """
        Fallback search with broader strategies.

        Strategy 1: Search functions by name
        Strategy 2: Search files by path, then get their functions
        """
        print("   ⚠️ [ENTRY_POINT] No matches found, searching broader...")

        candidates = []
        seen_qnames = set()

        # Strategy 1: Function name search
        for keyword in keywords:
            result = self.kb.search_by_name(keyword, self.repo_id, node_type='Function')
            for node in result.nodes:
                qualified_name = node.get('qualified_name')
                file_path = node.get('file_path')

                if qualified_name and qualified_name not in seen_qnames:
                    seen_qnames.add(qualified_name)
                    candidates.append((qualified_name, file_path))

        print(f"   📊 [ENTRY_POINT] Strategy 1 (function name) found {len(candidates)} candidates")

        # Strategy 2: File path search
        files_found = 0
        functions_from_files = 0

        for keyword in keywords:
            file_result = self.kb.search_by_name(keyword, self.repo_id, node_type='File')
            files_found += len(file_result.nodes)

            for file_node in file_result.nodes:
                file_path = file_node.get('file_path') or file_node.get('path')

                if not file_path:
                    continue

                if not self.file_classifier.is_entry_point_file(file_path):
                    continue

                # Get all functions in this file
                func_result = self.kb.execute_query(
                    """
                    MATCH (f:Function {repo_id: $repo_id})
                    WHERE f.file_path = $file_path
                    RETURN f
                    LIMIT 20
                    """,
                    {"repo_id": self.repo_id, "file_path": file_path}
                )

                functions_from_files += len(func_result.nodes)

                for node_wrapper in func_result.nodes:
                    func_node = node_wrapper.get('f', {})
                    qualified_name = func_node.get('qualified_name')

                    if qualified_name and qualified_name not in seen_qnames:
                        seen_qnames.add(qualified_name)
                        candidates.append((qualified_name, file_path))

        print(f"   📊 [ENTRY_POINT] Strategy 2 (file path) found {files_found} files, {functions_from_files} functions")
        print(f"   📊 [ENTRY_POINT] Total candidates: {len(candidates)}")

        # Sort by score
        candidates.sort(
            key=lambda c: self._calculate_relevance_score(c, keywords, domain_info),
            reverse=True
        )

        # Log top candidates
        if candidates:
            print(f"   📊 [ENTRY_POINT_FALLBACK] Scored {len(candidates)} candidates:")
            for qname, fpath in candidates[:5]:
                score = self._calculate_relevance_score((qname, fpath), keywords, domain_info)
                is_entry = "🎯 ENTRY" if self.file_classifier.is_entry_point_file(fpath) else ""
                is_util = "⚠️ UTILITY" if self.file_classifier.is_utility_file(fpath) else ""
                print(f"      {score:4d} {is_entry}{is_util} {fpath}")

        # Prioritize non-test, non-utility files
        non_test = [(qn, fp) for qn, fp in candidates if not self.file_classifier.is_test_file(fp)]
        test_only = [(qn, fp) for qn, fp in candidates if self.file_classifier.is_test_file(fp)]

        # Filter out negative scores (utilities)
        non_test_non_utility = [
            (qn, fp) for qn, fp in non_test
            if self._calculate_relevance_score((qn, fp), keywords, domain_info) >= 0
        ]

        if non_test_non_utility:
            print(f"   ✅ [ENTRY_POINT] Found {len(non_test_non_utility)} non-test, non-utility functions")
            return [qn for qn, _ in non_test_non_utility]
        elif non_test:
            print(f"   ⚠️ [ENTRY_POINT] Found {len(non_test)} non-test functions (all utilities)")
            return [qn for qn, _ in non_test]
        elif test_only:
            print(f"   ⚠️ [ENTRY_POINT] Falling back to {len(test_only)} test file functions")
            return [qn for qn, _ in test_only]
        else:
            print("   ❌ [ENTRY_POINT] No matches found")
            return []
