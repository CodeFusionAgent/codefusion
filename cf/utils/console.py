"""
Rich Console - Beautiful CLI output for CodeFusion

Provides:
- Progress bars for long operations
- Syntax highlighting for code
- Tables for structured data
- Live streaming output
- Panels and formatted sections
- Markdown rendering
"""

from typing import Optional, List, Dict, Any, Iterator
from contextlib import contextmanager

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text
from rich.tree import Tree
from rich.status import Status


# Global console instance
console = Console()


# ============================================================================
# Progress Tracking
# ============================================================================

def create_progress() -> Progress:
    """Create a progress bar with standard columns"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


@contextmanager
def progress_context(description: str = "Processing..."):
    """Context manager for simple progress tracking"""
    with console.status(f"[bold blue]{description}") as status:
        yield status


class AnalysisProgress:
    """
    Progress tracker for multi-phase analysis.

    Usage:
        with AnalysisProgress() as progress:
            progress.start_phase("discovery", total=10)
            for file in files:
                progress.advance("discovery")
            progress.complete_phase("discovery")
    """

    def __init__(self):
        self.progress = create_progress()
        self.tasks: Dict[str, Any] = {}

    def __enter__(self):
        self.progress.__enter__()
        return self

    def __exit__(self, *args):
        self.progress.__exit__(*args)

    def start_phase(self, name: str, total: int = 100, description: str = None):
        """Start a new phase"""
        desc = description or f"[cyan]{name.title()}"
        self.tasks[name] = self.progress.add_task(desc, total=total)

    def advance(self, name: str, amount: int = 1):
        """Advance a phase"""
        if name in self.tasks:
            self.progress.advance(self.tasks[name], amount)

    def update(self, name: str, completed: int = None, description: str = None):
        """Update a phase"""
        if name in self.tasks:
            kwargs = {}
            if completed is not None:
                kwargs['completed'] = completed
            if description is not None:
                kwargs['description'] = description
            self.progress.update(self.tasks[name], **kwargs)

    def complete_phase(self, name: str):
        """Mark a phase as complete"""
        if name in self.tasks:
            task = self.progress.tasks[self.tasks[name]]
            self.progress.update(self.tasks[name], completed=task.total)


# ============================================================================
# Code Display
# ============================================================================

def print_code(code: str, language: str = "python", title: str = None,
               line_numbers: bool = True, highlight_lines: set = None):
    """Print syntax-highlighted code"""
    syntax = Syntax(
        code,
        language,
        theme="monokai",
        line_numbers=line_numbers,
        highlight_lines=highlight_lines or set()
    )

    if title:
        console.print(Panel(syntax, title=f"[bold]{title}[/bold]", border_style="blue"))
    else:
        console.print(syntax)


def print_file(file_path: str, code: str, language: str = None):
    """Print a file with syntax highlighting"""
    # Auto-detect language from extension - use extension directly
    if language is None:
        if '.' in file_path:
            # Use extension without dot as language hint
            language = file_path.split('.')[-1]
        else:
            language = 'text'

    print_code(code, language, title=file_path)


# ============================================================================
# Tables
# ============================================================================

def print_table(title: str, columns: List[str], rows: List[List[str]],
                show_header: bool = True):
    """Print a formatted table"""
    table = Table(title=title, show_header=show_header)

    for col in columns:
        table.add_column(col, style="cyan")

    for row in rows:
        table.add_row(*row)

    console.print(table)


def print_file_table(files: List[Dict[str, Any]], title: str = "Files"):
    """Print a table of files with metadata"""
    table = Table(title=title)
    table.add_column("File", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Lines", justify="right")
    table.add_column("Relevance", justify="right")

    for f in files:
        table.add_row(
            f.get('path', f.get('file_path', 'unknown')),
            f.get('type', f.get('language', '-')),
            str(f.get('lines', f.get('line_count', '-'))),
            f"{f.get('relevance', f.get('score', 0)):.2f}" if 'relevance' in f or 'score' in f else '-'
        )

    console.print(table)


def print_metrics_table(metrics: Dict[str, Any], title: str = "Metrics"):
    """Print a metrics summary table"""
    table = Table(title=title)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    for key, value in metrics.items():
        if isinstance(value, float):
            table.add_row(key, f"{value:.3f}")
        else:
            table.add_row(key, str(value))

    console.print(table)


# ============================================================================
# Panels and Sections
# ============================================================================

def print_panel(content: str, title: str = None, style: str = "blue"):
    """Print content in a bordered panel"""
    console.print(Panel(content, title=title, border_style=style))


def print_section(title: str, content: str, style: str = "bold blue"):
    """Print a titled section"""
    console.print(f"\n[{style}]{title}[/{style}]")
    console.print(content)


def print_header(text: str):
    """Print a prominent header"""
    console.print(Panel(f"[bold white]{text}[/bold white]", style="bold blue"))


def print_success(message: str):
    """Print a success message"""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str):
    """Print an error message"""
    console.print(f"[bold red]✗[/bold red] {message}")


def print_warning(message: str):
    """Print a warning message"""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_info(message: str):
    """Print an info message"""
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


# ============================================================================
# Markdown Rendering
# ============================================================================

def print_markdown(text: str):
    """Render and print markdown"""
    md = Markdown(text)
    console.print(md)


def print_response(response: str, title: str = "Response"):
    """Print an LLM response with markdown rendering"""
    console.print(Panel(Markdown(response), title=f"[bold]{title}[/bold]", border_style="green"))


# ============================================================================
# Tree Display
# ============================================================================

def print_file_tree(files: List[str], title: str = "Files"):
    """Print files as a tree structure"""
    tree = Tree(f"[bold]{title}[/bold]")

    # Build tree structure from paths
    paths_dict: Dict[str, Any] = {}
    for f in files:
        parts = f.split('/')
        current = paths_dict
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]

    def add_to_tree(node, d: dict, prefix: str = ""):
        for name, children in sorted(d.items()):
            if children:
                branch = node.add(f"[bold blue]{name}/[/bold blue]")
                add_to_tree(branch, children, prefix + name + "/")
            else:
                node.add(f"[green]{name}[/green]")

    add_to_tree(tree, paths_dict)
    console.print(tree)


# ============================================================================
# Streaming Output
# ============================================================================

class StreamingResponse:
    """
    Live streaming response display.

    Usage:
        with StreamingResponse("Analyzing...") as stream:
            for chunk in get_chunks():
                stream.update(chunk)
    """

    def __init__(self, title: str = "Response"):
        self.title = title
        self.content = ""
        self.live: Optional[Live] = None

    def __enter__(self):
        self.live = Live(
            Panel("", title=f"[bold]{self.title}[/bold]", border_style="green"),
            console=console,
            refresh_per_second=10,
        )
        self.live.__enter__()
        return self

    def __exit__(self, *args):
        if self.live:
            self.live.__exit__(*args)

    def update(self, chunk: str):
        """Add a chunk to the response"""
        self.content += chunk
        if self.live:
            self.live.update(
                Panel(Markdown(self.content), title=f"[bold]{self.title}[/bold]", border_style="green")
            )

    def set_content(self, content: str):
        """Replace the entire content"""
        self.content = content
        if self.live:
            self.live.update(
                Panel(Markdown(self.content), title=f"[bold]{self.title}[/bold]", border_style="green")
            )


class StatusLine:
    """
    Status line for showing current operation.

    Usage:
        with StatusLine() as status:
            status.update("Discovering files...")
            # do work
            status.update("Analyzing code...")
    """

    def __init__(self, initial: str = "Starting..."):
        self.status: Optional[Status] = None
        self.initial = initial

    def __enter__(self):
        self.status = console.status(f"[bold blue]{self.initial}")
        self.status.__enter__()
        return self

    def __exit__(self, *args):
        if self.status:
            self.status.__exit__(*args)

    def update(self, message: str):
        """Update the status message"""
        if self.status:
            self.status.update(f"[bold blue]{message}")


# ============================================================================
# Analysis Output Formatting
# ============================================================================

def print_discovery_result(result: Dict[str, Any]):
    """Print formatted discovery results"""
    console.print()
    print_header("Discovery Results")

    # File summary
    files = result.get('files', result.get('discovered_files', []))
    if files:
        print_file_table(files, title="Discovered Files")

    # Strategy used
    if 'strategy' in result:
        print_info(f"Strategy: {result['strategy']}")

    # Timing
    if 'time_ms' in result:
        print_info(f"Time: {result['time_ms']:.1f}ms")


def print_analysis_result(result: Dict[str, Any]):
    """Print formatted analysis results"""
    console.print()
    print_header("Analysis Results")

    # Main narrative/answer
    answer = result.get('answer', result.get('narrative', result.get('summary', '')))
    if answer:
        print_response(answer, title="Answer")

    # Files analyzed
    files = result.get('files_analyzed', [])
    if files:
        console.print(f"\n[dim]Analyzed {len(files)} files[/dim]")

    # Confidence
    if 'confidence' in result:
        console.print(f"[dim]Confidence: {result['confidence']:.2f}[/dim]")

    # Timing
    if 'execution_time' in result:
        console.print(f"[dim]Time: {result['execution_time']:.2f}s[/dim]")


def print_tool_call(tool_name: str, params: Dict[str, Any]):
    """Print a tool call in a formatted way"""
    # Truncate long params
    formatted_params = []
    for k, v in params.items():
        v_str = str(v)
        if len(v_str) > 50:
            v_str = v_str[:47] + "..."
        formatted_params.append(f"{k}={v_str}")

    params_str = ", ".join(formatted_params)
    console.print(f"[bold cyan]→[/bold cyan] {tool_name}({params_str})")


def print_agent_status(agent_name: str, status: str, detail: str = None):
    """Print agent status update"""
    status_colors = {
        'starting': 'blue',
        'running': 'yellow',
        'complete': 'green',
        'error': 'red',
    }
    color = status_colors.get(status.lower(), 'white')

    msg = f"[bold {color}]●[/bold {color}] [bold]{agent_name}[/bold]: {status}"
    if detail:
        msg += f" - {detail}"

    console.print(msg)
