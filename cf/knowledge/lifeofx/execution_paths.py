"""
Execution Path Tracing

Traces complete execution paths through the codebase:
- Request-to-response paths (web apps)
- Entry-to-exit paths (any program flow)
- Complete call chains with context
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from collections import deque

from cf.knowledge.structural.dependency_graph import DependencyGraphBuilder
from cf.knowledge.metrics import KnowledgeLayerMetrics, register_layer_metrics


@dataclass
class ExecutionStep:
    """Represents one step in execution path"""
    function_name: str
    qualified_name: str
    step_type: str  # "entry", "call", "return", "exit"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"{self.function_name} ({self.step_type})"


@dataclass
class ExecutionPath:
    """Represents a complete execution path"""
    entry_point: str
    exit_point: str
    steps: List[ExecutionStep]
    total_functions: int
    max_depth: int
    confidence: float

    def __repr__(self):
        return f"ExecutionPath: {self.entry_point} -> {self.exit_point} ({self.total_functions} functions)"

    def to_narrative(self) -> str:
        """Generate human-readable narrative of execution path"""
        narrative = []

        narrative.append(f"# Execution Path: {self.entry_point}\n")
        narrative.append(f"This path traces the flow from {self.entry_point} to {self.exit_point}.\n")
        narrative.append(f"Total functions called: {self.total_functions}\n")
        narrative.append(f"Maximum call depth: {self.max_depth}\n\n")

        narrative.append("## Execution Flow\n")

        current_depth = 0
        for i, step in enumerate(self.steps, 1):
            indent = "  " * current_depth

            if step.step_type == "entry":
                narrative.append(f"{i}. {indent}📥 Enter: {step.function_name}\n")
                current_depth += 1

            elif step.step_type == "call":
                narrative.append(f"{i}. {indent}🔀 Call: {step.function_name}\n")

            elif step.step_type == "return":
                current_depth = max(0, current_depth - 1)
                narrative.append(f"{i}. {indent}📤 Return from: {step.function_name}\n")

            elif step.step_type == "exit":
                narrative.append(f"{i}. {indent}🏁 Exit: {step.function_name}\n")

        return "".join(narrative)


class ExecutionPathTracer(KnowledgeLayerMetrics):
    """
    Traces execution paths through code.

    Uses call graph to reconstruct complete execution flows.
    """

    def __init__(self, dep_graph: DependencyGraphBuilder):
        """
        Initialize execution path tracer.

        Args:
            dep_graph: Dependency graph builder
        """
        # Initialize metrics tracking
        super().__init__('lifeofx_tracing')
        register_layer_metrics(self)

        self.dep_graph = dep_graph

    def trace_from_entry_point(
        self,
        entry_point: str,
        max_depth: int = 20,
        max_paths: int = 10
    ) -> List[ExecutionPath]:
        """
        Trace all execution paths from an entry point.

        Args:
            entry_point: Starting function (e.g., "app.routes.handle_request")
            max_depth: Maximum call depth
            max_paths: Maximum number of paths to return

        Returns:
            List of execution paths
        """
        # Track this operation (graph traversal, no tokens/cost)
        with self.track_operation(tokens=0, cost=0.0):
            paths = []

            # BFS to find paths
            queue = deque([(entry_point, [], 0)])
            visited_paths = set()

            while queue and len(paths) < max_paths:
                current, path_so_far, depth = queue.popleft()

                if depth > max_depth:
                    continue

                # Create path signature to avoid duplicates
                path_sig = tuple(path_so_far + [current])
                if path_sig in visited_paths:
                    continue
                visited_paths.add(path_sig)

                # Get functions called by current function
                callees = self.dep_graph.call_graph.get(current, [])

                if not callees:
                    # End of path - create ExecutionPath
                    steps = self._build_execution_steps(path_so_far + [current])

                    paths.append(ExecutionPath(
                        entry_point=entry_point,
                        exit_point=current,
                        steps=steps,
                        total_functions=len(path_so_far) + 1,
                        max_depth=depth,
                        confidence=0.8
                    ))
                else:
                    # Continue tracing
                    for callee in callees:
                        if callee not in path_so_far:  # Avoid cycles
                            queue.append((callee, path_so_far + [current], depth + 1))

            return paths

    def find_path_between(
        self,
        start: str,
        end: str,
        max_depth: int = 15
    ) -> List[List[str]]:
        """
        Find call paths between two functions.

        Args:
            start: Starting function
            end: Target function
            max_depth: Maximum search depth

        Returns:
            List of paths (each path is a list of function names)
        """
        return self.dep_graph.find_call_chain(start, end, max_depth)

    def trace_request_lifecycle(
        self,
        endpoint_function: str,
        max_depth: int = 20
    ) -> ExecutionPath:
        """
        Trace request lifecycle for web applications.

        Finds path from HTTP endpoint to database and back.

        Args:
            endpoint_function: HTTP endpoint handler function
            max_depth: Maximum call depth

        Returns:
            ExecutionPath representing request lifecycle
        """
        # Find all functions called from endpoint
        callees = self.dep_graph.find_all_callees(endpoint_function, max_depth)

        # Look for database-related functions
        db_functions = [
            f for f in callees
            if any(keyword in f.lower() for keyword in ['query', 'execute', 'save', 'insert', 'update', 'db'])
        ]

        # Build execution steps
        all_functions = [endpoint_function] + list(callees)
        steps = []

        # Entry
        steps.append(ExecutionStep(
            function_name=endpoint_function.split('.')[-1],
            qualified_name=endpoint_function,
            step_type="entry",
            metadata={'type': 'http_endpoint'}
        ))

        # Calls
        for func in list(callees)[:20]:  # Limit to 20 for readability
            steps.append(ExecutionStep(
                function_name=func.split('.')[-1],
                qualified_name=func,
                step_type="call",
                metadata={}
            ))

        # Exit
        if db_functions:
            exit_func = db_functions[0]
            steps.append(ExecutionStep(
                function_name=exit_func.split('.')[-1],
                qualified_name=exit_func,
                step_type="exit",
                metadata={'type': 'database'}
            ))
        else:
            steps.append(ExecutionStep(
                function_name=endpoint_function.split('.')[-1],
                qualified_name=endpoint_function,
                step_type="exit",
                metadata={}
            ))

        return ExecutionPath(
            entry_point=endpoint_function,
            exit_point=db_functions[0] if db_functions else endpoint_function,
            steps=steps,
            total_functions=len(all_functions),
            max_depth=max_depth,
            confidence=0.7
        )

    def find_entry_points(self, all_functions: List[str]) -> List[str]:
        """
        Find likely entry points in the codebase.

        Entry points are functions that:
        - Are not called by other functions
        - Have names suggesting they're entry points (main, handler, etc.)

        Args:
            all_functions: List of all function qualified names

        Returns:
            List of likely entry points
        """
        entry_points = []

        # Functions never called (potential entry points)
        called_functions = set()
        for callees in self.dep_graph.call_graph.values():
            called_functions.update(callees)

        never_called = [f for f in all_functions if f not in called_functions]

        # Filter for likely entry points
        entry_keywords = ['main', 'handler', 'route', 'endpoint', 'serve', 'run', 'start', 'init']

        for func in never_called:
            func_lower = func.lower()
            if any(keyword in func_lower for keyword in entry_keywords):
                entry_points.append(func)

        return entry_points

    def detect_long_call_chains(
        self,
        min_length: int = 10
    ) -> List[List[str]]:
        """
        Detect long call chains (potential code smell).

        Args:
            min_length: Minimum chain length

        Returns:
            List of long call chains
        """
        long_chains = []

        # Sample some functions
        sample_functions = list(self.dep_graph.function_table.keys())[:100]

        for func in sample_functions:
            callees = self.dep_graph.find_all_callees(func, max_depth=min_length + 2)

            if len(callees) >= min_length:
                # Build chain
                chain = [func] + list(callees)[:min_length]
                long_chains.append(chain)

        # Sort by length
        long_chains.sort(key=len, reverse=True)

        return long_chains[:20]  # Return top 20

    def _build_execution_steps(self, path: List[str]) -> List[ExecutionStep]:
        """
        Build ExecutionStep list from function path.

        Args:
            path: List of function qualified names

        Returns:
            List of ExecutionSteps
        """
        steps = []

        for i, func in enumerate(path):
            func_name = func.split('.')[-1]

            if i == 0:
                step_type = "entry"
            elif i == len(path) - 1:
                step_type = "exit"
            else:
                step_type = "call"

            steps.append(ExecutionStep(
                function_name=func_name,
                qualified_name=func,
                step_type=step_type,
                metadata={'index': i}
            ))

        return steps

    def generate_sequence_diagram(self, path: ExecutionPath) -> str:
        """
        Generate PlantUML sequence diagram for execution path.

        Args:
            path: ExecutionPath to visualize

        Returns:
            PlantUML diagram code
        """
        lines = []
        lines.append("@startuml")
        lines.append("title Execution Path\\n" + path.entry_point)
        lines.append("")

        # Participants
        participants = set(step.function_name for step in path.steps)
        for participant in sorted(participants):
            lines.append(f'participant "{participant}"')

        lines.append("")

        # Sequence
        for i, step in enumerate(path.steps):
            if step.step_type == "entry":
                lines.append(f'activate "{step.function_name}"')

            elif step.step_type == "call":
                if i > 0:
                    prev_step = path.steps[i-1]
                    lines.append(f'"{prev_step.function_name}" -> "{step.function_name}": call')

            elif step.step_type == "return":
                lines.append(f'deactivate "{step.function_name}"')

        lines.append("@enduml")

        return "\n".join(lines)

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution path statistics"""
        # Get dependency graph stats
        dep_stats = self.dep_graph.get_dependency_stats()

        # Calculate entry points
        all_funcs = list(self.dep_graph.function_table.keys())
        entry_points = self.find_entry_points(all_funcs)

        return {
            **dep_stats,
            'num_entry_points': len(entry_points),
            'entry_points': entry_points[:10]  # Show first 10
        }
