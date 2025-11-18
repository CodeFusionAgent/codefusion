"""
CodeFusion Tracer

Clean tracing system with decorators for automatic method tracing.
Supports pluggable tracer backends (local files, Langfuse, etc.).

Enhanced with:
- Hierarchical spans (parent-child relationships)
- Detailed metrics (tokens, cost)
- Cross-agent correlation (pass tracking)
- MetricsCollector integration
"""

import os
import time
import json
import functools
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass
class TraceEvent:
    """A single trace event with hierarchical span support"""
    session_id: str
    timestamp: float
    event_type: str  # "method_call", "tool_call", "llm_call", "loop_detection", "analysis"
    method_name: str
    duration: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    # Hierarchical spans
    span_id: str = ""
    parent_span_id: Optional[str] = None

    # Detailed metrics
    tokens_used: int = 0
    cost_usd: float = 0.0

    # Cross-agent correlation
    pass_number: int = 1
    agent_name: str = ""
    agent_type: str = ""  # supervisor, code, docs, web


class TracerPlugin(ABC):
    """
    Base class for tracer plugins.

    Enables pluggable tracing backends:
    - Local file storage (default)
    - Langfuse (observability platform)
    - Custom backends
    """

    @abstractmethod
    def start_session(self, session_id: str, metadata: Dict[str, Any] = None):
        """Start a tracing session"""
        pass

    @abstractmethod
    def end_session(self, session_id: str, metadata: Dict[str, Any] = None):
        """End a tracing session"""
        pass

    @abstractmethod
    def log_event(self, event: TraceEvent):
        """Log a trace event"""
        pass

    @abstractmethod
    def flush(self):
        """Flush pending events"""
        pass


