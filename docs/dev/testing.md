# Testing Guide

This document provides comprehensive guidelines for testing CodeFusion, including unit tests, integration tests, and testing best practices.

## Testing Overview

CodeFusion uses a multi-layered testing approach to ensure reliability and performance:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Performance Tests**: Ensure acceptable performance characteristics
- **Configuration Tests**: Validate configuration handling

## Test Framework

CodeFusion uses **pytest** as the primary testing framework with additional tools:

```bash
# Install testing dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=cf --cov-report=html
```

## Test Structure

### Directory Organization

```
tests/
├── __init__.py
├── unit/
│   ├── test_config.py          # Configuration testing
│   ├── test_types.py           # Type system testing
│   ├── test_exceptions.py      # Exception handling
│   ├── test_aci/
│   │   ├── test_repo.py        # Repository abstraction
│   │   ├── test_environment.py # Environment management
│   │   └── test_system_access.py
│   ├── test_kb/
│   │   ├── test_knowledge_base.py
│   │   ├── test_vector_kb.py
│   │   ├── test_content_analyzer.py
│   │   └── test_relationship_detector.py
│   ├── test_agents/
│   │   ├── test_reasoning_agent.py
│   │   ├── test_plan_then_act.py
│   │   └── test_sense_then_act.py
│   ├── test_llm/
│   │   └── test_llm_model.py
│   └── test_indexer/
│       └── test_code_indexer.py
├── integration/
│   ├── test_indexing_workflow.py
│   ├── test_query_workflow.py
│   ├── test_exploration_strategies.py
│   └── test_knowledge_base_integration.py
├── e2e/
│   ├── test_cli_commands.py
│   ├── test_complete_workflows.py
│   └── test_configuration_scenarios.py
├── performance/
│   ├── test_indexing_performance.py
│   ├── test_query_performance.py
│   └── test_memory_usage.py
├── fixtures/
│   ├── sample_repos/
│   ├── test_configs/
│   └── mock_data/
└── conftest.py                 # Shared test configuration
```

## Unit Testing

### Configuration Testing

```python
# tests/unit/test_config.py
import pytest
import tempfile
import yaml
from cf.config import CfConfig

class TestCfConfig:
    def test_default_config(self):
        """Test default configuration values"""
        config = CfConfig()
        assert config.llm_model == "gpt-4o"
        assert config.kb_type == "vector"
        assert config.exploration_strategy == "react"
        assert config.max_exploration_depth == 5

    def test_config_from_dict(self):
        """Test configuration creation from dictionary"""
        config_dict = {
            "llm_model": "gpt-4",
            "kb_type": "neo4j",
            "exploration_strategy": "plan_act"
        }
        config = CfConfig.from_dict(config_dict)
        assert config.llm_model == "gpt-4"
        assert config.kb_type == "neo4j"
        assert config.exploration_strategy == "plan_act"

    def test_config_from_file(self):
        """Test configuration loading from YAML file"""
        config_data = {
            "llm_model": "gpt-3.5-turbo",
            "kb_type": "vector",
            "max_file_size": 2097152
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        config = CfConfig.from_file(config_path)
        assert config.llm_model == "gpt-3.5-turbo"
        assert config.max_file_size == 2097152

    def test_config_validation(self):
        """Test configuration validation"""
        # Valid configuration
        config = CfConfig(llm_model="gpt-4", kb_type="vector")
        config.validate()  # Should not raise

        # Invalid configuration
        with pytest.raises(ValueError):
            invalid_config = CfConfig(exploration_strategy="invalid_strategy")
            invalid_config.validate()
```

### Repository Testing

