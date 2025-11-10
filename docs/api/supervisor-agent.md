# Supervisor Agent

The `SupervisorAgent` orchestrates multiple specialized agents to perform comprehensive codebase analysis through intelligent coordination and cross-agent synthesis.

**Current Implementation**: See [SupervisorAgent API Documentation](index.md#multi-agent-analysis) for usage examples.

## Overview

The SupervisorAgent implements a multi-agent coordination pattern:

1. **Analyzes** the question to determine which agents are needed
2. **Coordinates** parallel execution of CodeAgent, DocsAgent, and WebAgent
3. **Synthesizes** results from multiple agents using LLM
4. **Generates** unified technical narratives with comprehensive insights

## Class Definition

```python
from cf.agents.supervisor import SupervisorAgent
```

## Constructor

```python
SupervisorAgent(repo_path: str, config: CfConfig)
```

**Parameters:**
- `repo_path` (str): Path to the repository for analysis
- `config` (CfConfig): Configuration with LLM and agent settings

## Key Methods

### analyze(question: str)

Performs comprehensive multi-agent analysis.

**Parameters:**
- `question` (str): The analysis question or goal

**Returns:**
- `dict`: Complete analysis results with narrative, insights, and metadata

**Example:**
```python
from cf.agents.supervisor import SupervisorAgent
from cf.configs.config_mgr import CfConfig

# Initialize SupervisorAgent
config = CfConfig.load_from_file("cf/configs/config.yaml")
supervisor = SupervisorAgent("/path/to/repository", config)

# Perform multi-agent analysis
result = supervisor.analyze("How does FastAPI routing work?")

print(result['narrative'])
print(f"Agents consulted: {result['agents_consulted']}")
print(f"Execution time: {result['execution_time']}s")
```

## Multi-Agent Coordination

The SupervisorAgent coordinates these specialized agents:

### CodeAgent Integration
- Analyzes source code using LLM function calling
- Identifies implementation patterns and architecture
- Provides code-specific insights

### DocsAgent Integration  
- Processes documentation and README files
- Extracts usage examples and API documentation
- Provides documentation quality assessment

### WebAgent Integration
- Searches external knowledge sources
- Finds best practices and tutorials
- Integrates industry documentation

## LLM Synthesis

The SupervisorAgent uses LLM to synthesize results:

```python
# The SupervisorAgent automatically:
# 1. Collects insights from all agents
# 2. Uses LLM to generate unified narrative
# 3. Provides comprehensive technical stories
# 4. Includes confidence scores and metadata
```

## Integration Patterns

### CLI Integration
```bash
# SupervisorAgent is used automatically by the CLI
python -m cf.run.main --verbose ask /path/to/repo "How does routing work?"
```

### Programmatic Usage
```python
# Direct SupervisorAgent usage
supervisor = SupervisorAgent("/path/to/repo", config)
result = supervisor.analyze("Explain the architecture")

# Access specific insights
code_insights = result.get('code_insights', [])
docs_insights = result.get('docs_insights', [])
web_insights = result.get('web_insights', [])
```

## Performance Characteristics

- **Response Time**: 15-45 seconds depending on repository size
- **Agent Coordination**: Parallel execution where possible  
- **LLM Integration**: Uses primary LLM for synthesis
- **Caching**: Leverages semantic caching for repeated queries

For complete documentation, see the [main API index](index.md).