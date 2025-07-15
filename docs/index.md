# CodeFusion Documentation

CodeFusion is a powerful code understanding tool designed for senior developers to quickly ramp up on large codebases. It provides agentic exploration capabilities, semantic search, and comprehensive analysis of code repositories.

## 🚀 Key Features

- **Agentic Exploration**: Intelligent code exploration using ReAct, Plan-then-Act, and Sense-then-Act strategies
- **Multi-Backend Knowledge Base**: Support for Neo4j graph database and vector databases for semantic search
- **LLM Integration**: Comprehensive reasoning with support for OpenAI, Anthropic, and other LLM providers
- **Advanced Analysis**: Deep code relationship detection and architectural pattern analysis
- **Interactive CLI**: Intuitive command-line interface for repository exploration and querying
- **Flexible Configuration**: Extensive configuration options for different use cases

## 🏗️ Architecture Overview

CodeFusion consists of several key components:

- **ACI (Agent Computer Interface)**: System interaction layer for file system, environment, and repository access
- **Knowledge Base**: Dual-backend storage supporting both graph (Neo4j) and vector (FAISS) databases
- **Indexer**: Code analysis and entity extraction with relationship detection
- **Agents**: Reasoning agents for different exploration strategies
- **LLM Integration**: Large language model integration for natural language understanding

## 🎯 Quick Start

Get started with CodeFusion in just a few commands:

```bash
# Install CodeFusion
pip install codefusion

# Index a repository
cf index /path/to/your/repo

# Ask questions about the code
cf query "How does authentication work in this codebase?"

# Full exploration workflow
cf explore /path/to/your/repo
```

## 📚 Documentation Structure

This documentation is organized into several sections:

- **[Installation](installation/quickstart.md)**: Get CodeFusion up and running
- **[Usage](usage/cli.md)**: Learn how to use CodeFusion effectively
- **[Configuration](config/overview.md)**: Customize CodeFusion for your needs
- **[Development](dev/contributing.md)**: Contribute to CodeFusion development
- **[Reference](reference/api.md)**: Detailed API and CLI reference

## 🛠️ Supported Languages

CodeFusion supports analysis of multiple programming languages:

- **Python** - Full AST analysis, import detection, class/function extraction
- **JavaScript/TypeScript** - Module analysis, function detection, framework support
- **Java** - Package structure analysis, class hierarchy detection
- **C/C++** - Header analysis, function extraction
- **Go** - Package analysis, function detection
- **Rust** - Crate analysis, module structure

## 🔧 Integration Options

CodeFusion integrates with various tools and services:

- **Neo4j** - Graph database for complex relationship analysis
- **Vector Databases** - FAISS for semantic similarity search
- **LLM Providers** - OpenAI, Anthropic, and other compatible APIs
- **Development Tools** - Git integration, testing frameworks, CI/CD pipelines

## 🤝 Contributing

We welcome contributions to CodeFusion! Please see our [Contributing Guide](dev/contributing.md) for details on how to get started.

## 📄 License

CodeFusion is released under the Apache License 2.0. See [LICENSE](https://github.com/CodeFusionAgent/codefusion/blob/main/LICENSE) for details.

## 🆘 Support

- 📖 [Documentation](https://codefusionagent.github.io/codefusion/)
- 💬 [GitHub Issues](https://github.com/CodeFusionAgent/codefusion/issues)
- 🐛 [Bug Reports](https://github.com/CodeFusionAgent/codefusion/issues/new?template=bug_report.md)
- 💡 [Feature Requests](https://github.com/CodeFusionAgent/codefusion/issues/new?template=feature_request.md)