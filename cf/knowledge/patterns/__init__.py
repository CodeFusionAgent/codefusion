"""
Pattern Recognition Layer

Detects design patterns, architectural patterns, and code smells:
- Design patterns (Factory, Singleton, Observer, Strategy, etc.)
- Architectural patterns (MVC, Repository, Service Layer, etc.)
- Code smells (God Class, Long Method, Feature Envy, etc.)
"""

from cf.knowledge.patterns.design_patterns import DesignPatternDetector
from cf.knowledge.patterns.architectural_patterns import ArchitecturalPatternDetector
from cf.knowledge.patterns.code_smells import CodeSmellDetector

__all__ = [
    "DesignPatternDetector",
    "ArchitecturalPatternDetector",
    "CodeSmellDetector"
]
