# LLM Integration

The CodeFusion framework provides comprehensive Language Model integration for AI-powered reasoning and analysis through the clean `cf/llm/` module.

## LLM Client

The LLM integration is handled by the unified client in `cf/llm/client.py`:

```python
from cf.llm.client import get_llm_client

# Get configured LLM client
llm_client = get_llm_client()

# Use for analysis
response = llm_client.generate("Analyze this code pattern")
```

## LLM Provider Support

The framework supports multiple LLM providers through LiteLLM:

### OpenAI Integration

```python
from cf.configs.config_mgr import CfConfig

# Configure for OpenAI
config = CfConfig()
config.llm.provider = "openai"
config.llm.model = "gpt-4o"
config.llm.api_key = "your-openai-api-key"
```

### Anthropic Integration

```python
# Configure for Anthropic
config.llm.provider = "anthropic"
config.llm.model = "claude-3-sonnet-20240229"
config.llm.api_key = "your-anthropic-api-key"
```

### Local LLM Integration

```python
# Configure for local LLM
config.llm.provider = "ollama"
config.llm.model = "llama2"
config.llm.base_url = "http://localhost:11434"
```

## LLM Function Calling

The framework supports LLM function calling for intelligent tool selection:

```python
from cf.tools.registry import ToolRegistry

# Get tool schemas for LLM function calling
registry = ToolRegistry("/path/to/repo")
schemas = registry.get_all_schemas()

# LLM can select tools based on context
tools_available = [
    "scan_directory",
    "read_file", 
    "search_files",
    "analyze_code",
    "web_search"
]
```

## LLM Configuration

### Basic Configuration

```yaml
# cf/configs/config.yaml
llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "your-api-key"
  max_tokens: 1000
  temperature: 0.7
  timeout: 30
```

### Advanced Configuration

```yaml
llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "your-api-key"
  max_tokens: 2000
  temperature: 0.5
  top_p: 0.9
  frequency_penalty: 0.0
  presence_penalty: 0.0
  timeout: 60
  retry_attempts: 3
  retry_delay: 1.0
```

## Usage Examples

### Basic LLM Usage

```python
from cf.llm.client import get_llm_client

# Initialize LLM client
llm_client = get_llm_client()

# Generate response
response = llm_client.generate(
    prompt="Explain the architecture of this system",
    max_tokens=1000
)

print(response)
```

### LLM with Function Calling

```python
from cf.agents.code import CodeAgent
from cf.configs.config_mgr import CfConfig

# CodeAgent uses LLM function calling internally
config = CfConfig.load_from_file("cf/configs/config.yaml")
code_agent = CodeAgent("/path/to/repo", config)

# LLM will intelligently select tools
result = code_agent.analyze("Find main application entry points")
```

### Multi-Agent LLM Coordination

```python
from cf.agents.supervisor import SupervisorAgent

# SupervisorAgent coordinates LLM across multiple agents
supervisor = SupervisorAgent("/path/to/repo", config)
result = supervisor.analyze("How does authentication work?")

# LLM synthesis combines insights from all agents
print(result['narrative'])
```

## LLM Integration Patterns

### Reasoning Pattern

```python
# Agents use LLM for reasoning about next actions
reasoning = llm_client.reasoning(
    context="Current repository state",
    question="What should I analyze next?",
    agent_type="code_analysis"
)
```

### Tool Selection Pattern

```python
# LLM selects optimal tools based on context
tool_selection = llm_client.function_calling(
    context="Repository analysis context",
    available_tools=tool_schemas,
    goal="Find routing implementation"
)
```

### Synthesis Pattern

```python
# LLM synthesizes results from multiple sources
narrative = llm_client.synthesize(
    question="How does FastAPI routing work?",
    code_insights=code_results,
    docs_insights=docs_results,
    web_insights=web_results
)
```

## Error Handling

### LLM Availability Checking

```python
from cf.llm.client import get_llm_client

llm_client = get_llm_client()
if llm_client and llm_client.is_available():
    # Use LLM functionality
    response = llm_client.generate(prompt)
else:
    # Fallback to non-LLM methods
    print("LLM not available, using fallback")
```

### Graceful Degradation

```python
try:
    # Try LLM function calling
    result = agent.llm_function_calling(context)
except Exception as e:
    # Fallback to hardcoded logic
    logger.warning(f"LLM function calling failed: {e}")
    result = agent.fallback_action_planning(context)
```

## Performance Optimization

### Token Usage Optimization

```python
# Configure for efficient token usage
config.llm.max_tokens = 1000  # Limit response length
config.llm.temperature = 0.3  # More focused responses
```

### Caching Integration

```python
# LLM responses are automatically cached
from cf.cache.semantic import SemanticCache

cache = SemanticCache()
# Repeated similar queries will use cached responses
```

### Parallel LLM Calls

```python
# SupervisorAgent coordinates parallel LLM usage
supervisor = SupervisorAgent("/path/to/repo", config)

# Multiple agents can use LLM simultaneously
result = supervisor.analyze("Complex multi-faceted question")
```

## Troubleshooting

### Common LLM Issues

**API Key Problems**:
```python
# Test API key validity
from cf.llm.client import get_llm_client

try:
    client = get_llm_client()
    test_response = client.generate("Hello")
    print("LLM connection successful")
except Exception as e:
    print(f"LLM connection failed: {e}")
```

**Rate Limiting**:
```python
# Configure retry behavior
config.llm.retry_attempts = 5
config.llm.retry_delay = 2.0
config.llm.timeout = 60
```

**Model Availability**:
```python
# Check if model is available
try:
    response = client.generate("test", model="gpt-4o")
except Exception as e:
    print(f"Model unavailable: {e}")
    # Fallback to different model
    response = client.generate("test", model="gpt-3.5-turbo")
```

## Migration Guide

If migrating from the old LLM system:

```python
# Old way (no longer available)
# from cf.llm.real_llm import RealLLM

# New way (clean architecture)
from cf.llm.client import get_llm_client

# Get LLM client
client = get_llm_client()
```

For complete documentation, see the [main API index](index.md).