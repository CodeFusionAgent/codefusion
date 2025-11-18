"""
Pattern Detector for Synthesis Pipeline

Detects design patterns using KB or from file summaries.
"""

from typing import Dict, List, Any


class PatternDetector:
    """Detects design patterns from KB (if available) or from file summaries."""

    def __init__(self, config: Dict[str, Any], kb_client=None):
        self.config = config
        self.kb = kb_client

    def detect_patterns_from_kb(self, file_summaries: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect design patterns using KB (if available) or from file summaries.

        Integrates pattern detection into synthesis so narratives mention
        patterns like "The system uses Factory pattern for ..."
        """
        patterns = []

        # Try KB pattern detection first (call layer directly - no wrapper)
        if self.kb and self.kb.design_pattern_detector is not None:
            try:
                # Query all classes from KB
                query = """
                MATCH (c:Class {repo_id: $repo_id})
                RETURN c.qualified_name as name, c.file_path as file, c
                LIMIT $limit
                """
                repo_id = getattr(self.kb, 'repo_id', 'default')
                synthesis_config = self.config.get('agents', {}).get('synthesis', {})
                query_limit = synthesis_config.get('kb_pattern_query_limit', 500)
                result = self.kb.kb.execute_query(query, {
                    'repo_id': repo_id,
                    'limit': query_limit
                })
                all_classes = [record['c'] for record in result.nodes]

                # Call design pattern detector directly
                raw_matches = self.kb.design_pattern_detector.detect_all_patterns(all_classes)

                # Convert PatternMatch objects to pattern dicts
                kb_patterns = [
                    {
                        'name': match.pattern.value,
                        'description': f"Detected pattern: {match.pattern.value}",
                        'files': [match.class_name],  # Simplified - would need file lookup
                        'confidence': match.confidence
                    }
                    for match in raw_matches
                ]

                if kb_patterns:
                    print(f"   🎨 Detected {len(kb_patterns)} patterns from KB")
                    return kb_patterns
            except Exception as e:
                print(f"   ⚠️ KB pattern detection failed: {e}")

        # Fallback: Detect patterns from file summaries
        pattern_keywords = {
            'Singleton Pattern': ['singleton', 'single instance', '_instance = None'],
            'Factory Pattern': ['factory', 'create_', 'make_', 'builder'],
            'Observer Pattern': ['observer', 'listener', 'subscribe', 'event'],
            'Strategy Pattern': ['strategy', 'algorithm', 'policy'],
            'Decorator Pattern': ['@decorator', 'wrapper', '@wraps'],
            'Repository Pattern': ['repository', 'data access', 'dao'],
            'MVC Pattern': ['model', 'view', 'controller'],
        }

        pattern_files = {}
        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            content = summary.get('content', '').lower()
            features = ' '.join(str(f).lower() for f in summary.get('key_features', []))
            insights = summary.get('architectural_insights', '').lower()
            combined = f"{content} {features} {insights}"

            for pattern_name, keywords in pattern_keywords.items():
                if any(kw in combined for kw in keywords):
                    if pattern_name not in pattern_files:
                        pattern_files[pattern_name] = []
                    pattern_files[pattern_name].append(file_path)

        # Convert to pattern dicts
        for pattern_name, files in pattern_files.items():
            if len(files) >= 1:
                patterns.append({
                    'name': pattern_name,
                    'description': f"Detected in {len(files)} file(s)",
                    'files': files[:3],
                    'confidence': min(0.5 + len(files) * 0.1, 0.9)
                })

        if patterns:
            print(f"   🎨 Detected {len(patterns)} patterns from summaries")

        return patterns
