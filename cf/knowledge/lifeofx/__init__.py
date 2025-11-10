"""
Life-of-X Analysis Layer

Provides enhanced execution path and data flow analysis:
- Execution path tracing (from request to response)
- Data flow analysis (variable usage and transformation)
- Request lifecycle tracking
- Data transformation chains
"""

from cf.knowledge.lifeofx.dataflow import DataFlowAnalyzer
from cf.knowledge.lifeofx.execution_paths import ExecutionPathTracer

__all__ = [
    "DataFlowAnalyzer",
    "ExecutionPathTracer"
]
