# Configuration Reference

This page provides a complete reference for all CodeFusion configuration options.

## Configuration File Format

Configuration files use YAML format with the following structure:

```yaml
# Basic settings
repo_path: null
output_dir: "./output"

# LLM configuration
llm_model: "gpt-3.5-turbo"
llm_api_key: null
llm_base_url: null

# Knowledge base settings
kb_type: "vector"
kb_path: "./kb"

# Exploration settings
exploration_strategy: "react"
max_exploration_depth: 5

# File filtering
max_file_size: 1048576
excluded_dirs: []
excluded_extensions: []

# Additional options...
```

## Core Configuration Options

### Basic Settings

#### `repo_path`
- **Type**: String (path) or null
- **Default**: null
- **Description**: Default repository path to analyze
- **Example**: `"/path/to/my/project"`

#### `output_dir`
- **Type**: String (path)
- **Default**: `"./output"`
- **Description**: Directory for output artifacts and logs
- **Example**: `"/tmp/codefusion-artifacts"`

## LLM Configuration

### `llm_model`
- **Type**: String
- **Default**: `"gpt-3.5-turbo"`
- **Description**: Language model to use for analysis
- **Valid values**:
  - OpenAI: `"gpt-3.5-turbo"`, `"gpt-4"`, `"gpt-4-turbo"`
  - Anthropic: `"claude-3-sonnet-20240229"`, `"claude-3-opus-20240229"`
  - Local: `"local-model"` (with custom base_url)

### `llm_api_key`
- **Type**: String or null
- **Default**: null
- **Description**: API key for LLM provider (use environment variable instead)
- **Environment variable**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.
- **Security note**: Never store in configuration files

### `llm_base_url`
- **Type**: String (URL) or null
- **Default**: null
- **Description**: Custom base URL for LLM API
- **Example**: `"https://api.example.com/v1"`
- **Use cases**: Self-hosted models, Azure OpenAI, custom proxies

### `llm_temperature`
- **Type**: Float
- **Default**: 0.0
- **Range**: 0.0 to 2.0
- **Description**: Controls randomness in LLM responses
- **Usage**: Higher values for creativity, lower for consistency

### `llm_max_tokens`
- **Type**: Integer
- **Default**: 4096
- **Description**: Maximum tokens per LLM response
- **Range**: 1 to model-specific limit

## Knowledge Base Configuration

### `kb_type`
- **Type**: String
- **Default**: `"vector"`
- **Description**: Type of knowledge base to use
- **Valid values**:
  - `"vector"`: Vector/embedding-based search
  - `"neo4j"`: Graph database for relationships
  - `"text"`: Simple text-based storage

### `kb_path`
- **Type**: String (path)
- **Default**: `"./kb"`
- **Description**: Path for knowledge base storage
- **Example**: `"/data/codefusion/kb"`

### Vector Database Options

#### `embedding_model`
- **Type**: String
- **Default**: `"all-MiniLM-L6-v2"`
- **Description**: Model for generating text embeddings
- **Options**:
  - `"all-MiniLM-L6-v2"`: Fast, good quality
  - `"all-mpnet-base-v2"`: Higher quality, slower
  - `"BAAI/bge-small-en-v1.5"`: Optimized for code

#### `vector_dimension`
- **Type**: Integer
- **Default**: 384 (for all-MiniLM-L6-v2)
- **Description**: Embedding vector dimensions
- **Note**: Must match embedding model dimensions

#### `similarity_threshold`
- **Type**: Float
- **Default**: 0.7
- **Range**: 0.0 to 1.0
- **Description**: Minimum similarity score for relevant results

### Neo4j Configuration

#### `neo4j_uri`
- **Type**: String (URI)
- **Default**: null
- **Description**: Neo4j database connection URI
- **Examples**:
  - Local: `"bolt://localhost:7687"`
  - Cloud: `"neo4j+s://instance.databases.neo4j.io"`

#### `neo4j_user`
- **Type**: String
- **Default**: null
- **Description**: Neo4j username
- **Environment variable**: `NEO4J_USER`

