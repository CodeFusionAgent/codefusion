# Usage Examples

This page provides practical examples of using CodeFusion for different scenarios and use cases.

## Basic Usage Examples

### 1. Quick Repository Analysis

```bash
# Index a small repository quickly
cf index /path/to/my-project

# Ask basic questions
cf query "What is the main entry point?"
cf query "How many Python files are there?"
cf query "What external dependencies are used?"
```

### 2. Comprehensive Code Exploration

```bash
# Full exploration with detailed analysis
cf explore /path/to/large-project

# Ask complex questions
cf query "How does the authentication system work?"
cf query "What design patterns are used in this codebase?"
cf query "How would I add a new API endpoint?"
```

### 3. Repository Statistics

```bash
# Get knowledge base statistics
cf stats

# Get statistics for specific repository
cf stats --repo-path /path/to/project
```

## Language-Specific Examples

### Python Project Analysis

```bash
# Index a Python project
cf index /path/to/python-project

# Python-specific questions
cf query "What Flask routes are defined?"
cf query "How is database connectivity handled?"
cf query "What testing framework is used?"
cf query "Are there any Django models defined?"
cf query "How does error handling work?"
```

**Example Output:**
```
🔍 Analysis Results:

Flask routes found in app.py:
- @app.route('/api/users', methods=['GET', 'POST'])
- @app.route('/api/auth/login', methods=['POST'])
- @app.route('/api/data/<int:id>', methods=['GET'])

Database connectivity:
- SQLAlchemy ORM used in models.py
- Connection string in config.py
- Database initialization in app/__init__.py
```

### JavaScript/Node.js Project

```bash
# Index a JavaScript project
cf index /path/to/js-project

# JavaScript-specific questions
cf query "What Express.js middlewares are used?"
cf query "How is API routing structured?"
cf query "What React components are defined?"
cf query "How is state management handled?"
cf query "What build tools are configured?"
```

### Java Project Analysis

```bash
# Index a Java project
cf index /path/to/java-project

# Java-specific questions
cf query "What Spring Boot controllers exist?"
cf query "How is dependency injection configured?"
cf query "What JPA entities are defined?"
cf query "How is exception handling implemented?"
cf query "What Maven dependencies are used?"
```

## Strategy-Specific Examples

### ReAct Strategy (Default)

Best for iterative exploration and general understanding:

```bash
# Use ReAct for balanced analysis
cf query --strategy react "Explain the overall architecture"
cf query --strategy react "How do I run tests?"
cf query --strategy react "What's the deployment process?"
```

**When to use ReAct:**
- General code understanding
- Interactive exploration
- Balanced speed and depth
- Unknown codebase exploration

### Plan-then-Act Strategy

Best for systematic analysis and step-by-step procedures:

```bash
# Use Plan-Act for systematic analysis
cf query --strategy plan_act "How do I set up this project locally?"
cf query --strategy plan_act "What's the complete CI/CD pipeline?"
cf query --strategy plan_act "How do I contribute to this project?"
```

**When to use Plan-Act:**
- Setup and installation guides
- Systematic code analysis
- Process documentation
- Step-by-step procedures

### Sense-then-Act Strategy

Best for complex codebases and pattern discovery:

```bash
# Use Sense-Act for complex analysis
cf query --strategy sense_act "What architectural patterns are used?"
cf query --strategy sense_act "How is security implemented?"
cf query --strategy sense_act "What performance optimizations exist?"
```

**When to use Sense-Act:**
- Large, complex codebases
- Pattern discovery
- Security analysis
- Performance investigation

## Configuration Examples

### Development Configuration

```yaml
# dev-config.yaml - Fast analysis for development
llm_model: "gpt-3.5-turbo"
kb_type: "vector"
exploration_strategy: "react"
max_exploration_depth: 3

excluded_dirs:
  - ".git"
  - "node_modules"
  - "__pycache__"
  - "venv"

excluded_extensions:
  - ".pyc"
  - ".log"
  - ".tmp"
```

```bash
cf --config dev-config.yaml index /path/to/project
```

### Production Analysis Configuration

```yaml
# prod-config.yaml - Thorough analysis
llm_model: "gpt-4"
kb_type: "neo4j"
neo4j_uri: "bolt://localhost:7687"
neo4j_user: "neo4j"
neo4j_password: "password"
exploration_strategy: "plan_act"
max_exploration_depth: 10
```

```bash
cf --config prod-config.yaml explore /path/to/complex-project
```

## Real-World Scenarios

### Scenario 1: Onboarding to a New Project

```bash
# Step 1: Get project overview
cf explore /path/to/new-project

# Step 2: Understand the technology stack
cf query "What technologies and frameworks are used?"

# Step 3: Find setup instructions
cf query "How do I set up the development environment?"

# Step 4: Understand the project structure
cf query "What is the overall project structure?"

# Step 5: Find the main entry points
cf query "What are the main entry points and how do I run the application?"
```

### Scenario 2: Code Review and Analysis

```bash
# Index the repository
cf index /path/to/review-project

# Check for security issues
cf query "Are there any potential security vulnerabilities?"

# Analyze code quality
cf query "What code quality issues should I be aware of?"

# Check testing coverage
cf query "How comprehensive is the test coverage?"

# Look for architectural concerns
cf query "Are there any architectural anti-patterns?"
```

### Scenario 3: Refactoring Planning

```bash
# Analyze current architecture
cf query --strategy sense_act "What is the current architecture?"

# Identify dependencies
cf query "What are the main dependencies between components?"

# Find coupling issues
cf query "Where is the code tightly coupled?"

# Identify refactoring opportunities
cf query "What parts of the code would benefit from refactoring?"
```

