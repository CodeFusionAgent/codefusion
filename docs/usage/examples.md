# Usage Examples

This page shows practical examples of using CodeFusion for code exploration.

## Basic Exploration

### Explore Authentication

```bash
# Start with a broad question
cf explore /path/to/webapp "How does authentication work?"

# Continue with specific questions
cf continue /path/to/webapp "How are passwords validated?" --previous "How does authentication work?"

# Explore session management
cf continue /path/to/webapp "How are user sessions managed?" --previous "How are passwords validated?"
```

### Explore API Structure

```bash
# Understand API endpoints
cf explore /path/to/api "What are the main API endpoints?"

# Dive into validation
cf continue /path/to/api "How is input validation handled?" --previous "What are the main API endpoints?"

# Check error handling
cf continue /path/to/api "How are API errors handled?" --previous "How is input validation handled?"
```

## Common Investigation Patterns

### Understanding New Codebase

```bash
# Start with architecture overview
cf explore /path/to/project "What is the overall architecture?"

# Explore main entry points
cf continue /path/to/project "How does the application start up?" --previous "What is the overall architecture?"

# Check configuration
cf continue /path/to/project "How is the application configured?" --previous "How does the application start up?"
```

### Debugging Issues

```bash
# Explore error handling
cf explore /path/to/project "How are errors handled and logged?"

# Check testing approach
cf continue /path/to/project "What testing strategies are used?" --previous "How are errors handled and logged?"

# Understand deployment
cf continue /path/to/project "How is the application deployed?" --previous "What testing strategies are used?"
```

## Advanced Usage

### Configuration for Large Repositories

```bash
# Create optimized config for large repos
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
  - "vendor"
  - "target"
EOF

# Use optimized config
cf --config large-repo-config.yaml explore /path/to/large/repo "How does the core system work?"
```

### Batch Exploration

```bash
#!/bin/bash
# Explore multiple related questions
REPO="/path/to/project"
QUESTIONS=(
    "How does authentication work?"
    "What are the main API endpoints?"
    "How is data validation handled?"
    "What testing frameworks are used?"
    "How is the application deployed?"
)

for question in "${QUESTIONS[@]}"; do
    echo "Exploring: $question"
    cf explore "$REPO" "$question"
    echo "---"
done
```

### Building Understanding Incrementally

```bash
# Start broad
cf explore /path/to/ecommerce "What is the overall architecture?"

# Narrow down to specific domains
cf continue /path/to/ecommerce "How does the shopping cart work?" --previous "What is the overall architecture?"

# Get specific implementation details
cf continue /path/to/ecommerce "How are cart items persisted?" --previous "How does the shopping cart work?"

# Explore related functionality
cf continue /path/to/ecommerce "How does checkout process work?" --previous "How are cart items persisted?"
```

## Language-Specific Examples

### Python Projects

```bash
# Explore Python project structure
cf explore /path/to/python/project "How is the package structure organized?"

# Check dependency management
cf continue /path/to/python/project "How are dependencies managed?" --previous "How is the package structure organized?"

# Understand testing
cf continue /path/to/python/project "How are tests organized and run?" --previous "How are dependencies managed?"
```

### JavaScript/Node.js Projects

```bash
# Explore Node.js application
cf explore /path/to/node/app "How is the Express.js application structured?"

# Check middleware
cf continue /path/to/node/app "What middleware is used?" --previous "How is the Express.js application structured?"

# Explore frontend build
cf continue /path/to/node/app "How is the frontend built and served?" --previous "What middleware is used?"
```

### Web Applications

```bash
# Explore web app architecture
cf explore /path/to/webapp "How is the MVC pattern implemented?"

# Check database interactions
cf continue /path/to/webapp "How does the application interact with the database?" --previous "How is the MVC pattern implemented?"

# Explore frontend integration
cf continue /path/to/webapp "How is the frontend integrated with the backend?" --previous "How does the application interact with the database?"
```

## Performance Tips

### Effective Questions

**Good questions:**
- "How does authentication work?"
- "What are the main API endpoints?"
- "How is data stored and retrieved?"
- "What testing strategies are used?"

