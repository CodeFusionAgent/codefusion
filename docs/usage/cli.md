# CLI Commands

CodeFusion provides an **AI-powered command-line interface** for intelligent codebase analysis using multi-agent coordination and verbose logging.

## Current Command Interface

```bash
# Main command interface with verbose logging
python -m cf.run.main --verbose ask /path/to/repo "How does routing work?"

# Example with detailed output showing agent activity
python -m cf.run.main --verbose ask /tmp/fastapi "Explain FastAPI and Starlette relationship"
```

## System Features

### 🤖 **Multi-Agent Coordination**
- **SupervisorAgent**: Orchestrates all agents and synthesizes responses
- **CodeAgent**: Analyzes source code using LLM function calling
- **DocsAgent**: Processes documentation and README files
- **WebAgent**: Integrates web search for external knowledge

### 📝 **Verbose Logging System**
- **Action Planning Phases**: Shows agent reasoning process
- **Tool Selection Logging**: Displays LLM tool choices with parameters
- **Progress Tracking**: Real-time visibility into system activity
- **Response Time Measurement**: Accurate execution timing

### 🔧 **LLM Function Calling**
- **Dynamic Tool Selection**: LLM chooses optimal tools based on context
- **Conversation History**: Multi-turn dialogue with context preservation
- **Available Tools**: `scan_directory`, `read_file`, `search_files`, `analyze_code`, `web_search`

## Current Commands

### `ask` - Main Analysis Command ⭐ **PRIMARY COMMAND**

Ask a question about a codebase and receive detailed technical analysis with verbose logging.

```bash
python -m cf.run.main [OPTIONS] ask REPO_PATH QUESTION
```

**Arguments:**
- `REPO_PATH`: Path to the repository to analyze
- `QUESTION`: Natural language question about the codebase

**Options:**
- `--verbose, -v`: Enable detailed verbose logging (RECOMMENDED)
- `--config, -c PATH`: Configuration file path

**Examples:**
```bash
# Basic analysis with verbose logging
python -m cf.run.main --verbose ask /tmp/fastapi "How does routing work?"

# Analyze framework relationships
python -m cf.run.main --verbose ask /path/to/repo "Explain the relationship between FastAPI and Starlette"

# Understand system architecture
python -m cf.run.main --verbose ask /path/to/repo "What specific responsibilities does Starlette handle?"
```

## Complete Working Example

### Input Command
```bash
python -m cf.run.main --verbose ask /tmp/fastapi "Explain the relationship between FastAPI and Starlette. What specific responsibilities does Starlette handle?"
```

