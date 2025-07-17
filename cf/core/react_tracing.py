"""
ReAct Tracing and Logging for CodeFusion agents.

This module provides comprehensive tracing and logging capabilities for ReAct loops,
including execution traces, performance metrics, and debugging information.
"""

import json
import os
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
import uuid


@dataclass
class ReActTrace:
    """A single trace entry in the ReAct loop."""
    trace_id: str
    agent_name: str
    iteration: int
    phase: str  # 'reason', 'act', 'observe'
    timestamp: float
    duration: float = 0.0
    content: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


@dataclass
class ReActSession:
    """A complete ReAct session trace."""
    session_id: str
    agent_name: str
    goal: str
    start_time: float
    end_time: Optional[float] = None
    total_iterations: int = 0
    traces: List[ReActTrace] = field(default_factory=list)
    final_result: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class ReActTracer:
    """
    Tracer for ReAct agent execution with logging and performance monitoring.
    """
    
    def __init__(self, log_level: str = "INFO", trace_dir: Optional[str] = None):
        self.logger = logging.getLogger("ReActTracer")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Setup file handler for traces if directory specified
        self.trace_dir = Path(trace_dir) if trace_dir else None
        if self.trace_dir:
            self.trace_dir.mkdir(exist_ok=True)
            
        # Active sessions
        self.active_sessions: Dict[str, ReActSession] = {}
        
        # Performance tracking
        self.global_metrics = {
            'total_sessions': 0,
            'total_iterations': 0,
            'total_errors': 0,
            'avg_session_duration': 0.0,
            'agent_usage': {},
            'phase_timings': {'reason': [], 'act': [], 'observe': []}
        }
        
    def start_session(self, agent_name: str, goal: str) -> str:
        """Start a new ReAct session."""
        session_id = str(uuid.uuid4())[:8]
        
        session = ReActSession(
            session_id=session_id,
            agent_name=agent_name,
            goal=goal,
            start_time=time.time()
        )
        
        self.active_sessions[session_id] = session
        self.global_metrics['total_sessions'] += 1
        self.global_metrics['agent_usage'][agent_name] = self.global_metrics['agent_usage'].get(agent_name, 0) + 1
        
        self.logger.info(f"🎯 Started ReAct session {session_id} for {agent_name}: {goal}")
        
        return session_id
    
    def trace_phase(self, session_id: str, phase: str, iteration: int, 
                   content: Dict[str, Any], duration: float = 0.0, 
                   success: bool = True, error: Optional[str] = None) -> str:
        """Trace a phase of the ReAct loop."""
        if session_id not in self.active_sessions:
            self.logger.warning(f"Session {session_id} not found for tracing")
            return ""
        
        session = self.active_sessions[session_id]
        trace_id = f"{session_id}-{iteration}-{phase}"
        
        trace = ReActTrace(
            trace_id=trace_id,
            agent_name=session.agent_name,
            iteration=iteration,
            phase=phase,
            timestamp=time.time(),
            duration=duration,
            content=content,
            success=success,
            error=error
        )
        
        session.traces.append(trace)
        
        # Update metrics
        if phase in self.global_metrics['phase_timings']:
            self.global_metrics['phase_timings'][phase].append(duration)
        
        if not success:
            self.global_metrics['total_errors'] += 1
        
        # Log the trace
        status = "✅" if success else "❌"
        self.logger.info(f"{status} {session.agent_name} [Iter {iteration}] {phase.upper()}: "
                        f"{content.get('summary', str(content)[:100])}")
        
        if error:
            self.logger.error(f"❌ Error in {phase}: {error}")
        
        if duration > 0:
            self.logger.debug(f"⏱️  {phase} took {duration:.2f}s")
        
        return trace_id
    
    def end_session(self, session_id: str, final_result: Dict[str, Any]) -> ReActSession:
        """End a ReAct session and calculate metrics."""
        if session_id not in self.active_sessions:
            self.logger.warning(f"Session {session_id} not found for ending")
            return None
        
        session = self.active_sessions[session_id]
        session.end_time = time.time()
        session.final_result = final_result
        session.total_iterations = len(set(trace.iteration for trace in session.traces))
        
        # Calculate session metrics
        total_duration = session.end_time - session.start_time
        session.performance_metrics = self._calculate_session_metrics(session)
        
        # Update global metrics
        self.global_metrics['total_iterations'] += session.total_iterations
        
        # Update average session duration
        total_sessions = self.global_metrics['total_sessions']
        current_avg = self.global_metrics['avg_session_duration']
        self.global_metrics['avg_session_duration'] = (
            (current_avg * (total_sessions - 1) + total_duration) / total_sessions
        )
        
        self.logger.info(f"🏁 Completed ReAct session {session_id} in {total_duration:.2f}s "
                        f"({session.total_iterations} iterations)")
        
        # Save trace to file if trace directory is configured
        if self.trace_dir:
            self._save_session_trace(session)
        
        # Remove from active sessions
        completed_session = self.active_sessions.pop(session_id)
        
        return completed_session
    
    def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get metrics for a specific session."""
        if session_id not in self.active_sessions:
            return {}
        
        session = self.active_sessions[session_id]
        return self._calculate_session_metrics(session)
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global performance metrics."""
        # Calculate averages for phase timings
        metrics = self.global_metrics.copy()
        
        for phase, timings in metrics['phase_timings'].items():
            if timings:
                metrics[f'avg_{phase}_duration'] = sum(timings) / len(timings)
                metrics[f'max_{phase}_duration'] = max(timings)
                metrics[f'min_{phase}_duration'] = min(timings)
            else:
                metrics[f'avg_{phase}_duration'] = 0.0
                metrics[f'max_{phase}_duration'] = 0.0
                metrics[f'min_{phase}_duration'] = 0.0
        
        return metrics
    
    def _calculate_session_metrics(self, session: ReActSession) -> Dict[str, Any]:
        """Calculate performance metrics for a session."""
        if not session.traces:
            return {}
        
        phase_timings = {'reason': [], 'act': [], 'observe': []}
        total_duration = 0.0
        
        for trace in session.traces:
            if trace.phase in phase_timings:
                phase_timings[trace.phase].append(trace.duration)
            total_duration += trace.duration
        
        metrics = {
            'total_duration': session.end_time - session.start_time if session.end_time else 0,
            'processing_duration': total_duration,
            'total_traces': len(session.traces),
            'iterations': session.total_iterations,
            'errors': len([t for t in session.traces if not t.success]),
            'success_rate': len([t for t in session.traces if t.success]) / len(session.traces)
        }
        
        # Phase-specific metrics
        for phase, timings in phase_timings.items():
            if timings:
                metrics[f'{phase}_count'] = len(timings)
                metrics[f'{phase}_total_time'] = sum(timings)
                metrics[f'{phase}_avg_time'] = sum(timings) / len(timings)
                metrics[f'{phase}_max_time'] = max(timings)
            else:
                metrics[f'{phase}_count'] = 0
                metrics[f'{phase}_total_time'] = 0.0
                metrics[f'{phase}_avg_time'] = 0.0
                metrics[f'{phase}_max_time'] = 0.0
        
        return metrics
    
    def _save_session_trace(self, session: ReActSession):
        """Save session trace to file."""
        try:
            trace_file = self.trace_dir / f"trace_{session.session_id}_{session.agent_name}.json"
            
            # Convert to serializable format
            trace_data = {
                'session': asdict(session),
                'traces': [asdict(trace) for trace in session.traces]
            }
            
            with open(trace_file, 'w') as f:
                json.dump(trace_data, f, indent=2, default=str)
            
            self.logger.debug(f"💾 Saved trace to {trace_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save trace: {e}")
    
    def export_metrics(self, output_file: str):
        """Export global metrics to file."""
        try:
            metrics = self.get_global_metrics()
            
            with open(output_file, 'w') as f:
                json.dump(metrics, f, indent=2, default=str)
            
            self.logger.info(f"📊 Exported metrics to {output_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}")
    
    def get_trace_summary(self, session_id: str) -> str:
        """Get a human-readable summary of traces for a session."""
        if session_id not in self.active_sessions:
            return f"Session {session_id} not found"
        
        session = self.active_sessions[session_id]
        summary = f"ReAct Trace Summary for {session.agent_name} (Session: {session_id})\\n"
        summary += f"Goal: {session.goal}\\n"
        summary += f"Iterations: {session.total_iterations}\\n"
        summary += "=" * 50 + "\\n"
        
        for trace in session.traces:
            status = "✅" if trace.success else "❌"
            summary += f"{status} Iter {trace.iteration} - {trace.phase.upper()}: "
            summary += f"{trace.content.get('summary', 'No summary')}\\n"
            
            if trace.error:
                summary += f"   Error: {trace.error}\\n"
            
            if trace.duration > 0:
                summary += f"   Duration: {trace.duration:.2f}s\\n"
        
        return summary


# Global tracer instance
tracer = ReActTracer(
    log_level=os.getenv('CF_LOG_LEVEL', 'INFO'),
    trace_dir=os.getenv('CF_TRACE_DIR')
)