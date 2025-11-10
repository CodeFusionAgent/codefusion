# Enhanced Tracing Guide

## Overview

CodeFusion tracing has been enhanced with:
- ✅ **Hierarchical Spans** - Parent-child relationships for nested operations
- ✅ **Detailed Metrics** - Token counts and cost tracking
- ✅ **Cross-Agent Correlation** - Multi-pass and agent handoff tracking
- ✅ **MetricsCollector Integration** - Unified observability

## Quick Start

### Basic Usage

```python
from cf.trace.tracer import Tracer
from cf.metrics.collector import get_global_collector

# Initialize tracer
config = {'enabled': True, 'output_dir': 'cf_trace'}
tracer = Tracer('my_agent', config)

# Integrate with MetricsCollector
tracer.set_metrics_collector(get_global_collector())

# Start session
session_id = tracer.start_session('my_task')

# Use hierarchical spans
with tracer.span("outer_operation"):
    # Do work
    with tracer.span("inner_operation"):
        # Nested work tracked automatically
        pass

# Log LLM calls with metrics
tracer.log_llm_call(
    session_id=session_id,
    model="gpt-4o",
    tokens_used=1500,
    cost_usd=0.03,
    duration=2.5,
    success=True,
    metadata={'tier': 'fast', 'prompt_type': 'classification'}
)

# End session (saves trace file)
tracer.end_session(session_id)
```

### Multi-Pass Tracking

```python
# Set pass number for cross-agent correlation
tracer.set_pass_number(1)

with tracer.span("pass_1_discovery"):
    # Pass 1 operations
    pass

tracer.set_pass_number(2)

with tracer.span("pass_2_deep_analysis"):
    # Pass 2 operations tracked separately
    pass
```

### Viewing Traces

#### Hierarchical View (Default)

```bash
python -m cf.trace.viewer timeline <session_id>
```

Output:
```
================================================================================
Trace Timeline: supervisor_q_1699564800
Agent: supervisor
Events: 45
Duration: 9.25s

📊 Metrics:
  Total Tokens: 23,450
  Total Cost: $0.0587
  LLM Calls: 23
  Success Rate: 100.0%
================================================================================

Hierarchical Trace:

[1] ✓ analyze_question (9250ms)
  └─ [1] ✓ discovery_pipeline (2100ms) @code
    └─ [1] ✓ kb_query (450ms) [🔤 0 tok, $0.0000]
    └─ [1] ✓ llm_classify (320ms) [🔤 850 tok, $0.0017] @code
  └─ [1] ✓ analysis_pipeline (3200ms) @code
    └─ [1] ✓ analyze_file (150ms) [🔤 1200 tok, $0.0024] @code
    └─ [1] ✓ analyze_file (145ms) [🔤 1150 tok, $0.0023] @code
    ...
  └─ [1] ✓ synthesis (2800ms) [🔤 5500 tok, $0.0165]

--------------------------------------------------------------------------------
Pass-by-Pass Summary:
  Pass 1: 38 events, 7.20s, 18,200 tokens, $0.0456
  Pass 2: 7 events, 2.05s, 5,250 tokens, $0.0131
--------------------------------------------------------------------------------
```

#### Flat Timeline View

```bash
python -m cf.trace.viewer timeline <session_id> --flat
```

Output:
```
[+ 0.00s]    ✓ session_start     analyze_question
[+ 0.12s] P1 ✓ llm_call         gpt-4o              120ms (850 tok, $0.0017)
[+ 0.45s] P1 ✓ tool_call        kb_query            330ms
[+ 2.10s] P1 ✓ llm_call         claude-haiku         95ms (1200 tok, $0.0024)
[+ 5.30s] P2 ✓ llm_call         claude-sonnet-4-5  2500ms (5500 tok, $0.0165)
```

## Integration with Multi-Pass Coordinator

```python
from cf.agents.multi_pass_coordinator import MultiPassCoordinator

class SupervisorAgent:
    def __init__(self, ...):
        # ...
        self.tracer.set_metrics_collector(get_global_collector())

    def _analyze_step(self, question: str):
        # Update pass number in tracer
        self.tracer.set_pass_number(self.pass_coordinator.current_pass.pass_number)

        # Use spans for operations
        with self.tracer.span(f"pass_{self.pass_number}_analysis"):
            # Analysis work
            pass
```

## Trace File Format

```json
{
  "session_id": "supervisor_q_1699564800",
  "agent_name": "supervisor",
  "start_time": 1699564800.123,
  "end_time": 1699564809.373,
  "total_events": 45,

  "metrics": {
    "total_tokens": 23450,
    "total_cost_usd": 0.0587,
    "llm_calls": 23,
    "total_duration": 9.25,
    "success_rate": 1.0
  },

  "events": [
    {
      "timestamp": 1699564800.123,
      "event_type": "llm_call",
      "method_name": "gpt-4o",
      "duration": 0.12,
      "success": true,

      "span_id": "a1b2c3d4",
      "parent_span_id": "x9y8z7w6",

      "tokens_used": 850,
      "cost_usd": 0.0017,

      "pass_number": 1,
      "agent_name": "supervisor",
      "agent_type": "supervisor",

      "metadata": {
        "tier": "fast",
        "prompt_type": "classification"
      }
    }
  ]
}
```

