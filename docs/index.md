# CodeFusion Documentation

CodeFusion is an **AI-powered multi-agent system** for intelligent codebase exploration and analysis. The system uses LLM function calling and verbose logging to provide comprehensive technical narratives about how systems work.

## 🎯 Current System Overview

CodeFusion provides detailed analysis through:

- **🤖 MULTI-AGENT COORDINATION**: SupervisorAgent orchestrates specialized agents
- **🔧 LLM FUNCTION CALLING**: AI dynamically selects tools with parameters  
- **📝 VERBOSE LOGGING**: Real-time visibility into agent decision making
- **📖 TECHNICAL NARRATIVES**: Comprehensive architectural overviews
- **⏱️ PERFORMANCE TRACKING**: Accurate execution time measurement

This creates intelligent, observable exploration that generates educational technical stories.

## 🚀 Current Features

- **Multi-Agent System**: SupervisorAgent, CodeAgent, DocsAgent, WebAgent coordination
- **LLM Function Calling**: Dynamic tool selection with intelligent parameter generation  
- **Verbose Logging**: Action planning phases and tool selection visibility
- **Technical Narratives**: Architectural overview generation with "Life of X" format
- **Response Time Tracking**: Accurate execution timing (fixed from 0.0s issue)
- **Tool Ecosystem**: `scan_directory`, `read_file`, `search_files`, `analyze_code`, `web_search`
- **LiteLLM Integration**: Multi-provider support (OpenAI, Anthropic, LLaMA)
- **Configuration Management**: YAML config with environment variable support

## 🔄 Current System Flow

CodeFusion follows this multi-agent process:

1. **📝 SUPERVISOR COORDINATION**: Orchestrates 3 specialized agents
2. **🎯 AGENT PLANNING**: Each agent shows ACTION PLANNING PHASE reasoning  
3. **🔧 LLM FUNCTION CALLING**: AI selects tools with dynamic parameters
4. **📊 RESULT SYNTHESIS**: SupervisorAgent consolidates insights into narrative
5. **⏱️ PERFORMANCE TRACKING**: Accurate timing and metrics reporting

### Current System Example

```bash
$ python -m cf.run.main --verbose ask /tmp/fastapi "How does routing work?"

🔍 [SupervisorAgent] Running code analysis agent...
🎯 [CodeAgent] ACTION PLANNING PHASE  
🎯 [CodeAgent] LLM selected tool: search_files
📋 [CodeAgent] Tool arguments: {'pattern': 'routing', 'file_types': ['*.py']}

📚 [SupervisorAgent] Running documentation agent...
🎯 [DocsAgent] ACTION PLANNING PHASE
🎯 [DocsAgent] LLM selected tool: search_files
📋 [DocsAgent] Tool arguments: {'pattern': 'routing', 'file_types': ['*.md']}

🌐 [SupervisorAgent] Running web search agent...
🎯 [WebAgent] ACTION PLANNING PHASE
🎯 [WebAgent] LLM selected tool: web_search
📋 [WebAgent] Tool arguments: {'query': 'FastAPI routing implementation'}

🤖 Consolidating results with LLM...
🎯 Life of FastAPI: Routing Architecture
======================================================================
🏗️ **Architectural Overview:** [Detailed technical narrative...]
⏱️ Response time: 30.4s
```

## 🎯 Quick Start

Get started with CodeFusion analysis:

```bash
# 1. Setup environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# 2. Configure API key
export OPENAI_API_KEY="your-openai-api-key"
# OR edit cf/configs/config.yaml

# 3. Run analysis with verbose logging  
python -m cf.run.main --verbose ask /path/to/repo "How does routing work?"
python -m cf.run.main --verbose ask /tmp/fastapi "Explain FastAPI and Starlette relationship"
python -m cf.run.main --verbose ask /path/to/repo "What specific responsibilities does X handle?"

# 4. Check execution details
# System shows:
# - Agent coordination and planning phases
# - LLM tool selection with parameters  
# - Real-time progress and results
# - Accurate response time measurement
```

