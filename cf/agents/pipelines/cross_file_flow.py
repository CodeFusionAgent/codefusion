"""
Cross-File Execution Flow Analyzer

NEW MODULE: Tracks execution flow across multiple files to build complete
call chains for "Life of X" narratives.

Example:
    login() -> verify_credentials() -> User.query() -> database_execute()
    (auth.py)  (auth.py)              (models/user.py)  (database.py)

This module enables understanding of cross-file dependencies and
complete execution paths through the system.
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field


@dataclass
class CrossFileStep:
    """Represents one step in cross-file execution"""
    function_name: str
    qualified_name: str
    file_path: str
    line_number: Optional[int] = None
    calls_to_other_files: List[str] = field(default_factory=list)


@dataclass
class CrossFileFlow:
    """Complete execution flow across multiple files"""
    entry_point: str
    entry_file: str
    steps: List[CrossFileStep]
    files_involved: Set[str] = field(default_factory=set)
    total_cross_file_calls: int = 0


class CrossFileFlowAnalyzer:
    """
    Analyzes execution flow across multiple files.

    Builds complete call chains that span multiple files to help
    engineers understand how different parts of the system interact.
    """

    def __init__(self, kb):
        """
        Initialize analyzer.

        Args:
            kb: Knowledge base with graph query capabilities
        """
        self.kb = kb

    def build_cross_file_flow(
        self,
        entry_point: str,
        repo_id: str,
        max_depth: int = 5
    ) -> Optional[CrossFileFlow]:
        """
        Build complete cross-file execution flow from an entry point.

        Args:
            entry_point: Starting function (qualified name)
            repo_id: Repository ID
            max_depth: Maximum depth to traverse

        Returns:
            CrossFileFlow object with complete call chain

        Example:
            >>> flow = analyzer.build_cross_file_flow('app.views.login', repo_id)
            >>> print(f"Files involved: {flow.files_involved}")
            {'app/views.py', 'app/auth.py', 'app/models.py', 'app/db.py'}
        """
        if not self.kb:
            return None

        try:
            steps = []
            files_involved = set()
            visited = set()  # Avoid cycles

            # Get entry point info
            entry_query = """
            MATCH (f:Function {repo_id: $repo_id, qualified_name: $qname})
            RETURN f.file_path as file, f.start_line as line
            LIMIT 1
            """
            result = self.kb.execute_query(entry_query, {
                'repo_id': repo_id,
                'qname': entry_point
            })

            if not result.records:
                return None

            entry_file = result.records[0]['file']
            files_involved.add(entry_file)

            # Recursively trace calls
            self._trace_calls_recursive(
                function_qname=entry_point,
                current_file=entry_file,
                repo_id=repo_id,
                depth=0,
                max_depth=max_depth,
                steps=steps,
                files_involved=files_involved,
                visited=visited
            )

            # Count cross-file calls
            cross_file_calls = sum(1 for step in steps if step.calls_to_other_files)

            return CrossFileFlow(
                entry_point=entry_point,
                entry_file=entry_file,
                steps=steps,
                files_involved=files_involved,
                total_cross_file_calls=cross_file_calls
            )

        except Exception as e:
            print(f"⚠️ [CROSS_FILE_FLOW] Failed to build flow: {e}")
            return None

    def _trace_calls_recursive(
        self,
        function_qname: str,
        current_file: str,
        repo_id: str,
        depth: int,
        max_depth: int,
        steps: List[CrossFileStep],
        files_involved: Set[str],
        visited: Set[str]
    ):
        """Recursively trace function calls across files"""
        if depth >= max_depth or function_qname in visited:
            return

        visited.add(function_qname)

        try:
            # Find what this function calls
            calls_query = """
            MATCH (caller:Function {repo_id: $repo_id, qualified_name: $qname})-[:CALLS]->(callee:Function)
            RETURN callee.qualified_name as callee_qname,
                   callee.file_path as callee_file,
                   callee.start_line as callee_line,
                   callee.name as callee_name
            LIMIT 20
            """
            result = self.kb.execute_query(calls_query, {
                'repo_id': repo_id,
                'qname': function_qname
            })

            cross_file_callees = []

            for record in result.records:
                callee_file = record['callee_file']
                callee_qname = record['callee_qname']

                # Check if this is a cross-file call
                if callee_file != current_file:
                    cross_file_callees.append(callee_qname)
                    files_involved.add(callee_file)

                    # Add step for the callee
                    step = CrossFileStep(
                        function_name=record['callee_name'],
                        qualified_name=callee_qname,
                        file_path=callee_file,
                        line_number=record.get('callee_line')
                    )
                    steps.append(step)

                    # Recursively trace from callee
                    self._trace_calls_recursive(
                        function_qname=callee_qname,
                        current_file=callee_file,
                        repo_id=repo_id,
                        depth=depth + 1,
                        max_depth=max_depth,
                        steps=steps,
                        files_involved=files_involved,
                        visited=visited
                    )

            # Update the current function's cross-file calls
            if cross_file_callees and steps:
                # Find the step for current function and update it
                for step in steps:
                    if step.qualified_name == function_qname:
                        step.calls_to_other_files = cross_file_callees
                        break

        except Exception as e:
            print(f"⚠️ [CROSS_FILE_FLOW] Trace failed at {function_qname}: {e}")

    def build_dependency_map(
        self,
        file_summaries: Dict[str, Dict[str, Any]],
        repo_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Build complete cross-file dependency map for a set of analyzed files.

        Args:
            file_summaries: Dictionary of file summaries from analysis pipeline
            repo_id: Repository ID

        Returns:
            Dictionary mapping function_qname -> list of external dependencies:
            {
                'app.auth.login': [
                    {'function': 'app.models.User.query', 'file': 'app/models.py'},
                    {'function': 'app.db.execute', 'file': 'app/db.py'}
                ]
            }
        """
        dependency_map = {}

        if not self.kb:
            return dependency_map

        try:
            for file_path, summary in file_summaries.items():
                functions = summary.get('structure', {}).get('functions', [])

                for function_name in functions:
                    # Build qualified name (simplified)
                    qualified_name = f"{file_path.replace('/', '.').replace('.py', '')}.{function_name}"

                    # Find external calls
                    calls_query = """
                    MATCH (caller:Function {repo_id: $repo_id})-[:CALLS]->(callee:Function)
                    WHERE caller.name = $func_name OR caller.qualified_name CONTAINS $func_name
                    AND callee.file_path != caller.file_path
                    RETURN callee.qualified_name as dep_qname,
                           callee.file_path as dep_file,
                           callee.name as dep_name
                    LIMIT 10
                    """
                    result = self.kb.execute_query(calls_query, {
                        'repo_id': repo_id,
                        'func_name': function_name
                    })

                    if result.records:
                        dependencies = [
                            {
                                'function': record['dep_qname'],
                                'simple_name': record['dep_name'],
                                'file': record['dep_file']
                            }
                            for record in result.records
                        ]

                        if dependencies:
                            dependency_map[qualified_name] = dependencies

            return dependency_map

        except Exception as e:
            print(f"⚠️ [CROSS_FILE_FLOW] Dependency map failed: {e}")
            return {}

    def format_flow_for_narrative(self, flow: CrossFileFlow) -> str:
        """
        Format cross-file flow as human-readable narrative.

        Args:
            flow: CrossFileFlow object

        Returns:
            Formatted string for inclusion in synthesis
        """
        if not flow or not flow.steps:
            return "No cross-file flow detected."

        narrative_parts = []

        narrative_parts.append(f"**Cross-File Execution Flow** (from `{flow.entry_point}`):\n")
        narrative_parts.append(f"Spans {len(flow.files_involved)} files:\n")

        for i, file in enumerate(sorted(flow.files_involved), 1):
            narrative_parts.append(f"  {i}. `{file}`")

        narrative_parts.append(f"\n**Call Chain Across Files:**\n")

        for i, step in enumerate(flow.steps, 1):
            line_ref = f":{step.line_number}" if step.line_number else ""
            narrative_parts.append(
                f"  {i}. `{step.function_name}` ({step.file_path}{line_ref})"
            )

            if step.calls_to_other_files:
                for callee in step.calls_to_other_files[:3]:  # Show top 3
                    narrative_parts.append(f"     ↳ calls {callee}")

        return "\n".join(narrative_parts)
