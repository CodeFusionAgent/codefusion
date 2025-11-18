"""
Cross-File Analyzer for Synthesis Pipeline

Analyzes relationships and data flow between files.
"""

from typing import Dict, List, Any


class CrossFileAnalyzer:
    """Analyzes relationships and data flow between files."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def analyze_cross_file_relationships(self, file_summaries: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze relationships and data flow between files.

        Provides architectural context beyond individual file analysis.
        Identifies:
        - Shared abstractions (classes/functions used across files)
        - Dependencies and imports between files
        - Data flow patterns
        - Component interactions

        This addresses the gap where individual file analysis misses the bigger picture.
        """
        if len(file_summaries) < 2:
            return {}  # Need at least 2 files for cross-file analysis

        relationships = {
            'shared_abstractions': [],
            'dependencies': [],
            'data_flow': [],
            'component_interactions': []
        }

        # Extract all entities (classes, functions) from all files
        all_entities = {}
        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            entities = []
            # Collect classes
            for cls in summary.get('classes', []):
                if isinstance(cls, dict):
                    entities.append({'type': 'class', 'name': cls.get('name', ''), 'file': file_path})

            # Collect functions
            for func in summary.get('functions', []):
                if isinstance(func, dict):
                    entities.append({'type': 'function', 'name': func.get('name', ''), 'file': file_path})

            all_entities[file_path] = entities

        # Identify shared abstractions (entities with similar names across files)
        entity_names = {}
        for file_path, entities in all_entities.items():
            for entity in entities:
                name = entity['name']
                if name not in entity_names:
                    entity_names[name] = []
                entity_names[name].append({'file': file_path, 'type': entity['type']})

        # Find entities referenced in multiple files (likely shared abstractions)
        for name, references in entity_names.items():
            if len(references) >= 2 or name.lower() in ['manager', 'service', 'controller', 'model', 'view', 'helper', 'utils']:
                relationships['shared_abstractions'].append({
                    'name': name,
                    'occurrences': len(references),
                    'files': [ref['file'] for ref in references[:3]]  # Limit to 3
                })

        # Infer dependencies based on file structure and naming patterns
        file_paths = list(file_summaries.keys())
        for i, file1 in enumerate(file_paths):
            for file2 in file_paths[i+1:]:
                # Check if files are in related directories (e.g., models and views, services and controllers)
                if self._are_files_related(file1, file2):
                    relationships['dependencies'].append({
                        'from': file1,
                        'to': file2,
                        'relationship': self._infer_relationship_type(file1, file2)
                    })

        # Infer data flow based on common patterns
        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            features = summary.get('key_features', [])
            arch_insights = summary.get('architectural_insights', '')

            # Look for data flow indicators
            if any(keyword in str(features).lower() + arch_insights.lower()
                   for keyword in ['processes', 'transforms', 'validates', 'filters', 'handles']):
                relationships['data_flow'].append({
                    'file': file_path,
                    'role': self._infer_data_flow_role(features, arch_insights),
                    'description': arch_insights[:150] if arch_insights else ''
                })

        print(f"   🔗 [SYNTHESIS] Cross-file analysis:")
        print(f"      Shared abstractions: {len(relationships['shared_abstractions'])}")
        print(f"      Dependencies: {len(relationships['dependencies'])}")
        print(f"      Data flow nodes: {len(relationships['data_flow'])}")

        return relationships

    def _are_files_related(self, file1: str, file2: str) -> bool:
        """Check if two files are likely related based on directory structure"""
        # Common related patterns
        patterns = [
            ('model', 'view'), ('model', 'controller'),
            ('service', 'controller'), ('repository', 'service'),
            ('manager', 'model'), ('utils', 'helper'),
            ('api', 'service'), ('handler', 'service')
        ]

        f1_lower = file1.lower()
        f2_lower = file2.lower()

        for pattern1, pattern2 in patterns:
            if (pattern1 in f1_lower and pattern2 in f2_lower) or \
               (pattern2 in f1_lower and pattern1 in f2_lower):
                return True

        return False

    def _infer_relationship_type(self, file1: str, file2: str) -> str:
        """Infer the type of relationship between two files"""
        if 'model' in file1.lower() and 'view' in file2.lower():
            return 'data-presentation'
        elif 'service' in file1.lower() and 'controller' in file2.lower():
            return 'business-logic-to-api'
        elif 'repository' in file1.lower() and 'service' in file2.lower():
            return 'data-access-to-service'
        elif 'manager' in file1.lower():
            return 'management-layer'
        else:
            return 'component-interaction'

    def _infer_data_flow_role(self, features: List[str], arch_insights: str) -> str:
        """Infer the role of a file in data flow"""
        text = (str(features) + ' ' + arch_insights).lower()

        if 'validates' in text or 'validation' in text:
            return 'validation'
        elif 'processes' in text or 'processing' in text:
            return 'processing'
        elif 'transforms' in text or 'transformation' in text:
            return 'transformation'
        elif 'filters' in text or 'filtering' in text:
            return 'filtering'
        elif 'manages' in text or 'management' in text:
            return 'management'
        else:
            return 'data-handler'
