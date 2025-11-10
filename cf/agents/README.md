# CodeFusion Agent Architecture

CodeFusion provides two agent patterns for different use cases. This document explains when to use each pattern and how to implement custom agents.

## Overview

CodeFusion has evolved to support **two distinct agent architectures**:

1. **Tool-Based Agents** (NEW - Recommended for most cases)
2. **Iterative Agents** (Legacy - For complex multi-step workflows)

Both patterns are supported and maintained. Choose based on your use case.

---

## 1. Tool-Based Agents (`KnowledgeAgent`)

### When to Use

Use `KnowledgeAgent` when you want to:
- Expose query capabilities as tools
- Enable runtime agent registration
- Support A/B testing and experimentation
- Provide composable, stateless operations
- Allow LLMs to call your capabilities

### Architecture

```python
from cf.agents.knowledge_base import KnowledgeAgent
from cf.agents.registry import AgentRegistry

class MyAgent(KnowledgeAgent):
    def __init__(self, config):
        super().__init__("my_agent", config)
        # Initialize your dependencies

    def get_capabilities(self) -> List[str]:
        """Return capability identifiers"""
        return ['custom_search', 'custom_analysis']

    def register_tools(self) -> Dict[str, Callable]:
        """Register tools (unprefixed - registry will add prefix)"""
        return {
            'search': self._search,          # Will become: my_agent_search
            'analyze': self._analyze,        # Will become: my_agent_analyze
        }

    def _search(self, query: str) -> Dict[str, Any]:
        """Tool implementation"""
        return {'success': True, 'results': [...]}
```

### Key Features

1. **Automatic Tool Prefixing**: Tools are automatically prefixed with agent name to prevent collisions
2. **Runtime Registration**: Agents can be registered/unregistered at runtime
3. **Tool Schemas**: Optional OpenAPI schemas for LLM function calling
4. **Metrics Tracking**: Built-in call/token/time tracking
5. **Protocol-Based Dependencies**: Use protocols (e.g., `KnowledgeBaseProtocol`) for loose coupling

### Example: KB Query Agent

```python
from cf.agents.knowledge_base import KnowledgeAgent
from cf.agents.protocols import KnowledgeBaseProtocol

class StructuralKBAgent(KnowledgeAgent):
    def __init__(self, kb: KnowledgeBaseProtocol, config):
        super().__init__("structural_kb", config)
        self.kb = kb  # Uses protocol, not concrete class!

    def get_capabilities(self):
        return ['semantic_search', 'pattern_detection']

    def register_tools(self):
        return {
            'search_by_semantics': self._search_by_semantics,
            'find_design_patterns': self._find_design_patterns
        }

    def _search_by_semantics(self, query: str, limit: int = 10):
        results = self.kb.search_by_natural_language(query, top_k=limit)
        return {'success': True, 'results': results}
```

### Tool Naming Convention

**IMPORTANT**: Tool names are ALWAYS prefixed by the registry.

```python
# In your agent:
def register_tools(self):
    return {
        'search': self._search,        # Unprefixed
        'analyze': self._analyze       # Unprefixed
    }

# After registration in AgentRegistry:
# 'search' becomes 'my_agent_search'
# 'analyze' becomes 'my_agent_analyze'

# For tool schemas, use get_prefixed_tool_name():
def get_tool_schemas(self):
    return [{
        'type': 'function',
        'function': {
            'name': self.get_prefixed_tool_name('search'),  # 'my_agent_search'
            'description': 'Search for items',
            'parameters': {...}
        }
    }]
```

---

## 2. Iterative Agents (`BaseAgent`)

### When to Use

Use `BaseAgent` when you need:
- Multi-step analysis loops
- Complex workflows with state
- Supervisor/coordinator patterns
- Iterative refinement
- Loop detection and recovery

### Architecture

```python
from cf.agents.base import BaseAgent

class MyAnalysisAgent(BaseAgent):
    def __init__(self, repo_path, config):
        super().__init__(repo_path, config, "my_agent")

    def _analyze_step(self, question: str) -> str:
        """Execute one analysis step"""
        # Perform one iteration of analysis
        # Return description of action taken
        return "analyzed files"

    def _is_analysis_complete(self, question: str) -> bool:
        """Check if analysis is complete"""
        return len(self.insights) >= 5

    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate final results"""
        return {
            'success': True,
            'answer': "Analysis complete",
            'insights': self.insights
        }
```

### Key Features

1. **Iterative Loop**: Automatic loop execution with max iterations
2. **State Management**: Built-in state (insights, results, iteration count)
3. **Tool Access**: Direct access to ToolRegistry
4. **LLM Integration**: Built-in LLM client with fast model support
5. **Tracing**: Decorator-based automatic tracing
6. **Loop Detection**: Detects and recovers from stuck states

### Example: Code Analysis Agent

```python
from cf.agents.base import BaseAgent

class CodeAnalysisAgent(BaseAgent):
    def __init__(self, repo_path, config):
        super().__init__(repo_path, config, "code_analysis")
        self.files_analyzed = []

    def _analyze_step(self, question: str):
        # Find relevant files
        files = self.use_tool('search_files', pattern="*.py", query=question)

        # Analyze each file
        for file in files[:3]:  # Limit per iteration
            content = self.use_tool('read_file', file_path=file)
            summary = self.call_llm_fast(f"Summarize this code:\n{content}")
            self.add_insight(summary)
            self.files_analyzed.append(file)

        return f"analyzed {len(files)} files"

    def _is_analysis_complete(self, question: str):
        return len(self.files_analyzed) >= 10 or len(self.insights) >= 5

    def _generate_results(self, question: str):
        # Synthesize final answer
        final_answer = self.call_llm(
            f"Based on these insights, answer: {question}\n\nInsights:\n" +
            "\n".join(i['content'] for i in self.insights)
        )

        return {
            'success': True,
            'answer': final_answer['content'],
            'confidence': self.get_confidence('high'),
            'files_analyzed': self.files_analyzed
        }
```

