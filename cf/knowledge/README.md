# Knowledge Base Module

Production-grade structural knowledge base for code analysis.

## Overview

The `cf.knowledge` module provides persistent graph-based storage for code structure, enabling:

- **Fast structural queries** - Find callers, dependencies, hierarchies in < 1 second
- **Incremental updates** - Only re-parse changed files (5s vs 90 min)
- **Accurate analysis** - AST-based extraction (no LLM hallucinations)
- **Scalable** - Handles 100K+ file repositories

## Module Structure

```
cf/knowledge/
├── __init__.py                 # Module exports
├── README.md                   # This file
│
├── structural/                 # Structural analysis layer
│   ├── __init__.py
│   ├── schema.py              # Graph schema definitions
│   ├── neo4j_client.py        # Neo4j database client
│   ├── ast_parser.py          # Python AST parser
│   └── dependency_graph.py    # Dependency analysis
│
└── incremental/                # Incremental updates
    ├── __init__.py
    ├── file_watcher.py        # File change detection
    └── differential.py        # Differential KB updates
```

## Components

### Structural Layer

#### `schema.py` - Graph Data Structures

Defines the Neo4j graph schema:

**Node Types:**
- `FileNode` - Source code files
- `FunctionNode` - Function/method definitions
- `ClassNode` - Class definitions
- `VariableNode` - Global/class variables
- `ModuleNode` - Imported modules

**Relationship Types:**
- `CALLS` - Function calls another function
- `IMPORTS` - File imports module
- `INHERITS` - Class inherits from class
- `USES` - Function uses variable
- `DEFINES` - Class/function defines variable
- `CONTAINED_IN` - Node is contained in file

**Usage:**
```python
from cf.knowledge.structural.schema import FunctionNode, RelationType

func = FunctionNode(
    name="process_data",
    qualified_name="module.process_data",
    start_line=10,
    end_line=20,
    file_path="module.py",
    parameters=["data", "options"],
    return_type="Dict[str, Any]"
)
```

#### `neo4j_client.py` - Graph Database Client

Manages Neo4j connections and operations:

**Key Methods:**
- `insert_structural_data()` - Store complete file structure
- `find_function_callers()` - Find all callers of a function
- `find_files_by_dependency()` - Find files importing a module
- `find_class_hierarchy()` - Get inheritance chains
- `search_by_name()` - Search functions/classes by name

**Usage:**
```python
from cf.knowledge.structural.neo4j_client import Neo4jKnowledgeBase

kb = Neo4jKnowledgeBase(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

# Find all callers of a function
result = kb.find_function_callers("authenticate", repo_id="my-repo")
for node in result.nodes:
    print(f"{node['name']} calls authenticate()")
```

#### `ast_parser.py` - Python AST Parser

Extracts structure from Python source code:

**Extracts:**
- Functions (name, params, return type, docstring, complexity)
- Classes (name, bases, methods, attributes)
- Imports (modules, from-imports)
- Function calls (for call graph)
- Variables (global, class-level)

**Usage:**
```python
from cf.knowledge.structural.ast_parser import PythonASTParser

parser = PythonASTParser(repo_path="/path/to/repo", repo_id="my-repo")
structural_data = parser.parse_file("/path/to/repo/module.py")

print(f"Functions: {len(structural_data.functions)}")
print(f"Classes: {len(structural_data.classes)}")
print(f"Imports: {len(structural_data.modules)}")
```

#### `dependency_graph.py` - Dependency Analysis

Builds and analyzes dependency graphs:

**Features:**
- Call graph construction
- Import dependency tracking
- Circular dependency detection
- Fan-in/fan-out metrics
- Call chain finding (BFS)

