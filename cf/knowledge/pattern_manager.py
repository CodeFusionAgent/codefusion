"""
Pattern Analysis Manager

Handles design pattern detection and code smell analysis.
Extracted from StructuralPipeline to improve maintainability.
"""

from typing import Dict, Any, Optional

from cf.knowledge.structural.neo4j_client import Neo4jKnowledgeBase
from cf.knowledge.patterns.design_patterns import DesignPatternDetector
from cf.knowledge.patterns.architectural_patterns import ArchitecturalPatternDetector
from cf.knowledge.patterns.code_smells import CodeSmellDetector


class PatternAnalysisManager:
    """
    Manages pattern detection and code smell analysis.

    Responsibilities:
    - Design pattern detection (Singleton, Factory, Observer, etc.)
    - Architectural pattern detection (MVC, Repository, etc.)
    - Code smell detection (God Class, Long Method, etc.)
    """

    def __init__(self, config: Dict[str, Any], kb: Neo4jKnowledgeBase = None):
        self.config = config
        self.patterns_config = config.get('knowledge_base', {}).get('patterns', {})
        self.kb = kb

        self._design_pattern_detector = None
        self._architectural_pattern_detector = None
        self._code_smell_detector = None

    def is_enabled(self) -> bool:
        """Check if pattern analysis is enabled"""
        return self.patterns_config.get('enabled', False)

    def initialize(self):
        """Initialize pattern detectors"""
        if not self.is_enabled() or not self.kb:
            return

        print("   🔍 Initializing pattern detection...")

        # Initialize detectors
        if self.patterns_config.get('detect_design_patterns', True):
            self._design_pattern_detector = DesignPatternDetector()

        if self.patterns_config.get('detect_architectural_patterns', True):
            self._architectural_pattern_detector = ArchitecturalPatternDetector()

        if self.patterns_config.get('detect_code_smells', True):
            thresholds = self.patterns_config.get('thresholds', {})
            self._code_smell_detector = CodeSmellDetector(config=thresholds)

    @property
    def design_pattern_detector(self) -> Optional[DesignPatternDetector]:
        """Get design pattern detector (lazy initialization)"""
        if not self.is_enabled():
            return None

        if self._design_pattern_detector is None and self.patterns_config.get('detect_design_patterns', True):
            self._design_pattern_detector = DesignPatternDetector()

        return self._design_pattern_detector

    @property
    def architectural_pattern_detector(self) -> Optional[ArchitecturalPatternDetector]:
        """Get architectural pattern detector (lazy initialization)"""
        if not self.is_enabled():
            return None

        if self._architectural_pattern_detector is None and self.patterns_config.get('detect_architectural_patterns', True):
            self._architectural_pattern_detector = ArchitecturalPatternDetector()

        return self._architectural_pattern_detector

    @property
    def code_smell_detector(self) -> Optional[CodeSmellDetector]:
        """Get code smell detector (lazy initialization)"""
        if not self.is_enabled():
            return None

        if self._code_smell_detector is None and self.patterns_config.get('detect_code_smells', True):
            thresholds = self.patterns_config.get('thresholds', {})
            self._code_smell_detector = CodeSmellDetector(config=thresholds)

        return self._code_smell_detector