## 📚 Documentation Structure

This documentation is organized into several sections:

- **[Installation](installation/setup.md)**: Get CodeFusion up and running
- **[Usage](usage/cli.md)**: Learn how to use the ReAct framework
- **[Configuration](usage/configuration.md)**: Configure LLM integration and performance
- **[ReAct Framework](react-framework.md)**: Comprehensive framework documentation
- **[API Reference](api/index.md)**: Complete API documentation
- **[Development](dev/architecture.md)**: Architecture and contribution guide

## 🏗️ Life of X Architecture

CodeFusion implements a sophisticated Life of X narrative generation system:

```
cf/
├── core/                       # ReAct Foundation
│   ├── react_agent.py         # Base ReAct agent with R→A→O loops
│   ├── react_config.py        # Performance and LLM configuration
│   └── react_tracing.py       # Execution monitoring and metrics
├── agents/                     # Specialized ReAct Agents
│   ├── react_supervisor_agent.py      # Multi-agent orchestration + Life of X generation
│   ├── react_documentation_agent.py   # Documentation analysis
│   └── react_code_architecture_agent.py # Combined code & architecture analysis
├── llm/                        # LLM Integration + Life of X System
│   ├── real_llm.py            # LiteLLM provider integration
│   ├── prompt_templates.py    # Template-based prompt system
│   ├── response_parser.py     # Unified response parsing
│   └── simple_llm.py          # Fallback reasoning
├── tools/                      # Tool Ecosystem + Narrative Utilities
│   ├── advanced_tools.py      # 8 specialized exploration tools
│   └── narrative_utils.py     # Life of X narrative generation utilities
└── run/
    └── simple_run.py           # Life of X CLI interface
```

## 🆚 Life of X vs Traditional Approaches

### ❌ Traditional Static Analysis
- One-time parsing of entire codebase
- Static analysis without context
- Limited reasoning about findings
- No adaptive exploration
- Fast but shallow, misses context
- **No architectural storytelling**

### ✅ Life of X Approach
- **Architectural storytelling** that follows features through entire systems
- **Narrative-driven exploration** that generates educational stories
- AI-powered reasoning and decision making
- Multi-agent collaborative analysis
- Adaptive exploration that learns from observations
- Goal-oriented loops with progress tracking
- Persistent caching across sessions
- Comprehensive error recovery
- **Template-based prompts** for consistent high-quality narratives

## 🤝 Contributing

We welcome contributions to the CodeFusion Life of X framework! Contributions should enhance the narrative generation capabilities:

1. **Enhance Life of X Narratives**: Improve architectural storytelling quality
2. **Maintain ReAct Principles**: Preserve the Reason → Act → Observe pattern
3. **Add Narrative Templates**: Create templates for different story types
4. **Add Specialized Agents**: Create domain-specific analysis agents
5. **Extend Tool Ecosystem**: Add new tools for enhanced capabilities
6. **Improve LLM Integration**: Support additional providers and models
7. **Enhance Error Recovery**: Strengthen resilience and fault tolerance

See [Contributing Guide](dev/contributing.md) for detailed information.

## 📄 License

CodeFusion is released under the Apache License 2.0. See [LICENSE](https://github.com/CodeFusionAgent/codefusion/blob/main/LICENSE) for details.

## 🆘 Support & Resources

- 📖 [Complete Documentation](https://codefusionagent.github.io/codefusion/)
- 🧠 [ReAct Framework Guide](react-framework.md)
- 🔧 [API Reference](api/index.md)
- 💬 [GitHub Issues](https://github.com/CodeFusionAgent/codefusion/issues)
- 🐛 [Bug Reports](https://github.com/CodeFusionAgent/codefusion/issues/new?template=bug_report.md)
- 💡 [Feature Requests](https://github.com/CodeFusionAgent/codefusion/issues/new?template=feature_request.md)

---

*Built on the ReAct pattern for systematic, intelligent code exploration through reasoning, acting, and observing.*