"""
Architectural Pattern Detection

Detects high-level architectural patterns:
- MVC (Model-View-Controller)
- Repository Pattern
- Service Layer
- Layered Architecture
- Microservices patterns
"""

from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from cf.knowledge.structural.schema import StructuralData


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
    All confidence scoring thresholds are configurable via config.yaml.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize architectural pattern detector.

        Args:
            config: Configuration dictionary with architectural pattern detection settings
        """
        self.patterns_found: List[ArchitecturalMatch] = []

        # Load architectural pattern detection configuration
        self.config = config or {}
        pattern_config = self.config.get('knowledge_base', {}).get('patterns', {}).get('confidence', {})

        # Load all confidence thresholds from config (with fallback defaults for safety)
        self.min_confidence = pattern_config.get('min_confidence', 0.5)
        self.max_confidence = pattern_config.get('max_confidence', 0.95)

        # MVC pattern scoring
        self.mvc_model_dir_score = pattern_config.get('mvc_model_dir', 0.25)
        self.mvc_view_dir_score = pattern_config.get('mvc_view_dir', 0.25)
        self.mvc_controller_dir_score = pattern_config.get('mvc_controller_dir', 0.25)
        self.mvc_model_classes_score = pattern_config.get('mvc_model_classes', 0.15)
        self.mvc_view_classes_score = pattern_config.get('mvc_view_classes', 0.10)
        self.mvc_controller_classes_score = pattern_config.get('mvc_controller_classes', 0.15)

        # Repository pattern scoring
        self.repository_classes_score = pattern_config.get('repository_classes', 0.8)
        self.repository_naming_score = pattern_config.get('repository_naming', 0.15)

        # Service layer pattern scoring
        self.service_layer_classes_score = pattern_config.get('service_layer_classes', 0.7)
        self.service_layer_multiple_score = pattern_config.get('service_layer_multiple', 0.2)

        # Layered architecture scoring
        self.layered_base_score = pattern_config.get('layered_base', 0.5)
        self.layered_per_layer_score = pattern_config.get('layered_per_layer', 0.1)
        self.layered_services_repos_score = pattern_config.get('layered_services_repos', 0.15)

    def detect_patterns(self, all_structural_data: List[StructuralData]) -> List[ArchitecturalMatch]:
        """
        Detect architectural patterns across the entire codebase.

        Args:
            all_structural_data: List of StructuralData from all files

        Returns:
            List of detected architectural patterns
        """
        # Collect all classes and files
        all_classes = []
        all_files = []

        for structural_data in all_structural_data:
            all_classes.extend(structural_data.classes)
            all_files.append(structural_data.file_node)

        return self.detect_all_patterns(all_classes, all_files)

    def detect_all_patterns(self, all_classes: List[Any], all_files: List[Any]) -> List[ArchitecturalMatch]:
        """
        Detect architectural patterns given lists of classes and files.

        Args:
            all_classes: List of ClassNode objects
            all_files: List of FileNode objects

        Returns:
            List of detected architectural patterns
        """
        patterns = []

        # Detect patterns
        patterns.extend(self._detect_mvc(all_classes, all_files))
        patterns.extend(self._detect_repository(all_classes))
        patterns.extend(self._detect_service_layer(all_classes))
        patterns.extend(self._detect_layered(all_files))

        self.patterns_found.extend(patterns)
        return patterns

    def _detect_mvc(self, all_classes: List[Any], all_files: List[Any]) -> List[ArchitecturalMatch]:
        """
        Detect MVC (Model-View-Controller) pattern.

        Indicators:
        - Directories named models/, views/, controllers/
        - Classes with Model, View, Controller suffixes
        - Clear separation of concerns
        """
        evidence = []
        components = []
        confidence = 0.0

        # Track classes by type
        models = []
        views = []
        controllers = []

        # Check file paths for MVC structure
        has_model_dir = False
        has_view_dir = False
        has_controller_dir = False

        for file_node in all_files:
            path_lower = file_node.path.lower()

            if '/models/' in path_lower or path_lower.startswith('models/'):
                has_model_dir = True
            if '/views/' in path_lower or path_lower.startswith('views/'):
                has_view_dir = True
            if '/controllers/' in path_lower or path_lower.startswith('controllers/'):
                has_controller_dir = True

        # Check class names
        for class_node in all_classes:
            name_lower = class_node.name.lower()

            if 'model' in name_lower or 'entity' in name_lower:
                models.append(class_node.qualified_name)
            if 'view' in name_lower or 'template' in name_lower:
                views.append(class_node.qualified_name)
            if 'controller' in name_lower or 'handler' in name_lower:
                controllers.append(class_node.qualified_name)

        # Score MVC pattern
        if has_model_dir:
            evidence.append("Has models/ directory")
            confidence += self.mvc_model_dir_score
        if has_view_dir:
            evidence.append("Has views/ directory")
            confidence += self.mvc_view_dir_score
        if has_controller_dir:
            evidence.append("Has controllers/ directory")
            confidence += self.mvc_controller_dir_score

        if len(models) >= 2:
            evidence.append(f"Found {len(models)} model classes")
            confidence += self.mvc_model_classes_score
            components.extend(models[:5])  # Include first 5
        if len(views) >= 1:
            evidence.append(f"Found {len(views)} view classes")
            confidence += self.mvc_view_classes_score
            components.extend(views[:5])
        if len(controllers) >= 2:
            evidence.append(f"Found {len(controllers)} controller classes")
            confidence += self.mvc_controller_classes_score
            components.extend(controllers[:5])

        if confidence >= self.min_confidence:
            return [ArchitecturalMatch(
                pattern=ArchitecturalPattern.MVC,
                confidence=min(confidence, self.max_confidence),
                components=components,
                evidence=evidence,
                metadata={
                    'models': len(models),
                    'views': len(views),
                    'controllers': len(controllers)
                }
            )]

        return []

    def _detect_repository(self, all_classes: List[Any]) -> List[ArchitecturalMatch]:
        """
        Detect Repository pattern.

        Indicators:
        - Classes named *Repository
        - Data access abstraction
        """
        evidence = []
        components = []
        confidence = 0.0

        repositories = []

        for class_node in all_classes:
            if 'repository' in class_node.name.lower():
                repositories.append(class_node.qualified_name)

        if len(repositories) >= 2:
            evidence.append(f"Found {len(repositories)} repository classes")
            confidence += self.repository_classes_score
            components = repositories[:10]

            # Check for common repository methods
            evidence.append("Classes follow Repository naming convention")
            confidence += self.repository_naming_score

        if confidence >= self.min_confidence:
            return [ArchitecturalMatch(
                pattern=ArchitecturalPattern.REPOSITORY,
                confidence=min(confidence, self.max_confidence),
                components=components,
                evidence=evidence,
                metadata={'num_repositories': len(repositories)}
            )]

        return []

    def _detect_service_layer(self, all_classes: List[Any]) -> List[ArchitecturalMatch]:
        """
        Detect Service Layer pattern.

        Indicators:
        - Classes named *Service
        - Business logic abstraction
        """
        evidence = []
        components = []
        confidence = 0.0

        services = []

        for class_node in all_classes:
            name_lower = class_node.name.lower()
            if 'service' in name_lower and name_lower.endswith('service'):
                services.append(class_node.qualified_name)

        if len(services) >= 2:
            evidence.append(f"Found {len(services)} service classes")
            confidence += self.service_layer_classes_score
            components = services[:10]

            # Additional evidence
            if len(services) >= 5:
                evidence.append("Multiple services suggest service layer architecture")
                confidence += self.service_layer_multiple_score

        if confidence >= self.min_confidence:
            return [ArchitecturalMatch(
                pattern=ArchitecturalPattern.SERVICE_LAYER,
                confidence=min(confidence, self.max_confidence),
                components=components,
                evidence=evidence,
                metadata={'num_services': len(services)}
            )]

        return []

    def _detect_layered(self, all_files: List[Any]) -> List[ArchitecturalMatch]:
        """
        Detect Layered Architecture.

        Indicators:
        - Directories for different layers (presentation, business, data)
        - Common layer names (api, services, repositories, models)
        """
        evidence = []
        components = []
        confidence = 0.0

        # Track layer directories
        layers = set()

        common_layers = {
            'api', 'presentation', 'ui',
            'services', 'business', 'domain',
            'repositories', 'data', 'dal',
            'models', 'entities',
            'utils', 'common'
        }

        for file_node in all_files:
            path_parts = file_node.path.split('/')

            for part in path_parts:
                if part.lower() in common_layers:
                    layers.add(part.lower())
                    components.append(file_node.path)

        # Score based on number of distinct layers
        num_layers = len(layers)

        if num_layers >= 3:
            evidence.append(f"Found {num_layers} distinct layers: {', '.join(sorted(layers))}")
            confidence = self.layered_base_score + (num_layers - 3) * self.layered_per_layer_score

            if 'services' in layers and 'repositories' in layers:
                evidence.append("Has both services and repositories (typical layering)")
                confidence += self.layered_services_repos_score

        if confidence >= self.min_confidence:
            return [ArchitecturalMatch(
                pattern=ArchitecturalPattern.LAYERED,
                confidence=min(confidence, self.max_confidence),
                components=components[:20],  # Limit components
                evidence=evidence,
                metadata={
                    'layers': sorted(layers),
                    'num_layers': num_layers
                }
            )]

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

    def print_report(self):
        """Print architectural pattern report"""
        if not self.patterns_found:
            print("No architectural patterns detected")
            return

        stats = self.get_statistics()

        print(f"\n🏛️ Architectural Pattern Detection Report:")
        print(f"   Total patterns found: {stats['total_patterns']}")
        print(f"   Average confidence: {stats['avg_confidence']:.2f}")
        print(f"\n   Patterns detected:")

        for match in self.patterns_found:
            print(f"\n   {match}")
            for evidence in match.evidence:
                print(f"     • {evidence}")
            if match.components:
                print(f"     Components: {len(match.components)} total")