def trace_method(method_type: str):
    """Decorator to automatically trace method calls"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            method_name = func.__name__
            
            try:
                result = func(self, *args, **kwargs)
                success = True
                error = None
            except Exception as e:
                result = {'error': str(e), 'success': False}
                success = False
                error = str(e)
            
            # Log to tracer if available
            if hasattr(self, 'tracer') and self.tracer:
                duration = time.time() - start_time
                self.tracer.log_method_call(
                    getattr(self, 'session_id', 'unknown'), 
                    method_name, method_type,
                    args, kwargs, result, duration, success, error
                )
            
            if not success:
                raise Exception(error)
            
            return result
        return wrapper
    return decorator


class Tracer:
    """Enhanced tracer for CodeFusion with hierarchical spans and metrics"""

    def __init__(self, agent_name: str, trace_config: Dict[str, Any], plugins: List[TracerPlugin] = None):
        self.agent_name = agent_name
        self.enabled = trace_config.get('enabled', True)
        self.output_dir = Path(trace_config.get('output_dir', 'cf_trace'))
        self.events: List[TraceEvent] = []
        self.plugins: List[TracerPlugin] = plugins or []

        # Hierarchical span tracking
        self._current_span_id: Optional[str] = None
        self._span_stack: List[str] = []

        # Cross-agent context
        self._current_pass: int = 1
        self._agent_type: str = agent_name  # supervisor, code, docs, web

        # Metrics integration
        self._metrics_collector = None

        # Create output directory
        if self.enabled:
            self.output_dir.mkdir(exist_ok=True)

    def add_plugin(self, plugin: TracerPlugin):
        """Add a tracer plugin"""
        self.plugins.append(plugin)

    def set_metrics_collector(self, collector):
        """Integrate with MetricsCollector for unified observability"""
        self._metrics_collector = collector

    def set_pass_number(self, pass_number: int):
        """Set current pass number for cross-agent correlation"""
        self._current_pass = pass_number

    @contextmanager
    def span(self, name: str, event_type: str = "span", metadata: Dict[str, Any] = None):
        """
        Context manager for hierarchical span tracking.

        Usage:
            with tracer.span("discovery_pipeline"):
                # nested operations automatically tracked
                with tracer.span("kb_query"):
                    result = query_kb()
        """
        if not self.enabled:
            yield None
            return

        # Create new span
        span_id = str(uuid.uuid4())[:8]
        parent_span_id = self._current_span_id

        # Push onto stack
        self._span_stack.append(span_id)
        old_span_id = self._current_span_id
        self._current_span_id = span_id

        start_time = time.time()

        try:
            yield span_id
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            duration = time.time() - start_time

            # Log span event
            event = TraceEvent(
                session_id=getattr(self, '_current_session_id', 'unknown'),
                timestamp=start_time,
                event_type=event_type,
                method_name=name,
                duration=duration,
                success=success,
                error=error,
                metadata=metadata or {},
                span_id=span_id,
                parent_span_id=parent_span_id,
                pass_number=self._current_pass,
                agent_name=self.agent_name,
                agent_type=self._agent_type
            )
            self.events.append(event)

            # Notify plugins
            for plugin in self.plugins:
                try:
                    plugin.log_event(event)
                except Exception as e:
                    print(f"⚠️ Plugin error: {e}")

            # Record to metrics collector
            if self._metrics_collector:
                try:
                    self._metrics_collector.record_call(
                        component=f"{self.agent_name}_{name}",
                        duration=duration,
                        success=success
                    )
                except Exception:
                    # Silently ignore metrics errors to not break tracing
                    pass

            # Pop from stack
            self._span_stack.pop()
            self._current_span_id = old_span_id
    
    def start_session(self, session_name: str) -> str:
        """Start a new tracing session"""
        session_id = f"{self.agent_name}_{session_name}_{int(time.time())}"
        self._current_session_id = session_id

        # Reset span tracking for new session
        self._current_span_id = None
        self._span_stack = []

        if self.enabled:
            self.log_event(session_id, "session_start", {"session_name": session_name})

            # Notify plugins
            for plugin in self.plugins:
                try:
                    plugin.start_session(session_id, {"session_name": session_name, "agent": self.agent_name})
                except Exception as e:
                    print(f"⚠️ Plugin error in start_session: {e}")

        return session_id
    
    def end_session(self, session_id: str):
        """End tracing session and save results"""
        if self.enabled:
            self.log_event(session_id, "session_end", {})
            self._save_session_trace(session_id)

            # Notify plugins
            for plugin in self.plugins:
                try:
                    plugin.end_session(session_id)
                    plugin.flush()
                except Exception as e:
                    print(f"⚠️ Plugin error in end_session: {e}")
    
    def log_llm_call(self, session_id: str, model: str, tokens_used: int,
                     cost_usd: float, duration: float, success: bool,
                     metadata: Dict[str, Any] = None):
        """
        Log an LLM call with detailed metrics.

        Args:
            session_id: Session ID
            model: Model name (e.g., "gpt-4o", "claude-sonnet-4-5")
            tokens_used: Total tokens consumed
            cost_usd: Estimated cost in USD
            duration: Call duration in seconds
            success: Whether call succeeded
            metadata: Additional context (prompt type, tier, etc.)
        """
        if not self.enabled:
            return

        event = TraceEvent(
            session_id=session_id,
            timestamp=time.time(),
            event_type="llm_call",
            method_name=model,
            duration=duration,
            success=success,
            metadata=metadata or {},
            span_id=self._current_span_id or str(uuid.uuid4())[:8],
            parent_span_id=self._span_stack[-2] if len(self._span_stack) >= 2 else None,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            pass_number=self._current_pass,
            agent_name=self.agent_name,
            agent_type=self._agent_type
        )
        self.events.append(event)

        # Record to metrics collector
        if self._metrics_collector:
            try:
                self._metrics_collector.record_tokens(
                    component=f"{self.agent_name}_llm",
                    tokens=tokens_used,
                    metadata={'model': model, 'cost': cost_usd}
                )
                self._metrics_collector.record_call(
                    component=f"{self.agent_name}_llm",
                    duration=duration,
                    success=success
                )
            except Exception:
                # Silently ignore metrics errors to not break tracing
                pass

        # Notify plugins
        for plugin in self.plugins:
            try:
                plugin.log_event(event)
            except Exception as e:
                print(f"⚠️ Plugin error in log_llm_call: {e}")

    def log_method_call(self, session_id: str, method_name: str, method_type: str,
                       args: tuple, kwargs: Dict[str, Any], result: Any,
                       duration: float, success: bool, error: Optional[str] = None):
        """Log a method call"""
        if not self.enabled:
            return

        event = TraceEvent(
            session_id=session_id,
            timestamp=time.time(),
            event_type=method_type,
            method_name=method_name,
            duration=duration,
            success=success,
            error=error,
            metadata={
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys()),
                'result_type': type(result).__name__
            },
            span_id=self._current_span_id or str(uuid.uuid4())[:8],
            parent_span_id=self._span_stack[-2] if len(self._span_stack) >= 2 else None,
            pass_number=self._current_pass,
            agent_name=self.agent_name,
            agent_type=self._agent_type
        )
        self.events.append(event)

        # Notify plugins
        for plugin in self.plugins:
            try:
                plugin.log_event(event)
            except Exception as e:
                print(f"⚠️ Plugin error in log_method_call: {e}")
    
    def log_event(self, session_id: str, event_type: str, metadata: Dict[str, Any]):
        """Log a general event"""
        if not self.enabled:
            return

        event = TraceEvent(
            session_id=session_id,
            timestamp=time.time(),
            event_type=event_type,
            method_name="",
            duration=0.0,
            success=True,
            metadata=metadata,
            span_id=self._current_span_id or str(uuid.uuid4())[:8],
            parent_span_id=self._span_stack[-2] if len(self._span_stack) >= 2 else None,
            pass_number=self._current_pass,
            agent_name=self.agent_name,
            agent_type=self._agent_type
        )
        self.events.append(event)

        # Notify plugins
        for plugin in self.plugins:
            try:
                plugin.log_event(event)
            except Exception as e:
                print(f"⚠️ Plugin error in log_event: {e}")
    
    def _save_session_trace(self, session_id: str):
        """Save session trace to file with hierarchical data"""
        if not self.enabled:
            return

        session_events = [e for e in self.events if e.session_id == session_id]

        # Calculate totals
        total_tokens = sum(e.tokens_used for e in session_events)
        total_cost = sum(e.cost_usd for e in session_events)
        llm_calls = [e for e in session_events if e.event_type == 'llm_call']

        trace_data = {
            'session_id': session_id,
            'agent_name': self.agent_name,
            'start_time': min(e.timestamp for e in session_events) if session_events else time.time(),
            'end_time': time.time(),
            'total_events': len(session_events),

            # Aggregated metrics
            'metrics': {
                'total_tokens': total_tokens,
                'total_cost_usd': total_cost,
                'llm_calls': len(llm_calls),
                'total_duration': sum(e.duration for e in session_events),
                'success_rate': sum(1 for e in session_events if e.success) / len(session_events) if session_events else 0
            },

            # Hierarchical events with all new fields
            'events': [
                {
                    'timestamp': e.timestamp,
                    'event_type': e.event_type,
                    'method_name': e.method_name,
                    'duration': e.duration,
                    'success': e.success,
                    'error': e.error,
                    'metadata': e.metadata,

                    # Hierarchical
                    'span_id': e.span_id,
                    'parent_span_id': e.parent_span_id,

                    # Metrics
                    'tokens_used': e.tokens_used,
                    'cost_usd': e.cost_usd,

                    # Correlation
                    'pass_number': e.pass_number,
                    'agent_name': e.agent_name,
                    'agent_type': e.agent_type
                }
                for e in session_events
            ]
        }

        trace_file = self.output_dir / f"{session_id}.json"
        with open(trace_file, 'w') as f:
            json.dump(trace_data, f, indent=2)

        # Remove events from memory to save space
        self.events = [e for e in self.events if e.session_id != session_id]
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of session events"""
        session_events = [e for e in self.events if e.session_id == session_id]
        
        if not session_events:
            return {'error': 'Session not found'}
        
        return {
            'session_id': session_id,
            'total_events': len(session_events),
            'total_duration': sum(e.duration for e in session_events),
            'success_rate': sum(1 for e in session_events if e.success) / len(session_events),
            'event_types': list(set(e.event_type for e in session_events))
        }