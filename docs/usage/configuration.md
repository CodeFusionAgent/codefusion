# Configuration

CodeFusion provides flexible configuration options to customize its behavior for different use cases and environments.

## Configuration Methods

### 1. Configuration Files

The primary way to configure CodeFusion is through YAML configuration files:

```bash
cf --config /path/to/config.yaml index /path/to/repo
```

### 2. Environment Variables

Override specific settings using environment variables:

```bash
export OPENAI_API_KEY="your-api-key"
export NEO4J_PASSWORD="password"
cf index /path/to/repo
```

### 3. Command Line Options

Some settings can be overridden via command line:

```bash
cf --verbose index --strategy plan_act /path/to/repo
```

## Configuration Hierarchy

Settings are applied in order of precedence (highest to lowest):

1. **Command line options** (highest priority)
2. **Configuration file** (specified with `--config`)
3. **Environment variables**
4. **Default values** (lowest priority)

## Basic Configuration

### Default Configuration

```yaml
# config/default/config.yaml
repo_path: null
output_dir: "./output"

# LLM settings
llm_model: "gpt-3.5-turbo"
llm_api_key: null
llm_base_url: null

# Knowledge base settings
kb_type: "vector"  # "text", "neo4j", or "vector"
kb_path: "./kb"
embedding_model: "all-MiniLM-L6-v2"

# Neo4j settings (when kb_type: "neo4j")
neo4j_uri: null
neo4j_user: null
neo4j_password: null

# File filtering
max_file_size: 1048576  # 1MB
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "venv"
excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".so"
  - ".dll"
  - ".exe"
  - ".env"

# Exploration settings
exploration_strategy: "react"  # "react", "plan_act", "sense_act"
max_exploration_depth: 5
```

### Custom Configuration Example

```yaml
# my-config.yaml
# Repository settings
repo_path: "/path/to/my/project"
output_dir: "/tmp/codefusion-output"

# Use GPT-4 for better analysis
llm_model: "gpt-4"
llm_api_key: null  # Will use OPENAI_API_KEY env var

# Use Neo4j for complex relationship analysis
kb_type: "neo4j"
neo4j_uri: "bolt://localhost:7687"
neo4j_user: "neo4j"
neo4j_password: "password"

# Custom file filtering for JavaScript project
excluded_dirs:
  - ".git"
  - "node_modules"
  - "dist"
  - "build"
  - ".next"
  - "coverage"
excluded_extensions:
  - ".map"
  - ".d.ts"
  - ".min.js"
  - ".bundle.js"

# Use plan-act strategy for systematic analysis
exploration_strategy: "plan_act"
max_exploration_depth: 8
```

## LLM Configuration

### OpenAI Configuration

```yaml
llm_model: "gpt-4"
llm_api_key: null  # Set via OPENAI_API_KEY
llm_base_url: null  # Use default OpenAI endpoint
```

```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

### Anthropic Configuration

```yaml
llm_model: "claude-3-sonnet-20240229"
llm_api_key: null  # Set via ANTHROPIC_API_KEY
```

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
```

### Azure OpenAI Configuration

```yaml
llm_model: "gpt-4"
llm_base_url: "https://your-resource.openai.azure.com/"
llm_api_key: null  # Set via AZURE_OPENAI_API_KEY
```

```bash
export AZURE_OPENAI_API_KEY="your-azure-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
```

### Local/Self-hosted Models

```yaml
llm_model: "local-model"
llm_base_url: "http://localhost:8000/v1"
llm_api_key: "not-required"
```

## Knowledge Base Configuration

### Vector Database (Default)

```yaml
kb_type: "vector"
kb_path: "./vector_kb"
embedding_model: "all-MiniLM-L6-v2"  # Fast, good quality

# Alternative models:
# embedding_model: "all-mpnet-base-v2"      # Higher quality, slower
# embedding_model: "BAAI/bge-small-en-v1.5" # Optimized for code
```

### Neo4j Graph Database

```yaml
kb_type: "neo4j"
kb_path: "./neo4j_kb"
neo4j_uri: "bolt://localhost:7687"
neo4j_user: "neo4j"
neo4j_password: "password"

# For Neo4j Cloud/AuraDB
# neo4j_uri: "neo4j+s://your-instance.databases.neo4j.io"
```

### Text-based (Simple)

```yaml
kb_type: "text"
kb_path: "./text_kb"
# Fastest option, limited search capabilities
```

## File Filtering Configuration

### Directory Exclusions

```yaml
excluded_dirs:
  # Version control
  - ".git"
  - ".svn"
  - ".hg"
  
  # Build artifacts
  - "dist"
  - "build"
  - "out"
  - "target"
  
  # Dependencies
  - "node_modules"
  - "vendor"
  - "venv"
  - ".venv"
  
  # IDE files
  - ".vscode"
  - ".idea"
  - ".vs"
  
  # Temporary files
  - "tmp"
  - "temp"
  - "__pycache__"
  - ".pytest_cache"
```

### File Extension Exclusions

```yaml
excluded_extensions:
  # Compiled files
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".class"
  - ".o"
  - ".so"
  - ".dll"
  - ".exe"
  
  # Archives
  - ".zip"
  - ".tar.gz"
  - ".rar"
  
  # Media files
  - ".jpg"
  - ".png"
  - ".gif"
  - ".mp4"
  - ".mp3"
  
  # Documentation
  - ".pdf"
  - ".doc"
  - ".docx"
  
  # Environment files
  - ".env"
  - ".env.local"
```

### File Size Limits

```yaml
max_file_size: 1048576  # 1MB in bytes

# For large codebases with big files
# max_file_size: 5242880  # 5MB

# For repositories with many small files
# max_file_size: 524288   # 512KB
```

