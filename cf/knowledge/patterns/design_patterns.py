"""
Design Pattern Detection

Detects common design patterns in code:
- Creational: Singleton, Factory, Builder, Prototype
- Structural: Adapter, Decorator, Proxy, Facade
- Behavioral: Observer, Strategy, Command, State
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

from cf.knowledge.structural.schema import StructuralData, ClassNode, FunctionNode
from cf.knowledge.metrics import KnowledgeLayerMetrics, register_layer_metrics


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


class DesignPatternDetector(KnowledgeLayerMetrics):
    """
    Detects design patterns in code using heuristics and rules.

    Uses class structure, method names, and relationships to identify patterns.
    All confidence scoring thresholds are configurable via config.yaml.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize pattern detector.

        Args:
            config: Configuration dictionary with pattern detection settings
        """
        # Initialize metrics tracking
        super().__init__('pattern_detection')
        register_layer_metrics(self)

        self.patterns_found: List[PatternMatch] = []

        # Load pattern detection configuration
        self.config = config or {}
        pattern_config = self.config.get('knowledge_base', {}).get('patterns', {}).get('confidence', {})

        # Load all confidence thresholds from config (with fallback defaults for safety)
        self.min_confidence = pattern_config.get('min_confidence', 0.5)
        self.max_confidence = pattern_config.get('max_confidence', 0.95)

        # Singleton pattern scoring
        self.singleton_name_score = pattern_config.get('singleton_private_constructor', 0.3)
        self.singleton_method_score = pattern_config.get('singleton_static_instance', 0.2)
        self.singleton_doc_score = pattern_config.get('singleton_lazy_init', 0.3)

        # Factory pattern scoring
        self.factory_name_score = pattern_config.get('factory_return_type', 0.5)
        self.factory_inheritance_score = pattern_config.get('factory_conditional', 0.3)
        self.factory_doc_score = pattern_config.get('factory_polymorphism', 0.2)

        # Builder pattern scoring
        self.builder_name_score = pattern_config.get('strategy_interface', 0.6)  # Reusing strategy_interface
        self.builder_methods_score = pattern_config.get('decorator_enhancement', 0.2)
        self.builder_doc_score = pattern_config.get('observer_subscription', 0.2)

        # Adapter pattern scoring
        self.adapter_name_score = pattern_config.get('observer_subject_methods', 0.7)  # Reusing observer score
        self.adapter_wrapper_score = pattern_config.get('factory_return_type', 0.5)
        self.adapter_doc_score = pattern_config.get('observer_subscription', 0.2)

        # Decorator pattern scoring
        self.decorator_name_score = pattern_config.get('decorator_wrapping', 0.7)
        self.decorator_interface_score = pattern_config.get('decorator_same_interface', 0.2)
        self.decorator_doc_score = pattern_config.get('decorator_enhancement', 0.2)

        # Proxy pattern scoring
        self.proxy_name_score = pattern_config.get('service_business_logic', 0.8)  # Reusing service score
        self.proxy_doc_score = pattern_config.get('observer_subscription', 0.2)

        # Observer pattern scoring
        self.observer_name_score = pattern_config.get('observer_subject_methods', 0.7)
        self.observer_listener_score = pattern_config.get('observer_subject_methods', 0.6)
        self.observer_doc_score = pattern_config.get('observer_update_method', 0.2)

        # Strategy pattern scoring
        self.strategy_name_score = pattern_config.get('strategy_interface', 0.7)
        self.strategy_interface_score = pattern_config.get('strategy_context', 0.2)
        self.strategy_doc_score = pattern_config.get('strategy_runtime_switching', 0.2)

        # Command pattern scoring
        self.command_name_score = pattern_config.get('service_business_logic', 0.8)  # Reusing service score
        self.command_doc_score = pattern_config.get('observer_update_method', 0.2)

    def detect_patterns(self, structural_data: StructuralData) -> List[PatternMatch]:
        """
        Detect all design patterns in structural data.

        Args:
            structural_data: StructuralData from AST parsing

        Returns:
            List of detected patterns
        """
        return self.detect_all_patterns(structural_data.classes)

    def detect_all_patterns(self, all_classes: List[ClassNode]) -> List[PatternMatch]:
        """
        Detect all design patterns in a list of classes.

        Args:
            all_classes: List[ClassNode] objects

        Returns:
            List of detected patterns
        """
        # Track this operation (pattern detection is CPU-bound, no tokens/cost)
        with self.track_operation(tokens=0, cost=0.0):
            patterns = []

            for class_node in all_classes:
                # Detect creational patterns
                patterns.extend(self._detect_singleton(class_node))
                patterns.extend(self._detect_factory(class_node))
                patterns.extend(self._detect_builder(class_node))

                # Detect structural patterns
                patterns.extend(self._detect_adapter(class_node))
                patterns.extend(self._detect_decorator(class_node))
                patterns.extend(self._detect_proxy(class_node))

                # Detect behavioral patterns
                patterns.extend(self._detect_observer(class_node))
                patterns.extend(self._detect_strategy(class_node))
                patterns.extend(self._detect_command(class_node))

            self.patterns_found.extend(patterns)
            return patterns

    # ========== Creational Patterns ==========

    def _detect_singleton(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Singleton pattern.

        Indicators:
        - Private constructor (__init__ checks instance)
        - Class method like getInstance() or instance()
        - Class variable storing single instance
        """
        evidence = []
        confidence = 0.0

        # Check class name
        if 'singleton' in class_node.name.lower():
            evidence.append("Class name contains 'singleton'")
            confidence += self.singleton_name_score

        # Check for getInstance/instance method
        # (Would need method info from structural data)
        if class_node.num_methods > 0:
            # Heuristic: if class has few methods and one is likely getInstance
            if class_node.num_methods <= 3:
                evidence.append("Class has few methods (typical for Singleton)")
                confidence += self.singleton_method_score

        # Check docstring
        if class_node.docstring and 'singleton' in class_node.docstring.lower():
            evidence.append("Docstring mentions singleton")
            confidence += self.singleton_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.SINGLETON,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={'num_methods': class_node.num_methods}
            )]

        return []

    def _detect_factory(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Factory pattern.

        Indicators:
        - Class name contains 'Factory'
        - Has create/make/build methods
        - Returns instances of other classes
        """
        evidence = []
        confidence = 0.0

        # Check class name
        if 'factory' in class_node.name.lower():
            evidence.append("Class name contains 'factory'")
            confidence += self.factory_name_score

        # Check base classes
        if any('factory' in base.lower() for base in class_node.base_classes):
            evidence.append("Inherits from factory class")
            confidence += self.factory_inheritance_score

        # Check docstring
        if class_node.docstring:
            doc_lower = class_node.docstring.lower()
            if any(word in doc_lower for word in ['factory', 'creates', 'builds']):
                evidence.append("Docstring suggests factory behavior")
                confidence += self.factory_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.FACTORY,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={}
            )]

        return []

    def _detect_builder(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Builder pattern.

        Indicators:
        - Class name contains 'Builder'
        - Has chaining methods (return self)
        - Has build() method
        """
        evidence = []
        confidence = 0.0

        # Check class name
        if 'builder' in class_node.name.lower():
            evidence.append("Class name contains 'builder'")
            confidence += self.builder_name_score

        # Check for typical builder method count (many setters + build)
        if class_node.num_methods >= 5:
            evidence.append(f"Has many methods ({class_node.num_methods}), typical for builder")
            confidence += self.builder_methods_score

        # Check docstring
        if class_node.docstring and 'builder' in class_node.docstring.lower():
            evidence.append("Docstring mentions builder")
            confidence += self.builder_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.BUILDER,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={'num_methods': class_node.num_methods}
            )]

        return []

    # ========== Structural Patterns ==========

    def _detect_adapter(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Adapter pattern.

        Indicators:
        - Class name contains 'Adapter' or 'Wrapper'
        - Wraps another class
        """
        evidence = []
        confidence = 0.0

        # Check class name
        name_lower = class_node.name.lower()
        if 'adapter' in name_lower:
            evidence.append("Class name contains 'adapter'")
            confidence += self.adapter_name_score
        elif 'wrapper' in name_lower:
            evidence.append("Class name contains 'wrapper'")
            confidence += self.adapter_wrapper_score

        # Check docstring
        if class_node.docstring:
            doc_lower = class_node.docstring.lower()
            if 'adapt' in doc_lower or 'wrapper' in doc_lower:
                evidence.append("Docstring suggests adapter behavior")
                confidence += self.adapter_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.ADAPTER,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={}
            )]

        return []

    def _detect_decorator(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Decorator pattern.

        Indicators:
        - Class name contains 'Decorator'
        - Inherits from same interface as wrapped class
        """
        evidence = []
        confidence = 0.0

        # Check class name
        if 'decorator' in class_node.name.lower():
            evidence.append("Class name contains 'decorator'")
            confidence += self.decorator_name_score

        # Check inheritance (if has same interface as another class)
        if len(class_node.base_classes) > 0:
            evidence.append("Implements interface (typical for decorator)")
            confidence += self.decorator_interface_score

        # Check docstring
        if class_node.docstring and 'decorator' in class_node.docstring.lower():
            evidence.append("Docstring mentions decorator")
            confidence += self.decorator_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.DECORATOR,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={}
            )]

        return []

    def _detect_proxy(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Proxy pattern.

        Indicators:
        - Class name contains 'Proxy'
        - Controls access to another object
        """
        evidence = []
        confidence = 0.0

        # Check class name
        if 'proxy' in class_node.name.lower():
            evidence.append("Class name contains 'proxy'")
            confidence += self.proxy_name_score

        # Check docstring
        if class_node.docstring:
            doc_lower = class_node.docstring.lower()
            if 'proxy' in doc_lower or 'controls access' in doc_lower:
                evidence.append("Docstring suggests proxy behavior")
                confidence += self.proxy_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.PROXY,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={}
            )]

        return []

    # ========== Behavioral Patterns ==========

    def _detect_observer(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Observer pattern.

        Indicators:
        - Class name contains 'Observer', 'Listener', 'Subscriber'
        - Has notify/update methods
        """
        evidence = []
        confidence = 0.0

        # Check class name
        name_lower = class_node.name.lower()
        if 'observer' in name_lower:
            evidence.append("Class name contains 'observer'")
            confidence += self.observer_name_score
        elif 'listener' in name_lower:
            evidence.append("Class name contains 'listener'")
            confidence += self.observer_listener_score
        elif 'subscriber' in name_lower:
            evidence.append("Class name contains 'subscriber'")
            confidence += self.observer_listener_score

        # Check docstring
        if class_node.docstring:
            doc_lower = class_node.docstring.lower()
            if any(word in doc_lower for word in ['observer', 'notify', 'publish', 'subscribe']):
                evidence.append("Docstring suggests observer behavior")
                confidence += self.observer_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.OBSERVER,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={}
            )]

        return []

    def _detect_strategy(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Strategy pattern.

        Indicators:
        - Class name contains 'Strategy'
        - Interface with execute/apply method
        """
        evidence = []
        confidence = 0.0

        # Check class name
        if 'strategy' in class_node.name.lower():
            evidence.append("Class name contains 'strategy'")
            confidence += self.strategy_name_score

        # Check if it's likely an interface/base class
        if class_node.is_abstract or len(class_node.base_classes) > 0:
            evidence.append("Is abstract or implements interface")
            confidence += self.strategy_interface_score

        # Check docstring
        if class_node.docstring and 'strategy' in class_node.docstring.lower():
            evidence.append("Docstring mentions strategy")
            confidence += self.strategy_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.STRATEGY,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={}
            )]

        return []

    def _detect_command(self, class_node: ClassNode) -> List[PatternMatch]:
        """
        Detect Command pattern.

        Indicators:
        - Class name contains 'Command'
        - Has execute method
        """
        evidence = []
        confidence = 0.0

        # Check class name
        if 'command' in class_node.name.lower():
            evidence.append("Class name contains 'command'")
            confidence += self.command_name_score

        # Check docstring
        if class_node.docstring:
            doc_lower = class_node.docstring.lower()
            if 'command' in doc_lower or 'execute' in doc_lower:
                evidence.append("Docstring suggests command behavior")
                confidence += self.command_doc_score

        if confidence >= self.min_confidence:
            return [PatternMatch(
                pattern=DesignPattern.COMMAND,
                confidence=min(confidence, self.max_confidence),
                class_name=class_node.name,
                qualified_name=class_node.qualified_name,
                file_path=class_node.file_path,
                evidence=evidence,
                metadata={}
            )]

        return []

    # ========== Analysis Methods ==========

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

    def print_report(self):
        """Print pattern detection report"""
        if not self.patterns_found:
            print("No design patterns detected")
            return

        stats = self.get_statistics()

        print(f"\n🎨 Design Pattern Detection Report:")
        print(f"   Total patterns found: {stats['total_patterns']}")
        print(f"   Average confidence: {stats['avg_confidence']:.2f}")
        print(f"\n   Patterns detected:")

        for pattern_name, count in sorted(stats['by_pattern'].items(), key=lambda x: x[1], reverse=True):
            print(f"     - {pattern_name}: {count}")

        print(f"\n   Details:")
        for match in self.patterns_found:
            print(f"\n   {match}")
            for evidence in match.evidence:
                print(f"     • {evidence}")
