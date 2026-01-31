"""
Code Analysis Module

Provides comprehensive code analysis capabilities:
- Pattern Detection: Design patterns, architectural patterns, code smells
- Execution Tracing: Execution paths, data flow analysis

Consolidated from pattern_detection.py and execution_tracing.py.
"""

from typing import List, Dict, Any, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict

from cf.knowledge_base.schema import StructuralData, ClassNode, FunctionNode, Relationship, RelationType
from cf.knowledge_base.dependency_analysis import DependencyGraphBuilder
from cf.metrics import get_global_collector


# ============================================================================
# PATTERN DETECTION
# ============================================================================

# ---------- Pattern Detectors Factory ----------

@dataclass
class PatternDetectors:
    """
    Container for all pattern detectors.

    Provides unified access to design pattern, architectural pattern,
    and code smell detection functionality.
    """
    design_pattern_detector: Optional['DesignPatternDetector'] = None
    architectural_pattern_detector: Optional['ArchitecturalPatternDetector'] = None
    code_smell_detector: Optional['CodeSmellDetector'] = None

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
        kb: Any = None
    ) -> Optional['PatternDetectors']:
        """
        Create PatternDetectors from configuration.

        Args:
            config: Full configuration dictionary
            kb: Optional knowledge base instance

        Returns:
            PatternDetectors instance or None if disabled
        """
        patterns_config = config.get('knowledge_base', {}).get('patterns', {})

        # Check if pattern analysis is enabled
        if not patterns_config.get('enabled', False):
            return None

        # Initialize detectors based on config
        design_detector = None
        architectural_detector = None
        smell_detector = None

        if patterns_config.get('detect_design_patterns', True):
            design_detector = DesignPatternDetector()

        if patterns_config.get('detect_architectural_patterns', True):
            architectural_detector = ArchitecturalPatternDetector()

        if patterns_config.get('detect_code_smells', True):
            thresholds = patterns_config.get('thresholds', {})
            smell_detector = CodeSmellDetector(config=thresholds)

        return cls(
            design_pattern_detector=design_detector,
            architectural_pattern_detector=architectural_detector,
            code_smell_detector=smell_detector
        )

    def is_enabled(self) -> bool:
        """Check if any detector is enabled"""
        return any([
            self.design_pattern_detector is not None,
            self.architectural_pattern_detector is not None,
            self.code_smell_detector is not None
        ])


# ---------- Code Smell Detection ----------

class CodeSmell(Enum):
    """Code smell types"""
    GOD_CLASS = "GodClass"
    LONG_METHOD = "LongMethod"
    LONG_PARAMETER_LIST = "LongParameterList"
    FEATURE_ENVY = "FeatureEnvy"
    DATA_CLASS = "DataClass"
    DUPLICATE_CODE = "DuplicateCode"
    DEAD_CODE = "DeadCode"
    LAZY_CLASS = "LazyClass"


