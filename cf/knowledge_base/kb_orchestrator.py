"""
Knowledge Base Client - Facade for KB Operations

Orchestrates KB building and querying using focused manager classes.

Architecture:
- kb_manager: KB lifecycle (build, update, parse)
- semantic_search: Semantic search (direct from config)
- pattern_detectors: Pattern detection (direct from config)
- execution_path_tracers: Execution paths (direct from config)
- query_engine: Query processing and file discovery
- entry_point_resolver: Entry point resolution
"""

import os
import time
import hashlib
import concurrent.futures
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from pathlib import Path

from cf.knowledge_base.schema import (
    StructuralData, BuildResult, QueryResult,
    FileNode, FunctionNode, ClassNode, ModuleNode, VariableNode,
    Relationship, RelationType
)
from cf.knowledge_base.dependency_analysis import DependencyGraphBuilder
from cf.knowledge_base.code_parser import PythonASTParser, MultiLanguageParser
from cf.llm.client import LLMClient

# Manager classes (refactored)
from cf.knowledge_base.query_engine import QueryEngine
from cf.knowledge_base.query_engine import EntryPointResolver

# Incremental update classes
from cf.knowledge_base.incremental import ChangeSet, FileChangeDetector, IncrementalKBUpdater

# Import types for property type hints
from cf.knowledge_base.semantic_search import CodeEmbedder, SemanticSearch
from cf.knowledge_base.code_analysis import (
    PatternDetectors, DesignPatternDetector, ArchitecturalPatternDetector, CodeSmellDetector,
    ExecutionPathTracers, DataFlowAnalyzer, ExecutionPathTracer
)
from neo4j import GraphDatabase, Driver

from cf.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Neo4j Database Client
# ============================================================================

