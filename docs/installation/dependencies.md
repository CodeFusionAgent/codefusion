# Dependencies

This page details all dependencies required for CodeFusion and optional components.

## Core Dependencies

### Required Python Packages

These are automatically installed with CodeFusion:

```
pyyaml>=6.0          # Configuration file parsing
pathlib              # File path handling (Python 3.4+)
dataclasses          # Data structures (Python 3.7+)
typing-extensions    # Type hints compatibility
```

### Python Version

- **Minimum**: Python 3.10
- **Recommended**: Python 3.11+
- **Tested**: Python 3.10, 3.11, 3.12

## Optional Dependencies

### LLM Integration

For enhanced natural language processing capabilities:

```bash
# For OpenAI models
pip install openai>=1.0.0

# For comprehensive LLM support via LiteLLM
pip install litellm>=1.0.0

# For local/offline models
pip install transformers torch
```

### Neo4j Graph Database

For advanced graph-based code relationship analysis:

```bash
# Neo4j Python driver
pip install neo4j>=5.0.0

# Neo4j database server (choose one):

# Option 1: Local installation (macOS)
brew install neo4j

# Option 2: Docker
docker pull neo4j:latest

# Option 3: Neo4j Desktop
# Download from https://neo4j.com/download/
```

### Vector Database Support

For semantic search and similarity matching:

```bash
# FAISS for fast similarity search
pip install faiss-cpu>=1.7.0
# Or for GPU support:
# pip install faiss-gpu>=1.7.0

# Sentence transformers for embeddings
pip install sentence-transformers>=2.0.0

# Alternative vector databases
pip install chromadb>=0.4.0    # ChromaDB
pip install weaviate-client    # Weaviate
pip install pinecone-client    # Pinecone
```

### Development Dependencies

For contributing to CodeFusion development:

```bash
# Testing framework
pip install pytest>=7.0.0
pip install pytest-cov>=4.0.0
pip install pytest-mock>=3.10.0

# Code quality tools
pip install black>=23.0.0      # Code formatting
pip install flake8>=6.0.0     # Linting
pip install mypy>=1.0.0       # Type checking
pip install isort>=5.12.0     # Import sorting

# Pre-commit hooks
pip install pre-commit>=3.0.0

# Documentation
pip install mkdocs>=1.5.0
pip install mkdocs-material>=9.0.0
pip install mkdocstrings[python]>=0.20.0
pip install pymdown-extensions>=10.0.0
```

## System Dependencies

### Operating System Support

- **Linux**: Ubuntu 18.04+, CentOS 7+, Debian 10+
- **macOS**: 10.15+ (Catalina or later)
- **Windows**: Windows 10+ (with WSL recommended)

### Memory Requirements

- **Minimum**: 4GB RAM
- **Recommended**: 8GB+ RAM for large repositories
- **Large codebases**: 16GB+ RAM recommended

### Storage Requirements

- **Installation**: ~100MB
- **Knowledge base**: Varies by repository size
  - Small repo (~1,000 files): ~10MB
  - Medium repo (~10,000 files): ~100MB
  - Large repo (~100,000 files): ~1GB+

## Environment Setup

### Virtual Environment (Recommended)

```bash
# Using venv (built-in)
python3.11 -m venv codefusion-env
source codefusion-env/bin/activate  # On Windows: codefusion-env\Scripts\activate

# Using conda
conda create -n codefusion python=3.11
conda activate codefusion

# Using poetry
poetry install
poetry shell
```

### Environment Variables

Set these for full functionality:

```bash
# LLM API keys
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"

# Neo4j configuration
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"

# Optional: Custom model configurations
export LLM_MODEL="gpt-4"
export EMBEDDING_MODEL="all-MiniLM-L6-v2"
```

## Dependency Groups

### Complete Installation

Install all optional dependencies:

```bash
pip install codefusion[all]
```

### Specific Feature Sets

```bash
# Graph database support
pip install codefusion[neo4j]

# Vector database support  
pip install codefusion[vector]

# LLM integration
pip install codefusion[llm]

# Development tools
pip install codefusion[dev]
```

## Compatibility Matrix

| Component | Python 3.10 | Python 3.11 | Python 3.12 |
|-----------|--------------|--------------|--------------|
| Core      | ✅           | ✅           | ✅           |
| Neo4j     | ✅           | ✅           | ✅           |
| FAISS     | ✅           | ✅           | ⚠️*          |
| LiteLLM   | ✅           | ✅           | ✅           |

*⚠️ Limited FAISS wheel availability for Python 3.12

## Troubleshooting Dependencies

### Common Issues

**Conflicting Dependencies**:
```bash
# Check for conflicts
pip check

# Resolve with pip-tools
pip install pip-tools
pip-compile requirements.in
```

**FAISS Installation Issues**:
```bash
# For macOS with Apple Silicon
pip install faiss-cpu --no-cache-dir

# Alternative for ARM64
conda install -c conda-forge faiss-cpu
```

**Neo4j Driver Issues**:
```bash
# Update to latest version
pip install --upgrade neo4j

# Test connection
python -c "import neo4j; print(neo4j.__version__)"
```

### Dependency Updates

Stay updated with compatible versions:

```bash
# Check outdated packages
pip list --outdated

# Update CodeFusion
pip install --upgrade codefusion

# Update all dependencies
pip install --upgrade -r requirements.txt
```

## Security Considerations

### API Key Management

- Store API keys in environment variables, not code
- Use `.env` files for local development
- Consider using secrets management for production

### Network Security

- Neo4j should be secured in production environments
- Use TLS/SSL for Neo4j connections
- Restrict network access to database ports

### Dependency Security

```bash
# Check for security vulnerabilities
python3.11 -m pip install safety
safety check

# Audit dependencies
pip-audit
```

## Performance Optimization

### Vector Operations

```bash
# Install optimized BLAS
pip install numpy[blas]

# For Intel CPUs
pip install intel-extension-for-pytorch
```

### Memory Usage

```bash
# Monitor memory during indexing
python3.11 -m pip install psutil
python3.11 -c "
import psutil
print(f'Available memory: {psutil.virtual_memory().available / 1e9:.1f} GB')
"
```

## Next Steps

- Complete the [Quick Start](quickstart.md) guide
- Learn about [Configuration](../config/overview.md)
- Explore [Usage Examples](../usage/examples.md)