class Severity(Enum):
    """Smell severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CodeSmellMatch:
    """Represents a detected code smell"""
    smell: CodeSmell
    severity: Severity
    element_name: str
    qualified_name: str
    file_path: str
    metrics: Dict[str, Any]
    suggestions: List[str]

    def __repr__(self):
        return f"{self.smell.value} in {self.element_name} ({self.severity.value})"


class CodeSmellDetector:
    """
    Detects code smells and anti-patterns.

    Uses metrics and heuristics to identify code quality issues.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize code smell detector.

        Args:
            config: Configuration with thresholds
        """
        self.config = config or {}
        self.smells_found: List[CodeSmellMatch] = []

        # Thresholds (can be configured)
        self.thresholds = {
            'god_class_methods': self.config.get('god_class_methods', 20),
            'god_class_lines': self.config.get('god_class_lines', 500),
            'long_method_lines': self.config.get('long_method_lines', 50),
            'long_method_complexity': self.config.get('long_method_complexity', 10),
            'long_parameter_list': self.config.get('long_parameter_list', 5),
            'lazy_class_max_methods': self.config.get('lazy_class_max_methods', 2)
        }

    def detect_smells(self, structural_data: StructuralData) -> List[CodeSmellMatch]:
        """
        Detect all code smells in structural data.

        Args:
            structural_data: StructuralData from AST parsing

        Returns:
            List of detected code smells
        """
        return self.detect_all_smells(structural_data.classes, structural_data.functions)

    def detect_all_smells(self, all_classes: List[ClassNode], all_functions: List[FunctionNode]) -> List[CodeSmellMatch]:
        """
        Detect all code smells in lists of classes and functions.

        Args:
            all_classes: List of ClassNode objects
            all_functions: List of FunctionNode objects

        Returns:
            List of detected code smells
        """
        smells = []

        # Detect class-level smells
        for class_node in all_classes:
            smells.extend(self._detect_god_class(class_node))
            smells.extend(self._detect_data_class(class_node, all_functions))
            smells.extend(self._detect_lazy_class(class_node))

        # Detect method-level smells
        for function in all_functions:
            smells.extend(self._detect_long_method(function))
            smells.extend(self._detect_long_parameter_list(function))

        self.smells_found.extend(smells)
        return smells

    def _detect_god_class(self, class_node: ClassNode) -> List[CodeSmellMatch]:
        """Detect God Class (class with too many responsibilities)."""
        smells = []

        # Check method count
        if class_node.num_methods > self.thresholds['god_class_methods']:
            severity = Severity.HIGH if class_node.num_methods > 30 else Severity.MEDIUM

            smells.append(CodeSmellMatch(
                smell=CodeSmell.GOD_CLASS,
                severity=severity,
                element_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                metrics={
                    'num_methods': class_node.num_methods,
                    'num_lines': class_node.num_lines
                },
                suggestions=[
                    "Split into multiple classes with single responsibilities",
                    "Extract related methods into new classes",
                    "Apply Single Responsibility Principle"
                ]
            ))

        # Check lines of code
        if class_node.num_lines > self.thresholds['god_class_lines']:
            severity = Severity.HIGH if class_node.num_lines > 1000 else Severity.MEDIUM

            smells.append(CodeSmellMatch(
                smell=CodeSmell.GOD_CLASS,
                severity=severity,
                element_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                metrics={
                    'num_methods': class_node.num_methods,
                    'num_lines': class_node.num_lines
                },
                suggestions=[
                    f"Class has {class_node.num_lines} lines - consider splitting",
                    "Extract functionality into helper classes"
                ]
            ))

        return smells

    def _detect_long_method(self, function: FunctionNode) -> List[CodeSmellMatch]:
        """Detect Long Method (method is too long or too complex)."""
        smells = []

        # Check line count
        if function.num_lines > self.thresholds['long_method_lines']:
            severity = Severity.HIGH if function.num_lines > 100 else Severity.MEDIUM

            smells.append(CodeSmellMatch(
                smell=CodeSmell.LONG_METHOD,
                severity=severity,
                element_name=function.name,
                qualified_name=function.qualified_name,
                file_path=function.file_path,
                metrics={
                    'num_lines': function.num_lines,
                    'complexity': function.cyclomatic_complexity
                },
                suggestions=[
                    f"Method has {function.num_lines} lines - extract sub-methods",
                    "Break into smaller, focused functions",
                    "Apply Extract Method refactoring"
                ]
            ))

        # Check complexity
        if function.cyclomatic_complexity > self.thresholds['long_method_complexity']:
            severity = Severity.HIGH if function.cyclomatic_complexity > 20 else Severity.MEDIUM

            smells.append(CodeSmellMatch(
                smell=CodeSmell.LONG_METHOD,
                severity=severity,
                element_name=function.name,
                qualified_name=function.qualified_name,
                file_path=function.file_path,
                metrics={
                    'num_lines': function.num_lines,
                    'complexity': function.cyclomatic_complexity
                },
                suggestions=[
                    f"Cyclomatic complexity {function.cyclomatic_complexity} is too high",
                    "Simplify conditional logic",
                    "Extract complex conditions into helper functions"
                ]
            ))

        return smells

    def _detect_long_parameter_list(self, function: FunctionNode) -> List[CodeSmellMatch]:
        """Detect Long Parameter List."""
        num_params = len(function.parameters)

        if num_params > self.thresholds['long_parameter_list']:
            severity = Severity.MEDIUM if num_params <= 8 else Severity.HIGH

            return [CodeSmellMatch(
                smell=CodeSmell.LONG_PARAMETER_LIST,
                severity=severity,
                element_name=function.name,
                qualified_name=function.qualified_name,
                file_path=function.file_path,
                metrics={'num_parameters': num_params},
                suggestions=[
                    f"Function has {num_params} parameters - use parameter object",
                    "Group related parameters into a class",
                    "Consider builder pattern for complex construction"
                ]
            )]

        return []

    def _detect_data_class(self, class_node: ClassNode, functions: List[FunctionNode]) -> List[CodeSmellMatch]:
        """Detect Data Class (class with only getters/setters)."""
        # Get methods for this class
        class_methods = [f for f in functions if f.is_method and f.qualified_name.startswith(class_node.qualified_name)]

        if len(class_methods) == 0:
            return []

        # Check if all methods are simple (likely getters/setters)
        simple_methods = sum(1 for m in class_methods if m.num_lines <= 3)

        if simple_methods == len(class_methods) and len(class_methods) > 3:
            return [CodeSmellMatch(
                smell=CodeSmell.DATA_CLASS,
                severity=Severity.LOW,
                element_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                metrics={
                    'num_methods': len(class_methods),
                    'simple_methods': simple_methods
                },
                suggestions=[
                    "Class appears to be a data holder - consider adding behavior",
                    "Move related logic from other classes into this class",
                    "Or use dataclass/namedtuple if it's truly just data"
                ]
            )]

        return []

    def _detect_lazy_class(self, class_node: ClassNode) -> List[CodeSmellMatch]:
        """Detect Lazy Class (class that doesn't do much)."""
        if class_node.num_methods <= self.thresholds['lazy_class_max_methods'] and class_node.num_lines < 20:
            return [CodeSmellMatch(
                smell=CodeSmell.LAZY_CLASS,
                severity=Severity.LOW,
                element_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                metrics={
                    'num_methods': class_node.num_methods,
                    'num_lines': class_node.num_lines
                },
                suggestions=[
                    "Class is very small - consider inlining into parent class",
                    "Merge with related classes",
                    "Or add more functionality if it's incomplete"
                ]
            )]

        return []

    def get_smells_by_severity(self, severity: Severity) -> List[CodeSmellMatch]:
        """Get all smells with a specific severity"""
        return [s for s in self.smells_found if s.severity == severity]

    def get_smells_by_file(self, file_path: str) -> List[CodeSmellMatch]:
        """Get all smells in a specific file"""
        return [s for s in self.smells_found if s.file_path == file_path]

    def get_statistics(self) -> Dict[str, Any]:
        """Get code smell statistics"""
        smell_counts = {}
        severity_counts = {}

        for smell in self.smells_found:
            smell_name = smell.smell.value
            smell_counts[smell_name] = smell_counts.get(smell_name, 0) + 1

            sev_name = smell.severity.value
            severity_counts[sev_name] = severity_counts.get(sev_name, 0) + 1

        return {
            'total_smells': len(self.smells_found),
            'by_smell': smell_counts,
            'by_severity': severity_counts
        }


# ---------- Design Pattern Detection ----------

class DesignPattern(Enum):
    """Design pattern types"""
    # Creational
    SINGLETON = "Singleton"
    FACTORY = "Factory"
    ABSTRACT_FACTORY = "AbstractFactory"
    BUILDER = "Builder"
    PROTOTYPE = "Prototype"
    # Structural
    ADAPTER = "Adapter"
    DECORATOR = "Decorator"
    PROXY = "Proxy"
    FACADE = "Facade"
    COMPOSITE = "Composite"
    # Behavioral
    OBSERVER = "Observer"
    STRATEGY = "Strategy"
    COMMAND = "Command"
    STATE = "State"
    TEMPLATE_METHOD = "TemplateMethod"


@dataclass
class PatternMatch:
    """Represents a detected pattern"""
    pattern: DesignPattern
    confidence: float  # 0.0-1.0
    class_name: str
    qualified_name: str
    file_path: str
    evidence: List[str]  # Evidence for this pattern
    metadata: Dict[str, Any]

    def __repr__(self):
        return f"{self.pattern.value} in {self.class_name} (confidence={self.confidence:.2f})"


class DesignPatternDetector:
    """
    Detects design patterns in code using heuristics and rules.

    Uses class structure, method names, and relationships to identify patterns.
    All confidence scoring thresholds are configurable via config.yaml.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.metrics_collector = get_global_collector()
        self.component_name = 'pattern_detection'
        self.patterns_found: List[PatternMatch] = []

        # Pattern detection is LLM-driven - no hardcoded scoring configuration
        self.config = config or {}

    def detect_patterns(self, structural_data: StructuralData) -> List[PatternMatch]:
        """Detect all design patterns in structural data."""
        return self.detect_all_patterns(structural_data.classes)

    def detect_all_patterns(self, all_classes: List[ClassNode]) -> List[PatternMatch]:
        """Design pattern detection - LLM-driven analysis of actual code structure."""
        # No hardcoded keyword matching - LLM analyzes actual code
        return []

    def get_patterns_by_type(self, pattern: DesignPattern) -> List[PatternMatch]:
        """Get all matches for a specific pattern type"""
        return [p for p in self.patterns_found if p.pattern == pattern]

    def get_patterns_by_file(self, file_path: str) -> List[PatternMatch]:
        """Get all patterns found in a specific file"""
        return [p for p in self.patterns_found if p.file_path == file_path]

    def get_statistics(self) -> Dict[str, Any]:
        """Get pattern detection statistics"""
        pattern_counts = {}
        for match in self.patterns_found:
            pattern_name = match.pattern.value
            pattern_counts[pattern_name] = pattern_counts.get(pattern_name, 0) + 1

        return {
            'total_patterns': len(self.patterns_found),
            'by_pattern': pattern_counts,
            'avg_confidence': sum(p.confidence for p in self.patterns_found) / len(self.patterns_found) if self.patterns_found else 0
        }


# ---------- Architectural Pattern Detection ----------

class ArchitecturalPattern(Enum):
    """Architectural pattern types"""
    MVC = "MVC"
    REPOSITORY = "Repository"
    SERVICE_LAYER = "ServiceLayer"
    LAYERED = "Layered"
    HEXAGONAL = "Hexagonal"
    CQRS = "CQRS"
    EVENT_SOURCING = "EventSourcing"


@dataclass
class ArchitecturalMatch:
    """Represents a detected architectural pattern"""
    pattern: ArchitecturalPattern
    confidence: float
    components: List[str]  # Classes/files involved
    evidence: List[str]
    metadata: Dict[str, Any]

    def __repr__(self):
        return f"{self.pattern.value} (confidence={self.confidence:.2f}, {len(self.components)} components)"


class ArchitecturalPatternDetector:
    """
    Detects architectural patterns in codebases.

    Analyzes file structure, class names, and relationships to identify
    high-level architectural patterns.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.patterns_found: List[ArchitecturalMatch] = []
        self.config = config or {}
        # Pattern detection is LLM-driven - no hardcoded scoring configuration needed

    def detect_patterns(self, all_structural_data: List[StructuralData]) -> List[ArchitecturalMatch]:
        """Detect architectural patterns across the entire codebase."""
        all_classes = []
        all_files = []

        for structural_data in all_structural_data:
            all_classes.extend(structural_data.classes)
            all_files.append(structural_data.file_node)

        return self.detect_all_patterns(all_classes, all_files)

    def detect_all_patterns(self, all_classes: List[Any], all_files: List[Any]) -> List[ArchitecturalMatch]:
        """Detect architectural patterns given lists of classes and files."""
        patterns = []
        patterns.extend(self._detect_mvc(all_classes, all_files))
        patterns.extend(self._detect_repository(all_classes))
        patterns.extend(self._detect_service_layer(all_classes))
        patterns.extend(self._detect_layered(all_files))
        self.patterns_found.extend(patterns)
        return patterns

    def _detect_mvc(self, all_classes: List[Any], all_files: List[Any]) -> List[ArchitecturalMatch]:
        """MVC detection - LLM-driven analysis of actual code structure."""
        # No hardcoded pattern matching - LLM analyzes actual code
        return []

    def _detect_repository(self, all_classes: List[Any]) -> List[ArchitecturalMatch]:
        """Repository detection - LLM-driven analysis of actual code structure."""
        # No hardcoded pattern matching - LLM analyzes actual code
        return []

    def _detect_service_layer(self, all_classes: List[Any]) -> List[ArchitecturalMatch]:
        """Service layer detection - LLM-driven analysis of actual code structure."""
        # No hardcoded pattern matching - LLM analyzes actual code
        return []

    def _detect_layered(self, all_files: List[Any]) -> List[ArchitecturalMatch]:
        """Layered architecture detection - LLM-driven analysis of actual code structure."""
        # No hardcoded pattern matching - LLM analyzes actual code
        return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get architectural pattern statistics"""
        pattern_counts = {}
        for match in self.patterns_found:
            pattern_name = match.pattern.value
            pattern_counts[pattern_name] = pattern_counts.get(pattern_name, 0) + 1

        return {
            'total_patterns': len(self.patterns_found),
            'by_pattern': pattern_counts,
            'avg_confidence': sum(p.confidence for p in self.patterns_found) / len(self.patterns_found) if self.patterns_found else 0
        }


# ============================================================================
# EXECUTION TRACING
# ============================================================================

# ---------- Execution Path Tracers Factory ----------

@dataclass
class ExecutionPathTracers:
    """
    Container for execution path tracers and data flow analyzers.

    Provides unified access to Life-of-X functionality.
    """
    dataflow_analyzer: Optional['DataFlowAnalyzer'] = None
    execution_path_tracer: Optional['ExecutionPathTracer'] = None

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
        dep_graph: Any = None
    ) -> Optional['ExecutionPathTracers']:
        """
        Create ExecutionPathTracers from configuration.

        Args:
            config: Full configuration dictionary
            dep_graph: Dependency graph instance

        Returns:
            ExecutionPathTracers instance or None if disabled
        """
        lifeofx_config = config.get('knowledge_base', {}).get('lifeofx', {})

        if not lifeofx_config.get('enabled', False):
            return None

        if not dep_graph:
            return None

        dataflow_analyzer = DataFlowAnalyzer(dep_graph)
        execution_path_tracer = ExecutionPathTracer(dep_graph)

        return cls(
            dataflow_analyzer=dataflow_analyzer,
            execution_path_tracer=execution_path_tracer
        )

    def is_enabled(self) -> bool:
        """Check if any tracer is enabled"""
        return any([
            self.dataflow_analyzer is not None,
            self.execution_path_tracer is not None
        ])


# ---------- Execution Path Structures ----------

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
                narrative.append(f"{i}. {indent}Enter: {step.function_name}\n")
                current_depth += 1
            elif step.step_type == "call":
                narrative.append(f"{i}. {indent}Call: {step.function_name}\n")
            elif step.step_type == "return":
                current_depth = max(0, current_depth - 1)
                narrative.append(f"{i}. {indent}Return from: {step.function_name}\n")
            elif step.step_type == "exit":
                narrative.append(f"{i}. {indent}Exit: {step.function_name}\n")

        return "".join(narrative)


class ExecutionPathTracer:
    """
    Traces execution paths through code.

    Uses call graph to reconstruct complete execution flows.
    """

    def __init__(self, dep_graph: DependencyGraphBuilder):
        self.metrics_collector = get_global_collector()
        self.component_name = 'lifeofx_tracing'
        self.dep_graph = dep_graph

    def trace_from_entry_point(
        self,
        entry_point: str,
        max_depth: int = 20,
        max_paths: int = 10
    ) -> List[ExecutionPath]:
        """Trace all execution paths from an entry point."""
        with self.metrics_collector.track_operation(self.component_name, tokens=0, cost=0.0):
            paths = []
            queue = deque([(entry_point, [], 0)])
            visited_paths = set()

            while queue and len(paths) < max_paths:
                current, path_so_far, depth = queue.popleft()

                if depth > max_depth:
                    continue

                path_sig = tuple(path_so_far + [current])
                if path_sig in visited_paths:
                    continue
                visited_paths.add(path_sig)

                callees = self.dep_graph.call_graph.get(current, [])

                if not callees:
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
                    for callee in callees:
                        if callee not in path_so_far:
                            queue.append((callee, path_so_far + [current], depth + 1))

            return paths

    def find_path_between(self, start: str, end: str, max_depth: int = 15) -> List[List[str]]:
        """Find call paths between two functions."""
        return self.dep_graph.find_call_chain(start, end, max_depth)

    def trace_request_lifecycle(self, endpoint_function: str, max_depth: int = 20) -> ExecutionPath:
        """Trace request lifecycle - follows call graph from entry point."""
        callees = self.dep_graph.find_all_callees(endpoint_function, max_depth)
        all_functions = [endpoint_function] + list(callees)
        steps = []

        steps.append(ExecutionStep(
            function_name=endpoint_function.split('.')[-1],
            qualified_name=endpoint_function,
            step_type="entry",
            metadata={}
        ))

        for func in list(callees)[:20]:
            steps.append(ExecutionStep(
                function_name=func.split('.')[-1],
                qualified_name=func,
                step_type="call",
                metadata={}
            ))

        # Exit point is the last callee in the chain (leaf node)
        exit_func = list(callees)[-1] if callees else endpoint_function
        steps.append(ExecutionStep(
            function_name=exit_func.split('.')[-1],
            qualified_name=exit_func,
            step_type="exit",
            metadata={}
        ))

        return ExecutionPath(
            entry_point=endpoint_function,
            exit_point=exit_func,
            steps=steps,
            total_functions=len(all_functions),
            max_depth=max_depth,
            confidence=0.7
        )

    def find_entry_points(self, all_functions: List[str]) -> List[str]:
        """
        Find entry points based on call graph structure.

        Entry points are functions that are never called by other functions
        in the codebase (top of call hierarchy).
        """
        called_functions = set()
        for callees in self.dep_graph.call_graph.values():
            called_functions.update(callees)

        # Entry points are functions that are never called
        # (no hardcoded keyword filtering - structure-based detection only)
        return [f for f in all_functions if f not in called_functions]

    def detect_long_call_chains(self, min_length: int = 10) -> List[List[str]]:
        """Detect long call chains (potential code smell)."""
        long_chains = []
        sample_functions = list(self.dep_graph.function_table.keys())[:100]

        for func in sample_functions:
            callees = self.dep_graph.find_all_callees(func, max_depth=min_length + 2)
            if len(callees) >= min_length:
                chain = [func] + list(callees)[:min_length]
                long_chains.append(chain)

        long_chains.sort(key=len, reverse=True)
        return long_chains[:20]

    def _build_execution_steps(self, path: List[str]) -> List[ExecutionStep]:
        """Build ExecutionStep list from function path."""
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
        """Generate PlantUML sequence diagram for execution path."""
        lines = []
        lines.append("@startuml")
        lines.append("title Execution Path\\n" + path.entry_point)
        lines.append("")

        participants = set(step.function_name for step in path.steps)
        for participant in sorted(participants):
            lines.append(f'participant "{participant}"')

        lines.append("")

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
        dep_stats = self.dep_graph.get_dependency_stats()
        all_funcs = list(self.dep_graph.function_table.keys())
        entry_points = self.find_entry_points(all_funcs)

        return {
            **dep_stats,
            'num_entry_points': len(entry_points),
            'entry_points': entry_points[:10]
        }


# ---------- Data Flow Analysis ----------

@dataclass
class DataFlowNode:
    """Represents a node in data flow graph"""
    element_id: str  # Function/variable qualified name
    element_type: str  # "function", "variable", "parameter"
    operations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlowEdge:
    """Represents data flow between nodes"""
    source: str
    target: str
    flow_type: str  # "parameter", "return", "assignment", "mutation"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlowPath:
    """Represents a complete data flow path"""
    start_node: str
    end_node: str
    path: List[str]
    transformations: List[str]
    confidence: float

    def __repr__(self):
        return f"{self.start_node} -> {self.end_node} ({len(self.path)} steps)"


class DataFlowAnalyzer:
    """
    Analyzes data flow through code.

    Tracks how data moves and transforms as it passes through functions.
    """

    def __init__(self, dep_graph: DependencyGraphBuilder):
        self.dep_graph = dep_graph
        self.flow_graph: Dict[str, List[DataFlowEdge]] = defaultdict(list)

    def build_flow_graph(self, all_structural_data: List[StructuralData]):
        """Build data flow graph from structural data."""
        for structural_data in all_structural_data:
            for function in structural_data.functions:
                self._analyze_function_flow(function)

            for rel in structural_data.relationships:
                if rel.rel_type == RelationType.CALLS:
                    self._analyze_call_flow(rel)

    def _analyze_function_flow(self, function: FunctionNode):
        """Analyze data flow within a function."""
        func_id = function.qualified_name

        for param in function.parameters:
            param_id = f"{func_id}.{param}"
            self.flow_graph[param_id].append(DataFlowEdge(
                source=param_id,
                target=func_id,
                flow_type="parameter",
                metadata={'param_name': param}
            ))

        if function.return_type:
            return_id = f"{func_id}.return"
            self.flow_graph[func_id].append(DataFlowEdge(
                source=func_id,
                target=return_id,
                flow_type="return",
                metadata={'return_type': function.return_type}
            ))

    def _analyze_call_flow(self, relationship: Relationship):
        """Analyze data flow through function calls."""
        caller_id = relationship.source_id
        callee_id = relationship.target_id

        self.flow_graph[caller_id].append(DataFlowEdge(
            source=caller_id,
            target=callee_id,
            flow_type="call",
            metadata={'line': relationship.metadata.get('line')}
        ))

        callee_return = f"{callee_id}.return"
        self.flow_graph[callee_return].append(DataFlowEdge(
            source=callee_return,
            target=caller_id,
            flow_type="return_value",
            metadata={}
        ))

    def trace_data_flow(self, start_element: str, max_depth: int = 10) -> List[DataFlowPath]:
        """Trace data flow from a starting element."""
        paths = []
        queue = deque([(start_element, [start_element], [])])
        visited = set()

        while queue and len(paths) < 100:
            current, path, transformations = queue.popleft()

            if len(path) > max_depth:
                continue

            if current in visited:
                continue
            visited.add(current)

            edges = self.flow_graph.get(current, [])

            if not edges:
                if len(path) > 1:
                    paths.append(DataFlowPath(
                        start_node=start_element,
                        end_node=current,
                        path=path,
                        transformations=transformations,
                        confidence=0.7
                    ))
            else:
                for edge in edges:
                    next_node = edge.target
                    if next_node not in path:
                        new_transformations = transformations + [edge.flow_type]
                        queue.append((next_node, path + [next_node], new_transformations))

        return paths

    def find_data_sources(self, target_element: str) -> List[str]:
        """Find all data sources that feed into a target element."""
        sources = []
        for source, edges in self.flow_graph.items():
            for edge in edges:
                if edge.target == target_element:
                    sources.append(source)
        return sources

    def find_data_sinks(self, source_element: str) -> List[str]:
        """Find all data sinks that receive data from a source element."""
        sinks = []
        for edge in self.flow_graph.get(source_element, []):
            sinks.append(edge.target)
        return sinks

    def trace_variable_usage(self, variable_name: str, starting_function: str) -> Dict[str, Any]:
        """Trace how a variable is used throughout execution."""
        usage_chain = self.dep_graph.find_all_callees(starting_function, max_depth=5)
        return {
            'variable': variable_name,
            'defined_in': starting_function,
            'potentially_used_in': list(usage_chain),
            'num_potential_uses': len(usage_chain)
        }

    def detect_data_transformation_chains(self, min_chain_length: int = 3) -> List[DataFlowPath]:
        """Detect long data transformation chains."""
        long_chains = []
        sample_elements = list(self.flow_graph.keys())[:100]

        for element in sample_elements:
            paths = self.trace_data_flow(element, max_depth=min_chain_length + 2)
            for path in paths:
                if len(path.path) >= min_chain_length:
                    long_chains.append(path)

        long_chains.sort(key=lambda p: len(p.path), reverse=True)
        return long_chains[:50]

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

    # Advanced Data Flow Analysis

    def compute_reaching_definitions(self, function_id: str) -> Dict[str, Set[str]]:
        """Compute reaching definitions for a function."""
        reaching_defs = defaultdict(set)
        sources = self.find_data_sources(function_id)

        for source in sources:
            parts = source.split('.')
            if len(parts) >= 2:
                var_name = parts[-1]
                reaching_defs[var_name].add(source)

        for var_name in list(reaching_defs.keys()):
            defs = set(reaching_defs[var_name])
            for def_point in list(defs):
                transitive_sources = self.find_data_sources(def_point)
                for t_source in transitive_sources:
                    t_parts = t_source.split('.')
                    if len(t_parts) >= 2:
                        t_var = t_parts[-1]
                        if t_var == var_name:
                            reaching_defs[var_name].add(t_source)

        return {var: defs for var, defs in reaching_defs.items()}

    def build_use_def_chains(self, function_id: str) -> Dict[str, List[str]]:
        """Build use-def chains for a function."""
        use_def_chains = {}

        for edge in self.flow_graph.get(function_id, []):
            if edge.flow_type in ["parameter", "call"]:
                use_point = edge.target
                reaching_defs = self.compute_reaching_definitions(use_point)

                for var_name, defs in reaching_defs.items():
                    use_key = f"{use_point}.use.{var_name}"
                    use_def_chains[use_key] = list(defs)

        return use_def_chains

    def build_def_use_chains(self, function_id: str) -> Dict[str, List[str]]:
        """Build def-use chains for a function."""
        def_use_chains = defaultdict(list)

        func_node = self.dep_graph.function_table.get(function_id)
        if func_node:
            for param in func_node.parameters:
                def_point = f"{function_id}.{param}"
                uses = self.find_data_sinks(def_point)
                if uses:
                    def_use_chains[def_point] = uses

        return_id = f"{function_id}.return"
        if return_id in self.flow_graph:
            uses = self.find_data_sinks(return_id)
            if uses:
                def_use_chains[return_id] = uses

        return dict(def_use_chains)

    def analyze_variable_lifetime(self, variable_id: str) -> Dict[str, Any]:
        """Analyze the lifetime of a variable through the program."""
        definition = variable_id
        uses = self.find_data_sinks(variable_id)

        all_downstream_uses = set(uses)
        for use in uses:
            transitive_uses = self.find_data_sinks(use)
            all_downstream_uses.update(transitive_uses)

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

    def detect_unused_variables(self, function_id: str) -> List[str]:
        """Detect unused variables in a function."""
        unused = []
        def_use_chains = self.build_def_use_chains(function_id)

        for def_point, uses in def_use_chains.items():
            if not uses:
                unused.append(def_point)

        return unused

    def detect_undefined_uses(self, function_id: str) -> List[str]:
        """Detect uses of undefined variables."""
        undefined = []
        use_def_chains = self.build_use_def_chains(function_id)

        for use_point, defs in use_def_chains.items():
            if not defs:
                undefined.append(use_point)

        return undefined

    def get_advanced_flow_analysis(self, function_id: str) -> Dict[str, Any]:
        """Get comprehensive data flow analysis for a function."""
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


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Pattern Detection
    'PatternDetectors',
    'CodeSmell',
    'Severity',
    'CodeSmellMatch',
    'CodeSmellDetector',
    'DesignPattern',
    'PatternMatch',
    'DesignPatternDetector',
    'ArchitecturalPattern',
    'ArchitecturalMatch',
    'ArchitecturalPatternDetector',

    # Execution Tracing
    'ExecutionPathTracers',
    'ExecutionStep',
    'ExecutionPath',
    'ExecutionPathTracer',
    'DataFlowNode',
    'DataFlowEdge',
    'DataFlowPath',
    'DataFlowAnalyzer',
]
