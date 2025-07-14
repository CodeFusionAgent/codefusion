# Quick Start Guide

Get CodeFusion up and running in minutes with this quick start guide.

## Installation

### Option 1: Install from PyPI (Recommended)

```bash
pip install codefusion
```

### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/CodeFusionAgent/codefusion.git
cd codefusion

# Install in development mode
pip install -e .
```

## Basic Usage

### 1. Index a Repository

Start by indexing a code repository to build the knowledge base:

```bash
cf index /path/to/your/repository
```

This will:
- Scan all files in the repository
- Extract code entities (classes, functions, modules)
- Detect relationships between entities
- Store everything in a knowledge base

### 2. Query the Code

Ask natural language questions about your codebase:

```bash
cf query "How does authentication work?"
cf query "What are the main API endpoints?"
cf query "Where is the database configuration?"
```

### 3. Full Exploration

Run a complete exploration workflow:

```bash
cf explore /path/to/your/repository
```

This combines indexing with automatic insights and analysis.

## Configuration

### Environment Variables

Set up your LLM API key for enhanced analysis:

```bash
# For OpenAI
export OPENAI_API_KEY="your-api-key-here"

# Or for Anthropic
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Configuration File

Create a configuration file for custom settings:

```yaml
# config.yaml
llm_model: "gpt-4"
kb_type: "neo4j"  # or "vector"
exploration_strategy: "react"  # or "plan_act", "sense_act"
```

Use it with:

```bash
cf --config config.yaml index /path/to/repo
```

## Next Steps

- Learn about [CLI Commands](../usage/cli.md)
- Explore [Configuration Options](../config/overview.md)
- Check out [Examples](../usage/examples.md)
- Read the [Architecture Guide](../dev/architecture.md)

## Troubleshooting

### Common Issues

**Import Error**: If you get import errors, make sure you're in the correct Python environment:

```bash
which python
pip list | grep codefusion
```

**Neo4j Connection**: If using Neo4j, ensure the database is running:

```bash
# Start Neo4j (if installed via Homebrew on macOS)
brew services start neo4j

# Or via Docker
docker run -p 7474:7474 -p 7687:7687 neo4j:latest
```

**API Key Issues**: Verify your API key is set correctly:

```bash
echo $OPENAI_API_KEY
# Should output your API key (not empty)
```

### Getting Help

- Check the [full documentation](../index.md)
- Search [GitHub Issues](https://github.com/CodeFusionAgent/codefusion/issues)
- Create a [new issue](https://github.com/CodeFusionAgent/codefusion/issues/new) if needed