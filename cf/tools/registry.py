"""
Tool Registry for CodeFusion

Central registry for all tools available to agents.
Supports pluggable agents via AgentRegistry.
Tracks per-tool metrics for cost analysis.
"""

import time
import yaml
from typing import Dict, Any, Callable, Optional
from pathlib import Path

from cf.tools.repo_tools import RepoTools
from cf.tools.llm_tools import LLMTools
from cf.tools.web_tools import WebTools
from cf.tools.kb_tools import KBTools
from cf.tools.registry_helpers import ToolMetricsTracker, ToolNameResolver


class ToolRegistry:
    """Central registry for all CodeFusion tools"""

    def __init__(self, repo_path: str, agent_registry: Optional[Any] = None,
                 kb_orchestrator: Optional[Any] = None):
        self.repo_path = repo_path
        self.agent_registry = agent_registry

        # Initialize tool modules
        self.repo_tools = RepoTools(repo_path)
        self.llm_tools = LLMTools()
        self.web_tools = WebTools()
        self.kb_tools = KBTools(repo_path, kb_orchestrator)

        # Initialize metrics tracker
        self.metrics_tracker = ToolMetricsTracker()

        # Initialize tool name resolver
        self.resolver = ToolNameResolver()

        # Load tool schemas from YAML
        self._schemas = self._load_schemas()

        # Register all available tools
        self.tools: Dict[str, Callable] = {}
        self._register_tools()

        # Register agent tools if registry provided
        if self.agent_registry:
            self._register_agent_tools()

    def _load_schemas(self) -> Dict[str, Any]:
        """Load tool schemas from YAML file"""
        schema_path = Path(__file__).parent / 'schemas.yaml'

        try:
            with open(schema_path, 'r') as f:
                schemas = yaml.safe_load(f)
            return schemas if schemas else {}
        except FileNotFoundError:
            print(f"⚠️ Schema file not found: {schema_path}")
            return {}
        except Exception as e:
            print(f"⚠️ Failed to load schemas: {e}")
            return {}

    def _register_tools(self):
        """Register all available tools"""
        
        # Repository tools
        self.tools['scan_directory'] = self.repo_tools.scan_directory
        self.tools['list_files'] = self.repo_tools.list_files
        self.tools['read_file'] = self.repo_tools.read_file
        self.tools['search_files'] = self.repo_tools.search_files
        self.tools['get_file_info'] = self.repo_tools.get_file_info

        # Enhanced file tools (head, tail, cat, wc, sed, stat equivalents)
        self.tools['head_file'] = self.repo_tools.head_file
        self.tools['tail_file'] = self.repo_tools.tail_file
        self.tools['cat_file'] = self.repo_tools.cat_file
        self.tools['word_count'] = self.repo_tools.word_count
        self.tools['regex_replace'] = self.repo_tools.regex_replace
        self.tools['get_file_stat'] = self.repo_tools.get_file_stat

        # Shell execution tool (with security whitelist)
        self.tools['bash_exec'] = self.repo_tools.bash_exec

        # LLM-based analysis tools
        self.tools['analyze_code_structure'] = self.llm_tools.analyze_code_structure
        self.tools['extract_functions'] = self.llm_tools.extract_functions
        self.tools['extract_classes'] = self.llm_tools.extract_classes
        self.tools['detect_patterns'] = self.llm_tools.detect_patterns
        self.tools['summarize_code'] = self.llm_tools.summarize_code
        
        # Web search tools
        self.tools['web_search'] = self.web_tools.search
        self.tools['search_documentation'] = self.web_tools.search_documentation

        # KB tools (work with or without KB - fallback to grep/AST)
        self.tools['find_callers'] = self.kb_tools.find_callers
        self.tools['find_callees'] = self.kb_tools.find_callees
        self.tools['find_usages'] = self.kb_tools.find_usages
        self.tools['search_by_semantics'] = self.kb_tools.search_by_semantics
        self.tools['search_by_functionality'] = self.kb_tools.search_by_functionality
        self.tools['find_dependencies'] = self.kb_tools.find_dependencies
        self.tools['find_files_for_question'] = self.kb_tools.find_files_for_question
        self.tools['find_related_tests'] = self.kb_tools.find_related_tests
    
    def execute(self, tool_name: str, **params) -> Dict[str, Any]:
        """Execute a tool with parameters and track metrics"""
        # Resolve tool name dynamically using ToolNameResolver
        resolved_name = self.resolver.resolve(tool_name, self.tools)

        # If resolution failed, return helpful error
        if resolved_name is None:
            return self.resolver.get_resolution_error(tool_name, self.tools)

        # Log tool call with truncated params
        param_str = ", ".join([f"{k}={str(v)[:50]}..." if len(str(v)) > 50 else f"{k}={v}" for k, v in params.items()])
        print(f"🔧 Tool call: {resolved_name}({param_str})")

        start_time = time.time()
        success = False
        tokens = 0
        cost = 0.0
        error = ""

        try:
            result = self.tools[resolved_name](**params)

            # Extract tokens and cost if available
            if isinstance(result, dict):
                tokens = result.get('tokens', 0)
                cost = result.get('cost', 0.0)

                # For LLM results with usage
                if 'usage' in result:
                    usage = result['usage']
                    tokens = usage.get('total_tokens', 0)

                    # Estimate cost if not provided
                    if cost == 0.0 and 'cost_estimate' in result:
                        cost = result['cost_estimate']

            success = True
            final_result = result if isinstance(result, dict) else {'result': result}

        except Exception as e:
            error = str(e)
            final_result = {'error': error}

        finally:
            duration = time.time() - start_time

            # Log tool completion with metrics
            status_icon = "✅" if success else "❌"
            metrics_str = f" | {tokens} tokens" if tokens > 0 else ""
            metrics_str += f" | ${cost:.4f}" if cost > 0 else ""
            print(f"   {status_icon} Completed in {duration:.2f}s{metrics_str}")

            # Record metrics
            self.metrics_tracker.record_call(
                tool_name=resolved_name,
                duration=duration,
                success=success,
                tokens=tokens,
                cost=cost,
                error=error,
                metadata=params
            )

        return final_result
    
    def get_available_tools(self) -> Dict[str, str]:
        """Get list of available tools with descriptions"""
        return {
            # Repository tools
            'scan_directory': 'Recursively scan directory structure',
            'list_files': 'List files matching pattern',
            'read_file': 'Read file contents',
            'search_files': 'Search for pattern across files',
            'get_file_info': 'Get file metadata',

            # Enhanced file tools (head, tail, cat, wc, sed, stat equivalents)
            'head_file': 'Read first N lines of a file (like head)',
            'tail_file': 'Read last N lines of a file (like tail)',
            'cat_file': 'Read entire file contents (like cat)',
            'word_count': 'Count lines, words, and characters (like wc)',
            'regex_replace': 'Preview/apply regex substitution (like sed)',
            'get_file_stat': 'Get comprehensive file statistics (like stat)',

            # Shell execution tool
            'bash_exec': 'Execute whitelisted shell commands (git, pytest, linters)',

            # LLM analysis tools
            'analyze_code_structure': 'Analyze code architecture using LLM',
            'extract_functions': 'Extract function signatures and docs',
            'extract_classes': 'Extract class definitions and methods',
            'detect_patterns': 'Detect design/architectural patterns',
            'summarize_code': 'Generate code summary',

            # Web search tools
            'web_search': 'Search web for information',
            'search_documentation': 'Search for official documentation',

            # KB tools (work with or without KB - fallback to grep/AST)
            'find_callers': 'Find functions that call a specific function',
            'find_callees': 'Find functions called by a specific function',
            'find_usages': 'Find all usages of a symbol',
            'search_by_semantics': 'Search code by semantic meaning',
            'search_by_functionality': 'Find code implementing specific functionality',
            'find_dependencies': 'Find what a module/function depends on',
            'find_files_for_question': 'Find relevant files to answer a question',
            'find_related_tests': 'Find test files related to a source file'
        }
    
    def get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        """Get OpenAPI-style schema for tool (for LLM function calling)"""
        # First check local schemas
        schema = self._schemas.get(tool_name)
        if schema:
            return schema

        # Check agent registry for KB tool schemas
        if self.agent_registry:
            all_agent_schemas = self.agent_registry.get_all_tool_schemas()
            for agent_schema in all_agent_schemas:
                # Agent schemas have 'function.name' structure
                func = agent_schema.get('function', agent_schema)
                if func.get('name') == tool_name:
                    return agent_schema

        return {}
    
    def get_all_schemas(self) -> list:
        """Get all tool schemas for LLM function calling"""
        schemas = []
        for tool_name in self.tools.keys():
            schema = self.get_tool_schema(tool_name)
            if schema:  # Only add if schema exists
                schemas.append(schema)

        # Add agent tool schemas if registry provided
        if self.agent_registry:
            agent_schemas = self.agent_registry.get_all_tool_schemas()
            schemas.extend(agent_schemas)

        return schemas

    def _register_agent_tools(self):
        """Register tools from all agents in the agent registry"""
        if not self.agent_registry:
            return

        agent_tools = self.agent_registry.get_all_tools()
        for tool_name, tool_func in agent_tools.items():
            # Avoid name conflicts with existing tools
            if tool_name in self.tools:
                print(f"⚠️ Tool '{tool_name}' from agent conflicts with existing tool")
                continue

            self.tools[tool_name] = tool_func
            print(f"✅ Registered agent tool: {tool_name}")

    def register_agent(self, agent: Any):
        """
        Register a knowledge agent and its tools.

        Args:
            agent: KnowledgeAgent instance to register
        """
        if not self.agent_registry:
            print("⚠️ No agent registry configured")
            return False

        # Register agent in registry
        success = self.agent_registry.register(agent)

        if success:
            # Refresh agent tools
            self._register_agent_tools()

        return success

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get tool usage metrics.

        Returns:
            Dictionary with all tool metrics
        """
        return self.metrics_tracker.export_for_eval()

    def get_tool_metrics(self, tool_name: str) -> Dict[str, Any]:
        """
        Get metrics for a specific tool.

        Args:
            tool_name: Tool to get metrics for

        Returns:
            Tool metrics dictionary
        """
        return self.metrics_tracker.get_tool_metrics(tool_name)

    def reset_metrics(self):
        """Reset all tool metrics"""
        self.metrics_tracker.reset()