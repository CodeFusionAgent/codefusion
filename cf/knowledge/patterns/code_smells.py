"""
Code Smell Detection

Detects code smells and anti-patterns:
- God Class (too many responsibilities)
- Long Method (too complex)
- Feature Envy (accessing other class's data too much)
- Data Class (only getters/setters)
- Duplicate Code
"""

from typing import List, Dict, Any, Set
from dataclasses import dataclass
from enum import Enum

from cf.knowledge.structural.schema import StructuralData, ClassNode, FunctionNode


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
        smells = []

        # Detect class-level smells
        for class_node in structural_data.classes:
            smells.extend(self._detect_god_class(class_node))
            smells.extend(self._detect_data_class(class_node, structural_data.functions))
            smells.extend(self._detect_lazy_class(class_node))

        # Detect method-level smells
        for function in structural_data.functions:
            smells.extend(self._detect_long_method(function))
            smells.extend(self._detect_long_parameter_list(function))

        self.smells_found.extend(smells)
        return smells

    def _detect_god_class(self, class_node: ClassNode) -> List[CodeSmellMatch]:
        """
        Detect God Class (class with too many responsibilities).

        Indicators:
        - Too many methods
        - Too many lines of code
        - Does too much
        """
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
        """
        Detect Long Method (method is too long or too complex).

        Indicators:
        - Too many lines
        - High cyclomatic complexity
        """
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
        """
        Detect Long Parameter List.

        Indicators:
        - Too many parameters
        """
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
        """
        Detect Data Class (class with only getters/setters).

        Indicators:
        - Few methods
        - All methods are simple getters/setters
        - No behavior
        """
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
        """
        Detect Lazy Class (class that doesn't do much).

        Indicators:
        - Very few methods
        - Very small
        """
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

    def print_report(self):
        """Print code smell report"""
        if not self.smells_found:
            print("✅ No code smells detected")
            return

        stats = self.get_statistics()

        print(f"\n🔍 Code Smell Detection Report:")
        print(f"   Total smells found: {stats['total_smells']}")
        print(f"\n   By severity:")
        for severity, count in sorted(stats['by_severity'].items()):
            print(f"     - {severity}: {count}")

        print(f"\n   By type:")
        for smell, count in sorted(stats['by_smell'].items(), key=lambda x: x[1], reverse=True):
            print(f"     - {smell}: {count}")

        # Show critical and high severity smells
        critical_smells = self.get_smells_by_severity(Severity.CRITICAL) + self.get_smells_by_severity(Severity.HIGH)

        if critical_smells:
            print(f"\n   🚨 High priority smells:")
            for smell in critical_smells[:10]:  # Show top 10
                print(f"\n   {smell}")
                for suggestion in smell.suggestions:
                    print(f"     💡 {suggestion}")
