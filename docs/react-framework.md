# CodeFusion ReAct Framework Documentation

## Overview

The CodeFusion ReAct Framework is a sophisticated agent-based system that uses the ReAct (Reasoning + Acting) pattern to systematically explore and analyze codebases. This framework provides intelligent, LLM-powered agents that work together to understand code structure, documentation, and architecture.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [Agent Types](#agent-types)
4. [Configuration](#configuration)
5. [Tool Ecosystem](#tool-ecosystem)
6. [LLM Integration](#llm-integration)
7. [Caching & Performance](#caching--performance)
8. [Tracing & Monitoring](#tracing--monitoring)
9. [Error Handling](#error-handling)
10. [Advanced Usage](#advanced-usage)
11. [API Reference](#api-reference)
12. [Troubleshooting](#troubleshooting)

## Quick Start

### Installation

```bash
# Install CodeFusion with ReAct framework
pip install -e .

# Optional: Install LiteLLM for advanced LLM support
pip install litellm
```

### Basic Usage

```bash
# Multi-agent repository analysis
cf analyze /path/to/repo --focus=all

# Documentation-focused analysis
cf analyze /path/to/repo --focus=docs

# Architecture-focused analysis  
cf analyze /path/to/repo --focus=arch

# Code-focused analysis
cf analyze /path/to/repo --focus=code
```

### Configuration

```bash
# Set up OpenAI integration
export CF_LLM_MODEL=gpt-4
export CF_LLM_API_KEY=your-openai-api-key

# Set up Anthropic integration
export CF_LLM_MODEL=claude-3-sonnet-20240229
export CF_LLM_API_KEY=your-anthropic-api-key

# Set up LLaMA integration
export CF_LLM_MODEL=together_ai/meta-llama/Llama-2-7b-chat-hf
export CF_LLM_API_KEY=your-together-ai-api-key
```

## Core Concepts

### ReAct Pattern

The ReAct pattern follows a systematic three-phase cycle:

1. **Reason**: Analyze current state and determine the next best action
2. **Act**: Execute the determined action using available tools
3. **Observe**: Process the results and update understanding

```python
# Example ReAct cycle
def execute_react_loop(self, goal: str) -> Dict[str, Any]:
    while not goal_achieved and iteration < max_iterations:
        # REASON: What should I do next?
        reasoning = self.reason()
        
        # ACT: Take the reasoned action
        action = self.plan_action(reasoning)
        observation = self.act(action)
        
        # OBSERVE: Reflect on what happened
        self.observe(observation)
```

### Multi-Agent Architecture

The framework uses specialized agents that work together:

- **Supervisor Agent**: Orchestrates other agents and synthesizes insights
- **Documentation Agent**: Analyzes README files, docs, and guides
- **Codebase Agent**: Examines source code, functions, and patterns
- **Architecture Agent**: Studies system design and architectural patterns

### Tool-Rich Environment

Each agent has access to 8 core tools:

- **Directory Scanning**: Explore repository structure
- **File Listing**: Find files matching patterns
- **File Reading**: Examine file contents
- **Pattern Searching**: Search across multiple files
- **Code Analysis**: Extract code entities and patterns
- **LLM Reasoning**: AI-powered decision making
- **LLM Summarization**: AI-powered content summarization
- **Caching**: Store and retrieve previous results

## Agent Types

### 1. ReAct Supervisor Agent

**Purpose**: Coordinates multiple specialized agents and synthesizes cross-agent insights.

```python
from cf.agents.react_supervisor_agent import ReActSupervisorAgent
from cf.aci.repo import LocalCodeRepo
from cf.config import CfConfig

# Create supervisor agent
repo = LocalCodeRepo("/path/to/repo")
config = CfConfig()
supervisor = ReActSupervisorAgent(repo, config)

# Run comprehensive analysis
results = supervisor.explore_repository(focus="all")
```

**Key Features**:
- Multi-agent coordination
- Cross-agent insight synthesis
- Focus-based analysis (docs, code, arch, all)
- Intelligent agent activation based on findings

### 2. ReAct Documentation Agent

**Purpose**: Specializes in analyzing documentation, README files, and guides.

```python
from cf.agents.react_documentation_agent import ReActDocumentationAgent

# Create documentation agent
doc_agent = ReActDocumentationAgent(repo, config)

# Analyze documentation
results = doc_agent.execute_react_loop("Analyze project documentation structure")
```

**Specializations**:
- Markdown file analysis
- Documentation structure mapping
- Guide and tutorial identification
- API documentation discovery

### 3. ReAct Codebase Agent

**Purpose**: Focuses on source code analysis, function extraction, and pattern detection.

```python
from cf.agents.react_codebase_agent import ReActCodebaseAgent

# Create codebase agent
code_agent = ReActCodebaseAgent(repo, config)

# Analyze codebase
results = code_agent.execute_react_loop("Identify main classes and functions")
```

**Specializations**:
- Code entity extraction (classes, functions, variables)
- Language-specific analysis
- Complexity assessment
- Dependency mapping
- Pattern recognition

### 4. ReAct Architecture Agent

**Purpose**: Understands system design, components, and architectural patterns.

```python
from cf.agents.react_architecture_agent import ReActArchitectureAgent

# Create architecture agent
arch_agent = ReActArchitectureAgent(repo, config)

# Analyze architecture
results = arch_agent.execute_react_loop("Understand system architecture")
```

**Specializations**:
- Component identification
- Design pattern detection
- System boundary analysis
- Architectural insight generation

## Configuration

### Environment Variables

```bash
# ReAct Loop Configuration
CF_REACT_MAX_ITERATIONS=20          # Maximum iterations per agent
CF_REACT_ITERATION_TIMEOUT=30.0     # Timeout per iteration (seconds)
CF_REACT_TOTAL_TIMEOUT=600.0        # Total timeout (seconds)

# Error Handling
CF_REACT_MAX_ERRORS=10               # Maximum errors before stopping
CF_REACT_MAX_CONSECUTIVE_ERRORS=3    # Maximum consecutive errors
CF_REACT_ERROR_RECOVERY=true         # Enable error recovery

# Caching Configuration
CF_REACT_CACHE_ENABLED=true          # Enable caching
CF_REACT_CACHE_MAX_SIZE=1000         # Maximum cache entries
CF_REACT_CACHE_TTL=3600              # Cache TTL (seconds)

# Tracing Configuration
CF_REACT_TRACING_ENABLED=true        # Enable tracing
CF_REACT_TRACE_DIR=./traces          # Trace output directory
CF_REACT_LOG_LEVEL=INFO              # Logging level

# LLM Configuration
CF_LLM_MODEL=gpt-4                   # LLM model to use
CF_LLM_API_KEY=your-api-key          # API key
CF_LLM_MAX_TOKENS=1000               # Max tokens per request
CF_LLM_TEMPERATURE=0.7               # LLM temperature
```

### Performance Profiles

```python
from cf.core.react_config import ReActConfig

# Fast profile - quick analysis
config = ReActConfig()
config.apply_performance_profile("fast")
# max_iterations=10, timeouts=15s, cache=500

# Balanced profile - default
config.apply_performance_profile("balanced")
# max_iterations=20, timeouts=30s, cache=1000

# Thorough profile - comprehensive analysis
config.apply_performance_profile("thorough")
# max_iterations=50, timeouts=60s, cache=2000
```

### Custom Configuration

```python
from cf.core.react_config import ReActConfig

# Create custom configuration
config = ReActConfig(
    max_iterations=30,
    iteration_timeout=45.0,
    cache_enabled=True,
    cache_max_size=2000,
    tracing_enabled=True,
    trace_directory="./custom_traces"
)

# Validate configuration
config.validate()

# Use with agent
agent = ReActCodebaseAgent(repo, cf_config, react_config=config)
```

## Tool Ecosystem

### Available Tools

Each ReAct agent has access to these tools through the `ActionType` enum:

#### 1. SCAN_DIRECTORY
```python
# Recursively scan directory structure
action = ReActAction(
    action_type=ActionType.SCAN_DIRECTORY,
    description="Scan project root directory",
    parameters={
        'directory': '.',
        'max_depth': 3
    }
)
```

#### 2. LIST_FILES
```python
# List files matching patterns
action = ReActAction(
    action_type=ActionType.LIST_FILES,
    description="Find Python files",
    parameters={
        'pattern': '*.py',
        'directory': './src'
    }
)
```

#### 3. READ_FILE
```python
# Read file contents
action = ReActAction(
    action_type=ActionType.READ_FILE,
    description="Read main module",
    parameters={
        'file_path': 'src/main.py',
        'max_lines': 100
    }
)
```

#### 4. SEARCH_FILES
```python
# Search for patterns across files
action = ReActAction(
    action_type=ActionType.SEARCH_FILES,
    description="Find API endpoints",
    parameters={
        'pattern': 'def api_',
        'file_types': ['.py'],
        'max_results': 20
    }
)
```

#### 5. ANALYZE_CODE
```python
# Analyze code structure
action = ReActAction(
    action_type=ActionType.ANALYZE_CODE,
    description="Analyze module complexity",
    parameters={
        'file_path': 'src/complex_module.py',
        'analysis_type': 'basic'
    }
)
```

#### 6. LLM_REASONING
```python
# Use LLM for reasoning
action = ReActAction(
    action_type=ActionType.LLM_REASONING,
    description="Reason about next action",
    parameters={
        'context': 'Current findings...',
        'question': 'What should I investigate next?',
        'agent_type': 'codebase'
    }
)
```

#### 7. LLM_SUMMARY
```python
# Generate AI summaries
action = ReActAction(
    action_type=ActionType.LLM_SUMMARY,
    description="Summarize findings",
    parameters={
        'content': 'Analysis results...',
        'summary_type': 'technical',
        'focus': 'architecture'
    }
)
```

#### 8. CACHE_LOOKUP / CACHE_STORE
```python
# Cache operations
lookup_action = ReActAction(
    action_type=ActionType.CACHE_LOOKUP,
    description="Check cached analysis",
    parameters={'key': 'module_analysis_main.py'}
)

store_action = ReActAction(
    action_type=ActionType.CACHE_STORE,
    description="Store analysis results",
    parameters={
        'key': 'module_analysis_main.py',
        'value': analysis_results
    }
)
```

### Tool Validation

The framework includes comprehensive tool validation:

```python
# Parameter validation
def _validate_action_parameters(self, action: ReActAction) -> Optional[str]:
    if action.action_type == ActionType.READ_FILE:
        if 'file_path' not in action.parameters:
            return "file_path parameter required for READ_FILE"
    return None

# Result validation
def _validate_tool_result(self, action: ReActAction, result: Any) -> Dict[str, Any]:
    if isinstance(result, dict) and 'error' in result:
        return {'valid': False, 'error': f"Tool returned error: {result['error']}"}
    return {'valid': True, 'error': None}
```

## LLM Integration

### Supported Providers

The framework supports multiple LLM providers through LiteLLM:

#### OpenAI
```bash
export CF_LLM_MODEL=gpt-4
export CF_LLM_API_KEY=your-openai-api-key
```

Supported models:
- `gpt-4`
- `gpt-4-turbo`
- `gpt-3.5-turbo`
- `gpt-3.5-turbo-16k`

#### Anthropic
```bash
export CF_LLM_MODEL=claude-3-sonnet-20240229
export CF_LLM_API_KEY=your-anthropic-api-key
```

Supported models:
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`

#### LLaMA via Together AI
```bash
export CF_LLM_MODEL=together_ai/meta-llama/Llama-2-7b-chat-hf
export CF_LLM_API_KEY=your-together-ai-api-key
```

Supported models:
- `together_ai/meta-llama/Llama-2-7b-chat-hf`
- `together_ai/meta-llama/Llama-2-13b-chat-hf`
- `together_ai/meta-llama/Llama-2-70b-chat-hf`
- `together_ai/meta-llama/Code-Llama-7b-Python-hf`

#### LLaMA via Replicate
```bash
export CF_LLM_MODEL=replicate/meta/llama-2-7b-chat
export CF_LLM_API_KEY=your-replicate-token
```

#### LLaMA via Ollama (Local)
```bash
export CF_LLM_MODEL=ollama/llama2
# No API key needed for local Ollama
```

### LLM Usage in Agents

```python
# Reasoning with LLM
def reason(self) -> str:
    reasoning_result = self._tool_llm_reasoning({
        'context': self._build_context(),
        'question': self.state.goal,
        'agent_type': self.agent_name.lower()
    })
    return reasoning_result.get('reasoning', 'Continue exploration')

# Summarization with LLM
def _generate_summary(self) -> str:
    summary_result = self._tool_llm_summary({
        'content': self._compile_findings(),
        'summary_type': 'technical',
        'focus': 'key_insights'
    })
    return summary_result.get('summary', 'Analysis completed')
```

### Fallback Mechanism

If LLM calls fail, the framework gracefully falls back to simple implementations:

```python
try:
    from ..llm.real_llm import real_llm
    result = real_llm.reasoning(context, question, agent_type)
    return result
except Exception as e:
    self.logger.warning(f"Real LLM failed, using fallback: {e}")
    from ..llm.simple_llm import llm
    result = llm.reasoning(context, question, agent_type)
    result['fallback'] = True
    return result
```

## Caching & Performance

### Persistent Caching

The framework includes sophisticated caching with persistence across sessions:

```python
class ReActCache:
    def __init__(self, max_size: int = 1000, cache_dir: Optional[str] = None, ttl: int = 3600):
        # In-memory cache with optional disk persistence
        # TTL-based expiration
        # LRU eviction policy
```

**Features**:
- **Persistent Storage**: JSON files for cross-session continuity
- **TTL Expiration**: Automatic cleanup of stale entries
- **LRU Eviction**: Memory-efficient cache management
- **Error Resilience**: Graceful handling of corrupt cache files

### Cache Configuration

```bash
# Enable persistent caching
CF_REACT_CACHE_ENABLED=true
CF_REACT_CACHE_MAX_SIZE=1000
CF_REACT_CACHE_TTL=3600
CF_REACT_TRACE_DIR=./traces  # Cache stored in ./traces/cache/
```

### Performance Optimization

```python
# Performance profiles optimize different aspects
config = ReActConfig()

# Fast: Prioritizes speed
config.apply_performance_profile("fast")
# - max_iterations: 10
# - iteration_timeout: 15s
# - cache_max_size: 500

# Balanced: Optimal balance
config.apply_performance_profile("balanced")
# - max_iterations: 20  
# - iteration_timeout: 30s
# - cache_max_size: 1000

# Thorough: Maximizes completeness
config.apply_performance_profile("thorough")
# - max_iterations: 50
# - iteration_timeout: 60s
# - cache_max_size: 2000
```

## Tracing & Monitoring

### Comprehensive Tracing

The framework includes detailed execution tracing:

```python
@dataclass
class ReActTrace:
    trace_id: str
    agent_name: str
    iteration: int
    phase: str  # 'reason', 'act', 'observe'
    timestamp: float
    duration: float
    content: Dict[str, Any]
    success: bool
    error: Optional[str]
```

### Session Management

```python
# Tracing lifecycle
tracer = ReActTracer()

# Start session
session_id = tracer.start_session("codebase_agent", "Analyze main module")

# Trace phases
tracer.trace_phase(session_id, "reason", iteration=1, 
                  content={'reasoning': 'Should read main.py first'}, 
                  duration=0.5)

tracer.trace_phase(session_id, "act", iteration=1,
                  content={'action': 'READ_FILE', 'file': 'main.py'},
                  duration=1.2, success=True)

# End session
completed_session = tracer.end_session(session_id, final_results)
```

### Performance Metrics

```python
# Get global metrics
metrics = tracer.get_global_metrics()

# Example metrics:
{
    'total_sessions': 15,
    'total_iterations': 180,
    'total_errors': 2,
    'avg_session_duration': 45.2,
    'avg_reason_duration': 1.1,
    'avg_act_duration': 2.3,
    'avg_observe_duration': 0.8,
    'agent_usage': {
        'codebase_agent': 8,
        'doc_agent': 4,
        'arch_agent': 3
    }
}
```

### Trace Export

```python
# Export traces to file
tracer.export_metrics('./metrics.json')

# Get human-readable summary
summary = tracer.get_trace_summary(session_id)
print(summary)
```

## Error Handling

### Multi-Level Error Handling

The framework implements comprehensive error handling at multiple levels:

#### 1. Circuit Breakers
```python
# Prevent cascading failures
if self.consecutive_errors >= self.react_config.max_consecutive_errors:
    self.logger.error(f"Too many consecutive errors ({self.consecutive_errors})")
    break
```

#### 2. Retry Logic
```python
# Retry failed operations
for attempt in range(self.react_config.max_tool_retries + 1):
    try:
        result = self._execute_tool_with_timeout(tool_func, action.parameters)
        break
    except Exception as e:
        if attempt < self.react_config.max_tool_retries:
            recovery_action = self._attempt_tool_recovery(action, str(e))
            continue
```

#### 3. Recovery Strategies
```python
def _attempt_tool_recovery(self, action: ReActAction, error: str) -> Optional[str]:
    error_lower = error.lower()
    
    if 'file not found' in error_lower:
        return 'file_not_found'  # Switch to directory scan
    elif 'permission denied' in error_lower:
        return 'permission_denied'  # Try different approach
    elif 'timeout' in error_lower:
        return 'timeout'  # Use cached results
```

#### 4. Graceful Degradation
```python
# LLM fallback
try:
    result = real_llm.reasoning(context, question)
except Exception:
    result = simple_llm.reasoning(context, question)
    result['fallback'] = True
```

### Error Configuration

```bash
# Error handling configuration
CF_REACT_MAX_ERRORS=10               # Maximum total errors
CF_REACT_MAX_CONSECUTIVE_ERRORS=3    # Maximum consecutive errors
CF_REACT_ERROR_RECOVERY=true         # Enable error recovery
CF_REACT_CIRCUIT_BREAKER_THRESHOLD=5 # Circuit breaker threshold
```

## Advanced Usage

### Custom Agent Development

Create specialized agents by extending `ReActAgent`:

```python
from cf.core.react_agent import ReActAgent, ReActAction, ActionType

class CustomAnalysisAgent(ReActAgent):
    def __init__(self, repo: CodeRepo, config: CfConfig):
        super().__init__(repo, config, "custom_agent")
        self.domain_knowledge = {}
    
    def reason(self) -> str:
        """Custom reasoning logic"""
        if not self.state.observations:
            return "Start by scanning the repository structure"
        elif len(self.state.observations) < 5:
            return "Search for domain-specific patterns"
        else:
            return "Analyze findings and generate insights"
    
    def plan_action(self, reasoning: str) -> ReActAction:
        """Custom action planning"""
        if "scan" in reasoning.lower():
            return ReActAction(
                action_type=ActionType.SCAN_DIRECTORY,
                description="Scan repository for structure",
                parameters={'directory': '.', 'max_depth': 2}
            )
        # ... additional action planning
    
    def _generate_summary(self) -> str:
        """Custom summary generation"""
        return f"Custom analysis completed with {len(self.state.observations)} observations"
```

### Multi-Agent Coordination

Implement custom coordination logic:

```python
class CustomSupervisor(ReActAgent):
    def __init__(self, repo: CodeRepo, config: CfConfig):
        super().__init__(repo, config, "custom_supervisor")
        self.specialized_agents = {
            'security': SecurityAnalysisAgent(repo, config),
            'performance': PerformanceAnalysisAgent(repo, config),
            'testing': TestAnalysisAgent(repo, config)
        }
    
    def coordinate_agents(self, focus: str) -> Dict[str, Any]:
        results = {}
        
        for agent_name, agent in self.specialized_agents.items():
            if focus == 'all' or focus == agent_name:
                agent_result = agent.execute_react_loop(f"Analyze {agent_name} aspects")
                results[agent_name] = agent_result
        
        return self._synthesize_results(results)
```

### Custom Tools

Add new tools to the ecosystem:

```python
# Extend ActionType enum
class ExtendedActionType(ActionType):
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    SECURITY_SCAN = "security_scan"
    PERFORMANCE_PROFILE = "performance_profile"

# Add tool implementations
def _tool_dependency_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """Custom dependency analysis tool"""
    file_path = params.get('file_path', '')
    # ... implementation
    return {'dependencies': dependencies, 'analysis': analysis}

# Register new tools
self.tools[ExtendedActionType.DEPENDENCY_ANALYSIS] = self._tool_dependency_analysis
```

### Batch Processing

Process multiple repositories:

```python
def batch_analyze_repositories(repo_paths: List[str], focus: str = "all") -> Dict[str, Any]:
    results = {}
    
    for repo_path in repo_paths:
        try:
            repo = LocalCodeRepo(repo_path)
            config = CfConfig()
            supervisor = ReActSupervisorAgent(repo, config)
            
            result = supervisor.explore_repository(focus=focus)
            results[repo_path] = result
            
        except Exception as e:
            results[repo_path] = {'error': str(e)}
    
    return results
```

## API Reference

### Core Classes

#### `ReActAgent` (Abstract Base Class)
```python
class ReActAgent(ABC):
    def __init__(self, repo: CodeRepo, config: CfConfig, agent_name: str, 
                 react_config: Optional[ReActConfig] = None)
    
    def execute_react_loop(self, goal: str, max_iterations: Optional[int] = None) -> Dict[str, Any]
    
    @abstractmethod
    def reason(self) -> str
    
    @abstractmethod
    def plan_action(self, reasoning: str) -> ReActAction
    
    def act(self, action: ReActAction) -> ReActObservation
    
    def observe(self, observation: ReActObservation)
    
    @abstractmethod
    def _generate_summary(self) -> str
```

#### `ReActConfig`
```python
@dataclass
class ReActConfig:
    max_iterations: int = 20
    iteration_timeout: float = 30.0
    total_timeout: float = 600.0
    max_errors: int = 10
    max_consecutive_errors: int = 3
    error_recovery_enabled: bool = True
    cache_enabled: bool = True
    cache_max_size: int = 1000
    cache_ttl: int = 3600
    tracing_enabled: bool = True
    
    @classmethod
    def from_env(cls) -> 'ReActConfig'
    
    def apply_performance_profile(self, profile: str)
    
    def validate(self) -> bool
```

#### `ReActAction`
```python
@dataclass
class ReActAction:
    action_type: ActionType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    tool_name: str = ""
```

#### `ReActObservation`
```python
@dataclass
class ReActObservation:
    action_taken: str
    result: Any
    success: bool
    insight: str
    confidence: float = 0.0
    suggests_next_action: Optional[str] = None
    goal_progress: float = 0.0
```

#### `ReActTracer`
```python
class ReActTracer:
    def __init__(self, log_level: str = "INFO", trace_dir: Optional[str] = None)
    
    def start_session(self, agent_name: str, goal: str) -> str
    
    def trace_phase(self, session_id: str, phase: str, iteration: int, 
                   content: Dict[str, Any], duration: float = 0.0, 
                   success: bool = True, error: Optional[str] = None) -> str
    
    def end_session(self, session_id: str, final_result: Dict[str, Any]) -> ReActSession
    
    def get_global_metrics(self) -> Dict[str, Any]
    
    def export_metrics(self, output_file: str)
```

### Specialized Agents

#### `ReActSupervisorAgent`
```python
class ReActSupervisorAgent(ReActAgent):
    def explore_repository(self, focus: str = "all", max_agents: int = 3) -> Dict[str, Any]
    
    def activate_agent(self, agent_type: str, sub_goal: str) -> Dict[str, Any]
    
    def synthesize_cross_agent_insights(self, agent_results: Dict[str, Any]) -> List[Dict[str, Any]]
```

#### `ReActDocumentationAgent`
```python
class ReActDocumentationAgent(ReActAgent):
    def discover_documentation(self) -> List[str]
    
    def analyze_documentation_structure(self, doc_files: List[str]) -> Dict[str, Any]
    
    def extract_documentation_insights(self, content: str) -> Dict[str, Any]
```

#### `ReActCodebaseAgent`
```python
class ReActCodebaseAgent(ReActAgent):
    def extract_code_entities(self, file_path: str) -> List[CodeEntity]
    
    def analyze_code_patterns(self, files: List[str]) -> List[CodePattern]
    
    def assess_code_complexity(self, file_path: str) -> Dict[str, Any]
```

#### `ReActArchitectureAgent`
```python
class ReActArchitectureAgent(ReActAgent):
    def identify_components(self) -> List[Dict[str, Any]]
    
    def detect_architectural_patterns(self) -> List[Dict[str, Any]]
    
    def analyze_system_boundaries(self) -> Dict[str, Any]
```

## Troubleshooting

### Common Issues

#### 1. LLM Connection Failures
```bash
# Check API key configuration
echo $CF_LLM_API_KEY

# Test with simple LLM fallback
CF_LLM_MODEL=simple cf analyze /repo
```

#### 2. Cache Permission Issues
```bash
# Check cache directory permissions
ls -la ./traces/cache/

# Use custom cache directory
CF_REACT_TRACE_DIR=/tmp/cf_traces cf analyze /repo
```

#### 3. Timeout Issues
```bash
# Increase timeouts for large repositories
CF_REACT_ITERATION_TIMEOUT=60.0 CF_REACT_TOTAL_TIMEOUT=1800.0 cf analyze /repo

# Use fast profile
CF_REACT_MAX_ITERATIONS=10 cf analyze /repo
```

#### 4. Memory Issues
```bash
# Reduce cache size
CF_REACT_CACHE_MAX_SIZE=500 cf analyze /repo

# Disable caching
CF_REACT_CACHE_ENABLED=false cf analyze /repo
```

### Debug Mode

Enable verbose logging for debugging:

```bash
# Enable debug logging
CF_REACT_LOG_LEVEL=DEBUG CF_REACT_VERBOSE_LOGGING=true cf analyze /repo

# Enable tracing
CF_REACT_TRACING_ENABLED=true CF_REACT_TRACE_DIR=./debug_traces cf analyze /repo
```

### Performance Tuning

```bash
# Quick analysis
CF_REACT_MAX_ITERATIONS=5 CF_REACT_ITERATION_TIMEOUT=10.0 cf analyze /repo

# Comprehensive analysis
CF_REACT_MAX_ITERATIONS=100 CF_REACT_ITERATION_TIMEOUT=120.0 cf analyze /repo

# Parallel tools (future feature)
CF_REACT_PARALLEL_TOOLS=true CF_REACT_MAX_PARALLEL_TOOLS=3 cf analyze /repo
```

### Error Recovery

If agents get stuck or error out:

```bash
# Enable aggressive error recovery
CF_REACT_ERROR_RECOVERY=true CF_REACT_MAX_CONSECUTIVE_ERRORS=1 cf analyze /repo

# Reduce circuit breaker threshold
CF_REACT_CIRCUIT_BREAKER_THRESHOLD=3 cf analyze /repo
```

---

For additional support, please refer to the [Architecture Documentation](./dev/architecture.md) or open an issue on the project repository.