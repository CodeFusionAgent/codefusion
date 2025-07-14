# CLI Commands

CodeFusion provides a comprehensive command-line interface for repository exploration and code analysis.

## Overview

The main CLI entry point is the `cf` command:

```bash
cf --help
```

## Global Options

These options are available for all commands:

```bash
cf [OPTIONS] COMMAND [ARGS]...

Global Options:
  --config, -c PATH    Configuration file path [default: config/default/config.yaml]
  --verbose, -v        Enable verbose output
  --help               Show help message
```

## Commands

### `index` - Index a Repository

Index a repository to build the knowledge base.

```bash
cf index [OPTIONS] REPO_PATH
```

**Arguments:**
- `REPO_PATH`: Path to the repository to index

**Options:**
- `--strategy {react,plan_act,sense_act}`: Exploration strategy [default: react]

**Examples:**
```bash
# Basic indexing
cf index /path/to/repository

# Use specific strategy
cf index --strategy plan_act /path/to/repository

# With custom config
cf --config my-config.yaml index /path/to/repository
```

### `query` - Query the Knowledge Base

Ask natural language questions about the indexed codebase.

```bash
cf query [OPTIONS] QUESTION
```

**Arguments:**
- `QUESTION`: Question to ask about the code

**Options:**
- `--repo-path PATH`: Repository path (if not using saved KB)
- `--strategy {react,plan_act,sense_act}`: Exploration strategy [default: react]

**Examples:**
```bash
# Basic query
cf query "How does authentication work?"

# Query with specific repository
cf query --repo-path /path/to/repo "What are the main API endpoints?"

# Use different reasoning strategy
cf query --strategy plan_act "How is the database configured?"
```

### `explore` - Full Exploration Workflow

Run complete exploration including indexing and automatic insights.

```bash
cf explore [OPTIONS] REPO_PATH
```

**Arguments:**
- `REPO_PATH`: Path to repository to explore

**Options:**
- `--strategy {react,plan_act,sense_act}`: Exploration strategy [default: react]

**Examples:**
```bash
# Full exploration
cf explore /path/to/repository

# With specific strategy
cf explore --strategy sense_act /path/to/repository
```

### `stats` - Show Knowledge Base Statistics

Display statistics about the knowledge base.

```bash
cf stats [OPTIONS]
```

**Options:**
- `--repo-path PATH`: Repository path

**Examples:**
```bash
# Show stats for current KB
cf stats

# Show stats for specific repository
cf stats --repo-path /path/to/repository
```

### `demo` - Run Demo

Run a demonstration of CodeFusion capabilities.

```bash
cf demo REPO_PATH
```

**Arguments:**
- `REPO_PATH`: Path to repository for demo

**Examples:**
```bash
cf demo /path/to/sample/repository
```

## Configuration Integration

### Using Configuration Files

```bash
# Use custom configuration
cf --config /path/to/config.yaml index /path/to/repo

# Configuration hierarchy:
# 1. Command line options (highest priority)
# 2. Configuration file
# 3. Environment variables
# 4. Default values (lowest priority)
```

### Environment Variables

Set environment variables to override configuration:

```bash
export OPENAI_API_KEY="your-api-key"
export NEO4J_PASSWORD="your-password"
cf index /path/to/repo
```

## Advanced Usage

### Exploration Strategies

#### ReAct Strategy (Default)

Reasoning + Acting approach for iterative exploration:

```bash
cf query --strategy react "Explain the architecture"
```

**Best for:**
- General code understanding
- Interactive exploration
- Balanced speed and thoroughness

#### Plan-then-Act Strategy

Create a plan before execution:

```bash
cf query --strategy plan_act "How do I set up this project?"
```

**Best for:**
- Systematic analysis
- Setup and installation questions
- Step-by-step procedures

#### Sense-then-Act Strategy

Observe before taking action:

```bash
cf query --strategy sense_act "What testing frameworks are used?"
```

**Best for:**
- Complex codebases
- Discovering patterns
- Unknown technology stacks

### Knowledge Base Types

#### Vector Database (Default)

For semantic similarity search:

```yaml
# config.yaml
kb_type: "vector"
embedding_model: "all-MiniLM-L6-v2"
```

```bash
cf --config config.yaml index /path/to/repo
```

#### Neo4j Graph Database

For relationship analysis:

```yaml
# config.yaml
kb_type: "neo4j"
neo4j_uri: "bolt://localhost:7687"
neo4j_user: "neo4j"
neo4j_password: "password"
```

```bash
cf --config config.yaml index /path/to/repo
```

### Batch Processing

#### Process Multiple Repositories

```bash
# Create a script for batch processing
#!/bin/bash
for repo in /path/to/repos/*; do
    if [ -d "$repo" ]; then
        echo "Processing $repo"
        cf index "$repo"
    fi
done
```

#### Using Configuration Templates

```bash
# Create repo-specific configs
cp config/default/config.yaml config/repo1.yaml
# Edit repo1.yaml for specific needs
cf --config config/repo1.yaml index /path/to/repo1
```

## Output and Logging

### Verbose Mode

Get detailed output during processing:

```bash
cf --verbose index /path/to/repo
```

### Artifact Directories

CodeFusion creates timestamped artifact directories:

```
artifacts_myproject_20240315_143022/
├── kb/
│   ├── entities.json
│   ├── relationships.json
│   └── embeddings.pkl
└── myproject_config.yaml
```

### Log Files

Check logs for troubleshooting:

```bash
# View recent activity
tail -f ~/.codefusion/logs/codefusion.log

# Search for errors
grep ERROR ~/.codefusion/logs/codefusion.log
```

## Integration with IDEs

### VS Code Integration

Create a VS Code task:

```json
// .vscode/tasks.json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "CodeFusion Index",
            "type": "shell",
            "command": "cf",
            "args": ["index", "${workspaceFolder}"],
            "group": "build",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            }
        }
    ]
}
```

### Shell Aliases

Create convenient aliases:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias cfi='cf index'
alias cfq='cf query'
alias cfe='cf explore'
alias cfs='cf stats'

# Usage
cfi /path/to/repo
cfq "How does login work?"
```

## Troubleshooting

### Common Issues

**Command not found:**
```bash
# Check installation
which cf
pip list | grep codefusion

# Reinstall if needed
pip install --upgrade codefusion
```

**Permission errors:**
```bash
# Check file permissions
ls -la /path/to/repo

# Run with appropriate permissions
sudo cf index /path/to/repo  # Not recommended
```

**Configuration errors:**
```bash
# Validate configuration
cf --config config.yaml stats

# Check configuration syntax
python3.11 -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

**Memory issues:**
```bash
# Monitor memory usage
cf --verbose index /path/to/large/repo

# Adjust configuration for large repos
# Increase max_file_size or add exclusions
```

### Debug Mode

Enable detailed debugging:

```bash
export CF_DEBUG=1
cf index /path/to/repo
```

### Performance Profiling

Profile command execution:

```bash
time cf index /path/to/repo

# With memory profiling
/usr/bin/time -v cf index /path/to/repo
```

## Next Steps

- Learn about [Configuration](configuration.md)
- See [Usage Examples](examples.md)
- Check the [API Reference](../reference/cli.md)