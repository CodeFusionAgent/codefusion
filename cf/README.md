# Core CodeFusion System

This directory contains the core implementation of CodeFusion's human-like code exploration system.

## Components

### `config.py`
Simple configuration management for exploration settings, file exclusions, and repository parameters.

### `aci/` - Abstract Code Interface
- `repo.py`: Repository abstraction layer supporting local and remote code access

### `agents/` - Exploration Agents  
- `human_explorer.py`: Human-like investigation agent using React pattern (Reason → Act → Observe)

### `core/` - Core Exploration
- `simple_explorer.py`: Main exploration engine with intelligent caching and progressive learning

### `run/` - CLI Interface
- `simple_run.py`: Command-line interface for exploration commands

## Architecture

The system follows a simple, human-like approach:
1. **No complex preprocessing** - Start exploring immediately
2. **Simple tools** - List directories, read files, search patterns  
3. **Progressive learning** - Build understanding incrementally
4. **Intelligent caching** - Remember findings for faster subsequent explorations

## Usage

```python
from cf.core.simple_explorer import SimpleExplorer

explorer = SimpleExplorer("/path/to/repo")
result = explorer.explore("How does authentication work?")
```

Or via CLI:
```bash
cf explore /path/to/repo "How does authentication work?"
```
