# Codebase Agent

**Note**: This functionality has been integrated into the CodeAgent in the clean architecture.

The CodeAgent in `cf/agents/code.py` now handles comprehensive codebase analysis using LLM function calling.

## Current Implementation

See [CodeAgent API Documentation](index.md#codeagent) for the current implementation.

### Migration Guide

The previous `ReActCodebaseAgent` functionality is now available through:

```python
from cf.agents.code import CodeAgent
from cf.configs.config_mgr import CfConfig

# Initialize CodeAgent (replaces ReActCodebaseAgent)
config = CfConfig.load_from_file("cf/configs/config.yaml")
code_agent = CodeAgent("/path/to/repository", config)

# Comprehensive codebase analysis
result = code_agent.analyze("analyze entire codebase structure and patterns")
```

The CodeAgent provides the same capabilities with improved LLM function calling:
- Source code analysis
- Pattern detection  
- Code quality assessment
- Dependency mapping
- Architecture exploration

For complete documentation, see the [main API index](index.md).