## API Reference

### Tracer

#### `span(name, event_type='span', metadata=None)`
Context manager for hierarchical span tracking.

```python
with tracer.span("discovery", metadata={'strategy': 'kb_graph'}):
    # Automatically tracked with parent-child relationship
    with tracer.span("query_kb"):
        result = query_kb()
```

#### `log_llm_call(session_id, model, tokens_used, cost_usd, duration, success, metadata)`
Log LLM call with detailed metrics.

```python
tracer.log_llm_call(
    session_id=session_id,
    model="claude-sonnet-4-5",
    tokens_used=5500,
    cost_usd=0.0165,
    duration=2.5,
    success=True,
    metadata={'tier': 'advanced', 'prompt_type': 'synthesis'}
)
```

#### `set_metrics_collector(collector)`
Integrate with MetricsCollector for unified observability.

```python
from cf.metrics.collector import get_global_collector
tracer.set_metrics_collector(get_global_collector())
```

#### `set_pass_number(pass_number)`
Set current pass number for cross-agent correlation.

```python
tracer.set_pass_number(2)  # Now in Pass 2
```

### TraceViewer

#### `visualize_timeline(session_id, show_hierarchy=True)`
Visualize trace with hierarchical spans (default) or flat timeline.

```python
from cf.trace.viewer import TraceViewer

viewer = TraceViewer()
viewer.visualize_timeline(session_id, show_hierarchy=True)
```

## Benefits

### 1. Hierarchical Spans ✅
- **See nested operations**: Understand call trees
- **Track relationships**: Know which operations called which
- **Visualize flow**: ASCII tree shows execution hierarchy

### 2. Detailed Metrics ✅
- **Token tracking**: Every LLM call logged with tokens
- **Cost tracking**: Automatic cost calculation per call
- **Aggregated totals**: Session-level metrics in trace file

### 3. Cross-Agent Correlation ✅
- **Multi-pass tracking**: See which events belong to which pass
- **Agent handoffs**: Track work across supervisor → code → docs
- **Pass summaries**: Aggregated metrics per pass

### 4. MetricsCollector Integration ✅
- **Unified observability**: Traces + metrics in one place
- **Automatic recording**: Spans auto-record to metrics
- **Hierarchical aggregation**: supervisor → orchestrator → pipelines

## Advanced Features

### Custom Span Metadata

```python
with tracer.span("file_analysis", metadata={
    'file_path': 'cf/agents/supervisor.py',
    'analysis_type': 'deep',
    'confidence': 0.85
}):
    # Metadata saved in trace
    pass
```

### Plugin Architecture

```python
from cf.trace.tracer import TracerPlugin

class LangfusePlugin(TracerPlugin):
    def log_event(self, event):
        # Send to Langfuse
        langfuse.trace(
            name=event.method_name,
            metadata={
                'tokens': event.tokens_used,
                'cost': event.cost_usd
            }
        )

# Add plugin
tracer.add_plugin(LangfusePlugin())
```

## Migration from Old Tracing

### Before (Limited)
```python
# No hierarchy, no metrics
tracer.log_event(session_id, "method_call", {})
```

### After (Enhanced)
```python
# Hierarchical with metrics
with tracer.span("outer"):
    with tracer.span("inner"):
        pass

tracer.log_llm_call(
    session_id=session_id,
    model="gpt-4o",
    tokens_used=1500,
    cost_usd=0.03,
    duration=2.5,
    success=True
)
```

## Score Improvement

**Before**: 7/10
- ✅ Session tracking
- ✅ Event logging
- ❌ No hierarchical spans
- ❌ No metrics tracking
- ❌ No cross-agent correlation

**After**: 9/10
- ✅ Session tracking
- ✅ Event logging
- ✅ Hierarchical spans with parent-child relationships
- ✅ Detailed metrics (tokens, cost) tracked
- ✅ Cross-agent correlation (passes, agents)
- ✅ MetricsCollector integration
- ⚠️ No real-time monitoring dashboard (future enhancement)

## Future Enhancements

1. **Real-time Dashboard** (Not implemented)
   - Live trace visualization
   - WebSocket streaming
   - Alert thresholds

2. **Distributed Tracing** (Partial)
   - ✅ Cross-agent correlation
   - ❌ Distributed context propagation
   - ❌ Trace sampling

3. **Performance Profiling**
   - Flame graphs
   - Bottleneck detection
   - Optimization suggestions
