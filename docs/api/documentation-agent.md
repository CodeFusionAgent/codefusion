# Documentation Agent

**Note**: This functionality is now implemented in the DocsAgent in the clean architecture.

The DocsAgent in `cf/agents/docs.py` handles documentation analysis using LLM function calling.

## Current Implementation

See [DocsAgent API Documentation](index.md#docsagent) for the current implementation.

### Migration Guide

The previous `ReActDocumentationAgent` functionality is now available through:

```python
from cf.agents.docs import DocsAgent
from cf.configs.config_mgr import CfConfig

# Initialize DocsAgent (replaces ReActDocumentationAgent)
config = CfConfig.load_from_file("cf/configs/config.yaml")
docs_agent = DocsAgent("/path/to/repository", config)

# Documentation analysis
result = docs_agent.analyze("analyze project documentation and README files")
```

The DocsAgent provides enhanced capabilities with LLM function calling:
- README analysis and quality assessment
- Documentation completeness evaluation
- API documentation parsing
- Usage example extraction
- Documentation pattern recognition

For complete documentation, see the [main API index](index.md).