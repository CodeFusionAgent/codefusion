"""
Agent Registry - Central Registration System

Manages runtime registration and discovery of knowledge agents.
Provides dynamic tool discovery with consistent naming.
"""

from typing import Dict, List, Any, Optional, Callable


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