```python
# tests/unit/test_aci/test_repo.py
import pytest
import tempfile
import os
from cf.aci.repo import LocalCodeRepo

class TestLocalCodeRepo:
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            os.makedirs(os.path.join(temp_dir, "src"))
            
            # Python file
            with open(os.path.join(temp_dir, "src", "main.py"), "w") as f:
                f.write("""
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
""")
            
            # JavaScript file
            with open(os.path.join(temp_dir, "src", "app.js"), "w") as f:
                f.write("""
function greet(name) {
    console.log(`Hello, ${name}!`);
}

greet("World");
""")
            
            # README
            with open(os.path.join(temp_dir, "README.md"), "w") as f:
                f.write("# Test Repository\n\nThis is a test repository.")
            
            yield temp_dir

    def test_repo_initialization(self, temp_repo):
        """Test repository initialization"""
        repo = LocalCodeRepo(temp_repo)
        assert repo.repo_path == temp_repo
        assert os.path.exists(repo.repo_path)

    def test_list_files(self, temp_repo):
        """Test file listing functionality"""
        repo = LocalCodeRepo(temp_repo)
        files = repo.list_files()
        
        assert len(files) >= 3
        assert any("main.py" in f for f in files)
        assert any("app.js" in f for f in files)
        assert any("README.md" in f for f in files)

    def test_get_file_content(self, temp_repo):
        """Test file content retrieval"""
        repo = LocalCodeRepo(temp_repo)
        main_py_path = os.path.join(temp_repo, "src", "main.py")
        
        content = repo.get_file_content(main_py_path)
        assert "def hello_world():" in content
        assert "print(\"Hello, World!\")" in content

    def test_get_repository_structure(self, temp_repo):
        """Test repository structure analysis"""
        repo = LocalCodeRepo(temp_repo)
        structure = repo.get_repository_structure()
        
        assert "files" in structure
        assert "directories" in structure
        assert structure["files"] >= 3
        assert "src" in structure["directories"]
```

### Knowledge Base Testing

```python
# tests/unit/test_kb/test_knowledge_base.py
import pytest
import tempfile
from cf.kb.knowledge_base import CodeKnowledgeBase
from cf.types import Entity, EntityType, Relationship, RelationshipType

class TestCodeKnowledgeBase:
    @pytest.fixture
    def temp_kb_path(self):
        """Create temporary knowledge base path"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_kb_initialization(self, temp_kb_path):
        """Test knowledge base initialization"""
        kb = CodeKnowledgeBase("text", temp_kb_path)
        assert kb.kb_type == "text"
        assert kb.kb_path == temp_kb_path

    def test_store_and_retrieve_entities(self, temp_kb_path):
        """Test entity storage and retrieval"""
        kb = CodeKnowledgeBase("text", temp_kb_path)
        
        # Create test entities
        entities = [
            Entity(
                id="1",
                type=EntityType.FUNCTION,
                name="hello_world",
                content="def hello_world():\n    print('Hello, World!')",
                file_path="main.py",
                line_number=1
            ),
            Entity(
                id="2", 
                type=EntityType.CLASS,
                name="MyClass",
                content="class MyClass:\n    pass",
                file_path="classes.py",
                line_number=1
            )
        ]
        
        # Store entities
        kb.store_entities(entities)
        
        # Retrieve entities
        retrieved = kb.query_entities("hello_world")
        assert len(retrieved) >= 1
        assert any(e.name == "hello_world" for e in retrieved)

    def test_relationships(self, temp_kb_path):
        """Test relationship storage and retrieval"""
        kb = CodeKnowledgeBase("text", temp_kb_path)
        
        # Create test relationship
        relationship = Relationship(
            id="rel_1",
            source_id="1",
            target_id="2",
            type=RelationshipType.CALLS
        )
        
        # Store relationship
        kb.store_relationships([relationship])
        
        # Retrieve relationships
        relationships = kb.get_relationships("1")
        assert len(relationships) >= 1
        assert relationships[0].type == RelationshipType.CALLS
```

### LLM Testing