#### `neo4j_password`
- **Type**: String
- **Default**: null
- **Description**: Neo4j password
- **Environment variable**: `NEO4J_PASSWORD`
- **Security note**: Use environment variable

#### `neo4j_database`
- **Type**: String
- **Default**: `"neo4j"`
- **Description**: Neo4j database name
- **Note**: Use default for single-database instances

## Exploration Configuration

### `exploration_strategy`
- **Type**: String
- **Default**: `"react"`
- **Description**: Strategy for code exploration
- **Valid values**:
  - `"react"`: Reasoning + Acting (balanced)
  - `"plan_act"`: Plan then Act (systematic)
  - `"sense_act"`: Sense then Act (observational)

### `max_exploration_depth`
- **Type**: Integer
- **Default**: 5
- **Range**: 1 to 50
- **Description**: Maximum depth for exploration steps
- **Guidelines**:
  - 1-3: Quick overview
  - 5-8: Standard analysis
  - 10+: Deep exploration

### Strategy-Specific Options

#### ReAct Strategy

```yaml
react_settings:
  reasoning_steps: 3
  action_timeout: 30
  backtrack_on_failure: true
  max_iterations: 10
```

#### Plan-Act Strategy

```yaml
plan_act_settings:
  planning_depth: 3
  execution_parallel: false
  plan_validation: true
  replanning_threshold: 0.5
```

#### Sense-Act Strategy

```yaml
sense_act_settings:
  observation_cycles: 5
  adaptation_threshold: 0.7
  exploration_breadth: 5
  context_window: 10
```

## File Filtering Configuration

### `max_file_size`
- **Type**: Integer (bytes)
- **Default**: 1048576 (1MB)
- **Description**: Maximum size for files to analyze
- **Common values**:
  - 524288 (512KB): Conservative
  - 1048576 (1MB): Default
  - 5242880 (5MB): Large files

### `excluded_dirs`
- **Type**: List of strings
- **Default**: `[".git", "__pycache__", "node_modules", ".venv", "venv"]`
- **Description**: Directory names to exclude from analysis
- **Examples**:
```yaml
excluded_dirs:
  - ".git"
  - "node_modules"
  - "__pycache__"
  - "dist"
  - "build"
  - "vendor"
  - ".pytest_cache"
```

### `excluded_extensions`
- **Type**: List of strings
- **Default**: `[".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".env"]`
- **Description**: File extensions to exclude
- **Examples**:
```yaml
excluded_extensions:
  - ".pyc"
  - ".log"
  - ".tmp"
  - ".map"
  - ".min.js"
  - ".bundle.js"
```

### `included_extensions`
- **Type**: List of strings
- **Default**: null (include all non-excluded)
- **Description**: Only analyze files with these extensions
- **Example**:
```yaml
included_extensions:
  - ".py"
  - ".js"
  - ".ts"
  - ".java"
```

### `file_patterns`
- **Type**: Object
- **Default**: {}
- **Description**: Regex patterns for file filtering
- **Example**:
```yaml
file_patterns:
  exclude:
    - "test_.*\\.py$"
    - ".*\\.test\\.js$"
  include:
    - ".*\\.(py|js|ts|java)$"
```

## Performance Configuration

### `batch_size`
- **Type**: Integer
- **Default**: 100
- **Description**: Number of files to process in each batch
- **Range**: 10 to 1000

### `max_workers`
- **Type**: Integer
- **Default**: 4
- **Description**: Maximum number of worker threads
- **Guidelines**: Usually CPU count / 2

### `memory_limit`
- **Type**: Integer (bytes)
- **Default**: null (no limit)
- **Description**: Maximum memory usage before optimization
- **Example**: 8589934592 (8GB)

### `cache_enabled`
- **Type**: Boolean
- **Default**: true
- **Description**: Enable caching of analysis results

### `cache_size`
- **Type**: Integer
- **Default**: 1000
- **Description**: Maximum number of cached items