### Scenario 4: API Documentation Generation

```bash
# Index the API project
cf index /path/to/api-project

# Find all API endpoints
cf query "What API endpoints are available?"

# Get endpoint details
cf query "What are the parameters and responses for each endpoint?"

# Understand authentication
cf query "How does API authentication work?"

# Find rate limiting
cf query "Is there rate limiting implemented?"
```

### Scenario 5: Migration Planning

```bash
# Analyze legacy codebase
cf explore /path/to/legacy-project

# Understand current technology stack
cf query "What technologies need to be migrated?"

# Identify migration challenges
cf query "What are the main challenges for migration?"

# Find external dependencies
cf query "What external services and APIs are used?"

# Plan migration strategy
cf query "What would be a good migration strategy?"
```

## Batch Processing Examples

### Process Multiple Repositories

```bash
#!/bin/bash
# batch-analyze.sh

repositories=(
    "/path/to/repo1"
    "/path/to/repo2"
    "/path/to/repo3"
)

for repo in "${repositories[@]}"; do
    echo "Processing $repo..."
    cf index "$repo"
    
    # Generate standard analysis
    cf query --repo-path "$repo" "What is the main technology stack?" > "${repo##*/}-analysis.txt"
    cf query --repo-path "$repo" "What are the main entry points?" >> "${repo##*/}-analysis.txt"
    cf query --repo-path "$repo" "How is testing structured?" >> "${repo##*/}-analysis.txt"
    
    echo "Completed $repo"
done
```

### Configuration-Based Batch Processing

```bash
#!/bin/bash
# config-batch.sh

configs=(
    "config/python-analysis.yaml"
    "config/javascript-analysis.yaml"
    "config/java-analysis.yaml"
)

repo_path="/path/to/multi-language-project"

for config in "${configs[@]}"; do
    echo "Running analysis with $config..."
    cf --config "$config" index "$repo_path"
    
    # Run language-specific queries
    language=$(basename "$config" .yaml | cut -d'-' -f1)
    cf --config "$config" query "What $language specific patterns are used?" > "$language-analysis.txt"
done
```

## Integration Examples

### VS Code Integration

Create `.vscode/tasks.json`:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "CodeFusion: Index Project",
            "type": "shell",
            "command": "cf",
            "args": ["index", "${workspaceFolder}"],
            "group": "build",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            },
            "problemMatcher": []
        },
        {
            "label": "CodeFusion: Project Stats",
            "type": "shell",
            "command": "cf",
            "args": ["stats"],
            "group": "build",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            },
            "problemMatcher": []
        }
    ]
}
```

### Git Hooks Integration

Create `.git/hooks/post-commit`:

```bash
#!/bin/bash
# Re-index after commits

echo "Re-indexing codebase after commit..."
cf index .
echo "Indexing complete!"
```

### CI/CD Integration

```yaml
# .github/workflows/code-analysis.yml
name: Code Analysis with CodeFusion

on:
  pull_request:
    branches: [ main ]

jobs:
  analyze:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install CodeFusion
      run: pip install codefusion
    
    - name: Analyze codebase
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: |
        cf index .
        cf query "What are the main changes in this codebase?" > analysis.txt
        cf query "Are there any potential issues?" >> analysis.txt
    
    - name: Upload analysis
      uses: actions/upload-artifact@v3
      with:
        name: code-analysis
        path: analysis.txt
```

## Performance Examples

### Large Repository Analysis

```bash
# For repositories with 10k+ files
cf --config large-repo-config.yaml index /path/to/large-repo

# Use sense-act for better handling of complexity
cf query --strategy sense_act "What are the main architectural components?"
```

**large-repo-config.yaml:**
```yaml
kb_type: "neo4j"
exploration_strategy: "sense_act"
max_exploration_depth: 15
max_file_size: 5242880  # 5MB

excluded_dirs:
  - ".git"
  - "node_modules"
  - "vendor"
  - "third_party"
  - "build"
  - "dist"
  - "coverage"
  - "logs"
  - "__pycache__"
```

### Memory-Constrained Environment

```yaml
# memory-efficient-config.yaml
kb_type: "text"  # Minimal memory usage
exploration_strategy: "react"
max_exploration_depth: 3
max_file_size: 524288  # 512KB

excluded_dirs:
  - ".git"
  - "node_modules"
  - "__pycache__"
  - "build"
  - "dist"
```

```bash
cf --config memory-efficient-config.yaml index /path/to/repo
```

## Troubleshooting Examples

### Debug Configuration Issues

```bash
# Test configuration
cf --config my-config.yaml --verbose stats

# Validate YAML
python3.11 -c "import yaml; print(yaml.safe_load(open('my-config.yaml')))"

# Check Neo4j connection
cf query "test" 2>&1 | grep -i neo4j
```

### Performance Debugging

```bash
# Monitor memory usage
time cf --verbose index /path/to/repo

# Profile with detailed timing
CF_DEBUG=1 cf index /path/to/repo
```

### Common Error Solutions

**API Key Issues:**
```bash
# Check if API key is set
echo $OPENAI_API_KEY

# Test with simple query
cf query "hello world"
```

**Memory Issues:**
```bash
# Use text-based KB for large repos
cf --config text-kb-config.yaml index /path/to/large/repo
```

**Neo4j Connection Issues:**
```bash
# Test Neo4j connectivity
curl http://localhost:7474
neo4j status
```

## Next Steps

- Learn about [Configuration](configuration.md)
- Read the [CLI Reference](../reference/cli.md)
- Check [Advanced Configuration](../config/reference.md)