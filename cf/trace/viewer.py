"""
Trace Viewer

Visualizes trace files with ASCII timelines and HTML reports.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class TraceViewer:
    """
    Viewer for CodeFusion trace files.

    Provides visualization options:
    - ASCII timeline (console output)
    - HTML interactive report
    - Session summary statistics
    """

    def __init__(self, trace_dir: str = "cf_trace"):
        """
        Initialize trace viewer.

        Args:
            trace_dir: Directory containing trace files
        """
        self.trace_dir = Path(trace_dir)

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load trace session from file.

        Args:
            session_id: Session ID to load

        Returns:
            Trace data dictionary or None if not found
        """
        trace_file = self.trace_dir / f"{session_id}.json"

        if not trace_file.exists():
            print(f"❌ Trace file not found: {trace_file}")
            return None

        with open(trace_file, 'r') as f:
            return json.load(f)

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List available trace sessions.

        Args:
            limit: Maximum sessions to return

        Returns:
            List of session info dicts with id, agent, start_time
        """
        if not self.trace_dir.exists():
            return []

        sessions = []
        for trace_file in sorted(self.trace_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(trace_file, 'r') as f:
                    data = json.load(f)
                    sessions.append({
                        'session_id': data.get('session_id'),
                        'agent_name': data.get('agent_name'),
                        'start_time': data.get('start_time'),
                        'total_events': data.get('total_events'),
                        'duration': data.get('end_time', 0) - data.get('start_time', 0)
                    })
            except Exception as e:
                print(f"⚠️ Error loading {trace_file}: {e}")

        return sessions

    def visualize_timeline(self, session_id: str, show_hierarchy: bool = True):
        """
        Print ASCII timeline of trace events with optional hierarchical view.

        Args:
            session_id: Session ID to visualize
            show_hierarchy: Show hierarchical span tree
        """
        data = self.load_session(session_id)
        if not data:
            return

        # Display header
        print(f"\n{'=' * 80}")
        print(f"Trace Timeline: {data['session_id']}")
        print(f"Agent: {data['agent_name']}")
        print(f"Events: {data['total_events']}")
        print(f"Duration: {data.get('end_time', 0) - data.get('start_time', 0):.2f}s")

        # Display metrics if available
        metrics = data.get('metrics', {})
        if metrics:
            print(f"\n📊 Metrics:")
            print(f"  Total Tokens: {metrics.get('total_tokens', 0):,}")
            print(f"  Total Cost: ${metrics.get('total_cost_usd', 0):.4f}")
            print(f"  LLM Calls: {metrics.get('llm_calls', 0)}")
            print(f"  Success Rate: {metrics.get('success_rate', 0):.1%}")

        print(f"{'=' * 80}\n")

        events = data.get('events', [])
        if not events:
            print("No events found.")
            return

        if show_hierarchy:
            self._visualize_hierarchical(events, data.get('start_time', 0))
        else:
            self._visualize_flat(events, data.get('start_time', 0))

    def _visualize_flat(self, events: List[Dict[str, Any]], start_time: float):
        """Visualize events in flat timeline format"""
        event_counts = {}
        total_duration = 0

        for event in events:
            rel_time = event['timestamp'] - start_time
            event_type = event['event_type']
            method = event.get('method_name', event_type)
            duration = event.get('duration', 0)
            success = event.get('success', True)
            error = event.get('error')
            tokens = event.get('tokens_used', 0)
            cost = event.get('cost_usd', 0)
            pass_num = event.get('pass_number', 1)

            # Count events
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            total_duration += duration

            # Format timeline entry
            status_icon = "✓" if success else "✗"
            duration_str = f"{duration*1000:.0f}ms" if duration > 0 else ""

            # Add pass number for multi-pass tracking
            pass_str = f"P{pass_num}" if pass_num > 1 else "  "

            print(f"[+{rel_time:6.2f}s] {pass_str} {status_icon} {event_type:15s} {method:30s} {duration_str:8s}", end="")

            # Show tokens/cost for LLM calls
            if tokens > 0:
                print(f" ({tokens} tok, ${cost:.4f})", end="")
            print()

            if error:
                print(f"            └─ Error: {error}")

        # Print summary
        print(f"\n{'-' * 80}")
        print("Event Summary:")
        for event_type, count in sorted(event_counts.items()):
            print(f"  {event_type:20s}: {count:3d}")
        print(f"  {'Total Duration':20s}: {total_duration:.2f}s")
        print(f"{'-' * 80}\n")

    def _visualize_hierarchical(self, events: List[Dict[str, Any]], start_time: float):
        """Visualize events in hierarchical tree format"""
        # Build span tree
        span_map = {}
        root_spans = []

        for event in events:
            span_id = event.get('span_id', '')
            parent_id = event.get('parent_span_id')

            if span_id:
                span_map[span_id] = event

            if not parent_id:
                root_spans.append(event)

        # Print hierarchical tree
        print("Hierarchical Trace:")
        print()

        def print_span(event: Dict[str, Any], depth: int = 0, start_time: float = start_time):
            """Recursively print span tree"""
            indent = "  " * depth
            connector = "└─" if depth > 0 else ""

            rel_time = event['timestamp'] - start_time
            event_type = event['event_type']
            method = event.get('method_name', event_type)
            duration = event.get('duration', 0)
            success = event.get('success', True)
            tokens = event.get('tokens_used', 0)
            cost = event.get('cost_usd', 0)
            pass_num = event.get('pass_number', 1)
            agent = event.get('agent_name', '')

            status_icon = "✓" if success else "✗"
            duration_str = f"{duration*1000:.0f}ms" if duration > 0 else ""

            # Format output
            line = f"{indent}{connector} [{pass_num}] {status_icon} {method}"
            if duration_str:
                line += f" ({duration_str})"
            if tokens > 0:
                line += f" [🔤 {tokens} tok, ${cost:.4f}]"
            if agent and agent != 'supervisor':
                line += f" @{agent}"

            print(line)

            # Find and print children
            span_id = event.get('span_id', '')
            children = [e for e in events if e.get('parent_span_id') == span_id]
            for child in sorted(children, key=lambda x: x['timestamp']):
                print_span(child, depth + 1, start_time)

        # Print each root span
        for root in sorted(root_spans, key=lambda x: x['timestamp']):
            print_span(root, 0, start_time)

        # Print aggregated summary
        print(f"\n{'-' * 80}")
        print("Pass-by-Pass Summary:")

        # Group by pass
        pass_groups = {}
        for event in events:
            pass_num = event.get('pass_number', 1)
            if pass_num not in pass_groups:
                pass_groups[pass_num] = []
            pass_groups[pass_num].append(event)

        for pass_num in sorted(pass_groups.keys()):
            pass_events = pass_groups[pass_num]
            total_tokens = sum(e.get('tokens_used', 0) for e in pass_events)
            total_cost = sum(e.get('cost_usd', 0) for e in pass_events)
            total_dur = sum(e.get('duration', 0) for e in pass_events)

            print(f"  Pass {pass_num}: {len(pass_events)} events, {total_dur:.2f}s, {total_tokens} tokens, ${total_cost:.4f}")

        print(f"{'-' * 80}\n")

    def generate_html_report(self, session_id: str, output_file: Optional[str] = None):
        """
        Generate interactive HTML report for trace session.

        Args:
            session_id: Session ID to visualize
            output_file: Output file path (default: {session_id}.html)
        """
        data = self.load_session(session_id)
        if not data:
            return

        if output_file is None:
            output_file = f"{session_id}.html"

        events = data.get('events', [])
        start_time = events[0]['timestamp'] if events else 0

        # Build HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Trace: {data['session_id']}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .summary {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .event {{
            background: white;
            padding: 12px;
            margin-bottom: 8px;
            border-left: 4px solid #667eea;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .event.error {{
            border-left-color: #e74c3c;
        }}
        .event-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
        }}
        .event-type {{
            font-weight: bold;
            color: #667eea;
        }}
        .event-time {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .event-duration {{
            background: #ecf0f1;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85em;
        }}
        .error-message {{
            color: #e74c3c;
            margin-top: 8px;
            padding: 8px;
            background: #fadbd8;
            border-radius: 4px;
        }}
        .timeline {{
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Trace Report</h1>
        <p><strong>Session:</strong> {data['session_id']}</p>
        <p><strong>Agent:</strong> {data['agent_name']}</p>
        <p><strong>Duration:</strong> {data.get('end_time', 0) - data.get('start_time', 0):.2f}s</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Events:</strong> {data['total_events']}</p>
        <p><strong>Start Time:</strong> {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="timeline">
        <h2>Timeline</h2>
"""

        for event in events:
            rel_time = event['timestamp'] - start_time
            event_type = event['event_type']
            method = event.get('method_name', event_type)
            duration = event.get('duration', 0)
            success = event.get('success', True)
            error = event.get('error')

            error_class = '' if success else 'error'
            status_icon = '✓' if success else '✗'

            html += f"""
        <div class="event {error_class}">
            <div class="event-header">
                <div>
                    <span style="font-size: 1.2em;">{status_icon}</span>
                    <span class="event-type">{event_type}</span>
                    <span style="color: #95a5a6;">→</span>
                    <span>{method}</span>
                </div>
                <div>
                    <span class="event-time">+{rel_time:.2f}s</span>
                    {"<span class='event-duration'>" + f"{duration*1000:.0f}ms" + "</span>" if duration > 0 else ""}
                </div>
            </div>
"""

            if error:
                html += f"""
            <div class="error-message">
                <strong>Error:</strong> {error}
            </div>
"""

            html += "        </div>\n"

        html += """
    </div>
</body>
</html>
"""

        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            f.write(html)

        print(f"✅ HTML report generated: {output_path.absolute()}")

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for a session.

        Args:
            session_id: Session ID

        Returns:
            Summary dict with stats
        """
        data = self.load_session(session_id)
        if not data:
            return {}

        events = data.get('events', [])
        if not events:
            return {}

        # Calculate statistics
        event_types = {}
        total_duration = 0
        success_count = 0
        error_count = 0

        for event in events:
            event_type = event['event_type']
            event_types[event_type] = event_types.get(event_type, 0) + 1

            duration = event.get('duration', 0)
            total_duration += duration

            if event.get('success', True):
                success_count += 1
            else:
                error_count += 1

        return {
            'session_id': data['session_id'],
            'agent_name': data['agent_name'],
            'total_events': len(events),
            'total_duration': total_duration,
            'success_count': success_count,
            'error_count': error_count,
            'success_rate': success_count / len(events) if events else 0,
            'event_types': event_types,
            'start_time': events[0]['timestamp'],
            'end_time': events[-1]['timestamp']
        }


# Command-line interface
if __name__ == "__main__":
    import sys

    viewer = TraceViewer()

    if len(sys.argv) < 2:
        print("Usage: python -m cf.trace.viewer <command> [args]")
        print("\nCommands:")
        print("  list                    - List recent sessions")
        print("  timeline <session_id>   - Show ASCII timeline")
        print("  html <session_id>       - Generate HTML report")
        print("  summary <session_id>    - Show session summary")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        sessions = viewer.list_sessions()
        print(f"\nRecent Trace Sessions ({len(sessions)}):\n")
        for s in sessions:
            print(f"  {s['session_id']:60s} | {s['agent_name']:15s} | {s['duration']:.2f}s | {s['total_events']} events")

    elif command == "timeline" and len(sys.argv) > 2:
        viewer.visualize_timeline(sys.argv[2])

    elif command == "html" and len(sys.argv) > 2:
        viewer.generate_html_report(sys.argv[2])

    elif command == "summary" and len(sys.argv) > 2:
        summary = viewer.get_session_summary(sys.argv[2])
        print(json.dumps(summary, indent=2))

    else:
        print("Invalid command or missing arguments")
