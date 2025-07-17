# CodeFusion ReAct Framework Documentation

CodeFusion is a comprehensive **ReAct (Reasoning + Acting) agent framework** for intelligent code exploration and analysis. It enables multi-agent, LLM-powered systematic investigation of codebases through sophisticated reasoning, tool usage, and observation cycles.

## 🎯 ReAct Philosophy

CodeFusion implements the ReAct pattern for systematic code analysis:

- **🧠 REASON**: AI-powered analysis of current state and goal progress
- **🎯 ACT**: Execute specialized tools based on reasoning
- **👁️ OBSERVE**: Process results and update understanding
- **🔄 REPEAT**: Continue until goals are achieved

This creates intelligent, adaptive exploration that learns from observations and adjusts strategy dynamically.

## 🚀 Key Features

- **Multi-Agent Architecture**: Specialized agents for documentation, code, and architecture analysis
- **AI-Powered Reasoning**: LLM-driven decision making and goal tracking
- **Rich Tool Ecosystem**: 8 specialized tools for comprehensive code exploration
- **Persistent Caching**: Cross-session memory with TTL and LRU eviction
- **Execution Tracing**: Performance monitoring and comprehensive logging
- **Error Recovery**: Circuit breakers, retry logic, and fallback strategies
- **LLM Integration**: Support for OpenAI, Anthropic, and LLaMA via LiteLLM

## 🔄 ReAct Process Flow

CodeFusion follows the systematic **Reason → Act → Observe** cycle:

1. **🧠 REASONING**: AI analyzes current state, goal progress, and available context
2. **🎯 ACTING**: Execute planned actions using specialized tools
3. **👁️ OBSERVING**: Process results, extract insights, and update understanding
4. **🔄 ITERATING**: Adapt exploration strategy based on findings

### Multi-Agent ReAct Example

```
Goal: "Comprehensive analysis of authentication system"

🤖 Supervisor Agent: Activates specialized agents based on focus
├── 📚 Documentation Agent: Reason → Search auth docs → Observe API patterns
├── 💻 Codebase Agent: Reason → Scan auth/ directory → Observe JWT implementation
└── 🏗️ Architecture Agent: Reason → Map auth flow → Observe security patterns

🔗 Cross-Agent Synthesis: Combine insights for comprehensive understanding
```

## 🎯 Quick Start

Get started with CodeFusion ReAct framework:

```bash
# Install CodeFusion
pip install -e .

# Install LLM support (optional but recommended)
pip install litellm

# Multi-agent comprehensive analysis
python -m cf.run.simple_run analyze /path/to/repo --focus=all

# Documentation-focused analysis
python -m cf.run.simple_run analyze /path/to/repo --focus=docs

# Question-based exploration
python -m cf.run.simple_run explore /path/to/repo "How does authentication work?"

# Demo the framework
python demo_cf_framework.py /path/to/repo
```

## 📚 Documentation Structure

This documentation is organized into several sections:

- **[Installation](installation/setup.md)**: Get CodeFusion up and running
- **[Usage](usage/cli.md)**: Learn how to use the ReAct framework
- **[Configuration](usage/configuration.md)**: Configure LLM integration and performance
- **[ReAct Framework](react-framework.md)**: Comprehensive framework documentation
- **[API Reference](api/index.md)**: Complete API documentation
- **[Development](dev/architecture.md)**: Architecture and contribution guide

## 🏗️ ReAct Framework Architecture

CodeFusion implements a sophisticated multi-agent ReAct architecture:

```
cf/
├── core/                       # ReAct Foundation
│   ├── react_agent.py         # Base ReAct agent with R→A→O loops
│   ├── react_config.py        # Performance and LLM configuration
│   └── react_tracing.py       # Execution monitoring and metrics
├── agents/                     # Specialized ReAct Agents
│   ├── react_supervisor_agent.py      # Multi-agent orchestration
│   ├── react_documentation_agent.py   # Documentation analysis
│   ├── react_codebase_agent.py       # Source code analysis
│   └── react_architecture_agent.py   # System design analysis
├── llm/                        # LLM Integration
│   ├── real_llm.py            # LiteLLM provider integration
│   └── simple_llm.py          # Fallback reasoning
├── tools/                      # Tool Ecosystem
│   └── advanced_tools.py      # 8 specialized exploration tools
└── run/
    └── simple_run.py           # Multi-agent CLI interface
```

## 🆚 ReAct vs Traditional Approaches

### ❌ Traditional Static Analysis
- One-time parsing of entire codebase
- Static analysis without context
- Limited reasoning about findings
- No adaptive exploration
- Fast but shallow, misses context

### ✅ ReAct Framework Approach
- AI-powered reasoning and decision making
- Multi-agent collaborative analysis
- Adaptive exploration that learns from observations
- Goal-oriented loops with progress tracking
- Persistent caching across sessions
- Comprehensive error recovery

## 🤝 Contributing

We welcome contributions to the CodeFusion ReAct framework! Contributions should enhance the ReAct pattern implementation:

1. **Maintain ReAct Principles**: Preserve the Reason → Act → Observe pattern
2. **Add Specialized Agents**: Create domain-specific analysis agents
3. **Extend Tool Ecosystem**: Add new tools for enhanced capabilities
4. **Improve LLM Integration**: Support additional providers and models
5. **Enhance Error Recovery**: Strengthen resilience and fault tolerance

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