```python
# tests/unit/test_llm/test_llm_model.py
import pytest
from unittest.mock import Mock, patch
from cf.llm.llm_model import LlmModel
from cf.config import CfConfig

class TestLlmModel:
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        config = CfConfig()
        config.llm_model = "gpt-3.5-turbo"
        config.llm_api_key = "test-key"
        return config

    @patch('cf.llm.llm_model.litellm')
    def test_llm_initialization(self, mock_litellm, mock_config):
        """Test LLM model initialization"""
        llm = LlmModel(mock_config)
        assert llm.model == "gpt-3.5-turbo"
        assert llm.config == mock_config

    @patch('cf.llm.llm_model.litellm')
    def test_generate_response(self, mock_litellm, mock_config):
        """Test response generation"""
        # Mock LiteLLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test response"
        mock_litellm.completion.return_value = mock_response
        
        llm = LlmModel(mock_config)
        response = llm.generate_response("Test prompt")
        
        assert response == "Test response"
        mock_litellm.completion.assert_called_once()

    @patch('cf.llm.llm_model.litellm')
    def test_error_handling(self, mock_litellm, mock_config):
        """Test LLM error handling"""
        # Mock LiteLLM exception
        mock_litellm.completion.side_effect = Exception("API Error")
        
        llm = LlmModel(mock_config)
        
        with pytest.raises(Exception):
            llm.generate_response("Test prompt")
```

## Integration Testing

### Indexing Workflow Integration

```python
# tests/integration/test_indexing_workflow.py
import pytest
import tempfile
import os
from cf.config import CfConfig
from cf.indexer.code_indexer import CodeIndexer
from cf.kb.knowledge_base import CodeKnowledgeBase

class TestIndexingWorkflow:
    @pytest.fixture
    def integration_setup(self):
        """Set up integration test environment"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test repository
            repo_path = os.path.join(temp_dir, "test_repo")
            os.makedirs(repo_path)
            
            # Create test files
            with open(os.path.join(repo_path, "main.py"), "w") as f:
                f.write("""
import os
from typing import List

class DataProcessor:
    def __init__(self, data_path: str):
        self.data_path = data_path
    
    def process_files(self, files: List[str]) -> dict:
        results = {}
        for file in files:
            results[file] = self.process_file(file)
        return results
    
    def process_file(self, file: str) -> str:
        with open(os.path.join(self.data_path, file)) as f:
            return f.read()

def main():
    processor = DataProcessor("/data")
    files = ["file1.txt", "file2.txt"]
    results = processor.process_files(files)
    print(results)

if __name__ == "__main__":
    main()
""")
            
            # Create knowledge base path
            kb_path = os.path.join(temp_dir, "kb")
            
            # Create configuration
            config = CfConfig()
            config.kb_type = "text"
            config.max_file_size = 1048576
            
            yield {
                "repo_path": repo_path,
                "kb_path": kb_path,
                "config": config
            }

    def test_full_indexing_workflow(self, integration_setup):
        """Test complete indexing workflow"""
        repo_path = integration_setup["repo_path"]
        kb_path = integration_setup["kb_path"] 
        config = integration_setup["config"]
        
        # Initialize components
        kb = CodeKnowledgeBase(config.kb_type, kb_path)
        indexer = CodeIndexer(config)
        
        # Run indexing
        result = indexer.index_repository(repo_path, kb)
        
        # Verify results
        assert result.success
        assert result.files_processed >= 1
        assert result.entities_extracted >= 3  # class, methods, functions
        
        # Verify entities in knowledge base
        entities = kb.query_entities("DataProcessor")
        assert len(entities) >= 1
        assert any(e.name == "DataProcessor" for e in entities)
        
        functions = kb.query_entities("process_files")
        assert len(functions) >= 1
        
        # Verify relationships
        relationships = kb.get_relationships("DataProcessor")
        assert len(relationships) >= 1
```

### Query Workflow Integration

