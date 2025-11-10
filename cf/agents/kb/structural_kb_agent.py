"""
Structural Knowledge Base Agent

Exposes all KB query capabilities as tools:
- Semantic search
- Pattern detection
- Code smell detection
- Execution path tracing
- Data flow analysis
- Architecture overview

Updated to use KnowledgeBaseProtocol for loose coupling.
"""

import time
from typing import Dict, List, Any, Callable

from cf.agents.knowledge_base import KnowledgeAgent, AgentResult
from cf.agents.protocols import KnowledgeBaseProtocol


class StructuralKBAgent(KnowledgeAgent):
    """
    Pluggable agent that provides all structural KB query capabilities.

    Uses KnowledgeBaseProtocol for dependency injection, enabling:
    - Testing with mock KB backends
    - Swapping KB implementations
    - Loose coupling between agent and KB layer
    """

    def __init__(self, kb: KnowledgeBaseProtocol, config: Dict[str, Any] = None):
        """
        Initialize structural KB agent.

        Args:
            kb: Knowledge base backend (any object implementing KnowledgeBaseProtocol)
            config: Agent configuration including layer enables
        """
        super().__init__("structural_kb", config)
        self.kb = kb

        # Extract layer configurations for capability detection
        kb_config = config.get('knowledge_base', {}) if config else {}
        self.semantic_config = kb_config.get('semantic', {})
        self.patterns_config = kb_config.get('patterns', {})
        self.lifeofx_config = kb_config.get('lifeofx', {})

    def get_capabilities(self) -> List[str]:
        """Get list of capabilities this agent provides"""
        capabilities = ['kb_queries']

        # Add layer-specific capabilities if enabled
        if self.semantic_config.get('enabled', False):
            capabilities.append('semantic_search')

        if self.patterns_config.get('enabled', False):
            capabilities.extend(['pattern_detection', 'code_smell_detection'])

        if self.lifeofx_config.get('enabled', False):
            capabilities.extend(['execution_tracing', 'data_flow_analysis'])

        return capabilities

    def register_tools(self) -> Dict[str, Callable]:
        """Register all KB query tools (unprefixed - registry will prefix)"""
        tools = {}

        # Semantic Layer Tools
        if self.semantic_config.get('enabled', False):
            tools['search_by_semantics'] = self._search_by_semantics
            tools['search_by_functionality'] = self._search_by_functionality
            tools['find_similar_components'] = self._find_similar_components
            tools['detect_duplicate_code'] = self._detect_duplicate_code

        # Pattern Recognition Tools
        if self.patterns_config.get('enabled', False):
            tools['find_design_patterns'] = self._find_design_patterns
            tools['detect_code_smells'] = self._detect_code_smells
            tools['find_similar_patterns'] = self._find_similar_patterns

        # Architecture Tools
        tools['get_architecture_overview'] = self._get_architecture_overview
        tools['get_module_boundaries'] = self._get_module_boundaries
        tools['identify_cross_cutting_concerns'] = self._identify_cross_cutting_concerns

        # Life-of-X Tools
        if self.lifeofx_config.get('enabled', False):
            tools['trace_execution_path'] = self._trace_execution_path
            tools['trace_data_flow'] = self._trace_data_flow
            tools['trace_request_lifecycle'] = self._trace_request_lifecycle

        return tools

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAPI-style schemas for all tools (with proper prefixing)"""
        schemas = []

        # Semantic search tools
        if self.semantic_config.get('enabled', False):
            schemas.extend([
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('search_by_semantics'),
                        'description': 'Search code using natural language semantic search (vector embeddings)',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'query': {'type': 'string', 'description': 'Natural language query describing what to find'},
                                'scope': {'type': 'string', 'description': 'Scope to search (functions, classes, all)', 'enum': ['functions', 'classes', 'all']},
                                'limit': {'type': 'integer', 'description': 'Maximum results to return', 'default': 10}
                            },
                            'required': ['query']
                        }
                    }
                },
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('search_by_functionality'),
                        'description': 'Find code components by functional description (e.g., "validate user input")',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'description': {'type': 'string', 'description': 'Functional description of what the code should do'},
                                'limit': {'type': 'integer', 'description': 'Maximum results', 'default': 10}
                            },
                            'required': ['description']
                        }
                    }
                },
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('find_similar_components'),
                        'description': 'Find code components similar to a given function or class',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'component_id': {'type': 'string', 'description': 'ID of the reference component'},
                                'limit': {'type': 'integer', 'description': 'Maximum similar components', 'default': 10}
                            },
                            'required': ['component_id']
                        }
                    }
                },
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('detect_duplicate_code'),
                        'description': 'Detect duplicate or highly similar code across the codebase',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'similarity_threshold': {'type': 'number', 'description': 'Minimum similarity score (0.0-1.0)', 'default': 0.8}
                            }
                        }
                    }
                }
            ])

        # Pattern detection tools
        if self.patterns_config.get('enabled', False):
            schemas.extend([
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('find_design_patterns'),
                        'description': 'Find design patterns (Singleton, Factory, Observer, etc.) in the codebase',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'pattern_type': {'type': 'string', 'description': 'Specific pattern to find (optional)', 'enum': ['Singleton', 'Factory', 'Observer', 'Strategy', 'all']}
                            }
                        }
                    }
                },
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('detect_code_smells'),
                        'description': 'Detect code smells and anti-patterns (God Class, Long Method, etc.)',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'scope': {'type': 'string', 'description': 'Scope to analyze (file_path, class_name, or all)', 'default': 'all'}
                            }
                        }
                    }
                }
            ])

        # Architecture tools
        schemas.extend([
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('get_architecture_overview'),
                    'description': 'Get high-level architecture overview of the codebase',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'scope': {'type': 'string', 'description': 'Scope to analyze (directory or all)', 'default': 'all'}
                        }
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('get_module_boundaries'),
                    'description': 'Identify module boundaries and layer violations',
                    'parameters': {
                        'type': 'object',
                        'properties': {}
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('identify_cross_cutting_concerns'),
                    'description': 'Identify cross-cutting concerns (logging, auth, caching, etc.)',
                    'parameters': {
                        'type': 'object',
                        'properties': {}
                    }
                }
            }
        ])

        # Life-of-X tools
        if self.lifeofx_config.get('enabled', False):
            schemas.extend([
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('trace_execution_path'),
                        'description': 'Trace execution path from an entry point through the codebase',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'entry_point': {'type': 'string', 'description': 'Function name to start tracing from'},
                                'max_depth': {'type': 'integer', 'description': 'Maximum depth to trace', 'default': 10},
                                'max_paths': {'type': 'integer', 'description': 'Maximum paths to return', 'default': 5}
                            },
                            'required': ['entry_point']
                        }
                    }
                },
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('trace_data_flow'),
                        'description': 'Trace data flow from a variable or function through the code',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'start_element': {'type': 'string', 'description': 'Starting variable or function name'},
                                'max_depth': {'type': 'integer', 'description': 'Maximum depth to trace', 'default': 20}
                            },
                            'required': ['start_element']
                        }
                    }
                },
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('trace_request_lifecycle'),
                        'description': 'Trace HTTP request lifecycle for web applications',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'endpoint_function': {'type': 'string', 'description': 'API endpoint function name'},
                                'max_depth': {'type': 'integer', 'description': 'Maximum depth', 'default': 20}
                            },
                            'required': ['endpoint_function']
                        }
                    }
                }
            ])

        return schemas

    # ========== Semantic Layer Tool Implementations ==========

    def _search_by_semantics(self, query: str, scope: str = 'all', limit: int = 10) -> Dict[str, Any]:
        """Search using semantic/vector search"""
        start_time = time.time()
        try:
            results = self.kb.search_by_natural_language(query, top_k=limit)

            self._record_call(
                tokens=0,  # Would need to track embedding tokens
                time_taken=time.time() - start_time,
                error=False
            )

            return {
                'success': True,
                'results': results,
                'count': len(results),
                'query': query
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def _search_by_functionality(self, description: str, limit: int = 10) -> Dict[str, Any]:
        """Search by functional description (alias for semantic search)"""
        return self._search_by_semantics(description, scope='all', limit=limit)

    def _find_similar_components(self, component_id: str, limit: int = 10) -> Dict[str, Any]:
        """Find similar code components"""
        start_time = time.time()
        try:
            results = self.kb.find_similar_code(component_id, top_k=limit)

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'results': results,
                'count': len(results),
                'reference_component': component_id
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def _detect_duplicate_code(self, similarity_threshold: float = 0.8) -> Dict[str, Any]:
        """Detect duplicate code"""
        start_time = time.time()
        try:
            clusters = self.kb.detect_duplicate_code(similarity_threshold)

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'clusters': clusters,
                'count': len(clusters),
                'threshold': similarity_threshold
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    # ========== Pattern Recognition Tool Implementations ==========

    def _find_design_patterns(self, pattern_type: str = 'all') -> Dict[str, Any]:
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

            # Detect patterns
            patterns = self.kb.detect_design_patterns(all_classes)

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

    def _detect_code_smells(self, scope: str = 'all') -> Dict[str, Any]:
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

            # Detect smells
            smells = self.kb.detect_code_smells(all_classes, all_functions)

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

    def _find_similar_patterns(self, example_component_id: str) -> Dict[str, Any]:
        """Find similar architectural patterns"""
        # This is essentially finding similar components
        return self._find_similar_components(example_component_id, limit=10)

    # ========== Architecture Tool Implementations ==========

    def _get_architecture_overview(self, scope: str = 'all') -> Dict[str, Any]:
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

    def _get_module_boundaries(self) -> Dict[str, Any]:
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

    def _identify_cross_cutting_concerns(self) -> Dict[str, Any]:
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

    # ========== Life-of-X Tool Implementations ==========

    def _trace_execution_path(self, entry_point: str, max_depth: int = 10, max_paths: int = 5) -> Dict[str, Any]:
        """Trace execution path"""
        start_time = time.time()
        try:
            paths = self.kb.trace_execution_path(entry_point, max_depth, max_paths)

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'paths': paths,
                'count': len(paths),
                'entry_point': entry_point
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def _trace_data_flow(self, start_element: str, max_depth: int = 20) -> Dict[str, Any]:
        """Trace data flow"""
        start_time = time.time()
        try:
            flows = self.kb.trace_data_flow(start_element, max_depth)

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'flows': flows,
                'count': len(flows),
                'start_element': start_element
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    def _trace_request_lifecycle(self, endpoint_function: str, max_depth: int = 20) -> Dict[str, Any]:
        """Trace request lifecycle"""
        start_time = time.time()
        try:
            lifecycle = self.kb.trace_request_lifecycle(endpoint_function, max_depth)

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'lifecycle': lifecycle,
                'endpoint': endpoint_function
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}
