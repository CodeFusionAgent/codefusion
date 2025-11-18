# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CodeFusion is an **AI-powered multi-agent system** for intelligent codebase exploration and analysis. It uses LLM-driven function calling and verbose logging to provide comprehensive technical narratives about how systems work.

## Current Architecture (Clean Structure)

### Directory Structure
```
cf/                           # Main Python package (clean architecture)
├── run/                     # CLI interface
│   └── main.py             # Entry point: python -m cf.run.main
├── agents/                  # Multi-agent system
│   ├── base.py             # Common agent functionality
│   ├── supervisor.py       # Orchestrates & synthesizes responses
│   ├── code.py             # Code analysis with LLM function calling
│   ├── docs.py             # Documentation processing
│   └── web.py              # Web search integration
├── tools/                   # Tool ecosystem for LLM function calling
│   ├── registry.py         # Schema management & tool dispatch
│   ├── repo_tools.py       # File system operations
│   ├── llm_tools.py        # AI-powered analysis tools
│   └── web_tools.py        # External search capabilities
├── llm/                     # LLM integration layer
│   └── client.py           # LiteLLM multi-provider interface
├── configs/                 # Configuration management
│   ├── config.yaml         # Main configuration file
│   └── config_mgr.py       # Configuration loading & validation
├── cache/                   # Persistent caching system
│   └── semantic.py         # Cross-session memory
├── trace/                   # Performance monitoring
│   └── tracer.py           # Execution tracing & metrics
└── utils/                   # Utilities
    └── logger.py           # Verbose logging system

docs/                        # Documentation
├── api/                    # API reference documentation
├── dev/                    # Development & architecture docs
├── usage/                  # User guides & examples
└── workflows/              # System workflow diagrams

Generated Data:
├── cf_cache/               # JSON cache files (auto-generated)
└── cf_trace/               # Execution traces (auto-generated)
```

### Core Components

**SupervisorAgent** (`cf/agents/supervisor.py`): 
- Orchestrates multiple specialized agents
- Synthesizes results using LLM
- Generates unified technical narratives

**Multi-Agent System**:
- **CodeAgent**: Analyzes source code using LLM function calling
- **DocsAgent**: Processes documentation and README files
- **WebAgent**: Integrates external knowledge via web search

**Tool Registry** (`cf/tools/registry.py`):
- Manages tool schemas for LLM function calling
- Dispatches tool execution to appropriate modules
- Handles parameter validation and error recovery

**LLM Integration** (`cf/llm/client.py`):
- LiteLLM multi-provider support (OpenAI, Anthropic, LLaMA)
- Function calling capabilities
- Graceful fallbacks and error handling

**Configuration System** (`cf/configs/`):
- YAML-based configuration with environment variable overrides
- Secure API key management
- Performance and behavior tuning

## Current System Features

### ✅ Working Features
- **Multi-Agent Coordination**: SupervisorAgent orchestrates 3 specialized agents
- **LLM Function Calling**: Dynamic tool selection with intelligent parameters
- **Verbose Logging**: Real-time visibility into agent decision making with ACTION PLANNING PHASE
- **Technical Narratives**: Comprehensive "Life of X" format responses
- **Response Time Tracking**: Accurate execution time measurement
- **Semantic Caching**: Persistent cross-session memory
- **Clean Package Structure**: Organized cf/ module with clear separation of concerns

### 🎯 Key Capabilities
- **Intelligent Tool Selection**: LLM chooses optimal tools based on context
- **Parallel Agent Execution**: Multiple agents work simultaneously where possible
- **Comprehensive Analysis**: Code + Documentation + External knowledge integration
- **Context-Aware Responses**: Each analysis builds on previous cached insights
- **Performance Monitoring**: Detailed tracing and metrics collection

## Usage Patterns

### Primary CLI Interface
```bash
# Main usage pattern with verbose logging
python -m cf.run.main --verbose ask /path/to/repo "How does routing work?"

# System shows complete workflow:
# 🤖 SupervisorAgent coordination
# 🎯 ACTION PLANNING PHASE for each agent
# 🔧 LLM function calling with tool selection
# 📊 Results synthesis and narrative generation
# ⏱️ Accurate response timing
```

### Configuration
```yaml
# cf/configs/config.yaml
llm:
  model: "gpt-4o"
  api_key: "your-openai-api-key"  # Or use OPENAI_API_KEY env var
  provider: "openai"
  max_tokens: 1000
  temperature: 0.7

agents:
  supervisor:
    enabled: true
    max_agents: 4
  code:
    enabled: true
    max_iterations: 20
  documentation:
    enabled: true
  web:
    enabled: true
```

