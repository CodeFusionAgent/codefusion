# Installation and Setup Guide

This guide covers setting up CodeFusion for development and usage.

## Prerequisites

- **Python 3.8+**: Required for all functionality
- **Git**: For cloning repositories and version control
- **Virtual Environment**: Highly recommended to avoid dependency conflicts

## Virtual Environment Setup

### Create Virtual Environment

```bash
# Navigate to project directory
cd codefusion

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Verify Activation

Your terminal prompt should show `(venv)` when the virtual environment is active:

```bash
(venv) $ python --version
Python 3.12.x
```

## Installation Options

### Basic Installation

Install core functionality with text-based knowledge base:

```bash
pip install -e .
```

This includes:
- Core system architecture
- Text-based knowledge base
- CLI interface
- Configuration management

### Vector Database Support

For semantic search and code embeddings:

```bash
pip install -e ".[vector]"
```

Adds:
- FAISS vector database
- Sentence transformers for embeddings
- Semantic code search capabilities

### LLM Integration

For AI-powered code analysis:

```bash
pip install -e ".[llm]"
```

Adds:
- LiteLLM for multiple AI providers
- OpenAI, Anthropic, Cohere support
- LLM tracing and monitoring

### Graph Database

For complex relationship analysis:

```bash
pip install -e ".[neo4j]"
```

Adds:
- Neo4j driver
- Graph-based knowledge storage
- Advanced relationship queries

### Development Tools

For contributing to CodeFusion:

```bash
pip install -e ".[dev]"
```

Adds:
- pytest testing framework
- Code formatting (black, isort)
- Type checking (mypy)
- Linting (flake8)
- Pre-commit hooks

### Complete Installation

Install everything:

```bash
pip install -e ".[all]"
```

## Verification

Test your installation:

```bash
# Check CLI is working
cf --help

# Run a quick demo
cf demo

# Test vector database (if installed)
python -c "from cf.kb.vector_kb import VectorKB; print('Vector DB available!')"
```

## Configuration

### Default Configuration

CodeFusion looks for configuration in these locations (in order):
1. Command line `--config` parameter
2. Current directory `config.yaml`
3. Default built-in configuration

### Basic Configuration File

Create `config.yaml`:

```yaml
# Basic text-based setup
kb_type: "text"
kb_path: "./kb"
exploration_strategy: "react"
max_file_size: 1048576  # 1MB
excluded_dirs: [".git", "__pycache__", "node_modules", ".venv"]
```

### Vector Database Configuration

For semantic search capabilities:

```yaml
# Vector database setup
kb_type: "vector"
kb_path: "./kb_vector"
embedding_model: "all-MiniLM-L6-v2"
exploration_strategy: "react"
max_file_size: 1048576
excluded_dirs: [".git", "__pycache__", "node_modules", ".venv"]
```

### LLM Configuration

For AI-powered analysis:

```yaml
# LLM integration
kb_type: "vector"
kb_path: "./kb_vector"
llm_model: "gpt-3.5-turbo"
llm_api_key: "your-api-key-here"  # Optional, can use env var
embedding_model: "all-MiniLM-L6-v2"
exploration_strategy: "react"
```

## Environment Variables

Set these environment variables for convenience:

```bash
# API keys (optional)
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"

# Default config file
export CF_CONFIG="./config.yaml"
```

## Troubleshooting

### Common Issues

**ImportError: No module named 'faiss'**
```bash
pip install -e ".[vector]"
```

**sentence-transformers not found**
```bash
pip install sentence-transformers
```

**Virtual environment not activated**
```bash
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

### Dependency Conflicts

If you encounter dependency conflicts:

```bash
# Create fresh virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate

# Reinstall with specific versions
pip install -e ".[all]"
```

### Performance Issues

For large codebases:

1. Increase `max_file_size` in config
2. Add more directories to `excluded_dirs`
3. Use vector database for faster search
4. Consider using smaller embedding models

## Next Steps

1. **Quick Start**: Try `cf demo` to see CodeFusion in action
2. **Explore a Codebase**: Run `cf explore /path/to/your/project`
3. **Configuration**: Customize `config.yaml` for your needs
4. **Documentation**: Read the usage guides in `docs/usage/`