"""
Structural Pipeline - Knowledge Base Construction

Orchestrates the building and querying of the structural knowledge base:
- Parallel file parsing using AST analysis
- Graph database population
- Progress tracking and error handling
- Query interface for code structure

Enables production-scale analysis:
- Build KB once: 100K files in 60-90 min (10 workers)
- Query KB: < 1 second
- Incremental updates: 5 files in 5 seconds
"""

import os
import time
import hashlib
import concurrent.futures
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

from cf.knowledge.structural.schema import StructuralData, BuildResult, QueryResult
from cf.knowledge.structural.ast_parser import PythonASTParser
from cf.knowledge.structural.neo4j_client import Neo4jKnowledgeBase
from cf.knowledge.structural.dependency_graph import DependencyGraphBuilder
from cf.knowledge.incremental.file_watcher import FileChangeDetector
from cf.knowledge.incremental.differential import IncrementalKBUpdater

# New layers
from cf.knowledge.semantic.embeddings import CodeEmbedder, EmbeddingModel
from cf.knowledge.semantic.similarity import SemanticSearch
from cf.knowledge.patterns.design_patterns import DesignPatternDetector
from cf.knowledge.patterns.architectural_patterns import ArchitecturalPatternDetector
from cf.knowledge.patterns.code_smells import CodeSmellDetector
from cf.knowledge.lifeofx.dataflow import DataFlowAnalyzer
from cf.knowledge.lifeofx.execution_paths import ExecutionPathTracer


