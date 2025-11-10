"""
Data Flow Analysis

Tracks how data flows through the codebase:
- Variable usage and transformations
- Data passed between functions
- State mutations
- Data transformation chains
"""

from typing import List, Dict, Any, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from cf.knowledge.structural.schema import StructuralData, FunctionNode, Relationship, RelationType
from cf.knowledge.structural.dependency_graph import DependencyGraphBuilder


@dataclass
class DataFlowNode:
    """Represents a node in data flow graph"""
    element_id: str  # Function/variable qualified name
    element_type: str  # "function", "variable", "parameter"
    operations: List[str] = field(default_factory=list)  # Operations performed
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlowEdge:
    """Represents data flow between nodes"""
    source: str  # Source element ID
    target: str  # Target element ID
    flow_type: str  # "parameter", "return", "assignment", "mutation"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlowPath:
    """Represents a complete data flow path"""
    start_node: str
    end_node: str
    path: List[str]  # List of element IDs in order
    transformations: List[str]  # Transformations applied
    confidence: float

    def __repr__(self):
        return f"{self.start_node} -> {self.end_node} ({len(self.path)} steps)"


class DataFlowAnalyzer:
    """
    Analyzes data flow through code.

    Tracks how data moves and transforms as it passes through functions.
    """

    def __init__(self, dep_graph: DependencyGraphBuilder):
        """
        Initialize data flow analyzer.

        Args:
            dep_graph: Dependency graph builder with structural data
        """
        self.dep_graph = dep_graph
        self.flow_graph: Dict[str, List[DataFlowEdge]] = defaultdict(list)

    def build_flow_graph(self, all_structural_data: List[StructuralData]):
        """
        Build data flow graph from structural data.

        Args:
            all_structural_data: List of StructuralData from all files
        """
        print("🔄 Building data flow graph...")

        # Process each file
        for structural_data in all_structural_data:
            # Analyze function parameters and returns
            for function in structural_data.functions:
                self._analyze_function_flow(function)

            # Analyze relationships (calls)
            for rel in structural_data.relationships:
                if rel.rel_type == RelationType.CALLS:
                    self._analyze_call_flow(rel)

        print(f"✅ Built data flow graph with {self._count_edges()} edges")

    def _analyze_function_flow(self, function: FunctionNode):
        """
        Analyze data flow within a function.

        Tracks:
        - Parameters (data input)
        - Return values (data output)
        - Internal transformations
        """
        func_id = function.qualified_name

        # Create flow nodes for parameters
        for param in function.parameters:
            param_id = f"{func_id}.{param}"

            # Parameter flows into function
            self.flow_graph[param_id].append(DataFlowEdge(
                source=param_id,
                target=func_id,
                flow_type="parameter",
                metadata={'param_name': param}
            ))

        # If function has return type, create output flow
        if function.return_type:
            return_id = f"{func_id}.return"

            # Function flows to return value
            self.flow_graph[func_id].append(DataFlowEdge(
                source=func_id,
                target=return_id,
                flow_type="return",
                metadata={'return_type': function.return_type}
            ))

    def _analyze_call_flow(self, relationship: Relationship):
        """
        Analyze data flow through function calls.

        When function A calls function B:
        - Data flows from A to B (via parameters)
        - Data flows from B back to A (via return value)
        """
        caller_id = relationship.source_id
        callee_id = relationship.target_id

        # Call edge (data flows from caller to callee)
        self.flow_graph[caller_id].append(DataFlowEdge(
            source=caller_id,
            target=callee_id,
            flow_type="call",
            metadata={'line': relationship.metadata.get('line')}
        ))

        # Return edge (data flows back from callee to caller)
        callee_return = f"{callee_id}.return"
        self.flow_graph[callee_return].append(DataFlowEdge(
            source=callee_return,
            target=caller_id,
            flow_type="return_value",
            metadata={}
        ))

    def trace_data_flow(
        self,
        start_element: str,
        max_depth: int = 10
    ) -> List[DataFlowPath]:
        """
        Trace data flow from a starting element.

        Args:
            start_element: Starting element (function, variable)
            max_depth: Maximum depth to trace

        Returns:
            List of data flow paths
        """
        from collections import deque

        paths = []
        queue = deque([(start_element, [start_element], [])])
        visited = set()

        while queue and len(paths) < 100:  # Limit to 100 paths
            current, path, transformations = queue.popleft()

            if len(path) > max_depth:
                continue

            if current in visited:
                continue
            visited.add(current)

            # Get outgoing edges
            edges = self.flow_graph.get(current, [])

            if not edges:
                # End of path
                if len(path) > 1:
                    paths.append(DataFlowPath(
                        start_node=start_element,
                        end_node=current,
                        path=path,
                        transformations=transformations,
                        confidence=0.7  # Base confidence
                    ))
            else:
                # Continue tracing
                for edge in edges:
                    next_node = edge.target

                    if next_node not in path:  # Avoid cycles
                        new_transformations = transformations + [edge.flow_type]
                        queue.append((next_node, path + [next_node], new_transformations))

        return paths

    def find_data_sources(self, target_element: str) -> List[str]:
        """
        Find all data sources that feed into a target element.

        Args:
            target_element: Target element ID

        Returns:
            List of source element IDs
        """
        sources = []

        for source, edges in self.flow_graph.items():
            for edge in edges:
                if edge.target == target_element:
                    sources.append(source)

        return sources

    def find_data_sinks(self, source_element: str) -> List[str]:
        """
        Find all data sinks that receive data from a source element.

        Args:
            source_element: Source element ID

        Returns:
            List of sink element IDs
        """
        sinks = []

        for edge in self.flow_graph.get(source_element, []):
            sinks.append(edge.target)

        return sinks

    def trace_variable_usage(
        self,
        variable_name: str,
        starting_function: str
    ) -> Dict[str, Any]:
        """
        Trace how a variable is used throughout execution.

        Args:
            variable_name: Variable to trace
            starting_function: Function where variable is defined

        Returns:
            Dictionary with usage information
        """
        # Find all functions that might use this variable
        usage_chain = self.dep_graph.find_all_callees(starting_function, max_depth=5)

        return {
            'variable': variable_name,
            'defined_in': starting_function,
            'potentially_used_in': list(usage_chain),
            'num_potential_uses': len(usage_chain)
        }

    def detect_data_transformation_chains(
        self,
        min_chain_length: int = 3
    ) -> List[DataFlowPath]:
        """
        Detect long data transformation chains.

        Finds data that goes through many transformations.

        Args:
            min_chain_length: Minimum chain length to report

        Returns:
            List of long transformation chains
        """
        long_chains = []

        # Sample some starting points
        sample_elements = list(self.flow_graph.keys())[:100]

        for element in sample_elements:
            paths = self.trace_data_flow(element, max_depth=min_chain_length + 2)

            for path in paths:
                if len(path.path) >= min_chain_length:
                    long_chains.append(path)

        # Sort by length (longest first)
        long_chains.sort(key=lambda p: len(p.path), reverse=True)

        return long_chains[:50]  # Return top 50

    def _count_edges(self) -> int:
        """Count total number of edges in flow graph"""
        return sum(len(edges) for edges in self.flow_graph.values())

    def get_statistics(self) -> Dict[str, Any]:
        """Get data flow statistics"""
        num_nodes = len(self.flow_graph)
        num_edges = self._count_edges()

        edge_types = defaultdict(int)
        for edges in self.flow_graph.values():
            for edge in edges:
                edge_types[edge.flow_type] += 1

        return {
            'num_nodes': num_nodes,
            'num_edges': num_edges,
            'edge_types': dict(edge_types),
            'avg_edges_per_node': num_edges / num_nodes if num_nodes > 0 else 0
        }

    def print_statistics(self):
        """Print data flow statistics"""
        stats = self.get_statistics()

        print(f"\n📊 Data Flow Analysis Statistics:")
        print(f"   Nodes: {stats['num_nodes']}")
        print(f"   Edges: {stats['num_edges']}")
        print(f"   Avg edges per node: {stats['avg_edges_per_node']:.2f}")
        print(f"\n   Edge types:")
        for edge_type, count in sorted(stats['edge_types'].items()):
            print(f"     - {edge_type}: {count}")

    # ========== Advanced Data Flow Analysis (Reaching Definitions, Use-Def, Def-Use) ==========

    def compute_reaching_definitions(
        self,
        function_id: str
    ) -> Dict[str, Set[str]]:
        """
        Compute reaching definitions for a function.

        Reaching definitions: For each program point, which variable definitions
        can reach that point (i.e., the definition has not been overwritten).

        Args:
            function_id: Function to analyze

        Returns:
            Dictionary mapping variable names to sets of definition points
        """
        reaching_defs = defaultdict(set)

        # Get all data flow paths that reach this function
        sources = self.find_data_sources(function_id)

        for source in sources:
            # Extract variable name from source
            # Format: "module.func.var" or "module.func.return"
            parts = source.split('.')
            if len(parts) >= 2:
                var_name = parts[-1]

                # Add this definition to reaching definitions
                reaching_defs[var_name].add(source)

        # Transitively find all reaching definitions
        for var_name in list(reaching_defs.keys()):
            defs = set(reaching_defs[var_name])
            for def_point in list(defs):
                # Find definitions that reach this definition
                transitive_sources = self.find_data_sources(def_point)
                for t_source in transitive_sources:
                    t_parts = t_source.split('.')
                    if len(t_parts) >= 2:
                        t_var = t_parts[-1]
                        if t_var == var_name:
                            reaching_defs[var_name].add(t_source)

        return {var: defs for var, defs in reaching_defs.items()}

    def build_use_def_chains(
        self,
        function_id: str
    ) -> Dict[str, List[str]]:
        """
        Build use-def chains for a function.

        Use-def chain: For each use of a variable, which definitions can reach it.
        Maps each variable USE to the DEFINITIONS that can reach it.

        Args:
            function_id: Function to analyze

        Returns:
            Dictionary mapping use points to definition points
        """
        use_def_chains = {}

        # Find all uses of variables in this function
        # A "use" is when a function receives data (parameter flow)
        for edge in self.flow_graph.get(function_id, []):
            if edge.flow_type in ["parameter", "call"]:
                use_point = edge.target

                # Find definitions that reach this use
                reaching_defs = self.compute_reaching_definitions(use_point)

                # For each variable used
                for var_name, defs in reaching_defs.items():
                    use_key = f"{use_point}.use.{var_name}"
                    use_def_chains[use_key] = list(defs)

        return use_def_chains

    def build_def_use_chains(
        self,
        function_id: str
    ) -> Dict[str, List[str]]:
        """
        Build def-use chains for a function.

        Def-use chain: For each definition of a variable, where is it used.
        Maps each variable DEFINITION to the USES of that variable.

        Args:
            function_id: Function to analyze

        Returns:
            Dictionary mapping definition points to use points
        """
        def_use_chains = defaultdict(list)

        # Find all definitions in this function
        # Parameters are definitions
        func_node = self.dep_graph.function_table.get(function_id)
        if func_node:
            for param in func_node.parameters:
                def_point = f"{function_id}.{param}"

                # Find all uses of this definition
                uses = self.find_data_sinks(def_point)

                if uses:
                    def_use_chains[def_point] = uses

        # Return values are also definitions
        return_id = f"{function_id}.return"
        if return_id in self.flow_graph:
            uses = self.find_data_sinks(return_id)
            if uses:
                def_use_chains[return_id] = uses

        return dict(def_use_chains)

    def analyze_variable_lifetime(
        self,
        variable_id: str
    ) -> Dict[str, Any]:
        """
        Analyze the lifetime of a variable through the program.

        Tracks:
        - Where variable is defined
        - All uses of the variable
        - Last use
        - Scope of lifetime

        Args:
            variable_id: Variable identifier (e.g., "module.func.var")

        Returns:
            Dictionary with lifetime information
        """
        # Find definition point
        definition = variable_id

        # Find all uses (sinks)
        uses = self.find_data_sinks(variable_id)

        # Trace through all uses
        all_downstream_uses = set(uses)
        for use in uses:
            # Transitively find uses
            transitive_uses = self.find_data_sinks(use)
            all_downstream_uses.update(transitive_uses)

        # Estimate lifetime scope
        parts = variable_id.split('.')
        scope = parts[-2] if len(parts) >= 2 else "global"

        return {
            'variable_id': variable_id,
            'definition_point': definition,
            'direct_uses': uses,
            'all_downstream_uses': list(all_downstream_uses),
            'use_count': len(all_downstream_uses),
            'scope': scope,
            'is_used': len(all_downstream_uses) > 0
        }

    def detect_unused_variables(
        self,
        function_id: str
    ) -> List[str]:
        """
        Detect unused variables in a function.

        A variable is unused if it has no uses in its def-use chain.

        Args:
            function_id: Function to analyze

        Returns:
            List of unused variable IDs
        """
        unused = []

        # Build def-use chains
        def_use_chains = self.build_def_use_chains(function_id)

        # Find definitions with no uses
        for def_point, uses in def_use_chains.items():
            if not uses:
                unused.append(def_point)

        return unused

    def detect_undefined_uses(
        self,
        function_id: str
    ) -> List[str]:
        """
        Detect uses of undefined variables.

        A use is undefined if it has no reaching definitions.

        Args:
            function_id: Function to analyze

        Returns:
            List of undefined use points
        """
        undefined = []

        # Build use-def chains
        use_def_chains = self.build_use_def_chains(function_id)

        # Find uses with no reaching definitions
        for use_point, defs in use_def_chains.items():
            if not defs:
                undefined.append(use_point)

        return undefined

    def get_advanced_flow_analysis(
        self,
        function_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive data flow analysis for a function.

        Includes:
        - Reaching definitions
        - Use-def chains
        - Def-use chains
        - Unused variables
        - Undefined uses

        Args:
            function_id: Function to analyze

        Returns:
            Complete analysis dictionary
        """
        return {
            'function_id': function_id,
            'reaching_definitions': {
                var: list(defs)
                for var, defs in self.compute_reaching_definitions(function_id).items()
            },
            'use_def_chains': self.build_use_def_chains(function_id),
            'def_use_chains': self.build_def_use_chains(function_id),
            'unused_variables': self.detect_unused_variables(function_id),
            'undefined_uses': self.detect_undefined_uses(function_id)
        }
