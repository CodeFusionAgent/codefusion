# CLI Commands

CodeFusion provides an **interactive, multi-agent command-line interface** for intelligent codebase exploration and analysis. The system features continuous question-answer sessions with persistent memory, adaptive response formats, and seamless web search integration.

## Overview

CodeFusion offers both **interactive sessions** and **single-question commands**:

```bash
# Interactive mode with persistent memory
python -m cf interactive /path/to/repo --session-dir ./my_sessions

# Single question with multi-agent coordination
python -m cf explore /path/to/repo "How does routing work?"

# Traditional analysis mode
python -m cf.run.simple_run analyze /path/to/repo --focus=all
```

## Adaptive Response Formats

CodeFusion's innovation is **intelligent response format detection** that automatically selects the optimal format based on your question type:

### 🎯 Journey Format (Life of X)
For process flows and system architecture:
- "How does authentication work?"
- "What happens when a user logs in?"
- "How is data processed?"

### 🔍 Comparison Format  
For performance analysis and technical trade-offs:
- "async def vs def performance implications?"
- "FastAPI vs Django differences?"
- "SQLite vs PostgreSQL for this use case?"

### 📚 Explanation Format
For conceptual questions and configurations:
- "What is dependency injection?"
- "How to configure Docker for production?"

**Key Features:**
- 🧠 **LLM-Powered Format Detection**: Automatically selects optimal response format
- 🤖 **Multi-Agent Coordination**: Uses 1-3 specialized agents based on complexity
- 🌐 **Web Search Integration**: External knowledge woven naturally into responses
- 💾 **Session Memory**: Remembers context across questions in interactive mode

## Global Options

These options are available for all commands:

```bash
python -m cf.run.simple_run [OPTIONS] COMMAND [ARGS]...

Global Options:
  --config, -c PATH         Configuration file path
  --session-dir PATH        Directory for saving session data (default: ./cf_sessions)
  --verbose, -v            Enable verbose output  
  --help                   Show help message
```

## Commands

### `interactive` - Interactive Session Mode ⭐ **PRIMARY COMMAND**

Start a continuous question-answer session with persistent memory and context building.

```bash
python -m cf interactive [OPTIONS] REPO_PATH
```

**Arguments:**
- `REPO_PATH`: Path to the repository to explore

**Options:**
- `--session-dir PATH`: Directory to save session data (default: ./cf_sessions)

**Examples:**
```bash
# Start interactive session with default session directory
python -m cf interactive /tmp/fastapi_test

# Start session with custom session directory  
python -m cf interactive /tmp/fastapi_test --session-dir ./my_sessions

# Session example:
# You: How does FastAPI routing work?
# 🤖 [Journey format response with routing flow...]
# 
# You: What about async def vs def performance?
# 🤖 [Comparison format response, remembers routing context...]
# 
# You: exit
# Session saved to: ./my_sessions/fastapi_test_session_20240115_143025.json
```

### `explore` - Single Question Analysis

Ask a single question with automatic multi-agent coordination and adaptive response format.

```bash
python -m cf explore [OPTIONS] REPO_PATH QUESTION
```

**Arguments:**
- `REPO_PATH`: Path to the repository to explore
- `QUESTION`: Question to ask (any type - system will detect optimal format)

**Examples:**
```bash
# Journey format - process flow questions
python -m cf explore /tmp/fastapi_test "How does authentication work?"
# Output: 🎯 Life of Authentication: A Journey Through the System

# Comparison format - performance questions  
python -m cf explore /tmp/fastapi_test "async def vs def performance implications?"
# Output: 🔍 Technical Comparison Analysis: async def vs def

# Explanation format - conceptual questions
python -m cf explore /tmp/fastapi_test "What is dependency injection?"
# Output: 📚 Conceptual explanation format

# Automatic multi-agent coordination (3 agents for complex questions)
python -m cf explore /tmp/fastapi_test "Explain the relationship between FastAPI and Starlette"
# 🤖 Agents used: 3 | Code analysis, documentation, web search
```

