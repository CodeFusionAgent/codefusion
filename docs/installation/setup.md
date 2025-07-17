# Installation and Setup Guide

This guide covers setting up CodeFusion for human-like code exploration.

## Prerequisites

- **Python 3.10+**: Required for all functionality
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
Python 3.10.x
```

## Installation Options

### Basic Installation

Install CodeFusion with human-like exploration capabilities:

```bash
pip install -e .
```

This includes:
- Core human-like exploration system
- Simple CLI interface
- Text-based caching
- Repository access layer
- Basic configuration management

### Development Installation

For development and contributing:

```bash
pip install -e ".[dev]"
```

This adds:
- Testing framework (pytest)
- Code formatting (black)
- Import sorting (isort)
- Linting (flake8)
- Type checking (mypy)
- Pre-commit hooks

### Documentation Installation

For building and serving documentation:

```bash
pip install -e ".[docs]"
```

This adds:
- MkDocs for documentation
- Material theme
- Mermaid diagrams
- Python docstring support

### Complete Installation

Install everything:

```bash
pip install -e ".[all]"
```

## Verify Installation

### Basic Verification

```bash
# Check if cf command is available
cf --help

# Verify Python imports work
python -c "import cf; print(f'CodeFusion v{cf.__version__}')"
```

### Test with Sample Repository

```bash
# Test basic exploration
cf explore . "How does the simple explorer work?"

# Test with a larger repository
cf explore /path/to/some/repo "What is the overall architecture?"
```

## Initial Configuration

### Default Configuration

CodeFusion works out of the box with sensible defaults. The default configuration is located at:

```
config/default/config.yaml
```

### Custom Configuration

Create your own configuration file:

```bash
# Copy default configuration
cp config/default/config.yaml my-config.yaml

# Edit configuration
nano my-config.yaml

# Use custom configuration
cf --config my-config.yaml explore /path/to/repo "How does authentication work?"
```

## Development Setup

### Additional Development Tools

```bash
# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Format code
black .

# Sort imports
isort .

# Check types
mypy cf/

# Lint code
flake8 cf/
```

### IDE Configuration

#### VS Code

Install recommended extensions:

```json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.black-formatter",
        "ms-python.isort",
        "ms-python.flake8",
        "ms-python.mypy-type-checker"
    ]
}
```

#### PyCharm

Configure interpreters:
1. Go to File → Settings → Project → Python Interpreter
2. Select the virtual environment: `./venv/bin/python`
3. Enable type checking and linting

## Common Installation Issues

### Python Version Issues

```bash
# Check Python version
python --version

# If you have multiple Python versions, use specific version
python3.10 -m venv venv
```

### Permission Issues

```bash
# On macOS/Linux, if you get permission errors:
sudo chown -R $(whoami) ~/.local/lib/python3.10/site-packages/

# Or use user installation
pip install --user -e .
```

### Virtual Environment Issues

```bash
# Deactivate and recreate virtual environment
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### Dependencies Issues

```bash
# Clear pip cache
pip cache purge

# Upgrade pip and setuptools
pip install --upgrade pip setuptools wheel

# Reinstall dependencies
pip install --force-reinstall -e .
```

## Directory Structure

After installation, your directory structure should look like:

```
codefusion/
├── cf/                          # Main package
│   ├── core/
│   │   └── simple_explorer.py   # Main exploration interface
│   ├── agents/
│   │   └── human_explorer.py    # Human-like investigation
│   ├── run/
│   │   └── simple_run.py        # CLI interface
│   ├── aci/
│   │   └── repo.py              # Repository access
│   └── config.py                # Configuration management
├── config/
│   └── default/
│       └── config.yaml          # Default configuration
├── examples/
│   └── human_exploration_demo.py # Demo script
├── tests/                       # Test suite
├── docs/                        # Documentation
├── pyproject.toml               # Package configuration
└── README.md                    # Main documentation
```

## Environment Variables

CodeFusion uses minimal environment variables:

```bash
# Optional: Set default configuration path
export CF_CONFIG_PATH="/path/to/config.yaml"

# Optional: Enable debug mode
export CF_DEBUG=1

# Optional: Set output directory
export CF_OUTPUT_DIR="/path/to/output"
```

## Troubleshooting

### Command Not Found

```bash
# Check if cf is in PATH
which cf

# If not found, try:
pip install -e . --force-reinstall

# Or use python module execution
python -m cf --help
```

### Import Errors

```bash
# Check if package is installed
pip list | grep codefusion

# If not listed, reinstall
pip install -e .

# Check for import issues
python -c "import cf; print('OK')"
```

### Configuration Errors

```bash
# Validate configuration
cf --config config.yaml summary /path/to/repo

# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

## Performance Optimization

### For Large Repositories

```bash
# Create optimized configuration
cat > large-repo-config.yaml << 'EOF'
max_file_size: 2097152  # 2MB
max_exploration_depth: 3
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "dist"
  - "build"
  - "target"
  - "vendor"
EOF

# Use optimized configuration
cf --config large-repo-config.yaml explore /path/to/large/repo "How does X work?"
```

### Memory Usage

```bash
# Monitor memory usage
/usr/bin/time -v cf explore /path/to/repo "How does X work?"

# For memory-constrained environments
export CF_MAX_FILE_SIZE=524288  # 512KB
```

## Next Steps

1. **Try the demo**: Run `python examples/human_exploration_demo.py`
2. **Explore a repository**: Use `cf explore /path/to/repo "How does X work?"`
3. **Read the documentation**: Check out the [CLI Usage](../usage/cli.md) guide
4. **Configure for your needs**: See [Configuration](../usage/configuration.md)
5. **Contributing**: Check the development setup above

## Getting Help

If you encounter issues:

1. **Check the documentation**: Look through the docs/ directory
2. **Run diagnostics**: Use `cf --verbose` for detailed output
3. **Check dependencies**: Ensure all required packages are installed
4. **Test configuration**: Validate your configuration files
5. **Create an issue**: Report bugs or request features in the repository

## Uninstallation

To remove CodeFusion:

```bash
# Uninstall package
pip uninstall codefusion

# Remove virtual environment
deactivate
rm -rf venv

# Clean up cache (optional)
rm -rf ~/.cache/pip/
```