## Logging Configuration

### `log_level`
- **Type**: String
- **Default**: `"INFO"`
- **Valid values**: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`
- **Description**: Minimum log level to output

### `log_file`
- **Type**: String (path) or null
- **Default**: null
- **Description**: File path for log output
- **Example**: `"/var/log/codefusion.log"`

### `verbose`
- **Type**: Boolean
- **Default**: false
- **Description**: Enable verbose console output

### `debug`
- **Type**: Boolean
- **Default**: false
- **Description**: Enable debug mode with detailed logging

## Advanced Configuration

### Security Settings

```yaml
security:
  api_key_validation: true
  secure_temp_files: true
  sanitize_outputs: true
  max_query_length: 10000
```

### Timeout Settings

```yaml
timeouts:
  llm_request: 300      # 5 minutes
  kb_operation: 600     # 10 minutes
  file_processing: 30   # 30 seconds
  exploration_step: 120 # 2 minutes
```

### Retry Settings

```yaml
retry:
  max_attempts: 3
  backoff_factor: 2.0
  max_delay: 60
  retry_on_errors:
    - "rate_limit"
    - "timeout"
    - "connection_error"
```

## Environment Variables

All configuration options can be overridden with environment variables using the pattern `CF_<OPTION_NAME>`:

```bash
export CF_LLM_MODEL="gpt-4"
export CF_KB_TYPE="neo4j"
export CF_MAX_EXPLORATION_DEPTH="10"
export CF_EXCLUDED_DIRS='[".git", "node_modules"]'
```

Special environment variables:
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `NEO4J_URI`: Neo4j connection URI
- `NEO4J_USER`: Neo4j username
- `NEO4J_PASSWORD`: Neo4j password

## Configuration Validation

### Schema Validation

CodeFusion validates configuration against a schema:

```bash
# Test configuration
cf --config my-config.yaml --validate-only
```

### Required Fields by KB Type

**Vector KB:**
- `kb_path`
- `embedding_model` (optional, has default)

**Neo4j KB:**
- `neo4j_uri`
- `neo4j_user`
- `neo4j_password`

**Text KB:**
- `kb_path`

### Validation Rules

- `max_exploration_depth` must be positive
- `max_file_size` must be positive
- `llm_temperature` must be between 0.0 and 2.0
- File paths must be valid
- URLs must be well-formed

## Configuration Examples

### Minimal Configuration

```yaml
llm_model: "gpt-3.5-turbo"
kb_type: "text"
exploration_strategy: "react"
```

### Complete Configuration

```yaml
# Repository settings
repo_path: "/path/to/project"
output_dir: "/tmp/codefusion"

# LLM settings
llm_model: "gpt-4"
llm_api_key: null
llm_temperature: 0.1
llm_max_tokens: 8192

# Knowledge base
kb_type: "neo4j"
kb_path: "./kb"
neo4j_uri: "bolt://localhost:7687"
neo4j_user: "neo4j"
neo4j_password: "password"

# Exploration
exploration_strategy: "sense_act"
max_exploration_depth: 15

# File filtering
max_file_size: 2097152
excluded_dirs:
  - ".git"
  - "node_modules"
  - "__pycache__"
excluded_extensions:
  - ".pyc"
  - ".log"

# Performance
batch_size: 200
max_workers: 8
cache_enabled: true

# Logging
log_level: "DEBUG"
verbose: true
```

## Troubleshooting

### Configuration Not Loading

```bash
# Check file syntax
python3.11 -c "import yaml; print(yaml.safe_load(open('config.yaml')))"

# Check file permissions
ls -la config.yaml
```

### Invalid Values

```bash
# Validate specific options
cf --config config.yaml stats --verbose
```

### Environment Variable Issues

```bash
# Check environment variables
env | grep -E "(CF_|OPENAI_|NEO4J_)"
```

## Next Steps

- Learn about [exploration strategies](strategies.md)
- See [configuration examples](../usage/examples.md)
- Check the [CLI reference](../reference/cli.md)