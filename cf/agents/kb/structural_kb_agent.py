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

import os
import time
from typing import Dict, List, Any, Callable

from cf.agents.knowledge_base import KnowledgeAgent, AgentResult
from cf.agents.protocols import KnowledgeBaseProtocol


# Tool name constants for external reference (eliminates fragile dynamic resolution)
class StructuralKBTools:
    """Tool name constants for StructuralKBAgent (prefixed by registry)"""
    # High-level discovery
    FIND_FILES_FOR_QUESTION = 'find_files_for_question'

    # Semantic layer
    SEARCH_BY_SEMANTICS = 'search_by_semantics'
    SEARCH_BY_FUNCTIONALITY = 'search_by_functionality'
    FIND_SIMILAR_COMPONENTS = 'find_similar_components'
    DETECT_DUPLICATE_CODE = 'detect_duplicate_code'
    SEARCH_BY_EXAMPLE = 'search_by_example'

    # Pattern layer
    FIND_DESIGN_PATTERNS = 'find_design_patterns'
    DETECT_CODE_SMELLS = 'detect_code_smells'

    # Architecture layer
    GET_ARCHITECTURE_OVERVIEW = 'get_architecture_overview'
    GET_MODULE_BOUNDARIES = 'get_module_boundaries'
    IDENTIFY_CROSS_CUTTING_CONCERNS = 'identify_cross_cutting_concerns'
    FIND_LAYER_COMPONENTS = 'find_layer_components'

    # Code navigation
    FIND_CALLERS = 'find_callers'
    FIND_CALLEES = 'find_callees'
    FIND_USAGES = 'find_usages'
    FIND_RELATED_TESTS = 'find_related_tests'
    FIND_IMPLEMENTATIONS = 'find_implementations'

    # Life-of-X layer
    TRACE_EXECUTION_PATH = 'trace_execution_path'
    TRACE_DATA_FLOW = 'trace_data_flow'
    TRACE_REQUEST_LIFECYCLE = 'trace_request_lifecycle'


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

        # Load KB agent tool defaults from config
        agent_config = config.get('agents', {}) if config else {}
        kb_agent_config = agent_config.get('structural_kb_agent', {})

        # Semantic search defaults
        self.default_search_limit = kb_agent_config.get('default_search_limit', 10)
        self.default_similar_components_limit = kb_agent_config.get('default_similar_components_limit', 10)
        self.default_example_search_limit = kb_agent_config.get('default_example_search_limit', 10)
        self.duplicate_code_similarity_threshold = kb_agent_config.get('duplicate_code_similarity_threshold', 0.8)
        self.snippet_preview_length = kb_agent_config.get('snippet_preview_length', 100)

        # Code navigation defaults
        self.default_callers_limit = kb_agent_config.get('default_callers_limit', 20)
        self.default_callees_limit = kb_agent_config.get('default_callees_limit', 20)
        self.default_usages_limit = kb_agent_config.get('default_usages_limit', 30)

        # Execution tracing defaults
        self.trace_execution_max_depth = kb_agent_config.get('trace_execution_max_depth', 10)
        self.trace_execution_max_paths = kb_agent_config.get('trace_execution_max_paths', 5)
        self.trace_dataflow_max_depth = kb_agent_config.get('trace_dataflow_max_depth', 20)
        self.trace_lifecycle_max_depth = kb_agent_config.get('trace_lifecycle_max_depth', 20)

        # File discovery defaults
        self.default_file_discovery_limit = kb_agent_config.get('default_file_discovery_limit', 50)
        self.query_result_limit = kb_agent_config.get('query_result_limit', 1000)

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

    def get_tool_name(self, tool_constant: str, prefixed: bool = True) -> str:
        """
        Get tool name with optional prefix.

        Args:
            tool_constant: Tool name from StructuralKBTools class
            prefixed: Whether to include agent prefix (default: True)

        Returns:
            Tool name (prefixed or unprefixed)

        Example:
            >>> agent.get_tool_name(StructuralKBTools.FIND_FILES_FOR_QUESTION)
            'structural_kb_find_files_for_question'
            >>> agent.get_tool_name(StructuralKBTools.FIND_FILES_FOR_QUESTION, prefixed=False)
            'find_files_for_question'
        """
        if prefixed:
            return f"{self.agent_name}_{tool_constant}"
        return tool_constant

    def register_tools(self) -> Dict[str, Callable]:
        """Register all KB query tools (unprefixed - registry will prefix)"""
        tools = {}

        # High-Level Discovery Tool (combines multiple strategies)
        tools[StructuralKBTools.FIND_FILES_FOR_QUESTION] = self._find_files_for_question

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

        # Code Navigation Tools (NEW)
        tools['find_callers'] = self._find_callers
        tools['find_callees'] = self._find_callees
        tools['find_usages'] = self._find_usages
        tools['find_related_tests'] = self._find_related_tests
        tools['find_implementations'] = self._find_implementations

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

        # Code Navigation tools (NEW)
        schemas.extend([
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('find_callers'),
                    'description': 'Find all functions that call a given function',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'function_name': {'type': 'string', 'description': 'Qualified name of the function to find callers for'},
                            'max_results': {'type': 'integer', 'description': 'Maximum callers to return', 'default': 20}
                        },
                        'required': ['function_name']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('find_callees'),
                    'description': 'Find all functions called by a given function',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'function_name': {'type': 'string', 'description': 'Qualified name of the function to find callees for'},
                            'max_results': {'type': 'integer', 'description': 'Maximum callees to return', 'default': 20}
                        },
                        'required': ['function_name']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('find_usages'),
                    'description': 'Find all usages of a class, function, or variable across the codebase',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'symbol_name': {'type': 'string', 'description': 'Name of the symbol to find usages for'},
                            'symbol_type': {'type': 'string', 'description': 'Type of symbol (function, class, variable)', 'enum': ['function', 'class', 'variable', 'any']},
                            'max_results': {'type': 'integer', 'description': 'Maximum usages to return', 'default': 30}
                        },
                        'required': ['symbol_name']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('find_related_tests'),
                    'description': 'Find test files that test a given production file',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'file_path': {'type': 'string', 'description': 'Path to the production file'},
                            'include_indirect': {'type': 'boolean', 'description': 'Include tests that indirectly test this file', 'default': False}
                        },
                        'required': ['file_path']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': self.get_prefixed_tool_name('find_implementations'),
                    'description': 'Find all implementations of an interface, abstract class, or base class',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'interface_name': {'type': 'string', 'description': 'Name of the interface or abstract class'},
                            'include_indirect': {'type': 'boolean', 'description': 'Include indirect implementations (subclasses of implementations)', 'default': False}
                        },
                        'required': ['interface_name']
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

    def _search_by_semantics(self, query: str, scope: str = 'all', limit: int = None) -> Dict[str, Any]:
        """Search using semantic/vector search"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            limit = limit if limit is not None else self.default_search_limit
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

    def _search_by_functionality(self, description: str, limit: int = None) -> Dict[str, Any]:
        """Search by functional description (alias for semantic search)"""
        limit = limit if limit is not None else self.default_search_limit
        return self._search_by_semantics(description, scope='all', limit=limit)

    def _find_similar_components(self, component_id: str, limit: int = None) -> Dict[str, Any]:
        """Find similar code components"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            limit = limit if limit is not None else self.default_similar_components_limit
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

    def _detect_duplicate_code(self, similarity_threshold: float = None) -> Dict[str, Any]:
        """Detect duplicate code"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            similarity_threshold = similarity_threshold if similarity_threshold is not None else self.duplicate_code_similarity_threshold
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

    def _search_by_example(self, code_snippet: str, limit: int = None) -> Dict[str, Any]:
        """Find code similar to a given example snippet using semantic search"""
        start_time = time.time()
        try:
            # Call semantic search layer directly (no wrapper)
            if self.kb.semantic_search is None:
                return {'success': False, 'error': 'Semantic search not enabled'}

            limit = limit if limit is not None else self.default_example_search_limit
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
                'snippet': code_snippet[:self.snippet_preview_length] + '...' if len(code_snippet) > 100 else code_snippet
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

    def _trace_execution_path(self, entry_point: str, max_depth: int = None, max_paths: int = None) -> Dict[str, Any]:
        """Trace execution path"""
        start_time = time.time()
        try:
            # Call execution path tracer directly (no wrapper)
            if self.kb.execution_path_tracer is None:
                return {'success': False, 'error': 'Execution path tracing not enabled'}

            max_depth = max_depth if max_depth is not None else self.trace_execution_max_depth
            max_paths = max_paths if max_paths is not None else self.trace_execution_max_paths
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

    def _trace_data_flow(self, start_element: str, max_depth: int = None) -> Dict[str, Any]:
        """Trace data flow"""
        start_time = time.time()
        try:
            # Call dataflow analyzer directly (no wrapper)
            if self.kb.dataflow_analyzer is None:
                return {'success': False, 'error': 'Data flow analysis not enabled'}

            max_depth = max_depth if max_depth is not None else self.trace_dataflow_max_depth
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

    def _trace_request_lifecycle(self, endpoint_function: str, max_depth: int = None) -> Dict[str, Any]:
        """Trace request lifecycle"""
        start_time = time.time()
        try:
            # Call execution path tracer directly (no wrapper)
            if self.kb.execution_path_tracer is None:
                return {'success': False, 'error': 'Execution path tracing not enabled'}

            max_depth = max_depth if max_depth is not None else self.trace_lifecycle_max_depth
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

    def _find_files_for_question(self, question: str, max_results: int = None,
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
            # Apply default max_results
            max_results = max_results if max_results is not None else self.default_file_discovery_limit
            
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

    # ========== Code Navigation Tools (NEW) ==========

    def _find_callers(self, function_name: str, max_results: int = None) -> Dict[str, Any]:
        """
        Find all functions that call a given function.

        Uses CALLS relationship in knowledge graph to find caller functions.

        Args:
            function_name: Qualified name of function (e.g., "module.Class.method")
            max_results: Maximum number of callers to return

        Returns:
            Dict with success status and list of callers with file/line info
        """
        start_time = time.time()
        try:
            # Apply default max_results
            max_results = max_results if max_results is not None else self.default_callers_limit
            
            # Query KB for caller relationships
            query = """
            MATCH (caller:Function)-[:CALLS]->(target:Function)
            WHERE target.qualified_name = $function_name OR target.name = $function_name
            RETURN caller.qualified_name as caller_name,
                   caller.file_path as file_path,
                   caller.start_line as line,
                   caller.name as simple_name
            LIMIT $limit
            """

            results = self.kb.execute_query(query, {
                'function_name': function_name,
                'limit': max_results
            })

            callers = []
            for record in results.records:
                callers.append({
                    'caller': record['caller_name'],
                    'simple_name': record['simple_name'],
                    'file_path': record['file_path'],
                    'line': record['line']
                })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'function': function_name,
                'callers': callers,
                'count': len(callers)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'callers': []}

    def _find_callees(self, function_name: str, max_results: int = None) -> Dict[str, Any]:
        """
        Find all functions called by a given function.

        Uses CALLS relationship in knowledge graph to find callee functions.

        Args:
            function_name: Qualified name of function
            max_results: Maximum number of callees to return

        Returns:
            Dict with success status and list of callees with file/line info
        """
        start_time = time.time()
        try:
            # Apply default max_results
            max_results = max_results if max_results is not None else self.default_callees_limit
            
            query = """
            MATCH (caller:Function)-[:CALLS]->(callee:Function)
            WHERE caller.qualified_name = $function_name OR caller.name = $function_name
            RETURN callee.qualified_name as callee_name,
                   callee.file_path as file_path,
                   callee.start_line as line,
                   callee.name as simple_name
            LIMIT $limit
            """

            results = self.kb.execute_query(query, {
                'function_name': function_name,
                'limit': max_results
            })

            callees = []
            for record in results.records:
                callees.append({
                    'callee': record['callee_name'],
                    'simple_name': record['simple_name'],
                    'file_path': record['file_path'],
                    'line': record['line']
                })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'function': function_name,
                'callees': callees,
                'count': len(callees)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'callees': []}

    def _find_usages(self, symbol_name: str, symbol_type: str = 'any', max_results: int = None) -> Dict[str, Any]:
        """
        Find all usages of a class, function, or variable.

        Searches across imports, calls, and references.

        Args:
            symbol_name: Name of the symbol
            symbol_type: Type of symbol (function, class, variable, any)
            max_results: Maximum usages to return

        Returns:
            Dict with success status and list of usages
        """
        start_time = time.time()
        try:
            # Apply default max_results
            max_results = max_results if max_results is not None else self.default_usages_limit

            usages = []

            # Build query based on symbol type
            if symbol_type == 'function' or symbol_type == 'any':
                # Find function calls
                query = """
                MATCH (caller:Function)-[:CALLS]->(target:Function)
                WHERE target.name = $symbol_name
                RETURN 'call' as usage_type,
                       caller.qualified_name as location,
                       caller.file_path as file_path,
                       caller.start_line as line
                LIMIT $limit
                """
                results = self.kb.execute_query(query, {'symbol_name': symbol_name, 'limit': max_results})
                for record in results.records:
                    usages.append({
                        'type': record['usage_type'],
                        'location': record['location'],
                        'file_path': record['file_path'],
                        'line': record['line']
                    })

            if symbol_type == 'class' or symbol_type == 'any':
                # Find class usages (imports, inheritance)
                query = """
                MATCH (c:Class)
                WHERE c.name = $symbol_name
                OPTIONAL MATCH (c)<-[:INHERITS]-(subclass:Class)
                OPTIONAL MATCH (f:File)-[:IMPORTS]->(m:Module)
                WHERE m.name CONTAINS $symbol_name
                RETURN 'inheritance' as usage_type,
                       subclass.qualified_name as location,
                       subclass.file_path as file_path,
                       subclass.start_line as line
                LIMIT $limit
                """
                results = self.kb.execute_query(query, {'symbol_name': symbol_name, 'limit': max_results - len(usages)})
                for record in results.records:
                    if record['location']:  # Only if we found actual usages
                        usages.append({
                            'type': record['usage_type'],
                            'location': record['location'],
                            'file_path': record['file_path'],
                            'line': record['line']
                        })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'symbol': symbol_name,
                'symbol_type': symbol_type,
                'usages': usages,
                'count': len(usages)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'usages': []}

    def _find_related_tests(self, file_path: str, include_indirect: bool = False) -> Dict[str, Any]:
        """
        Find test files that test a given production file.

        Looks for:
        1. Test files with matching names (test_<name>.py, <name>_test.py)
        2. Test files that import the production file
        3. (Optional) Indirect tests that test dependencies

        Args:
            file_path: Path to production file
            include_indirect: Include tests that indirectly test this file

        Returns:
            Dict with success status and list of related test files
        """
        start_time = time.time()
        try:
            test_files = []

            # Pattern 1: Name-based matching
            # Extract base name from file_path
            base_name = os.path.basename(file_path).replace('.py', '')
            test_patterns = [
                f'test_{base_name}',
                f'{base_name}_test',
                f'test{base_name}',
                f'{base_name}test'
            ]

            # Find test files matching patterns
            for pattern in test_patterns:
                query = """
                MATCH (f:File)
                WHERE f.path CONTAINS $pattern AND f.path CONTAINS 'test'
                RETURN f.path as test_file
                LIMIT 10
                """
                results = self.kb.execute_query(query, {'pattern': pattern})
                for record in results.records:
                    if record['test_file'] not in [t['file_path'] for t in test_files]:
                        test_files.append({
                            'file_path': record['test_file'],
                            'relationship': 'name_match',
                            'confidence': 0.9
                        })

            # Pattern 2: Import-based matching
            # Find test files that import this file
            query = """
            MATCH (test_file:File)-[:IMPORTS]->(m:Module)
            WHERE test_file.path CONTAINS 'test' AND m.name CONTAINS $base_name
            RETURN test_file.path as test_file
            LIMIT 10
            """
            results = self.kb.execute_query(query, {'base_name': base_name})
            for record in results.records:
                if record['test_file'] not in [t['file_path'] for t in test_files]:
                    test_files.append({
                        'file_path': record['test_file'],
                        'relationship': 'imports',
                        'confidence': 0.8
                    })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'production_file': file_path,
                'test_files': test_files,
                'count': len(test_files)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'test_files': []}

    def _find_implementations(self, interface_name: str, include_indirect: bool = False) -> Dict[str, Any]:
        """
        Find all implementations of an interface or abstract class.

        Uses INHERITS relationship to find direct and indirect subclasses.

        Args:
            interface_name: Name of interface or abstract class
            include_indirect: Include indirect implementations (subclasses of subclasses)

        Returns:
            Dict with success status and list of implementations
        """
        start_time = time.time()
        try:
            # Find direct implementations
            depth = '*1..3' if include_indirect else '*1'
            query = f"""
            MATCH (base:Class)-[:INHERITS{depth}]-(impl:Class)
            WHERE base.name = $interface_name OR base.qualified_name = $interface_name
            RETURN impl.qualified_name as implementation,
                   impl.file_path as file_path,
                   impl.start_line as line,
                   impl.name as simple_name,
                   impl.is_abstract as is_abstract
            LIMIT 50
            """

            results = self.kb.execute_query(query, {'interface_name': interface_name})

            implementations = []
            for record in results.records:
                # Filter out abstract classes from results (they're not concrete implementations)
                if not record.get('is_abstract', False):
                    implementations.append({
                        'implementation': record['implementation'],
                        'simple_name': record['simple_name'],
                        'file_path': record['file_path'],
                        'line': record['line']
                    })

            self._record_call(time_taken=time.time() - start_time, error=False)
            return {
                'success': True,
                'interface': interface_name,
                'implementations': implementations,
                'count': len(implementations)
            }
        except Exception as e:
            self._record_call(time_taken=time.time() - start_time, error=True)
            return {'success': False, 'error': str(e), 'implementations': []}