**Sample Journey Output:**
```
🎯 Life of Routing: A Journey Through the System
======================================================================

🏗️ **Architecture & Flow:** When an HTTP request arrives at `/api/users/{user_id}`, 
FastAPI's routing system springs into action. The journey begins in main.py where the 
FastAPI application instance routes the request through its internal ASGI middleware 
stack, ultimately reaching the path operation function that handles user retrieval.

🛤️ **Technical Flow:** The process follows this path:
   **1. Request Reception:** FastAPI receives the HTTP request and parses the URL path 
   **2. Route Matching:** The router in routing.py:156 matches `/api/users/{user_id}` pattern
   **3. Path Parameter Extraction:** FastAPI extracts `user_id` from the URL path
   **4. Handler Execution:** The get_user() function in api/users.py:45 processes the request

💻 **Code Examples:** Implementation details:
   • In main.py:23: @app.get('/api/users/{user_id}') async def get_user(user_id: int)
   • In api/users.py:45: return await UserService.get_by_id(user_id)

📈 ⏱️  Response time: 28.3s | 🤖 Agents used: 3 | 💾 Cache hits: 2
```

**Sample Comparison Output:**
```
🔍 Technical Comparison Analysis: async def vs def performance implications
======================================================================

📉 **Analysis:** In FastAPI applications, the choice between `async def` and `def` 
for path operation functions significantly impacts performance and concurrency handling.

⚖️ **Key Comparisons:**

   **Performance:**
   • async def: Non-blocking I/O operations, handles 1000+ concurrent requests efficiently
   • def: Blocking operations, limited to thread pool size (~40 concurrent requests)
   • Recommendation: Use async def for I/O-heavy operations, def for CPU-intensive tasks

💻 **Code Examples:**
   • async def get_user(user_id: int): return await db.fetch_user(user_id)  # Non-blocking
   • def get_user_sync(user_id: int): return db.fetch_user_sync(user_id)    # Blocking

🎯 **Conclusion:** Use async def for I/O operations and def for CPU-intensive tasks

📈 **Analysis Confidence:** 92.5%
```

### `ask` - Ask a Question (alias for explore)

Ask a natural language question about a codebase and receive a Life of X narrative.

```bash
python -m cf.run.simple_run ask [OPTIONS] REPO_PATH QUESTION
```

**Arguments:**
- `REPO_PATH`: Path to the repository
- `QUESTION`: Question to ask about the code

**Examples:**
```bash
# Ask about testing
python -m cf.run.simple_run ask /path/to/repo "What testing frameworks are used?"

# Ask about deployment
python -m cf.run.simple_run ask /path/to/repo "How is this application deployed?"
```

### `continue` - Continue Life of X Narrative

Continue exploring by building on previous Life of X investigations to create connected architectural stories.

```bash
python -m cf.run.simple_run continue [OPTIONS] REPO_PATH QUESTION --previous PREVIOUS_QUESTION
```

**Arguments:**
- `REPO_PATH`: Path to the repository
- `QUESTION`: New question to explore
- `--previous`: Previous question that was explored

**Examples:**
```bash
# Continue from authentication to sessions
python -m cf.run.simple_run continue /path/to/repo "How are user sessions managed?" --previous "How does authentication work?"

# Continue from API to validation
python -m cf.run.simple_run continue /path/to/repo "How is input validation handled?" --previous "What are the main API endpoints?"

# Continue from data processing to storage
python -m cf.run.simple_run continue /path/to/repo "How is data persisted?" --previous "How is data processed?"
```

### `analyze` - Traditional Multi-Agent Analysis

Perform comprehensive multi-agent analysis using the ReAct framework (traditional mode).

```bash
python -m cf.run.simple_run analyze [OPTIONS] REPO_PATH
```

**Arguments:**
- `REPO_PATH`: Path to the repository to analyze

**Options:**
- `--focus {all,docs,code_arch}`: Analysis focus (default: all)

**Examples:**
```bash
# Comprehensive multi-agent analysis
python -m cf.run.simple_run analyze /path/to/repository --focus=all

# Documentation-focused analysis
python -m cf.run.simple_run analyze /path/to/repository --focus=docs

# Code and architecture analysis
python -m cf.run.simple_run analyze /path/to/repository --focus=code_arch
```

