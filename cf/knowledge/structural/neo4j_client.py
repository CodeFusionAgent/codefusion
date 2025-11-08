"""
Neo4j Knowledge Base Client

Handles all interactions with Neo4j graph database:
- Connection management
- Node and relationship insertion
- Graph queries for code analysis
- Repository management

Provides high-level API for structural knowledge operations.
"""

import time
from typing import List, Dict, Any, Optional
from cf.knowledge.structural.schema import (
    StructuralData, FileNode, FunctionNode, ClassNode, VariableNode, ModuleNode,
    Relationship, RelationType, QueryResult, BuildResult
)

try:
    from neo4j import GraphDatabase, Driver, Session
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️ Neo4j driver not installed. Run: pip install neo4j")


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
        if not NEO4J_AVAILABLE:
            raise RuntimeError("Neo4j driver not available. Install with: pip install neo4j")

        self.uri = uri
        self.user = user
        self.database = database
        self.driver: Optional[Driver] = None

        # Connect to database
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            self.driver.verify_connectivity()
            print(f"✅ Connected to Neo4j at {uri}")
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            raise

        # Create indexes for performance
        self._create_indexes()

    def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()
            print("✅ Neo4j connection closed")

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
            print(f"✅ Deleted repository: {repo_id}")

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
            'relationships': "MATCH ()-[r]->() WHERE EXISTS((startNode(r)).repo_id) AND (startNode(r)).repo_id = $repo_id RETURN count(r) as count"
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
                session.run(query, path=path, repo_id=repo_id, props=props)
            return True
        except Exception as e:
            print(f"❌ Failed to insert file node {file_node.path}: {e}")
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
                session.run(
                    query,
                    file_path=file_path,
                    repo_id=repo_id,
                    qualified_name=qualified_name,
                    props={**props, 'repo_id': repo_id}
                )
            return True
        except Exception as e:
            print(f"❌ Failed to insert function {function.name}: {e}")
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
                session.run(
                    query,
                    file_path=file_path,
                    repo_id=repo_id,
                    qualified_name=qualified_name,
                    props={**props, 'repo_id': repo_id}
                )
            return True
        except Exception as e:
            print(f"❌ Failed to insert class {class_node.name}: {e}")
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
                session.run(query, name=name, props=props)
            return True
        except Exception as e:
            print(f"❌ Failed to insert module {module.name}: {e}")
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
                session.run(
                    query,
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    repo_id=repo_id,
                    metadata=rel.metadata
                )
            return True
        except Exception as e:
            print(f"❌ Failed to create relationship {rel.rel_type.value}: {e}")
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
            print(f"❌ Query failed: {e}")

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
            print(f"❌ Query failed: {e}")

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
            print(f"❌ Query failed: {e}")

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
            print(f"❌ Query failed: {e}")

        return results