```python
# tests/integration/test_query_workflow.py
import pytest
from unittest.mock import Mock, patch
from cf.config import CfConfig
from cf.agents.reasoning_agent import ReasoningAgent
from cf.kb.knowledge_base import CodeKnowledgeBase

class TestQueryWorkflow:
    @pytest.fixture
    def query_setup(self):
        """Set up query test environment"""
        # Mock configuration
        config = CfConfig()
        config.llm_model = "gpt-3.5-turbo"
        config.exploration_strategy = "react"
        
        # Mock knowledge base with test data
        kb = Mock(spec=CodeKnowledgeBase)
        
        # Mock entities
        mock_entities = [
            Mock(name="DataProcessor", type="class", content="class DataProcessor:..."),
            Mock(name="process_files", type="function", content="def process_files(...):")
        ]
        kb.query_entities.return_value = mock_entities
        kb.get_relationships.return_value = []
        
        yield {
            "config": config,
            "kb": kb
        }

    @patch('cf.agents.reasoning_agent.LlmModel')
    def test_query_processing(self, mock_llm_class, query_setup):
        """Test query processing workflow"""
        config = query_setup["config"]
        kb = query_setup["kb"]
        
        # Mock LLM responses
        mock_llm = Mock()
        mock_llm.generate_response.return_value = "The DataProcessor class handles file processing..."
        mock_llm_class.return_value = mock_llm
        
        # Initialize agent
        agent = ReasoningAgent(config)
        
        # Process query
        result = agent.process_query("How does file processing work?", kb)
        
        # Verify results
        assert result is not None
        assert "DataProcessor" in result or "processing" in result.lower()
        
        # Verify interactions
        kb.query_entities.assert_called()
        mock_llm.generate_response.assert_called()
```

## End-to-End Testing

### CLI Command Testing

```python
# tests/e2e/test_cli_commands.py
import pytest
import subprocess
import tempfile
import os

class TestCLICommands:
    @pytest.fixture
    def test_repo(self):
        """Create test repository for CLI testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create simple Python file
            with open(os.path.join(temp_dir, "hello.py"), "w") as f:
                f.write("print('Hello, World!')")
            
            yield temp_dir

    def test_index_command(self, test_repo):
        """Test cf index command"""
        result = subprocess.run(
            ["python", "-m", "cf", "index", test_repo],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        assert result.returncode == 0
        assert "indexed" in result.stdout.lower() or "complete" in result.stdout.lower()

    def test_stats_command(self, test_repo):
        """Test cf stats command"""
        # First index the repository
        subprocess.run(
            ["python", "-m", "cf", "index", test_repo],
            capture_output=True,
            timeout=60
        )
        
        # Then get stats
        result = subprocess.run(
            ["python", "-m", "cf", "stats"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        assert "files" in result.stdout.lower()

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OpenAI API key"
    )
    def test_query_command(self, test_repo):
        """Test cf query command (requires API key)"""
        # First index the repository
        subprocess.run(
            ["python", "-m", "cf", "index", test_repo],
            capture_output=True,
            timeout=60
        )
        
        # Then query
        result = subprocess.run(
            ["python", "-m", "cf", "query", "What does this code do?"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        assert result.returncode == 0
        assert len(result.stdout) > 0
```

### Complete Workflow Testing

```python
# tests/e2e/test_complete_workflows.py
import pytest
import tempfile
import os
from cf.run.explore_single_repo import explore_repository

class TestCompleteWorkflows:
    @pytest.fixture
    def sample_project(self):
        """Create sample project for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create project structure
            src_dir = os.path.join(temp_dir, "src")
            os.makedirs(src_dir)
            
            # Main application file
            with open(os.path.join(src_dir, "app.py"), "w") as f:
                f.write("""
from flask import Flask, jsonify
from database import Database

app = Flask(__name__)
db = Database()

@app.route('/api/users')
def get_users():
    users = db.get_all_users()
    return jsonify(users)

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(debug=True)
""")
            
            # Database module
            with open(os.path.join(src_dir, "database.py"), "w") as f:
                f.write("""
import sqlite3
from typing import List, Dict

class Database:
    def __init__(self, db_path: str = "app.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL
                )
            ''')
    
    def get_all_users(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM users")
            return [{"id": row[0], "name": row[1], "email": row[2]} 
                    for row in cursor.fetchall()]
""")
            
            # Configuration file
            with open(os.path.join(temp_dir, "config.yaml"), "w") as f:
                f.write("""
kb_type: text
max_file_size: 1048576
excluded_dirs:
  - ".git"
  - "__pycache__"
exploration_strategy: react
max_exploration_depth: 3
""")
            
            # README
            with open(os.path.join(temp_dir, "README.md"), "w") as f:
                f.write("""
# Sample Flask Application

A simple Flask web application with SQLite database.

## Features
- User management API
- Health check endpoint
- SQLite database integration

## Usage
```bash
python src/app.py
```
""")
            
            yield temp_dir

    def test_complete_exploration_workflow(self, sample_project):
        """Test complete repository exploration"""
        config_path = os.path.join(sample_project, "config.yaml")
        
        # Run exploration
        result = explore_repository(sample_project, config_path)
        
        # Verify exploration completed
        assert result.success
        assert result.files_processed >= 3  # app.py, database.py, README.md
        assert result.entities_extracted >= 5  # classes, functions, routes
        
        # Verify specific entities were found
        entities = result.entities
        entity_names = [e.name for e in entities]
        
        assert "Database" in entity_names
        assert "get_users" in entity_names or "get_all_users" in entity_names
        assert "Flask" in str(entities)  # Should detect Flask usage
```