### Detailed Output
```bash
🚀 CodeFusion - Ask
📁 /tmp/fastapi | 🤖 code, docs, web
==================================================
📝 [SupervisorAgent] Processing: Explain the relationship between FastAPI and Starlette...

🧠 [SupervisorAgent] Analyzing question and building context...
🤖 [SupervisorAgent] Coordinating multiple specialized agents...
🔍 [SupervisorAgent] Running code analysis agent...
🎯 [CodeAgent] ACTION PLANNING PHASE
💭 [CodeAgent] Based on reasoning: Since there are no code files found yet, the first step is to identify and explore...
🔧 [CodeAgent] Using LLM function calling for intelligent tool selection
📡 [CodeAgent] Calling LLM with function calling enabled...
🎯 [CodeAgent] LLM selected tool: search_files
📋 [CodeAgent] Tool arguments: {'pattern': 'FastAPI', 'file_types': ['*.py'], 'max_results': 5}
📡 [CodeAgent] Calling LLM with function calling enabled...
🎯 [CodeAgent] LLM selected tool: search_documentation
📋 [CodeAgent] Tool arguments: {'topic': 'FastAPI', 'framework': 'FastAPI'}
✅ [SupervisorAgent] Code analysis completed
📚 [SupervisorAgent] Running documentation agent...
🎯 [DocsAgent] ACTION PLANNING PHASE
💭 [DocsAgent] Based on reasoning: Analyzing documentation files to understand the system architecture...
🔧 [DocsAgent] Using LLM function calling for intelligent tool selection
📡 [DocsAgent] Calling LLM with function calling enabled...
🎯 [DocsAgent] LLM selected tool: search_files
📋 [DocsAgent] Tool arguments: {'pattern': 'FastAPI and Starlette', 'file_types': ['md', 'txt'], 'max_results': 3}
✅ [SupervisorAgent] Documentation analysis completed
🌐 [SupervisorAgent] Running web search agent...
🎯 [WebAgent] ACTION PLANNING PHASE
💭 [WebAgent] Based on reasoning: Searching the web for external documentation and related information...
🔧 [WebAgent] Using LLM function calling for intelligent tool selection
📡 [WebAgent] Calling LLM with function calling enabled...
🎯 [WebAgent] LLM selected tool: web_search
📋 [WebAgent] Tool arguments: {'query': 'relationship between FastAPI and Starlette responsibilities', 'max_results': 5}
✅ [SupervisorAgent] Web search completed
🤖 Consolidating results with LLM...
============================================================
✅ [SupervisorAgent] Integrated 6 insights into narrative

🎯 Life of FastAPI: The Role of Starlette
======================================================================

🏗️ **Architectural Overview:** When a developer decides to use FastAPI for building a web application, 
the journey begins with FastAPI itself, which is a modern, fast (high-performance), web framework for 
building APIs with Python 3.6+ based on standard Python type hints. The underlying technology that 
FastAPI relies on is Starlette, a lightweight ASGI (Asynchronous Server Gateway Interface) framework. 
Starlette handles several core responsibilities that are critical for the operation of FastAPI. The entry 
point for handling HTTP requests in FastAPI typically involves the `FastAPI` class, which is defined in 
a FastAPI-specific file but leverages Starlette's routing and ASGI capabilities. FastAPI uses Starlette's 
capabilities to manage HTTP requests, responses, WebSocket support, and background tasks. For example, 
when an HTTP request is made to a FastAPI endpoint, Starlette's built-in routing system directs the 
request to the appropriate endpoint defined in the FastAPI application. This routing mechanism is 
responsible for efficiently managing and directing requests. The actual request handling logic is 
facilitated by FastAPI, which builds on Starlette's robust ASGI infrastructure. Once a request is 
handled, Starlette further assists in managing responses through its middleware and exception handling 
features, completing the lifecycle of a request in this framework.

📊 **Analysis Confidence:** 75.0%
🤖 **Powered by:** gpt-4o
🎯 **Agents used:** 3
💡 This unified narrative traces the complete journey of how your
   question flows through interconnected system components.
⏱️  Response time: 30.4s
```

## Configuration

### Configuration File

Edit `cf/configs/config.yaml`:

```yaml
# LLM settings
llm:
  model: "gpt-4o"
  api_key: "your-openai-api-key"  # Or use OPENAI_API_KEY env var
  max_tokens: 1000
  temperature: 0.7
  provider: "openai"

# Agent settings  
agents:
  supervisor:
    enabled: true
    max_agents: 4
    timeout: 300
  
  documentation:
    enabled: true
    file_types: [".md", ".rst", ".txt"]
    
  codebase:
    enabled: true
    languages: ["python", "javascript", "typescript", "java"]
```

### Environment Variables

```bash
# API key (recommended method)
export OPENAI_API_KEY="your-openai-api-key"

# Alternative model configuration
export CF_LLM_MODEL="gpt-4o"
export CF_LLM_MAX_TOKENS=1000
```

## System Requirements

- Python 3.10+
- Virtual environment (`.venv` recommended)
- Valid OpenAI API key or other LLM provider
- `litellm` package for LLM integration

## Troubleshooting

### Common Issues

**API Key Problems:**
```bash
# Check if API key is set
echo $OPENAI_API_KEY

# Test API key validity
python -c "import openai; print('API key works')"
```

**Import Errors:**
```bash
# Verify installation
python -c "import cf; print('CodeFusion installed')"

# Reinstall if needed
pip install -e .
```

**LiteLLM Issues:**
```bash
# Install/reinstall LiteLLM
pip install --upgrade litellm

# Enable debug mode
python -c "import litellm; litellm._turn_on_debug()"
```
