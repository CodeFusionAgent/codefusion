# API Reference

Welcome to the CodeFusion ReAct Framework API documentation. This section provides comprehensive documentation for all classes, methods, and interfaces in the framework.

## Core Components

### ReAct Foundation

- **[ReAct Agent](react-agent.md)** - Base agent implementing Reason → Act → Observe loops
- **[ReAct Config](react-config.md)** - Configuration and performance tuning
- **[ReAct Tracing](react-tracing.md)** - Execution monitoring and metrics

### Specialized Agents

- **[Supervisor Agent](supervisor-agent.md)** - Multi-agent orchestration and **Life of X narrative generation**
- **[Documentation Agent](documentation-agent.md)** - Documentation analysis and processing
- **[Code Architecture Agent](code-architecture-agent.md)** - **Combined** source code analysis and architectural analysis

### Infrastructure

- **[LLM Integration](llm.md)** - Language model providers and interfaces
- **[Life of X Utilities](life-of-x-utilities.md)** - Narrative generation, prompt templates, and response parsing
- **[Tools](tools.md)** - Exploration tool ecosystem
- **[Repository Interface](repository.md)** - Code repository access and operations
- **[Configuration](config.md)** - Global configuration management

## Quick API Examples

### Life of X Narrative Generation

```python
from cf.agents.react_supervisor_agent import ReActSupervisorAgent
from cf.aci.repo import LocalCodeRepo
from cf.config import CfConfig

# Initialize components
repo = LocalCodeRepo("/path/to/repository")
config = CfConfig()
supervisor = ReActSupervisorAgent(repo, config)

# Generate Life of X narrative
narrative = supervisor.generate_life_of_x_narrative(
    question="How does authentication work?"
)

# Access narrative components
story = narrative['narrative']
journey = narrative['journey_stages']
components = narrative['key_components']
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

For detailed information about specific components, explore the individual API documentation pages.