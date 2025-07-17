# ReAct Supervisor Agent

::: cf.agents.react_supervisor_agent.ReActSupervisorAgent

The `ReActSupervisorAgent` orchestrates multiple specialized ReAct agents to perform comprehensive codebase analysis through intelligent coordination and cross-agent synthesis.

## Overview

The Supervisor Agent implements a hierarchical ReAct pattern:

1. **Reasons** about which agents to activate based on the analysis goal
2. **Acts** by delegating tasks to specialized agents
3. **Observes** results from multiple agents
4. **Synthesizes** cross-agent insights for comprehensive understanding

## Specialized Agents

The supervisor coordinates these specialized agents:

- **Documentation Agent**: Analyzes README files, guides, and documentation
- **Codebase Agent**: Examines source code, functions, and patterns  
- **Architecture Agent**: Studies system design and architectural patterns

## Usage Examples

### Basic Multi-Agent Analysis

```python
from cf.agents.react_supervisor_agent import ReActSupervisorAgent
from cf.aci.repo import LocalCodeRepo
from cf.config import CfConfig

# Initialize supervisor
repo = LocalCodeRepo("/path/to/repository")
config = CfConfig()
supervisor = ReActSupervisorAgent(repo, config)

# Comprehensive analysis
results = supervisor.explore_repository(
    goal="understand authentication system",
    focus="all"
)

# Access individual agent results
agent_results = supervisor.get_agent_results()
doc_results = agent_results.get('documentation')
code_results = agent_results.get('codebase')
arch_results = agent_results.get('architecture')

print(f"Documentation findings: {doc_results.get('summary')}")
print(f"Code analysis: {code_results.get('summary')}")
print(f"Architecture insights: {arch_results.get('summary')}")
```

### Focused Analysis

```python
# Documentation-focused analysis
doc_results = supervisor.explore_repository(
    goal="analyze API documentation quality",
    focus="docs"
)

# Architecture-focused analysis
arch_results = supervisor.explore_repository(
    goal="understand system design patterns",
    focus="arch"
)

# Code-focused analysis
code_results = supervisor.explore_repository(
    goal="identify security vulnerabilities",
    focus="code"
)
```

### Cross-Agent Insights

```python
# Run comprehensive analysis
results = supervisor.explore_repository(
    goal="security audit",
    focus="all"
)

# Get cross-agent insights
insights = supervisor.get_cross_agent_insights()

for insight in insights:
    print(f"Insight Type: {insight.insight_type}")
    print(f"Content: {insight.content}")
    print(f"Confidence: {insight.confidence}")
    print(f"Contributing Agents: {insight.contributing_agents}")
    print(f"Evidence: {insight.evidence}")
    print("---")
```

### Comprehensive Reporting

```python
# Generate detailed report
report = supervisor.generate_comprehensive_report()

print(f"Goal: {report['goal']}")
print(f"Execution Time: {report['execution_time']}")
print(f"Summary: {report['summary']}")

# Agent-specific summaries
for agent_name in ['documentation', 'codebase', 'architecture']:
    summary_key = f"{agent_name}_summary"
    if summary_key in report:
        print(f"{agent_name.title()} Summary: {report[summary_key]}")

# Cross-agent insights
for insight in report['cross_agent_insights']:
    print(f"Cross-Agent Insight: {insight['insight_type']}")
```

## Agent Coordination Patterns

### Sequential Activation

```python
class CustomSupervisor(ReActSupervisorAgent):
    def plan_action(self, reasoning: str) -> ReActAction:
        """Custom agent activation strategy."""
        active_agents = list(self.agent_results.keys())
        
        # Custom activation logic
        if not active_agents:
            return self._activate_primary_agent()
        elif len(active_agents) == 1:
            return self._activate_secondary_agent()
        else:
            return self._synthesize_results()
    
    def _activate_primary_agent(self):
        """Activate primary agent based on goal."""
        if 'security' in self.state.goal.lower():
            return self._create_activation_action('codebase', 'security analysis')
        elif 'design' in self.state.goal.lower():
            return self._create_activation_action('architecture', 'design analysis')
        else:
            return self._create_activation_action('documentation', 'overview analysis')
```

