# Configuration

The CodeFusion framework provides comprehensive configuration options for performance tuning, LLM integration, and behavioral customization through the clean `cf/configs/` module.

## Configuration Management

### CfConfig Class

The configuration is managed by the `CfConfig` class in `cf/configs/config_mgr.py`:

```python
from cf.configs.config_mgr import CfConfig

# Load configuration from YAML file
config = CfConfig.load_from_file("cf/configs/config.yaml")

# Access configuration values
llm_model = config.llm.model
api_key = config.llm.api_key
max_tokens = config.llm.max_tokens
```

### Configuration File Structure

The main configuration file is `cf/configs/config.yaml`:

```yaml
# LLM Configuration
llm:
  model: "gpt-4o"
  api_key: "your-openai-api-key"  # Or use OPENAI_API_KEY env var
  max_tokens: 1000
  temperature: 0.7
  provider: "openai"

# Agent Configuration
agents:
  supervisor:
    enabled: true
    max_agents: 4
    timeout: 300
  
  code:
    enabled: true
    max_iterations: 20
    languages: ["python", "javascript", "typescript", "java"]
    
  documentation:
    enabled: true
    file_types: [".md", ".rst", ".txt"]
    
  web:
    enabled: true
    max_results: 10

# Tool Configuration
tools:
  registry:
    enabled: true
    max_tools: 50
  
  caching:
    enabled: true
    ttl: 3600
    max_size: 1000

# Logging Configuration
logging:
  level: "INFO"
  verbose: true
  file_output: false
```

## Environment Variables

Configuration can be overridden with environment variables:

```bash
# LLM Configuration
export OPENAI_API_KEY="your-openai-api-key"
export CF_LLM_MODEL="gpt-4o"
export CF_LLM_MAX_TOKENS=1000
export CF_LLM_TEMPERATURE=0.7

# Agent Configuration
export CF_AGENT_MAX_ITERATIONS=20
export CF_AGENT_TIMEOUT=300

# Logging Configuration
export CF_LOG_LEVEL="DEBUG"
export CF_VERBOSE_LOGGING=true
```

## Configuration Examples

### Basic Setup

```python
from cf.configs.config_mgr import CfConfig

# Load default configuration
config = CfConfig.load_from_file("cf/configs/config.yaml")

# Use with agents
from cf.agents.supervisor import SupervisorAgent
supervisor = SupervisorAgent("/path/to/repo", config)
```

### Custom Configuration

```python
# Create custom config
config = CfConfig()
config.llm.model = "gpt-4"
config.llm.max_tokens = 2000
config.llm.temperature = 0.5

# Override with environment variables
config.load_environment_overrides()
```

### Configuration Validation

```python
# Validate configuration
try:
    config = CfConfig.load_from_file("cf/configs/config.yaml")
    config.validate()
    print("Configuration is valid")
except Exception as e:
    print(f"Configuration error: {e}")
```

## LLM Provider Configuration

### OpenAI Configuration

```yaml
llm:
  provider: "openai"
  model: "gpt-4o"
  api_key: "sk-..."
  max_tokens: 1000
  temperature: 0.7
```

### Anthropic Configuration

```yaml
llm:
  provider: "anthropic" 
  model: "claude-3-sonnet-20240229"
  api_key: "sk-ant-..."
  max_tokens: 1000
  temperature: 0.7
```

### Local LLM Configuration

```yaml
llm:
  provider: "ollama"
  model: "llama2"
  base_url: "http://localhost:11434"
  max_tokens: 1000
  temperature: 0.7
```

## Performance Configuration

### Caching Settings

```yaml
tools:
  caching:
    enabled: true
    ttl: 3600  # 1 hour
    max_size: 1000  # Maximum cached items
    storage_path: "./cf_cache"
```

### Agent Performance

```yaml
agents:
  code:
    max_iterations: 20  # Maximum ReAct iterations
    timeout: 300  # 5 minutes
    parallel_tools: true
    
  supervisor:
    max_agents: 4  # Maximum concurrent agents
    synthesis_timeout: 60  # LLM synthesis timeout
```

### Tool Registry Settings

```yaml
tools:
  registry:
    enabled: true
    max_tools: 50
    schema_validation: true
    error_recovery: true
```

## Migration from Legacy Configuration

If migrating from the old configuration system:

```python
# Old way (no longer available)
# from cf.config import CfConfig

# New way (clean architecture)
from cf.configs.config_mgr import CfConfig

# Load configuration
config = CfConfig.load_from_file("cf/configs/config.yaml")
```

## Configuration Best Practices

1. **Use Environment Variables for Secrets**: Never commit API keys to configuration files
2. **Validate Configuration**: Always validate config before using
3. **Use Appropriate Timeouts**: Set reasonable timeouts for your use case
4. **Enable Caching**: Use caching for better performance
5. **Monitor Usage**: Track LLM token usage and costs

## Troubleshooting

### Common Configuration Issues

**API Key Issues**:
```bash
# Check if API key is set
echo $OPENAI_API_KEY

# Validate API key
python -c "from cf.configs.config_mgr import CfConfig; config = CfConfig.load_from_file('cf/configs/config.yaml'); print('Config loaded successfully')"
```

**Configuration File Not Found**:
```python
import os
config_path = "cf/configs/config.yaml"
if os.path.exists(config_path):
    print(f"Config file found: {config_path}")
else:
    print(f"Config file not found: {config_path}")
```

**LLM Provider Issues**:
```python
# Test LLM connectivity
from cf.llm.client import get_llm_client
client = get_llm_client()
if client:
    print("LLM client initialized successfully")
else:
    print("LLM client initialization failed")
```

For complete documentation, see the [main API index](index.md).