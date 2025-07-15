# Contributing to CodeFusion

Thank you for your interest in contributing to CodeFusion! This document provides guidelines and information for contributors.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Coding Standards](#coding-standards)

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/CodeFusionAgent/codefusion.git`
3. Add the upstream remote: `git remote add upstream https://github.com/CodeFusionAgent/codefusion.git`

## Development Setup

1. **Install Python 3.8 or higher**

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks:**
   ```bash
   pre-commit install
   ```

5. **Verify installation:**
   ```bash
   python -m cf demo .
   ```

## Making Changes

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes following our coding standards**

3. **Write or update tests as needed**

4. **Run the test suite:**
   ```bash
   pytest
   ```

5. **Run code quality checks:**
   ```bash
   pre-commit run --all-files
   ```

## Testing

We use pytest for testing. Please ensure:

- All new code has appropriate tests
- All tests pass before submitting
- Test coverage remains high

Run tests with:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cf

# Run specific test file
pytest tests/test_config.py
```

## Submitting Changes

1. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: add new exploration strategy"
   ```

2. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create a Pull Request:**
   - Use the provided PR template
   - Include a clear description of changes
   - Reference any related issues
   - Ensure CI checks pass

## Coding Standards

### Python Code Style
- Follow PEP 8 guidelines
- Use Black for code formatting (line length: 88)
- Use isort for import sorting
- Use type hints throughout
- Follow Google-style docstrings

### Commit Messages
Use conventional commit format:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for test additions/changes
- `refactor:` for code refactoring
- `style:` for formatting changes

### Documentation
- Update documentation for any user-facing changes
- Include docstrings for all public functions/classes
- Update the README if needed

## Architecture Guidelines

When contributing to CodeFusion:

1. **Respect the kernel-based architecture**
2. **Follow the agentic exploration patterns**
3. **Maintain separation of concerns**
4. **Use the established type system**
5. **Handle exceptions appropriately**

## Issue Reporting

When reporting issues:
- Use the provided issue templates
- Include steps to reproduce
- Provide system information
- Include relevant logs/error messages

## Questions?

- Check existing issues and discussions
- Create a new issue for questions
- Join our community discussions

Thank you for contributing to CodeFusion!