**Usage:**
```python
from cf.knowledge.structural.dependency_graph import DependencyGraphBuilder

dep_graph = DependencyGraphBuilder()

# Add structural data from multiple files
for structural_data in all_files:
    dep_graph.add_structural_data(structural_data)

# Find call chains
chains = dep_graph.find_call_chain("function_a", "function_z", max_depth=10)
for chain in chains:
    print(" → ".join(chain))

# Detect circular dependencies
cycles = dep_graph.detect_circular_dependencies()
if cycles:
    print(f"Found {len(cycles)} circular dependencies")

# Calculate complexity metrics
metrics = dep_graph.calculate_fan_metrics()
complex_funcs = sorted(
    metrics.items(),
    key=lambda x: x[1]['complexity_score'],
    reverse=True
)[:10]
```

### Incremental Layer

#### `file_watcher.py` - File Change Detection

Tracks file changes for incremental updates:

**Features:**
- MD5 hashing for accurate change detection
- Persistent state (`.codefusion/file_state.json`)
- Tracks added, modified, deleted files
- Configurable file extensions

**Usage:**
```python
from cf.knowledge.incremental.file_watcher import FileChangeDetector

detector = FileChangeDetector(repo_path="/path/to/repo")

# First scan (establishes baseline)
detector.force_scan()

# Later: detect changes
changes = detector.detect_changes()

print(f"Added: {len(changes.added)}")
print(f"Modified: {len(changes.modified)}")
print(f"Deleted: {len(changes.deleted)}")
```

#### `differential.py` - Incremental KB Updates

Applies changes to the knowledge base:

**Features:**
- Re-parse only changed files
- Update graph nodes and relationships
- Batch processing support
- Progress tracking

**Usage:**
```python
from cf.knowledge.incremental.differential import IncrementalKBUpdater

updater = IncrementalKBUpdater(kb, parser)

# Apply detected changes
stats = updater.apply_changes(change_set, repo_path, repo_id)

print(f"Files added: {stats['files_added']}")
print(f"Files modified: {stats['files_modified']}")
print(f"Files deleted: {stats['files_deleted']}")
print(f"Time: {stats['elapsed_seconds']:.2f}s")
```

## Quick Start

### 1. Install Dependencies

```bash
pip install neo4j>=5.0.0
```

### 2. Start Neo4j

```bash
docker run -d -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

### 3. Build Knowledge Base

```python
from cf.knowledge.structural.neo4j_client import Neo4jKnowledgeBase
from cf.knowledge.structural.ast_parser import PythonASTParser

