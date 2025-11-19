"""
Schema Builder for StructuralKBAgent

Handles construction of OpenAPI-style tool schemas for LLM function calling.
"""

from typing import Dict, List, Any, Callable


class SchemaBuilder:
    """Builds OpenAPI-style schemas for all KB tools."""

    def __init__(self, config: Dict[str, Any], get_prefixed_name_fn: Callable[[str], str]):
        """
        Initialize schema builder.

        Args:
            config: Agent configuration
            get_prefixed_name_fn: Function to get prefixed tool names (from parent agent)
        """
        self.config = config
        self.get_prefixed_tool_name = get_prefixed_name_fn

        # Extract layer configurations
        kb_config = config.get('knowledge_base', {}) if config else {}
        self.semantic_config = kb_config.get('semantic', {})
        self.patterns_config = kb_config.get('patterns', {})
        self.lifeofx_config = kb_config.get('lifeofx', {})

    def build_all_schemas(self) -> List[Dict[str, Any]]:
        """Build all tool schemas based on enabled layers"""
        schemas = []

        # Add schemas for each enabled layer
        if self.semantic_config.get('enabled', False):
            schemas.extend(self._build_semantic_schemas())

        if self.patterns_config.get('enabled', False):
            schemas.extend(self._build_pattern_schemas())

        schemas.extend(self._build_architecture_schemas())
        schemas.extend(self._build_navigation_schemas())

        if self.lifeofx_config.get('enabled', False):
            schemas.extend(self._build_tracing_schemas())

        return schemas

    def _build_semantic_schemas(self) -> List[Dict[str, Any]]:
        """Build schemas for semantic search tools"""
        return [
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
        ]

    def _build_pattern_schemas(self) -> List[Dict[str, Any]]:
        """Build schemas for pattern detection tools"""
        return [
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
        ]

    def _build_architecture_schemas(self) -> List[Dict[str, Any]]:
        """Build schemas for architecture tools"""
        return [
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
        ]

    def _build_navigation_schemas(self) -> List[Dict[str, Any]]:
        """Build schemas for code navigation tools"""
        return [
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
        ]

    def _build_tracing_schemas(self) -> List[Dict[str, Any]]:
        """Build schemas for Life-of-X tracing tools"""
        return [
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
        ]
