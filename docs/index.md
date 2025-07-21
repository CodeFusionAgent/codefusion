# CodeFusion ReAct Framework Documentation

CodeFusion is a comprehensive **ReAct (Reasoning + Acting) agent framework** for intelligent code exploration and analysis. **The primary innovation is the "Life of X" narrative system** that generates compelling architectural stories following features through entire systems - similar to "Life of a Search Query in Google".

## 🎯 Life of X Philosophy

CodeFusion transforms code exploration through architectural storytelling:

- **📖 NARRATIVE**: Generate compelling stories that follow features through entire systems
- **🧠 REASON**: AI-powered analysis of current state and goal progress
- **🎯 ACT**: Execute specialized tools based on reasoning
- **👁️ OBSERVE**: Process results and update understanding
- **🔄 REPEAT**: Continue until architectural story is complete

This creates intelligent, narrative-driven exploration that generates educational architectural stories.

## 🚀 Key Features

- **Life of X Narratives**: **PRIMARY FEATURE** - Generate architectural stories like "Life of a Search Query in Google"
- **Multi-Agent Architecture**: Specialized agents for documentation and code/architecture analysis
- **Template-Based Prompts**: Sophisticated prompt templates for different narrative types
- **Unified Response Parsing**: Schema-based parsing for consistent LLM responses
- **AI-Powered Reasoning**: LLM-driven decision making and goal tracking
- **Rich Tool Ecosystem**: 8 specialized tools for comprehensive code exploration
- **Persistent Caching**: Cross-session memory with TTL and LRU eviction
- **Execution Tracing**: Performance monitoring and comprehensive logging
- **Error Recovery**: Circuit breakers, retry logic, and fallback strategies
- **LLM Integration**: Support for OpenAI, Anthropic, and LLaMA via LiteLLM

## 🔄 Life of X Process Flow

CodeFusion follows the systematic **Reason → Act → Observe** cycle to generate architectural narratives:

1. **🧠 REASONING**: AI analyzes question and determines exploration strategy
2. **🎯 ACTING**: Execute specialized tools to gather system insights
3. **👁️ OBSERVING**: Process results and extract architectural patterns
4. **📖 NARRATING**: Generate compelling "Life of X" architectural story

### Life of X Generation Example

```
Question: "How does authentication work?"

🤖 Supervisor Agent: Orchestrates narrative generation
├── 📚 Documentation Agent: Reason → Search auth docs → Observe API patterns
└── 💻🏗️ Code Architecture Agent: Reason → Scan auth/ directory → Observe JWT implementation & security patterns

📖 Life of X Narrative: "Life of Authentication"
🛤️ The Journey: Login → Validation → Token Generation → Secure Storage
🏗️ Key Components: AuthController, UserService, JWTGenerator, CookieManager
```

## 🎯 Quick Start

Get started with CodeFusion's Life of X narrative generation:

```bash
# Install CodeFusion
pip install -e .

# Install LLM support (optional but recommended)
pip install litellm

# Generate Life of X architectural narratives
python -m cf.run.simple_run explore /path/to/repo "How does authentication work?"
python -m cf.run.simple_run ask /path/to/repo "What happens when a user logs in?"
python -m cf.run.simple_run explore /path/to/repo "How is data processed?"

# Continue narrative exploration
python -m cf.run.simple_run continue /path/to/repo "How is the response sent back?" --previous "How does authentication work?"

# Traditional multi-agent analysis
python -m cf.run.simple_run analyze /path/to/repo --focus=all

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