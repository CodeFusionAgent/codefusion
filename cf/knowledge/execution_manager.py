"""
Execution Path Manager

Handles execution path tracing and data flow analysis.
Extracted from StructuralPipeline to improve maintainability.
"""

from typing import Dict, Any, Optional

from cf.knowledge.structural.neo4j_client import Neo4jKnowledgeBase
from cf.knowledge.lifeofx.dataflow import DataFlowAnalyzer
from cf.knowledge.lifeofx.execution_paths import ExecutionPathTracer


class ExecutionPathManager:
    """
    Manages execution path tracing and data flow analysis.

    Responsibilities:
    - Execution path tracing (call chains)
    - Data flow analysis
    - Entry point resolution
    """

    def __init__(self, config: Dict[str, Any], dep_graph=None):
        self.config = config
        self.lifeofx_config = config.get('knowledge_base', {}).get('lifeofx', {})
        self.dep_graph = dep_graph

        self._dataflow_analyzer = None
        self._execution_path_tracer = None

    def is_enabled(self) -> bool:
        """Check if execution path tracing is enabled"""
        return self.lifeofx_config.get('enabled', False)

    def initialize(self):
        """Initialize execution path tracers"""
        if not self.is_enabled() or not self.dep_graph:
            return

        print("   🔄 Initializing execution path tracing...")

        # Initialize analyzers with dependency graph
        self._dataflow_analyzer = DataFlowAnalyzer(self.dep_graph)
        self._execution_path_tracer = ExecutionPathTracer(self.dep_graph)

    @property
    def dataflow_analyzer(self) -> Optional[DataFlowAnalyzer]:
        """Get data flow analyzer (lazy initialization)"""
        if not self.is_enabled() or not self.dep_graph:
            return None

        if self._dataflow_analyzer is None:
            self._dataflow_analyzer = DataFlowAnalyzer(self.dep_graph)

        return self._dataflow_analyzer

    @property
    def execution_path_tracer(self) -> Optional[ExecutionPathTracer]:
        """Get execution path tracer (lazy initialization)"""
        if not self.is_enabled() or not self.dep_graph:
            return None

        if self._execution_path_tracer is None:
            self._execution_path_tracer = ExecutionPathTracer(self.dep_graph)

        return self._execution_path_tracer
