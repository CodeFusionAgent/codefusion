# Architecture Agent

**Note**: This agent has been integrated into the CodeAgent in the clean architecture.

The CodeAgent in `cf/agents/code.py` now handles architectural analysis as part of its code analysis capabilities.

## Current Implementation

In the clean architecture, architectural analysis is handled by the **CodeAgent** (`cf/agents/code.py`) which uses LLM function calling to:

- Identify system components through intelligent tool selection
- Detect architectural patterns via LLM analysis
- Map data flows using code exploration
- Analyze layers through repository structure examination
- Recognize design patterns via code analysis tools

## Usage Examples

### Architectural Analysis with CodeAgent

```python
from cf.agents.code import CodeAgent
from cf.configs.config_mgr import CfConfig

# Initialize CodeAgent for architectural analysis
config = CfConfig.load_from_file("cf/configs/config.yaml")
code_agent = CodeAgent("/path/to/repository", config)

# Analyze system architecture
results = code_agent.analyze("analyze system architecture and design patterns")

print(f"Analysis results: {results['insights']}")
print(f"Components found: {results.get('components_analyzed', 0)}")
```

### System Component Analysis

```python
# Use CodeAgent to identify components
component_analysis = code_agent.analyze("identify main system components and their responsibilities")

# The CodeAgent uses LLM function calling to:
# 1. scan_directory - Explore repository structure
# 2. search_files - Find component definitions
# 3. analyze_code - Examine component patterns
# 4. llm_reasoning - Synthesize architectural insights
```

### Pattern Detection via LLM Function Calling

```python
# Analyze architectural patterns
pattern_analysis = code_agent.analyze("identify architectural patterns and design principles used")

# CodeAgent will intelligently select tools like:
# - search_files to find pattern implementations
# - analyze_code to examine pattern usage
# - llm_reasoning to identify pattern types
```

For complete API documentation, see the [CodeAgent documentation](index.md#code-agent).