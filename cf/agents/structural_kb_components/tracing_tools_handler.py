"""
Tracing Tools Handler for StructuralKBAgent

Handles Life-of-X execution tracing tools (execution paths, data flow, lifecycles).
"""

import time
from typing import Dict, Any, Callable
from cf.agents.protocols import KnowledgeBaseProtocol


class TracingToolsHandler:
    """Handles Life-of-X execution tracing tools."""

    def __init__(self, kb: KnowledgeBaseProtocol, config: Dict[str, Any], record_call_fn: Callable):
        self.kb = kb
        self.config = config
        self._record_call = record_call_fn

        # Load config defaults
        kb_agent_config = config.get('agents', {}).get('structural_kb_agent', {})
        self.trace_execution_max_depth = kb_agent_config.get('trace_execution_max_depth', 10)
        self.trace_execution_max_paths = kb_agent_config.get('trace_execution_max_paths', 5)
        self.trace_dataflow_max_depth = kb_agent_config.get('trace_dataflow_max_depth', 20)
        self.trace_lifecycle_max_depth = kb_agent_config.get('trace_lifecycle_max_depth', 20)

    def trace_execution_path(self, entry_point: str, max_depth: int = None, max_paths: int = None) -> Dict[str, Any]:
        """Trace execution path"""
        start_time = time.time()
        try:
            # Call execution path tracer directly (no wrapper)
            if self.kb.execution_path_tracer is None:
                return {'success': False, 'error': 'Execution path tracing not enabled'}

            max_depth = max_depth if max_depth is not None else self.trace_execution_max_depth
            max_paths = max_paths if max_paths is not None else self.trace_execution_max_paths
            raw_paths = self.kb.execution_path_tracer.trace_from_entry_point(
                entry_point, max_depth=max_depth, max_paths=max_paths
            )

            # Convert ExecutionPath objects to dicts
            paths = [
                {
                    'entry_point': p.entry_point,
                    'exit_point': p.exit_point,
                    'total_functions': p.total_functions,
                    'max_depth': p.max_depth,
                    'confidence': p.confidence,
                    'steps': [
                        {
                            'function_name': s.function_name,
                            'qualified_name': s.qualified_name,
                            'step_type': s.step_type,
                            'metadata': s.metadata
                        }
                        for s in p.steps
                    ]
                }
                for p in raw_paths
            ]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'paths': paths,
                'count': len(paths),
                'entry_point': entry_point
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def trace_data_flow(self, start_element: str, max_depth: int = None) -> Dict[str, Any]:
        """Trace data flow"""
        start_time = time.time()
        try:
            # Call dataflow analyzer directly (no wrapper)
            if self.kb.dataflow_analyzer is None:
                return {'success': False, 'error': 'Data flow analysis not enabled'}

            max_depth = max_depth if max_depth is not None else self.trace_dataflow_max_depth
            raw_paths = self.kb.dataflow_analyzer.trace_data_flow(start_element, max_depth=max_depth)

            # Convert DataFlowPath objects to dicts
            flows = [
                {
                    'start_node': p.start_node,
                    'end_node': p.end_node,
                    'path_length': len(p.path),
                    'path': p.path,
                    'transformations': p.transformations,
                    'confidence': p.confidence
                }
                for p in raw_paths
            ]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'flows': flows,
                'count': len(flows),
                'start_element': start_element
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def trace_request_lifecycle(self, endpoint_function: str, max_depth: int = None) -> Dict[str, Any]:
        """Trace request lifecycle"""
        start_time = time.time()
        try:
            # Call execution path tracer directly (no wrapper)
            if self.kb.execution_path_tracer is None:
                return {'success': False, 'error': 'Execution path tracing not enabled'}

            max_depth = max_depth if max_depth is not None else self.trace_lifecycle_max_depth
            raw_path = self.kb.execution_path_tracer.trace_request_lifecycle(endpoint_function, max_depth=max_depth)

            if raw_path is None:
                lifecycle = None
            else:
                # Convert ExecutionPath object to dict
                lifecycle = {
                    'entry_point': raw_path.entry_point,
                    'exit_point': raw_path.exit_point,
                    'total_functions': raw_path.total_functions,
                    'max_depth': raw_path.max_depth,
                    'confidence': raw_path.confidence,
                    'steps': [
                        {
                            'function_name': s.function_name,
                            'qualified_name': s.qualified_name,
                            'step_type': s.step_type,
                            'metadata': s.metadata
                        }
                        for s in raw_path.steps
                    ]
                }

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'lifecycle': lifecycle,
                'endpoint': endpoint_function
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}
