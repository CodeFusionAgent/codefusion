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
from cf.knowledge.structural.sqlite_client import SQLiteKnowledgeBase
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


def create_knowledge_base(config: dict):
    """
    Factory function to create appropriate knowledge base backend.

    Supports:
    - neo4j: Graph database (recommended for large codebases)
    - sqlite: Lightweight file-based database (recommended for small-medium codebases)

    Args:
        config: Knowledge base configuration dict with 'type' and backend-specific settings

    Returns:
        Knowledge base instance (Neo4jKnowledgeBase or SQLiteKnowledgeBase)

    Example:
        # Neo4j backend
        config = {
            'type': 'neo4j',
            'neo4j': {
                'uri': 'bolt://localhost:7687',
                'user': 'neo4j',
                'password': 'your-password',
                'database': 'codefusion'
            }
        }
        kb = create_knowledge_base(config)

        # SQLite backend (no external dependencies)
        config = {
            'type': 'sqlite',
            'sqlite': {
                'db_path': '.codefusion/knowledge.db'
            }
        }
        kb = create_knowledge_base(config)
    """
    kb_type = config.get('type', 'neo4j').lower()

    if kb_type == 'neo4j':
        neo4j_config = config.get('neo4j', {})
        return Neo4jKnowledgeBase(
            uri=neo4j_config.get('uri', 'bolt://localhost:7687'),
            user=neo4j_config.get('user', 'neo4j'),
            password=neo4j_config.get('password', ''),
            database=neo4j_config.get('database', 'neo4j')
        )
    elif kb_type == 'sqlite':
        sqlite_config = config.get('sqlite', {})
        return SQLiteKnowledgeBase(
            db_path=sqlite_config.get('db_path', '.codefusion/knowledge.db')
        )
    else:
        raise ValueError(f"Unsupported knowledge base type: {kb_type}. Use 'neo4j' or 'sqlite'")


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
    "SQLiteKnowledgeBase",
    "create_knowledge_base",
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
