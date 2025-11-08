"""
Unit tests for Python AST Parser

Tests the structural analysis of Python code using AST parsing.
"""

import os
import tempfile
import pytest
from pathlib import Path

from cf.knowledge.structural.ast_parser import PythonASTParser
from cf.knowledge.structural.schema import FunctionNode, ClassNode


@pytest.fixture
def temp_repo():
    """Create a temporary repository for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def parser(temp_repo):
    """Create AST parser instance"""
    return PythonASTParser(temp_repo, "test-repo-id")


class TestPythonASTParser:
    """Test suite for Python AST parser"""

    def test_parse_simple_function(self, parser, temp_repo):
        """Test parsing a simple function"""
        # Create test file
        test_file = Path(temp_repo) / "test_simple.py"
        test_file.write_text("""
def hello_world():
    '''Say hello'''
    print("Hello, World!")
""")

        # Parse file
        result = parser.parse_file(str(test_file))

        # Verify results
        assert result is not None
        assert result.file_node.language == "python"
        assert len(result.functions) == 1

        func = result.functions[0]
        assert func.name == "hello_world"
        assert func.docstring == "Say hello"
        assert func.parameters == []
        assert not func.is_async
        assert not func.is_method

    def test_parse_function_with_parameters(self, parser, temp_repo):
        """Test parsing function with parameters and return type"""
        test_file = Path(temp_repo) / "test_params.py"
        test_file.write_text("""