---

## Comparison

| Feature | Tool-Based (`KnowledgeAgent`) | Iterative (`BaseAgent`) |
|---------|-------------------------------|-------------------------|
| **Use Case** | Composable tools, KB queries | Multi-step analysis workflows |
| **State** | Stateless (tools are functions) | Stateful (insights, results) |
| **Execution** | Single function call | Iterative loop |
| **LLM Integration** | External (via LlmTask) | Built-in |
| **Tool Access** | Agent IS the tool provider | Agent USES tools |
| **Runtime Registration** | Yes (via AgentRegistry) | No |
| **A/B Testing** | Native support | Requires wrapper |
| **Tracing** | Automatic (via registry) | Decorator-based |
| **Complexity** | Simpler | More complex |

---

## Migration Guide: BaseAgent → KnowledgeAgent

If you have an existing `BaseAgent` that you want to convert to `KnowledgeAgent`:

### Before (BaseAgent)
```python
class MyAgent(BaseAgent):
    def __init__(self, repo_path, config):
        super().__init__(repo_path, config, "my_agent")

    def _analyze_step(self, question):
        result = self.use_tool('search_files', pattern="*.py")
        return "searched files"

    def _is_analysis_complete(self, question):
        return True

    def _generate_results(self, question):
        return {'success': True, 'answer': "Done"}
```

### After (KnowledgeAgent)
```python
class MyAgent(KnowledgeAgent):
    def __init__(self, tools: ToolRegistryProtocol, config):
        super().__init__("my_agent", config)
        self.tools = tools

    def get_capabilities(self):
        return ['file_analysis']

    def register_tools(self):
        return {'analyze': self._analyze}

    def _analyze(self, question: str):
        result = self.tools.execute('search_files', pattern="*.py")
        return {'success': True, 'answer': "Done", 'files': result}
```

---

## Best Practices

### For Tool-Based Agents

1. **Use Protocols for Dependencies**
   ```python
   def __init__(self, kb: KnowledgeBaseProtocol, config):  # ✅ Protocol
       # NOT: def __init__(self, kb: Neo4jKnowledgeBase, config):  # ❌ Concrete class
   ```

2. **Return Structured Dictionaries**
   ```python
   return {
       'success': True/False,
       'data': ...,
       'error': "..." if failed
   }
   ```

3. **Use get_prefixed_tool_name() in Schemas**
   ```python
   def get_tool_schemas(self):
       return [{
           'function': {
               'name': self.get_prefixed_tool_name('search'),  # ✅ Correct
               # NOT: 'name': 'search',  # ❌ Missing prefix
           }
       }]
   ```

4. **Track Metrics**
   ```python
   def _my_tool(self, param: str):
       start_time = time.time()
       try:
           result = do_work(param)
           self._record_call(time_taken=time.time() - start_time)
           return {'success': True, 'result': result}
       except Exception as e:
           self._record_call(time_taken=time.time() - start_time, error=True)
           return {'success': False, 'error': str(e)}
   ```

### For Iterative Agents

1. **Use Fast Model for Routine Tasks**
   ```python
   summary = self.call_llm_fast("Summarize this code")  # Cheaper
   final_answer = self.call_llm("Generate detailed analysis")  # Quality
   ```

2. **Limit Iterations**
   ```python
   # Process a few items per iteration
   for item in items[:5]:  # Not all at once
       process(item)
   ```

3. **Use Confidence Levels from Config**
   ```python
   return {
       'confidence': self.get_confidence('high'),  # From config
       # NOT: 'confidence': 0.8,  # Hardcoded
   }
   ```

---

## Testing

### Testing Tool-Based Agents

```python
# Use mock KB backend
class MockKB:
    def search_by_natural_language(self, query, top_k):
        return [{'file': 'test.py', 'score': 0.9}]

# Test agent
agent = StructuralKBAgent(kb=MockKB(), config={})
tools = agent.register_tools()
result = tools['search_by_semantics']('find auth code')
assert result['success'] == True
```

### Testing Iterative Agents

```python
# Create agent with test config
config = load_test_config()
agent = MyAnalysisAgent("/path/to/test/repo", config)

# Run analysis
result = agent.analyze("test question")
assert result['success'] == True
assert len(result['insights']) > 0
```

---

## Examples

See:
- `examples/basic_usage.py` - Tool-based agent examples
- `examples/ab_testing_example.py` - A/B testing with variants
- `cf/agents/kb/structural_kb_agent.py` - Complete tool-based agent
- `cf/agents/code.py` - Complete iterative agent

---

## Questions?

- **Q: Which pattern should I use?**
  - A: Use Tool-Based for most cases. Use Iterative only for complex multi-step workflows.

- **Q: Can I mix both patterns?**
  - A: Yes! Iterative agents can USE tools from Tool-Based agents via ToolRegistry.

- **Q: How do I register a custom agent?**
  - A: See `examples/basic_usage.py` example 2 (custom agent registration).

- **Q: How do I prevent tool name collisions?**
  - A: AgentRegistry automatically prefixes all tools. Choose unique agent names.

---

**Last Updated**: 2025-11-10
**Version**: 2.0 (Post-Refactoring)
