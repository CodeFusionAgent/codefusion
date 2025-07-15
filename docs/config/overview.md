# Configuration Overview

CodeFusion offers flexible configuration options to customize its behavior for different environments, use cases, and project requirements.

## Configuration Architecture

CodeFusion uses a hierarchical configuration system that allows you to:

- Set defaults through built-in configuration
- Override settings with configuration files
- Fine-tune with environment variables
- Adjust specific options via command-line arguments

## Configuration Hierarchy

Settings are applied in order of precedence (highest to lowest):

1. **Command-line arguments** (highest priority)
2. **Configuration files** (specified with `--config`)
3. **Environment variables**
4. **Default values** (lowest priority)

This hierarchy allows you to maintain base configurations while making environment-specific or task-specific adjustments.

## Configuration Methods

### 1. Configuration Files

The primary configuration method using YAML files:

```bash
cf --config /path/to/config.yaml index /path/to/repo
```

### 2. Environment Variables

Override specific settings without modifying configuration files:

```bash
export OPENAI_API_KEY="your-api-key"
export NEO4J_PASSWORD="password"
cf index /path/to/repo
```

### 3. Command-Line Options

Quick adjustments for specific commands:

```bash
cf --verbose query --strategy plan_act "How does authentication work?"
```

## Core Configuration Areas

### LLM Configuration

Control which language models to use and how to connect to them:

```yaml
llm_model: "gpt-4"
llm_api_key: null  # Use environment variable
llm_base_url: null  # Use default provider endpoint
```

### Knowledge Base Configuration

Choose and configure the storage backend for code analysis:

```yaml
kb_type: "neo4j"  # Options: "vector", "neo4j", "text"
kb_path: "./kb"
```

### Exploration Strategy

Select how CodeFusion analyzes and explores your codebase:

```yaml
exploration_strategy: "react"  # Options: "react", "plan_act", "sense_act"
max_exploration_depth: 5
```

### File Filtering

Control which files and directories to analyze:

```yaml
excluded_dirs:
  - ".git"
  - "node_modules"
  - "__pycache__"

excluded_extensions:
  - ".pyc"
  - ".log"
  - ".env"

max_file_size: 1048576  # 1MB in bytes
```

## Configuration Patterns

### Development vs Production

**Development Configuration:**
- Fast analysis with lightweight models
- Limited exploration depth
- Aggressive file filtering

**Production Configuration:**
- Comprehensive analysis with advanced models
- Deep exploration
- Minimal filtering for thorough coverage

### Project-Specific Configurations

**Python Projects:**
```yaml
excluded_dirs:
  - ".git"
  - "__pycache__"
  - ".pytest_cache"
  - "venv"
  - ".venv"

excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
```

**JavaScript Projects:**
```yaml
excluded_dirs:
  - ".git"
  - "node_modules"
  - "dist"
  - "build"
  - ".next"

excluded_extensions:
  - ".map"
  - ".min.js"
  - ".bundle.js"
```

## Configuration Validation

CodeFusion validates configuration files at startup:

```bash
# Test configuration validity
cf --config my-config.yaml stats
```

Common validation checks:
- YAML syntax correctness
- Required fields for selected knowledge base type
- Valid strategy names
- Numeric ranges for depth and size limits

## Configuration Templates

CodeFusion provides several built-in configuration templates:

- **Default**: Balanced settings for general use
- **Fast**: Optimized for quick analysis
- **Thorough**: Comprehensive analysis for complex projects
- **Memory-efficient**: Minimal resource usage
- **Large-repo**: Optimized for repositories with 10k+ files

## Environment-Specific Settings

### Local Development

```yaml
llm_model: "gpt-3.5-turbo"
kb_type: "vector"
exploration_strategy: "react"
max_exploration_depth: 3
```

### CI/CD Pipelines

```yaml
llm_model: "gpt-4"
kb_type: "text"  # Minimal dependencies
exploration_strategy: "plan_act"
max_exploration_depth: 5
```

### Production Analysis

```yaml
llm_model: "gpt-4"
kb_type: "neo4j"
exploration_strategy: "sense_act"
max_exploration_depth: 10
```

## Security Considerations

### API Key Management

- Never store API keys in configuration files
- Use environment variables or secure key management
- Rotate keys regularly

### Database Security

- Secure Neo4j instances in production
- Use proper authentication and network restrictions
- Enable encryption for sensitive codebases

## Performance Tuning

### Memory Optimization

```yaml
max_file_size: 524288  # 512KB
kb_type: "text"        # Minimal memory usage
```

### Speed Optimization

```yaml
exploration_strategy: "react"  # Fastest strategy
max_exploration_depth: 3       # Shallow exploration
```

### Quality Optimization

```yaml
llm_model: "gpt-4"           # Best analysis quality
exploration_strategy: "sense_act"  # Most thorough
max_exploration_depth: 15    # Deep exploration
```

## Configuration Best Practices

1. **Start with defaults** and adjust incrementally
2. **Use version control** for configuration files
3. **Document environment-specific** changes
4. **Test configurations** before production use
5. **Monitor resource usage** and adjust accordingly
6. **Keep sensitive data** in environment variables
7. **Use meaningful file names** for different configurations

## Troubleshooting Configuration

### Common Issues

**Configuration not found:**
```bash
# Verify file path
ls -la /path/to/config.yaml
```

**YAML syntax errors:**
```bash
# Validate YAML syntax
python3.11 -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

**Missing dependencies:**
```bash
# Check required packages
pip list | grep -E "(neo4j|faiss|sentence-transformers)"
```

### Debug Mode

Enable verbose configuration loading:

```bash
cf --verbose --config debug-config.yaml stats
```

## Next Steps

- Learn about specific [configuration options](reference.md)
- Explore [exploration strategies](strategies.md) in detail
- See [configuration examples](../usage/examples.md) for different scenarios
- Check the [CLI reference](../reference/cli.md) for command-line options