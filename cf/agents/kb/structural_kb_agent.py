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
Refactored with focused handler components for single responsibility.
"""

import os
import time
from typing import Dict, List, Any, Callable

from cf.agents.knowledge_base import KnowledgeAgent, AgentResult
from cf.agents.protocols import KnowledgeBaseProtocol
from cf.agents.structural_kb_components.semantic_tools_handler import SemanticToolsHandler
from cf.agents.structural_kb_components.pattern_tools_handler import PatternToolsHandler
from cf.agents.structural_kb_components.architecture_tools_handler import ArchitectureToolsHandler
from cf.agents.structural_kb_components.navigation_tools_handler import NavigationToolsHandler
from cf.agents.structural_kb_components.tracing_tools_handler import TracingToolsHandler
from cf.agents.structural_kb_components.schema_builder import SchemaBuilder


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

        # File discovery defaults (still needed by this class)
        self.default_file_discovery_limit = kb_agent_config.get('default_file_discovery_limit', 50)
        self.query_result_limit = kb_agent_config.get('query_result_limit', 1000)

        # Initialize handler components (delegate tool logic)
        self.semantic_handler = SemanticToolsHandler(kb, config, self._record_call)
        self.pattern_handler = PatternToolsHandler(kb, config, self._record_call)
        self.architecture_handler = ArchitectureToolsHandler(kb, config, self._record_call)
        self.navigation_handler = NavigationToolsHandler(kb, config, self._record_call)
        self.tracing_handler = TracingToolsHandler(kb, config, self._record_call)
        self.schema_builder = SchemaBuilder(config, self.get_prefixed_tool_name)

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
        """Get OpenAPI-style schemas for all tools (delegate to SchemaBuilder)"""
        return self.schema_builder.build_all_schemas()

    def _get_tool_schemas_old(self) -> List[Dict[str, Any]]:
        """Old implementation - replaced by SchemaBuilder"""
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

    # ========== Semantic Layer Tool Implementations (Delegated) ==========

    def _search_by_semantics(self, query: str, scope: str = 'all', limit: int = None) -> Dict[str, Any]:
        """Search using semantic/vector search (delegates to SemanticToolsHandler)"""
        return self.semantic_handler.search_by_semantics(query, scope, limit)

    def _search_by_functionality(self, description: str, limit: int = None) -> Dict[str, Any]:
        """Search by functional description (delegates to SemanticToolsHandler)"""
        return self.semantic_handler.search_by_functionality(description, limit)

    def _find_similar_components(self, component_id: str, limit: int = None) -> Dict[str, Any]:
        """Find similar code components (delegates to SemanticToolsHandler)"""
        return self.semantic_handler.find_similar_components(component_id, limit)

    def _detect_duplicate_code(self, similarity_threshold: float = None) -> Dict[str, Any]:
        """Detect duplicate code (delegates to SemanticToolsHandler)"""
        return self.semantic_handler.detect_duplicate_code(similarity_threshold)

    def _search_by_example(self, code_snippet: str, limit: int = None) -> Dict[str, Any]:
        """Find code similar to a given example snippet (delegates to SemanticToolsHandler)"""
        return self.semantic_handler.search_by_example(code_snippet, limit)

    # ========== Pattern Recognition Tool Implementations ==========

    def _find_design_patterns(self, pattern_type: str = 'all') -> Dict[str, Any]:
        """Find design patterns (delegates to PatternToolsHandler)"""
        return self.pattern_handler.find_design_patterns(pattern_type)

    def _detect_code_smells(self, scope: str = 'all') -> Dict[str, Any]:
        """Detect code smells (delegates to PatternToolsHandler)"""
        return self.pattern_handler.detect_code_smells(scope)

    def _find_similar_patterns(self, example_component_id: str) -> Dict[str, Any]:
        """Find similar patterns (delegates to PatternToolsHandler)"""
        return self.pattern_handler.find_similar_patterns(example_component_id, self.semantic_handler)

    # ========== Architecture Tool Implementations ==========

    def _get_architecture_overview(self, scope: str = 'all') -> Dict[str, Any]:
        """Get architecture overview (delegates to ArchitectureToolsHandler)"""
        return self.architecture_handler.get_architecture_overview(scope)

    def _get_module_boundaries(self) -> Dict[str, Any]:
        """Get module boundaries (delegates to ArchitectureToolsHandler)"""
        return self.architecture_handler.get_module_boundaries()

    def _identify_cross_cutting_concerns(self) -> Dict[str, Any]:
        """Identify cross-cutting concerns (delegates to ArchitectureToolsHandler)"""
        return self.architecture_handler.identify_cross_cutting_concerns()

    def _find_layer_components(self, layer: str) -> Dict[str, Any]:
        """Find layer components (delegates to ArchitectureToolsHandler)"""
        return self.architecture_handler.find_layer_components(layer)

    # ========== Life-of-X Tool Implementations ==========

    def _trace_execution_path(self, entry_point: str, max_depth: int = None, max_paths: int = None) -> Dict[str, Any]:
        """Trace execution path (delegates to TracingToolsHandler)"""
        return self.tracing_handler.trace_execution_path(entry_point, max_depth, max_paths)

    def _trace_data_flow(self, start_element: str, max_depth: int = None) -> Dict[str, Any]:
        """Trace data flow (delegates to TracingToolsHandler)"""
        return self.tracing_handler.trace_data_flow(start_element, max_depth)

    def _trace_request_lifecycle(self, endpoint_function: str, max_depth: int = None) -> Dict[str, Any]:
        """Trace request lifecycle (delegates to TracingToolsHandler)"""
        return self.tracing_handler.trace_request_lifecycle(endpoint_function, max_depth)

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
        """Find callers (delegates to NavigationToolsHandler)"""
        return self.navigation_handler.find_callers(function_name, max_results)

    def _find_callees(self, function_name: str, max_results: int = None) -> Dict[str, Any]:
        """Find callees (delegates to NavigationToolsHandler)"""
        return self.navigation_handler.find_callees(function_name, max_results)

    def _find_usages(self, symbol_name: str, symbol_type: str = 'any', max_results: int = None) -> Dict[str, Any]:
        """Find usages (delegates to NavigationToolsHandler)"""
        return self.navigation_handler.find_usages(symbol_name, symbol_type, max_results)

    def _find_related_tests(self, file_path: str, include_indirect: bool = False) -> Dict[str, Any]:
        """Find related tests (delegates to NavigationToolsHandler)"""
        return self.navigation_handler.find_related_tests(file_path, include_indirect)

    def _find_implementations(self, interface_name: str, include_indirect: bool = False) -> Dict[str, Any]:
        """Find implementations (delegates to NavigationToolsHandler)"""
        return self.navigation_handler.find_implementations(interface_name, include_indirect)