## Performance Testing

### Indexing Performance

```python
# tests/performance/test_indexing_performance.py
import pytest
import time
import tempfile
import os
from cf.indexer.code_indexer import CodeIndexer
from cf.config import CfConfig

class TestIndexingPerformance:
    @pytest.fixture
    def large_repo(self):
        """Create large repository for performance testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create many files to test performance
            for i in range(100):
                file_path = os.path.join(temp_dir, f"file_{i}.py")
                with open(file_path, "w") as f:
                    f.write(f"""
class Class{i}:
    def __init__(self):
        self.value = {i}
    
    def method_{i}(self):
        return self.value * 2
    
    def process_data(self, data):
        result = []
        for item in data:
            result.append(item + self.value)
        return result

def function_{i}():
    obj = Class{i}()
    return obj.method_{i}()
""")
            
            yield temp_dir

    def test_indexing_performance_small_repo(self):
        """Test indexing performance on small repository"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create small test file
            with open(os.path.join(temp_dir, "test.py"), "w") as f:
                f.write("print('Hello, World!')")
            
            config = CfConfig()
            config.kb_type = "text"
            
            indexer = CodeIndexer(config)
            
            start_time = time.time()
            result = indexer.index_repository(temp_dir)
            end_time = time.time()
            
            duration = end_time - start_time
            
            # Should complete very quickly
            assert duration < 5.0
            assert result.success

    def test_indexing_performance_large_repo(self, large_repo):
        """Test indexing performance on larger repository"""
        config = CfConfig()
        config.kb_type = "text"
        config.batch_size = 50
        
        indexer = CodeIndexer(config)
        
        start_time = time.time()
        result = indexer.index_repository(large_repo)
        end_time = time.time()
        
        duration = end_time - start_time
        
        # Should complete within reasonable time
        assert duration < 120.0  # 2 minutes max
        assert result.success
        assert result.files_processed == 100

    def test_memory_usage_during_indexing(self, large_repo):
        """Test memory usage stays within acceptable limits"""
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        config = CfConfig()
        config.kb_type = "text"
        config.batch_size = 25  # Smaller batches for memory efficiency
        
        indexer = CodeIndexer(config)
        result = indexer.index_repository(large_repo)
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        # Should not use excessive memory
        assert memory_increase < 200  # Less than 200MB increase
        assert result.success
```

## Test Configuration

### Pytest Configuration

```python
# conftest.py - Shared test configuration
import pytest
import tempfile
import os
from cf.config import CfConfig

@pytest.fixture(scope="session")
def test_config():
    """Create test configuration"""
    config = CfConfig()
    config.kb_type = "text"
    config.llm_model = "gpt-3.5-turbo"
    config.max_file_size = 1048576
    config.batch_size = 10
    config.max_workers = 2
    return config

@pytest.fixture
def temp_directory():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def sample_python_file():
    """Create sample Python file for testing"""
    content = """
import os
from typing import List

def process_files(files: List[str]) -> dict:
    \"\"\"Process a list of files and return results.\"\"\"
    results = {}
    for file in files:
        if os.path.exists(file):
            with open(file, 'r') as f:
                results[file] = len(f.read())
    return results

class FileProcessor:
    def __init__(self, base_path: str):
        self.base_path = base_path
    
    def process_directory(self) -> dict:
        files = os.listdir(self.base_path)
        return process_files([os.path.join(self.base_path, f) for f in files])
"""
    return content

# Pytest markers
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"  
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
```

