"""
Knowledge Base Layer for CodeFusion

This module provides persistent knowledge base infrastructure for code analysis:
- Structural layer: AST parsing, dependency graphs, call graphs
- Semantic layer: Vector embeddings, semantic search
- Incremental updates: Differential KB updates on file changes

The knowledge base dramatically improves performance for large codebases:
- First analysis: Build KB once (60-90 min for 100K files)
- Subsequent analyses: Query KB (< 1 second)
- Incremental updates: Only re-parse changed files
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
