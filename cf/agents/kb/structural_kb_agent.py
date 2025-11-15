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

        # High-Level Discovery Tool (combines multiple strategies)
        tools['find_files_for_question'] = self._find_files_for_question

        # Semantic Layer Tools
        if self.semantic_config.get('enabled', False):
            tools['search_by_semantics'] = self._search_by_semantics
            tools['search_by_functionality'] = self._search_by_functionality
            tools['find_similar_components'] = self._find_similar_components
            tools['detect_duplicate_code'] = self._detect_duplicate_code
            tools['search_by_example'] = self._search_by_example

        # Pattern Recognition Tools
        if self.patterns_config.get('enabled', False):
            tools['find_design_patterns'] = self._find_design_patterns
            tools['detect_code_smells'] = self._detect_code_smells
            tools['find_similar_patterns'] = self._find_similar_patterns

        # Architecture Tools
        tools['get_architecture_overview'] = self._get_architecture_overview
        tools['get_module_boundaries'] = self._get_module_boundaries
        tools['identify_cross_cutting_concerns'] = self._identify_cross_cutting_concerns
        tools['find_layer_components'] = self._find_layer_components

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
                },
                {
                    'type': 'function',
                    'function': {
                        'name': self.get_prefixed_tool_name('search_by_example'),
                        'description': 'Find code similar to a given code snippet using semantic similarity',
                        'parameters': {
                            'type': 'object',
                            'properties': {
                                'code_snippet': {'type': 'string', 'description': 'Code snippet to use as example'},
                                'limit': {'type': 'integer', 'description': 'Maximum results to return', 'default': 10}
                            },
                            'required': ['code_snippet']
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
            },
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('find_layer_components'),
                    'description': 'List all components in an architectural layer (presentation, business, data, infrastructure)',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'layer': {
                                'type': 'string',
                                'description': 'Layer name to query',
                                'enum': ['presentation', 'business', 'data', 'infrastructure']
                            }
                        },
                        'required': ['layer']
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
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
            raw_results = self.kb.semantic_search.search_by_natural_language(
                query, top_k=limit, min_similarity=min_similarity
            )

            # Convert SimilarityResult objects to dicts
            results = [
                {
                    'element_id': r.element_id,
                    'similarity_score': r.similarity_score,
                    'element_type': r.element_type,
                    'text': r.text,
                    'metadata': r.metadata
                }
                for r in raw_results
            ]

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
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            raw_results = self.kb.semantic_search.find_similar_functions(component_id, top_k=limit)

            # Convert SimilarityResult objects to dicts
            results = [
                {
                    'element_id': r.element_id,
                    'similarity_score': r.similarity_score,
                    'element_type': r.element_type,
                    'text': r.text,
                    'metadata': r.metadata
                }
                for r in raw_results
            ]

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
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            clusters = self.kb.semantic_search.cluster_similar_code(similarity_threshold)

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

    def _search_by_example(self, code_snippet: str, limit: int = 10) -> Dict[str, Any]:
        """Find code similar to a given example snippet using semantic search"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
            raw_results = self.kb.semantic_search.search_by_natural_language(
                code_snippet, top_k=limit, min_similarity=min_similarity
            )

            # Convert SimilarityResult objects to dicts
            results = [
                {
                    'element_id': r.element_id,
                    'similarity_score': r.similarity_score,
                    'element_type': r.element_type,
                    'text': r.text,
                    'metadata': r.metadata
                }
                for r in raw_results
            ]

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'results': results,
                'count': len(results),
                'snippet': code_snippet[:100] + '...' if len(code_snippet) > 100 else code_snippet
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

    def _find_layer_components(self, layer: str) -> Dict[str, Any]:
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

    # ========== Life-of-X Tool Implementations ==========

    def _trace_execution_path(self, entry_point: str, max_depth: int = 10, max_paths: int = 5) -> Dict[str, Any]:
        """Trace execution path"""
        start_time = time.time()
        try:
            # Call execution path tracer directly (no wrapper)
            if self.kb.execution_path_tracer is None:
                return {'success': False, 'error': 'Execution path tracing not enabled'}

            raw_paths = self.kb.execution_path_tracer.trace_from_entry_point(
                entry_point, max_depth=max_depth, max_paths=max_paths
            )

            # Convert ExecutionPath objects to dicts
            paths = [
                {
                    'entry_point': p.entry_point,
                    'exit_point': p.exit_point,
                    'total_functions': p.total_functions,
                    'max_depth': p.max_depth,
                    'confidence': p.confidence,
                    'steps': [
                        {
                            'function_name': s.function_name,
                            'qualified_name': s.qualified_name,
                            'step_type': s.step_type,
                            'metadata': s.metadata
                        }
                        for s in p.steps
                    ]
                }
                for p in raw_paths
            ]

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
            # Call dataflow analyzer directly (no wrapper)
            if self.kb.dataflow_analyzer is None:
                return {'success': False, 'error': 'Data flow analysis not enabled'}

            raw_paths = self.kb.dataflow_analyzer.trace_data_flow(start_element, max_depth=max_depth)

            # Convert DataFlowPath objects to dicts
            flows = [
                {
                    'start_node': p.start_node,
                    'end_node': p.end_node,
                    'path_length': len(p.path),
                    'path': p.path,
                    'transformations': p.transformations,
                    'confidence': p.confidence
                }
                for p in raw_paths
            ]

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
            # Call execution path tracer directly (no wrapper)
            if self.kb.execution_path_tracer is None:
                return {'success': False, 'error': 'Execution path tracing not enabled'}

            raw_path = self.kb.execution_path_tracer.trace_request_lifecycle(endpoint_function, max_depth=max_depth)

            if raw_path is None:
                lifecycle = None
            else:
                # Convert ExecutionPath object to dict
                lifecycle = {
                    'entry_point': raw_path.entry_point,
                    'exit_point': raw_path.exit_point,
                    'total_functions': raw_path.total_functions,
                    'max_depth': raw_path.max_depth,
                    'confidence': raw_path.confidence,
                    'steps': [
                        {
                            'function_name': s.function_name,
                            'qualified_name': s.qualified_name,
                            'step_type': s.step_type,
                            'metadata': s.metadata
                        }
                        for s in raw_path.steps
                    ]
                }

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'lifecycle': lifecycle,
                'endpoint': endpoint_function
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e)}

    # ========== High-Level Discovery Tool ==========

    def _find_files_for_question(self, question: str, max_results: int = 50,
                                 question_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Find relevant files for a question using all KB strategies.

        This is the primary file discovery tool that combines:
        - Semantic search (vector embeddings)
        - Pattern detection (AST analysis)
        - Life-of-X tracing (execution paths)
        - Dependency analysis (graph queries)

        Args:
            question: User question
            max_results: Maximum files to return
            question_context: Optional LLM classification context from supervisor

        Returns:
            Dictionary with success status and list of file paths
        """
        start_time = time.time()
        try:
            # Check if KB has find_files_for_question method (StructuralPipeline does)
            if hasattr(self.kb, 'find_files_for_question'):
                file_paths = self.kb.find_files_for_question(
                    question=question,
                    max_results=max_results,
                    question_context=question_context
                )
            else:
                # Fallback: just use semantic search directly
                file_paths = []
                if self.semantic_config.get('enabled', False) and self.kb.semantic_search is not None:
                    min_similarity = self.semantic_config.get('similarity_threshold', 0.7)
                    raw_results = self.kb.semantic_search.search_by_natural_language(
                        question, top_k=max_results, min_similarity=min_similarity
                    )
                    # Extract file paths from SimilarityResult objects
                    for result in raw_results:
                        file_path = result.metadata.get('file_path') if hasattr(result, 'metadata') else None
                        if file_path:
                            file_paths.append(file_path)

            self._record_call(time_taken=time.time() - start_time, error=False)

            return {
                'success': True,
                'file_paths': file_paths,
                'count': len(file_paths),
                'question': question
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'file_paths': []}
