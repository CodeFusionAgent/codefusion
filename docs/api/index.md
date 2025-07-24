# API Reference

Welcome to the CodeFusion API documentation. This section provides comprehensive documentation for the current working multi-agent system with LLM function calling.

## Core Components

### Multi-Agent System

- **[SupervisorAgent](supervisor-agent.md)** - Orchestrates agents and synthesizes responses
- **[CodeAgent](#code-agent)** - Code analysis using LLM function calling loops
- **[DocsAgent](#docs-agent)** - Documentation analysis and processing  
- **[WebAgent](#web-agent)** - Web search integration

### Infrastructure

- **[BaseAgent](#base-agent)** - Common agent functionality and LLM integration
- **[ToolRegistry](#tool-registry)** - Function calling schema management
- **[LLM Integration](llm.md)** - LiteLLM and multi-provider support
- **[Configuration](config.md)** - YAML configuration and environment variables

## Quick API Examples

### Current Multi-Agent Analysis

```python
from cf.agents.supervisor import SupervisorAgent
from cf.config import CfConfig

# Initialize components
config = CfConfig.load_from_file("cf/configs/config.yaml")
supervisor = SupervisorAgent("/path/to/repository", config)

# Analyze with multi-agent coordination
result = supervisor.analyze("How does FastAPI routing work?")

# Access results
narrative = result['narrative']
confidence = result['confidence']
agents_used = result['agents_consulted']
insights = result['insights']
execution_time = result['execution_time']
```

### Using Individual Agents

```python
from cf.agents.code import CodeAgent
from cf.agents.docs import DocsAgent
from cf.agents.web import WebAgent

# Initialize agents
code_agent = CodeAgent("/path/to/repo", config)
docs_agent = DocsAgent("/path/to/repo", config)
web_agent = WebAgent("/path/to/repo", config)

# Run individual analysis
code_result = code_agent.analyze("Find FastAPI routing implementation")
docs_result = docs_agent.analyze("Look for routing documentation")
web_result = web_agent.analyze("Search for FastAPI routing best practices")
```

### Tool Registry Usage

```python
from cf.tools.registry import ToolRegistry

# Initialize tool registry
tools = ToolRegistry("/path/to/repo")

# Get available tool schemas for LLM function calling
schemas = tools.get_all_schemas()

# Execute specific tool
result = tools.use_tool("search_files", pattern="FastAPI", file_types=["*.py"])
```

### Traditional Multi-Agent Analysis

```python
# Run multi-agent analysis
results = supervisor.explore_repository(
    goal="analyze authentication system",
    focus="all"
)

# Access results
agent_results = supervisor.get_agent_results()
insights = supervisor.get_cross_agent_insights()
```

### Custom Agent Development

```python
from cf.core.react_agent import ReActAgent, ReActAction, ActionType

class CustomAnalysisAgent(ReActAgent):
    def reason(self) -> str:
        # Implement reasoning logic
        if not self.state.observations:
            return "Need to start analysis by scanning codebase"
        return "Continue with detailed examination"
    
    def plan_action(self, reasoning: str) -> ReActAction:
        # Plan next action based on reasoning
        return ReActAction(
            action_type=ActionType.SCAN_DIRECTORY,
            description="Scan for analysis targets",
            parameters={'directory': '.', 'pattern': '*.py'}
        )
    
    def _generate_summary(self) -> str:
        return f"Custom analysis complete: {len(self.state.observations)} findings"
```

### LLM Integration with Life of X

```python
from cf.llm.real_llm import RealLLM, LLMConfig
from cf.llm.prompt_templates import PromptBuilder
from cf.llm.response_parser import ResponseParser

# Configure LLM provider
config = LLMConfig(
    model="gpt-4",
    api_key="your-api-key",
    max_tokens=1000,
    temperature=0.7
)

llm = RealLLM(config)

# Generate Life of X narrative
narrative_result = llm.generate_life_of_x_narrative(
    question="How does authentication work?",
    insights={'agents': 'results'},
    components=[{'name': 'AuthController', 'type': 'api'}],
    flows=[{'source': 'Client', 'target': 'AuthService'}]
)

# Use for reasoning
reasoning_result = llm.reasoning(
    context="Current codebase state",
    question="What should I analyze next?",
    agent_type="codebase"
)
```

### Life of X Utilities

```python
from cf.tools.narrative_utils import extract_key_entity, display_life_of_x_narrative
from cf.llm.prompt_templates import PromptBuilder
from cf.llm.response_parser import ResponseParser, LIFE_OF_X_SCHEMA

# Extract entity from question
entity = extract_key_entity("How does authentication work?")
# Returns: "Authentication"

# Build prompts using templates
builder = PromptBuilder()
prompt = builder.build_life_of_x_prompt(
    question="How does authentication work?",
    insights="System insights...",
    components="Key components...",
    flows="Data flows...",
    code_examples="Code examples...",
    key_entity="Authentication",
    model_name="gpt-4"
)

# Parse responses with schema validation
parser = ResponseParser()
parsed = parser.parse_response(llm_response, LIFE_OF_X_SCHEMA)

# Display narrative with beautiful formatting
display_life_of_x_narrative(parsed, "How does authentication work?")
```

## Navigation

Use the sidebar to navigate through the API documentation. Each section provides:

- **Class Overview**: Purpose and role in the framework
- **Constructor Parameters**: How to initialize the class
- **Methods**: All public methods with parameters and return types
- **Examples**: Practical usage examples
- **Integration**: How the class integrates with other components

## Type Definitions

All APIs use type hints for better development experience:

```python
from typing import Dict, List, Any, Optional
from cf.core.react_agent import ReActAction, ReActObservation, ActionType
```

## Error Handling

The framework includes comprehensive error handling:

```python
try:
    results = supervisor.explore_repository(goal="analysis")
except Exception as e:
    print(f"Analysis failed: {e}")
    # Framework includes automatic recovery mechanisms
```

## Agent API Documentation

### CodeAgent

The CodeAgent specializes in analyzing source code using LLM function calling loops.

```python
from cf.agents.code import CodeAgent
from cf.configs.config_mgr import CfConfig

# Initialize agent
config = CfConfig.load_from_file("cf/configs/config.yaml")
code_agent = CodeAgent("/path/to/repo", config)

# Analyze code with LLM function calling
result = code_agent.analyze("Find FastAPI routing implementation")
print(result['insights'])
```

**Key Methods:**
- `analyze(goal: str)` - Main analysis method with LLM function calling
- `plan_action(reasoning: str)` - LLM-driven action planning
- `execute_action(action)` - Tool execution with registry

### DocsAgent

The DocsAgent processes documentation and README files.

```python
from cf.agents.docs import DocsAgent

# Initialize and analyze documentation
docs_agent = DocsAgent("/path/to/repo", config)
result = docs_agent.analyze("Look for routing documentation")
print(result['documentation_insights'])
```

**Key Methods:**
- `analyze(goal: str)` - Documentation analysis
- `extract_documentation_patterns()` - Find doc patterns
- `analyze_readme_quality()` - README assessment

### WebAgent

The WebAgent integrates external knowledge via web search.

```python
from cf.agents.web import WebAgent

# Initialize and search web
web_agent = WebAgent("/path/to/repo", config)
result = web_agent.analyze("Search for FastAPI routing best practices")
print(result['web_insights'])
```

**Key Methods:**
- `analyze(goal: str)` - Web search analysis
- `generate_search_queries()` - LLM-driven query generation
- `process_web_results()` - Result integration

### BaseAgent

Common functionality shared by all agents.

```python
from cf.agents.base import BaseAgent

# BaseAgent provides common methods:
# - LLM integration patterns
# - Logging and tracing
# - Tool registry access
# - Configuration management
```

**Key Methods:**
- `call_llm(prompt: str)` - LLM interaction
- `get_tool_registry()` - Access to tools
- `log_action(action: str)` - Progress logging

### ToolRegistry

Centralized tool management for LLM function calling.

```python
from cf.tools.registry import ToolRegistry

# Initialize tool registry
tools = ToolRegistry("/path/to/repo")

# Get available tool schemas for LLM function calling
schemas = tools.get_all_schemas()

# Execute specific tool
result = tools.execute_tool("search_files", {"pattern": "FastAPI", "file_types": ["*.py"]})
```

**Available Tools:**
- `scan_directory` - Repository structure exploration
- `read_file` - File content analysis
- `search_files` - Pattern-based file search
- `analyze_code` - Code complexity analysis
- `web_search` - External knowledge search

For detailed information about specific components, explore the individual API documentation pages.