## Exploration Strategy Configuration

### ReAct Strategy

```yaml
exploration_strategy: "react"
max_exploration_depth: 5

# ReAct-specific settings (if available)
react_settings:
  reasoning_steps: 3
  action_timeout: 30
  backtrack_on_failure: true
```

### Plan-then-Act Strategy

```yaml
exploration_strategy: "plan_act"
max_exploration_depth: 8

# Plan-Act specific settings
plan_act_settings:
  planning_depth: 3
  execution_parallel: false
  plan_validation: true
```

### Sense-then-Act Strategy

```yaml
exploration_strategy: "sense_act"
max_exploration_depth: 10

# Sense-Act specific settings
sense_act_settings:
  observation_cycles: 5
  adaptation_threshold: 0.7
  exploration_breadth: 5
```

## Environment-Specific Configurations

### Development Environment

```yaml
# dev-config.yaml
llm_model: "gpt-3.5-turbo"  # Faster, cheaper
kb_type: "vector"           # Quick setup
exploration_strategy: "react"
max_exploration_depth: 3    # Quick exploration
excluded_dirs:
  - ".git"
  - "node_modules"
  - "__pycache__"
```

### Production Analysis

```yaml
# prod-config.yaml
llm_model: "gpt-4"          # Best quality
kb_type: "neo4j"           # Advanced analysis
exploration_strategy: "plan_act"
max_exploration_depth: 10   # Thorough analysis
max_file_size: 5242880      # Handle larger files
```

### Large Codebase Configuration

```yaml
# large-repo-config.yaml
kb_type: "neo4j"
exploration_strategy: "sense_act"
max_exploration_depth: 15
max_file_size: 2097152  # 2MB

# More aggressive filtering
excluded_dirs:
  - ".git"
  - "node_modules"
  - "vendor"
  - "third_party"
  - "external"
  - "deps"
  - "build"
  - "dist"
  - "out"
  - "target"
  - "bin"
  - "obj"
  - "logs"
  - "tmp"
  - "temp"
  - "cache"
  - ".cache"
  - "__pycache__"
  - ".pytest_cache"
  - ".mypy_cache"
  - "coverage"
  - ".coverage"
  - "htmlcov"

excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".so"
  - ".dll"
  - ".exe"
  - ".class"
  - ".jar"
  - ".war"
  - ".zip"
  - ".tar.gz"
  - ".rar"
  - ".7z"
  - ".pdf"
  - ".doc"
  - ".docx"
  - ".xls"
  - ".xlsx"
  - ".ppt"
  - ".pptx"
  - ".jpg"
  - ".jpeg"
  - ".png"
  - ".gif"
  - ".bmp"
  - ".ico"
  - ".svg"
  - ".mp3"
  - ".mp4"
  - ".avi"
  - ".mov"
  - ".wmv"
  - ".flv"
  - ".env"
  - ".env.local"
  - ".env.production"
  - ".log"
  - ".lock"
```

## Configuration Validation

### Validate Configuration

```bash
# Test configuration
cf --config my-config.yaml stats

# Validate YAML syntax
python3.11 -c "
import yaml
with open('my-config.yaml') as f:
    config = yaml.safe_load(f)
    print('Configuration is valid')
"
```

### Common Configuration Errors

**Invalid YAML syntax:**
```bash
# Check for syntax errors
yamllint my-config.yaml
```

**Missing required fields:**
```yaml
# This will cause errors:
kb_type: "neo4j"
# Missing: neo4j_uri, neo4j_user, neo4j_password
```

**Invalid values:**
```yaml
# These will cause validation errors:
kb_type: "invalid_type"
exploration_strategy: "unknown_strategy"
max_exploration_depth: -1
```

## Advanced Configuration

### Custom Artifact Directories

```yaml
# Specify custom artifact location
output_dir: "/custom/path/artifacts"
kb_path: "/custom/path/knowledge_base"
```

### Performance Tuning

```yaml
# For high-performance analysis
max_file_size: 10485760     # 10MB
max_exploration_depth: 20
exploration_strategy: "sense_act"

# Vector DB optimization
embedding_model: "BAAI/bge-small-en-v1.5"  # Optimized for code

# Neo4j optimization
neo4j_settings:
  max_connections: 10
  connection_timeout: 30
  query_timeout: 300
```

### Debugging Configuration

```yaml
# Enable detailed logging
debug: true
verbose: true
log_level: "DEBUG"
log_file: "/tmp/codefusion-debug.log"
```

## Configuration Templates

### Python Project Template

```yaml
# python-project.yaml
llm_model: "gpt-4"
kb_type: "vector"
exploration_strategy: "react"

excluded_dirs:
  - ".git"
  - "__pycache__"
  - ".pytest_cache"
  - ".mypy_cache"
  - "venv"
  - ".venv"
  - "env"
  - ".env"
  - "dist"
  - "build"
  - "*.egg-info"

excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".so"
  - ".egg"
  - ".whl"
```

### JavaScript Project Template

```yaml
# javascript-project.yaml
llm_model: "gpt-4"
kb_type: "vector"
exploration_strategy: "react"

excluded_dirs:
  - ".git"
  - "node_modules"
  - "dist"
  - "build"
  - ".next"
  - "coverage"
  - ".nyc_output"

excluded_extensions:
  - ".map"
  - ".min.js"
  - ".min.css"
  - ".bundle.js"
  - ".chunk.js"
```

## Next Steps

- Learn about [CLI Commands](cli.md)
- See [Configuration Examples](examples.md)
- Check the [Configuration Reference](../config/reference.md)