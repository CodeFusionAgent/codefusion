# Interactive Sessions

**Note**: Interactive session functionality is now integrated into the SupervisorAgent and CLI in the clean architecture.

Interactive sessions are now handled through the clean command-line interface and persistent caching.

## Current Implementation

Interactive capabilities are provided through:

### CLI Interface (`cf/run/main.py`)

```bash
# Interactive analysis with persistent memory
python -m cf.run.main --verbose ask /path/to/repo "How does routing work?"

# Follow-up questions benefit from cached analysis
python -m cf.run.main --verbose ask /path/to/repo "What about error handling?"
```

### SupervisorAgent Coordination

```python
from cf.agents.supervisor import SupervisorAgent
from cf.configs.config_mgr import CfConfig

# Create supervisor for interactive-like sessions
config = CfConfig.load_from_file("cf/configs/config.yaml")
supervisor = SupervisorAgent("/path/to/repo", config)

# Each analysis builds on previous context through caching
result1 = supervisor.analyze("How does authentication work?")
result2 = supervisor.analyze("What about authorization?")  # Benefits from cached insights
```

### Persistent Memory (`cf/cache/semantic.py`)

The framework provides persistent memory through semantic caching:

```python
from cf.cache.semantic import SemanticCache

# Cache automatically stores and retrieves analysis results
cache = SemanticCache()

# Similar questions use cached insights for faster, more comprehensive responses
```

## Interactive Features

### Multi-Turn Conversations

While there's no explicit session manager, the caching system provides continuity:

```bash
# First question - full analysis
python -m cf.run.main --verbose ask /repo "Explain the architecture"

# Follow-up questions leverage cached knowledge
python -m cf.run.main --verbose ask /repo "How does the routing layer work?"
python -m cf.run.main --verbose ask /repo "What about the database layer?"
```

### Context Building

Each analysis contributes to the knowledge base:

1. **Repository Structure**: Cached after first exploration
2. **Code Patterns**: Identified patterns are remembered
3. **Documentation Insights**: README and docs analysis is cached
4. **Web Knowledge**: External research is cached for reuse

### Multi-Agent Coordination

The SupervisorAgent provides interactive-like coordination:

```python
# Supervisor intelligently selects agents per question
supervisor = SupervisorAgent("/path/to/repo", config)

# Code-focused question - primarily uses CodeAgent
code_result = supervisor.analyze("Find the main application entry point")

# Documentation question - primarily uses DocsAgent  
docs_result = supervisor.analyze("What does the README say about installation?")

# Best practices question - uses WebAgent
web_result = supervisor.analyze("What are FastAPI performance best practices?")
```

## Session-Like Workflow

### Programmatic Session Pattern

```python
from cf.agents.supervisor import SupervisorAgent
from cf.configs.config_mgr import CfConfig

class InteractiveAnalysis:
    def __init__(self, repo_path: str):
        self.config = CfConfig.load_from_file("cf/configs/config.yaml")
        self.supervisor = SupervisorAgent(repo_path, self.config)
        self.session_history = []
    
    def ask(self, question: str):
        """Ask a question with session context."""
        result = self.supervisor.analyze(question)
        
        # Store in session history
        self.session_history.append({
            "question": question,
            "result": result,
            "timestamp": time.time()
        })
        
        return result
    
    def get_session_summary(self):
        """Get summary of session questions and insights."""
        return {
            "questions_asked": len(self.session_history),
            "total_insights": sum(len(r["result"].get("insights", [])) for r in self.session_history),
            "agents_used": set(r["result"].get("agents_consulted", []) for r in self.session_history)
        }

# Usage
session = InteractiveAnalysis("/path/to/repo")
result1 = session.ask("How does the application start?")
result2 = session.ask("What are the main API endpoints?") 
result3 = session.ask("How is authentication handled?")

summary = session.get_session_summary()
```

### CLI Session Pattern

```bash
#!/bin/bash
# session.sh - Interactive analysis script

REPO_PATH="/path/to/repo"

echo "🚀 Starting CodeFusion Interactive Session"
echo "Repository: $REPO_PATH"
echo

# Initial architecture overview
echo "📋 Getting architecture overview..."
python -m cf.run.main --verbose ask "$REPO_PATH" "Provide an overview of the system architecture"

echo
echo "🔍 Analyzing core components..."
python -m cf.run.main --verbose ask "$REPO_PATH" "What are the main components and their responsibilities?"

echo  
echo "🌐 Checking API structure..."
python -m cf.run.main --verbose ask "$REPO_PATH" "How are the API endpoints organized?"

echo
echo "✅ Session complete - all analysis cached for future use"
```

## Migration Guide

If migrating from an explicit InteractiveSessionManager:

```python
# Old way (no longer available)  
# from cf.core.interactive_session import InteractiveSessionManager
# session_manager = InteractiveSessionManager(repo, config)

# New way (clean architecture)
from cf.agents.supervisor import SupervisorAgent
supervisor = SupervisorAgent("/path/to/repo", config)

# Interactive-like usage through repeated calls
# (benefits from automatic caching)
result = supervisor.analyze("Your question here")
```

## Advantages of Current Approach

1. **Simpler Architecture**: No complex session state management
2. **Automatic Caching**: Persistent memory without explicit session handling
3. **Stateless Operations**: Each call is independent but benefits from cache
4. **CLI Integration**: Works seamlessly with command-line workflows
5. **Multi-Agent Coordination**: Intelligent agent selection per question

For complete documentation, see the [main API index](index.md).