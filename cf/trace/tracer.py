"""
CodeFusion Tracer

Clean tracing system with decorators for automatic method tracing.
Supports pluggable tracer backends (local files, Langfuse, etc.).
"""

import os
import time
import json
import functools
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TraceEvent:
    """A single trace event"""
    session_id: str
    timestamp: float
    event_type: str  # "method_call", "tool_call", "llm_call", "loop_detection", "analysis"
    method_name: str
    duration: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


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
    """Simple, clean tracer for CodeFusion with plugin support"""

    def __init__(self, agent_name: str, trace_config: Dict[str, Any], plugins: List[TracerPlugin] = None):
        self.agent_name = agent_name
        self.enabled = trace_config.get('enabled', True)
        self.output_dir = Path(trace_config.get('output_dir', 'cf_trace'))
        self.events: List[TraceEvent] = []
        self.plugins: List[TracerPlugin] = plugins or []

        # Create output directory
        if self.enabled:
            self.output_dir.mkdir(exist_ok=True)

    def add_plugin(self, plugin: TracerPlugin):
        """Add a tracer plugin"""
        self.plugins.append(plugin)
    
    def start_session(self, session_name: str) -> str:
        """Start a new tracing session"""
        session_id = f"{self.agent_name}_{session_name}_{int(time.time())}"

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
            }
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
            metadata=metadata
        )
        self.events.append(event)

        # Notify plugins
        for plugin in self.plugins:
            try:
                plugin.log_event(event)
            except Exception as e:
                print(f"⚠️ Plugin error in log_event: {e}")
    
    def _save_session_trace(self, session_id: str):
        """Save session trace to file"""
        if not self.enabled:
            return
            
        session_events = [e for e in self.events if e.session_id == session_id]
        
        trace_data = {
            'session_id': session_id,
            'agent_name': self.agent_name,
            'start_time': min(e.timestamp for e in session_events) if session_events else time.time(),
            'end_time': time.time(),
            'total_events': len(session_events),
            'events': [
                {
                    'timestamp': e.timestamp,
                    'event_type': e.event_type,
                    'method_name': e.method_name,
                    'duration': e.duration,
                    'success': e.success,
                    'error': e.error,
                    'metadata': e.metadata
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