def add_numbers(a: int, b: int) -> int:
    '''Add two numbers'''
    return a + b
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert len(result.functions) == 1

        func = result.functions[0]
        assert func.name == "add_numbers"
        assert func.parameters == ["a", "b"]
        assert func.return_type == "int"

    def test_parse_async_function(self, parser, temp_repo):
        """Test parsing async function"""
        test_file = Path(temp_repo) / "test_async.py"
        test_file.write_text("""
async def fetch_data(url: str):
    '''Fetch data from URL'''
    return await client.get(url)
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert len(result.functions) == 1

        func = result.functions[0]
        assert func.name == "fetch_data"
        assert func.is_async
        assert func.parameters == ["url"]

    def test_parse_class(self, parser, temp_repo):
        """Test parsing class definition"""
        test_file = Path(temp_repo) / "test_class.py"
        test_file.write_text("""
class Person:
    '''A person class'''

    def __init__(self, name: str):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}"
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert len(result.classes) == 1
        assert len(result.functions) == 2  # __init__ and greet

        cls = result.classes[0]
        assert cls.name == "Person"
        assert cls.docstring == "A person class"
        assert cls.num_methods == 2

        # Check methods
        methods = [f for f in result.functions if f.is_method]
        assert len(methods) == 2
        method_names = {m.name for m in methods}
        assert "__init__" in method_names
        assert "greet" in method_names

    def test_parse_class_inheritance(self, parser, temp_repo):
        """Test parsing class with inheritance"""
        test_file = Path(temp_repo) / "test_inheritance.py"
        test_file.write_text("""
class Animal:
    pass

class Dog(Animal):
    def bark(self):
        return "Woof!"

class Cat(Animal):
    pass
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert len(result.classes) == 3

        # Find Dog class
        dog_class = next(c for c in result.classes if c.name == "Dog")
        assert "Animal" in dog_class.base_classes

        # Check inheritance relationships
        inherit_rels = [r for r in result.relationships if r.rel_type.value == "INHERITS"]
        assert len(inherit_rels) == 2  # Dog and Cat both inherit from Animal

    def test_parse_imports(self, parser, temp_repo):
        """Test parsing import statements"""
        test_file = Path(temp_repo) / "test_imports.py"
        test_file.write_text("""
import os
import sys
from pathlib import Path
from typing import List, Dict
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert len(result.modules) >= 2  # At least os and sys

        module_names = {m.name for m in result.modules}
        assert "os" in module_names
        assert "sys" in module_names

        # Check import relationships
        import_rels = [r for r in result.relationships if r.rel_type.value == "IMPORTS"]
        assert len(import_rels) >= 2

    def test_parse_function_calls(self, parser, temp_repo):
        """Test extracting function calls"""
        test_file = Path(temp_repo) / "test_calls.py"
        test_file.write_text("""
def process_data(data):
    cleaned = clean_data(data)
    validated = validate_data(cleaned)
    return save_data(validated)

def clean_data(data):
    return data.strip()
""")

        result = parser.parse_file(str(test_file))

        assert result is not None

        # Check for call relationships
        call_rels = [r for r in result.relationships if r.rel_type.value == "CALLS"]
        assert len(call_rels) >= 3  # process_data calls clean_data, validate_data, save_data

    def test_parse_private_function(self, parser, temp_repo):
        """Test identifying private functions"""
        test_file = Path(temp_repo) / "test_private.py"
        test_file.write_text("""
def public_function():
    pass

def _private_function():
    pass

def __very_private():
    pass
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert len(result.functions) == 3

        public = next(f for f in result.functions if f.name == "public_function")
        assert not public.is_private

        private = next(f for f in result.functions if f.name == "_private_function")
        assert private.is_private

    def test_parse_static_method(self, parser, temp_repo):
        """Test identifying static methods"""
        test_file = Path(temp_repo) / "test_static.py"
        test_file.write_text("""
class Utils:
    @staticmethod
    def helper():
        return "Help!"

    def regular_method(self):
        return "Regular"
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        methods = [f for f in result.functions if f.is_method]
        assert len(methods) == 2

        static = next(f for f in methods if f.name == "helper")
        assert static.is_static

        regular = next(f for f in methods if f.name == "regular_method")
        assert not regular.is_static

    def test_parse_complexity(self, parser, temp_repo):
        """Test cyclomatic complexity calculation"""
        test_file = Path(temp_repo) / "test_complexity.py"
        test_file.write_text("""
def simple():
    return 1

def complex_function(x, y):
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x - y
    else:
        return 0
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert len(result.functions) == 2

        simple = next(f for f in result.functions if f.name == "simple")
        assert simple.cyclomatic_complexity == 1

        complex_func = next(f for f in result.functions if f.name == "complex_function")
        assert complex_func.cyclomatic_complexity > 1

    def test_parse_invalid_syntax(self, parser, temp_repo):
        """Test handling of syntax errors"""
        test_file = Path(temp_repo) / "test_invalid.py"
        test_file.write_text("""
def broken_function(
    # Missing closing parenthesis
    return "broken"
""")

        result = parser.parse_file(str(test_file))

        # Should return None for syntax errors
        assert result is None

    def test_parse_qualified_names(self, parser, temp_repo):
        """Test qualified name generation"""
        test_file = Path(temp_repo) / "mymodule/utils.py"
        os.makedirs(Path(temp_repo) / "mymodule", exist_ok=True)
        test_path = Path(temp_repo) / "mymodule/utils.py"
        test_path.write_text("""
class Helper:
    def process(self):
        pass

def standalone():
    pass
""")

        result = parser.parse_file(str(test_path))

        assert result is not None

        # Check qualified names
        helper_class = next(c for c in result.classes if c.name == "Helper")
        assert "Helper" in helper_class.qualified_name

        process_method = next(f for f in result.functions if f.name == "process")
        assert "Helper" in process_method.qualified_name
        assert "process" in process_method.qualified_name

    def test_file_hash_generation(self, parser, temp_repo):
        """Test file hash is generated correctly"""
        test_file = Path(temp_repo) / "test_hash.py"
        content = "def test(): pass"
        test_file.write_text(content)

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert result.file_node.hash is not None
        assert len(result.file_node.hash) == 32  # MD5 hash length

    def test_parse_multiple_decorators(self, parser, temp_repo):
        """Test parsing functions with multiple decorators"""
        test_file = Path(temp_repo) / "test_decorators.py"
        test_file.write_text("""
class MyClass:
    @property
    @staticmethod
    def decorated():
        return "decorated"
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        decorated = next(f for f in result.functions if f.name == "decorated")
        assert decorated.is_static

    def test_structural_data_counts(self, parser, temp_repo):
        """Test total node and relationship counts"""
        test_file = Path(temp_repo) / "test_counts.py"
        test_file.write_text("""
import os

class DataProcessor:
    def __init__(self):
        self.data = []

    def process(self, item):
        return self._clean(item)

    def _clean(self, item):
        return item.strip()

def helper():
    pass
""")

        result = parser.parse_file(str(test_file))

        assert result is not None
        assert result.total_nodes > 0  # File + functions + classes + modules
        assert result.total_relationships > 0  # Imports, calls, contains

        # Verify specific counts
        assert len(result.functions) == 4  # __init__, process, _clean, helper
        assert len(result.classes) == 1  # DataProcessor
        assert len(result.modules) >= 1  # os


@pytest.mark.integration
class TestPythonASTParserIntegration:
    """Integration tests for AST parser"""

    def test_parse_real_python_file(self, parser, temp_repo):
        """Test parsing a real-world Python file"""
        # Create a more realistic file
        test_file = Path(temp_repo) / "service.py"
        test_file.write_text("""
'''
User service module
'''

from typing import Optional, List
from dataclasses import dataclass

@dataclass
class User:
    '''User model'''
    id: int
    name: str
    email: str

    def validate(self) -> bool:
        '''Validate user data'''
        return bool(self.email and '@' in self.email)


class UserService:
    '''Service for managing users'''

    def __init__(self, db_connection):
        self.db = db_connection
        self._cache = {}

    def get_user(self, user_id: int) -> Optional[User]:
        '''Get user by ID'''
        if user_id in self._cache:
            return self._cache[user_id]

        user_data = self.db.query("SELECT * FROM users WHERE id = ?", user_id)
        if user_data:
            user = User(**user_data)
            self._cache[user_id] = user
            return user
        return None

    def create_user(self, name: str, email: str) -> User:
        '''Create new user'''
        user_id = self.db.insert("INSERT INTO users (name, email) VALUES (?, ?)", name, email)
        user = User(id=user_id, name=name, email=email)

        if user.validate():
            self._cache[user_id] = user
            return user
        else:
            raise ValueError("Invalid user data")

    @staticmethod
    def hash_password(password: str) -> str:
        '''Hash password'''
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()
""")

        result = parser.parse_file(str(test_file))

        # Comprehensive validation
        assert result is not None

        # Check classes
        assert len(result.classes) == 2
        class_names = {c.name for c in result.classes}
        assert "User" in class_names
        assert "UserService" in class_names

        # Check functions/methods
        assert len(result.functions) >= 5
        func_names = {f.name for f in result.functions}
        assert "validate" in func_names
        assert "get_user" in func_names
        assert "create_user" in func_names
        assert "hash_password" in func_names

        # Check imports
        module_names = {m.name for m in result.modules}
        assert "typing" in module_names
        assert "dataclasses" in module_names

        # Check relationships
        assert len(result.relationships) > 0
