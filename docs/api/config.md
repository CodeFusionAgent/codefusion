# Configuration

::: cf.config.CfConfig

::: cf.core.react_config.ReActConfig

The CodeFusion framework provides comprehensive configuration options for performance tuning, LLM integration, and behavioral customization.

## Global Configuration

### Basic Configuration

```python
from cf.config import CfConfig

# Default configuration
config = CfConfig()

# Load from file
config = CfConfig.from_yaml("config/my_config.yaml")
config = CfConfig.from_json("config/my_config.json")
```

### Configuration File Example

```yaml
# config.yaml
llm:
  model: "gpt-4"
  api_key: "your-api-key"
  max_tokens: 1500
  temperature: 0.3

react:
  max_iterations: 25
  iteration_timeout: 45.0
  total_timeout: 900.0
  cache_enabled: true
  cache_max_size: 1000

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## ReAct Configuration

### Performance Profiles

```python
from cf.core.react_config import ReActConfig

# Fast analysis
fast_config = ReActConfig(
    max_iterations=10,
    iteration_timeout=15.0,
    total_timeout=300.0
)

# Balanced analysis
balanced_config = ReActConfig(
    max_iterations=20,
    iteration_timeout=30.0,
    total_timeout=600.0
)

# Thorough analysis
thorough_config = ReActConfig(
    max_iterations=50,
    iteration_timeout=60.0,
    total_timeout=1800.0
)
```

### Environment Variables

```bash
# ReAct Loop Configuration
export CF_REACT_MAX_ITERATIONS=25
export CF_REACT_ITERATION_TIMEOUT=45.0
export CF_REACT_TOTAL_TIMEOUT=900.0

# Caching Configuration
export CF_REACT_CACHE_ENABLED=true
export CF_REACT_CACHE_MAX_SIZE=1000
export CF_REACT_CACHE_TTL=3600

# LLM Configuration
export CF_LLM_MODEL=gpt-4
export CF_LLM_API_KEY=your-api-key
export CF_LLM_MAX_TOKENS=1500
export CF_LLM_TEMPERATURE=0.3
```

## Usage Examples

### Custom Configuration

```python
# Create custom configuration
config = CfConfig(
    llm_model="claude-3-sonnet-20240229",
    llm_api_key="your-anthropic-key",
    cache_enabled=True,
    verbose_logging=True
)

# Use with agents
from cf.agents.react_supervisor_agent import ReActSupervisorAgent
supervisor = ReActSupervisorAgent(repo, config)
```

### Runtime Configuration Updates

```python
# Update configuration at runtime
config.llm_model = "gpt-4-turbo"
config.cache_max_size = 2000

# Apply to existing agents
agent.update_config(config)
```

For complete configuration options, see the [source code](../../cf/config.py).