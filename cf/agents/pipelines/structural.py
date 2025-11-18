"""
Structural Pipeline - Knowledge Base Orchestration (REFACTORED)

Orchestrates KB building and querying using focused manager classes.
Reduced from 1549 lines to ~350 lines by extracting responsibilities.

Architecture:
- kb_manager: KB lifecycle (build, update, parse)
- semantic_manager: Semantic search
- pattern_manager: Pattern detection
- execution_manager: Execution paths
- query_engine: Query processing and file discovery
- entry_point_resolver: Entry point resolution
- file_classifier: File type classification
"""

import os
import time
import hashlib
from typing import Dict, List, Any, Optional
from pathlib import Path

from cf.knowledge.structural.schema import StructuralData, BuildResult, QueryResult
from cf.knowledge.structural.neo4j_client import Neo4jKnowledgeBase
from cf.knowledge.structural.dependency_graph import DependencyGraphBuilder
from cf.knowledge.incremental.file_watcher import FileChangeDetector
from cf.llm.client import LLMClient

# Manager classes (refactored)
from cf.knowledge.kb_manager import KnowledgeBaseManager
from cf.knowledge.semantic_manager import SemanticSearchManager
from cf.knowledge.pattern_manager import PatternAnalysisManager
from cf.knowledge.execution_manager import ExecutionPathManager
from cf.knowledge.query_engine import QueryEngine
from cf.knowledge.entry_point_resolver import EntryPointResolver
from cf.knowledge.utils.file_classifier import FileClassifier

# Import types for property type hints
from cf.knowledge.semantic.embeddings import CodeEmbedder
from cf.knowledge.semantic.similarity import SemanticSearch
from cf.knowledge.patterns.design_patterns import DesignPatternDetector
from cf.knowledge.patterns.architectural_patterns import ArchitecturalPatternDetector
from cf.knowledge.patterns.code_smells import CodeSmellDetector
from cf.knowledge.lifeofx.dataflow import DataFlowAnalyzer
from cf.knowledge.lifeofx.execution_paths import ExecutionPathTracer


