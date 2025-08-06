# WebAgent API

The `WebAgent` provides intelligent web search capabilities with LLM-powered query generation and seamless integration of external knowledge into technical responses.

## Overview

The WebAgent enables:
- **LLM-Powered Query Generation**: Intelligent search query crafting based on questions and codebase context
- **External Knowledge Integration**: Web search results seamlessly woven into main narrative responses
- **Relevance Filtering**: AI-driven filtering of search results for technical accuracy
- **Best Practices Enhancement**: Industry documentation and tutorials automatically included
- **No Configuration Required**: Web search automatically enabled when beneficial

## Current Implementation

See [WebAgent API Documentation](index.md#webagent) for the current implementation.

## Class Definition

```python
from cf.agents.web import WebAgent
```

## Constructor

```python
WebAgent(repo_path: str, config: CfConfig)
```

**Parameters:**
- `repo_path` (str): Path to the repository for context-aware search
- `config` (CfConfig): Configuration with web search and LLM settings

**Example:**
```python
from cf.agents.web import WebAgent
from cf.configs.config_mgr import CfConfig

# Initialize configuration and WebAgent
config = CfConfig.load_from_file("cf/configs/config.yaml")
web_agent = WebAgent("/path/to/repository", config)

# Perform web search analysis
result = web_agent.analyze("Search for FastAPI routing best practices")
print(result['web_insights'])
```

## Key Methods

### analyze(goal: str)

Performs web search analysis based on the goal.

**Parameters:**
- `goal` (str): The search objective or question

**Returns:**
- `dict`: Analysis results with web insights

**Example:**
```python
result = web_agent.analyze("Find best practices for FastAPI authentication")
```

### generate_search_queries(question: str)

Generates intelligent search queries using LLM.

**Parameters:**
- `question` (str): Original question or topic

**Returns:**
- `list`: Generated search queries

### process_web_results(results: list)

Processes and filters web search results.

**Parameters:**
- `results` (list): Raw web search results

**Returns:**
- `dict`: Processed and filtered results

## Integration with Multi-Agent System

The WebAgent integrates seamlessly with the SupervisorAgent:

```python
from cf.agents.supervisor import SupervisorAgent

# SupervisorAgent automatically uses WebAgent when beneficial
supervisor = SupervisorAgent("/path/to/repo", config)
result = supervisor.analyze("How does FastAPI handle authentication?")

# WebAgent results are automatically integrated into the final narrative
```

## Web Search Tools

The WebAgent uses the following tools via LLM function calling:

- **web_search**: External knowledge search via DuckDuckGo API
- **search_documentation**: Find relevant documentation online
- **extract_best_practices**: Identify industry best practices

For complete documentation, see the [main API index](index.md).