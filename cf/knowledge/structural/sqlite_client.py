"""
SQLite Knowledge Base Client

Lightweight alternative to Neo4j for structural code analysis.
Uses relational database with efficient indexing.

Trade-offs vs Neo4j:
- ✅ No external database server required
- ✅ File-based, portable, easy to set up
- ✅ Good performance for small-medium codebases (<10K files)
- ❌ Slower for deep graph traversals (call chains, inheritance)
- ❌ Limited concurrent access
- ❌ Less efficient for complex graph queries

Recommended for:
- Local development and testing
- Small to medium codebases
- Quick setup without infrastructure
- Single-user analysis sessions
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from cf.knowledge.structural.schema import (
    StructuralData, FileNode, FunctionNode, ClassNode, VariableNode, ModuleNode,
    Relationship, RelationType, QueryResult, BuildResult
)


class SQLiteKnowledgeBase:
    """
    SQLite-based persistent knowledge base for code structure.

    Provides same interface as Neo4jKnowledgeBase but with relational DB.
    """

    def __init__(self, db_path: str = ".codefusion/knowledge.db"):
        """
        Initialize SQLite connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Create directory if needed
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Access columns by name

        print(f"✅ Connected to SQLite at {db_path}")

        # Create tables and indexes
        self._create_tables()
        self._create_indexes()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✅ SQLite connection closed")

    def _create_tables(self):
        """Create database tables"""
        cursor = self.conn.cursor()

        # Files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                repo_id TEXT NOT NULL,
                language TEXT,
                size_bytes INTEGER,
                line_count INTEGER,
                file_hash TEXT,
                last_modified TEXT,
                UNIQUE(path, repo_id)
            )
        """)

        # Functions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS functions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                repo_id TEXT NOT NULL,
                start_line INTEGER,
                end_line INTEGER,
                parameters TEXT,  -- JSON array
                return_type TEXT,
                docstring TEXT,
                is_async BOOLEAN,
                is_method BOOLEAN,
                complexity INTEGER,
                UNIQUE(qualified_name, repo_id)
            )
        """)

        # Classes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                repo_id TEXT NOT NULL,
                start_line INTEGER,
                end_line INTEGER,
                base_classes TEXT,  -- JSON array
                docstring TEXT,
                num_methods INTEGER,
                UNIQUE(qualified_name, repo_id)
            )
        """)

        # Modules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                is_stdlib BOOLEAN,
                UNIQUE(name)
            )
        """)

        # Relationships table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rel_type TEXT NOT NULL,
                source_type TEXT NOT NULL,  -- Function, Class, File
                source_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                repo_id TEXT NOT NULL,
                metadata TEXT,  -- JSON
                UNIQUE(rel_type, source_id, target_id, repo_id)
            )
        """)

        self.conn.commit()

    def _create_indexes(self):
        """Create indexes for common queries"""
        cursor = self.conn.cursor()

        # File indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repo_id)")

        # Function indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_qualified ON functions(qualified_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_file ON functions(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_repo ON functions(repo_id)")

        # Class indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_qualified ON classes(qualified_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_file ON classes(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_repo ON classes(repo_id)")

        # Module indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modules_name ON modules(name)")

        # Relationship indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rels_type ON relationships(rel_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rels_source ON relationships(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rels_target ON relationships(target_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rels_repo ON relationships(repo_id)")

        self.conn.commit()

    # ========== Repository Management ==========

    def check_repo_exists(self, repo_id: str) -> bool:
        """Check if repository already exists in KB"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files WHERE repo_id = ?", (repo_id,))
        count = cursor.fetchone()[0]
        return count > 0

    def delete_repository(self, repo_id: str):
        """Delete all data for a repository"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM files WHERE repo_id = ?", (repo_id,))
        cursor.execute("DELETE FROM functions WHERE repo_id = ?", (repo_id,))
        cursor.execute("DELETE FROM classes WHERE repo_id = ?", (repo_id,))
        cursor.execute("DELETE FROM relationships WHERE repo_id = ?", (repo_id,))
        self.conn.commit()
        print(f"✅ Deleted repository: {repo_id}")

    def get_repository_stats(self, repo_id: str) -> Dict[str, int]:
        """Get statistics for a repository"""
        cursor = self.conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) FROM files WHERE repo_id = ?", (repo_id,))
        stats['files'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM functions WHERE repo_id = ?", (repo_id,))
        stats['functions'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM classes WHERE repo_id = ?", (repo_id,))
        stats['classes'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM relationships WHERE repo_id = ?", (repo_id,))
        stats['relationships'] = cursor.fetchone()[0]

        return stats

    # ========== Node Insertion ==========

    def insert_file_node(self, file_node: FileNode) -> bool:
        """Insert or update a file node"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO files (path, repo_id, language, size_bytes, line_count, file_hash, last_modified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_node.path,
                file_node.repo_id,
                file_node.language,
                file_node.size_bytes,
                file_node.line_count,
                file_node.file_hash,
                file_node.last_modified
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Failed to insert file node {file_node.path}: {e}")
            return False

    def insert_function_node(self, function: FunctionNode, file_path: str, repo_id: str) -> bool:
        """Insert a function node and link to file"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO functions
                (name, qualified_name, file_path, repo_id, start_line, end_line,
                 parameters, return_type, docstring, is_async, is_method, complexity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                function.name,
                function.qualified_name,
                file_path,
                repo_id,
                function.start_line,
                function.end_line,
                json.dumps(function.parameters),
                function.return_type,
                function.docstring,
                function.is_async,
                function.is_method,
                function.cyclomatic_complexity
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Failed to insert function {function.name}: {e}")
            return False

    def insert_class_node(self, class_node: ClassNode, file_path: str, repo_id: str) -> bool:
        """Insert a class node and link to file"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO classes
                (name, qualified_name, file_path, repo_id, start_line, end_line,
                 base_classes, docstring, num_methods)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                class_node.name,
                class_node.qualified_name,
                file_path,
                repo_id,
                class_node.start_line,
                class_node.end_line,
                json.dumps(class_node.base_classes),
                class_node.docstring,
                class_node.num_methods
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Failed to insert class {class_node.name}: {e}")
            return False

    def insert_module_node(self, module: ModuleNode, repo_id: str) -> bool:
        """Insert a module node"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO modules (name, is_stdlib)
                VALUES (?, ?)
            """, (module.name, module.is_stdlib))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Failed to insert module {module.name}: {e}")
            return False

    # ========== Relationship Insertion ==========

    def create_relationship(self, rel: Relationship, repo_id: str) -> bool:
        """Create a relationship between nodes"""
        try:
            # Determine source and target types based on relationship
            if rel.rel_type == RelationType.CALLS:
                source_type = target_type = "Function"
            elif rel.rel_type == RelationType.IMPORTS:
                source_type = "File"
                target_type = "Module"
            elif rel.rel_type == RelationType.INHERITS:
                source_type = target_type = "Class"
            else:
                source_type = target_type = "Unknown"

            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO relationships
                (rel_type, source_type, source_id, target_type, target_id, repo_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                rel.rel_type.value,
                source_type,
                rel.source_id,
                target_type,
                rel.target_id,
                repo_id,
                json.dumps(rel.metadata)
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Failed to create relationship {rel.rel_type.value}: {e}")
            return False

    # ========== Bulk Insertion ==========

    def insert_structural_data(self, data: StructuralData) -> bool:
        """Insert complete structural data for a file"""
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
        """Delete all nodes associated with a file"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM files WHERE path = ? AND repo_id = ?", (file_path, repo_id))
        cursor.execute("DELETE FROM functions WHERE file_path = ? AND repo_id = ?", (file_path, repo_id))
        cursor.execute("DELETE FROM classes WHERE file_path = ? AND repo_id = ?", (file_path, repo_id))
        self.conn.commit()

    # ========== Graph Queries ==========

    def find_function_callers(self, function_name: str, repo_id: str, max_depth: int = 5) -> QueryResult:
        """
        Find all functions that call a given function.

        NOTE: This is less efficient than Neo4j for deep call chains.
        Uses recursive CTE for graph traversal.
        """
        query = """
            WITH RECURSIVE call_chain AS (
                -- Base case: find target function
                SELECT
                    f.qualified_name AS target_name,
                    f.qualified_name AS caller_name,
                    f.name AS name,
                    f.file_path AS file_path,
                    0 AS depth
                FROM functions f
                WHERE (f.name = ? OR f.qualified_name = ?)
                    AND f.repo_id = ?

                UNION ALL

                -- Recursive case: find callers
                SELECT
                    cc.target_name,
                    f.qualified_name AS caller_name,
                    f.name AS name,
                    f.file_path AS file_path,
                    cc.depth + 1 AS depth
                FROM call_chain cc
                JOIN relationships r ON r.target_id = cc.caller_name
                    AND r.rel_type = 'CALLS'
                    AND r.repo_id = ?
                JOIN functions f ON f.qualified_name = r.source_id
                    AND f.repo_id = ?
                WHERE cc.depth < ?
            )
            SELECT DISTINCT caller_name, name, file_path, depth
            FROM call_chain
            WHERE depth > 0
            LIMIT 100
        """

        start_time = time.time()
        results = QueryResult()

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (function_name, function_name, repo_id, repo_id, repo_id, max_depth))

            for row in cursor.fetchall():
                node = {
                    'qualified_name': row[0],
                    'name': row[1],
                    'file_path': row[2],
                    'depth': row[3]
                }
                results.nodes.append(node)

            results.total_results = len(results.nodes)
            results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            print(f"❌ Query failed: {e}")

        return results

    def find_files_by_dependency(self, module_name: str, repo_id: str) -> QueryResult:
        """Find all files that import a given module"""
        query = """
            SELECT DISTINCT f.path, f.language, f.line_count
            FROM files f
            JOIN relationships r ON r.source_id = f.path
                AND r.rel_type = 'IMPORTS'
                AND r.repo_id = ?
            WHERE r.target_id = ?
            LIMIT 100
        """

        start_time = time.time()
        results = QueryResult()

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (repo_id, module_name))

            for row in cursor.fetchall():
                node = {
                    'path': row[0],
                    'language': row[1],
                    'line_count': row[2]
                }
                results.nodes.append(node)

            results.total_results = len(results.nodes)
            results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            print(f"❌ Query failed: {e}")

        return results

    def find_class_hierarchy(self, class_name: str, repo_id: str) -> QueryResult:
        """
        Find class inheritance hierarchy.

        Uses recursive CTE to traverse inheritance tree.
        """
        query = """
            WITH RECURSIVE inheritance AS (
                -- Base case: find target class
                SELECT
                    c.qualified_name,
                    c.name,
                    c.file_path,
                    c.base_classes,
                    0 AS depth
                FROM classes c
                WHERE (c.name = ? OR c.qualified_name = ?)
                    AND c.repo_id = ?

                UNION ALL

                -- Recursive case: find base classes
                SELECT
                    c.qualified_name,
                    c.name,
                    c.file_path,
                    c.base_classes,
                    i.depth + 1 AS depth
                FROM inheritance i
                JOIN relationships r ON r.source_id = i.qualified_name
                    AND r.rel_type = 'INHERITS'
                    AND r.repo_id = ?
                JOIN classes c ON c.qualified_name = r.target_id
                    AND c.repo_id = ?
                WHERE i.depth < 10
            )
            SELECT qualified_name, name, file_path, base_classes, depth
            FROM inheritance
        """

        start_time = time.time()
        results = QueryResult()

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (class_name, class_name, repo_id, repo_id, repo_id))

            for row in cursor.fetchall():
                node = {
                    'qualified_name': row[0],
                    'name': row[1],
                    'file_path': row[2],
                    'base_classes': json.loads(row[3] or '[]'),
                    'depth': row[4]
                }
                results.nodes.append(node)

            results.total_results = len(results.nodes)
            results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            print(f"❌ Query failed: {e}")

        return results

    def search_by_name(self, search_term: str, repo_id: str, node_type: str = "Function") -> QueryResult:
        """Search for nodes by name (case-insensitive)"""
        start_time = time.time()
        results = QueryResult()

        try:
            cursor = self.conn.cursor()

            if node_type == "Function":
                query = """
                    SELECT name, qualified_name, file_path, start_line, end_line
                    FROM functions
                    WHERE LOWER(name) LIKE LOWER(?) AND repo_id = ?
                    LIMIT 50
                """
            elif node_type == "Class":
                query = """
                    SELECT name, qualified_name, file_path, start_line, end_line
                    FROM classes
                    WHERE LOWER(name) LIKE LOWER(?) AND repo_id = ?
                    LIMIT 50
                """
            elif node_type == "File":
                query = """
                    SELECT path, language, line_count
                    FROM files
                    WHERE LOWER(path) LIKE LOWER(?) AND repo_id = ?
                    LIMIT 50
                """
            else:
                return results

            cursor.execute(query, (f'%{search_term}%', repo_id))

            for row in cursor.fetchall():
                if node_type == "File":
                    node = {'path': row[0], 'language': row[1], 'line_count': row[2]}
                else:
                    node = {
                        'name': row[0],
                        'qualified_name': row[1],
                        'file_path': row[2],
                        'start_line': row[3],
                        'end_line': row[4]
                    }
                results.nodes.append(node)

            results.total_results = len(results.nodes)
            results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            print(f"❌ Query failed: {e}")

        return results

    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> QueryResult:
        """
        Execute arbitrary SQL query with optional parameters.

        IMPORTANT: Always use parameterized queries to prevent SQL injection.
        Use ? placeholders and pass values via parameters dict.

        Args:
            query: SQL query string (use ? for parameters)
            parameters: Dictionary of parameter values (default: {})

        Returns:
            QueryResult with query results

        Example:
            # GOOD - parameterized:
            result = kb.execute_query(
                "SELECT * FROM classes WHERE repo_id = ?",
                {'repo_id': 'abc123'}
            )
        """
        if parameters is None:
            parameters = {}

        start_time = time.time()
        results = QueryResult()

        try:
            cursor = self.conn.cursor()

            # Convert dict to list of values (ordered by placeholder position)
            param_values = list(parameters.values()) if isinstance(parameters, dict) else parameters

            cursor.execute(query, param_values)

            # Collect all rows
            for row in cursor.fetchall():
                # Convert row to dict
                node_dict = dict(row)
                results.nodes.append(node_dict)

            results.total_results = len(results.nodes)
            results.query_time_ms = (time.time() - start_time) * 1000

        except Exception as e:
            print(f"❌ Query execution failed: {e}")
            print(f"   Query: {query[:200]}...")
            print(f"   Parameters: {parameters}")

        return results
