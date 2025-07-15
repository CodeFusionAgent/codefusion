"""Type definitions for CodeFusion."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Protocol, TypeVar, Union

# Basic types
PathLike = Union[str, Path]
JsonDict = Dict[str, Any]
ConfigDict = Dict[str, Any]


# Entity types
class EntityType(str, Enum):
    """Types of code entities."""

    FILE = "file"
    DIRECTORY = "directory"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    MODULE = "module"
    PACKAGE = "package"
    INTERFACE = "interface"
    ENUM = "enum"
    CONSTANT = "constant"
    PROJECT = "project"
    APPLICATION = "application"
    SERVICE = "service"
    NAMESPACE = "namespace"


class RelationshipType(str, Enum):
    """Types of relationships between entities."""

    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    CONTAINS = "contains"
    USES = "uses"
    EXTENDS = "extends"
    REFERENCES = "references"
    DEPENDS_ON = "depends_on"
    INSTANTIATES = "instantiates"


class LanguageType(str, Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    CSHARP = "csharp"
    GO = "go"
    RUST = "rust"
    PHP = "php"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SCALA = "scala"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    MARKDOWN = "markdown"
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    UNKNOWN = "unknown"


class ExplorationStrategy(str, Enum):
    """Available exploration strategies."""

    REACT = "react"
    PLAN_ACT = "plan_act"
    SENSE_ACT = "sense_act"


class KnowledgeBaseType(str, Enum):
    """Types of knowledge base storage."""

    TEXT = "text"
    NEO4J = "neo4j"
    VECTOR = "vector"


class C4Level(str, Enum):
    """C4 architecture levels."""

    CONTEXT = "context"
    CONTAINERS = "containers"
    COMPONENTS = "components"
    CODE = "code"


# Protocol definitions
class Explorable(Protocol):
    """Protocol for objects that can be explored."""

    def explore(self, strategy: ExplorationStrategy) -> JsonDict:
        """Explore using the given strategy."""
        ...


class Queryable(Protocol):
    """Protocol for objects that can be queried."""

    def query(self, query: str) -> List[Any]:
        """Execute a query and return results."""
        ...


class Persistable(Protocol):
    """Protocol for objects that can be persisted."""

    def save(self) -> None:
        """Save to persistent storage."""
        ...

    def load(self) -> None:
        """Load from persistent storage."""
        ...


class Traceable(Protocol):
    """Protocol for objects that can be traced."""

    def trace(self, operation: str, **kwargs: Any) -> str:
        """Start tracing an operation."""
        ...


# Generic types
T = TypeVar("T")


# Callback types
ExplorationCallback = Callable[[str, JsonDict], None]
ProgressCallback = Callable[[int, int], None]
ErrorCallback = Callable[[Exception], None]


# Configuration types
LlmConfig = Dict[str, Union[str, int, float, bool, None]]
KnowledgeBaseConfig = Dict[str, Union[str, int, bool, None]]
ExplorationConfig = Dict[str, Union[str, int, float]]
RepositoryConfig = Dict[str, Union[str, int, List[str]]]


# Result types
ExplorationResult = Dict[str, Union[int, List[str], Dict[str, Any]]]
QueryResult = Dict[str, Union[str, List[JsonDict], int]]
IndexingResult = Dict[str, Union[int, str, List[str]]]
AnalysisResult = Dict[str, Union[str, JsonDict, List[JsonDict]]]


# Trace types
TraceData = Dict[str, Union[str, int, float, datetime, JsonDict]]
TraceSummary = Dict[str, Union[int, float, List[str]]]


# File information types
FileMetadata = Dict[str, Union[str, int, float, bool]]
DirectoryInfo = Dict[str, Union[str, int, List[str]]]
RepositoryStats = Dict[str, Union[int, Dict[str, int], List[tuple]]]