### `summary` - Show Analysis Summary

Display a summary of analysis performed on a repository.

```bash
python -m cf.run.simple_run summary [OPTIONS] REPO_PATH
```

**Arguments:**
- `REPO_PATH`: Path to the repository

**Examples:**
```bash
# Show analysis summary
python -m cf.run.simple_run summary /path/to/repository

# Verbose summary
python -m cf.run.simple_run --verbose summary /path/to/repository
```

## ReAct Framework Process

### How it Works

CodeFusion follows the **ReAct (Reasoning + Acting) pattern**:

1. **🧠 REASON**: AI analyzes current state and determines next action
2. **🎯 ACT**: Execute specialized tools based on reasoning
3. **👁️ OBSERVE**: Process results and update understanding
4. **🔄 ITERATE**: Continue until goals are achieved

### Multi-Agent Coordination

The supervisor agent orchestrates specialized agents:

- **📚 Documentation Agent**: Analyzes README files, guides, and documentation
- **💻🏗️ Code Architecture Agent**: Examines source code, functions, patterns, and system design

### Example Analysis Flow

```bash
$ python -m cf.run.simple_run analyze /path/to/repo --focus=all

🤖 CodeFusion - Multi-Agent Analysis
==================================================
✅ Ready to explore: my-project

🔍 Analyzing with focus: all
------------------------------

📋 Analysis Summary:
Supervisor Coordination Summary:
• Coordinated 2 agents
• Generated 2 cross-agent insights
• Documentation agent: Successfully completed analysis
• Code architecture agent: Successfully completed analysis
• Cross-agent insights: documentation_code_consistency, architecture_code_alignment
• Total cache hits: 8

⏱️  Execution Time: 4.23s (6 iterations)
```

## Configuration Integration

### Environment Variables

Configure the ReAct framework using environment variables:

```bash
# ReAct Loop Configuration
export CF_REACT_MAX_ITERATIONS=25
export CF_REACT_ITERATION_TIMEOUT=45.0
export CF_REACT_TOTAL_TIMEOUT=900.0

# LLM Integration
export CF_LLM_MODEL=gpt-4
export CF_LLM_API_KEY=your-api-key

# Caching Configuration
export CF_REACT_CACHE_ENABLED=true
export CF_REACT_CACHE_MAX_SIZE=1000

# Run analysis
python -m cf.run.simple_run analyze /path/to/repo --focus=all
```

### Configuration Files

Use YAML configuration files:

```yaml
# config.yaml
react:
  max_iterations: 25
  iteration_timeout: 45.0
  total_timeout: 900.0
  cache_enabled: true
  cache_max_size: 1000

llm:
  model: "gpt-4"
  api_key: "your-api-key"
  max_tokens: 1500
  temperature: 0.3
```

```bash
# Use configuration file
python -m cf.run.simple_run --config config.yaml analyze /path/to/repo
```

## LLM Integration

### Supported Providers

CodeFusion supports multiple LLM providers via LiteLLM:

```bash
# OpenAI
export CF_LLM_MODEL=gpt-4
export CF_LLM_API_KEY=your-openai-key

# Anthropic Claude
export CF_LLM_MODEL=claude-3-sonnet-20240229
export CF_LLM_API_KEY=your-anthropic-key

# LLaMA via Together AI
export CF_LLM_MODEL=together_ai/meta-llama/Llama-2-7b-chat-hf
export CF_LLM_API_KEY=your-together-ai-key

# LLaMA via Ollama
export CF_LLM_MODEL=ollama/llama2
```

### Installing LLM Support

```bash
# Install LiteLLM for full LLM support
pip install litellm

# Framework works without LLM but with reduced capabilities
python -m cf.run.simple_run analyze /path/to/repo --focus=all
```

## Advanced Usage

### Performance Tuning