### Parallel Coordination

```python
# The supervisor can coordinate agents in parallel workflows
supervisor = ReActSupervisorAgent(repo, config)

# Start comprehensive analysis that activates multiple agents
results = supervisor.explore_repository(
    goal="complete system analysis", 
    focus="all"
)

# Agents work in parallel, supervisor synthesizes results
synthesis = supervisor.get_synthesis_results()
```

## Performance Optimization

```python
# Access performance metrics
results = supervisor.explore_repository(goal="analysis", focus="all")

# Get detailed performance data
agent_results = supervisor.get_agent_results()

total_cache_hits = sum(
    result.get('cache_hits', 0) 
    for result in agent_results.values()
    if isinstance(result, dict)
)

total_errors = sum(
    result.get('error_count', 0)
    for result in agent_results.values() 
    if isinstance(result, dict)
)

print(f"Total Cache Hits: {total_cache_hits}")
print(f"Total Errors: {total_errors}")
print(f"Success Rate: {(len(agent_results) - total_errors) / len(agent_results) * 100:.1f}%")
```

## Advanced Configuration

```python
from cf.core.react_config import ReActConfig

# Custom configuration for supervisor
supervisor_config = ReActConfig(
    max_iterations=25,  # Allow more iterations for coordination
    iteration_timeout=60.0,  # Longer timeout for agent coordination
    total_timeout=1200.0,  # Extended total timeout
    cache_enabled=True,
    error_recovery_enabled=True
)

supervisor = ReActSupervisorAgent(
    repo, 
    config, 
    react_config=supervisor_config
)
```

## Error Handling and Recovery

```python
class RobustSupervisor(ReActSupervisorAgent):
    def _activate_agent(self, agent_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced agent activation with error handling."""
        try:
            return super()._activate_agent(agent_name, parameters)
        except Exception as e:
            self.logger.error(f"Agent {agent_name} activation failed: {e}")
            
            # Attempt recovery with alternative agent
            if agent_name == 'codebase':
                return self._activate_agent('documentation', parameters)
            elif agent_name == 'architecture':
                return self._activate_agent('codebase', parameters)
            else:
                return {'error': f'All agents failed: {e}', 'recovery_attempted': True}
```

## Integration Examples

### With Custom Analysis Pipeline

```python
def comprehensive_security_audit(repo_path: str) -> Dict[str, Any]:
    """Complete security audit using supervisor coordination."""
    repo = LocalCodeRepo(repo_path)
    config = CfConfig()
    supervisor = ReActSupervisorAgent(repo, config)
    
    # Phase 1: Documentation security review
    doc_security = supervisor.explore_repository(
        goal="security documentation and policies",
        focus="docs"
    )
    
    # Phase 2: Code security analysis
    code_security = supervisor.explore_repository(
        goal="security vulnerabilities and patterns",
        focus="code"
    )
    
    # Phase 3: Architecture security assessment
    arch_security = supervisor.explore_repository(
        goal="security architecture and design",
        focus="arch"
    )
    
    # Generate comprehensive security report
    return supervisor.generate_comprehensive_report()
```

### With Performance Monitoring

```python
import time

def monitored_analysis(repo_path: str, goal: str) -> Dict[str, Any]:
    """Analysis with detailed performance monitoring."""
    start_time = time.time()
    
    supervisor = ReActSupervisorAgent(LocalCodeRepo(repo_path), CfConfig())
    results = supervisor.explore_repository(goal=goal, focus="all")
    
    end_time = time.time()
    
    # Add performance metrics to results
    results['performance_metrics'] = {
        'total_execution_time': end_time - start_time,
        'agents_activated': len(supervisor.get_agent_results()),
        'cross_agent_insights': len(supervisor.get_cross_agent_insights()),
        'cache_efficiency': calculate_cache_efficiency(supervisor),
        'error_rate': calculate_error_rate(supervisor)
    }
    
    return results
```