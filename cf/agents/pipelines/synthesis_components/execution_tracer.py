"""
Execution Tracer for Synthesis Pipeline

Traces execution paths for "how does X work?" questions.
"""

import re
from typing import Dict, List, Any


class ExecutionTracer:
    """Traces execution paths and call sequences."""

    def __init__(self, config: Dict[str, Any], kb_client=None):
        self.config = config
        self.kb = kb_client

    def trace_execution_paths(self,
                             question: str,
                             file_summaries: Dict[str, Any],
                             architectural_analysis=None) -> List[Dict[str, Any]]:
        """
        Trace execution paths for "how does X work?" questions.

        Uses KB's Life-of-X layer to trace call chains and data flow,
        providing step-by-step execution paths in narratives.
        """
        paths = []

        # Try KB execution path tracing first (call layer directly - no wrapper)
        if self.kb and self.kb.execution_path_tracer is not None:
            try:
                print("   🔄 Tracing execution paths from KB...")

                # Extract potential entry function names from question and architectural analysis
                entry_functions = self._extract_entry_functions(question, architectural_analysis)

                for entry_func in entry_functions[:3]:  # Limit to 3 entry points
                    try:
                        # Trace execution path from entry function (direct layer call)
                        max_depth = self.config.get('agents', {}).get('max_execution_trace_depth', 10)
                        synthesis_config = self.config.get('agents', {}).get('synthesis', {})
                        max_paths = synthesis_config.get('kb_execution_max_paths', 10)

                        traced_paths = self.kb.execution_path_tracer.trace_from_entry_point(
                            entry_point=entry_func,
                            max_depth=max_depth,
                            max_paths=max_paths
                        )

                        # traced_paths is a list of ExecutionPath objects
                        for path_obj in traced_paths[:1]:  # Take first path for each entry point
                            if path_obj and path_obj.steps:
                                # Convert ExecutionPath object to dict
                                paths.append({
                                    'name': f"Flow from {entry_func}",
                                    'entry_point': entry_func,
                                    'steps': [
                                        {
                                            'function_name': s.function_name,
                                            'qualified_name': s.qualified_name,
                                            'step_type': s.step_type,
                                            'metadata': s.metadata
                                        }
                                        for s in path_obj.steps
                                    ],
                                    'depth': len(path_obj.steps)
                                })
                    except Exception as e:
                        print(f"   ⚠️ Failed to trace path from {entry_func}: {e}")

                if paths:
                    print(f"   ✅ Traced {len(paths)} execution paths")
                    return paths

            except Exception as e:
                print(f"   ⚠️ KB execution path tracing failed: {e}")

        # Fallback: Extract call sequences from file summaries
        print("   🔄 Extracting call sequences from summaries...")
        paths = self._extract_call_sequences_from_summaries(question, file_summaries)

        if paths:
            print(f"   ✅ Extracted {len(paths)} call sequences from code")

        return paths

    def _extract_entry_functions(self, question: str, architectural_analysis=None) -> List[str]:
        """Extract potential entry function names from question and architecture"""
        entry_functions = []

        # From architectural analysis
        if architectural_analysis and architectural_analysis.entry_points:
            for entry_point in architectural_analysis.entry_points:
                # Extract function names from details
                if 'functions' in entry_point.details:
                    entry_functions.extend(entry_point.details['functions'][:2])

        # From question keywords
        # Look for function-like words in question
        words = re.findall(r'\b[a-z_][a-z0-9_]*\b', question.lower())
        relevant_words = [w for w in words if len(w) > 4 and w not in ['does', 'work', 'what', 'where', 'when', 'which']]

        # Common entry point patterns
        entry_patterns = ['main', 'run', 'execute', 'start', 'init', 'handle', 'process']
        for word in relevant_words:
            for pattern in entry_patterns:
                if pattern in word:
                    entry_functions.append(word)

        return list(set(entry_functions))[:5]  # Deduplicate and limit

    def _extract_call_sequences_from_summaries(self,
                                               question: str,
                                               file_summaries: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fallback: Extract call sequences by analyzing function calls in code.

        This is less accurate than KB tracing but provides some flow information.
        """
        sequences = []

        # Look for function call patterns in code
        call_pattern = re.compile(r'(\w+)\s*\([^)]*\)')  # function_name(args)

        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            content = summary.get('content', '')
            functions = summary.get('functions', [])

            # For each function, extract its call sequence
            for func_info in functions[:3]:  # Limit to 3 functions per file
                if not isinstance(func_info, dict):
                    continue

                func_name = func_info.get('name', '')
                if not func_name:
                    continue

                # Find function calls within this function (simplified)
                # In real implementation, would need to parse function body
                called_functions = call_pattern.findall(content)
                if called_functions:
                    steps = [
                        {
                            'function': func_name,
                            'file': file_path,
                            'line': func_info.get('line', 0)
                        }
                    ]

                    # Add called functions (up to 5)
                    for called_func in called_functions[:5]:
                        if called_func != func_name:  # Avoid self-references
                            steps.append({
                                'function': called_func,
                                'file': file_path,  # Simplified - might be in different file
                                'line': '?'
                            })

                    if len(steps) > 1:  # At least 2 steps (caller + callee)
                        sequences.append({
                            'name': f"Calls from {func_name}",
                            'entry_point': func_name,
                            'steps': steps,
                            'depth': len(steps)
                        })

        return sequences[:3]  # Limit to 3 sequences
