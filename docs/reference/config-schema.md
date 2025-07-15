# Configuration Schema

This document provides a complete schema reference for CodeFusion configuration files, including validation rules and examples.

## Schema Overview

CodeFusion configuration uses YAML format with the following top-level structure:

```yaml
# Basic settings
repo_path: string | null
output_dir: string

# LLM configuration
llm_model: string
llm_api_key: string | null
llm_base_url: string | null
llm_temperature: number
llm_max_tokens: integer

# Knowledge base configuration  
kb_type: enum
kb_path: string

# Vector database settings
embedding_model: string
similarity_threshold: number

# Neo4j settings
neo4j_uri: string | null
neo4j_user: string | null
neo4j_password: string | null
neo4j_database: string

# Exploration settings
exploration_strategy: enum
max_exploration_depth: integer

# File filtering
max_file_size: integer
excluded_dirs: array[string]
excluded_extensions: array[string]

# Performance settings
batch_size: integer
max_workers: integer
cache_enabled: boolean

# Logging settings
log_level: enum
verbose: boolean
debug: boolean
```

## JSON Schema

Complete JSON Schema for validation:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CodeFusion Configuration",
  "type": "object",
  "properties": {
    "repo_path": {
      "type": ["string", "null"],
      "description": "Default repository path to analyze"
    },
    "output_dir": {
      "type": "string",
      "default": "./output",
      "description": "Directory for output artifacts"
    },
    "llm_model": {
      "type": "string",
      "enum": [
        "gpt-3.5-turbo",
        "gpt-4",
        "gpt-4-turbo",
        "claude-3-sonnet-20240229",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
        "local-model"
      ],
      "default": "gpt-3.5-turbo",
      "description": "Language model to use"
    },
    "llm_api_key": {
      "type": ["string", "null"],
      "description": "API key for LLM provider"
    },
    "llm_base_url": {
      "type": ["string", "null"],
      "format": "uri",
      "description": "Custom base URL for LLM API"
    },
    "llm_temperature": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 2.0,
      "default": 0.0,
      "description": "Temperature for LLM responses"
    },
    "llm_max_tokens": {
      "type": "integer",
      "minimum": 1,
      "maximum": 32768,
      "default": 4096,
      "description": "Maximum tokens per LLM response"
    },
    "kb_type": {
      "type": "string",
      "enum": ["vector", "neo4j", "text"],
      "default": "vector",
      "description": "Knowledge base type"
    },
    "kb_path": {
      "type": "string",
      "default": "./kb",
      "description": "Knowledge base storage path"
    },
    "embedding_model": {
      "type": "string",
      "enum": [
        "all-MiniLM-L6-v2",
        "all-mpnet-base-v2",
        "BAAI/bge-small-en-v1.5",
        "sentence-transformers/all-MiniLM-L12-v2"
      ],
      "default": "all-MiniLM-L6-v2",
      "description": "Embedding model for vector database"
    },
    "similarity_threshold": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "default": 0.7,
      "description": "Minimum similarity threshold"
    },
    "neo4j_uri": {
      "type": ["string", "null"],
      "format": "uri",
      "description": "Neo4j database URI"
    },
    "neo4j_user": {
      "type": ["string", "null"],
      "description": "Neo4j username"
    },
    "neo4j_password": {
      "type": ["string", "null"],
      "description": "Neo4j password"
    },
    "neo4j_database": {
      "type": "string",
      "default": "neo4j",
      "description": "Neo4j database name"
    },
    "exploration_strategy": {
      "type": "string",
      "enum": ["react", "plan_act", "sense_act"],
      "default": "react",
      "description": "Exploration strategy"
    },
    "max_exploration_depth": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50,
      "default": 5,
      "description": "Maximum exploration depth"
    },
    "max_file_size": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 104857600,
      "default": 1048576,
      "description": "Maximum file size in bytes"
    },
    "excluded_dirs": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "default": [".git", "__pycache__", "node_modules", ".venv", "venv"],
      "description": "Directories to exclude"
    },
    "excluded_extensions": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "default": [".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".env"],
      "description": "File extensions to exclude"
    },
    "batch_size": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 100,
      "description": "Batch size for processing"
    },
    "max_workers": {
      "type": "integer",
      "minimum": 1,
      "maximum": 16,
      "default": 4,
      "description": "Maximum worker threads"
    },
    "cache_enabled": {
      "type": "boolean",
      "default": true,
      "description": "Enable result caching"
    },
    "log_level": {
      "type": "string",
      "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
      "default": "INFO",
      "description": "Logging level"
    },
    "verbose": {
      "type": "boolean",
      "default": false,
      "description": "Enable verbose output"
    },
    "debug": {
      "type": "boolean",
      "default": false,
      "description": "Enable debug mode"
    }
  },
  "required": [],
  "additionalProperties": false,
  "if": {
    "properties": {
      "kb_type": {
        "const": "neo4j"
      }
    }
  },
  "then": {
    "required": ["neo4j_uri", "neo4j_user", "neo4j_password"]
  }
}
```

## Field Definitions

### Basic Settings

#### `repo_path`
- **Type**: String or null
- **Default**: null
- **Description**: Default repository path for analysis
- **Validation**: Must be a valid directory path if specified
- **Example**: `"/path/to/my/project"`

#### `output_dir`
- **Type**: String
- **Default**: `"./output"`
- **Description**: Directory for storing output artifacts
- **Validation**: Must be a valid path
- **Example**: `"/tmp/codefusion-output"`

### LLM Configuration

#### `llm_model`
- **Type**: String (enum)
- **Default**: `"gpt-3.5-turbo"`
- **Valid Values**:
  - `"gpt-3.5-turbo"` - OpenAI GPT-3.5 Turbo
  - `"gpt-4"` - OpenAI GPT-4
  - `"gpt-4-turbo"` - OpenAI GPT-4 Turbo
  - `"claude-3-sonnet-20240229"` - Anthropic Claude 3 Sonnet
  - `"claude-3-opus-20240229"` - Anthropic Claude 3 Opus
  - `"claude-3-haiku-20240307"` - Anthropic Claude 3 Haiku
  - `"local-model"` - Custom local model
- **Description**: Language model for code analysis

#### `llm_api_key`
- **Type**: String or null
- **Default**: null
- **Description**: API key for LLM provider
- **Security**: Should be set via environment variables
- **Environment Variables**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

#### `llm_base_url`
- **Type**: String (URI) or null
- **Default**: null
- **Description**: Custom base URL for LLM API
- **Validation**: Must be a valid URI if specified
- **Examples**:
  - `"https://api.openai.com/v1"`
  - `"https://your-instance.openai.azure.com/"`
  - `"http://localhost:8000/v1"`

#### `llm_temperature`
- **Type**: Number
- **Default**: 0.0
- **Range**: 0.0 to 2.0
- **Description**: Controls randomness in LLM responses
- **Guidelines**:
  - `0.0`: Deterministic responses
  - `0.3`: Slight creativity
  - `0.7`: Balanced creativity
  - `1.0+`: High creativity

#### `llm_max_tokens`
- **Type**: Integer
- **Default**: 4096
- **Range**: 1 to 32768 (model dependent)
- **Description**: Maximum tokens per LLM response
- **Guidelines**:
  - `1024`: Short responses
  - `4096`: Standard responses
  - `8192+`: Long, detailed responses

### Knowledge Base Configuration

#### `kb_type`
- **Type**: String (enum)
- **Default**: `"vector"`
- **Valid Values**:
  - `"vector"`: Vector database for semantic search
  - `"neo4j"`: Graph database for relationships
  - `"text"`: Simple text-based storage
- **Description**: Type of knowledge base storage

#### `kb_path`
- **Type**: String
- **Default**: `"./kb"`
- **Description**: Path for knowledge base storage
- **Validation**: Must be a valid directory path
- **Example**: `"/data/codefusion/kb"`

### Vector Database Settings

#### `embedding_model`
- **Type**: String (enum)
- **Default**: `"all-MiniLM-L6-v2"`
- **Valid Values**:
  - `"all-MiniLM-L6-v2"`: Fast, good quality (384 dimensions)
  - `"all-mpnet-base-v2"`: Higher quality, slower (768 dimensions)
  - `"BAAI/bge-small-en-v1.5"`: Optimized for code (384 dimensions)
  - `"sentence-transformers/all-MiniLM-L12-v2"`: Balanced (384 dimensions)
- **Description**: Model for generating text embeddings

#### `similarity_threshold`
- **Type**: Number
- **Default**: 0.7
- **Range**: 0.0 to 1.0
- **Description**: Minimum similarity score for relevant results
- **Guidelines**:
  - `0.5`: Very loose matching
  - `0.7`: Balanced matching
  - `0.9`: Very strict matching

### Neo4j Configuration

#### `neo4j_uri`
- **Type**: String (URI) or null
- **Default**: null
- **Description**: Neo4j database connection URI
- **Required**: When `kb_type` is `"neo4j"`
- **Examples**:
  - `"bolt://localhost:7687"` - Local instance
  - `"neo4j+s://instance.databases.neo4j.io"` - Neo4j AuraDB

#### `neo4j_user`
- **Type**: String or null
- **Default**: null
- **Description**: Neo4j username
- **Required**: When `kb_type` is `"neo4j"`
- **Environment Variable**: `NEO4J_USER`

#### `neo4j_password`
- **Type**: String or null
- **Default**: null
- **Description**: Neo4j password
- **Required**: When `kb_type` is `"neo4j"`
- **Security**: Should be set via environment variables
- **Environment Variable**: `NEO4J_PASSWORD`

#### `neo4j_database`
- **Type**: String
- **Default**: `"neo4j"`
- **Description**: Neo4j database name
- **Note**: Use default for single-database instances

### Exploration Settings

#### `exploration_strategy`
- **Type**: String (enum)
- **Default**: `"react"`
- **Valid Values**:
  - `"react"`: Reasoning + Acting (fast, balanced)
  - `"plan_act"`: Plan then Act (systematic, thorough)
  - `"sense_act"`: Sense then Act (adaptive, comprehensive)
- **Description**: Strategy for code exploration

#### `max_exploration_depth`
- **Type**: Integer
- **Default**: 5
- **Range**: 1 to 50
- **Description**: Maximum number of exploration steps
- **Guidelines**:
  - `1-3`: Quick overview
  - `5-8`: Standard analysis
  - `10+`: Deep exploration

### File Filtering

#### `max_file_size`
- **Type**: Integer
- **Default**: 1048576 (1MB)
- **Range**: 1024 (1KB) to 104857600 (100MB)
- **Description**: Maximum file size in bytes
- **Common Values**:
  - `524288`: 512KB (conservative)
  - `1048576`: 1MB (default)
  - `5242880`: 5MB (large files)

#### `excluded_dirs`
- **Type**: Array of strings
- **Default**: `[".git", "__pycache__", "node_modules", ".venv", "venv"]`
- **Description**: Directory names to exclude from analysis
- **Pattern Support**: Supports glob patterns
- **Examples**:
  ```yaml
  excluded_dirs:
    - ".git"
    - "node_modules"
    - "build"
    - "dist"
    - "*.egg-info"
  ```

#### `excluded_extensions`
- **Type**: Array of strings
- **Default**: `[".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".env"]`
- **Description**: File extensions to exclude
- **Format**: Must include leading dot
- **Examples**:
  ```yaml
  excluded_extensions:
    - ".pyc"
    - ".log"
    - ".tmp"
    - ".map"
    - ".min.js"
  ```

### Performance Settings

#### `batch_size`
- **Type**: Integer
- **Default**: 100
- **Range**: 1 to 1000
- **Description**: Number of files to process in each batch
- **Guidelines**:
  - `50`: Conservative (low memory)
  - `100`: Default (balanced)
  - `200+`: Aggressive (high memory)

#### `max_workers`
- **Type**: Integer
- **Default**: 4
- **Range**: 1 to 16
- **Description**: Maximum number of worker threads
- **Guidelines**: Usually CPU count / 2

#### `cache_enabled`
- **Type**: Boolean
- **Default**: true
- **Description**: Enable caching of analysis results
- **Note**: Improves performance for repeated queries

### Logging Settings

#### `log_level`
- **Type**: String (enum)
- **Default**: `"INFO"`
- **Valid Values**:
  - `"DEBUG"`: Very detailed logging
  - `"INFO"`: Standard logging
  - `"WARNING"`: Warnings and errors only
  - `"ERROR"`: Errors only
  - `"CRITICAL"`: Critical errors only
- **Description**: Minimum log level to output

#### `verbose`
- **Type**: Boolean
- **Default**: false
- **Description**: Enable verbose console output
- **Note**: Can be overridden with `--verbose` CLI flag

#### `debug`
- **Type**: Boolean
- **Default**: false
- **Description**: Enable debug mode with detailed logging
- **Note**: Automatically sets `log_level` to `"DEBUG"`

## Advanced Configuration

### Strategy-Specific Settings

#### ReAct Strategy
```yaml
react_settings:
  reasoning_steps: 3          # integer, 1-10, default: 3
  action_timeout: 30          # integer, 10-300, default: 30
  backtrack_on_failure: true  # boolean, default: true
  max_iterations: 10          # integer, 1-50, default: 10
```

#### Plan-Act Strategy
```yaml
plan_act_settings:
  planning_depth: 3           # integer, 1-10, default: 3
  execution_parallel: false   # boolean, default: false
  plan_validation: true       # boolean, default: true
  replanning_threshold: 0.5   # number, 0.0-1.0, default: 0.5
  max_plan_steps: 20         # integer, 5-100, default: 20
```

#### Sense-Act Strategy
```yaml
sense_act_settings:
  observation_cycles: 5      # integer, 1-20, default: 5
  adaptation_threshold: 0.7  # number, 0.0-1.0, default: 0.7
  exploration_breadth: 5     # integer, 1-20, default: 5
  context_window: 10         # integer, 5-50, default: 10
  pattern_recognition: true  # boolean, default: true
```

### Security Settings
```yaml
security:
  api_key_validation: true    # boolean, default: true
  secure_temp_files: true     # boolean, default: true
  sanitize_outputs: true      # boolean, default: true
  max_query_length: 10000     # integer, 100-50000, default: 10000
```

### Timeout Settings
```yaml
timeouts:
  llm_request: 300      # integer, 30-1800, default: 300
  kb_operation: 600     # integer, 60-3600, default: 600
  file_processing: 30   # integer, 5-300, default: 30
  exploration_step: 120 # integer, 30-600, default: 120
```

## Validation Rules

### Conditional Requirements

1. **Neo4j Configuration**: When `kb_type` is `"neo4j"`, the following fields are required:
   - `neo4j_uri`
   - `neo4j_user`
   - `neo4j_password`

2. **Custom LLM**: When `llm_model` is `"local-model"`, `llm_base_url` is required.

### Cross-Field Validation

1. **File Size Limits**: `max_file_size` should be reasonable for the chosen `batch_size`
2. **Worker Limits**: `max_workers` should not exceed available CPU cores
3. **Depth Limits**: `max_exploration_depth` should be appropriate for the chosen strategy

### Format Validation

1. **URLs**: `llm_base_url` and `neo4j_uri` must be valid URIs
2. **Paths**: Directory paths must be valid for the operating system
3. **Extensions**: File extensions must start with a dot (`.`)

## Environment Variable Mapping

Configuration fields can be overridden with environment variables:

```bash
# Basic mapping pattern: CF_<FIELD_NAME>
export CF_LLM_MODEL="gpt-4"
export CF_KB_TYPE="neo4j"
export CF_MAX_EXPLORATION_DEPTH="10"

# Nested fields use underscores
export CF_REACT_SETTINGS_REASONING_STEPS="5"
export CF_NEO4J_SETTINGS_MAX_CONNECTIONS="10"

# Array values use JSON format
export CF_EXCLUDED_DIRS='[".git", "node_modules", "build"]'
export CF_EXCLUDED_EXTENSIONS='[".pyc", ".log", ".tmp"]'
```

## Configuration Examples

### Minimal Configuration
```yaml
llm_model: "gpt-3.5-turbo"
kb_type: "text"
```

### Development Configuration
```yaml
llm_model: "gpt-3.5-turbo"
kb_type: "vector"
exploration_strategy: "react"
max_exploration_depth: 3
verbose: true

excluded_dirs:
  - ".git"
  - "node_modules"
  - "__pycache__"
```

### Production Configuration
```yaml
llm_model: "gpt-4"
llm_temperature: 0.1
kb_type: "neo4j"
neo4j_uri: "bolt://neo4j-cluster:7687"
neo4j_user: "production_user"
neo4j_password: null  # Set via environment

exploration_strategy: "plan_act"
max_exploration_depth: 10
batch_size: 200
max_workers: 8

log_level: "WARNING"
cache_enabled: true
```

### Memory-Optimized Configuration
```yaml
kb_type: "text"
max_file_size: 524288  # 512KB
batch_size: 25
max_workers: 2
cache_enabled: false

excluded_dirs:
  - ".git"
  - "node_modules"
  - "vendor"
  - "build"
  - "dist"
  - "logs"
```

## Validation Tools

### Schema Validation
```python
import yaml
import jsonschema

# Load configuration
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Load schema
with open('config-schema.json') as f:
    schema = json.load(f)

# Validate
try:
    jsonschema.validate(config, schema)
    print("Configuration is valid")
except jsonschema.ValidationError as e:
    print(f"Validation error: {e.message}")
```

### CLI Validation
```bash
# Test configuration with CodeFusion
cf --config my-config.yaml stats

# Use yamllint for syntax checking
yamllint my-config.yaml
```

## Next Steps

- See [configuration examples](../usage/examples.md) for practical use cases
- Check the [CLI reference](cli.md) for command-line options
- Review [configuration best practices](../config/overview.md)