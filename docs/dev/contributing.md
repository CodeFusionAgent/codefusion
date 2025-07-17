# Contributing to CodeFusion

Thank you for your interest in contributing to CodeFusion! This project focuses on simplicity and human-like exploration patterns.

## Philosophy

CodeFusion is built on the principle that code exploration should be as natural as human investigation. When contributing, please keep these principles in mind:

- **Keep it simple**: Avoid complex dependencies and solutions
- **Human-like patterns**: Follow natural investigation workflows
- **Immediate usability**: No complex setup or preprocessing
- **Incremental understanding**: Build knowledge step by step

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Basic understanding of command-line tools

### Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd codefusion

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install for development
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
pytest
```

## Code Organization

### Project Structure

```
cf/
├── core/
│   └── simple_explorer.py      # Main exploration interface
├── agents/
│   └── human_explorer.py       # Human-like investigation agent
├── run/
│   └── simple_run.py           # CLI interface
├── aci/
│   └── repo.py                 # Repository access
└── config.py                   # Simple configuration
```

### Key Components

1. **CLI** (`cf/run/simple_run.py`): Command-line interface
2. **Simple Explorer** (`cf/core/simple_explorer.py`): Main orchestration
3. **Human Explorer** (`cf/agents/human_explorer.py`): Investigation logic
4. **Repository Interface** (`cf/aci/repo.py`): File system access
5. **Configuration** (`cf/config.py`): Simple settings management

## Development Workflow

### Making Changes

1. **Create a branch**: `git checkout -b feature/your-feature`
2. **Make changes**: Follow the coding standards below
3. **Test changes**: Run tests and verify functionality
4. **Commit changes**: Use clear, descriptive commit messages
5. **Push branch**: `git push origin feature/your-feature`
6. **Create PR**: Submit a pull request for review

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cf

# Run specific test file
pytest tests/test_simple_explorer.py

# Run tests with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Check linting
flake8 cf/

# Type checking
mypy cf/

# Run all quality checks
black . && isort . && flake8 cf/ && mypy cf/
```

## Coding Standards

### Python Style

- Follow PEP 8 style guide
- Use Black for code formatting
- Sort imports with isort
- Add type hints for function parameters and return values
- Keep functions focused and single-purpose

### Example Code Style

```python
def explore_repository(repo_path: str, question: str) -> str:
    """
    Explore a repository to answer a question.
    
    Args:
        repo_path: Path to the repository
        question: Question to investigate
        
    Returns:
        Human-readable investigation results
    """
    explorer = SimpleExplorer(repo_path)
    return explorer.explore(question)
```

### Documentation

- Use Google-style docstrings
- Include type hints
- Provide clear examples
- Document complex logic with comments

## Adding Features

### New Exploration Tools

To add a new exploration tool:

1. Add method to `ExplorationTools` class in `cf/agents/human_explorer.py`
2. Update `_take_action` method to use the new tool
3. Add observation handling in `_observe_results`
4. Write tests for the new functionality

Example:
```python
def find_imports(self, file_path: str) -> List[str]:
    """Find import statements in a file."""
    try:
        content = self.repo.read_file(file_path)
        # Simple regex to find imports
        import re
        imports = re.findall(r'^(?:from|import)\s+(\S+)', content, re.MULTILINE)
        return imports
    except Exception as e:
        return [f"Error finding imports: {e}"]
```

### New CLI Commands

To add a new CLI command:

1. Add parser in `create_parser` method in `cf/run/simple_run.py`
2. Create command handler method (e.g., `cmd_new_command`)
3. Add to the argument parser setup
4. Test the new command

### Configuration Options

To add new configuration options:

1. Add field to `CfConfig` class in `cf/config.py`
2. Update `to_dict` and validation methods
3. Update default configuration file
4. Document the new option

## Testing Guidelines

### Unit Tests

- Test individual components in isolation
- Mock external dependencies
- Use descriptive test names
- Test both success and failure cases

Example:
```python
def test_simple_explorer_caching():
    """Test that exploration results are cached correctly."""
    explorer = SimpleExplorer("/test/repo")
    
    # Mock the investigation
    with patch.object(explorer.explorer, 'investigate') as mock_investigate:
        mock_investigate.return_value = Mock(...)
        
        # First call should hit investigation
        result1 = explorer.explore("test question")
        assert mock_investigate.called
        
        # Second call should use cache
        result2 = explorer.explore("test question")
        assert result1 == result2
```

### Integration Tests

- Test end-to-end workflows
- Use temporary directories for file operations
- Test CLI commands with real repositories
- Verify error handling

### Performance Tests

- Test with large repositories
- Monitor memory usage
- Measure response times
- Test caching effectiveness

## Submitting Changes

### Pull Request Process

1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Test thoroughly**
5. **Update documentation**
6. **Submit pull request**

### PR Guidelines

- Clear, descriptive title
- Detailed description of changes
- Reference any related issues
- Include tests for new features
- Update documentation as needed

## Bug Reports

### Before Reporting

1. Check existing issues
2. Try latest version
3. Verify it's not a configuration issue
4. Test with minimal example

### Bug Report Template

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., macOS 12.0]
- Python: [e.g., 3.10.0]
- CodeFusion: [e.g., 0.0.1]

## Additional Context
Any other relevant information
```

## Feature Requests

### Guidelines

- Keep features simple and focused
- Align with human-like exploration philosophy
- Avoid complex dependencies
- Consider maintenance burden

## Community

### Communication

- Be respectful and professional
- Focus on the code, not the person
- Provide constructive feedback
- Help others learn and improve

### Getting Help

- Check existing documentation
- Search previous issues
- Ask questions in discussions
- Be specific about problems

## Thank You

Thank you for contributing to CodeFusion! Your contributions help make code exploration more natural and accessible for developers everywhere.

---

*Remember: Keep it simple, keep it human-like, and keep it useful.*