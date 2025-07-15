# Exploration Strategies

CodeFusion offers three distinct exploration strategies, each optimized for different types of analysis and codebase characteristics.

## Strategy Overview

| Strategy | Best For | Speed | Thoroughness | Complexity |
|----------|----------|-------|--------------|------------|
| **ReAct** | General exploration | Fast | Medium | Low |
| **Plan-Act** | Systematic analysis | Medium | High | Medium |
| **Sense-Act** | Complex codebases | Slow | Very High | High |

## ReAct Strategy

**Reasoning + Acting** - The default strategy that balances speed and thoroughness.

### How It Works

ReAct follows a simple cycle:
1. **Reason** about the current state and goal
2. **Act** by taking a specific exploration step
3. **Observe** the results
4. **Repeat** until the goal is achieved

### Configuration

```yaml
exploration_strategy: "react"
max_exploration_depth: 5

react_settings:
  reasoning_steps: 3        # Steps to think before acting
  action_timeout: 30        # Seconds per action
  backtrack_on_failure: true  # Retry failed paths
  max_iterations: 10        # Maximum cycles per query
```

### When to Use ReAct

**✅ Good for:**
- General code understanding
- Quick repository exploration
- Interactive development workflow
- Unknown codebases
- Time-constrained analysis

**❌ Not ideal for:**
- Very complex architectural analysis
- Comprehensive security audits
- Large-scale refactoring planning

### Examples

```bash
# General exploration
cf query --strategy react "How does the user authentication work?"

# Quick overview
cf query --strategy react "What are the main components of this system?"

# Development workflow
cf query --strategy react "How do I add a new API endpoint?"
```

**Typical ReAct Flow:**
```
1. Reason: "I need to understand authentication"
2. Act: Search for authentication-related files
3. Observe: Found auth.py, login.py, middleware/auth.js
4. Reason: "Let me examine the main auth module"
5. Act: Analyze auth.py contents
6. Observe: Found JWT token handling and user validation
7. Reason: "I should check how this integrates with routes"
8. Act: Search for route decorators using auth
```

## Plan-Act Strategy

**Plan then Act** - Systematic approach that creates a comprehensive plan before execution.

### How It Works

Plan-Act follows a structured approach:
1. **Analyze** the query and codebase scope
2. **Plan** a detailed sequence of exploration steps
3. **Validate** the plan for completeness
4. **Execute** each step systematically
5. **Adapt** the plan if needed

### Configuration

```yaml
exploration_strategy: "plan_act"
max_exploration_depth: 8

plan_act_settings:
  planning_depth: 3           # How detailed the initial plan
  execution_parallel: false   # Execute steps in parallel
  plan_validation: true       # Validate plan before execution
  replanning_threshold: 0.5   # When to replan (0.0-1.0)
  max_plan_steps: 20         # Maximum steps in a plan
```

### When to Use Plan-Act

**✅ Good for:**
- Setup and installation guides
- Systematic code analysis
- Process documentation
- Step-by-step procedures
- Compliance and audit requirements
- Large team onboarding

**❌ Not ideal for:**
- Quick exploratory questions
- Highly dynamic or evolving requirements
- Real-time development assistance

### Examples

```bash
# Systematic setup guide
cf query --strategy plan_act "How do I set up this project locally?"

# Comprehensive analysis
cf query --strategy plan_act "What's the complete CI/CD pipeline?"

# Process documentation
cf query --strategy plan_act "How do I contribute to this project?"
```

**Typical Plan-Act Flow:**
```
Query: "How do I deploy this application?"

Planning Phase:
1. Identify deployment-related files
2. Analyze build process
3. Examine configuration files
4. Check environment requirements
5. Find deployment scripts
6. Review documentation

Execution Phase:
Step 1: Search for Dockerfile, docker-compose.yml
Step 2: Analyze package.json/requirements.txt for dependencies
Step 3: Examine config/ directory for environment settings
Step 4: Review scripts/ or deploy/ directories
Step 5: Check README.md and docs/ for deployment docs
Step 6: Synthesize complete deployment guide
```

## Sense-Act Strategy

**Sense then Act** - Advanced strategy that observes and adapts to complex codebases.

### How It Works

Sense-Act uses an adaptive approach:
1. **Sense** the codebase structure and patterns
2. **Analyze** relationships and dependencies
3. **Adapt** strategy based on observations
4. **Act** with context-aware exploration
5. **Learn** from results to improve future actions

### Configuration

```yaml
exploration_strategy: "sense_act"
max_exploration_depth: 15

sense_act_settings:
  observation_cycles: 5      # Initial observation rounds
  adaptation_threshold: 0.7  # When to adapt strategy
  exploration_breadth: 5     # Parallel exploration paths
  context_window: 10         # Context items to maintain
  pattern_recognition: true  # Enable pattern detection
```

### When to Use Sense-Act

**✅ Good for:**
- Large, complex codebases (10k+ files)
- Pattern and architecture discovery
- Security analysis and vulnerability detection
- Performance optimization planning
- Legacy code understanding
- Cross-team dependency analysis

**❌ Not ideal for:**
- Simple repositories
- Time-sensitive queries
- Resource-constrained environments
- Straightforward development tasks

### Examples

```bash
# Complex architecture analysis
cf query --strategy sense_act "What architectural patterns are used?"

# Security analysis
cf query --strategy sense_act "What are potential security vulnerabilities?"

# Performance investigation
cf query --strategy sense_act "Where are the performance bottlenecks?"
```

