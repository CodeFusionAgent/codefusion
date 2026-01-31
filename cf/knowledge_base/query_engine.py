"""
Query Engine for File Discovery

Extracted from StructuralPipeline to improve maintainability.
Handles all query logic and multi-strategy file discovery.
"""

import os
import traceback
from typing import Dict, List, Any, Optional, Tuple

from cf.utils.logger import get_logger
from cf.knowledge_base import kb_orchestrator

logger = get_logger(__name__)


class QueryEngine:
    """
    Manages query processing and multi-strategy file discovery.

    Responsibilities:
    - Question analysis and intent extraction
    - Multi-strategy file discovery (semantic, patterns, execution tracing)
    - Result scoring and ranking
    - Integration with KB layers (semantic, pattern, execution)
    """

    def __init__(
        self,
        kb,
        repo_id: str,
        repo_path: str,
        semantic_search,
        pattern_detectors,
        execution_path_tracers,
        config: Dict[str, Any]
    ):
        """
        Initialize query engine.

        Args:
            kb: Knowledge base instance
            repo_id: Repository ID
            repo_path: Repository path
            semantic_search: Semantic search instance (or None if disabled)
            pattern_detectors: Pattern detectors instance (or None if disabled)
            execution_path_tracers: Execution path tracers instance (or None if disabled)
            config: Configuration dictionary
        """
        self.kb = kb
        self.repo_id = repo_id
        self.repo_path = repo_path
        self.semantic_search = semantic_search
        self.pattern_detectors = pattern_detectors
        self.execution_path_tracers = execution_path_tracers
        self.config = config

        # Extract config sections
        self.semantic_config = config.get('knowledge_base', {}).get('semantic', {})
        self.patterns_config = config.get('knowledge_base', {}).get('patterns', {})
        self.lifeofx_config = config.get('knowledge_base', {}).get('lifeofx', {})

        # Load scoring configuration for entry point resolution
        scoring_config = config.get('knowledge_base', {}).get('lifeofx', {}).get('scoring', {})
        self.entry_point_bonus = scoring_config.get('entry_point_bonus', 100)
        self.utility_penalty = scoring_config.get('utility_penalty', -50)
        self.keyword_match_bonus = scoring_config.get('keyword_match_bonus', 10)
        self.all_keywords_bonus = scoring_config.get('all_keywords_bonus', 20)
        self.domain_match_bonus = scoring_config.get('domain_match_bonus', 50)
        self.repo_path = repo_path

    def find_files(
        self,
        question: str,
        max_results: int = 50,
        question_context: Dict[str, Any] = None,
        entry_point_resolver=None
    ) -> List[str]:
        """
        Find relevant files for a question using multi-strategy approach.

        Args:
            question: User question
            max_results: Maximum files to return
            question_context: Optional LLM classification from supervisor
            entry_point_resolver: Optional entry point resolver instance

        Returns:
            List of file paths ranked by relevance
        """
        if not self.kb:
            return []

        file_paths = []
        file_scores = {}  # Track relevance scores

        # Strategy 1: Semantic Search (PRIMARY)
        self._semantic_search_strategy(question, max_results, file_paths, file_scores)

        # Strategy 2: Question Type-Specific Queries
        intent = self._analyze_question(question, llm_context=question_context)

        if intent.get('type') == 'life_of_x':
            self._life_of_x_strategy(
                intent, question_context, entry_point_resolver, file_paths, file_scores
            )
        elif intent.get('type') == 'dependency':
            self._dependency_strategy(intent, file_paths, file_scores)
        elif intent.get('type') == 'function_usage':
            self._function_usage_strategy(intent, file_paths, file_scores)
        elif intent.get('type') == 'class_hierarchy':
            self._class_hierarchy_strategy(intent, file_paths, file_scores)

        # Strategy 3: Pattern-Based Discovery
        if question_context:
            self._pattern_strategy(question_context, file_paths, file_scores)

        # Strategy 4: Fallback Keyword Search
        if not file_paths:
            self._keyword_search_strategy(intent, file_paths, file_scores)

        # Remove duplicates and rank by score
        unique_files = list(dict.fromkeys(file_paths))
        ranked_files = sorted(
            unique_files,
            key=lambda f: file_scores.get(f, 0.5),
            reverse=True
        )

        return ranked_files[:max_results]

    def _semantic_search_strategy(
        self,
        question: str,
        max_results: int,
        file_paths: List[str],
        file_scores: Dict[str, float]
    ):
        """Execute semantic search strategy"""
        if not self.semantic_config.get('enabled', False):
            return

        if not self.semantic_search:
            return

        try:
            min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
            raw_results = self.semantic_search.search_by_natural_language(
                question, top_k=max_results, min_similarity=min_similarity
            )

            # Convert results
            semantic_results = [
                {
                    'element_id': r.element_id,
                    'similarity_score': r.similarity_score,
                    'element_type': r.element_type,
                    'text': r.text,
                    'metadata': r.metadata
                }
                for r in raw_results
            ]

            default_relevance = self.semantic_config.get('default_relevance', 0.7)

            for result in semantic_results:
                if not isinstance(result, dict) or 'metadata' not in result:
                    continue

                metadata = result.get('metadata', {})
                if not isinstance(metadata, dict):
                    continue

                file_path = metadata.get('file_path')
                if file_path and isinstance(file_path, str):
                    score = result.get('similarity_score')
                    if not isinstance(score, (int, float)) or score < 0 or score > 1:
                        score = default_relevance

                    file_scores[file_path] = max(file_scores.get(file_path, 0), score)
                    file_paths.append(file_path)

            logger.debug(f"KB_SEMANTIC] Found {len(semantic_results)} files via semantic search")

        except Exception as e:
            logger.warning(f"KB_SEMANTIC] Semantic search failed: {e}")

    def _life_of_x_strategy(
        self,
        intent: Dict[str, Any],
        question_context: Optional[Dict[str, Any]],
        entry_point_resolver,
        file_paths: List[str],
        file_scores: Dict[str, float]
    ):
        """Execute life-of-x execution tracing strategy"""
        if not self.lifeofx_config.get('enabled', False):
            return

        entry_point = intent.get('entry_point', '')
        if not entry_point or not entry_point_resolver:
            return

        try:
            # Resolve entry point
            domain_info = question_context.get('domain_info', {}) if question_context else {}
            resolved_entry_points = entry_point_resolver.resolve(entry_point, domain_info)

            if not resolved_entry_points:
                logger.warning(f"KB_LIFEOFX] Could not resolve entry point: {entry_point}")
                return

            logger.info(f"KB_LIFEOFX] Resolved entry point '{entry_point}' to {len(resolved_entry_points)} function(s)")

            # Trace execution paths
            execution_tracer = self.execution_path_tracers.execution_path_tracer if self.execution_path_tracers else None
            if not execution_tracer:
                return

            all_paths = []
            for resolved_ep in resolved_entry_points[:3]:
                raw_paths = execution_tracer.trace_from_entry_point(
                    resolved_ep, max_depth=10, max_paths=5
                )

                for p in raw_paths:
                    all_paths.append({
                        'entry_point': p.entry_point,
                        'steps': [
                            {
                                'qualified_name': s.qualified_name,
                                'metadata': s.metadata
                            }
                            for s in p.steps
                        ]
                    })

            logger.debug(f"KB_LIFEOFX] Found {len(all_paths)} execution paths")

            # Extract files from execution paths
            files_extracted = 0
            broken_links = 0
            total_steps = 0

            for path_info in all_paths:
                for step in path_info.get('steps', []):
                    qualified_name = step.get('qualified_name', '')
                    total_steps += 1

                    if qualified_name:
                        file_path = self._lookup_file_path(qualified_name)

                        if file_path and os.path.isfile(os.path.join(self.repo_path, file_path) if self.repo_path else file_path):
                            file_scores[file_path] = max(file_scores.get(file_path, 0), 0.9)
                            file_paths.append(file_path)
                            files_extracted += 1
                        elif file_path:
                            broken_links += 1

            if files_extracted > 0:
                logger.info(f"KB_LIFEOFX] Extracted {files_extracted} files from execution paths")

            if broken_links > 0:
                broken_percentage = (broken_links / total_steps * 100) if total_steps > 0 else 0
                logger.warning(f"KB_LIFEOFX] Found {broken_links} broken links ({broken_percentage:.1f}%)")

        except Exception as e:
            logger.warning(f"KB_LIFEOFX] Execution tracing failed: {e}")
            traceback.print_exc()

    def _dependency_strategy(
        self,
        intent: Dict[str, Any],
        file_paths: List[str],
        file_scores: Dict[str, float]
    ):
        """Execute dependency query strategy"""
        modules = intent.get('modules', [])
        for module in modules:
            try:
                result = self.kb.find_files_by_dependency(module, self.repo_id)
                for node in result.nodes:
                    file_path = node.get('path')
                    if file_path:
                        file_scores[file_path] = max(file_scores.get(file_path, 0), 0.85)
                        file_paths.append(file_path)
            except Exception as e:
                logger.warning(f"QUERY_ENGINE] Failed to find dependencies for module '{module}': {e}")

    def _function_usage_strategy(
        self,
        intent: Dict[str, Any],
        file_paths: List[str],
        file_scores: Dict[str, float]
    ):
        """Execute function usage query strategy"""
        function_name = intent.get('function')
        if not function_name:
            return

        try:
            result = self.kb.find_function_callers(function_name, self.repo_id)
            for node in result.nodes:
                file_path = node.get('file_path')
                if file_path:
                    file_scores[file_path] = max(file_scores.get(file_path, 0), 0.85)
                    file_paths.append(file_path)
        except Exception as e:
            logger.warning(f"QUERY_ENGINE] Failed to find callers for function '{function_name}': {e}")

    def _class_hierarchy_strategy(
        self,
        intent: Dict[str, Any],
        file_paths: List[str],
        file_scores: Dict[str, float]
    ):
        """Execute class hierarchy query strategy"""
        class_name = intent.get('class')
        if not class_name:
            return

        try:
            result = self.kb.find_class_hierarchy(class_name, self.repo_id)
            for node in result.nodes:
                file_path = node.get('file_path')
                if file_path:
                    file_scores[file_path] = max(file_scores.get(file_path, 0), 0.85)
                    file_paths.append(file_path)
        except Exception as e:
            logger.warning(f"QUERY_ENGINE] Failed to find hierarchy for class '{class_name}': {e}")

    def _pattern_strategy(
        self,
        question_context: Dict[str, Any],
        file_paths: List[str],
        file_scores: Dict[str, float]
    ):
        """Execute pattern detection strategy"""
        if not self.patterns_config.get('enabled', False):
            return

        try:
            question_type = question_context.get('type', 'search').lower()
            # Pattern-based check instead of hardcoded list
            is_pattern_question = any(
                kw in question_type for kw in ['pattern', 'architect', 'class', 'hierarchy', 'structure']
            )

            if not is_pattern_question:
                return

            # Query all classes
            query = """
            MATCH (c:Class {repo_id: $repo_id})
            RETURN c.qualified_name as name, c.file_path as file, c
            LIMIT $limit
            """
            result = self.kb.execute_query(query, {
                'repo_id': self.repo_id,
                'limit': self.patterns_config.get('max_classes_to_analyze', 500)
            })
            all_classes = [record['c'] for record in result.nodes]

            # Detect patterns
            design_detector = self.pattern_detectors.design_pattern_detector if self.pattern_detectors else None
            if not design_detector or not self.patterns_config.get('detect_design_patterns', True):
                return

            raw_matches = design_detector.detect_all_patterns(all_classes)

            patterns = [
                {
                    'pattern': match.pattern.value,
                    'class_name': match.class_name,
                    'evidence': match.evidence
                }
                for match in raw_matches
            ]

            for pattern in patterns:
                file_path = pattern.get('evidence', {}).get('file_path')
                if not file_path:
                    class_name = pattern.get('class_name')
                    if class_name:
                        query = """
                        MATCH (c:Class {repo_id: $repo_id, qualified_name: $class_name})
                        RETURN c.file_path as file_path
                        LIMIT 1
                        """
                        result = self.kb.execute_query(query, {
                            'repo_id': self.repo_id,
                            'class_name': class_name
                        })
                        if result.nodes:
                            file_path = result.nodes[0].get('file_path')

                if file_path:
                    file_scores[file_path] = max(file_scores.get(file_path, 0), 0.88)
                    file_paths.append(file_path)

            logger.debug(f"KB_PATTERNS] Found {len(patterns)} design patterns")

        except Exception as e:
            logger.warning(f"KB_PATTERNS] Pattern detection failed: {e}")

    def _keyword_search_strategy(
        self,
        intent: Dict[str, Any],
        file_paths: List[str],
        file_scores: Dict[str, float]
    ):
        """Execute keyword search fallback strategy"""
        search_term = intent.get('term', '')
        if not search_term:
            return

        try:
            # Search functions
            result = self.kb.search_by_name(search_term, self.repo_id, node_type='Function')
            for node in result.nodes:
                file_path = node.get('file_path')
                if file_path:
                    file_scores[file_path] = max(file_scores.get(file_path, 0), 0.6)
                    file_paths.append(file_path)

            # Search classes
            result = self.kb.search_by_name(search_term, self.repo_id, node_type='Class')
            for node in result.nodes:
                file_path = node.get('file_path')
                if file_path:
                    file_scores[file_path] = max(file_scores.get(file_path, 0), 0.6)
                    file_paths.append(file_path)

            logger.debug(f"KB_KEYWORD] Found {len(file_paths)} files via keyword search")

        except Exception as e:
            logger.warning(f"QUERY_ENGINE] Keyword search failed for '{search_term}': {e}")

    def _analyze_question(
        self,
        question: str,
        llm_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze question to determine intent and extract parameters.

        Uses LLM classification from supervisor if available, otherwise
        falls back to simple keyword matching.

        Args:
            question: User question
            llm_context: Optional LLM classification from supervisor

        Returns:
            Dict with type, term, entry_point, etc.
        """
        # Prefer LLM classification if available
        if llm_context and llm_context.get('analysis_type'):
            analysis_type = llm_context.get('analysis_type')

            # Map analysis type to intent
            if analysis_type == 'life_of_x':
                entry_point_info = self._extract_entry_point(question)
                return {
                    'type': 'life_of_x',
                    'entry_point': entry_point_info.get('entry_point', ''),
                    'term': entry_point_info.get('keywords', [question.lower()])[0]
                }

        # Fallback: return generic search type - LLM determines actual strategy
        return {'type': 'search', 'term': question.lower()}

    def _extract_entry_point(self, question: str) -> Dict[str, Any]:
        """
        Extract entry point from question - uses words from question as keywords.
        No hardcoded pattern matching.
        """
        # Use question words as keywords - LLM determines actual entry point
        words = question.lower().split()
        return {
            'entry_point': question.lower(),
            'keywords': words
        }

    def _lookup_file_path(self, qualified_name: str) -> Optional[str]:
        """
        Look up file path for a qualified name in KB.

        Args:
            qualified_name: Qualified function/class name

        Returns:
            File path or None
        """
        if not self.kb:
            return None

        try:
            # Try as function
            query = """
            MATCH (f:Function {repo_id: $repo_id, qualified_name: $qname})
            RETURN f.file_path as file_path
            LIMIT 1
            """
            result = self.kb.execute_query(query, {
                'repo_id': self.repo_id,
                'qname': qualified_name
            })

            if result.nodes and len(result.nodes) > 0:
                return result.nodes[0].get('file_path')

            # Try as class
            query = """
            MATCH (c:Class {repo_id: $repo_id, qualified_name: $qname})
            RETURN c.file_path as file_path
            LIMIT 1
            """
            result = self.kb.execute_query(query, {
                'repo_id': self.repo_id,
                'qname': qualified_name
            })

            if result.nodes and len(result.nodes) > 0:
                return result.nodes[0].get('file_path')

        except Exception as e:
            logger.warning(f"QUERY_ENGINE] File path lookup failed for {qualified_name}: {e}")

        return None


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
            entry_point: User-provided entry point (extracted from question)
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
                    print(f"      {score:4d} {fpath}")

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


                if qualified_name:
                    candidates.append((qualified_name, file_path))

        # Search classes
        for keyword in keywords:
            result = self.kb.search_by_name(keyword, self.repo_id, node_type='Class')
            for node in result.nodes:
                qualified_name = node.get('qualified_name')
                file_path = node.get('file_path', '')


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
        Calculate relevance score based on keyword matching.
        LLM determines actual relevance - this is for initial ordering.
        """
        qname, fpath = candidate
        name_lower = qname.lower()
        score = 0

        # Keyword matching from question
        if any(kw in name_lower for kw in keywords):
            score += self.keyword_match_bonus

        # All keywords present
        if all(kw in name_lower for kw in keywords):
            score += self.all_keywords_bonus

        # Domain matching (if provided by LLM)
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
                print(f"      {score:4d} {fpath}")

        non_test = candidates
        test_only = []

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
        self.domain_match_bonus = scoring_config.get('domain_match_bonus', 50)
        self.repo_path = repo_path

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
            entry_point: User-provided entry point (extracted from question)
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
                    print(f"      {score:4d} {fpath}")

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


                if qualified_name:
                    candidates.append((qualified_name, file_path))

        # Search classes
        for keyword in keywords:
            result = self.kb.search_by_name(keyword, self.repo_id, node_type='Class')
            for node in result.nodes:
                qualified_name = node.get('qualified_name')
                file_path = node.get('file_path', '')


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
        Calculate relevance score based on keyword matching.
        LLM determines actual relevance - this is for initial ordering.
        """
        qname, fpath = candidate
        name_lower = qname.lower()
        score = 0

        # Keyword matching from question
        if any(kw in name_lower for kw in keywords):
            score += self.keyword_match_bonus

        # All keywords present
        if all(kw in name_lower for kw in keywords):
            score += self.all_keywords_bonus

        # Domain matching (if provided by LLM)
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
                print(f"      {score:4d} {fpath}")

        non_test = candidates
        test_only = []

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
