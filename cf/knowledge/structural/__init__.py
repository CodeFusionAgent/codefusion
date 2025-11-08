"""
Structural Knowledge Layer

Provides AST-based code structure analysis and graph storage:
- Parse source files to extract functions, classes, variables
- Build dependency graphs (imports, function calls, inheritance)
- Store in Neo4j for persistent, queryable knowledge base
- Enable fast graph queries for code understanding
"""

from cf.knowledge.structural.schema import (
    NodeType,
    RelationType,
    StructuralData,
    FunctionNode,
    ClassNode,
    FileNode,
    VariableNode
)
from cf.knowledge.structural.neo4j_client import Neo4jKnowledgeBase
from cf.knowledge.structural.ast_parser import PythonASTParser
from cf.knowledge.structural.dependency_graph import DependencyGraphBuilder

__all__ = [
    "NodeType",
    "RelationType",
    "StructuralData",
    "FunctionNode",
    "ClassNode",
    "FileNode",
    "VariableNode",
    "Neo4jKnowledgeBase",
    "PythonASTParser",
    "DependencyGraphBuilder"
]
