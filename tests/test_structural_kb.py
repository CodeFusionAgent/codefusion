"""
Integration tests for Structural Knowledge Base

Tests the complete KB workflow including building, querying, and incremental updates.
Requires Neo4j running at bolt://localhost:7687
"""

import os
import tempfile
import pytest
from pathlib import Path

from cf.knowledge_base.schema import FileNode, FunctionNode, ClassNode, ModuleNode, Relationship, RelationType, StructuralData
from cf.knowledge_base.kb_orchestrator import Neo4jKnowledgeBase
from cf.knowledge_base.code_parser import PythonASTParser
from cf.knowledge_base.incremental import FileChangeDetector, IncrementalKBUpdater
from cf.knowledge_base.kb_orchestrator import KBOrchestrator


# Skip all tests if Neo4j is not available
pytest_plugins = []

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


def check_neo4j_running():
    """Check if Neo4j is running"""
    if not NEO4J_AVAILABLE:
        return False
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


NEO4J_RUNNING = check_neo4j_running()

skip_if_no_neo4j = pytest.mark.skipif(
    not NEO4J_RUNNING,
    reason="Neo4j not running at bolt://localhost:7687"
)


@pytest.fixture
def temp_repo():
    """Create a temporary repository for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_repo_id():
    """Generate unique test repo ID"""
    import uuid
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def kb(test_repo_id):
    """Create Neo4j KB instance and cleanup after test"""
    if not NEO4J_RUNNING:
        pytest.skip("Neo4j not available")

    kb = Neo4jKnowledgeBase(
        uri="bolt://localhost:7687",
        user="neo4j",
        password=os.environ.get("NEO4J_PASSWORD", "password"),
        database="neo4j"
    )

    yield kb

    # Cleanup: delete test repository data
    try:
        kb.delete_repository(test_repo_id)
    except Exception:
        pass

    kb.close()


@pytest.mark.integration
@skip_if_no_neo4j
class TestNeo4jKnowledgeBase:
    """Test suite for Neo4j knowledge base"""

    def test_connection(self, kb):
        """Test Neo4j connection"""
        assert kb is not None
        assert kb.driver is not None

    def test_repo_lifecycle(self, kb, test_repo_id):
        """Test repository create, check, delete"""
        # Initially should not exist
        assert not kb.check_repo_exists(test_repo_id)

        # Create a file node
        file_node = FileNode(
            path="test.py",
            language="python",
            size=100,
            last_modified=0.0,
            lines_of_code=10,
            repo_id=test_repo_id
        )
        kb.insert_file_node(file_node)

        # Now should exist
        assert kb.check_repo_exists(test_repo_id)

        # Get stats
        stats = kb.get_repository_stats(test_repo_id)
        assert stats['files'] == 1

        # Delete
        kb.delete_repository(test_repo_id)
        assert not kb.check_repo_exists(test_repo_id)

    def test_insert_function_node(self, kb, test_repo_id):
        """Test inserting function nodes"""
        # Create file first
        file_node = FileNode(
            path="test.py",
            language="python",
            size=100,
            last_modified=0.0,
            lines_of_code=10,
            repo_id=test_repo_id
        )
        kb.insert_file_node(file_node)

        # Create function
        func_node = FunctionNode(
            name="test_function",
            qualified_name="test.test_function",
            start_line=1,
            end_line=5,
            file_path="test.py",
            parameters=["arg1", "arg2"]
        )

        success = kb.insert_function_node(func_node, "test.py", test_repo_id)
        assert success

        # Verify
        stats = kb.get_repository_stats(test_repo_id)
        assert stats['functions'] == 1

    def test_insert_class_node(self, kb, test_repo_id):
        """Test inserting class nodes"""
        # Create file first
        file_node = FileNode(
            path="test.py",
            language="python",
            size=100,
            last_modified=0.0,
            lines_of_code=10,
            repo_id=test_repo_id
        )
        kb.insert_file_node(file_node)

        # Create class
        class_node = ClassNode(
            name="TestClass",
            qualified_name="test.TestClass",
            start_line=1,
            end_line=10,
            file_path="test.py",
            base_classes=["BaseClass"]
        )

        success = kb.insert_class_node(class_node, "test.py", test_repo_id)
        assert success

        # Verify
        stats = kb.get_repository_stats(test_repo_id)
        assert stats['classes'] == 1

    def test_find_function_callers(self, kb, test_repo_id):
        """Test finding function callers"""
        # Create file
        file_node = FileNode(
            path="test.py",
            language="python",
            size=100,
            last_modified=0.0,
            lines_of_code=10,
            repo_id=test_repo_id
        )
        kb.insert_file_node(file_node)

        # Create functions
        caller = FunctionNode(
            name="caller",
            qualified_name="test.caller",
            start_line=1,
            end_line=5,
            file_path="test.py"
        )
        callee = FunctionNode(
            name="callee",
            qualified_name="test.callee",
            start_line=7,
            end_line=10,
            file_path="test.py"
        )

        kb.insert_function_node(caller, "test.py", test_repo_id)
        kb.insert_function_node(callee, "test.py", test_repo_id)

        # Create call relationship
        rel = Relationship(
            rel_type=RelationType.CALLS,
            source_id="test.caller",
            target_id="test.callee"
        )
        kb.create_relationship(rel, test_repo_id)

        # Query
        result = kb.find_function_callers("callee", test_repo_id)
        assert result.total_results >= 1

    def test_find_files_by_dependency(self, kb, test_repo_id):
        """Test finding files by module dependency"""
        # Create file
        file_node = FileNode(
            path="test.py",
            language="python",
            size=100,
            last_modified=0.0,
            lines_of_code=10,
            repo_id=test_repo_id
        )
        kb.insert_file_node(file_node)

        # Create module
        module = ModuleNode(
            name="os",
            is_builtin=True,
            is_third_party=False,
            is_local=False
        )
        kb.insert_module_node(module, test_repo_id)

        # Create import relationship
        rel = Relationship(
            rel_type=RelationType.IMPORTS,
            source_id="test.py",
            target_id="os"
        )
        kb.create_relationship(rel, test_repo_id)

        # Query
        result = kb.find_files_by_dependency("os", test_repo_id)
        assert result.total_results >= 1
        assert any(node['path'] == 'test.py' for node in result.nodes)


@pytest.mark.integration
@skip_if_no_neo4j
class TestKBOrchestrator:
    """Test suite for KBOrchestrator"""

    def test_kb_build(self, temp_repo, kb, test_repo_id):
        """Test KB build process"""
        # Create test Python files
        (Path(temp_repo) / "module1.py").write_text("""
