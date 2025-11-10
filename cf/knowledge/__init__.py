"""
Knowledge Base Layer for CodeFusion

This module provides persistent knowledge base infrastructure for code analysis:
- Structural layer: AST parsing, dependency graphs, call graphs
- Semantic layer: Vector embeddings, semantic search
- Pattern recognition: Design patterns, architectural patterns, code smells
- Life-of-X analysis: Execution paths, data flow tracing
- Incremental updates: Differential KB updates on file changes

The knowledge base dramatically improves performance for large codebases:
- First analysis: Build KB once (60-90 min for 100K files)
- Subsequent analyses: Query KB (< 1 second)
- Incremental updates: Only re-parse changed files
"""

# Structural layer
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

# Semantic layer
from cf.knowledge.semantic.embeddings import CodeEmbedder, EmbeddingModel
from cf.knowledge.semantic.similarity import SemanticSearch

# Pattern recognition layer
from cf.knowledge.patterns.design_patterns import DesignPatternDetector, DesignPattern
from cf.knowledge.patterns.architectural_patterns import ArchitecturalPatternDetector, ArchitecturalPattern
from cf.knowledge.patterns.code_smells import CodeSmellDetector, CodeSmell, Severity

# Life-of-X layer
from cf.knowledge.lifeofx.dataflow import DataFlowAnalyzer
from cf.knowledge.lifeofx.execution_paths import ExecutionPathTracer

__all__ = [
    # Structural layer
    "NodeType",
    "RelationType",
    "StructuralData",
    "FunctionNode",
    "ClassNode",
    "FileNode",
    "VariableNode",
    "Neo4jKnowledgeBase",
    "PythonASTParser",
    "DependencyGraphBuilder",
    # Semantic layer
    "CodeEmbedder",
    "EmbeddingModel",
    "SemanticSearch",
    # Pattern recognition layer
    "DesignPatternDetector",
    "DesignPattern",
    "ArchitecturalPatternDetector",
    "ArchitecturalPattern",
    "CodeSmellDetector",
    "CodeSmell",
    "Severity",
    # Life-of-X layer
    "DataFlowAnalyzer",
    "ExecutionPathTracer"
]