**Typical Sense-Act Flow:**
```
Query: "What are the main architectural patterns in this codebase?"

Sensing Phase:
- Observe: Directory structure suggests MVC pattern
- Observe: Multiple microservices in services/ directory
- Observe: Shared libraries in common/ directory
- Observe: API gateway pattern in gateway/ directory
- Sense: Dependency injection used throughout

Adaptation Phase:
- Adapt: Focus on service boundaries and communication
- Adapt: Prioritize interface definitions and contracts
- Adapt: Look for cross-cutting concerns

Acting Phase:
- Act: Analyze service interfaces and APIs
- Act: Map service dependencies and communication patterns
- Act: Identify shared components and utilities
- Act: Examine configuration and deployment patterns
```

## Strategy Comparison

### Performance Characteristics

```yaml
# Speed comparison (relative)
react: 1.0x      # Baseline
plan_act: 0.7x   # 30% slower due to planning
sense_act: 0.4x  # 60% slower due to sensing

# Resource usage
react:
  cpu: Low
  memory: Low
  network: Medium

plan_act:
  cpu: Medium
  memory: Medium
  network: Low

sense_act:
  cpu: High
  memory: High
  network: High
```

### Accuracy and Completeness

```yaml
# Analysis quality (subjective)
react:
  completeness: 70%
  accuracy: 85%
  depth: Medium

plan_act:
  completeness: 90%
  accuracy: 90%
  depth: High

sense_act:
  completeness: 95%
  accuracy: 95%
  depth: Very High
```

## Strategy Selection Guide

### By Codebase Size

```yaml
# Small repositories (< 1,000 files)
recommended: "react"
alternative: "plan_act"

# Medium repositories (1,000 - 10,000 files)
recommended: "plan_act"
alternative: "react"

# Large repositories (> 10,000 files)
recommended: "sense_act"
alternative: "plan_act"
```

### By Query Type

```yaml
# Quick questions
"What does this function do?": "react"
"How do I run tests?": "react"

# Systematic analysis
"How do I deploy this?": "plan_act"
"What's the development workflow?": "plan_act"

# Complex analysis
"What are the architectural patterns?": "sense_act"
"Where are performance bottlenecks?": "sense_act"
```

### By Time Constraints

```yaml
# Immediate (< 1 minute)
strategy: "react"
max_exploration_depth: 3

# Standard (1-5 minutes)
strategy: "plan_act"
max_exploration_depth: 5

# Thorough (5+ minutes)
strategy: "sense_act"
max_exploration_depth: 10
```

## Mixed Strategy Approaches

### Sequential Strategies

Use different strategies for different phases:

```bash
# Phase 1: Quick overview with ReAct
cf query --strategy react "What type of application is this?"

# Phase 2: Systematic analysis with Plan-Act
cf query --strategy plan_act "How is the application structured?"

# Phase 3: Deep analysis with Sense-Act
cf query --strategy sense_act "What are the architectural trade-offs?"
```

### Conditional Strategy Selection

```yaml
# Configuration for automatic strategy selection
strategy_selection:
  auto_select: true
  rules:
    - condition: "file_count < 1000"
      strategy: "react"
    - condition: "file_count > 10000"
      strategy: "sense_act"
    - condition: "query_complexity == 'high'"
      strategy: "sense_act"
  default: "plan_act"
```

## Strategy Optimization

### ReAct Optimization

```yaml
react_settings:
  # For faster exploration
  reasoning_steps: 1
  max_iterations: 5
  
  # For more thorough exploration
  reasoning_steps: 5
  max_iterations: 15
  backtrack_on_failure: true
```

### Plan-Act Optimization

```yaml
plan_act_settings:
  # For faster execution
  planning_depth: 2
  execution_parallel: true
  
  # For more comprehensive plans
  planning_depth: 4
  plan_validation: true
  max_plan_steps: 30
```

### Sense-Act Optimization

```yaml
sense_act_settings:
  # For faster sensing
  observation_cycles: 3
  exploration_breadth: 3
  
  # For deeper understanding
  observation_cycles: 8
  exploration_breadth: 8
  context_window: 15
```

## Debugging Strategies

### Strategy Performance Monitoring

```bash
# Enable strategy debugging
export CF_STRATEGY_DEBUG=1
cf query --strategy sense_act "Complex query here"
```

### Strategy Metrics

CodeFusion tracks strategy performance:

```yaml
metrics:
  exploration_time: 45.2s
  steps_executed: 12
  accuracy_score: 0.89
  completeness_score: 0.92
  efficiency_ratio: 0.76
```

### Common Strategy Issues

**ReAct getting stuck in loops:**
```yaml
react_settings:
  max_iterations: 8        # Reduce iterations
  backtrack_on_failure: false  # Disable backtracking
```

**Plan-Act taking too long:**
```yaml
plan_act_settings:
  planning_depth: 2        # Reduce planning depth
  execution_parallel: true # Enable parallel execution
```

**Sense-Act using too much memory:**
```yaml
sense_act_settings:
  observation_cycles: 3    # Reduce observation cycles
  exploration_breadth: 3   # Reduce breadth
```

## Next Steps

- Learn about [configuration options](reference.md) for fine-tuning strategies
- See [usage examples](../usage/examples.md) with different strategies
- Check [performance tuning](../dev/performance.md) for optimization tips