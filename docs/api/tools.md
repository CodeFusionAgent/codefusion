# Tools Ecosystem

::: cf.tools.advanced_tools

The CodeFusion ReAct framework provides a comprehensive set of 8 specialized tools for code exploration and analysis.

## Core Tools

### Directory and File Operations

- **SCAN_DIRECTORY**: Recursive directory structure exploration
- **LIST_FILES**: Pattern-based file discovery with filtering
- **READ_FILE**: Intelligent file content reading with limits

### Search and Analysis

- **SEARCH_FILES**: Multi-file pattern searching with context
- **ANALYZE_CODE**: Code structure and complexity analysis

### AI-Powered Tools

- **LLM_REASONING**: AI-powered decision making and analysis
- **LLM_SUMMARY**: Intelligent content summarization

### Caching Operations

- **CACHE_OPERATIONS**: Persistent memory management with TTL

## Usage Examples

### Basic Tool Usage

```python
from cf.tools.advanced_tools import AdvancedTools
from cf.aci.repo import LocalCodeRepo

# Initialize tools
repo = LocalCodeRepo("/path/to/repository")
tools = AdvancedTools(repo)

# Scan directory
result = tools.scan_directory(".", max_depth=2)
print(f"Found {len(result['contents'])} items")

# Search files
search_result = tools.search_files("authentication", file_types=['.py'], max_results=10)
print(f"Found {len(search_result['results'])} matches")

# Read file
file_content = tools.read_file("main.py", max_lines=100)
print(f"Read {len(file_content['content'])} characters")
```

### Advanced Tool Integration

Tools are automatically integrated with ReAct agents through the ActionType system:

```python
from cf.core.react_agent import ReActAction, ActionType

# Tools are used via actions
action = ReActAction(
    action_type=ActionType.SCAN_DIRECTORY,
    description="Scan repository structure",
    parameters={'directory': '.', 'max_depth': 3}
)

# Agents automatically route to appropriate tools
```

For complete tool documentation, see the [source code](../../cf/tools/advanced_tools.py).