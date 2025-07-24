"""
Tool Registry for CodeFusion

Central registry for all tools available to agents.
"""

from typing import Dict, Any, Callable
from pathlib import Path

from cf.tools.repo_tools import RepoTools
from cf.tools.llm_tools import LLMTools
from cf.tools.web_tools import WebTools


class ToolRegistry:
    """Central registry for all CodeFusion tools"""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        
        # Initialize tool modules
        self.repo_tools = RepoTools(repo_path)
        self.llm_tools = LLMTools()
        self.web_tools = WebTools()
        
        # Register all available tools
        self.tools: Dict[str, Callable] = {}
        self._register_tools()
    
    def _register_tools(self):
        """Register all available tools"""
        
        # Repository tools
        self.tools['scan_directory'] = self.repo_tools.scan_directory
        self.tools['list_files'] = self.repo_tools.list_files
        self.tools['read_file'] = self.repo_tools.read_file
        self.tools['search_files'] = self.repo_tools.search_files
        self.tools['get_file_info'] = self.repo_tools.get_file_info
        
        # LLM-based analysis tools
        self.tools['analyze_code_structure'] = self.llm_tools.analyze_code_structure
        self.tools['extract_functions'] = self.llm_tools.extract_functions
        self.tools['extract_classes'] = self.llm_tools.extract_classes
        self.tools['detect_patterns'] = self.llm_tools.detect_patterns
        self.tools['summarize_code'] = self.llm_tools.summarize_code
        
        # Web search tools
        self.tools['web_search'] = self.web_tools.search
        self.tools['search_documentation'] = self.web_tools.search_documentation
    
    def execute(self, tool_name: str, **params) -> Dict[str, Any]:
        """Execute a tool with parameters"""
        if tool_name not in self.tools:
            return {
                'error': f'Tool "{tool_name}" not found',
                'available_tools': list(self.tools.keys())
            }
        
        try:
            result = self.tools[tool_name](**params)
            return result if isinstance(result, dict) else {'result': result}
        except Exception as e:
            return {'error': str(e)}
    
    def get_available_tools(self) -> Dict[str, str]:
        """Get list of available tools with descriptions"""
        return {
            # Repository tools
            'scan_directory': 'Recursively scan directory structure',
            'list_files': 'List files matching pattern',
            'read_file': 'Read file contents',
            'search_files': 'Search for pattern across files',
            'get_file_info': 'Get file metadata',
            
            # LLM analysis tools
            'analyze_code_structure': 'Analyze code architecture using LLM',
            'extract_functions': 'Extract function signatures and docs',
            'extract_classes': 'Extract class definitions and methods',
            'detect_patterns': 'Detect design/architectural patterns',
            'summarize_code': 'Generate code summary',
            
            # Web search tools
            'web_search': 'Search web for information',
            'search_documentation': 'Search for official documentation'
        }
    
    def get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        """Get OpenAPI-style schema for tool (for LLM function calling)"""
        schemas = {
            # Repository tools
            'scan_directory': {
                'type': 'function',
                'function': {
                    'name': 'scan_directory',
                    'description': 'Recursively scan directory to discover files and structure',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'directory': {'type': 'string', 'description': 'Directory to scan'},
                            'max_depth': {'type': 'integer', 'description': 'Maximum recursion depth'}
                        },
                        'required': ['directory']
                    }
                }
            },
            'list_files': {
                'type': 'function',
                'function': {
                    'name': 'list_files',
                    'description': 'List files matching pattern in directory',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'pattern': {'type': 'string', 'description': 'File pattern (e.g., *.py)'},
                            'directory': {'type': 'string', 'description': 'Directory to search'},
                            'recursive': {'type': 'boolean', 'description': 'Search recursively'}
                        },
                        'required': ['pattern']
                    }
                }
            },
            'read_file': {
                'type': 'function',
                'function': {
                    'name': 'read_file',
                    'description': 'Read contents of a specific file',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'file_path': {'type': 'string', 'description': 'Path to file to read'},
                            'max_lines': {'type': 'integer', 'description': 'Maximum lines to read'}
                        },
                        'required': ['file_path']
                    }
                }
            },
            'search_files': {
                'type': 'function', 
                'function': {
                    'name': 'search_files',
                    'description': 'Search for pattern across multiple files',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'pattern': {'type': 'string', 'description': 'Search pattern'},
                            'file_types': {'type': 'array', 'items': {'type': 'string'}, 'description': 'File extensions to search'},
                            'max_results': {'type': 'integer', 'description': 'Maximum results to return'}
                        },
                        'required': ['pattern']
                    }
                }
            },
            'get_file_info': {
                'type': 'function',
                'function': {
                    'name': 'get_file_info',
                    'description': 'Get metadata about a file',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'file_path': {'type': 'string', 'description': 'Path to file'}
                        },
                        'required': ['file_path']
                    }
                }
            },
            
            # LLM analysis tools
            'analyze_code_structure': {
                'type': 'function',
                'function': {
                    'name': 'analyze_code_structure',
                    'description': 'Analyze code architecture and structure using LLM',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'code_content': {'type': 'string', 'description': 'Code to analyze'},
                            'file_path': {'type': 'string', 'description': 'Path of the code file'},
                            'focus': {'type': 'string', 'description': 'What to focus on (functions, classes, patterns)'}
                        },
                        'required': ['code_content']
                    }
                }
            },
            'extract_functions': {
                'type': 'function',
                'function': {
                    'name': 'extract_functions',
                    'description': 'Extract function signatures and documentation from code',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'code_content': {'type': 'string', 'description': 'Code to analyze'},
                            'file_path': {'type': 'string', 'description': 'Path of the code file'}
                        },
                        'required': ['code_content']
                    }
                }
            },
            'extract_classes': {
                'type': 'function',
                'function': {
                    'name': 'extract_classes',
                    'description': 'Extract class definitions and methods from code',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'code_content': {'type': 'string', 'description': 'Code to analyze'},
                            'file_path': {'type': 'string', 'description': 'Path of the code file'}
                        },
                        'required': ['code_content']
                    }
                }
            },
            'detect_patterns': {
                'type': 'function',
                'function': {
                    'name': 'detect_patterns',
                    'description': 'Detect design and architectural patterns in code',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'code_content': {'type': 'string', 'description': 'Code to analyze'},
                            'file_path': {'type': 'string', 'description': 'Path of the code file'},
                            'pattern_types': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Types of patterns to look for'}
                        },
                        'required': ['code_content']
                    }
                }
            },
            'summarize_code': {
                'type': 'function',
                'function': {
                    'name': 'summarize_code',
                    'description': 'Generate summary of code functionality and structure',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'code_content': {'type': 'string', 'description': 'Code to summarize'},
                            'file_path': {'type': 'string', 'description': 'Path of the code file'},
                            'summary_type': {'type': 'string', 'description': 'Type of summary (overview, detailed, technical)'}
                        },
                        'required': ['code_content']
                    }
                }
            },
            
            # Web search tools
            'web_search': {
                'type': 'function',
                'function': {
                    'name': 'web_search',
                    'description': 'Search web for information about topic',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'query': {'type': 'string', 'description': 'Search query'},
                            'max_results': {'type': 'integer', 'description': 'Maximum results to return'}
                        },
                        'required': ['query']
                    }
                }
            },
            'search_documentation': {
                'type': 'function',
                'function': {
                    'name': 'search_documentation',
                    'description': 'Search for official documentation and guides',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'topic': {'type': 'string', 'description': 'Documentation topic to search'},
                            'framework': {'type': 'string', 'description': 'Framework or technology name'}
                        },
                        'required': ['topic']
                    }
                }
            }
        }
        
        return schemas.get(tool_name, {})
    
    def get_all_schemas(self) -> list:
        """Get all tool schemas for LLM function calling"""
        schemas = []
        for tool_name in self.tools.keys():
            schema = self.get_tool_schema(tool_name)
            if schema:  # Only add if schema exists
                schemas.append(schema)
        return schemas