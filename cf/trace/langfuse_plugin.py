"""
Langfuse Tracer Plugin

Implements TracerPlugin for Langfuse observability platform.
Enables advanced monitoring and analytics for LLM applications.

Installation:
    pip install langfuse

Usage:
    from cf.trace.tracer import Tracer
    from cf.trace.langfuse_plugin import LangfusePlugin

    plugin = LangfusePlugin(
        public_key="pk-...",
        secret_key="sk-...",
        host="https://cloud.langfuse.com"
    )

    tracer = Tracer("my_agent", config, plugins=[plugin])
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path

from cf.trace.tracer import TracerPlugin, TraceEvent

# Optional dependency - Langfuse may not be installed
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None


class LangfusePlugin(TracerPlugin):
    """
    Langfuse tracer plugin.

    Sends trace events to Langfuse for:
    - LLM observability
    - Cost tracking
    - Performance monitoring
    - Debugging
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: str = "https://cloud.langfuse.com",
        enabled: bool = True
    ):
        """
        Initialize Langfuse plugin.

        Args:
            public_key: Langfuse public key (or from LANGFUSE_PUBLIC_KEY env)
            secret_key: Langfuse secret key (or from LANGFUSE_SECRET_KEY env)
            host: Langfuse host URL
            enabled: Whether plugin is enabled
        """
        self.enabled = enabled
        self._langfuse = None
        self._traces = {}  # session_id -> trace object

        if not enabled:
            return

        try:
            from langfuse import Langfuse

            self._langfuse = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host
            )
            print(" Langfuse plugin initialized")
        except ImportError:
            print("� Langfuse not installed. Run: pip install langfuse")
            self.enabled = False
        except Exception as e:
            print(f"� Failed to initialize Langfuse: {e}")
            self.enabled = False

    def start_session(self, session_id: str, metadata: Dict[str, Any] = None):
        """Start a Langfuse trace"""
        if not self.enabled or not self._langfuse:
            return

        try:
            trace = self._langfuse.trace(
                name=session_id,
                metadata=metadata or {},
                session_id=session_id
            )
            self._traces[session_id] = trace
        except Exception as e:
            print(f"� Langfuse start_session error: {e}")

    def end_session(self, session_id: str, metadata: Dict[str, Any] = None):
        """End a Langfuse trace"""
        if not self.enabled or not self._langfuse:
            return

        try:
            if session_id in self._traces:
                trace = self._traces[session_id]
                # Update trace with final metadata
                if metadata:
                    trace.update(metadata=metadata)
                del self._traces[session_id]
        except Exception as e:
            print(f"� Langfuse end_session error: {e}")

    def log_event(self, event: TraceEvent):
        """Log event to Langfuse"""
        if not self.enabled or not self._langfuse:
            return

        try:
            session_id = event.session_id

            if session_id not in self._traces:
                # Create trace if doesn't exist
                self.start_session(session_id, {})

            trace = self._traces.get(session_id)
            if not trace:
                return

            # Map event type to Langfuse span
            if event.event_type == "llm_call" or event.event_type == "llm_generation":
                # Create LLM generation span
                generation = trace.generation(
                    name=event.method_name or "llm_call",
                    start_time=event.timestamp,
                    end_time=event.timestamp + event.duration,
                    model=event.metadata.get('model', 'unknown'),
                    metadata={
                        'success': event.success,
                        'error': event.error,
                        **event.metadata
                    }
                )

                # Add usage info if available
                if 'usage' in event.metadata:
                    usage = event.metadata['usage']
                    generation.update(
                        usage={
                            'input': usage.get('prompt_tokens', 0),
                            'output': usage.get('completion_tokens', 0),
                            'total': usage.get('total_tokens', 0)
                        }
                    )

            elif event.event_type == "tool_call":
                # Create tool span
                trace.span(
                    name=event.method_name or "tool_call",
                    start_time=event.timestamp,
                    end_time=event.timestamp + event.duration,
                    metadata={
                        'success': event.success,
                        'error': event.error,
                        **event.metadata
                    }
                )

            else:
                # Generic span for other events
                trace.span(
                    name=event.method_name or event.event_type,
                    start_time=event.timestamp,
                    end_time=event.timestamp + event.duration,
                    metadata={
                        'event_type': event.event_type,
                        'success': event.success,
                        'error': event.error,
                        **event.metadata
                    }
                )

        except Exception as e:
            print(f"� Langfuse log_event error: {e}")

    def flush(self):
        """Flush pending events to Langfuse"""
        if not self.enabled or not self._langfuse:
            return

        try:
            self._langfuse.flush()
        except Exception as e:
            print(f"� Langfuse flush error: {e}")


class LocalFilePlugin(TracerPlugin):
    """
    Simple file-based tracer plugin.

    Alternative to default Tracer file output - demonstrates plugin pattern.
    """

    def __init__(self, output_dir: str = "cf_trace_plugin"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.sessions = {}  # session_id -> events list

    def start_session(self, session_id: str, metadata: Dict[str, Any] = None):
        """Start session"""
        self.sessions[session_id] = {
            'session_id': session_id,
            'metadata': metadata or {},
            'events': []
        }

    def end_session(self, session_id: str, metadata: Dict[str, Any] = None):
        """End session and save to file"""
        if session_id not in self.sessions:
            return

        session_data = self.sessions[session_id]
        if metadata:
            session_data['metadata'].update(metadata)

        # Save to file
        filepath = self.output_dir / f"{session_id}.json"
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)

        # Clean up
        del self.sessions[session_id]

    def log_event(self, event: TraceEvent):
        """Log event"""
        session_id = event.session_id

        if session_id not in self.sessions:
            self.start_session(session_id, {})

        self.sessions[session_id]['events'].append({
            'timestamp': event.timestamp,
            'event_type': event.event_type,
            'method_name': event.method_name,
            'duration': event.duration,
            'success': event.success,
            'error': event.error,
            'metadata': event.metadata
        })

    def flush(self):
        """Flush (no-op for file plugin)"""
        pass
