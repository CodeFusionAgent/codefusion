"""
Neo4j Graph Schema for Structural Knowledge Base

Defines node types, relationships, and data structures for storing
code structure in a graph database.

Node Types:
- File: Source code files
- Function: Function/method definitions
- Class: Class definitions
- Variable: Global variables, class attributes
- Module: Python modules/packages

Relationships:
- CONTAINS: File contains Function/Class
- CALLS: Function calls another Function
- IMPORTS: File imports Module/File
- INHERITS: Class inherits from Class
- USES: Function uses Variable
- DEFINES: Class/Function defines Variable
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class NodeType(Enum):
    """Graph node types"""
    FILE = "File"
    FUNCTION = "Function"
    CLASS = "Class"
    VARIABLE = "Variable"
    MODULE = "Module"


class RelationType(Enum):
    """Graph relationship types"""
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    IMPORTS = "IMPORTS"
    INHERITS = "INHERITS"
    USES = "USES"
    DEFINES = "DEFINES"


@dataclass
class FileNode:
    """Represents a source code file"""
    path: str  # Relative path from repo root
    language: str  # python, javascript, go, etc.
    size: int  # File size in bytes
    last_modified: float  # Unix timestamp
    lines_of_code: int
    repo_id: str  # Repository identifier

    # Optional metadata
    encoding: str = "utf-8"
    hash: Optional[str] = None  # File content hash for change detection

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j insertion"""
        return {
            'path': self.path,
            'language': self.language,
            'size': self.size,
            'last_modified': self.last_modified,
            'lines_of_code': self.lines_of_code,
            'repo_id': self.repo_id,
            'encoding': self.encoding,
            'hash': self.hash
        }


@dataclass
class FunctionNode:
    """Represents a function or method"""
    name: str
    qualified_name: str  # Full path: module.class.function
    start_line: int
    end_line: int
    file_path: str

    # Function signature
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None

    # Attributes
    is_async: bool = False
    is_method: bool = False  # True if inside a class
    is_static: bool = False
    is_private: bool = False  # Starts with _

    # Docstring
    docstring: Optional[str] = None

    # Complexity metrics
    num_lines: int = 0
    cyclomatic_complexity: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j insertion"""
        return {
            'name': self.name,
            'qualified_name': self.qualified_name,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'file_path': self.file_path,
            'parameters': self.parameters,
            'return_type': self.return_type,
            'is_async': self.is_async,
            'is_method': self.is_method,
            'is_static': self.is_static,
            'is_private': self.is_private,
            'docstring': self.docstring,
            'num_lines': self.num_lines,
            'cyclomatic_complexity': self.cyclomatic_complexity
        }


@dataclass
class ClassNode:
    """Represents a class definition"""
    name: str
    qualified_name: str  # Full path: module.class
    start_line: int
    end_line: int
    file_path: str

    # Inheritance
    base_classes: List[str] = field(default_factory=list)

    # Attributes
    is_abstract: bool = False
    is_private: bool = False

    # Docstring
    docstring: Optional[str] = None

    # Metrics
    num_methods: int = 0
    num_attributes: int = 0
    num_lines: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j insertion"""
        return {
            'name': self.name,
            'qualified_name': self.qualified_name,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'file_path': self.file_path,
            'base_classes': self.base_classes,
            'is_abstract': self.is_abstract,
            'is_private': self.is_private,
            'docstring': self.docstring,
            'num_methods': self.num_methods,
            'num_attributes': self.num_attributes,
            'num_lines': self.num_lines
        }


@dataclass
class VariableNode:
    """Represents a variable (global, class attribute, etc.)"""
    name: str
    qualified_name: str
    scope: str  # 'global', 'class', 'instance'
    file_path: str
    line: int

    # Type information
    type_hint: Optional[str] = None
    inferred_type: Optional[str] = None

    # Attributes
    is_constant: bool = False  # ALL_CAPS naming
    is_private: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j insertion"""
        return {
            'name': self.name,
            'qualified_name': self.qualified_name,
            'scope': self.scope,
            'file_path': self.file_path,
            'line': self.line,
            'type_hint': self.type_hint,
            'inferred_type': self.inferred_type,
            'is_constant': self.is_constant,
            'is_private': self.is_private
        }


@dataclass
class ModuleNode:
    """Represents a Python module or package"""
    name: str  # e.g., 'os', 'django.http'
    is_builtin: bool
    is_third_party: bool
    is_local: bool
    file_path: Optional[str] = None  # For local modules

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j insertion"""
        return {
            'name': self.name,
            'is_builtin': self.is_builtin,
            'is_third_party': self.is_third_party,
            'is_local': self.is_local,
            'file_path': self.file_path
        }


@dataclass
class Relationship:
    """Represents a relationship between nodes"""
    rel_type: RelationType
    source_id: str  # Source node qualified name or path
    target_id: str  # Target node qualified name or path

    # Optional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j insertion"""
        return {
            'type': self.rel_type.value,
            'source': self.source_id,
            'target': self.target_id,
            'metadata': self.metadata
        }


@dataclass
class StructuralData:
    """
    Complete structural data extracted from a file.

    This is the output of AST parsing and the input to Neo4j insertion.
    """
    file_node: FileNode
    functions: List[FunctionNode] = field(default_factory=list)
    classes: List[ClassNode] = field(default_factory=list)
    variables: List[VariableNode] = field(default_factory=list)
    modules: List[ModuleNode] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'file': self.file_node.to_dict(),
            'functions': [f.to_dict() for f in self.functions],
            'classes': [c.to_dict() for c in self.classes],
            'variables': [v.to_dict() for v in self.variables],
            'modules': [m.to_dict() for m in self.modules],
            'relationships': [r.to_dict() for r in self.relationships]
        }

    @property
    def total_nodes(self) -> int:
        """Total number of nodes in this structural data"""
        return 1 + len(self.functions) + len(self.classes) + len(self.variables) + len(self.modules)

    @property
    def total_relationships(self) -> int:
        """Total number of relationships"""
        return len(self.relationships)


@dataclass
class BuildResult:
    """Result of building the knowledge base"""
    total_files: int
    total_functions: int
    total_classes: int
    total_variables: int
    total_modules: int
    total_relationships: int

    # Metrics
    build_time_seconds: float
    files_per_second: float

    # Errors
    failed_files: List[str] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_files': self.total_files,
            'total_functions': self.total_functions,
            'total_classes': self.total_classes,
            'total_variables': self.total_variables,
            'total_modules': self.total_modules,
            'total_relationships': self.total_relationships,
            'build_time_seconds': self.build_time_seconds,
            'files_per_second': self.files_per_second,
            'failed_files': self.failed_files,
            'errors': self.errors
        }


@dataclass
class QueryResult:
    """Result of a graph query"""
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    paths: List[List[str]] = field(default_factory=list)

    # Metadata
    query_time_ms: float = 0.0
    total_results: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'nodes': self.nodes,
            'relationships': self.relationships,
            'paths': self.paths,
            'query_time_ms': self.query_time_ms,
            'total_results': self.total_results
        }