class Neo4jKnowledgeBase:
    """
    Neo4j-based persistent knowledge base for code structure.

    Provides:
    - Structural node insertion (files, functions, classes)
    - Relationship management (calls, imports, inheritance)
    - Graph queries (find callers, trace dependencies)
    - Repository lifecycle (create, update, delete)
    """

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        """
        Initialize Neo4j connection.

        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            user: Database username
            password: Database password
            database: Database name (default: neo4j)
        """
        self.uri = uri
        self.user = user
        self.database = database
        self.driver: Optional[Driver] = None

        # Connect to database
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            self.driver.verify_connectivity()
            logger.debug(f"Connected to Neo4j at {uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

        # Create indexes for performance
        self._create_indexes()

    def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def _create_indexes(self):
        """Create indexes for common queries"""
        index_queries = [
            # File indexes
            "CREATE INDEX file_path IF NOT EXISTS FOR (f:File) ON (f.path)",
            "CREATE INDEX file_repo IF NOT EXISTS FOR (f:File) ON (f.repo_id)",

            # Function indexes
            "CREATE INDEX function_name IF NOT EXISTS FOR (fn:Function) ON (fn.name)",
            "CREATE INDEX function_qualified IF NOT EXISTS FOR (fn:Function) ON (fn.qualified_name)",

            # Class indexes
            "CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name)",
            "CREATE INDEX class_qualified IF NOT EXISTS FOR (c:Class) ON (c.qualified_name)",

            # Module indexes
            "CREATE INDEX module_name IF NOT EXISTS FOR (m:Module) ON (m.name)",
        ]

        with self.driver.session(database=self.database) as session:
            for query in index_queries:
                try:
                    session.run(query)
                except Exception as e:
                    # Index might already exist
                    pass

    # ========== Repository Management ==========

    def check_repo_exists(self, repo_id: str) -> bool:
        """
        Check if repository already exists in KB.

        Args:
            repo_id: Repository identifier

        Returns:
            True if repo exists, False otherwise
        """
        query = """
        MATCH (f:File {repo_id: $repo_id})
        RETURN count(f) as count
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, repo_id=repo_id)
            record = result.single()
            return record['count'] > 0 if record else False

    def delete_repository(self, repo_id: str):
        """
        Delete all data for a repository.

        Args:
            repo_id: Repository identifier
        """
        query = """
        MATCH (n {repo_id: $repo_id})
        DETACH DELETE n
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, repo_id=repo_id)
            logger.info(f"Deleted repository: {repo_id}")

    def get_repository_stats(self, repo_id: str) -> Dict[str, int]:
        """
        Get statistics for a repository.

        Args:
            repo_id: Repository identifier

        Returns:
            Dictionary with node and relationship counts
        """
        queries = {
            'files': "MATCH (f:File {repo_id: $repo_id}) RETURN count(f) as count",
            'functions': "MATCH (fn:Function)-[:CONTAINED_IN]->(:File {repo_id: $repo_id}) RETURN count(fn) as count",
            'classes': "MATCH (c:Class)-[:CONTAINED_IN]->(:File {repo_id: $repo_id}) RETURN count(c) as count",
            'relationships': "MATCH ()-[r]->() WHERE (startNode(r)).repo_id IS NOT NULL AND (startNode(r)).repo_id = $repo_id RETURN count(r) as count"
        }

        stats = {}
        with self.driver.session(database=self.database) as session:
            for key, query in queries.items():
                result = session.run(query, repo_id=repo_id)
                record = result.single()
                stats[key] = record['count'] if record else 0

        return stats

    # ========== Node Insertion ==========

    def insert_file_node(self, file_node: FileNode) -> bool:
        """
        Insert or update a file node.

        Args:
            file_node: FileNode to insert

        Returns:
            True if successful
        """
        query = """
        MERGE (f:File {path: $path, repo_id: $repo_id})
        SET f += $props
        RETURN f
        """
        props = file_node.to_dict()
        path = props.pop('path')
        repo_id = props.pop('repo_id')

        try:
            with self.driver.session(database=self.database) as session:
                def _insert(tx):
                    tx.run(query, path=path, repo_id=repo_id, props=props)
                session.execute_write(_insert)
            return True
        except Exception as e:
            logger.error(f"Failed to insert file node {file_node.path}: {e}")
            return False

    def insert_function_node(self, function: FunctionNode, file_path: str, repo_id: str) -> bool:
        """
        Insert a function node and link to file.

        Args:
            function: FunctionNode to insert
            file_path: Path to containing file
            repo_id: Repository identifier

        Returns:
            True if successful
        """
        query = """
        MATCH (f:File {path: $file_path, repo_id: $repo_id})
        MERGE (fn:Function {qualified_name: $qualified_name, repo_id: $repo_id})
        SET fn += $props
        MERGE (fn)-[:CONTAINED_IN]->(f)
        RETURN fn
        """
        props = function.to_dict()
        qualified_name = props.pop('qualified_name')

        try:
            with self.driver.session(database=self.database) as session:
                def _insert(tx):
                    tx.run(
                        query,
                        file_path=file_path,
                        repo_id=repo_id,
                        qualified_name=qualified_name,
                        props={**props, 'repo_id': repo_id}
                    )
                session.execute_write(_insert)
            return True
        except Exception as e:
            logger.error(f"Failed to insert function {function.name}: {e}")
            return False

    def insert_class_node(self, class_node: ClassNode, file_path: str, repo_id: str) -> bool:
        """
        Insert a class node and link to file.

        Args:
            class_node: ClassNode to insert
            file_path: Path to containing file
            repo_id: Repository identifier

        Returns:
            True if successful
        """
        query = """
        MATCH (f:File {path: $file_path, repo_id: $repo_id})
        MERGE (c:Class {qualified_name: $qualified_name, repo_id: $repo_id})
        SET c += $props
        MERGE (c)-[:CONTAINED_IN]->(f)
        RETURN c
        """
        props = class_node.to_dict()
        qualified_name = props.pop('qualified_name')

        try:
            with self.driver.session(database=self.database) as session:
                def _insert(tx):
                    tx.run(
                        query,
                        file_path=file_path,
                        repo_id=repo_id,
                        qualified_name=qualified_name,
                        props={**props, 'repo_id': repo_id}
                    )
                session.execute_write(_insert)
            return True
        except Exception as e:
            logger.error(f"Failed to insert class {class_node.name}: {e}")
            return False

    def insert_module_node(self, module: ModuleNode, repo_id: str) -> bool:
        """
        Insert a module node.

        Args:
            module: ModuleNode to insert
            repo_id: Repository identifier

        Returns:
            True if successful
        """
        query = """
        MERGE (m:Module {name: $name})
        SET m += $props
        RETURN m
        """
        props = module.to_dict()
        name = props.pop('name')

        try:
            with self.driver.session(database=self.database) as session:
                def _insert(tx):
                    tx.run(query, name=name, props=props)
                session.execute_write(_insert)
            return True
        except Exception as e:
            logger.error(f"Failed to insert module {module.name}: {e}")
            return False

    # ========== Relationship Insertion ==========

    def create_relationship(self, rel: Relationship, repo_id: str) -> bool:
        """
        Create a relationship between nodes.

        Args:
            rel: Relationship to create
            repo_id: Repository identifier

        Returns:
            True if successful
        """
        # Different query based on relationship type
        if rel.rel_type == RelationType.CALLS:
            query = """
            MATCH (source:Function {qualified_name: $source_id, repo_id: $repo_id})
            MATCH (target:Function {qualified_name: $target_id, repo_id: $repo_id})
            MERGE (source)-[r:CALLS]->(target)
            SET r += $metadata
            RETURN r
            """
        elif rel.rel_type == RelationType.IMPORTS:
            query = """
            MATCH (source:File {path: $source_id, repo_id: $repo_id})
            MATCH (target:Module {name: $target_id})
            MERGE (source)-[r:IMPORTS]->(target)
            SET r += $metadata
            RETURN r
            """
        elif rel.rel_type == RelationType.INHERITS:
            query = """
            MATCH (source:Class {qualified_name: $source_id, repo_id: $repo_id})
            MATCH (target:Class {qualified_name: $target_id, repo_id: $repo_id})
            MERGE (source)-[r:INHERITS]->(target)
            SET r += $metadata
            RETURN r
            """
        else:
            # Generic relationship
            query = f"""
            MATCH (source {{qualified_name: $source_id, repo_id: $repo_id}})
            MATCH (target {{qualified_name: $target_id, repo_id: $repo_id}})
            MERGE (source)-[r:{rel.rel_type.value}]->(target)
            SET r += $metadata
            RETURN r
            """

        try:
            with self.driver.session(database=self.database) as session:
                def _insert(tx):
                    tx.run(
                        query,
                        source_id=rel.source_id,
                        target_id=rel.target_id,
                        repo_id=repo_id,
                        metadata=rel.metadata
                    )
                session.execute_write(_insert)
            return True
        except Exception as e:
            logger.error(f"Failed to create relationship {rel.rel_type.value}: {e}")
            return False

    # ========== Bulk Insertion ==========

    def insert_structural_data(self, data: StructuralData) -> bool:
        """
        Insert complete structural data for a file.

        Args:
            data: StructuralData containing all nodes and relationships

        Returns:
            True if successful
        """
        repo_id = data.file_node.repo_id

        # Insert file node
        if not self.insert_file_node(data.file_node):
            return False

        # Insert function nodes
        for function in data.functions:
            self.insert_function_node(function, data.file_node.path, repo_id)

        # Insert class nodes
        for class_node in data.classes:
            self.insert_class_node(class_node, data.file_node.path, repo_id)

        # Insert module nodes
        for module in data.modules:
            self.insert_module_node(module, repo_id)

        # Create relationships
        for rel in data.relationships:
            self.create_relationship(rel, repo_id)

        return True

    # ========== File Deletion (for incremental updates) ==========

    def delete_file_nodes(self, file_path: str, repo_id: str):
        """
        Delete all nodes associated with a file.

        Used for incremental updates when file changes.

        Args:
            file_path: Path to file
            repo_id: Repository identifier
        """
        query = """
        MATCH (f:File {path: $file_path, repo_id: $repo_id})
        OPTIONAL MATCH (f)<-[:CONTAINED_IN]-(child)
        DETACH DELETE child, f
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, file_path=file_path, repo_id=repo_id)

    # ========== Graph Queries ==========

    def find_function_callers(self, function_name: str, repo_id: str, max_depth: int = 5) -> QueryResult:
        """
        Find all functions that call a given function.

        Args:
            function_name: Name or qualified name of function
            repo_id: Repository identifier
            max_depth: Maximum depth for call chain traversal

        Returns:
            QueryResult with caller functions and call chains
        """
        query = f"""
        MATCH path = (caller:Function {{repo_id: $repo_id}})-[:CALLS*1..{max_depth}]->(target:Function {{repo_id: $repo_id}})
        WHERE target.name = $function_name OR target.qualified_name = $function_name
        RETURN caller, target, path
        LIMIT 100
        """

        start_time = time.time()
        results = QueryResult()

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, function_name=function_name, repo_id=repo_id)

                for record in result:
                    caller = dict(record['caller'])
                    results.nodes.append(caller)

                results.total_results = len(results.nodes)
                results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            logger.error(f"Query failed: {e}")

        return results

    def find_files_by_dependency(self, module_name: str, repo_id: str) -> QueryResult:
        """
        Find all files that import a given module.

        Args:
            module_name: Module name (e.g., 'os', 'django.http')
            repo_id: Repository identifier

        Returns:
            QueryResult with file paths
        """
        query = """
        MATCH (f:File {repo_id: $repo_id})-[:IMPORTS]->(m:Module {name: $module_name})
        RETURN f
        LIMIT 100
        """

        start_time = time.time()
        results = QueryResult()

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, module_name=module_name, repo_id=repo_id)

                for record in result:
                    file_node = dict(record['f'])
                    results.nodes.append(file_node)

                results.total_results = len(results.nodes)
                results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            logger.error(f"Query failed: {e}")

        return results

    def find_class_hierarchy(self, class_name: str, repo_id: str) -> QueryResult:
        """
        Find class inheritance hierarchy.

        Args:
            class_name: Class name
            repo_id: Repository identifier

        Returns:
            QueryResult with class hierarchy
        """
        query = """
        MATCH path = (c:Class {repo_id: $repo_id})-[:INHERITS*0..10]->(base:Class {repo_id: $repo_id})
        WHERE c.name = $class_name OR c.qualified_name = $class_name
        RETURN c, base, path
        """

        start_time = time.time()
        results = QueryResult()

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, class_name=class_name, repo_id=repo_id)

                for record in result:
                    class_node = dict(record['c'])
                    base_node = dict(record['base'])
                    results.nodes.append(class_node)
                    results.nodes.append(base_node)

                results.total_results = len(results.nodes)
                results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            logger.error(f"Query failed: {e}")

        return results

    def search_by_name(self, search_term: str, repo_id: str, node_type: str = "Function") -> QueryResult:
        """
        Search for nodes by name (case-insensitive).

        Args:
            search_term: Search term
            repo_id: Repository identifier
            node_type: Type of node to search (Function, Class, File)

        Returns:
            QueryResult with matching nodes
        """
        query = f"""
        MATCH (n:{node_type} {{repo_id: $repo_id}})
        WHERE toLower(n.name) CONTAINS toLower($search_term)
        RETURN n
        LIMIT 50
        """

        start_time = time.time()
        results = QueryResult()

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, search_term=search_term, repo_id=repo_id)

                for record in result:
                    node = dict(record['n'])
                    results.nodes.append(node)

                results.total_results = len(results.nodes)
                results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            logger.error(f"Query failed: {e}")

        return results

    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> QueryResult:
        """
        Execute arbitrary Cypher query with optional parameters.

        IMPORTANT: Always use parameterized queries to prevent injection attacks.
        Use $parameter_name in query string and pass values via parameters dict.

        Args:
            query: Cypher query string (use $param for parameters)
            parameters: Dictionary of parameter values (default: {})

        Returns:
            QueryResult with query results
        """
        if parameters is None:
            parameters = {}

        start_time = time.time()
        results = QueryResult()

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, **parameters)

                # Collect all records
                for record in result:
                    # Convert record to dict, handling different node types
                    node_dict = {}
                    for key in record.keys():
                        value = record[key]
                        # Handle Neo4j node objects
                        if hasattr(value, '__dict__'):
                            node_dict[key] = dict(value)
                        else:
                            node_dict[key] = value
                    results.nodes.append(node_dict)

                results.total_results = len(results.nodes)
                results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.debug(f"   Query: {query[:200]}...")
            logger.debug(f"   Parameters: {parameters}")

        return results

    def execute_query_batch(self, queries: List[Dict[str, Any]]) -> List[QueryResult]:
        """
        Execute multiple queries in batch for better performance.

        Args:
            queries: List of query dictionaries with 'query' and 'parameters'

        Returns:
            List of QueryResult objects
        """
        if not queries:
            return []

        start_time = time.time()
        results = []

        try:
            with self.driver.session(database=self.database) as session:
                for query_dict in queries:
                    query = query_dict.get('query')
                    parameters = query_dict.get('parameters', {})

                    if not query:
                        results.append(QueryResult())
                        continue

                    query_start = time.time()
                    query_result = QueryResult()

                    try:
                        result = session.run(query, **parameters)

                        for record in result:
                            node_dict = {}
                            for key in record.keys():
                                value = record[key]
                                if hasattr(value, '__dict__'):
                                    node_dict[key] = dict(value)
                                else:
                                    node_dict[key] = value
                            query_result.nodes.append(node_dict)

                        query_result.total_results = len(query_result.nodes)
                        query_result.query_time_ms = (time.time() - query_start) * 1000

                    except Exception as e:
                        logger.error(f"Query execution failed in batch: {e}")
                        query_result.query_time_ms = (time.time() - query_start) * 1000

                    results.append(query_result)

            total_time = (time.time() - start_time) * 1000
            avg_time = total_time / len(queries) if queries else 0
            logger.info(f"Batch query completed: {len(queries)} queries in {total_time:.1f}ms")

        except Exception as e:
            logger.error(f"Batch query execution failed: {e}")
            results = [QueryResult() for _ in queries]

        return results


# ============================================================================
# Knowledge Base Manager
# ============================================================================

class KnowledgeBaseManager:
    """
    Manages knowledge base lifecycle and operations.

    Responsibilities:
    - KB initialization (build/load)
    - File parsing (AST analysis)
    - Incremental updates
    - Repository statistics
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], kb: "Neo4jKnowledgeBase" = None):
        self.repo_path = repo_path
        self.config = config
        self.kb = kb
        self.repo_id = self._generate_repo_id(repo_path)

        # Incremental update support
        self.file_watcher = None
        self.incremental_updater = None

        # Store last build's structural data for enhanced layers
        self._last_structural_data = []

    def _generate_repo_id(self, repo_path: str) -> str:
        """Generate unique repo ID from path"""
        abs_path = os.path.abspath(repo_path)
        return hashlib.md5(abs_path.encode()).hexdigest()[:12]

    def is_available(self) -> bool:
        """Check if KB is available"""
        return self.kb is not None

    def exists(self) -> bool:
        """Check if KB exists (has data)"""
        if not self.kb:
            return False
        try:
            stats = self.kb.get_repository_stats(self.repo_id)
            return stats.get('files', 0) > 0
        except Exception:
            return False

    def parse_file(self, file_path: str) -> Optional[StructuralData]:
        """Parse a file and extract structural data (auto-detect language)"""
        try:
            # Try Python AST parser first (most accurate for Python)
            parser = PythonASTParser(self.repo_path, self.repo_id)
            result = parser.parse_file(file_path)
            if result:
                return result

            # Fall back to multi-language parser (content-driven detection)
            ml_parser = MultiLanguageParser(self.repo_path, self.repo_id)
            return ml_parser.parse_file(file_path)

        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def build(self, force_rebuild: bool = False) -> BuildResult:
        """
        Build knowledge base from source files.

        Args:
            force_rebuild: Force rebuild even if KB exists

        Returns:
            BuildResult with statistics
        """
        if not self.kb:
            return BuildResult(
                success=False,
                total_files=0,
                total_functions=0,
                total_classes=0,
                build_time_seconds=0,
                error="KB not initialized"
            )

        start_time = time.time()

        # Delete existing KB if force rebuild
        if force_rebuild and self.exists():
            logger.info("Force rebuild - deleting existing KB...")
            self.kb.delete_repository(self.repo_id)

        # Check if KB exists (after potential deletion)
        if not force_rebuild and self.exists():
            logger.info("KB already exists, skipping build")
            stats = self.get_stats()
            total_files = stats.get('files', 0)
            return BuildResult(
                total_files=total_files,
                total_functions=stats.get('functions', 0),
                total_classes=stats.get('classes', 0),
                total_variables=stats.get('variables', 0),
                total_modules=stats.get('modules', 0),
                total_relationships=stats.get('relationships', 0),
                build_time_seconds=time.time() - start_time,
                files_per_second=0
            )

        logger.info("Building knowledge base...")

        # Get source files
        source_files = self._get_source_files()
        logger.info(f"Found {len(source_files)} source files")

        # Parse files in parallel
        build_config = self.config.get('knowledge_base', {}).get('build', {})
        max_workers = build_config.get('parallel_workers', 10)

        structural_data_list = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.parse_file, f): f for f in source_files}

            for future in concurrent.futures.as_completed(futures):
                file_path = futures[future]
                try:
                    data = future.result()
                    if data:
                        structural_data_list.append(data)
                except Exception as e:
                    logger.error(f"Error parsing {file_path}: {e}")

        logger.info(f"Parsed {len(structural_data_list)} files successfully")

        # Populate KB
        logger.info(f"Inserting {len(structural_data_list)} files into Neo4j...")
        for i, structural_data in enumerate(structural_data_list, 1):
            try:
                self.kb.insert_structural_data(structural_data)
                if i % 100 == 0:
                    logger.info(f"Inserted {i}/{len(structural_data_list)} files...")
            except Exception as e:
                logger.error(f"Failed to insert {structural_data.file_node.path}: {e}")

        # Store structural data for enhanced layers
        self._last_structural_data = structural_data_list

        build_time = time.time() - start_time
        stats = self.get_stats()

        logger.info(f"KB built in {build_time:.1f}s")

        # Initialize file watcher to track current state for incremental updates
        incremental_config = self.config.get('knowledge_base', {}).get('incremental', {})
        if incremental_config.get('enabled', False):
            self.file_watcher = FileChangeDetector(
                self.repo_path,
                use_hashing=incremental_config.get('use_file_hashing', True)
            )
            self.file_watcher.force_scan()  # Establish baseline

        total_files = stats.get('files', 0)
        files_per_sec = total_files / build_time if build_time > 0 else 0

        return BuildResult(
            total_files=total_files,
            total_functions=stats.get('functions', 0),
            total_classes=stats.get('classes', 0),
            total_variables=stats.get('variables', 0),
            total_modules=stats.get('modules', 0),
            total_relationships=stats.get('relationships', 0),
            build_time_seconds=build_time,
            files_per_second=files_per_sec
        )

    def update(self) -> Dict[str, Any]:
        """Incrementally update KB with changed files"""
        if not self.kb:
            return {'success': False, 'error': 'KB not initialized'}

        incremental_config = self.config.get('knowledge_base', {}).get('incremental', {})
        if not incremental_config.get('enabled', False):
            return {'success': False, 'error': 'Incremental updates not enabled'}

        # Initialize file watcher if needed
        if not self.file_watcher:
            self.file_watcher = FileChangeDetector(
                self.repo_path,
                use_hashing=incremental_config.get('use_file_hashing', True)
            )

        # Initialize incremental updater
        if not self.incremental_updater:
            self.incremental_updater = IncrementalKBUpdater(self.kb, self.repo_id)

        # Detect changes
        changes = self.file_watcher.detect_changes()
        if not changes.has_changes():
            return {'success': True, 'changes': 0}

        # Parse changed files (convert relative paths to absolute)
        structural_data_list = []
        for rel_path in list(changes.modified) + list(changes.added):
            abs_path = os.path.join(self.repo_path, rel_path)
            data = self.parse_file(abs_path)
            if data:
                structural_data_list.append(data)

        # Update KB
        self.incremental_updater.update(structural_data_list, list(changes.deleted))

        return {
            'success': True,
            'changes': len(changes.modified) + len(changes.added) + len(changes.deleted),
            'added': len(changes.added),
            'modified': len(changes.modified),
            'deleted': len(changes.deleted)
        }

    def _get_source_files(self) -> List[str]:
        """Get all source files in repository - discovers files dynamically"""
        repo_config = self.config.get('repo', {})
        excluded_dirs = set(repo_config.get('excluded_dirs', []))

        source_files = []
        for root, dirs, files in os.walk(self.repo_path):
            # Filter excluded directories and hidden directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('.')]

            for file in files:
                # Skip hidden files
                if file.startswith('.'):
                    continue

                file_path = os.path.join(root, file)

                # Try to detect if file is text/source by attempting to read it
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        # Read first chunk to verify it's text
                        f.read(1024)
                    source_files.append(file_path)
                except (UnicodeDecodeError, IOError):
                    # Binary file or unreadable - skip
                    continue

        return source_files

    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics from KB"""
        if not self.kb:
            return {}

        try:
            return self.kb.get_repository_stats(self.repo_id)
        except Exception as e:
            logger.warning(f"Failed to get stats: {e}")
            return {}

    def get_structural_data(self) -> List[Any]:
        """Get structural data from last build."""
        return self._last_structural_data

    def lookup_file_path(self, qualified_name: str) -> Optional[str]:
        """Look up file path for a qualified name"""
        if not self.kb:
            return None

        try:
            query = """
            MATCH (n {qualified_name: $qname, repo_id: $repo_id})
            WHERE n:Function OR n:Class
            RETURN n.file_path as file_path
            LIMIT 1
            """
            result = self.kb.execute_query(query, {'qname': qualified_name, 'repo_id': self.repo_id})

            if result.nodes:
                return result.nodes[0]['file_path']
        except Exception as e:
            logger.warning(f"Lookup failed for {qualified_name}: {e}")

        return None

    def close(self):
        """Close KB connection"""
        if self.kb:
            try:
                self.kb.close()
            except Exception:
                pass


# ============================================================================
# KB Orchestrator Facade
# ============================================================================

class KBOrchestrator:
    """
    Orchestrates knowledge base construction and querying.

    Acts as a thin orchestration layer that delegates to specialized managers.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], kb: Neo4jKnowledgeBase = None):
        """
        Initialize structural pipeline with all managers.

        Args:
            repo_path: Root path of repository
            config: Configuration dictionary
            kb: Optional Neo4j KB instance
        """
        self.repo_path = repo_path
        self.config = config
        self.repo_id = self._generate_repo_id(repo_path)

        # Initialize KB if not provided
        if kb is None:
            kb_config = config.get('knowledge_base', {}).get('neo4j', {})
            password = kb_config.get('password') or os.environ.get('NEO4J_PASSWORD', 'password')

            try:
                self.kb = Neo4jKnowledgeBase(
                    uri=kb_config.get('uri', 'bolt://localhost:7687'),
                    user=kb_config.get('user', 'neo4j'),
                    password=password,
                    database=kb_config.get('database', 'neo4j')
                )
            except Exception as e:
                logger.warning(f"Failed to connect to Neo4j: {e}")
                self.kb = None
        else:
            self.kb = kb

        # Initialize dependency graph builder
        self.dep_graph = DependencyGraphBuilder()

        # Initialize LLM client
        self._llm_client = None
        try:
            self._llm_client = LLMClient(self.config.get('llm', {}))
        except Exception as e:
            logger.warning(f"LLM client initialization failed: {e}")

        # Initialize all manager classes
        self.kb_manager = KnowledgeBaseManager(repo_path, config, self.kb)
        self.semantic_search = SemanticSearch.from_config(config, self._llm_client)
        self.pattern_detectors = PatternDetectors.from_config(config, self.kb)
        self.execution_path_tracers = ExecutionPathTracers.from_config(config, self.dep_graph)

        # Initialize query engine
        self.query_engine = QueryEngine(
            kb=self.kb,
            repo_id=self.repo_id,
            repo_path=repo_path,
            semantic_search=self.semantic_search,
            pattern_detectors=self.pattern_detectors,
            execution_path_tracers=self.execution_path_tracers,
            config=config
        )

        # Initialize entry point resolver
        self.entry_point_resolver = EntryPointResolver(
            kb=self.kb,
            repo_id=self.repo_id,
            repo_path=repo_path,
            config=config
        )

        # File watcher for incremental updates
        self.file_watcher = None

        # Config shortcuts
        self.semantic_config = config.get('knowledge_base', {}).get('semantic', {})
        self.patterns_config = config.get('knowledge_base', {}).get('patterns', {})
        self.lifeofx_config = config.get('knowledge_base', {}).get('lifeofx', {})

        # Try loading enhanced layers if KB already exists
        if self.kb_exists():
            self._try_load_enhanced_layers()

    def _generate_repo_id(self, repo_path: str) -> str:
        """Generate unique repo ID from path"""
        abs_path = os.path.abspath(repo_path)
        return hashlib.md5(abs_path.encode()).hexdigest()[:12]

    # ========== Context Manager Support ==========

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close KB connection"""
        if hasattr(self, 'kb_manager'):
            self.kb_manager.close()

    def __del__(self):
        self.close()

    # ========== KB Availability ==========

    def is_kb_available(self) -> bool:
        """Check if KB is available"""
        return self.kb_manager.is_available()

    def kb_exists(self) -> bool:
        """Check if KB has data"""
        return self.kb_manager.exists()

    # ========== Query Delegation ==========

    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> QueryResult:
        """Execute query on underlying KB."""
        if self.kb is None:
            return QueryResult()
        return self.kb.execute_query(query, parameters)

    # ========== KB Lifecycle ==========

    def build_knowledge_base(self, force_rebuild: bool = False) -> BuildResult:
        """Build knowledge base from source files."""
        result = self.kb_manager.build(force_rebuild)

        if result and result.total_files > 0 and self.kb:
            structural_data = self.kb_manager.get_structural_data()
            self._build_enhanced_layers(structural_data)

        return result

    def update_knowledge_base(self) -> Dict[str, Any]:
        """Incrementally update KB with changed files."""
        return self.kb_manager.update()

    def _try_load_enhanced_layers(self):
        """Try loading enhanced layers from cache."""
        if self.semantic_search is not None:
            cache_file = self.semantic_config.get('cache_file', '.codefusion/embeddings.pkl')
            try:
                self.semantic_search.load_index(cache_file)
                logger.debug("Loaded semantic embeddings from cache")
            except Exception as e:
                logger.debug(f"Failed to load semantic cache: {e}")

    def _build_enhanced_layers(self, structural_data_list: List[Any] = None):
        """Build enhanced layers (semantic, pattern, execution)."""
        if self.semantic_search is not None:
            logger.debug("Generating semantic embeddings...")
            try:
                if not structural_data_list:
                    cache_file = self.semantic_config.get('cache_file', '.codefusion/embeddings.pkl')
                    try:
                        self.semantic_search.load_index(cache_file)
                    except:
                        logger.debug("No structural data and no cache found")
                else:
                    cache_file = self.semantic_config.get('cache_file')
                    self.semantic_search.initialize_from_structural_data(
                        structural_data_list,
                        cache_file=cache_file
                    )
            except Exception as e:
                logger.warning(f"Semantic layer failed: {e}")

        if self.pattern_detectors is not None and self.pattern_detectors.is_enabled():
            logger.debug("Pattern detection ready")

        if self.execution_path_tracers is not None and self.execution_path_tracers.is_enabled():
            logger.debug("Execution path tracing ready")

    # ========== Query Interface ==========

    def find_files_for_question(
        self,
        question: str,
        max_results: int = 50,
        question_context: Dict[str, Any] = None
    ) -> List[str]:
        """Find relevant files for a question."""
        return self.query_engine.find_files(
            question=question,
            max_results=max_results,
            question_context=question_context,
            entry_point_resolver=self.entry_point_resolver
        )

    def get_repository_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        return self.kb_manager.get_stats()

    # ========== Property Delegation ==========

    @property
    def code_embedder(self) -> Optional[CodeEmbedder]:
        """Get code embedder from semantic search"""
        return self.semantic_search.embedder if self.semantic_search else None

    @property
    def design_pattern_detector(self) -> Optional[DesignPatternDetector]:
        """Get design pattern detector"""
        return self.pattern_detectors.design_pattern_detector if self.pattern_detectors else None

    @property
    def architectural_pattern_detector(self) -> Optional[ArchitecturalPatternDetector]:
        """Get architectural pattern detector"""
        return self.pattern_detectors.architectural_pattern_detector if self.pattern_detectors else None

    @property
    def code_smell_detector(self) -> Optional[CodeSmellDetector]:
        """Get code smell detector"""
        return self.pattern_detectors.code_smell_detector if self.pattern_detectors else None

    @property
    def dataflow_analyzer(self) -> Optional[DataFlowAnalyzer]:
        """Get data flow analyzer"""
        return self.execution_path_tracers.dataflow_analyzer if self.execution_path_tracers else None

    @property
    def execution_path_tracer(self) -> Optional[ExecutionPathTracer]:
        """Get execution path tracer"""
        return self.execution_path_tracers.execution_path_tracer if self.execution_path_tracers else None


# Export all
__all__ = [
    'Neo4jKnowledgeBase',
    'KnowledgeBaseManager',
    'KBOrchestrator',
    'ChangeSet',
    'FileChangeDetector',
    'IncrementalKBUpdater',
]