def function1():
    pass

class Class1:
    def method1(self):
        pass
""")

        (Path(temp_repo) / "module2.py").write_text("""
import os

def function2():
    function1()
""")

        # Create config
        config = {
            'knowledge_base': {
                'enabled': True,
                'neo4j': {
                    'uri': 'bolt://localhost:7687',
                    'user': 'neo4j',
                    'password': os.environ.get('NEO4J_PASSWORD', 'password'),
                    'database': 'neo4j'
                },
                'build': {
                    'parallel_workers': 2,
                    'auto_build': True
                },
                'incremental': {
                    'enabled': True
                }
            },
            'repo': {
                'excluded_dirs': ['.git', '__pycache__'],
                'source_code_extensions': ['.py']
            }
        }

        # Create pipeline
        pipeline = KBOrchestrator(temp_repo, config, kb=kb)

        # Override repo_id for testing
        pipeline.repo_id = test_repo_id
        pipeline.parser.repo_id = test_repo_id

        # Build KB
        result = pipeline.build_knowledge_base()

        # Verify
        assert result.total_files == 2
        assert result.total_functions >= 3  # function1, method1, function2
        assert result.total_classes >= 1  # Class1

        # Check KB stats
        stats = pipeline.get_repository_stats()
        assert stats['files'] == 2

    def test_incremental_update(self, temp_repo, kb, test_repo_id):
        """Test incremental KB updates"""
        # Create initial file
        test_file = Path(temp_repo) / "module.py"
        test_file.write_text("""
def original_function():
    pass
""")

        # Create config
        config = {
            'knowledge_base': {
                'enabled': True,
                'neo4j': {
                    'uri': 'bolt://localhost:7687',
                    'user': 'neo4j',
                    'password': os.environ.get('NEO4J_PASSWORD', 'password'),
                    'database': 'neo4j'
                },
                'build': {
                    'parallel_workers': 1,
                    'auto_build': True
                },
                'incremental': {
                    'enabled': True
                }
            },
            'repo': {
                'excluded_dirs': ['.git', '__pycache__'],
                'source_code_extensions': ['.py']
            }
        }

        # Create pipeline and build
        pipeline = KBOrchestrator(temp_repo, config, kb=kb)
        pipeline.repo_id = test_repo_id
        pipeline.parser.repo_id = test_repo_id

        build_result = pipeline.build_knowledge_base()
        assert build_result.total_files == 1
        assert build_result.total_functions == 1

        # Modify file
        import time
        time.sleep(0.1)  # Ensure mtime changes
        test_file.write_text("""
def original_function():
    pass

def new_function():
    pass
""")

        # Update KB
        update_result = pipeline.update_knowledge_base()

        # Should detect 1 modified file
        assert update_result.get('files_modified', 0) == 1

        # Verify new function is in KB
        stats = pipeline.get_repository_stats()
        assert stats.get('total_functions', 0) == 2


@pytest.mark.integration
class TestFileChangeDetector:
    """Test suite for file change detection"""

    def test_detect_added_files(self, temp_repo):
        """Test detecting added files"""
        detector = FileChangeDetector(temp_repo)

        # Initial scan (no files)
        detector.force_scan()

        # Add file
        (Path(temp_repo) / "new_file.py").write_text("def test(): pass")

        # Detect changes
        changes = detector.detect_changes()

        assert len(changes.added) == 1
        assert "new_file.py" in changes.added

    def test_detect_modified_files(self, temp_repo):
        """Test detecting modified files"""
        test_file = Path(temp_repo) / "test.py"
        test_file.write_text("def test1(): pass")

        detector = FileChangeDetector(temp_repo)
        detector.force_scan()

        # Modify file
        import time
        time.sleep(0.1)
        test_file.write_text("def test2(): pass")

        # Detect changes
        changes = detector.detect_changes()

        assert len(changes.modified) == 1
        assert "test.py" in changes.modified

    def test_detect_deleted_files(self, temp_repo):
        """Test detecting deleted files"""
        test_file = Path(temp_repo) / "test.py"
        test_file.write_text("def test(): pass")

        detector = FileChangeDetector(temp_repo)
        detector.force_scan()

        # Delete file
        test_file.unlink()

        # Detect changes
        changes = detector.detect_changes()

        assert len(changes.deleted) == 1
        assert "test.py" in changes.deleted

    def test_no_changes(self, temp_repo):
        """Test when no changes detected"""
        (Path(temp_repo) / "test.py").write_text("def test(): pass")

        detector = FileChangeDetector(temp_repo)
        detector.force_scan()

        # No changes
        changes = detector.detect_changes(save_state=False)

        assert not changes.has_changes()
        assert changes.total_changes() == 0
