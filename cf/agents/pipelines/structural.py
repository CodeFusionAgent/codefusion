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

    def find_files_for_question(self, question: str, max_results: int = 50) -> List[str]:
        """
        Find relevant files for a question using KB queries.

        Analyzes question to extract intent and uses graph queries.

        Args:
            question: User question
            max_results: Maximum files to return

        Returns:
            List of file paths
        """
        if not self.is_kb_available() or not self.kb_exists():
            return []

        # Extract keywords and intent from question
        intent = self._analyze_question(question)

        file_paths = []

        # Query based on intent
        if intent.get('type') == 'dependency':
            # "How does authentication work?" -> Find files importing 'auth' modules
            modules = intent.get('modules', [])
            for module in modules:
                result = self.kb.find_files_by_dependency(module, self.repo_id)
                file_paths.extend([node['path'] for node in result.nodes])

        elif intent.get('type') == 'function_usage':
            # "What calls the login function?" -> Find callers
            function_name = intent.get('function')
            if function_name:
                result = self.kb.find_function_callers(function_name, self.repo_id)
                # Extract file paths from function nodes
                file_paths.extend([node['file_path'] for node in result.nodes if 'file_path' in node])

        elif intent.get('type') == 'class_hierarchy':
            # "What inherits from BaseModel?" -> Find class hierarchy
            class_name = intent.get('class')
            if class_name:
                result = self.kb.find_class_hierarchy(class_name, self.repo_id)
                file_paths.extend([node['file_path'] for node in result.nodes if 'file_path' in node])

        elif intent.get('type') == 'search':
            # "Find authentication code" -> Search by name
            search_term = intent.get('term', '')
            if search_term:
                # Search functions
                result = self.kb.search_by_name(search_term, self.repo_id, node_type='Function')
                file_paths.extend([node['file_path'] for node in result.nodes if 'file_path' in node])

                # Search classes
                result = self.kb.search_by_name(search_term, self.repo_id, node_type='Class')
                file_paths.extend([node['file_path'] for node in result.nodes if 'file_path' in node])

        # Remove duplicates and limit
        file_paths = list(dict.fromkeys(file_paths))[:max_results]

        return file_paths

    def _analyze_question(self, question: str) -> Dict[str, Any]:
        """
        Analyze question to extract intent and entities.

        Simple keyword-based analysis (could be enhanced with LLM).

        Args:
            question: User question

        Returns:
            Dictionary with intent type and entities
        """
        question_lower = question.lower()

        # Dependency patterns
        if any(word in question_lower for word in ['import', 'uses', 'depends on', 'dependency']):
            # Extract potential module names
            modules = []
            for word in question.split():
                if word.endswith('s') or word.endswith('.'):
                    modules.append(word.rstrip('s.'))
            return {'type': 'dependency', 'modules': modules}

        # Function call patterns
        if any(word in question_lower for word in ['calls', 'calling', 'invokes', 'who calls']):
            # Extract function name (simple heuristic)
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
        # Extract meaningful terms (filter out common words)
        stop_words = {'how', 'does', 'what', 'where', 'is', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
        terms = [word.strip('?.,;') for word in question.split() if word.lower() not in stop_words]

        # Use longest term as search term
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

    def close(self):
        """Close KB connection"""
        if self.kb:
            self.kb.close()
