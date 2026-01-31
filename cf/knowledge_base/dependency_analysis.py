"""
Dependency Graph Builder

Builds higher-level dependency analysis on top of AST parsing:
- Resolve function call targets (map call sites to definitions)
- Build complete call graphs across files
- Analyze import dependencies
- Detect circular dependencies
- Calculate dependency metrics (fan-in, fan-out)

This provides more sophisticated analysis than raw AST data.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict, deque

# Optional dependencies for config file parsing
try:
    import toml
    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from cf.knowledge_base.schema import (
    StructuralData, FunctionNode, Relationship, RelationType
)


class DependencyGraphBuilder:
    """
    Build and analyze dependency graphs from structural data.

    Provides:
    - Call graph construction across multiple files
    - Import dependency resolution
    - Circular dependency detection
    - Dependency metrics
    """

    def __init__(self):
        """Initialize dependency graph builder"""
        # Symbol tables for name resolution
        self.function_table: Dict[str, FunctionNode] = {}  # qualified_name -> FunctionNode
        self.class_table: Dict[str, Dict[str, Any]] = {}   # qualified_name -> ClassNode
        self.module_table: Dict[str, str] = {}              # module_name -> file_path

        # Dependency graphs
        self.call_graph: Dict[str, List[str]] = defaultdict(list)  # caller -> [callees]
        self.import_graph: Dict[str, List[str]] = defaultdict(list)  # file -> [imported_modules]

        # Reverse graphs for queries
        self.reverse_call_graph: Dict[str, List[str]] = defaultdict(list)  # callee -> [callers]
        self.reverse_import_graph: Dict[str, List[str]] = defaultdict(list)  # module -> [importing_files]

    def add_structural_data(self, data: StructuralData):
        """
        Add structural data from a file to the dependency graph.

        Args:
            data: StructuralData from AST parsing
        """
        # Add functions to symbol table
        for function in data.functions:
            self.function_table[function.qualified_name] = function

        # Add classes to symbol table
        for class_node in data.classes:
            self.class_table[class_node.qualified_name] = class_node

        # Add modules to symbol table
        for module in data.modules:
            if module.is_local and module.file_path:
                self.module_table[module.name] = module.file_path

        # Process relationships
        for rel in data.relationships:
            if rel.rel_type == RelationType.CALLS:
                # Add to call graph
                caller = rel.source_id
                callee = rel.target_id

                self.call_graph[caller].append(callee)
                self.reverse_call_graph[callee].append(caller)

            elif rel.rel_type == RelationType.IMPORTS:
                # Add to import graph
                file_path = rel.source_id
                module = rel.target_id

                self.import_graph[file_path].append(module)
                self.reverse_import_graph[module].append(file_path)

    def resolve_function_calls(self) -> List[Relationship]:
        """
        Resolve function call targets to their definitions.

        AST parsing gives us call sites like "foo()" or "bar.method()".
        This resolves them to actual function qualified names.

        Returns:
            List of resolved CALLS relationships
        """
        resolved_relationships = []

        for caller_qname, callees in self.call_graph.items():
            for callee_name in callees:
                # Try to resolve callee_name to a qualified name
                resolved = self._resolve_function_name(callee_name, caller_qname)

                if resolved:
                    rel = Relationship(
                        rel_type=RelationType.CALLS,
                        source_id=caller_qname,
                        target_id=resolved,
                        metadata={'original_name': callee_name}
                    )
                    resolved_relationships.append(rel)

        return resolved_relationships

    def _resolve_function_name(self, name: str, context: str) -> Optional[str]:
        """
        Resolve a function name to its qualified name.

        Args:
            name: Function name (e.g., "foo", "Bar.method", "module.func")
            context: Qualified name of calling function for context

        Returns:
            Resolved qualified name or None
        """
        # Direct lookup (already qualified)
        if name in self.function_table:
            return name

        # Try with context module
        # Extract module from context: "module.Class.method" -> "module"
        context_parts = context.split('.')
        if len(context_parts) >= 2:
            module = context_parts[0]

            # Try: module.name
            candidate = f"{module}.{name}"
            if candidate in self.function_table:
                return candidate

            # Try: module.Class.name (if context is in a class)
            if len(context_parts) >= 3:
                class_name = context_parts[1]
                candidate = f"{module}.{class_name}.{name}"
                if candidate in self.function_table:
                    return candidate

        # Partial match - search for functions ending with this name
        for qname in self.function_table.keys():
            if qname.endswith('.' + name) or qname == name:
                return qname

        return None

    def find_call_chain(self, source: str, target: str, max_depth: int = 10) -> List[List[str]]:
        """
        Find call chains from source function to target function.

        Uses BFS to find shortest paths in call graph.

        Args:
            source: Source function qualified name
            target: Target function qualified name
            max_depth: Maximum depth to search

        Returns:
            List of call chains (each chain is a list of function names)
        """
        # BFS to find paths
        queue = deque([(source, [source])])
        paths = []
        visited = set()

        while queue and len(paths) < 100:  # Limit to 100 paths
            current, path = queue.popleft()

            if len(path) > max_depth:
                continue

            if current == target:
                paths.append(path)
                continue

            if current in visited:
                continue
            visited.add(current)

            # Explore callees
            for callee in self.call_graph.get(current, []):
                if callee not in path:  # Avoid cycles
                    queue.append((callee, path + [callee]))

        return paths

    def find_all_callers(self, function: str, max_depth: int = 5) -> Set[str]:
        """
        Find all functions that call the given function (directly or indirectly).

        Args:
            function: Function qualified name
            max_depth: Maximum depth to traverse

        Returns:
            Set of caller function qualified names
        """
        callers = set()
        queue = deque([(function, 0)])
        visited = set()

        while queue:
            current, depth = queue.popleft()

            if depth >= max_depth:
                continue

            if current in visited:
                continue
            visited.add(current)

            # Get direct callers
            for caller in self.reverse_call_graph.get(current, []):
                callers.add(caller)
                queue.append((caller, depth + 1))

        return callers

    def find_all_callees(self, function: str, max_depth: int = 5) -> Set[str]:
        """
        Find all functions called by the given function (directly or indirectly).

        Args:
            function: Function qualified name
            max_depth: Maximum depth to traverse

        Returns:
            Set of callee function qualified names
        """
        callees = set()
        queue = deque([(function, 0)])
        visited = set()

        while queue:
            current, depth = queue.popleft()

            if depth >= max_depth:
                continue

            if current in visited:
                continue
            visited.add(current)

            # Get direct callees
            for callee in self.call_graph.get(current, []):
                callees.add(callee)
                queue.append((callee, depth + 1))

        return callees

    def detect_circular_dependencies(self) -> List[List[str]]:
        """
        Detect circular import dependencies.

        Returns:
            List of circular dependency chains
        """
        cycles = []

        def find_cycles_from(start: str, path: List[str], visited: Set[str]) -> None:
            """DFS to find cycles"""
            if start in path:
                # Found a cycle
                cycle_start = path.index(start)
                cycle = path[cycle_start:]
                if cycle not in cycles:
                    cycles.append(cycle)
                return

            if start in visited:
                return

            visited.add(start)
            path.append(start)

            # Explore imports
            for imported_module in self.import_graph.get(start, []):
                # Find files that provide this module
                for file_path in self.reverse_import_graph.get(imported_module, []):
                    find_cycles_from(file_path, path.copy(), visited.copy())

        # Check from each file
        for file_path in self.import_graph.keys():
            find_cycles_from(file_path, [], set())

        return cycles

    def calculate_fan_metrics(self) -> Dict[str, Dict[str, int]]:
        """
        Calculate fan-in and fan-out metrics for functions.

        Fan-in: Number of functions that call this function
        Fan-out: Number of functions this function calls

        High fan-in = widely used function
        High fan-out = complex function

        Returns:
            Dictionary mapping function name to {fan_in, fan_out}
        """
        metrics = {}

        for func_name in self.function_table.keys():
            fan_in = len(self.reverse_call_graph.get(func_name, []))
            fan_out = len(self.call_graph.get(func_name, []))

            metrics[func_name] = {
                'fan_in': fan_in,
                'fan_out': fan_out,
                'complexity_score': fan_in * fan_out  # Simple complexity metric
            }

        return metrics

    def get_import_dependencies(self, file_path: str) -> Dict[str, List[str]]:
        """
        Get import dependency information for a file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with direct and transitive dependencies
        """
        direct = self.import_graph.get(file_path, [])

        # BFS to find transitive dependencies
        transitive = set()
        queue = deque(direct)
        visited = set([file_path])

        while queue:
            module = queue.popleft()

            if module in visited:
                continue
            visited.add(module)

            # Find files that provide this module
            for provider_file in self.reverse_import_graph.get(module, []):
                if provider_file != file_path and provider_file not in transitive:
                    transitive.add(provider_file)

                    # Add their imports
                    for sub_import in self.import_graph.get(provider_file, []):
                        if sub_import not in visited:
                            queue.append(sub_import)

        return {
            'direct': direct,
            'transitive': list(transitive)
        }

    def get_dependency_stats(self) -> Dict[str, Any]:
        """
        Get overall dependency statistics.

        Returns:
            Dictionary with various dependency metrics
        """
        return {
            'total_functions': len(self.function_table),
            'total_classes': len(self.class_table),
            'total_modules': len(self.module_table),
            'total_call_edges': sum(len(callees) for callees in self.call_graph.values()),
            'total_import_edges': sum(len(imports) for imports in self.import_graph.values()),
            'circular_dependencies': len(self.detect_circular_dependencies()),
            'avg_fan_out': sum(
                len(callees) for callees in self.call_graph.values()
            ) / max(len(self.call_graph), 1),
            'max_fan_in': max(
                (len(callers) for callers in self.reverse_call_graph.values()),
                default=0
            ),
            'max_fan_out': max(
                (len(callees) for callees in self.call_graph.values()),
                default=0
            )
        }

    def export_dot(self, output_file: str, max_nodes: int = 50):
        """
        Export call graph to DOT format for visualization.

        Args:
            output_file: Path to output .dot file
            max_nodes: Maximum number of nodes to include
        """
        with open(output_file, 'w') as f:
            f.write("digraph CallGraph {\n")
            f.write("  rankdir=LR;\n")
            f.write("  node [shape=box];\n\n")

            # Limit to most connected functions
            fan_metrics = self.calculate_fan_metrics()
            top_functions = sorted(
                fan_metrics.items(),
                key=lambda x: x[1]['complexity_score'],
                reverse=True
            )[:max_nodes]

            top_function_names = set(name for name, _ in top_functions)

            # Write nodes
            for func_name in top_function_names:
                f.write(f'  "{func_name}";\n')

            # Write edges
            for caller, callees in self.call_graph.items():
                if caller in top_function_names:
                    for callee in callees:
                        if callee in top_function_names:
                            f.write(f'  "{caller}" -> "{callee}";\n')

            f.write("}\n")

        print(f"✅ Call graph exported to {output_file}")

    # ========== Layer 3: Extended Dependency Graphs ==========

    def build_dependency_graph(self, repo_path: str) -> Dict[str, List[str]]:
        """
        Build dependency graph from build configuration files.

        Analyzes:
        - requirements.txt / pyproject.toml (Python)
        - package.json (JavaScript/Node)
        - Makefile
        - setup.py

        Args:
            repo_path: Path to repository root

        Returns:
            Dictionary mapping dependency files to their dependencies
        """
        build_deps = {}
        repo_root = Path(repo_path)

        # Discover files in repo root dynamically
        for item in repo_root.iterdir():
            if not item.is_file():
                continue

            fname = item.name
            deps = []

            try:
                # Try to parse as TOML (pyproject.toml, etc.)
                if fname.endswith('.toml') and TOML_AVAILABLE:
                    data = toml.load(item)
                    # Look for dependencies in common TOML structures
                    if 'tool' in data and 'poetry' in data['tool']:
                        poetry_deps = data['tool']['poetry'].get('dependencies', {})
                        deps.extend([pkg for pkg in poetry_deps.keys() if pkg != 'python'])
                    if 'project' in data:
                        project_deps = data['project'].get('dependencies', [])
                        deps.extend([dep.split()[0] for dep in project_deps])

                # Try to parse as JSON (package.json, etc.)
                elif fname.endswith('.json'):
                    with open(item) as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            deps.extend(data.get('dependencies', {}).keys())
                            deps.extend(data.get('devDependencies', {}).keys())

                # Try to parse as requirements file (text with package specs)
                elif fname.endswith('.txt'):
                    with open(item) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                # Extract package name (before ==, >=, etc.)
                                pkg = line.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].strip()
                                if pkg and not pkg.startswith('-'):  # Skip flags like -r, -e
                                    deps.append(pkg)

                # Try to parse Python setup files
                elif fname.endswith('.py'):
                    with open(item) as f:
                        content = f.read()
                        # Look for install_requires pattern
                        match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                        if match:
                            deps_str = match.group(1)
                            deps = [
                                dep.strip().strip('"').strip("'").split('==')[0].split('>=')[0]
                                for dep in deps_str.split(',')
                                if dep.strip()
                            ]

                if deps:
                    build_deps[fname] = deps

            except Exception:
                # Skip files that can't be parsed
                pass

        return build_deps

    def detect_runtime_dependencies(self) -> Dict[str, List[str]]:
        """
        Detect runtime dependencies (dynamic imports, plugin systems).

        Looks for:
        - importlib.import_module() calls
        - __import__() calls
        - Plugin registration patterns

        Returns:
            Dictionary mapping source to runtime dependencies
        """
        runtime_deps = defaultdict(list)

        # Look for dynamic import patterns in function bodies
        for func_name, func_node in self.function_table.items():
            # Check metadata for dynamic imports (would need AST parser to add this)
            if hasattr(func_node, 'metadata') and func_node.metadata:
                dynamic_imports = func_node.metadata.get('dynamic_imports', [])
                if dynamic_imports:
                    runtime_deps[func_name] = dynamic_imports

        return dict(runtime_deps)

    def build_config_dependency_graph(self, repo_path: str) -> Dict[str, List[str]]:
        """
        Build configuration dependency graph.

        Analyzes config files and their dependencies:
        - .env files
        - config.yaml / config.json
        - settings.py
        - Configuration inheritance

        Args:
            repo_path: Repository root path

        Returns:
            Configuration dependency mapping
        """
        config_deps = {}
        repo_root = Path(repo_path)

        # Discover files dynamically
        for item in repo_root.iterdir():
            if not item.is_file():
                continue

            fname = item.name
            deps = []

            try:
                # .env style files (KEY=VALUE format)
                if fname.startswith('.env') or fname.endswith('.env'):
                    with open(item) as f:
                        for line in f:
                            line = line.strip()
                            if '=' in line and not line.startswith('#'):
                                key = line.split('=')[0].strip()
                                deps.append(key)

                # YAML files
                elif fname.endswith(('.yaml', '.yml')) and YAML_AVAILABLE:
                    with open(item) as f:
                        data = yaml.safe_load(f)
                        if isinstance(data, dict):
                            deps.extend(data.keys())

                # JSON files (non-package files)
                elif fname.endswith('.json'):
                    with open(item) as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            # Skip dependency files (already handled in build deps)
                            if 'dependencies' not in data and 'devDependencies' not in data:
                                deps.extend(data.keys())

                if deps:
                    config_deps[fname] = deps

            except Exception:
                # Skip files that can't be parsed
                pass

        return config_deps

    def get_all_dependency_layers(self, repo_path: str) -> Dict[str, Any]:
        """
        Get comprehensive dependency information across all layers.

        Returns:
            Dictionary with all dependency types
        """
        return {
            'code_dependencies': {
                'call_graph_edges': sum(len(c) for c in self.call_graph.values()),
                'import_graph_edges': sum(len(i) for i in self.import_graph.values()),
                'circular_dependencies': len(self.detect_circular_dependencies())
            },
            'build_dependencies': self.build_dependency_graph(repo_path),
            'runtime_dependencies': self.detect_runtime_dependencies(),
            'config_dependencies': self.build_config_dependency_graph(repo_path),
            'metrics': self.get_dependency_stats()
        }
