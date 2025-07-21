"""
Tool Registry for LLM Function Calling

This module defines the tools available to LLM for function calling,
including their schemas and execution mappings.
"""

from typing import Dict, List, Any, Callable
import json

from cf.utils.logging_utils import tool_log, error_log
from cf.tools.web_search import web_search_general, web_search_documentation, web_search_code_examples, web_search_comparison


class ToolRegistry:
    """Registry of tools available for LLM function calling."""
    
    def __init__(self):
        self.tools = {}
        self.tool_schemas = []
        self._register_core_tools()
    
    def _register_core_tools(self):
        """Register core tools for code exploration."""
        
        # File system tools
        self.register_tool(
            name="scan_directory",
            description="Scan a directory to understand its structure and find files",
            parameters={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path to scan (default: '.')"
                    },
                    "max_depth": {
                        "type": "integer", 
                        "description": "Maximum depth to scan (default: 3)"
                    }
                },
                "required": ["directory"]
            },
            function=self._scan_directory_tool
        )
        
        self.register_tool(
            name="list_files",
            description="List files matching specific patterns in a directory",
            parameters={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in (default: '.')"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "File pattern to match (e.g., '*.py', '*routing*')"
                    }
                },
                "required": ["pattern"]
            },
            function=self._list_files_tool
        )
        
        self.register_tool(
            name="read_file",
            description="Read and analyze the contents of a specific file",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum number of lines to read (default: 500)"
                    }
                },
                "required": ["file_path"]
            },
            function=self._read_file_tool
        )
        
        self.register_tool(
            name="search_files",
            description="Search for files containing specific content or patterns",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern or keyword to find in files"
                    },
                    "file_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File extensions to search in (e.g., ['.py', '.js'])"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 20)"
                    }
                },
                "required": ["pattern"]
            },
            function=self._search_files_tool
        )
        
        self.register_tool(
            name="analyze_code",
            description="Analyze code structure, patterns, and architecture in a file",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the code file to analyze"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["structure", "patterns", "functions", "classes"],
                        "description": "Type of analysis to perform"
                    }
                },
                "required": ["file_path", "analysis_type"]
            },
            function=self._analyze_code_tool
        )
        
        # Reasoning tools
        self.register_tool(
            name="generate_summary",
            description="Generate a summary of analyzed content or findings",
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to summarize"
                    },
                    "summary_type": {
                        "type": "string",
                        "enum": ["brief", "detailed", "architectural", "technical"],
                        "description": "Type of summary to generate"
                    },
                    "focus": {
                        "type": "string",
                        "description": "Focus area for the summary"
                    }
                },
                "required": ["content", "summary_type"]
            },
            function=self._generate_summary_tool
        )
        
        # LLM-based code analysis tools
        self.register_tool(
            name="analyze_function_signatures",
            description="Use LLM to intelligently extract and analyze function signatures, purposes, and relationships",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the code file to analyze"
                    },
                    "content": {
                        "type": "string", 
                        "description": "Code content to analyze for function signatures"
                    },
                    "focus": {
                        "type": "string",
                        "enum": ["all", "public", "entry_points", "api", "core_logic"],
                        "description": "Focus area for function analysis"
                    }
                },
                "required": ["content"]
            },
            function=self._analyze_function_signatures_tool
        )
        
        self.register_tool(
            name="analyze_class_hierarchies",
            description="Use LLM to intelligently analyze class structures, inheritance, and architectural patterns",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the code file to analyze"
                    },
                    "content": {
                        "type": "string",
                        "description": "Code content to analyze for class hierarchies"
                    },
                    "focus": {
                        "type": "string", 
                        "enum": ["inheritance", "composition", "patterns", "interfaces", "all"],
                        "description": "Focus area for class analysis"
                    }
                },
                "required": ["content"]
            },
            function=self._analyze_class_hierarchies_tool
        )
        
        self.register_tool(
            name="detect_code_patterns",
            description="Use LLM to intelligently detect architectural and design patterns in code",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the code file to analyze"
                    },
                    "content": {
                        "type": "string",
                        "description": "Code content to analyze for patterns"
                    },
                    "pattern_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of patterns to look for (e.g., 'design_patterns', 'architectural_patterns', 'api_patterns')"
                    }
                },
                "required": ["content"]
            },
            function=self._detect_code_patterns_tool
        )
        
        # Web search tools
        self.register_tool(
            name="web_search",
            description="Search the web for documentation, tutorials, and examples related to technologies or concepts",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for web search"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)"
                    },
                    "filter_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to filter results (e.g., ['docs', 'tutorial', 'example'])"
                    }
                },
                "required": ["query"]
            },
            function=web_search_general
        )
        
        self.register_tool(
            name="search_documentation",
            description="Search for official documentation about a specific technology or topic",
            parameters={
                "type": "object",
                "properties": {
                    "technology": {
                        "type": "string",
                        "description": "Technology or framework name (e.g., 'FastAPI', 'Starlette', 'Python')"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Specific topic to search for (e.g., 'routing', 'authentication', 'middleware')"
                    }
                },
                "required": ["technology", "topic"]
            },
            function=web_search_documentation
        )
        
        self.register_tool(
            name="search_code_examples",
            description="Search for code examples and implementations related to a specific use case",
            parameters={
                "type": "object",
                "properties": {
                    "technology": {
                        "type": "string",
                        "description": "Technology or framework name"
                    },
                    "use_case": {
                        "type": "string",
                        "description": "Specific use case or implementation pattern"
                    }
                },
                "required": ["technology", "use_case"]
            },
            function=web_search_code_examples
        )
        
        self.register_tool(
            name="search_technology_comparison",
            description="Search for comparisons between two technologies or frameworks",
            parameters={
                "type": "object",
                "properties": {
                    "tech1": {
                        "type": "string",
                        "description": "First technology to compare"
                    },
                    "tech2": {
                        "type": "string",
                        "description": "Second technology to compare"
                    }
                },
                "required": ["tech1", "tech2"]
            },
            function=web_search_comparison
        )
    
    def register_tool(self, name: str, description: str, parameters: Dict[str, Any], function: Callable):
        """Register a new tool."""
        # Store the function for execution
        self.tools[name] = function
        
        # Store the schema for LLM
        tool_schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        }
        self.tool_schemas.append(tool_schema)
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas for LLM."""
        return self.tool_schemas
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any], agent_context: Any = None) -> Dict[str, Any]:
        """Execute a tool with given arguments."""
        
        tool_log(f"\n🔧 [ToolRegistry] Executing tool: {tool_name}")
        tool_log(f"📝 [ToolRegistry] Arguments: {arguments}")
        
        if tool_name not in self.tools:
            error_log(f"❌ [ToolRegistry] Tool '{tool_name}' not found in registry")
            tool_log(f"📋 [ToolRegistry] Available tools: {list(self.tools.keys())}")
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "result": None
            }
        
        try:
            tool_log(f"⚙️  [ToolRegistry] Calling tool function for {tool_name}")
            # Pass agent context to tool for execution
            result = self.tools[tool_name](arguments, agent_context)
            
            tool_log(f"✅ [ToolRegistry] Tool {tool_name} executed successfully")
            if isinstance(result, dict) and 'summary' in result:
                tool_log(f"📊 [ToolRegistry] Result summary: {result.get('summary', 'No summary')}")
            
            return {
                "success": True,
                "error": None,
                "result": result
            }
        except Exception as e:
            error_log(f"❌ [ToolRegistry] Tool {tool_name} execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "result": None
            }
    
    # Tool implementations that delegate to agent methods
    def _scan_directory_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute scan_directory tool."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        directory = args.get("directory", ".")
        max_depth = args.get("max_depth", 3)
        
        # Call agent's scan directory method
        return agent_context._tool_scan_directory({
            "directory": directory,
            "max_depth": max_depth
        })
    
    def _list_files_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute list_files tool."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        pattern = args.get("pattern", "*")
        directory = args.get("directory", ".")
        
        return agent_context._tool_list_files({
            "pattern": pattern,
            "directory": directory
        })
    
    def _read_file_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute read_file tool."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        file_path = args["file_path"]
        max_lines = args.get("max_lines", 500)
        
        return agent_context._tool_read_file({
            "file_path": file_path,
            "max_lines": max_lines
        })
    
    def _search_files_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute search_files tool."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        pattern = args["pattern"]
        file_types = args.get("file_types", [".py", ".js", ".ts"])
        max_results = args.get("max_results", 20)
        
        return agent_context._tool_search_files({
            "pattern": pattern,
            "file_types": file_types,
            "max_results": max_results
        })
    
    def _analyze_code_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute analyze_code tool."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        file_path = args["file_path"]
        analysis_type = args["analysis_type"]
        
        return agent_context._tool_analyze_code({
            "file_path": file_path,
            "analysis_type": analysis_type
        })
    
    def _generate_summary_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute generate_summary tool."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        content = args["content"]
        summary_type = args["summary_type"]
        focus = args.get("focus", "all")
        
        return agent_context._tool_llm_summary({
            "content": content,
            "summary_type": summary_type,
            "focus": focus
        })
    
    def _analyze_function_signatures_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute LLM-based function signature analysis."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        content = args["content"]
        file_path = args.get("file_path", "unknown")
        focus = args.get("focus", "all")
        
        return agent_context._tool_llm_function_analysis({
            "content": content,
            "file_path": file_path,
            "focus": focus
        })
    
    def _analyze_class_hierarchies_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute LLM-based class hierarchy analysis."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        content = args["content"]
        file_path = args.get("file_path", "unknown")
        focus = args.get("focus", "all")
        
        return agent_context._tool_llm_class_analysis({
            "content": content,
            "file_path": file_path,
            "focus": focus
        })
    
    def _detect_code_patterns_tool(self, args: Dict[str, Any], agent_context: Any) -> Dict[str, Any]:
        """Execute LLM-based code pattern detection."""
        if not agent_context:
            raise ValueError("Agent context required for tool execution")
        
        content = args["content"]
        file_path = args.get("file_path", "unknown")
        pattern_types = args.get("pattern_types", ["design_patterns", "architectural_patterns"])
        
        return agent_context._tool_llm_pattern_detection({
            "content": content,
            "file_path": file_path,
            "pattern_types": pattern_types
        })


# Global tool registry instance
tool_registry = ToolRegistry()