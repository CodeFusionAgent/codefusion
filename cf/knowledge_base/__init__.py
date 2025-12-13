"""
Structural Knowledge Layer

Provides AST-based code structure analysis and graph storage:
- Parse source files to extract functions, classes, variables
- Build dependency graphs (imports, function calls, inheritance)
- Store in Neo4j for persistent, queryable knowledge base
- Enable fast graph queries for code understanding
"""

from cf.knowledge_base.schema import (
    NodeType,
    RelationType,
    StructuralData,
    FunctionNode,
    ClassNode,
    FileNode,
    VariableNode
)
from cf.knowledge_base.kb_orchestrator import (
    Neo4jKnowledgeBase,
    KnowledgeBaseManager,
    FileClassifier,
    KBOrchestrator,
)
from cf.knowledge_base.incremental import (
    ChangeSet,
    FileChangeDetector,
    IncrementalKBUpdater,
)
from cf.knowledge_base.code_parser import PythonASTParser
from cf.knowledge_base.dependency_analysis import DependencyGraphBuilder

__all__ = [
    # Schema types
    "NodeType",
    "RelationType",
    "StructuralData",
    "FunctionNode",
    "ClassNode",
    "FileNode",
    "VariableNode",
    # KB orchestration
    "Neo4jKnowledgeBase",
    "KnowledgeBaseManager",
    "FileClassifier",
    "KBOrchestrator",
    # Incremental updates
    "ChangeSet",
    "FileChangeDetector",
    "IncrementalKBUpdater",
    # Parsing
    "PythonASTParser",
    "DependencyGraphBuilder",
]
