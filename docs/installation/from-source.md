# Installing from Source

This guide covers installing CodeFusion from source code for development or when you need the latest features.

## Prerequisites

### System Requirements

- **Python**: 3.10 or higher
- **Git**: For cloning the repository
- **pip**: Python package manager

### Optional Dependencies

- **Neo4j**: For graph database functionality
- **Docker**: For containerized Neo4j deployment

## Step-by-Step Installation

### 1. Clone the Repository

```bash
git clone https://github.com/CodeFusionAgent/codefusion.git
cd codefusion
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install in development mode
pip install -e .

# Or install with all optional dependencies
pip install -e ".[all]"
```

### 4. Install Optional Dependencies

#### For Neo4j Support

```bash
pip install neo4j
```

#### For Vector Database Support

```bash
pip install faiss-cpu sentence-transformers
# Or for GPU support:
# pip install faiss-gpu sentence-transformers
```

#### For Development

```bash
pip install -e ".[dev]"
```

This includes testing, linting, and documentation dependencies.

## Setting Up Neo4j

### Option 1: Local Installation (macOS)

```bash
# Install via Homebrew
brew install neo4j

# Start the service
brew services start neo4j

# Access Neo4j Browser at http://localhost:7474
# Default credentials: neo4j/neo4j (change on first login)
```

### Option 2: Docker

```bash
# Run Neo4j in Docker
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -d \
    -v $HOME/neo4j/data:/data \
    -v $HOME/neo4j/logs:/logs \
    -v $HOME/neo4j/import:/var/lib/neo4j/import \
    -v $HOME/neo4j/plugins:/plugins \
    --env NEO4J_AUTH=neo4j/password \
    neo4j:latest
```

### Option 3: Neo4j Desktop

1. Download from [Neo4j Desktop](https://neo4j.com/download/)
2. Install and create a new project
3. Create a new database instance
4. Start the database

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# .env
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### Configuration File

Copy the default configuration:

```bash
cp config/default/config.yaml config/local.yaml
```

Edit `config/local.yaml` for your setup:

```yaml
# config/local.yaml
llm_model: "gpt-4"
llm_api_key: null  # Will use environment variable
kb_type: "neo4j"
neo4j_uri: "bolt://localhost:7687"
neo4j_user: "neo4j"
neo4j_password: "password"
exploration_strategy: "react"
max_exploration_depth: 5
```

## Verification

### Test the Installation

```bash
# Test basic functionality
python3.11 -m cf --help

# Test with a sample repository
python3.11 -m cf demo /path/to/small/repo
```

### Run Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_config.py
pytest tests/test_knowledge_base.py

# Run with coverage
pytest --cov=cf tests/
```

### Test Neo4j Connection

```bash
# Test Neo4j connectivity
python3.11 -c "
from cf.kb.knowledge_base import create_knowledge_base
kb = create_knowledge_base('neo4j', './test_kb', 
    uri='bolt://localhost:7687', user='neo4j', password='password')
print('Neo4j connection successful!')
"
```

## Development Setup

### Pre-commit Hooks

Set up pre-commit hooks for code quality:

```bash
pip install pre-commit
pre-commit install
```

### IDE Configuration

#### VS Code

Install recommended extensions:
- Python
- Pylance
- Python Docstring Generator

#### PyCharm

Configure interpreter to use your virtual environment.

## Troubleshooting

### Common Build Issues

**Missing Dependencies**:
```bash
# Update pip and setuptools
pip install --upgrade pip setuptools wheel
```

**Neo4j Connection Issues**:
```bash
# Check if Neo4j is running
curl http://localhost:7474

# Check Neo4j logs
tail -f ~/neo4j/logs/neo4j.log
```

**Import Errors**:
```bash
# Verify installation
pip list | grep codefusion
python3.11 -c "import cf; print(cf.__version__)"
```

### Performance Issues

**Slow Vector Operations**:
```bash
# Install optimized BLAS libraries
pip install numpy[blas]
```

**Memory Issues**:
```bash
# Monitor memory usage during indexing
python3.11 -m cf index --verbose /path/to/repo
```

## Next Steps

- Set up your [development environment](../dev/contributing.md)
- Learn about [testing](../dev/testing.md)
- Explore the [architecture](../dev/architecture.md)
- Start [contributing](../dev/contributing.md)