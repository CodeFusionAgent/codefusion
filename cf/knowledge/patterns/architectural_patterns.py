"""
Architectural Pattern Detection

Detects high-level architectural patterns:
- MVC (Model-View-Controller)
- Repository Pattern
- Service Layer
- Layered Architecture
- Microservices patterns
"""

from typing import List, Dict, Any, Set
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
    """

    def __init__(self):
        self.patterns_found: List[ArchitecturalMatch] = []

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
            confidence += 0.25
        if has_view_dir:
            evidence.append("Has views/ directory")
            confidence += 0.25
        if has_controller_dir:
            evidence.append("Has controllers/ directory")
            confidence += 0.25

        if len(models) >= 2:
            evidence.append(f"Found {len(models)} model classes")
            confidence += 0.15
            components.extend(models[:5])  # Include first 5
        if len(views) >= 1:
            evidence.append(f"Found {len(views)} view classes")
            confidence += 0.10
            components.extend(views[:5])
        if len(controllers) >= 2:
            evidence.append(f"Found {len(controllers)} controller classes")
            confidence += 0.15
            components.extend(controllers[:5])

        if confidence >= 0.5:
            return [ArchitecturalMatch(
                pattern=ArchitecturalPattern.MVC,
                confidence=min(confidence, 0.95),
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
            confidence += 0.8
            components = repositories[:10]

            # Check for common repository methods
            evidence.append("Classes follow Repository naming convention")
            confidence += 0.15

        if confidence >= 0.5:
            return [ArchitecturalMatch(
                pattern=ArchitecturalPattern.REPOSITORY,
                confidence=min(confidence, 0.95),
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
            confidence += 0.7
            components = services[:10]

            # Additional evidence
            if len(services) >= 5:
                evidence.append("Multiple services suggest service layer architecture")
                confidence += 0.2

        if confidence >= 0.5:
            return [ArchitecturalMatch(
                pattern=ArchitecturalPattern.SERVICE_LAYER,
                confidence=min(confidence, 0.95),
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
            confidence = 0.5 + (num_layers - 3) * 0.1

            if 'services' in layers and 'repositories' in layers:
                evidence.append("Has both services and repositories (typical layering)")
                confidence += 0.15

        if confidence >= 0.5:
            return [ArchitecturalMatch(
                pattern=ArchitecturalPattern.LAYERED,
                confidence=min(confidence, 0.95),
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
