"""
Agent Protocols - Interface Definitions

Defines protocols (structural subtyping interfaces) for agent dependencies.
This enables loose coupling and easier testing through dependency injection.

Using Protocol instead of ABC allows duck typing while maintaining type safety.
"""

from typing import Protocol, List, Dict, Any, Optional


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

        # Both work with StructuralKBAgent!
        agent = StructuralKBAgent(kb=real_kb, config={})
        agent = StructuralKBAgent(kb=mock_kb, config={})  # For testing
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
