"""
Pluggable Knowledge Base Agent Architecture

Enables modular experimentation and A/B testing by allowing:
- Runtime registration of custom agents
- Swappable analysis strategies
- Metric-based comparisons

Design goal: Answer questions like "Does AST help/hinder certain queries?"
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """Standard result format for all agents"""
    success: bool
    data: Any
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class KnowledgeAgent(ABC):
    """
    Base class for pluggable knowledge agents.

    Agents can contribute to the knowledge base by:
    - Providing specialized query capabilities
    - Adding new analysis layers
    - Implementing custom search strategies

    This enables A/B testing: "Does AST help/hinder certain queries?"
    """

    def __init__(self, name: str, config: Dict[str, Any] = None):
        """
        Initialize knowledge agent.

        Args:
            name: Unique agent identifier
            config: Agent-specific configuration
        """
        self.name = name
        self.config = config or {}
        self.enabled = config.get('enabled', True) if config else True
        self._metrics = {
            'calls': 0,
            'tokens': 0,
            'time': 0.0,
            'errors': 0
        }

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get list of capabilities this agent provides.

        Returns:
            List of capability identifiers (e.g., 'semantic_search', 'pattern_detection')
        """
        pass

    @abstractmethod
    def register_tools(self) -> Dict[str, Callable]:
        """
        Register tools that this agent provides.

        Returns:
            Dictionary mapping tool names to callable functions
        """
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get OpenAPI-style schemas for tools (for LLM function calling).

        Returns:
            List of tool schemas
        """
        return []

    def initialize(self) -> bool:
        """
        Initialize agent (build indexes, load models, etc.).

        Returns:
            True if successful, False otherwise
        """
        return True

    def is_available(self) -> bool:
        """Check if agent is available and ready"""
        return self.enabled

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get agent performance metrics.

        Returns:
            Dictionary with metrics (calls, tokens, time, etc.)
        """
        return self._metrics.copy()

    def _record_call(self, tokens: int = 0, time_taken: float = 0.0, error: bool = False):
        """
        Record a tool call for metrics.

        Args:
            tokens: Number of tokens used
            time_taken: Time taken in seconds
            error: Whether an error occurred
        """
        self._metrics['calls'] += 1
        self._metrics['tokens'] += tokens
        self._metrics['time'] += time_taken
        if error:
            self._metrics['errors'] += 1


class AnalysisStrategy(ABC):
    """
    Base class for different analysis strategies.

    Enables A/B testing different approaches:
    - AST-based vs. LLM-based pattern detection
    - Graph queries vs. semantic search
    - Different embedding models
    """

    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    def analyze(self, input_data: Any, **kwargs) -> AgentResult:
        """
        Perform analysis.

        Args:
            input_data: Data to analyze
            **kwargs: Strategy-specific parameters

        Returns:
            AgentResult with analysis results
        """
        pass

    def get_cost_estimate(self, input_data: Any) -> float:
        """
        Estimate cost of analysis (in dollars).

        Returns:
            Estimated cost
        """
        return 0.0


class AgentRegistry:
    """
    Central registry for all knowledge agents.

    Enables:
    - Runtime registration of custom agents
    - Dynamic tool discovery
    - Agent lifecycle management
    """

    def __init__(self):
        self._agents: Dict[str, KnowledgeAgent] = {}
        self._capabilities: Dict[str, List[str]] = {}  # capability -> agent names
        self._initialized = set()

    def register(self, agent: KnowledgeAgent) -> bool:
        """
        Register a knowledge agent.

        Args:
            agent: Agent to register

        Returns:
            True if successful, False if agent name already exists
        """
        if agent.name in self._agents:
            print(f"  Agent '{agent.name}' already registered")
            return False

        # Register agent
        self._agents[agent.name] = agent

        # Register capabilities
        for capability in agent.get_capabilities():
            if capability not in self._capabilities:
                self._capabilities[capability] = []
            self._capabilities[capability].append(agent.name)

        print(f" Registered agent: {agent.name}")
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
        for capability in agent.get_capabilities():
            if capability in self._capabilities:
                self._capabilities[capability].remove(agent_name)
                if not self._capabilities[capability]:
                    del self._capabilities[capability]

        # Remove agent
        del self._agents[agent_name]
        self._initialized.discard(agent_name)

        print(f" Unregistered agent: {agent_name}")
        return True

    def get_agent(self, agent_name: str) -> Optional[KnowledgeAgent]:
        """Get agent by name"""
        return self._agents.get(agent_name)

    def get_agents_by_capability(self, capability: str) -> List[KnowledgeAgent]:
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
                    success = agent.initialize()
                    if success:
                        self._initialized.add(name)
                    results[name] = success
                except Exception as e:
                    print(f"  Failed to initialize agent '{name}': {e}")
                    results[name] = False
            else:
                results[name] = True
        return results

    def get_all_tools(self) -> Dict[str, Callable]:
        """
        Get all tools from all registered agents.

        Returns:
            Dictionary mapping tool names to callables
        """
        tools = {}
        for agent in self._agents.values():
            if agent.is_available():
                agent_tools = agent.register_tools()
                # Prefix tool names with agent name to avoid conflicts
                # Format: agentname_toolname
                for tool_name, tool_func in agent_tools.items():
                    prefixed_name = f"{agent.name}_{tool_name}" if '_' not in tool_name else tool_name
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
            if agent.is_available():
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
            if agent.is_available():
                summary[name] = agent.get_metrics()
        return summary


# Global agent registry instance
_global_registry = AgentRegistry()


def get_global_registry() -> AgentRegistry:
    """Get the global agent registry"""
    return _global_registry