**Less effective questions:**
- "Tell me about this code" (too vague)
- "What is line 42 in file.py?" (too specific)
- "Is this code good?" (subjective)

### Exploration Strategies

**Start broad, then narrow:**
```bash
# 1. Get overview
cf explore /path/to/repo "What is the overall architecture?"

# 2. Focus on area of interest
cf continue /path/to/repo "How does the authentication system work?" --previous "What is the overall architecture?"

# 3. Get implementation details
cf continue /path/to/repo "How are JWT tokens validated?" --previous "How does the authentication system work?"
```

**Use the cache effectively:**
```bash
# Related questions benefit from cache
cf explore /path/to/repo "How does authentication work?"
cf continue /path/to/repo "How are user sessions managed?" --previous "How does authentication work?"
cf continue /path/to/repo "How are passwords validated?" --previous "How are user sessions managed?"
```

## Integration Examples

### VS Code Integration

Create a VS Code task:

```json
// .vscode/tasks.json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "CodeFusion Explore",
            "type": "shell",
            "command": "cf",
            "args": ["explore", "${workspaceFolder}", "${input:question}"],
            "group": "build",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            }
        }
    ],
    "inputs": [
        {
            "id": "question",
            "description": "Question to explore",
            "default": "How does authentication work?",
            "type": "promptString"
        }
    ]
}
```

### Shell Aliases

Add to your `.bashrc` or `.zshrc`:

```bash
# CodeFusion aliases
alias cfx='cf explore'
alias cfa='cf ask'
alias cfc='cf continue'
alias cfs='cf summary'

# Usage
cfx /path/to/repo "How does login work?"
cfa /path/to/repo "What are the API endpoints?"
cfc /path/to/repo "How is validation handled?" --previous "What are the API endpoints?"
```

## Troubleshooting Examples

### Common Issues

**Slow exploration:**
```bash
# Create performance config
cat > fast-config.yaml << 'EOF'
max_file_size: 524288  # 512KB
max_exploration_depth: 3
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "dist"
  - "build"
EOF

cf --config fast-config.yaml explore /path/to/repo "How does X work?"
```

**Permission issues:**
```bash
# Check permissions
ls -la /path/to/repo

# Fix if needed
chmod -R 755 /path/to/repo
```

**Configuration errors:**
```bash
# Test configuration
cf --config my-config.yaml summary /path/to/repo

# Validate YAML
python -c "import yaml; yaml.safe_load(open('my-config.yaml'))"
```

## LLM Function Calling Examples

### Basic LLM-Driven Exploration

```bash
# LLM selects optimal tools for FastAPI exploration
python -m cf.run.simple_run explore /path/to/fastapi "How does request routing work?"

# LLM-powered architectural analysis
python -m cf.run.simple_run explore /path/to/project "Life of an API Request"

# Dynamic tool selection based on context
python -m cf.run.simple_run explore /path/to/microservices "How do services communicate?"
```

### LLM Function Calling with Life of X Narratives

```bash
# Generate technical architectural stories
python -m cf.run.simple_run explore /path/to/webapp "Life of User Authentication"

# Follow data through the system
python -m cf.run.simple_run explore /path/to/ecommerce "Life of a Shopping Cart Item"

# Trace request flows
python -m cf.run.simple_run explore /path/to/api "Life of a Database Query"
```

### Configuration for LLM Function Calling

```yaml
# llm-config.yaml
llm:
  model: "claude-3-sonnet-20240229"  # or gpt-4, together_ai/meta-llama/...
  api_key: "${CF_LLM_API_KEY}"
  max_tokens: 2000
  temperature: 0.7
  provider: "anthropic"

# ReAct agent settings
agents:
  code_architecture:
    llm_reasoning_enabled: true
    llm_function_calling_enabled: true
    fallback_to_hardcoded: true
```

### Environment Variables for LLM Integration

