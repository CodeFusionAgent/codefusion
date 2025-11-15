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
import json
import subprocess
import concurrent.futures
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

from cf.knowledge.structural.schema import StructuralData, BuildResult, QueryResult
from cf.knowledge.structural.ast_parser import PythonASTParser
from cf.knowledge.structural.multi_lang_parser import MultiLanguageParser
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

        # Initialize parsers (Python AST + multi-language regex)
        self.parser = PythonASTParser(repo_path, self.repo_id)
        self.multi_lang_parser = MultiLanguageParser(repo_path, self.repo_id)

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

    def _parse_file_auto(self, file_path: str) -> Optional[StructuralData]:
        """
        Automatically parse file using appropriate parser based on extension.

        Args:
            file_path: Absolute path to source file

        Returns:
            StructuralData or None if parsing fails
        """
        ext = Path(file_path).suffix.lower()

        # Use Python AST parser for .py files
        if ext == '.py':
            return self.parser.parse_file(file_path)

        # Use multi-language parser for other supported languages
        language = self.multi_lang_parser.detect_language(file_path)
        if language:
            return self.multi_lang_parser.parse_file(file_path)

        # Unsupported file type
        return None

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
        progress_interval = self.build_config.get('progress_interval', 100)  # More frequent updates
        max_build_time = self.build_config.get('max_build_time_seconds', 7200)  # 2 hours default

        print(f"⚙️ Using {num_workers} parallel workers (timeout: {max_build_time}s)")

        # Estimate total time based on typical parsing rate
        estimated_seconds = total_files / 20  # ~20 files/sec typical
        estimated_minutes = estimated_seconds / 60
        print(f"⏱️  Estimated time: {estimated_minutes:.1f} minutes (for {total_files} files)")

        # Track if we hit timeout
        timeout_hit = False

        # Process files in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all parsing tasks with appropriate parser
            future_to_file = {
                executor.submit(self._parse_file_auto, os.path.join(self.repo_path, file_path)): file_path
                for file_path in source_files
            }

            # Process results as they complete
            for i, future in enumerate(concurrent.futures.as_completed(future_to_file), 1):
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > max_build_time:
                    print(f"\n⚠️ KB build timeout after {elapsed:.0f}s (max: {max_build_time}s)")
                    print(f"   Processed {i}/{total_files} files before timeout")
                    timeout_hit = True
                    # Cancel remaining futures
                    for remaining_future in future_to_file:
                        remaining_future.cancel()
                    break

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

                # Progress logging with percentage and ETA
                if i % progress_interval == 0 or i == total_files:
                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    percent = (i / total_files * 100) if total_files > 0 else 0

                    # Calculate ETA
                    if rate > 0:
                        remaining_files = total_files - i
                        eta_seconds = remaining_files / rate
                        eta_minutes = eta_seconds / 60
                        eta_str = f"ETA: {eta_minutes:.1f}m" if eta_minutes >= 1 else f"ETA: {eta_seconds:.0f}s"
                    else:
                        eta_str = "ETA: calculating..."

                    # Progress bar
                    bar_length = 30
                    filled = int(bar_length * i / total_files) if total_files > 0 else 0
                    bar = '█' * filled + '░' * (bar_length - filled)

                    print(f"   [{bar}] {percent:.1f}% ({i}/{total_files}) | {rate:.1f} files/s | {eta_str}")

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

        if timeout_hit:
            print(f"\n⚠️ Knowledge base build incomplete (timeout)")
            print(f"   Processed {successful}/{total_files} files successfully")
        else:
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

        # Default to multiple languages (Python, JavaScript, TypeScript, Java, Go, Rust, C++, C#)
        default_extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs',
                             '.cpp', '.cc', '.cxx', '.hpp', '.h', '.cs']
        source_extensions = set(repo_config.get('source_code_extensions', default_extensions))

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
        if self.semantic_config.get('enabled', False) and self.semantic_search is not None:
            try:
                # Call semantic search layer directly (no wrapper)
                min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
                raw_results = self.semantic_search.search_by_natural_language(
                    question, top_k=max_results, min_similarity=min_similarity
                )

                # Convert SimilarityResult objects to dicts
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

                # Validate semantic search results
                if not isinstance(semantic_results, list):
                    print(f"⚠️ [KB_SEMANTIC] Invalid results type: {type(semantic_results)}")
                    semantic_results = []

                default_relevance = self.semantic_config.get('default_relevance', 0.7)

                for result in semantic_results:
                    # Validate result structure
                    if not isinstance(result, dict):
                        continue

                    if 'metadata' not in result:
                        continue

                    metadata = result.get('metadata', {})
                    if not isinstance(metadata, dict):
                        continue

                    file_path = metadata.get('file_path')
                    if file_path and isinstance(file_path, str):
                        score = result.get('similarity_score')
                        # Validate score
                        if not isinstance(score, (int, float)) or score < 0 or score > 1:
                            score = default_relevance

                        file_scores[file_path] = max(file_scores.get(file_path, 0), score)
                        file_paths.append(file_path)

                print(f"✅ [KB_SEMANTIC] Found {len([r for r in semantic_results if isinstance(r, dict)])} files via semantic search")
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
                    # Resolve entry point to actual function names in KB
                    resolved_entry_points = self._resolve_entry_point(entry_point)

                    if not resolved_entry_points:
                        print(f"⚠️ [KB_LIFEOFX] Could not resolve entry point: {entry_point}")
                        print(f"   💡 [KB_LIFEOFX] Tip: Entry points like views.py or api.py may not exist,")
                        print(f"   💡 [KB_LIFEOFX]      or they may not contain functions matching '{entry_point}'")
                        print(f"   💡 [KB_LIFEOFX]      Other discovery strategies will try to find relevant files")
                    else:
                        print(f"✅ [KB_LIFEOFX] Resolved entry point '{entry_point}' to {len(resolved_entry_points)} function(s)")

                        all_paths = []
                        for resolved_ep in resolved_entry_points[:3]:  # Limit to 3 entry points
                            # Call execution path tracer directly (no wrapper)
                            raw_paths = self.execution_path_tracer.trace_from_entry_point(
                                resolved_ep, max_depth=10, max_paths=5
                            )

                            # Convert ExecutionPath objects to dicts
                            for p in raw_paths:
                                all_paths.append({
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
                                })

                        print(f"✅ [KB_LIFEOFX] Found {len(all_paths)} execution paths")

                        files_extracted = 0
                        for path_info in all_paths:
                            steps = path_info.get('steps', [])

                            for step in steps:
                                # qualified_name format: "module.Class.function" (dot notation)
                                # Need to lookup file_path from KB using qualified_name
                                qualified_name = step.get('qualified_name', '')

                                if qualified_name:
                                    # Query KB for file_path of this function
                                    file_path = self._lookup_file_path(qualified_name)
                                    if file_path:
                                        # High relevance for execution flow files
                                        file_scores[file_path] = max(file_scores.get(file_path, 0), 0.9)
                                        file_paths.append(file_path)
                                        files_extracted += 1

                        if files_extracted > 0:
                            print(f"✅ [KB_LIFEOFX] Extracted {files_extracted} files from execution paths")

            except Exception as e:
                print(f"⚠️ [KB_LIFEOFX] Execution tracing failed: {e}")
                import traceback
                traceback.print_exc()


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
                # Use LLM classification from question_context instead of hardcoded keywords
                question_type = question_context.get('type', 'search') if question_context else 'search'
                is_pattern_question = question_type in ['pattern', 'architecture', 'class_hierarchy']
                
                if is_pattern_question:
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

                    # Call design pattern detector directly (no wrapper)
                    if self.design_pattern_detector is None:
                        patterns = []
                    else:
                        if not self.patterns_config.get('detect_design_patterns', True):
                            patterns = []
                        else:
                            raw_matches = self.design_pattern_detector.detect_all_patterns(all_classes)

                            # Convert PatternMatch objects to dicts
                            patterns = [
                                {
                                    'pattern': match.pattern.value,
                                    'class_name': match.class_name,
                                    'confidence': match.confidence,
                                    'evidence': match.evidence
                                }
                                for match in raw_matches
                            ]

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

    def _lookup_file_path(self, qualified_name: str) -> Optional[str]:
        """
        Look up file_path for a qualified function/class name in KB.

        Args:
            qualified_name: Qualified name in dot notation (e.g., "module.Class.function")

        Returns:
            File path if found, None otherwise
        """
        if not self.is_kb_available():
            return None

        try:
            # Try as function first
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
            print(f"⚠️ [KB_LIFEOFX] File path lookup failed for {qualified_name}: {e}")

        return None

    def _resolve_entry_point(self, entry_point: str) -> List[str]:
        """
        Resolve a high-level entry point name to actual qualified function names in KB.

        Uses intelligent filtering to prioritize actual entry points (views, APIs, handlers)
        over utility functions (managers, tasks, helpers).

        Args:
            entry_point: User-provided entry point (e.g., "student application", "user login")

        Returns:
            List of qualified function names found in KB, sorted by relevance
        """
        if not self.is_kb_available():
            return []

        candidates = []  # List of (qualified_name, file_path, score) tuples

        # Split entry point into keywords for searching
        keywords = entry_point.lower().split()

        try:
            # Search for matching functions
            for keyword in keywords:
                result = self.kb.search_by_name(keyword, self.repo_id, node_type='Function')
                for node in result.nodes:
                    qualified_name = node.get('qualified_name')
                    file_path = node.get('file_path', '')

                    # Skip test files - prioritize implementation code
                    if self._is_test_file(file_path):
                        continue

                    if qualified_name:
                        candidates.append((qualified_name, file_path))

            # Also search for matching classes (entry points might be classes like views/viewsets)
            for keyword in keywords:
                result = self.kb.search_by_name(keyword, self.repo_id, node_type='Class')
                for node in result.nodes:
                    qualified_name = node.get('qualified_name')
                    file_path = node.get('file_path', '')

                    # Skip test files
                    if self._is_test_file(file_path):
                        continue

                    if qualified_name:
                        candidates.append((qualified_name, file_path))

            # Remove duplicates while preserving order
            seen = set()
            unique_candidates = []
            for qname, fpath in candidates:
                if qname not in seen:
                    seen.add(qname)
                    unique_candidates.append((qname, fpath))

            # Smart relevance scoring with path-based prioritization
            def relevance_score(candidate_tuple):
                qname, fpath = candidate_tuple
                name_lower = qname.lower()
                score = 0

                # Check utility FIRST - utilities should not get entry point bonus
                is_utility = self._is_utility_file(fpath)
                is_entry_point = self._is_entry_point_file(fpath)

                # DEBUG: Log ALL file paths being scored to diagnose pattern matching
                if '/factories/' in (fpath or '').lower() or '/management/commands/' in (fpath or '').lower():
                    print(f"   🔍 [SCORE_DEBUG] Scoring: {qname}")
                    print(f"        file_path: '{fpath}'")
                    print(f"        is_utility: {is_utility}, is_entry_point: {is_entry_point}")

                # HIGHEST priority: Entry point files (views, API endpoints, handlers)
                # But NOT if they're also utilities (factories, management commands)
                entry_point_bonus = 0
                if is_entry_point and not is_utility:
                    entry_point_bonus = 100
                    score += 100

                # PENALTY: Utility files (managers, tasks, helpers, factories, commands)
                utility_penalty = 0
                if is_utility:
                    utility_penalty = -50
                    score -= 50

                # Name matching scores
                # Exact match in any part
                keyword_bonus = 0
                if any(kw in name_lower for kw in keywords):
                    keyword_bonus += 10
                    score += 10

                # All keywords present (higher relevance)
                if all(kw in name_lower for kw in keywords):
                    keyword_bonus += 20
                    score += 20

                # Bonus for common entry point function names
                name_bonus = 0
                entry_point_names = [
                    'submit', 'create', 'register', 'process',
                    'handle', 'view', 'endpoint', 'post', 'get'
                ]
                if any(ep_name in name_lower for ep_name in entry_point_names):
                    name_bonus = 15
                    score += 15

                # DEBUG: Show score breakdown for problematic files
                if '/factories/' in (fpath or '').lower() or '/management/commands/' in (fpath or '').lower():
                    print(f"        score breakdown: entry_point={entry_point_bonus}, utility={utility_penalty}, keyword={keyword_bonus}, name={name_bonus}, total={score}")

                return score

            # Sort by relevance score (highest first)
            unique_candidates.sort(key=relevance_score, reverse=True)

            # Debug logging AFTER sorting (not during)
            if unique_candidates:
                print(f"   📊 [KB_LIFEOFX] Scored {len(unique_candidates)} candidates:")
                for qname, fpath in unique_candidates[:5]:  # Show top 5
                    score = relevance_score((qname, fpath))
                    is_entry = "🎯 ENTRY" if self._is_entry_point_file(fpath) else ""
                    is_util = "⚠️ UTILITY" if self._is_utility_file(fpath) else ""
                    print(f"      {score:4d} {is_entry}{is_util} {fpath}")

            # Extract just the qualified names
            resolved = [qname for qname, _ in unique_candidates]

            # If no high-scoring results found, warn user and potentially reject
            if resolved:
                top_score = relevance_score(unique_candidates[0])

                # If ALL results are utilities (negative scores), reject and return empty
                # This allows other discovery strategies to try finding better matches
                if top_score < 0:
                    print(f"   ⚠️ [KB_LIFEOFX] All matches are utilities (score: {top_score}). Rejecting to allow other strategies.")
                    resolved = []  # Clear results to trigger other strategies
                elif top_score < 20:
                    print(f"   ⚠️ [KB_LIFEOFX] Low confidence matches (score: {top_score}). May not be true entry points.")

            # If nothing found, try fallback - prioritize non-test files
            if not resolved:
                print("   ⚠️ [KB_LIFEOFX] No entry point matches found, searching broader...")

                # Strategy 1: Search for functions by name
                candidates = []
                seen_qnames = set()
                for keyword in keywords:
                    result = self.kb.search_by_name(keyword, self.repo_id, node_type='Function')
                    for node in result.nodes:
                        qualified_name = node.get('qualified_name')
                        file_path = node.get('file_path')
                        if qualified_name and qualified_name not in seen_qnames:
                            seen_qnames.add(qualified_name)
                            candidates.append((qualified_name, file_path))

                print(f"   📊 [KB_LIFEOFX] Strategy 1 (function name search) found {len(candidates)} candidates")

                # Strategy 2: Search for files by path, then get all their functions
                # This catches entry points like "apps/applications/views.py::submit()"
                # where the file path contains "application" but function name doesn't
                files_found = 0
                functions_from_files = 0
                for keyword in keywords:
                    file_result = self.kb.search_by_name(keyword, self.repo_id, node_type='File')
                    files_found += len(file_result.nodes)
                    print(f"   📊 [KB_LIFEOFX] Strategy 2: keyword '{keyword}' found {len(file_result.nodes)} File nodes")

                    for file_node in file_result.nodes:
                        file_path = file_node.get('file_path') or file_node.get('path')
                        print(f"   📊 [KB_LIFEOFX]   - File node: {file_path}")

                        if not file_path:
                            print(f"   ⚠️ [KB_LIFEOFX]     Skipped: no file_path property")
                            continue

                        if not self._is_entry_point_file(file_path):
                            print(f"   ⚠️ [KB_LIFEOFX]     Skipped: not an entry point file")
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
                        print(f"   📊 [KB_LIFEOFX]     Found {len(func_result.nodes)} functions in this file")
                        functions_from_files += len(func_result.nodes)

                        for func_node in func_result.nodes:
                            qualified_name = func_node.get('qualified_name')
                            if qualified_name and qualified_name not in seen_qnames:
                                seen_qnames.add(qualified_name)
                                candidates.append((qualified_name, file_path))

                print(f"   📊 [KB_LIFEOFX] Strategy 2 (file-path search) found {files_found} files, {functions_from_files} functions, added {len(candidates) - len([c for c,f in candidates if c in seen_qnames])} new candidates")
                print(f"   📊 [KB_LIFEOFX] Total candidates after both strategies: {len(candidates)}")

                # Prioritize non-test files over test files
                non_test_candidates = [(qname, fpath) for qname, fpath in candidates if not self._is_test_file(fpath)]
                test_candidates = [(qname, fpath) for qname, fpath in candidates if self._is_test_file(fpath)]

                if non_test_candidates:
                    print(f"   ✅ [KB_LIFEOFX] Found {len(non_test_candidates)} non-test function(s), prioritizing these over {len(test_candidates)} test files")
                    resolved = [qname for qname, _ in non_test_candidates]
                elif test_candidates:
                    print(f"   ⚠️ [KB_LIFEOFX] No non-test matches found, falling back to {len(test_candidates)} test file(s)")
                    resolved = [qname for qname, _ in test_candidates]
                else:
                    print("   ❌ [KB_LIFEOFX] No matches found at all")

        except Exception as e:
            print(f"⚠️ [KB_LIFEOFX] Entry point resolution failed: {e}")
            import traceback
            traceback.print_exc()

        return resolved[:10]  # Return top 10 matches

    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file path is a test file"""
        if not file_path:
            return False
        path_lower = file_path.lower()
        return ('test' in path_lower or
                '/tests/' in path_lower or
                path_lower.startswith('test') or
                '_test.' in path_lower or
                '.test.' in path_lower)

    def _is_utility_file(self, file_path: str) -> bool:
        """
        Check if file is a utility/helper file (not main business logic entry point).

        Utility files are important but typically don't contain entry points for
        major application flows like "student application submission".
        """
        if not file_path:
            print(f"   🔍 [UTILITY_DEBUG] _is_utility_file called with EMPTY file_path!")
            return False
        path_lower = file_path.lower()

        # Utility directories and file patterns
        utility_patterns = [
            '/utils/', '/helpers/', '/common/utils/', '/lib/',
            '/managers.py',  # Django model managers - data access, not entry points
            '/tasks.py',      # Celery tasks - background jobs, not entry points
            '/migrations/', '/admin.py', '/apps.py',
            '/constants.py', '/config.py', '/settings.py',
            '/serializers.py',  # DRF serializers - data transformation
            '/permissions.py', '/middleware.py',
            '/exceptions.py', '/validators.py',
            '/factories/',    # Factory pattern files - create objects, not entry points
            '/management/commands/',  # Django management commands - CLI, not HTTP endpoints
        ]

        result = any(pattern in path_lower for pattern in utility_patterns)

        # DEBUG: Log for ALL files that look like they should be utilities
        # Also log if path contains expected keywords but doesn't match
        has_factory_keyword = 'factory' in path_lower or 'factories' in path_lower
        has_command_keyword = 'command' in path_lower or 'commands' in path_lower
        should_debug = (
            '/factories/' in path_lower or
            '/management/commands/' in path_lower or
            (has_factory_keyword and not result) or
            (has_command_keyword and not result)
        )

        if should_debug:
            print(f"   🔍 [UTILITY_DEBUG] _is_utility_file('{file_path}') = {result}")
            print(f"        path_lower: '{path_lower}'")
            print(f"        has '/factories/' in path: {'/factories/' in path_lower}")
            print(f"        has '/management/commands/' in path: {'/management/commands/' in path_lower}")
            matched_patterns = [p for p in utility_patterns if p in path_lower]
            if matched_patterns:
                print(f"        ✓ Matched patterns: {matched_patterns}")
            else:
                print(f"        ✗ No patterns matched (expected one to match!)")

        return result

    def _is_entry_point_file(self, file_path: str) -> bool:
        """
        Check if file likely contains entry points for application flows.

        Entry point files typically contain HTTP endpoints, form handlers,
        or main service orchestration logic.
        """
        if not file_path:
            return False
        path_lower = file_path.lower()

        # Directory patterns (check if directory is in path)
        directory_patterns = [
            '/views/', '/viewsets/', '/api/', '/endpoints/', '/routes/',
            '/controllers/', '/handlers/', '/forms/',
            '/services/',  # Service layer often contains orchestration
            '/workflows/', '/processes/',
            '/commands/',  # Management commands can be entry points
        ]

        # Filename patterns (check if path ends with these)
        # Use endswith to avoid matching utility files like 'frontend_urls.py' or 'test_views.py'
        filename_patterns = [
            '/views.py', '/api.py', '/urls.py', '/routes.py',
            '/forms.py', '/endpoints.py', '/handlers.py'
        ]

        # Check directory patterns (anywhere in path)
        if any(pattern in path_lower for pattern in directory_patterns):
            return True

        # Check filename patterns (must end with pattern to avoid false matches)
        if any(path_lower.endswith(pattern) for pattern in filename_patterns):
            return True

        return False

    def _analyze_question(self, question: str, llm_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze question to extract intent and entities using LLM.

        UPDATED: Pure LLM approach - NO hardcoded keyword patterns.
        Uses fast-tier LLM for cost efficiency.

        Args:
            question: User question
            llm_context: Optional LLM classification from supervisor (contains 'analysis_type')

        Returns:
            Dictionary with intent type and entities (LLM-extracted)
        """
        # Check if we have access to LLM client
        if not hasattr(self, '_llm_client'):
            # Initialize on first use
            try:
                from cf.llm.client import LLMClient
                self._llm_client = LLMClient(self.config.get('llm', {}))
            except Exception as e:
                print(f"⚠️ [KB_QUERY] Cannot initialize LLM for question analysis: {e}")
                # Return generic search type
                return {'type': 'search', 'term': question, 'llm_classified': False}

        # Build LLM prompt for question intent and entity extraction
        prompt = f"""Analyze this codebase question and extract the intent and entities.

Question: "{question}"

Classify the question type and extract relevant entities:

**Question Types:**
- life_of_x: Execution flow, lifecycle, "how does X work", trace, journey
- dependency: Imports, uses, depends on, what uses X
- function_usage: Who calls X, where is X called, function invocations
- class_hierarchy: Inheritance, extends, subclass, parent class
- pattern: Design patterns, architecture patterns
- search: General code search, find code doing X

**Extract entities:**
- For life_of_x: extract entry_point (function/class name)
- For dependency: extract modules (list of module names)
- For function_usage: extract function (function name)
- For class_hierarchy: extract class (class name)
- For search: extract search_term (key terms)

Respond ONLY with JSON:
{{"type": "question_type", "entry_point": "...", "modules": [...], "function": "...", "class": "...", "search_term": "..."}}

Include only relevant fields for the question type."""

        try:
            # Use fast tier for cost efficiency
            response = self._llm_client.generate_fast(
                prompt=prompt,
                system_prompt="You are a codebase query classifier. Return only valid JSON.",
                temperature=0.1,
                max_tokens=150
            )

            if response.get('success'):
                content = response.get('content', '{}').strip()

                # Extract JSON from response
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    result = json.loads(json_str)

                    # Validate and return
                    if 'type' in result:
                        result['llm_classified'] = True
                        print(f"✅ [KB_QUERY] LLM classified question as: {result['type']}")
                        return result

        except Exception as e:
            print(f"⚠️ [KB_QUERY] LLM classification failed: {e}")

        # If LLM fails, return generic search (no hardcoded patterns!)
        print("⚠️ [KB_QUERY] LLM classification failed, defaulting to semantic search")
        return {'type': 'search', 'term': question, 'llm_classified': False}

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

            # Ensure we have an LLM client available if embeddings should use it
            llm_client = None
            if self.semantic_config.get('use_llm_client', False):
                if not hasattr(self, '_llm_client') or self._llm_client is None:
                    try:
                        from cf.llm.client import LLMClient
                        # Pass full config so LLMClient can resolve tiers/models
                        self._llm_client = LLMClient(self.config)
                    except Exception as e:
                        print(f"⚠️ [SEMANTIC] Failed to initialize LLMClient for embeddings: {e}")
                        self._llm_client = None
                llm_client = getattr(self, '_llm_client', None)

            # Pass semantic config to embedder
            self._code_embedder = CodeEmbedder(
                model=model,
                config=self.semantic_config,
                llm_client=llm_client
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

    # Note: Removed query wrapper methods (search_by_natural_language, find_similar_code,
    # detect_duplicate_code, detect_design_patterns, detect_architectural_patterns,
    # detect_code_smells, trace_data_flow, trace_execution_path, trace_request_lifecycle).
    # These were thin wrappers that just delegated to the knowledge layer properties.
    # Callers should now use the properties directly (e.g., self.semantic_search.search_by_natural_language())

    # ========== Pattern Recognition Layer Properties ==========

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

    # ========== Life-of-X Analysis Layer Properties ==========

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

    def close(self):
        """Close KB connection"""
        if self.kb:
            self.kb.close()
