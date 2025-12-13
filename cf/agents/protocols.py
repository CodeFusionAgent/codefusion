"""
Agent Infrastructure - Protocols and Registry

This module provides the core infrastructure for CodeFusion agents:

1. Agent Protocols (Interface Definitions):
   - Define protocols using structural subtyping for loose coupling
   - Enable dependency injection and easier testing
   - Support duck typing while maintaining type safety

2. Agent Registry (Registration System):
   - Manages runtime registration and discovery of agents
   - Provides dynamic tool discovery with consistent naming
   - Handles agent lifecycle management
"""

from typing import Any, Callable, Dict, List, Optional, Protocol


class KnowledgeBaseProtocol(Protocol):
    """
    Protocol for knowledge base backends.

    Any class implementing these methods can be used as a KB backend
    for agents, regardless of inheritance hierarchy.

    This enables:
    - Swapping KB implementations (Neo4j, in-memory, mock)
    - Testing agents without full KB infrastructure
    - Loose coupling between agents and KB layers

    Example:
        # Real implementation
        class Neo4jKnowledgeBase:
            def search_by_natural_language(self, query, top_k):
                # Query Neo4j with embeddings
                ...

        # Mock for testing
        class MockKnowledgeBase:
            def search_by_natural_language(self, query, top_k):
                return [{'file': 'test.py', 'score': 0.9}]

        # Both work with KBTools in ToolRegistry!
        # KB tools are registered directly and use fallback when KB unavailable.
        kb_tools = KBTools(repo_path, kb_orchestrator=real_kb)
        kb_tools = KBTools(repo_path, kb_orchestrator=None)  # Uses grep/AST fallback
    """

    # Semantic Search Methods
    def search_by_natural_language(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search code using natural language query.

        Args:
            query: Natural language description
            top_k: Maximum results to return

        Returns:
            List of matching code elements with metadata
        """
        ...

    def find_similar_code(self, component_id: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Find code similar to a given component.

        Args:
            component_id: Reference component identifier
            top_k: Maximum similar components

        Returns:
            List of similar components with similarity scores
        """
        ...

    def detect_duplicate_code(self, similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Detect duplicate or highly similar code.

        Args:
            similarity_threshold: Minimum similarity (0.0-1.0)

        Returns:
            List of duplicate code clusters
        """
        ...

    # Pattern Detection Methods
    def detect_design_patterns(self, classes: List[Any]) -> List[Dict[str, Any]]:
        """
        Detect design patterns in code.

        Args:
            classes: List of class AST nodes or metadata

        Returns:
            List of detected patterns with locations
        """
        ...

    def detect_code_smells(self, classes: List[Any], functions: List[Any]) -> List[Dict[str, Any]]:
        """
        Detect code smells and anti-patterns.

        Args:
            classes: List of class nodes
            functions: List of function nodes

        Returns:
            List of code smells with severity
        """
        ...

    # Architecture Analysis Methods
    def get_repository_stats(self) -> Dict[str, Any]:
        """
        Get repository statistics.

        Returns:
            Statistics about codebase (files, classes, functions, LOC, etc.)
        """
        ...

    # Query Execution (for custom queries)
    def execute_query(self, query: str, params: Dict[str, Any]) -> Any:
        """
        Execute a custom query on the knowledge base.

        Args:
            query: Query string (e.g., Cypher for Neo4j)
            params: Query parameters

        Returns:
            Query results
        """
        ...

    def execute_query_batch(self, queries: List[Dict[str, Any]]) -> List[Any]:
        """
        Execute multiple queries in batch for better performance.

        Executes all queries in a single transaction/session when possible,
        reducing connection overhead and improving throughput.

        Args:
            queries: List of query dictionaries, each containing:
                - 'query': Query string (e.g., Cypher for Neo4j)
                - 'parameters': Dict of query parameters (optional, default: {})

        Returns:
            List of query results, one per input query (preserves order)

        Example:
            >>> queries = [
            ...     {'query': 'MATCH (f:Function {name: $name}) RETURN f', 'parameters': {'name': 'foo'}},
            ...     {'query': 'MATCH (c:Class) RETURN count(c) as count', 'parameters': {}},
            ... ]
            >>> results = kb.execute_query_batch(queries)
            >>> len(results)  # Returns 2 results
            2
        """
        ...

    # High-Level Discovery Method
    def find_files_for_question(self, question: str, max_results: int = 50,
                                question_context: Dict[str, Any] = None) -> List[str]:
        """
        Find relevant files for a question using multiple KB strategies.

        Combines semantic search, pattern detection, life-of-x tracing, etc.

        Args:
            question: User question
            max_results: Maximum files to return
            question_context: Optional LLM classification context

        Returns:
            List of file paths ranked by relevance
        """
        ...

    # Life-of-X Methods
    def trace_execution_path(self, entry_point: str, max_depth: int = 10,
                            max_paths: int = 5) -> List[Dict[str, Any]]:
        """
        Trace execution paths from an entry point.

        Args:
            entry_point: Function name to start from
            max_depth: Maximum call depth
            max_paths: Maximum paths to return

        Returns:
            List of execution paths
        """
        ...

    def trace_data_flow(self, start_element: str, max_depth: int = 20) -> List[Dict[str, Any]]:
        """
        Trace data flow from a variable or function.

        Args:
            start_element: Starting variable/function name
            max_depth: Maximum trace depth

        Returns:
            List of data flow edges
        """
        ...

    def trace_request_lifecycle(self, endpoint_function: str,
                                max_depth: int = 20) -> Dict[str, Any]:
        """
        Trace HTTP request lifecycle for web applications.

        Args:
            endpoint_function: API endpoint function name
            max_depth: Maximum trace depth

        Returns:
            Request lifecycle information
        """
        ...


class LLMClientProtocol(Protocol):
    """
    Protocol for LLM clients.

    Enables swapping LLM providers (OpenAI, Anthropic, local models)
    without changing agent code.
    """

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Dict[str, Any]:
        """
        Generate completion from LLM.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            **kwargs: Provider-specific arguments

        Returns:
            Response with content, usage, model info
        """
        ...

    def generate_fast(self, prompt: str, system_prompt: str = "", **kwargs) -> Dict[str, Any]:
        """
        Generate using fast/cheap model.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            **kwargs: Provider-specific arguments

        Returns:
            Response with content, usage, model info
        """
        ...


class ToolRegistryProtocol(Protocol):
    """
    Protocol for tool registries.

    Enables different tool registry implementations.
    """

    def execute(self, tool_name: str, **params) -> Dict[str, Any]:
        """
        Execute a tool with parameters.

        Args:
            tool_name: Name of tool to execute
            **params: Tool parameters

        Returns:
            Tool execution results
        """
        ...

    def get_available_tools(self) -> Dict[str, str]:
        """
        Get all available tools with descriptions.

        Returns:
            Dictionary mapping tool names to descriptions
        """
        ...

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get tool usage metrics.

        Returns:
            Metrics for all tools
        """
        ...


class TracerProtocol(Protocol):
    """
    Protocol for tracers.

    Enables different tracing implementations (local, Langfuse, custom).
    """

    def start_session(self, session_name: str) -> str:
        """
        Start a tracing session.

        Args:
            session_name: Name of session

        Returns:
            Session ID
        """
        ...

    def end_session(self, session_id: str):
        """
        End a tracing session.

        Args:
            session_id: Session to end
        """
        ...

    def log_event(self, session_id: str, event_type: str, metadata: Dict[str, Any]):
        """
        Log a trace event.

        Args:
            session_id: Session ID
            event_type: Type of event
            metadata: Event metadata
        """
        ...



# ==============================================================================
# Agent Registry (merged from registry.py)
# ==============================================================================


class AgentRegistry:
    """
    Central registry for all knowledge agents.

    Enables:
    - Runtime registration of custom agents
    - Dynamic tool discovery
    - Agent lifecycle management
    - Consistent tool naming (always prefixed)
    """

    def __init__(self):
        self._agents: Dict[str, Any] = {}  # agent_name -> KnowledgeAgent
        self._capabilities: Dict[str, List[str]] = {}  # capability -> agent names
        self._initialized = set()

    def register(self, agent: Any) -> bool:
        """
        Register a knowledge agent.

        Args:
            agent: Agent to register (must have 'name' attribute)

        Returns:
            True if successful, False if agent name already exists
        """
        if agent.name in self._agents:
            print(f"⚠️ Agent '{agent.name}' already registered")
            return False

        # Register agent
        self._agents[agent.name] = agent

        # Register capabilities
        if hasattr(agent, 'get_capabilities'):
            for capability in agent.get_capabilities():
                if capability not in self._capabilities:
                    self._capabilities[capability] = []
                self._capabilities[capability].append(agent.name)

        print(f"✅ Registered agent: {agent.name}")
        return True

    def unregister(self, agent_name: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_name: Name of agent to remove

        Returns:
            True if successful, False if not found
        """
        if agent_name not in self._agents:
            return False

        agent = self._agents[agent_name]

        # Remove from capabilities
        if hasattr(agent, 'get_capabilities'):
            for capability in agent.get_capabilities():
                if capability in self._capabilities:
                    self._capabilities[capability].remove(agent_name)
                    if not self._capabilities[capability]:
                        del self._capabilities[capability]

        # Remove agent
        del self._agents[agent_name]
        self._initialized.discard(agent_name)

        print(f"🗑️ Unregistered agent: {agent_name}")
        return True

    def get_agent(self, agent_name: str) -> Optional[Any]:
        """Get agent by name"""
        return self._agents.get(agent_name)

    def get_agents_by_capability(self, capability: str) -> List[Any]:
        """Get all agents that provide a specific capability"""
        agent_names = self._capabilities.get(capability, [])
        return [self._agents[name] for name in agent_names if name in self._agents]

    def list_agents(self) -> List[str]:
        """Get list of all registered agent names"""
        return list(self._agents.keys())

    def list_capabilities(self) -> Dict[str, List[str]]:
        """Get all capabilities and the agents that provide them"""
        return self._capabilities.copy()

    def initialize_all(self) -> Dict[str, bool]:
        """
        Initialize all registered agents.

        Returns:
            Dictionary mapping agent names to success status
        """
        results = {}
        for name, agent in self._agents.items():
            if name not in self._initialized:
                try:
                    if hasattr(agent, 'initialize'):
                        success = agent.initialize()
                    else:
                        success = True

                    if success:
                        self._initialized.add(name)
                    results[name] = success
                except Exception as e:
                    print(f"⚠️ Failed to initialize agent '{name}': {e}")
                    results[name] = False
            else:
                results[name] = True
        return results

    def get_all_tools(self) -> Dict[str, Callable]:
        """
        Get all tools from all registered agents.

        Tool names are ALWAYS prefixed with agent name to prevent collisions:
        Format: {agent_name}_{tool_name}

        Returns:
            Dictionary mapping prefixed tool names to callables

        Raises:
            ValueError: If tool name collision detected
        """
        tools = {}

        for agent in self._agents.values():
            # Check if agent is available
            if hasattr(agent, 'is_available') and not agent.is_available():
                continue

            # Get agent tools
            if hasattr(agent, 'register_tools'):
                agent_tools = agent.register_tools()

                # ALWAYS prefix tool names to prevent collisions
                for tool_name, tool_func in agent_tools.items():
                    prefixed_name = f"{agent.name}_{tool_name}"

                    # Check for collisions
                    if prefixed_name in tools:
                        raise ValueError(
                            f"⚠️ Tool name collision: '{prefixed_name}' "
                            f"already registered by another agent"
                        )

                    tools[prefixed_name] = tool_func

        return tools

    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get all tool schemas from all registered agents.

        Returns:
            List of OpenAPI-style tool schemas
        """
        schemas = []

        for agent in self._agents.values():
            if hasattr(agent, 'is_available') and not agent.is_available():
                continue

            if hasattr(agent, 'get_tool_schemas'):
                schemas.extend(agent.get_tool_schemas())

        return schemas

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get performance metrics from all agents.

        Returns:
            Dictionary with aggregated metrics
        """
        summary = {}

        for name, agent in self._agents.items():
            available = True
            if hasattr(agent, 'is_available'):
                available = agent.is_available()

            if available and hasattr(agent, 'get_metrics'):
                summary[name] = agent.get_metrics()

        return summary


# Global agent registry instance
_global_registry = AgentRegistry()


def get_global_registry() -> AgentRegistry:
    """Get the global agent registry instance"""
    return _global_registry