```bash
# Fast analysis (fewer iterations)
CF_REACT_MAX_ITERATIONS=10 python -m cf.run.simple_run analyze /repo

# Thorough analysis (more iterations)
CF_REACT_MAX_ITERATIONS=50 python -m cf.run.simple_run analyze /repo

# Custom cache size for large repositories
CF_REACT_CACHE_MAX_SIZE=2000 python -m cf.run.simple_run analyze /repo
```

### Debugging and Monitoring

```bash
# Enable detailed tracing
CF_REACT_TRACING_ENABLED=true CF_REACT_TRACE_DIR=./traces python -m cf.run.simple_run analyze /repo

# View trace files
ls -la ./traces/
cat ./traces/trace_*_supervisor.json

# Enable verbose debugging
CF_REACT_LOG_LEVEL=DEBUG python -m cf.run.simple_run --verbose analyze /repo
```

### Focus Options

Target specific analysis areas:

```bash
# Documentation quality and coverage
python -m cf.run.simple_run analyze /repo --focus=docs

# Code patterns, security, and architecture
python -m cf.run.simple_run analyze /repo --focus=code_arch

# Complete multi-agent analysis
python -m cf.run.simple_run analyze /repo --focus=all
```

## Demo Script

Use the demo script for interactive exploration:

```bash
# Run demo on any repository
python demo_cf_framework.py /path/to/repo

# Educational mode with explanations
python demo_cf_framework.py /path/to/repo --focus=all

# Quick focused demo
python demo_cf_framework.py /path/to/repo --focus=docs --no-concepts

# Self-analysis (analyze CodeFusion itself)
python demo_cf_framework.py --self-analysis

# Show framework comparison
python demo_cf_framework.py --show-comparison

# Show usage examples
python demo_cf_framework.py --show-usage
```

## Integration Examples

### Shell Aliases

Create convenient aliases:

```bash
# Add to ~/.bashrc or ~/.zshrc
alias cf-analyze='python -m cf.run.simple_run analyze'
alias cf-explore='python -m cf.run.simple_run explore'
alias cf-demo='python demo_cf_framework.py'

# Usage
cf-analyze /path/to/repo --focus=all
cf-explore /path/to/repo "How does auth work?"
cf-demo /path/to/repo
```

### Batch Analysis

```bash
#!/bin/bash
# analyze-multiple-repos.sh

REPOS=(
    "/path/to/repo1"
    "/path/to/repo2"
    "/path/to/repo3"
)

for repo in "${REPOS[@]}"; do
    echo "Analyzing: $repo"
    python -m cf.run.simple_run analyze "$repo" --focus=all
    echo "---"
done
```

### CI/CD Integration

```yaml
# .github/workflows/code-analysis.yml
name: CodeFusion Analysis
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install CodeFusion
        run: |
          pip install -e .
          pip install litellm
      
      - name: Run Analysis
        env:
          CF_LLM_MODEL: gpt-3.5-turbo
          CF_LLM_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m cf.run.simple_run analyze . --focus=all
```

## Troubleshooting

### Common Issues

**Import errors:**
```bash
# Check installation
python -c "import cf; print('CodeFusion installed')"

# Reinstall if needed
pip install -e .
```

**LLM connection issues:**
```bash
# Test without LLM
python -m cf.run.simple_run analyze /repo --focus=code

# Install LLM support
pip install litellm

# Verify API key
echo $CF_LLM_API_KEY
```

**Performance issues:**
```bash
# Reduce iterations for faster analysis
CF_REACT_MAX_ITERATIONS=10 python -m cf.run.simple_run analyze /repo

# Disable caching for testing
CF_REACT_CACHE_ENABLED=false python -m cf.run.simple_run analyze /repo
```

### Debug Output

Enable detailed logging:

```bash
# Python logging
CF_REACT_LOG_LEVEL=DEBUG python -m cf.run.simple_run --verbose analyze /repo

# Save debug output
python -m cf.run.simple_run --verbose analyze /repo 2>&1 | tee debug.log
```

## Next Steps

- Learn about [Configuration](configuration.md)
- See [Usage Examples](examples.md) 
- Check the [ReAct Framework Guide](../react-framework.md)
- Explore the [API Reference](../api/index.md)