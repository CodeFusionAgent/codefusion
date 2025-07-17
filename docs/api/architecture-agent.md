# Architecture Agent

::: cf.agents.react_architecture_agent.ReActArchitectureAgent

The Architecture Agent specializes in analyzing system design and architectural patterns using the ReAct pattern.

## Overview

The Architecture Agent excels at:

- System component identification
- Architectural pattern detection
- Data flow mapping
- Layer analysis
- Design pattern recognition

## Usage Examples

### Basic Architecture Analysis

```python
from cf.agents.react_architecture_agent import ReActArchitectureAgent
from cf.aci.repo import LocalCodeRepo
from cf.config import CfConfig

# Initialize agent
repo = LocalCodeRepo("/path/to/repository")
config = CfConfig()
arch_agent = ReActArchitectureAgent(repo, config)

# Analyze architecture
results = arch_agent.map_architecture("system architecture and design patterns")

print(f"Components identified: {len(results.get('components', {}))}")
print(f"Patterns detected: {len(results.get('patterns', []))}")
print(f"Layers found: {len(results.get('layers', {}))}")
```

### Component Analysis

```python
# Get system components
components = arch_agent.get_system_components()

for component_type, component_list in components.items():
    print(f"{component_type.title()} Components: {len(component_list)}")
    for component in component_list[:3]:  # Show first 3
        print(f"  - {component.name} ({component.component_type})")
```

### Pattern Detection

```python
# Get architectural patterns
patterns = arch_agent.get_architectural_patterns()

for pattern in patterns:
    print(f"Pattern: {pattern.pattern_type}")
    print(f"Description: {pattern.description}")
    print(f"Confidence: {pattern.confidence}")
    print(f"Occurrences: {pattern.occurrences}")
```

For complete API documentation, see the [source code](../../cf/agents/react_architecture_agent.py).