"""
Pattern Tools Handler for StructuralKBAgent

Handles pattern detection and code smell detection tools.
"""

import time
from typing import Dict, Any, Callable
from cf.agents.protocols import KnowledgeBaseProtocol


class PatternToolsHandler:
    """Handles pattern detection and code smell detection tools."""

    def __init__(self, kb: KnowledgeBaseProtocol, config: Dict[str, Any], record_call_fn: Callable):
        self.kb = kb
        self.config = config
        self._record_call = record_call_fn

        # Load config
        self.patterns_config = config.get('knowledge_base', {}).get('patterns', {})

    def find_design_patterns(self, pattern_type: str = 'all') -> Dict[str, Any]:
        """Find design patterns"""
        start_time = time.time()
        try:
            # Query all classes from KB
            query = """
            MATCH (c:Class {repo_id: $repo_id})
            RETURN c.qualified_name as name, c.file_path as file, c
            LIMIT $limit
            """
            # Get repo_id from kb if available (duck typing)
            repo_id = getattr(self.kb, 'repo_id', 'default')
            result = self.kb.execute_query(query, {
                'repo_id': repo_id,
                'limit': self.patterns_config.get('max_classes_to_analyze', 500)
            })
            all_classes = [record['c'] for record in result.nodes]

            # Call design pattern detector directly (no wrapper)
            if self.kb.design_pattern_detector is None:
                return {'success': False, 'error': 'Pattern detection not enabled'}

            if not self.patterns_config.get('detect_design_patterns', True):
                return {'success': True, 'patterns': [], 'count': 0, 'pattern_type': pattern_type}

            raw_matches = self.kb.design_pattern_detector.detect_all_patterns(all_classes)

            # Convert PatternMatch objects to dicts
            patterns = [
                {
                    'pattern': match.pattern.value,
                    'class_name': match.class_name,
                    'confidence': match.confidence,
                    'evidence': match.evidence
                }
                for match in raw_matches
            ]

            # Filter by pattern type if specified
            if pattern_type != 'all':
                patterns = [p for p in patterns if p['pattern'].lower() == pattern_type.lower()]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'patterns': patterns,
                'count': len(patterns),
                'pattern_type': pattern_type
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def detect_code_smells(self, scope: str = 'all') -> Dict[str, Any]:
        """Detect code smells"""
        start_time = time.time()
        try:
            # Query classes and functions
            classes_query = """
            MATCH (c:Class {repo_id: $repo_id})
            RETURN c
            LIMIT $limit
            """
            functions_query = """
            MATCH (f:Function {repo_id: $repo_id})
            RETURN f
            LIMIT $limit
            """

            repo_id = getattr(self.kb, 'repo_id', 'default')
            limit = 1000  # Reasonable limit
            classes_result = self.kb.execute_query(classes_query, {
                'repo_id': repo_id,
                'limit': limit
            })
            functions_result = self.kb.execute_query(functions_query, {
                'repo_id': repo_id,
                'limit': limit
            })

            all_classes = [record['c'] for record in classes_result.nodes]
            all_functions = [record['f'] for record in functions_result.nodes]

            # Call code smell detector directly (no wrapper)
            if self.kb.code_smell_detector is None:
                return {'success': False, 'error': 'Code smell detection not enabled'}

            if not self.patterns_config.get('detect_code_smells', True):
                return {'success': True, 'smells': [], 'count': 0, 'scope': scope}

            raw_matches = self.kb.code_smell_detector.detect_all_smells(all_classes, all_functions)

            # Convert SmellMatch objects to dicts
            smells = [
                {
                    'smell': match.smell.value,
                    'element_name': match.element_name,
                    'severity': match.severity.value,
                    'metrics': match.metrics,
                    'suggestion': match.suggestion
                }
                for match in raw_matches
            ]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'smells': smells,
                'count': len(smells),
                'scope': scope
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def find_similar_patterns(self, example_component_id: str, semantic_handler) -> Dict[str, Any]:
        """Find similar architectural patterns (delegates to semantic handler)"""
        return semantic_handler.find_similar_components(example_component_id, limit=10)