```bash
# OpenAI Configuration
export CF_LLM_MODEL=gpt-4
export CF_LLM_API_KEY=your-openai-api-key

# Anthropic Configuration  
export CF_LLM_MODEL=claude-3-sonnet-20240229
export CF_LLM_API_KEY=your-anthropic-api-key

# LLaMA via Together AI
export CF_LLM_MODEL=together_ai/meta-llama/Llama-2-7b-chat-hf
export CF_LLM_API_KEY=your-together-ai-key

# Run with LLM function calling
python -m cf.run.simple_run explore /path/to/repo "How does authentication work?"
```

### Advanced LLM Function Calling Examples

```bash
# Complex architectural analysis with LLM tool selection
python -m cf.run.simple_run explore /path/to/distributed/system "How does the system handle distributed transactions?"

# LLM-driven security analysis
python -m cf.run.simple_run explore /path/to/webapp "How are security vulnerabilities prevented?"

# Performance analysis with intelligent tool selection
python -m cf.run.simple_run explore /path/to/high/traffic/app "How does the system handle high load?"
```

## Multi-Agent Framework Examples

### Comprehensive Repository Analysis

```bash
# Run comprehensive multi-agent analysis with LLM function calling
python -m cf.run.simple_run analyze /path/to/repo --focus=all

# Focus on specific areas with LLM-driven tool selection
python -m cf.run.simple_run analyze /path/to/repo --focus=docs
python -m cf.run.simple_run analyze /path/to/repo --focus=code_arch
```

### Advanced Multi-Agent Workflows

```bash
# Full comprehensive analysis
cf analyze /path/to/large/project --focus all

# Documentation-focused analysis
cf analyze /path/to/project --focus docs

# Code structure analysis
cf analyze /path/to/project --focus code

# Architecture mapping
cf analyze /path/to/project --focus arch
```

### Configuration for Multi-Agent System

```yaml
# multi-agent-config.yaml
agents:
  supervisor:
    enabled: true
    max_agents: 6
    timeout: 600  # 10 minutes
    
  documentation:
    enabled: true
    file_types: [".md", ".rst", ".txt", ".adoc", ".wiki"]
    max_files: 100
    
  codebase:
    enabled: true
    languages: ["python", "javascript", "typescript", "java", "go", "rust", "c", "cpp", "kotlin", "swift"]
    max_files: 500
    
  architecture:
    enabled: true
    diagram_types: ["mermaid", "plantuml", "graphviz", "drawio"]
    max_components: 200
    
  summary:
    enabled: true
    max_sections: 15
    cheat_sheet_format: "markdown"

error_recovery:
  enabled: true
  max_retries: 5
  circuit_breaker_threshold: 8
  loop_detection_window: 15
```

### Usage with Custom Configuration

```bash
# Use custom multi-agent config
cf --config multi-agent-config.yaml analyze /path/to/enterprise/repo

# Generate comprehensive documentation
cf --config multi-agent-config.yaml analyze /path/to/repo --focus docs > project-analysis.md

# Architecture mapping for complex systems
cf --config multi-agent-config.yaml analyze /path/to/microservices --focus arch
```

### Integration with CI/CD

```yaml
# .github/workflows/codefusion-analysis.yml
name: CodeFusion Analysis
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install CodeFusion
        run: pip install codefusion
      - name: Run Multi-Agent Analysis
        run: |
          cf analyze . --focus all > analysis-report.md
          cf analyze . --focus code > code-structure.md
      - name: Upload Analysis
        uses: actions/upload-artifact@v3
        with:
          name: codefusion-analysis
          path: |
            analysis-report.md
            code-structure.md
```

### Error Recovery Examples

```bash
# Enable verbose error reporting
cf --verbose analyze /path/to/complex/repo

# Custom error recovery settings
cat > error-config.yaml << 'EOF'
error_recovery:
  enabled: true
  max_retries: 3
  circuit_breaker_threshold: 5
  loop_detection_window: 10
agents:
  supervisor:
    timeout: 300
EOF

cf --config error-config.yaml analyze /path/to/repo
```

## Next Steps

- Learn about [CLI Commands](cli.md)
- Understand [Configuration](configuration.md)
- Check the [Installation Guide](../installation/setup.md)
- Explore [Multi-Agent Architecture](../dev/architecture.md)