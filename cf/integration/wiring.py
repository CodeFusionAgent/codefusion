"""
System Wiring - Component Integration

Wires together all pluggable components:
- AgentRegistry
- ToolRegistry
- StructuralKBAgent
- Tracer with plugins
- LLMTask

Provides tool-first interface (no direct pipeline access).
"""

from typing import Dict, Any, Optional

from cf.agents.registry import AgentRegistry, get_global_registry
from cf.agents.kb.structural_kb_agent import StructuralKBAgent
from cf.agents.pipelines.structural import StructuralPipeline
from cf.tools.registry import ToolRegistry
from cf.trace.tracer import Tracer
from cf.trace.langfuse_plugin import LangfusePlugin
from cf.llm.task import LlmTask
from cf.llm.client import LLMClient


def create_integrated_system(
    repo_path: str,
    config: Dict[str, Any],
    enable_langfuse: bool = False,
    langfuse_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a fully integrated CodeFusion system with all pluggable components.

    This function wires together:
    1. AgentRegistry - for runtime agent registration
    2. ToolRegistry - for unified tool access
    3. StructuralKBAgent - exposes all KB query tools
    4. Tracer - with optional Langfuse plugin
    5. LLMTask - message-based LLM interface

    IMPORTANT: Only tool_registry is exposed for external use.
    Internal components (pipeline, kb_agent) are not exposed to enforce
    tool-first design pattern.

    Args:
        repo_path: Path to repository root
        config: Configuration dictionary
        enable_langfuse: Whether to enable Langfuse tracing
        langfuse_config: Langfuse configuration (public_key, secret_key, host)

    Returns:
        Dictionary with accessible system components:
        - 'agent_registry': AgentRegistry for custom agent registration
        - 'tool_registry': ToolRegistry for executing all tools (PRIMARY INTERFACE)
        - 'tracer': Tracer for observability
        - 'llm_client': LLMClient for LLM operations
        - 'llm_task': LlmTask for conversation management
        - 'config': Configuration dictionary

    Example:
        >>> system = create_integrated_system(
        ...     repo_path="/path/to/repo",
        ...     config=load_config(),
        ...     enable_langfuse=True,
        ...     langfuse_config={
        ...         'public_key': 'pk-...',
        ...         'secret_key': 'sk-...'
        ...     }
        ... )
        >>>
        >>> # Use tools (recommended approach)
        >>> tools = system['tool_registry']
        >>> result = tools.execute('structural_kb_search_by_semantics', query="find auth code")
        >>>
        >>> # Register custom agents
        >>> registry = system['agent_registry']
        >>> registry.register(my_custom_agent)
    """
    # 1. Create Agent Registry
    agent_registry = get_global_registry()

    # 2. Create ToolRegistry with agent registry support
    tool_registry = ToolRegistry(repo_path, agent_registry=agent_registry)

    # 3. Create StructuralPipeline (KB backend) - INTERNAL USE ONLY
    pipeline = StructuralPipeline(repo_path, config)

    # 4. Create and register StructuralKBAgent
    # Agent uses pipeline through protocol interface
    kb_agent = StructuralKBAgent(kb=pipeline, config=config)
    agent_registry.register(kb_agent)

    # Initialize the KB agent
    kb_agent.initialize()

    # 5. Set up Tracer with optional Langfuse plugin
    tracer_plugins = []
    if enable_langfuse and langfuse_config:
        langfuse_plugin = LangfusePlugin(
            public_key=langfuse_config.get('public_key'),
            secret_key=langfuse_config.get('secret_key'),
            host=langfuse_config.get('host', 'https://cloud.langfuse.com'),
            enabled=True
        )
        tracer_plugins.append(langfuse_plugin)

    tracer = Tracer(
        agent_name="integrated_system",
        trace_config=config.get('trace', {}),
        plugins=tracer_plugins
    )

    # 6. Create LLM client and task interface
    llm_client = LLMClient(config.get('llm', {}))
    llm_task = LlmTask(llm_client, max_history=10)

    # Return ONLY the public interfaces
    # DO NOT expose 'pipeline' or 'kb_agent' directly - this enforces tool-first design
    return {
        'agent_registry': agent_registry,
        'tool_registry': tool_registry,     # PRIMARY INTERFACE FOR USERS
        'tracer': tracer,
        'llm_client': llm_client,
        'llm_task': llm_task,
        'config': config
    }
