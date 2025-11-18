"""
Query Engine for File Discovery

Extracted from StructuralPipeline to improve maintainability.
Handles all query logic and multi-strategy file discovery.
"""

import traceback
from typing import Dict, List, Any, Optional

from cf.knowledge.utils.file_classifier import FileClassifier


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
        semantic_manager,
        pattern_manager,
        execution_manager,
        config: Dict[str, Any]
    ):
        """
        Initialize query engine.

        Args:
            kb: Knowledge base instance
            repo_id: Repository ID
            repo_path: Repository path
            semantic_manager: Semantic search manager
            pattern_manager: Pattern analysis manager
            execution_manager: Execution path manager
            config: Configuration dictionary
        """
        self.kb = kb
        self.repo_id = repo_id
        self.repo_path = repo_path
        self.semantic_manager = semantic_manager
        self.pattern_manager = pattern_manager
        self.execution_manager = execution_manager
        self.config = config

        # Extract config sections
        self.semantic_config = config.get('knowledge_base', {}).get('semantic', {})
        self.patterns_config = config.get('knowledge_base', {}).get('patterns', {})
        self.lifeofx_config = config.get('knowledge_base', {}).get('lifeofx', {})

        # File classifier for validation
        self.file_classifier = FileClassifier(repo_path)

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

        semantic_search = self.semantic_manager.search
        if not semantic_search:
            return

        try:
            min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
            raw_results = semantic_search.search_by_natural_language(
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

            print(f"✅ [KB_SEMANTIC] Found {len(semantic_results)} files via semantic search")

        except Exception as e:
            print(f"⚠️ [KB_SEMANTIC] Semantic search failed: {e}")

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
                print(f"⚠️ [KB_LIFEOFX] Could not resolve entry point: {entry_point}")
                return

            print(f"✅ [KB_LIFEOFX] Resolved entry point '{entry_point}' to {len(resolved_entry_points)} function(s)")

            # Trace execution paths
            execution_tracer = self.execution_manager.execution_path_tracer
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

            print(f"✅ [KB_LIFEOFX] Found {len(all_paths)} execution paths")

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

                        if file_path and self.file_classifier.validate_file_path(file_path):
                            file_scores[file_path] = max(file_scores.get(file_path, 0), 0.9)
                            file_paths.append(file_path)
                            files_extracted += 1
                        elif file_path:
                            broken_links += 1

            if files_extracted > 0:
                print(f"✅ [KB_LIFEOFX] Extracted {files_extracted} files from execution paths")

            if broken_links > 0:
                broken_percentage = (broken_links / total_steps * 100) if total_steps > 0 else 0
                print(f"⚠️ [KB_LIFEOFX] Found {broken_links} broken links ({broken_percentage:.1f}%)")

        except Exception as e:
            print(f"⚠️ [KB_LIFEOFX] Execution tracing failed: {e}")
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
                print(f"⚠️ [QUERY_ENGINE] Failed to find dependencies for module '{module}': {e}")

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
            print(f"⚠️ [QUERY_ENGINE] Failed to find callers for function '{function_name}': {e}")

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
            print(f"⚠️ [QUERY_ENGINE] Failed to find hierarchy for class '{class_name}': {e}")

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
            question_type = question_context.get('type', 'search')
            is_pattern_question = question_type in ['pattern', 'architecture', 'class_hierarchy']

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
            design_detector = self.pattern_manager.design_pattern_detector
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

            print(f"✅ [KB_PATTERNS] Found {len(patterns)} design patterns")

        except Exception as e:
            print(f"⚠️ [KB_PATTERNS] Pattern detection failed: {e}")

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

            print(f"✅ [KB_KEYWORD] Found {len(file_paths)} files via keyword search")

        except Exception as e:
            print(f"⚠️ [QUERY_ENGINE] Keyword search failed for '{search_term}': {e}")

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

        # Fallback to simple heuristics
        question_lower = question.lower()

        # Life-of-X patterns
        if any(phrase in question_lower for phrase in ['how does', 'life of', 'flow of', 'process of']):
            entry_point_info = self._extract_entry_point(question)
            return {
                'type': 'life_of_x',
                'entry_point': entry_point_info.get('entry_point', ''),
                'term': entry_point_info.get('keywords', [question_lower])[0]
            }

        # Dependency patterns
        if 'depend' in question_lower or 'import' in question_lower:
            return {'type': 'dependency', 'modules': [], 'term': question_lower}

        # Function usage patterns
        if 'who calls' in question_lower or 'where is' in question_lower and 'used' in question_lower:
            return {'type': 'function_usage', 'function': '', 'term': question_lower}

        # Class hierarchy patterns
        if 'inherit' in question_lower or 'subclass' in question_lower or 'hierarchy' in question_lower:
            return {'type': 'class_hierarchy', 'class': '', 'term': question_lower}

        # Default: standard search
        return {'type': 'search', 'term': question_lower}

    def _extract_entry_point(self, question: str) -> Dict[str, Any]:
        """
        Extract entry point from life-of-x question.

        Args:
            question: User question

        Returns:
            Dict with entry_point and keywords
        """
        question_lower = question.lower()

        # Common entry point patterns
        patterns = [
            'student application', 'user registration', 'login', 'authentication',
            'checkout', 'payment', 'order', 'search', 'upload', 'download'
        ]

        for pattern in patterns:
            if pattern in question_lower:
                return {
                    'entry_point': pattern,
                    'keywords': pattern.split()
                }

        # Extract from "how does X work" pattern
        if 'how does' in question_lower and 'work' in question_lower:
            start = question_lower.index('how does') + len('how does')
            end = question_lower.index('work')
            entry_point = question[start:end].strip()
            return {
                'entry_point': entry_point,
                'keywords': entry_point.split()
            }

        # Default: use question as entry point
        return {
            'entry_point': question_lower,
            'keywords': question_lower.split()
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
            print(f"⚠️ [QUERY_ENGINE] File path lookup failed for {qualified_name}: {e}")

        return None