### Programmatic Usage
```python
from cf.agents.supervisor import SupervisorAgent
from cf.configs.config_mgr import CfConfig

# Initialize system
config = CfConfig.load_from_file("cf/configs/config.yaml")
supervisor = SupervisorAgent("/path/to/repo", config)

# Perform analysis
result = supervisor.analyze("How does authentication work?")
print(result['narrative'])
print(f"Execution time: {result['execution_time']}s")
```

## Development Workflow

### Essential Commands

#### Installation & Setup
```bash
# Set up development environment (REQUIRED)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# Install development dependencies
pip install -e .[dev]

# Set up API key for testing
export OPENAI_API_KEY="your-openai-api-key"
```

#### Running Tests
```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_react_framework.py -v

# Run with coverage report
pytest --cov=cf --cov-report=html
```

#### Code Quality & Linting
```bash
# Format code
black cf/ tests/

# Sort imports
isort cf/ tests/

# Type checking
mypy cf/

# Linting
flake8 cf/ tests/

# Run all quality checks
black cf/ tests/ && isort cf/ tests/ && mypy cf/ && flake8 cf/ tests/
```

#### Main Application Commands
```bash
# Primary interface - verbose logging shows full workflow
python -m cf.run.main --verbose ask /path/to/repo "How does routing work?"

# Simple interface - for basic usage
codefusion analyze /path/to/repo
# Or using the short alias:
cf analyze /path/to/repo

# Test system functionality
python -m cf.run.main --verbose ask . "Test question"
```

#### Configuration Validation
```bash
# Check configuration loading
python -c "from cf.configs.config_mgr import ConfigManager; print('Config loaded successfully')"

# Verify LLM connectivity
python -c "from cf.llm.client import get_llm_client; print('LLM client initialized')"

# Test with custom config
python -m cf.run.main --config custom_config.yaml ask /path/to/repo "Test"
```

### Code Standards & Architecture
- **Python 3.10+** with type hints throughout
- **PEP 8** formatting enforced by black (line length: 88)
- **Absolute imports**: `from cf.module import Class`
- **Error handling** with proper exception management
- **Logging** via `cf/utils/logger.py` for verbose output
- **LLM function calling** for dynamic tool selection
- **Modular agents** in `cf/agents/` with clear separation of concerns

### Key Files to Understand
1. **`cf/run/main.py`** - CLI entry point and argument parsing
2. **`cf/agents/supervisor.py`** - Multi-agent orchestration logic  
3. **`cf/tools/registry.py`** - Tool management and LLM function calling
4. **`cf/llm/client.py`** - LLM integration and provider management
5. **`cf/configs/config_mgr.py`** - Configuration system

### Common Development Tasks

#### Adding New Tools
```bash
# 1. Create tool in appropriate module (cf/tools/)
# 2. Register in cf/tools/registry.py
# 3. Test with: python -m cf.run.main --verbose ask . "Test new tool"
```

#### Modifying Agents
```bash
# 1. Edit agent classes in cf/agents/
# 2. Run tests: pytest tests/test_agents.py -v
# 3. Test integration: python -m cf.run.main --verbose ask /path/to/repo "Test question"
```

#### Configuration Changes
```bash
# 1. Edit cf/configs/config.yaml
# 2. Or set environment variables: export CF_LLM_MODEL="gpt-4o"
# 3. Validate: python -c "from cf.configs.config_mgr import ConfigManager; print('OK')"
```

#### Debugging Issues
```bash
# Use verbose mode to see full workflow
python -m cf.run.main --verbose ask /path/to/repo "Debug question"

# Check trace files in cf_trace/ directory
ls -la cf_trace/

# Enable debug logging
export CF_LOG_LEVEL=DEBUG
```

## Current Status

✅ **Production Ready**: The system is stable and functional
✅ **Multi-Agent Coordination**: All agents work together seamlessly  
✅ **LLM Function Calling**: Dynamic tool selection is working
✅ **Verbose Logging**: Complete visibility into system operation
✅ **Technical Narratives**: Generates comprehensive "Life of X" responses
✅ **Caching System**: Persistent memory across sessions
✅ **Clean Architecture**: Well-organized package structure

The system provides intelligent, observable exploration that generates educational technical stories about how code systems work.