# ReAct Agent Base Class

::: cf.core.react_agent.ReActAgent

The `ReActAgent` class is the foundation of the CodeFusion ReAct framework, implementing the core Reason → Act → Observe pattern that drives intelligent code exploration.

## Overview

The ReAct (Reasoning + Acting) pattern enables agents to:

1. **Reason** about the current state and determine the next action
2. **Act** by executing tools and operations
3. **Observe** the results and update their understanding
4. **Iterate** until the goal is achieved

## Key Components

### Action Types

::: cf.core.react_agent.ActionType

### State Management

::: cf.core.react_agent.ReActState

### Actions and Observations

::: cf.core.react_agent.ReActAction

::: cf.core.react_agent.ReActObservation

### Caching System

::: cf.core.react_agent.ReActCache

## Usage Examples

### Basic Agent Implementation

```python
from cf.core.react_agent import ReActAgent, ReActAction, ActionType

class MyCustomAgent(ReActAgent):
    def reason(self) -> str:
        """Implement domain-specific reasoning logic."""
        if self.state.iteration == 1:
            return "Starting analysis by scanning the repository structure"
        
        if not self.state.observations:
            return "Need to gather more information about the codebase"
        
        return "Continue with detailed examination based on findings"
    
    def plan_action(self, reasoning: str) -> ReActAction:
        """Plan the next action based on reasoning."""
        if "scanning" in reasoning.lower():
            return ReActAction(
                action_type=ActionType.SCAN_DIRECTORY,
                description="Scan repository structure",
                parameters={'directory': '.', 'max_depth': 3},
                expected_outcome="Understand project layout"
            )
        
        return ReActAction(
            action_type=ActionType.READ_FILE,
            description="Read main configuration file",
            parameters={'file_path': 'config.py'},
            expected_outcome="Understand project configuration"
        )
    
    def _generate_summary(self) -> str:
        """Generate analysis summary."""
        return f"Custom analysis completed in {self.state.iteration} iterations"

# Usage
agent = MyCustomAgent(repo, config, "MyAgent")
results = agent.execute_react_loop("Analyze project structure")
```

### Advanced Customization

```python
class AdvancedAgent(ReActAgent):
    def __init__(self, repo, config, agent_name):
        super().__init__(repo, config, agent_name)
        self.domain_knowledge = {}
        self.analysis_patterns = []
    
    def observe(self, observation):
        """Enhanced observation with domain-specific processing."""
        super().observe(observation)
        
        # Custom observation processing
        if observation.success:
            self._extract_domain_patterns(observation.result)
            self._update_knowledge_base(observation)
    
    def _extract_domain_patterns(self, result):
        """Extract domain-specific patterns from results."""
        # Custom pattern extraction logic
        pass
    
    def _update_knowledge_base(self, observation):
        """Update internal knowledge base."""
        # Custom knowledge management
        pass
```

## Integration with Tools

The ReAct agent integrates with the tool ecosystem:

```python
# Tools are automatically available via ActionType
action = ReActAction(
    action_type=ActionType.SEARCH_FILES,
    description="Search for authentication patterns",
    parameters={
        'pattern': 'auth',
        'file_types': ['.py', '.js'],
        'max_results': 10
    }
)
```

## Error Handling and Recovery

```python
class RobustAgent(ReActAgent):
    def act(self, action: ReActAction) -> ReActObservation:
        """Act with enhanced error handling."""
        try:
            return super().act(action)
        except Exception as e:
            # Custom error recovery
            self.logger.warning(f"Action failed: {e}, attempting recovery")
            return self._recover_from_error(action, e)
    
    def _recover_from_error(self, action, error):
        """Implement custom error recovery."""
        return ReActObservation(
            action_taken=action.description,
            result={"error": str(error)},
            success=False,
            insight="Error encountered, adjusting strategy",
            confidence=0.0
        )
```

## Performance Monitoring

```python
# Access performance metrics
agent = MyCustomAgent(repo, config, "MyAgent")
results = agent.execute_react_loop("Analysis goal")

# Get metrics
print(f"Iterations: {agent.state.iteration}")
print(f"Cache hits: {agent.state.cache_hits}")
print(f"Errors: {agent.state.error_count}")
print(f"Goal progress: {results.get('goal_achieved', False)}")
```

## Configuration Options

```python
from cf.core.react_config import ReActConfig

# Custom configuration
custom_config = ReActConfig(
    max_iterations=30,
    iteration_timeout=45.0,
    total_timeout=900.0,
    cache_enabled=True,
    cache_max_size=2000,
    error_recovery_enabled=True
)

agent = MyCustomAgent(repo, config, "MyAgent", react_config=custom_config)
```