# ReAct Agent Base Class

**Note**: The ReAct agent foundation is now implemented in the BaseAgent class in the clean architecture.

The BaseAgent in `cf/agents/base.py` provides the foundation for all agents using common functionality patterns.

## Current Implementation

See [BaseAgent API Documentation](index.md#baseagent) for the current implementation.

## Overview

The BaseAgent provides common functionality for all agents:

- **LLM Integration**: Unified interface to LLM providers
- **Tool Registry Access**: Centralized tool management
- **Logging and Tracing**: Progress tracking and debugging
- **Configuration Management**: YAML config and environment variables
- **Error Handling**: Robust error recovery patterns

## Migration Guide

The previous `ReActAgent` functionality is now available through `BaseAgent`:

```python
from cf.agents.base import BaseAgent
from cf.configs.config_mgr import CfConfig

# BaseAgent is extended by all specific agents
from cf.agents.code import CodeAgent
from cf.agents.supervisor import SupervisorAgent

# Initialize any agent (they all extend BaseAgent)
config = CfConfig.load_from_file("cf/configs/config.yaml")
code_agent = CodeAgent("/path/to/repository", config)

# All agents inherit BaseAgent functionality:
# - call_llm() for LLM interaction
# - get_tool_registry() for tool access
# - log_action() for progress tracking
```

## Core Patterns

The BaseAgent implements these core patterns that all agents inherit:

### LLM Integration Pattern
```python
# All agents can call LLM through BaseAgent
result = agent.call_llm("Analyze this code pattern")
```

### Tool Registry Pattern
```python
# All agents have access to tools through BaseAgent
registry = agent.get_tool_registry()
schemas = registry.get_all_schemas()
```

### Logging Pattern
```python
# All agents can log actions through BaseAgent
agent.log_action("Starting code analysis")
```

For complete documentation, see the [main API index](index.md).