### Test Execution

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/ -m integration

# Run with coverage
pytest --cov=cf --cov-report=html --cov-report=term

# Run performance tests
pytest tests/performance/ -m performance

# Run specific test file
pytest tests/unit/test_config.py

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x

# Run tests matching pattern
pytest -k "test_config"

# Run slow tests only
pytest -m slow

# Skip slow tests
pytest -m "not slow"
```

## Test Data Management

### Test Fixtures

Create reusable test data:

```python
# tests/fixtures/test_repositories.py
import os
import tempfile

def create_python_project():
    """Create sample Python project structure"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create package structure
        package_dir = os.path.join(temp_dir, "mypackage")
        os.makedirs(package_dir)
        
        # __init__.py
        with open(os.path.join(package_dir, "__init__.py"), "w") as f:
            f.write('__version__ = "1.0.0"')
        
        # main.py
        with open(os.path.join(package_dir, "main.py"), "w") as f:
            f.write("""
from .utils import helper_function

def main():
    result = helper_function("test")
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
""")
        
        # utils.py
        with open(os.path.join(package_dir, "utils.py"), "w") as f:
            f.write("""
def helper_function(text: str) -> str:
    return text.upper()

class UtilityClass:
    def __init__(self, value: int):
        self.value = value
    
    def double(self) -> int:
        return self.value * 2
""")
        
        yield temp_dir
```

### Mock Data

```python
# tests/fixtures/mock_data.py
from cf.types import Entity, EntityType, Relationship, RelationshipType

def create_mock_entities():
    """Create mock entities for testing"""
    return [
        Entity(
            id="entity_1",
            type=EntityType.CLASS,
            name="TestClass",
            content="class TestClass:\n    pass",
            file_path="test.py",
            line_number=1
        ),
        Entity(
            id="entity_2", 
            type=EntityType.FUNCTION,
            name="test_function",
            content="def test_function():\n    return True",
            file_path="test.py",
            line_number=4
        )
    ]

def create_mock_relationships():
    """Create mock relationships for testing"""
    return [
        Relationship(
            id="rel_1",
            source_id="entity_1",
            target_id="entity_2",
            type=RelationshipType.CONTAINS
        )
    ]
```

## Continuous Integration

### GitHub Actions Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.10, 3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Run linting
      run: |
        flake8 cf/
        black --check cf/
        isort --check-only cf/
    
    - name: Run type checking
      run: mypy cf/
    
    - name: Run unit tests
      run: pytest tests/unit/ -v
    
    - name: Run integration tests
      run: pytest tests/integration/ -v -m integration
    
    - name: Run performance tests
      run: pytest tests/performance/ -v -m performance
    
    - name: Generate coverage report
      run: |
        pytest --cov=cf --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Best Practices

### Test Writing Guidelines

1. **Test Names**: Use descriptive test names that explain what is being tested
2. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
3. **Test Isolation**: Each test should be independent and not rely on other tests
4. **Mock External Dependencies**: Use mocks for external services, APIs, and file systems
5. **Test Edge Cases**: Include tests for boundary conditions and error scenarios

### Performance Testing

1. **Set Realistic Benchmarks**: Based on expected usage patterns
2. **Monitor Memory Usage**: Ensure tests don't cause memory leaks
3. **Test Different Repository Sizes**: Small, medium, and large repositories
4. **Configuration Variations**: Test different configuration combinations

### Debugging Tests

```bash
# Run tests with debugging
pytest --pdb

# Run specific test with output
pytest tests/unit/test_config.py::TestCfConfig::test_default_config -s

# Debug with print statements
pytest -s --capture=no

# Run tests with specific log level
pytest --log-cli-level=DEBUG
```

## Next Steps

- Review [performance guide](performance.md) for optimization techniques
- Check [architecture documentation](architecture.md) for system design
- See [contributing guide](contributing.md) for development workflow