class StructuralPipeline:
    """
    Orchestrates knowledge base construction and querying.

    Now acts as a thin orchestration layer that delegates to specialized managers.
    Responsibilities reduced to:
    - Manager initialization
    - Property delegation (backward compatibility)
    - Repository statistics
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], kb: Neo4jKnowledgeBase = None):
        """
        Initialize structural pipeline with all managers.

        Args:
            repo_path: Root path of repository
            config: Configuration dictionary
            kb: Optional Neo4j KB instance
        """
        self.repo_path = repo_path
        self.config = config
        self.repo_id = self._generate_repo_id(repo_path)

        # Initialize KB if not provided
        if kb is None:
            kb_config = config.get('knowledge_base', {}).get('neo4j', {})
            password = kb_config.get('password') or os.environ.get('NEO4J_PASSWORD', 'password')

            try:
                self.kb = Neo4jKnowledgeBase(
                    uri=kb_config.get('uri', 'bolt://localhost:7687'),
                    user=kb_config.get('user', 'neo4j'),
                    password=password,
                    database=kb_config.get('database', 'neo4j')
                )
            except Exception as e:
                print(f"⚠️ Failed to connect to Neo4j: {e}")
                self.kb = None
        else:
            self.kb = kb

        # Initialize dependency graph builder
        self.dep_graph = DependencyGraphBuilder()

        # Initialize LLM client (needed by semantic manager)
        self._llm_client = None
        try:
            self._llm_client = LLMClient(self.config.get('llm', {}))
        except Exception as e:
            print(f"⚠️ [STRUCTURAL_KB] LLM client initialization failed: {e}")

        # Initialize all manager classes
        self.kb_manager = KnowledgeBaseManager(repo_path, config, self.kb)
        self.semantic_manager = SemanticSearchManager(config, self._llm_client)
        self.pattern_manager = PatternAnalysisManager(config, self.kb)
        self.execution_manager = ExecutionPathManager(config, self.dep_graph)

        # Initialize query engine (depends on other managers)
        self.query_engine = QueryEngine(
            kb=self.kb,
            repo_id=self.repo_id,
            repo_path=repo_path,
            semantic_manager=self.semantic_manager,
            pattern_manager=self.pattern_manager,
            execution_manager=self.execution_manager,
            config=config
        )

        # Initialize entry point resolver
        self.entry_point_resolver = EntryPointResolver(
            kb=self.kb,
            repo_id=self.repo_id,
            repo_path=repo_path,
            config=config
        )

        # Initialize file classifier utility
        self.file_classifier = FileClassifier(repo_path)

        # File watcher for incremental updates
        self.file_watcher = None

        # Config shortcuts
        self.semantic_config = config.get('knowledge_base', {}).get('semantic', {})
        self.patterns_config = config.get('knowledge_base', {}).get('patterns', {})
        self.lifeofx_config = config.get('knowledge_base', {}).get('lifeofx', {})

        # Try loading enhanced layers if KB already exists
        if self.kb_exists():
            self._try_load_enhanced_layers()

    def _generate_repo_id(self, repo_path: str) -> str:
        """Generate unique repo ID from path"""
        abs_path = os.path.abspath(repo_path)
        return hashlib.md5(abs_path.encode()).hexdigest()[:12]

    # ========== Context Manager Support ==========

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close KB connection"""
        if hasattr(self, 'kb_manager'):
            self.kb_manager.close()

    def __del__(self):
        self.close()

    # ========== KB Availability ==========

    def is_kb_available(self) -> bool:
        """Check if KB is available"""
        return self.kb_manager.is_available()

    def kb_exists(self) -> bool:
        """Check if KB has data"""
        return self.kb_manager.exists()

    # ========== KB Lifecycle (Delegate to kb_manager) ==========

    def build_knowledge_base(self, force_rebuild: bool = False) -> BuildResult:
        """
        Build knowledge base from source files.

        Delegates to kb_manager.

        Args:
            force_rebuild: Force rebuild even if KB exists

        Returns:
            BuildResult with statistics
        """
        # Build KB through manager
        result = self.kb_manager.build(force_rebuild)

        # If successful (has files), build enhanced layers
        if result and result.total_files > 0 and self.kb:
            # Get structural data from KB manager
            structural_data = self.kb_manager.get_structural_data()
            self._build_enhanced_layers(structural_data)

        return result

    def update_knowledge_base(self) -> Dict[str, Any]:
        """
        Incrementally update KB with changed files.

        Delegates to kb_manager.

        Returns:
            Update result dict
        """
        return self.kb_manager.update()

    def _try_load_enhanced_layers(self):
        """
        Try loading enhanced layers from cache when KB already exists.

        Called during initialization if KB is already built.
        """
        # Try loading semantic layer from cache
        if self.semantic_manager.is_enabled():
            cache_file = self.semantic_config.get('cache_file', '.codefusion/embeddings.pkl')
            try:
                if self.semantic_manager.load_from_cache(cache_file):
                    print(f"✅ [STRUCTURAL_KB] Loaded semantic embeddings from cache")
                # If cache doesn't exist, semantic search will just return 0 results
            except Exception as e:
                print(f"⚠️ [STRUCTURAL_KB] Failed to load semantic cache: {e}")

        # Pattern and execution layers will be initialized on-demand

    def _build_enhanced_layers(self, structural_data_list: List[Any] = None):
        """
        Build enhanced layers (semantic, pattern, execution).

        Args:
            structural_data_list: Optional structural data for semantic layer
        """
        # Build semantic layer
        if self.semantic_manager.is_enabled():
            print("   🧠 Generating semantic embeddings...")
            try:
                # Try loading from cache first if no structural data provided
                if not structural_data_list:
                    cache_file = self.semantic_config.get('cache_file', '.codefusion/embeddings.pkl')
                    if self.semantic_manager.load_from_cache(cache_file):
                        print(f"   ✅ Loaded semantic embeddings from cache")
                    else:
                        print(f"   ⚠️ No structural data and no cache found - semantic search unavailable")
                else:
                    # Build from structural data
                    self.semantic_manager.initialize(structural_data_list)
            except Exception as e:
                print(f"   ⚠️ Semantic layer failed: {e}")

        # Build pattern detection layer
        if self.pattern_manager.is_enabled():
            print("   🔍 Detecting patterns and code smells...")
            try:
                self.pattern_manager.initialize()
                print("   ✅ Pattern detection ready")
            except Exception as e:
                print(f"   ⚠️ Pattern detection failed: {e}")

        # Build Life-of-X layer
        if self.execution_manager.is_enabled():
            print("   🔄 Building data flow graphs...")
            try:
                self.execution_manager.initialize()
            except Exception as e:
                print(f"   ⚠️ Life-of-X layer failed: {e}")

    # ========== Query Interface (Delegate to query_engine) ==========

    def find_files_for_question(
        self,
        question: str,
        max_results: int = 50,
        question_context: Dict[str, Any] = None
    ) -> List[str]:
        """
        Find relevant files for a question.

        Delegates to query_engine.

        Args:
            question: User question
            max_results: Maximum files to return
            question_context: Optional LLM classification from supervisor

        Returns:
            List of file paths ranked by relevance
        """
        return self.query_engine.find_files(
            question=question,
            max_results=max_results,
            question_context=question_context,
            entry_point_resolver=self.entry_point_resolver
        )

    def get_repository_stats(self) -> Dict[str, Any]:
        """
        Get repository statistics.

        Delegates to kb_manager.

        Returns:
            Statistics dictionary
        """
        return self.kb_manager.get_stats()

    # ========== Property Delegation (Backward Compatibility) ==========

    @property
    def code_embedder(self) -> Optional[CodeEmbedder]:
        """Delegate to SemanticSearchManager"""
        return self.semantic_manager.embedder

    @property
    def semantic_search(self) -> Optional[SemanticSearch]:
        """Delegate to SemanticSearchManager"""
        return self.semantic_manager.search

    @property
    def design_pattern_detector(self) -> Optional[DesignPatternDetector]:
        """Delegate to PatternAnalysisManager"""
        return self.pattern_manager.design_pattern_detector

    @property
    def architectural_pattern_detector(self) -> Optional[ArchitecturalPatternDetector]:
        """Delegate to PatternAnalysisManager"""
        return self.pattern_manager.architectural_pattern_detector

    @property
    def code_smell_detector(self) -> Optional[CodeSmellDetector]:
        """Delegate to PatternAnalysisManager"""
        return self.pattern_manager.code_smell_detector

    @property
    def dataflow_analyzer(self) -> Optional[DataFlowAnalyzer]:
        """Delegate to ExecutionPathManager"""
        return self.execution_manager.dataflow_analyzer

    @property
    def execution_path_tracer(self) -> Optional[ExecutionPathTracer]:
        """Delegate to ExecutionPathManager"""
        return self.execution_manager.execution_path_tracer
