"""
Architecture Tools Handler for StructuralKBAgent

Handles architecture analysis tools (overview, boundaries, concerns, layers).
"""

import time
from typing import Dict, Any, Callable
from cf.agents.protocols import KnowledgeBaseProtocol


class ArchitectureToolsHandler:
    """Handles architecture analysis tools."""

    def __init__(self, kb: KnowledgeBaseProtocol, config: Dict[str, Any], record_call_fn: Callable):
        self.kb = kb
        self.config = config
        self._record_call = record_call_fn

    def get_architecture_overview(self, scope: str = 'all') -> Dict[str, Any]:
        """Get architecture overview"""
        start_time = time.time()
        try:
            stats = self.kb.get_repository_stats()

            # Query module structure
            modules_query = """
            MATCH (m:Module {repo_id: $repo_id})
            RETURN m.name as name, m.file_path as path
            LIMIT 100
            """
            repo_id = getattr(self.kb, 'repo_id', 'default')
            modules_result = self.kb.execute_query(modules_query, {
                'repo_id': repo_id
            })

            modules = [{'name': r['name'], 'path': r['path']} for r in modules_result.nodes]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'stats': stats,
                'modules': modules,
                'scope': scope
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def get_module_boundaries(self) -> Dict[str, Any]:
        """Identify module boundaries"""
        start_time = time.time()
        try:
            # Query cross-module dependencies
            query = """
            MATCH (m1:Module {repo_id: $repo_id})-[:IMPORTS]->(m2:Module {repo_id: $repo_id})
            WHERE m1.name <> m2.name
            RETURN m1.name as from_module, m2.name as to_module, count(*) as import_count
            ORDER BY import_count DESC
            LIMIT 100
            """
            repo_id = getattr(self.kb, 'repo_id', 'default')
            result = self.kb.execute_query(query, {
                'repo_id': repo_id
            })

            dependencies = [
                {'from': r['from_module'], 'to': r['to_module'], 'count': r['import_count']}
                for r in result.nodes
            ]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'dependencies': dependencies,
                'count': len(dependencies)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def identify_cross_cutting_concerns(self) -> Dict[str, Any]:
        """Identify cross-cutting concerns"""
        start_time = time.time()
        try:
            # Look for common patterns: logging, auth, caching, etc.
            concerns_patterns = {
                'logging': ['log', 'logger', 'logging'],
                'authentication': ['auth', 'login', 'authenticate'],
                'caching': ['cache', 'cached', 'memoize'],
                'error_handling': ['exception', 'error', 'try', 'catch'],
                'validation': ['validate', 'validator', 'check']
            }

            concerns = {}
            repo_id = getattr(self.kb, 'repo_id', 'default')

            for concern_name, keywords in concerns_patterns.items():
                # Search for functions matching keywords
                results = []
                for keyword in keywords:
                    query = """
                    MATCH (f:Function {repo_id: $repo_id})
                    WHERE toLower(f.name) CONTAINS toLower($keyword)
                    RETURN f.qualified_name as name, f.file_path as file
                    LIMIT 20
                    """
                    result = self.kb.execute_query(query, {
                        'repo_id': repo_id,
                        'keyword': keyword
                    })
                    results.extend([{'name': r['name'], 'file': r['file']} for r in result.nodes])

                if results:
                    concerns[concern_name] = results

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'concerns': concerns,
                'count': len(concerns)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def find_layer_components(self, layer: str) -> Dict[str, Any]:
        """List all components in an architectural layer"""
        start_time = time.time()
        try:
            # Layer patterns matching common architectural patterns
            layer_patterns = {
                'presentation': ['ui', 'views', 'controllers', 'handlers', 'routes', 'api'],
                'business': ['agents', 'services', 'logic', 'domain', 'core', 'orchestrator'],
                'data': ['repositories', 'dao', 'models', 'persistence', 'storage', 'kb'],
                'infrastructure': ['utils', 'helpers', 'config', 'tools', 'common']
            }

            patterns = layer_patterns.get(layer.lower(), [])
            if not patterns:
                return {
                    'success': False,
                    'error': f'Unknown layer: {layer}. Valid layers: {list(layer_patterns.keys())}'
                }

            components = []
            repo_id = getattr(self.kb, 'repo_id', 'default')

            # Search for modules/files matching layer patterns
            for pattern in patterns:
                query = """
                MATCH (m:Module {repo_id: $repo_id})
                WHERE toLower(m.file_path) CONTAINS toLower($pattern)
                RETURN m.name as name, m.file_path as path
                LIMIT 50
                """
                result = self.kb.execute_query(query, {
                    'repo_id': repo_id,
                    'pattern': pattern
                })
                for r in result.nodes:
                    if {'name': r['name'], 'path': r['path']} not in components:
                        components.append({'name': r['name'], 'path': r['path']})

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'layer': layer,
                'components': components,
                'count': len(components)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}
