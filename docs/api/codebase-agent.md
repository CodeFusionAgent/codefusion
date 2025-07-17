# Codebase Agent

::: cf.agents.react_codebase_agent.ReActCodebaseAgent

The Codebase Agent specializes in comprehensive source code analysis using the ReAct pattern.

## Overview

The Codebase Agent excels at:

- Source code analysis and pattern detection
- Function and class extraction
- Dependency analysis
- Code complexity assessment
- Language-specific analysis (Python, JavaScript, TypeScript, etc.)

## Usage Examples

### Basic Code Analysis

```python
from cf.agents.react_codebase_agent import ReActCodebaseAgent
from cf.aci.repo import LocalCodeRepo
from cf.config import CfConfig

# Initialize agent
repo = LocalCodeRepo("/path/to/repository")
config = CfConfig()
code_agent = ReActCodebaseAgent(repo, config)

# Analyze codebase
results = code_agent.analyze_codebase("comprehensive code structure analysis")

print(f"Code files analyzed: {len(results.get('analyzed_files', {}))}")
print(f"Code entities found: {len(results.get('code_entities', {}))}")
print(f"Patterns detected: {len(results.get('code_patterns', []))}")
```

### Language-Specific Analysis

```python
# Python-specific analysis
python_results = code_agent.analyze_codebase("Python code patterns and structure")

# JavaScript/TypeScript analysis  
js_results = code_agent.analyze_codebase("JavaScript and TypeScript analysis")

# Access language statistics
language_stats = code_agent.get_language_stats()
print(f"Languages found: {language_stats}")
```

### Code Entity Extraction

```python
# Get detailed code entities
entities = code_agent.get_code_entities()

for file_path, file_entities in entities.items():
    print(f"File: {file_path}")
    for entity in file_entities:
        print(f"  {entity.type}: {entity.name} (lines {entity.line_start}-{entity.line_end})")
        if entity.docstring:
            print(f"    Docstring: {entity.docstring[:100]}...")
```

For complete API documentation, see the [source code](../../cf/agents/react_codebase_agent.py).