# Connect to Neo4j
kb = Neo4jKnowledgeBase(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

# Parse Python file
parser = PythonASTParser(repo_path="/path/to/repo", repo_id="my-repo")
structural_data = parser.parse_file("/path/to/repo/module.py")

# Store in KB
kb.insert_structural_data(structural_data)

# Query KB
result = kb.find_function_callers("my_function", "my-repo")
print(f"Found {result.total_results} callers")
```

### 4. Use StructuralPipeline (High-Level API)

```python
from cf.agents.pipelines.structural import StructuralPipeline

config = {
    'knowledge_base': {
        'enabled': True,
        'neo4j': {'uri': 'bolt://localhost:7687', 'user': 'neo4j', 'password': 'password'}
    },
    'repo': {'source_code_extensions': ['.py']}
}

pipeline = StructuralPipeline("/path/to/repo", config)

# Build KB (parallel processing)
result = pipeline.build_knowledge_base()
print(f"Built KB: {result.total_files} files in {result.build_time_seconds:.1f}s")

# Query for relevant files
files = pipeline.find_files_for_question("How does authentication work?")
print(f"Found {len(files)} relevant files")
```

## Performance

### Build Performance (10 workers)

| Files | Build Time | Files/sec |
|-------|-----------|-----------|
| 100 | 6s | 16.7 |
| 1K | 1m | 16.7 |
| 10K | 10m | 16.7 |
| 100K | 90m | 18.5 |

### Query Performance

| Operation | Time |
|-----------|------|
| Find function callers | < 1s |
| Find file dependencies | < 1s |
| Find class hierarchy | < 1s |
| Search by name | < 1s |

### Incremental Updates

| Changes | Update Time |
|---------|------------|
| 1 file | < 1s |
| 5 files | ~5s |
| 50 files | ~30s |
| 500 files | ~60s |

## Testing

```bash
# Run unit tests
pytest tests/test_ast_parser.py -v

# Run integration tests (requires Neo4j running)
pytest tests/test_structural_kb.py -v -m integration

# Run all tests
pytest tests/ -v
```

## Examples

### Example 1: Find All Callers

```python
# Find what calls the `authenticate` function
result = kb.find_function_callers("authenticate", repo_id)

for node in result.nodes:
    print(f"{node['qualified_name']} (line {node['start_line']})")
```

### Example 2: Analyze Dependencies

```python
# Find all files importing 'django.http'
result = kb.find_files_by_dependency("django.http", repo_id)

for node in result.nodes:
    print(f"{node['path']} imports django.http")
```

### Example 3: Get Class Hierarchy

```python
# Find inheritance chain for BaseModel
result = kb.find_class_hierarchy("BaseModel", repo_id)

for node in result.nodes:
    bases = ", ".join(node.get('base_classes', []))
    print(f"{node['name']} extends {bases}")
```

### Example 4: Incremental Update Workflow

```python
from cf.knowledge.incremental.file_watcher import FileChangeDetector
from cf.knowledge.incremental.differential import IncrementalKBUpdater

# Initial build
pipeline.build_knowledge_base()

# Later: detect and apply changes
detector = FileChangeDetector(repo_path)
changes = detector.detect_changes()

if changes.has_changes():
    updater = IncrementalKBUpdater(kb, parser)
    stats = updater.apply_changes(changes, repo_path, repo_id)
    print(f"Updated in {stats['elapsed_seconds']:.1f}s")
else:
    print("No changes detected")
```

## Architecture Decisions

### Why Neo4j?

- **Graph queries** - Natural fit for code relationships (calls, imports, inheritance)
- **Cypher language** - Expressive query language for traversals
- **Indexing** - Fast lookups by function name, file path, etc.
- **ACID transactions** - Data consistency guarantees
- **Scalability** - Handles millions of nodes and relationships

### Why AST Parsing?

- **Accuracy** - No LLM hallucinations, deterministic results
- **Fast** - Native Python `ast` module is very fast
- **Rich data** - Extract parameters, return types, complexity metrics
- **Reliable** - Works offline, no API costs

### Why Incremental Updates?

- **Performance** - 5s vs 90 min for large repos
- **Cost efficiency** - Don't re-analyze unchanged code
- **Real-time** - Quick updates enable near real-time analysis

## Troubleshooting

### Import Errors

```python
# If you see: ModuleNotFoundError: No module named 'neo4j'
pip install neo4j>=5.0.0
```

### Connection Errors

```python
# If you see: Failed to connect to Neo4j
# 1. Check Neo4j is running
docker ps | grep neo4j

# 2. Check connection details
# Default: bolt://localhost:7687

# 3. Check password
export NEO4J_PASSWORD="your-password"
```

### Memory Issues

```python
# If KB build runs out of memory, reduce workers:
config['knowledge_base']['build']['parallel_workers'] = 2
```

## Contributing

To add support for a new language:

1. Create AST parser (e.g., `javascript_parser.py`)
2. Extract same node types (functions, classes, etc.)
3. Return `StructuralData` object
4. Add tests in `tests/test_<lang>_parser.py`

Example skeleton:

```python
# cf/knowledge/structural/javascript_parser.py

class JavaScriptASTParser:
    def __init__(self, repo_path: str, repo_id: str):
        self.repo_path = repo_path
        self.repo_id = repo_id

    def parse_file(self, file_path: str) -> Optional[StructuralData]:
        # 1. Read file
        # 2. Parse AST (using acorn, esprima, etc.)
        # 3. Extract functions, classes, imports
        # 4. Return StructuralData
        pass
```

## License

Apache License 2.0