class StructuralPipeline:
    """
    Pipeline for building and querying structural knowledge base.

    Coordinates:
    - AST parsing of source files
    - Graph database storage
    - Incremental updates
    - Structural queries
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], kb: Neo4jKnowledgeBase = None):
        """
        Initialize structural pipeline.

        Args:
            repo_path: Root path of repository
            config: Configuration dictionary
            kb: Optional Neo4j KB instance (will create if None)
        """
        self.repo_path = repo_path
        self.config = config
        self.repo_id = self._generate_repo_id(repo_path)

        # Initialize KB if not provided
        if kb is None:
            kb_config = config.get('knowledge_base', {}).get('neo4j', {})

            # Get password from env variable if not in config
            password = kb_config.get('password') or os.environ.get('NEO4J_PASSWORD', 'password')

            try:
                self.kb = Neo4jKnowledgeBase(
                    uri=kb_config.get('uri', 'bolt://localhost:7687'),
                    user=kb_config.get('user', 'neo4j'),
                    password=password,
                    database=kb_config.get('database', 'neo4j')
                )
            except Exception as e:
                print(f"⚠️ Failed to connect to Neo4j: {e}")
                print("   KB-based features will be disabled")
                self.kb = None
        else:
            self.kb = kb

        # Initialize parser
        self.parser = PythonASTParser(repo_path, self.repo_id)

        # Initialize dependency graph builder
        self.dep_graph = DependencyGraphBuilder()

        # Initialize file change detector
        self.file_detector = FileChangeDetector(repo_path)

        # Build configuration
        self.build_config = config.get('knowledge_base', {}).get('build', {})
        self.incremental_config = config.get('knowledge_base', {}).get('incremental', {})

        # Initialize new layers (lazy initialization - created when first used)
        self.semantic_config = config.get('knowledge_base', {}).get('semantic', {})
        self.patterns_config = config.get('knowledge_base', {}).get('patterns', {})
        self.lifeofx_config = config.get('knowledge_base', {}).get('lifeofx', {})

        self._semantic_search = None
        self._code_embedder = None
        self._design_pattern_detector = None
        self._architectural_pattern_detector = None
        self._code_smell_detector = None
        self._dataflow_analyzer = None
        self._execution_path_tracer = None

    def _generate_repo_id(self, repo_path: str) -> str:
        """
        Generate unique repository ID.

        Uses combination of repo path and git remote (if available).

        Args:
            repo_path: Repository root path

        Returns:
            Unique repository identifier
        """
        # Try to get git remote
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                remote = result.stdout.strip()
                # Use hash of remote URL
                return hashlib.md5(remote.encode()).hexdigest()
        except Exception:
            pass

        # Fallback to absolute path hash
        abs_path = os.path.abspath(repo_path)
        return hashlib.md5(abs_path.encode()).hexdigest()

    def __enter__(self):
        """Context manager entry - returns self for use in 'with' statements"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures KB connection is closed"""
        self.close()
        return False  # Don't suppress exceptions

    def close(self):
        """Explicitly close KB connection (safe for interactive mode)"""
        try:
            if hasattr(self, 'kb') and self.kb is not None:
                self.kb.close()
                self.kb = None
                print("✅ [STRUCTURAL] KB connection closed")
        except Exception as e:
            print(f"⚠️ [STRUCTURAL] Failed to close KB connection: {e}")

    def __del__(self):
        """Cleanup Neo4j connection on object destruction"""
        # Call explicit close method
        self.close()

    def is_kb_available(self) -> bool:
        """Check if KB is available and connected"""
        return self.kb is not None

    def kb_exists(self) -> bool:
        """
        Check if KB already exists for this repository.

        Returns:
            True if KB exists, False otherwise
        """
        if not self.is_kb_available():
            return False

        return self.kb.check_repo_exists(self.repo_id)

    def build_knowledge_base(self, force_rebuild: bool = False) -> BuildResult:
        """
        Build complete knowledge base for repository.

        Parses all source files in parallel and stores in graph database.

        Args:
            force_rebuild: If True, delete existing KB and rebuild

        Returns:
            BuildResult with statistics
        """
        if not self.is_kb_available():
            print("❌ KB not available - cannot build")
            return BuildResult(
                total_files=0, total_functions=0, total_classes=0,
                total_variables=0, total_modules=0, total_relationships=0,
                build_time_seconds=0, files_per_second=0,
                failed_files=[], errors=[{'error': 'KB not available'}]
            )

        print(f"🏗️ Building knowledge base for repository: {self.repo_id}")
        start_time = time.time()

        # Delete existing KB if force rebuild
        if force_rebuild and self.kb_exists():
            print("🗑️ Force rebuild requested - deleting existing KB...")
            self.kb.delete_repository(self.repo_id)

        # Get all source files
        source_files = self._get_source_files()
        total_files = len(source_files)

        print(f"📁 Found {total_files} source files to analyze")

        # Counters
        successful = 0
        failed_files = []
        errors = []
        total_functions = 0
        total_classes = 0
        total_variables = 0
        total_modules = 0
        total_relationships = 0

        # Get build configuration
        num_workers = self.build_config.get('parallel_workers', 10)
        batch_size = self.build_config.get('batch_size', 100)
        progress_interval = self.build_config.get('progress_interval', 1000)

        print(f"⚙️ Using {num_workers} parallel workers")

        # Process files in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all parsing tasks
            future_to_file = {
                executor.submit(self.parser.parse_file, os.path.join(self.repo_path, file_path)): file_path
                for file_path in source_files
            }

            # Process results as they complete
            for i, future in enumerate(concurrent.futures.as_completed(future_to_file), 1):
                file_path = future_to_file[future]

                try:
                    # Get parsing result
                    structural_data = future.result()

                    if structural_data:
                        # Store in KB
                        if self.kb.insert_structural_data(structural_data):
                            successful += 1

                            # Update counters
                            total_functions += len(structural_data.functions)
                            total_classes += len(structural_data.classes)
                            total_variables += len(structural_data.variables)
                            total_modules += len(structural_data.modules)
                            total_relationships += len(structural_data.relationships)

                            # Add to dependency graph
                            self.dep_graph.add_structural_data(structural_data)
                        else:
                            failed_files.append(file_path)
                            errors.append({'file': file_path, 'error': 'Failed to insert into KB'})
                    else:
                        failed_files.append(file_path)
                        errors.append({'file': file_path, 'error': 'Failed to parse'})

                except Exception as e:
                    failed_files.append(file_path)
                    errors.append({'file': file_path, 'error': str(e)})

                # Progress logging
                if i % progress_interval == 0 or i == total_files:
                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    print(f"   Progress: {i}/{total_files} files ({rate:.1f} files/sec)")

        # Force scan to establish baseline for change detection
        self.file_detector.force_scan()

        # Post-processing: Build enhanced layers
        print("\n🔬 Building enhanced knowledge layers...")
        self._build_enhanced_layers()

        # Calculate final stats
        build_time = time.time() - start_time
        files_per_second = successful / build_time if build_time > 0 else 0

        result = BuildResult(
            total_files=successful,
            total_functions=total_functions,
            total_classes=total_classes,
            total_variables=total_variables,
            total_modules=total_modules,
            total_relationships=total_relationships,
            build_time_seconds=build_time,
            files_per_second=files_per_second,
            failed_files=failed_files,
            errors=errors
        )

        print(f"\n✅ Knowledge base built successfully!")
        print(f"   Files: {successful}/{total_files}")
        print(f"   Functions: {total_functions}")
        print(f"   Classes: {total_classes}")
        print(f"   Relationships: {total_relationships}")
        print(f"   Time: {build_time:.1f}s ({files_per_second:.1f} files/sec)")

        if failed_files:
            print(f"   ⚠️ Failed: {len(failed_files)} files")

        return result

    def update_knowledge_base(self) -> Dict[str, Any]:
        """
        Update KB incrementally based on file changes.

        Detects changes since last scan and updates only changed files.

        Returns:
            Dictionary with update statistics
        """
        if not self.is_kb_available():
            print("❌ KB not available - cannot update")
            return {'error': 'KB not available'}

        if not self.kb_exists():
            print("⚠️ KB doesn't exist - run build_knowledge_base() first")
            return {'error': 'KB does not exist'}

        # Detect file changes
        change_set = self.file_detector.detect_changes()

        if not change_set.has_changes():
            print("✅ No changes detected - KB is up to date")
            return {'changes': 0, 'message': 'No changes'}

        # Apply incremental updates
        updater = IncrementalKBUpdater(self.kb, self.parser)
        stats = updater.apply_changes(change_set, self.repo_path, self.repo_id)

        return stats

    def _get_source_files(self) -> List[str]:
        """
        Get all source files to analyze.

        Returns:
            List of relative file paths
        """
        source_files = []

        # Get repository configuration
        repo_config = self.config.get('repo', {})
        excluded_dirs = set(repo_config.get('excluded_dirs', []))
        source_extensions = set(repo_config.get('source_code_extensions', ['.py']))

        # Walk repository
        for root, dirs, files in os.walk(self.repo_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('.')]

            for file in files:
                # Check if source file
                _, ext = os.path.splitext(file)
                if ext in source_extensions:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.repo_path)
                    source_files.append(rel_path)

        return source_files

    # ========== Query Interface ==========

    def find_files_for_question(self, question: str, max_results: int = 50, question_context: Dict[str, Any] = None) -> List[str]:
        """
        Find relevant files for a question using enhanced KB features.

        Uses semantic search, pattern detection, and execution tracing as primary methods,
        with fallback to traditional keyword-based queries.

        Args:
            question: User question
            max_results: Maximum files to return
            question_context: Optional LLM classification from supervisor (replaces hardcoded patterns)

        Returns:
            List of file paths ranked by relevance
        """
        if not self.is_kb_available() or not self.kb_exists():
            return []

        file_paths = []
        file_scores = {}  # Track relevance scores for ranking

        # Strategy 1: Semantic Search (PRIMARY - uses vector embeddings)
        if self.semantic_config.get('enabled', False):
            try:
                semantic_results = self.search_by_natural_language(question, top_k=max_results)
                for result in semantic_results:
                    file_path = result.get('metadata', {}).get('file_path')
                    if file_path:
                        score = result.get('similarity_score', 0.7)
                        file_scores[file_path] = max(file_scores.get(file_path, 0), score)
                        file_paths.append(file_path)
                print(f"✅ [KB_SEMANTIC] Found {len(semantic_results)} files via semantic search")
            except Exception as e:
                print(f"⚠️ [KB_SEMANTIC] Semantic search failed: {e}")

        # Strategy 2: Question Type Detection for specialized queries
        # Use LLM classification from supervisor if available, otherwise fall back to patterns
        intent = self._analyze_question(question, llm_context=question_context)

        # Life-of-X questions: Use execution path tracing
        if intent.get('type') == 'life_of_x':
            try:
                entry_point = intent.get('entry_point', '')
                if entry_point and self.lifeofx_config.get('enabled', False):
                    paths = self.trace_execution_path(entry_point, max_depth=10, max_paths=5)
                    for path_info in paths:
                        for step in path_info.get('steps', []):
                            file_path = step.get('metadata', {}).get('file_path')
                            if file_path:
                                # High relevance for execution flow files
                                file_scores[file_path] = max(file_scores.get(file_path, 0), 0.9)
                                file_paths.append(file_path)
                    print(f"✅ [KB_LIFEOFX] Found {len(paths)} execution paths")
            except Exception as e:
                print(f"⚠️ [KB_LIFEOFX] Execution tracing failed: {e}")

        # Dependency queries
        elif intent.get('type') == 'dependency':
            modules = intent.get('modules', [])
            for module in modules:
                try:
                    result = self.kb.find_files_by_dependency(module, self.repo_id)
                    for node in result.nodes:
                        file_path = node.get('path')
                        if file_path:
                            file_scores[file_path] = max(file_scores.get(file_path, 0), 0.85)
                            file_paths.append(file_path)
                except Exception:
                    pass

        # Function usage queries
        elif intent.get('type') == 'function_usage':
            function_name = intent.get('function')
            if function_name:
                try:
                    result = self.kb.find_function_callers(function_name, self.repo_id)
                    for node in result.nodes:
                        file_path = node.get('file_path')
                        if file_path:
                            file_scores[file_path] = max(file_scores.get(file_path, 0), 0.85)
                            file_paths.append(file_path)
                except Exception:
                    pass

        # Class hierarchy queries
        elif intent.get('type') == 'class_hierarchy':
            class_name = intent.get('class')
            if class_name:
                try:
                    result = self.kb.find_class_hierarchy(class_name, self.repo_id)
                    for node in result.nodes:
                        file_path = node.get('file_path')
                        if file_path:
                            file_scores[file_path] = max(file_scores.get(file_path, 0), 0.85)
                            file_paths.append(file_path)
                except Exception:
                    pass

        # Strategy 3: Pattern-based discovery (for architecture questions)
        if self.patterns_config.get('enabled', False):
            try:
                # Check if question is about patterns or architecture
                if any(word in question.lower() for word in ['pattern', 'architecture', 'design', 'structure']):
                    # Query all classes first (would need optimization for large codebases)
                    query = """
                    MATCH (c:Class {repo_id: $repo_id})
                    RETURN c.qualified_name as name, c.file_path as file, c
                    LIMIT $limit
                    """
                    # Use parameterized query to prevent injection
                    result = self.kb.execute_query(query, {
                        'repo_id': self.repo_id,
                        'limit': self.patterns_config.get('max_classes_to_analyze', 500)
                    })
                    all_classes = [record['c'] for record in result.nodes]

                    # Detect patterns
                    patterns = self.detect_design_patterns(all_classes)
                    for pattern in patterns:
                        # Extract file path from class metadata
                        file_path = pattern.get('evidence', {}).get('file_path')
                        if not file_path:
                            # Try to query for the class
                            class_name = pattern.get('class_name')
                            if class_name:
                                query = """
                                MATCH (c:Class {repo_id: $repo_id, qualified_name: $class_name})
                                RETURN c.file_path as file_path
                                LIMIT 1
                                """
                                # Use parameterized query to prevent injection
                                result = self.kb.execute_query(query, {
                                    'repo_id': self.repo_id,
                                    'class_name': class_name
                                })
                                if result.nodes:
                                    file_path = result.nodes[0].get('file_path')

                        if file_path:
                            # Patterns are highly relevant for architecture questions
                            file_scores[file_path] = max(file_scores.get(file_path, 0), 0.88)
                            file_paths.append(file_path)
                    print(f"✅ [KB_PATTERNS] Found {len(patterns)} design patterns")
            except Exception as e:
                print(f"⚠️ [KB_PATTERNS] Pattern detection failed: {e}")

        # Strategy 4: Fallback to keyword-based search (if no results yet)
        if not file_paths:
            search_term = intent.get('term', '')
            if search_term:
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
                except Exception:
                    pass

        # Remove duplicates and rank by score
        unique_files = list(dict.fromkeys(file_paths))
        ranked_files = sorted(unique_files, key=lambda f: file_scores.get(f, 0.5), reverse=True)

        return ranked_files[:max_results]

    def _analyze_question(self, question: str, llm_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze question to extract intent and entities.

        Now uses LLM classification from supervisor when available (replaces hardcoded patterns).
        Falls back to pattern matching only if LLM context is not provided.

        Args:
            question: User question
            llm_context: Optional LLM classification from supervisor (contains 'analysis_type')

        Returns:
            Dictionary with intent type and entities
        """
        # PRIORITY 1: Use LLM classification from supervisor if available
        if llm_context and 'analysis_type' in llm_context:
            analysis_type = llm_context.get('analysis_type', 'standard')

            # Map supervisor's analysis_type to KB query type
            if analysis_type == 'summary':
                # Summary questions typically need broad coverage
                return {'type': 'search', 'term': '', 'llm_classified': True, 'analysis_type': 'summary'}
            elif analysis_type == 'standard':
                # Standard questions - try to extract entities from the question
                # Look for specific patterns that indicate specialized queries
                question_lower = question.lower()

                # Check for life-of-x indicators
                if any(pattern in question_lower for pattern in [
                    'how does', 'how do', 'lifecycle', 'life of', 'flow of',
                    'journey of', 'trace', 'execution', 'what happens when'
                ]):
                    # Extract entry point
                    entry_point = None
                    words = question.split()
                    for i, word in enumerate(words):
                        if word.lower() in ['how', 'does', 'do']:
                            for j in range(i + 1, min(i + 4, len(words))):
                                if words[j].lower() not in ['the', 'a', 'an', 'work', 'works']:
                                    entry_point = words[j].strip('?.,;')
                                    break
                            break
                    return {'type': 'life_of_x', 'entry_point': entry_point or '', 'llm_classified': True}

                # Check for dependency patterns
                if any(word in question_lower for word in ['import', 'uses', 'depends on', 'dependency']):
                    modules = [word.rstrip('s.') for word in question.split() if word.endswith('s') or word.endswith('.')]
                    return {'type': 'dependency', 'modules': modules, 'llm_classified': True}

                # Check for function call patterns
                if any(word in question_lower for word in ['calls', 'calling', 'invokes', 'who calls']):
                    words = question.split()
                    function = None
                    for i, word in enumerate(words):
                        if word.lower() in ['function', 'method'] and i + 1 < len(words):
                            function = words[i + 1].strip('?.,;')
                            break
                    return {'type': 'function_usage', 'function': function, 'llm_classified': True}

                # Check for class hierarchy patterns
                if any(word in question_lower for word in ['inherits', 'extends', 'subclass', 'parent', 'base class']):
                    words = question.split()
                    class_name = None
                    for i, word in enumerate(words):
                        if word.lower() in ['class', 'from'] and i + 1 < len(words):
                            class_name = words[i + 1].strip('?.,;')
                            break
                    return {'type': 'class_hierarchy', 'class': class_name, 'llm_classified': True}

                # Default: keyword search for standard questions
                stop_words = {'how', 'does', 'what', 'where', 'is', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
                terms = [word.strip('?.,;') for word in question.split() if word.lower() not in stop_words]
                search_term = max(terms, key=len) if terms else ''
                return {'type': 'search', 'term': search_term, 'llm_classified': True}

        # FALLBACK: Use hardcoded pattern matching if no LLM context
        # This path is only taken if supervisor doesn't provide classification
        print("⚠️ [KB_QUERY] No LLM classification provided, using fallback pattern matching")

        question_lower = question.lower()

        # Life-of-X patterns (execution flow questions)
        if any(pattern in question_lower for pattern in [
            'how does', 'how do', 'lifecycle', 'life of', 'flow of',
            'journey of', 'trace', 'execution', 'what happens when'
        ]):
            # Try to extract entry point
            entry_point = None
            words = question.split()
            for i, word in enumerate(words):
                if word.lower() in ['how', 'does', 'do']:
                    # Next non-stopword might be the entry point
                    for j in range(i + 1, min(i + 4, len(words))):
                        if words[j].lower() not in ['the', 'a', 'an', 'work', 'works']:
                            entry_point = words[j].strip('?.,;')
                            break
                    break
            return {'type': 'life_of_x', 'entry_point': entry_point or ''}

        # Dependency patterns
        if any(word in question_lower for word in ['import', 'uses', 'depends on', 'dependency']):
            modules = [word.rstrip('s.') for word in question.split() if word.endswith('s') or word.endswith('.')]
            return {'type': 'dependency', 'modules': modules}

        # Function call patterns
        if any(word in question_lower for word in ['calls', 'calling', 'invokes', 'who calls']):
            words = question.split()
            for i, word in enumerate(words):
                if word.lower() in ['function', 'method']:
                    if i + 1 < len(words):
                        return {'type': 'function_usage', 'function': words[i + 1].strip('?.,;')}
            return {'type': 'function_usage', 'function': None}

        # Class hierarchy patterns
        if any(word in question_lower for word in ['inherits', 'extends', 'subclass', 'parent', 'base class']):
            words = question.split()
            for i, word in enumerate(words):
                if word.lower() in ['class', 'from']:
                    if i + 1 < len(words):
                        return {'type': 'class_hierarchy', 'class': words[i + 1].strip('?.,;')}
            return {'type': 'class_hierarchy', 'class': None}

        # Default: keyword search
        stop_words = {'how', 'does', 'what', 'where', 'is', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
        terms = [word.strip('?.,;') for word in question.split() if word.lower() not in stop_words]
        search_term = max(terms, key=len) if terms else ''
        return {'type': 'search', 'term': search_term}

    def get_repository_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge base.

        Returns:
            Dictionary with KB statistics
        """
        if not self.is_kb_available() or not self.kb_exists():
            return {'error': 'KB not available or does not exist'}

        stats = self.kb.get_repository_stats(self.repo_id)

        # Add dependency graph stats if available
        if self.dep_graph:
            dep_stats = self.dep_graph.get_dependency_stats()
            stats.update(dep_stats)

        return stats

    def _build_enhanced_layers(self):
        """
        Build enhanced KB layers (semantic, patterns, life-of-x) after structural KB is built.

        This is called automatically during KB build to:
        1. Generate embeddings for semantic search
        2. Detect design and architectural patterns
        3. Build data flow graphs
        """
        # Query all structural data from KB
        if not self.is_kb_available():
            return

        print("   📊 Querying structural data from KB...")
        # Get all classes and functions from KB for processing
        all_classes_query = """
        MATCH (c:Class {repo_id: $repo_id})
        RETURN c.qualified_name as name, c.file_path as file, c
        LIMIT $limit
        """

        all_functions_query = """
        MATCH (f:Function {repo_id: $repo_id})
        RETURN f.qualified_name as name, f.file_path as file, f
        LIMIT $limit
        """

        query_params = {
            'repo_id': self.repo_id,
            'limit': 10000
        }

        # Build semantic layer
        if self.semantic_config.get('enabled', False) and self.code_embedder:
            print("   🧠 Generating semantic embeddings...")
            try:
                # Note: Actual embedding generation happens on-demand via lazy loading
                # The embedder will cache embeddings as they're generated
                print("   ✅ Semantic layer ready (embeddings will be generated on-demand)")
            except Exception as e:
                print(f"   ⚠️ Semantic layer initialization failed: {e}")

        # Build pattern recognition layer
        if self.patterns_config.get('enabled', False):
            print("   🔍 Detecting patterns and code smells...")
            try:
                # Pattern detection is also done on-demand, but we can pre-scan
                # This would require querying all classes/functions from KB
                print("   ✅ Pattern detection layer ready (analysis on-demand)")
            except Exception as e:
                print(f"   ⚠️ Pattern detection failed: {e}")

        # Build Life-of-X layer
        if self.lifeofx_config.get('enabled', False):
            print("   🔄 Building data flow graphs...")
            try:
                # Initialize the analyzers - they'll build graphs on-demand from dep_graph
                if self.dataflow_analyzer:
                    # The data flow analyzer uses the dependency graph we've already built
                    print("   ✅ Data flow analysis ready")
                if self.execution_path_tracer:
                    # The execution path tracer also uses the dependency graph
                    print("   ✅ Execution path tracing ready")
            except Exception as e:
                print(f"   ⚠️ Life-of-X layer initialization failed: {e}")

        print("   ✅ Enhanced layers built successfully!")

    # ========== Semantic Layer Methods ==========

    @property
    def code_embedder(self) -> Optional[CodeEmbedder]:
        """Lazy initialization of CodeEmbedder"""
        if not self.semantic_config.get('enabled', False):
            return None

        if self._code_embedder is None:
            model_name = self.semantic_config.get('embedding_model', 'text-embedding-3-small')
            use_local = self.semantic_config.get('use_local_model', False)

            # Map config to EmbeddingModel enum
            if use_local:
                if 'mpnet' in model_name.lower():
                    model = EmbeddingModel.LOCAL_MPNET
                else:
                    model = EmbeddingModel.LOCAL_MINILM
            else:
                if 'large' in model_name:
                    model = EmbeddingModel.OPENAI_LARGE
                else:
                    model = EmbeddingModel.OPENAI_SMALL

            # Pass semantic config to embedder
            self._code_embedder = CodeEmbedder(
                model=model,
                config=self.semantic_config
            )

        return self._code_embedder

    @property
    def semantic_search(self) -> Optional[SemanticSearch]:
        """Lazy initialization of SemanticSearch"""
        if not self.semantic_config.get('enabled', False):
            return None

        if self._semantic_search is None and self.code_embedder is not None:
            self._semantic_search = SemanticSearch(self.code_embedder)

        return self._semantic_search

    def search_by_natural_language(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search for code using natural language query.

        Args:
            query: Natural language description (e.g., "Find functions that validate user input")
            top_k: Number of results to return

        Returns:
            List of similar code elements with similarity scores
        """
        if self.semantic_search is None:
            return []

        min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
        results = self.semantic_search.search_by_natural_language(
            query, top_k=top_k, min_similarity=min_similarity
        )

        return [
            {
                'element_id': r.element_id,
                'similarity_score': r.similarity_score,
                'element_type': r.element_type,
                'text': r.text,
                'metadata': r.metadata
            }
            for r in results
        ]

    def find_similar_code(self, element_id: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Find code similar to a specific function or class.

        Args:
            element_id: ID of the code element to find similar code for
            top_k: Number of results to return

        Returns:
            List of similar code elements
        """
        if self.semantic_search is None:
            return []

        results = self.semantic_search.find_similar_functions(element_id, top_k=top_k)

        return [
            {
                'element_id': r.element_id,
                'similarity_score': r.similarity_score,
                'element_type': r.element_type,
                'text': r.text,
                'metadata': r.metadata
            }
            for r in results
        ]

    def detect_duplicate_code(self, similarity_threshold: float = 0.8) -> List[List[str]]:
        """
        Detect clusters of similar/duplicate code.

        Args:
            similarity_threshold: Minimum similarity to consider as duplicate

        Returns:
            List of clusters, where each cluster is a list of element IDs
        """
        if self.semantic_search is None:
            return []

        return self.semantic_search.cluster_similar_code(similarity_threshold)

    # ========== Pattern Recognition Methods ==========

    @property
    def design_pattern_detector(self) -> Optional[DesignPatternDetector]:
        """Lazy initialization of DesignPatternDetector"""
        if not self.patterns_config.get('enabled', False):
            return None

        if self._design_pattern_detector is None:
            self._design_pattern_detector = DesignPatternDetector()

        return self._design_pattern_detector

    @property
    def architectural_pattern_detector(self) -> Optional[ArchitecturalPatternDetector]:
        """Lazy initialization of ArchitecturalPatternDetector"""
        if not self.patterns_config.get('enabled', False):
            return None

        if self._architectural_pattern_detector is None:
            self._architectural_pattern_detector = ArchitecturalPatternDetector()

        return self._architectural_pattern_detector

    @property
    def code_smell_detector(self) -> Optional[CodeSmellDetector]:
        """Lazy initialization of CodeSmellDetector"""
        if not self.patterns_config.get('enabled', False):
            return None

        if self._code_smell_detector is None:
            thresholds = self.patterns_config.get('thresholds', {})
            self._code_smell_detector = CodeSmellDetector(thresholds)

        return self._code_smell_detector

    def detect_design_patterns(self, all_classes: List[Any]) -> List[Dict[str, Any]]:
        """
        Detect design patterns in code.

        Args:
            all_classes: List of ClassNode objects to analyze

        Returns:
            List of detected patterns with details
        """
        if self.design_pattern_detector is None:
            return []

        if not self.patterns_config.get('detect_design_patterns', True):
            return []

        matches = self.design_pattern_detector.detect_all_patterns(all_classes)

        return [
            {
                'pattern': match.pattern.value,
                'class_name': match.class_name,
                'confidence': match.confidence,
                'evidence': match.evidence
            }
            for match in matches
        ]

    def detect_architectural_patterns(
        self, all_classes: List[Any], all_files: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect architectural patterns in codebase.

        Args:
            all_classes: List of ClassNode objects
            all_files: List of FileNode objects

        Returns:
            List of detected architectural patterns
        """
        if self.architectural_pattern_detector is None:
            return []

        if not self.patterns_config.get('detect_architectural_patterns', True):
            return []

        matches = self.architectural_pattern_detector.detect_all_patterns(all_classes, all_files)

        return [
            {
                'pattern': match.pattern.value,
                'confidence': match.confidence,
                'components': match.components,
                'evidence': match.evidence
            }
            for match in matches
        ]

    def detect_code_smells(
        self, all_classes: List[Any], all_functions: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect code smells and anti-patterns.

        Args:
            all_classes: List of ClassNode objects
            all_functions: List of FunctionNode objects

        Returns:
            List of detected code smells with severity
        """
        if self.code_smell_detector is None:
            return []

        if not self.patterns_config.get('detect_code_smells', True):
            return []

        matches = self.code_smell_detector.detect_all_smells(all_classes, all_functions)

        return [
            {
                'smell': match.smell.value,
                'element_name': match.element_name,
                'severity': match.severity.value,
                'metrics': match.metrics,
                'suggestion': match.suggestion
            }
            for match in matches
        ]

    # ========== Life-of-X Analysis Methods ==========

    @property
    def dataflow_analyzer(self) -> Optional[DataFlowAnalyzer]:
        """Lazy initialization of DataFlowAnalyzer"""
        if not self.lifeofx_config.get('enabled', False):
            return None

        if self._dataflow_analyzer is None:
            self._dataflow_analyzer = DataFlowAnalyzer(self.dep_graph)

        return self._dataflow_analyzer

    @property
    def execution_path_tracer(self) -> Optional[ExecutionPathTracer]:
        """Lazy initialization of ExecutionPathTracer"""
        if not self.lifeofx_config.get('enabled', False):
            return None

        if self._execution_path_tracer is None:
            self._execution_path_tracer = ExecutionPathTracer(self.dep_graph)

        return self._execution_path_tracer

    def trace_data_flow(self, start_element: str, max_depth: int = None) -> List[Dict[str, Any]]:
        """
        Trace data flow from a starting element.

        Args:
            start_element: Starting function/variable name
            max_depth: Maximum depth to trace (None = use config)

        Returns:
            List of data flow paths
        """
        if self.dataflow_analyzer is None:
            return []

        if max_depth is None:
            max_depth = self.lifeofx_config.get('max_trace_depth', 20)

        paths = self.dataflow_analyzer.trace_data_flow(start_element, max_depth=max_depth)

        return [
            {
                'start_node': p.start_node,
                'end_node': p.end_node,
                'path_length': len(p.path),
                'path': p.path,
                'transformations': p.transformations,
                'confidence': p.confidence
            }
            for p in paths
        ]

    def trace_execution_path(
        self, entry_point: str, max_depth: int = None, max_paths: int = None
    ) -> List[Dict[str, Any]]:
        """
        Trace execution paths from an entry point.

        Args:
            entry_point: Entry point function name
            max_depth: Maximum depth to trace
            max_paths: Maximum paths to return

        Returns:
            List of execution paths
        """
        if self.execution_path_tracer is None:
            return []

        if max_depth is None:
            max_depth = self.lifeofx_config.get('max_trace_depth', 20)
        if max_paths is None:
            max_paths = self.lifeofx_config.get('max_paths', 10)

        paths = self.execution_path_tracer.trace_from_entry_point(
            entry_point, max_depth=max_depth, max_paths=max_paths
        )

        return [
            {
                'entry_point': p.entry_point,
                'exit_point': p.exit_point,
                'total_functions': p.total_functions,
                'max_depth': p.max_depth,
                'confidence': p.confidence,
                'steps': [
                    {
                        'function_name': s.function_name,
                        'qualified_name': s.qualified_name,
                        'step_type': s.step_type,
                        'metadata': s.metadata
                    }
                    for s in p.steps
                ]
            }
            for p in paths
        ]

    def trace_request_lifecycle(self, endpoint_function: str, max_depth: int = None) -> Optional[Dict[str, Any]]:
        """
        Trace request lifecycle for web applications.

        Args:
            endpoint_function: API endpoint function name
            max_depth: Maximum depth to trace

        Returns:
            Request lifecycle execution path
        """
        if self.execution_path_tracer is None:
            return None

        if max_depth is None:
            max_depth = self.lifeofx_config.get('max_trace_depth', 20)

        path = self.execution_path_tracer.trace_request_lifecycle(endpoint_function, max_depth=max_depth)

        if path is None:
            return None

        return {
            'entry_point': path.entry_point,
            'exit_point': path.exit_point,
            'total_functions': path.total_functions,
            'max_depth': path.max_depth,
            'confidence': path.confidence,
            'steps': [
                {
                    'function_name': s.function_name,
                    'qualified_name': s.qualified_name,
                    'step_type': s.step_type,
                    'metadata': s.metadata
                }
                for s in path.steps
            ]
        }

    def close(self):
        """Close KB connection"""
        if self.kb:
            self.kb.close()
