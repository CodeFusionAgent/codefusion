# API Reference

This document provides a complete reference for CodeFusion's Python API, allowing you to integrate CodeFusion directly into your Python applications.

## Installation

```bash
pip install codefusion
```

## Basic Usage

```python
from cf.config import CfConfig
from cf.aci import LocalCodeRepo, EnvironmentManager

# Create configuration
config = CfConfig.from_file("config.yaml")
# Or create from dictionary
config = CfConfig.from_dict({
    "llm_model": "gpt-4",
    "kb_type": "vector",
    "exploration_strategy": "react"
})

# Initialize repository
repo = LocalCodeRepo("/path/to/repository")

# Create environment manager
env = EnvironmentManager(repo, config)

# Get repository overview
overview = env.get_repository_overview()
print(f"Primary language: {overview['primary_language']}")

# Use CLI for full functionality
# cf index /path/to/repository
# cf query "How does authentication work?"
```

## Core Classes

### CfConfig

Configuration management class from `cf.config`.

```python
class CfConfig:
    @classmethod
    def from_file(cls, config_path: str) -> 'CfConfig'
    @classmethod
    def from_dict(cls, config_dict: Dict) -> 'CfConfig'
    def validate(self) -> None
    def to_dict(self) -> Dict
```

#### Methods

##### `from_file(config_path: str) -> CfConfig`

Load configuration from a YAML or JSON file.

**Parameters:**
- `config_path` (str): Path to configuration file

**Returns:**
- `CfConfig`: Configuration instance

**Example:**
```python
config = CfConfig.from_file("config/default/config.yaml")
```

##### `from_dict(config_dict: Dict) -> CfConfig`

Create configuration from a dictionary.

**Parameters:**
- `config_dict` (Dict): Configuration dictionary

**Returns:**
- `CfConfig`: Configuration instance

**Example:**
```python
config = CfConfig.from_dict({
    "llm_model": "gpt-4",
    "kb_type": "vector",
    "exploration_strategy": "react"
})
```

### LocalCodeRepo

Repository abstraction class from `cf.aci.repo`.

```python
class LocalCodeRepo:
    def __init__(self, repo_path: str)
    def get_file_content(self, file_path: str) -> str
    def list_files(self, pattern: str = None) -> List[str]
    def get_repository_structure(self) -> Dict
```

### EnvironmentManager

Environment management class from `cf.aci.environment_manager`.

```python
class EnvironmentManager:
    def __init__(self, repo: LocalCodeRepo, config: CfConfig)
    def get_repository_overview(self) -> Dict
    def suggest_exploration_strategy(self) -> List[str]
```

### Knowledge Base Classes

#### CodeKnowledgeBase

Core knowledge base from `cf.kb.knowledge_base`.

```python
class CodeKnowledgeBase:
    def __init__(self, kb_type: str, config: CfConfig)
    def store_entities(self, entities: List[Entity]) -> None
    def query_entities(self, query: str) -> List[Entity]
    def get_relationships(self, entity_id: str) -> List[Relationship]
```

#### VectorKB

Vector database implementation from `cf.kb.vector_kb`.

```python
class VectorKB:
    def __init__(self, kb_path: str, embedding_model: str)
    def add_documents(self, documents: List[str]) -> None
    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]
```

## Configuration

### Config

Configuration class for CodeFusion settings.

```python
class Config:
    def __init__(self, **kwargs)
    def load_from_file(self, file_path: str) -> None
    def save_to_file(self, file_path: str) -> None
    def validate(self) -> List[ValidationError]
```

#### Constructor Parameters

```python
Config(
    # Basic settings
    repo_path: str = None,
    output_dir: str = "./output",
    
    # LLM settings
    llm_model: str = "gpt-3.5-turbo",
    llm_api_key: str = None,
    llm_base_url: str = None,
    llm_temperature: float = 0.0,
    llm_max_tokens: int = 4096,
    
    # Knowledge base settings
    kb_type: str = "vector",
    kb_path: str = "./kb",
    
    # Vector DB settings
    embedding_model: str = "all-MiniLM-L6-v2",
    similarity_threshold: float = 0.7,
    
    # Neo4j settings
    neo4j_uri: str = None,
    neo4j_user: str = None,
    neo4j_password: str = None,
    neo4j_database: str = "neo4j",
    
    # Exploration settings
    exploration_strategy: str = "react",
    max_exploration_depth: int = 5,
    
    # File filtering
    max_file_size: int = 1048576,
    excluded_dirs: List[str] = None,
    excluded_extensions: List[str] = None,
    
    # Performance settings
    batch_size: int = 100,
    max_workers: int = 4,
    cache_enabled: bool = True,
    
    # Logging settings
    log_level: str = "INFO",
    verbose: bool = False,
    debug: bool = False
)
```

#### Methods

##### `load_from_file(file_path: str) -> None`

Load configuration from a YAML file.

**Parameters:**
- `file_path` (str): Path to YAML configuration file

**Raises:**
- `FileNotFoundError`: If configuration file doesn't exist
- `yaml.YAMLError`: If file contains invalid YAML

**Example:**
```python
config = Config()
config.load_from_file("my-config.yaml")
```

##### `save_to_file(file_path: str) -> None`

Save configuration to a YAML file.

**Parameters:**
- `file_path` (str): Path where to save configuration

**Example:**
```python
config = Config(llm_model="gpt-4", kb_type="neo4j")
config.save_to_file("saved-config.yaml")
```

##### `validate() -> List[ValidationError]`

Validate configuration settings.

**Returns:**
- `List[ValidationError]`: List of validation errors, empty if valid

**Example:**
```python
config = Config(kb_type="neo4j")  # Missing neo4j_uri
errors = config.validate()
for error in errors:
    print(f"Error: {error.message}")
```

## Result Objects

### IndexResult

Result object from repository indexing.

```python
class IndexResult:
    success: bool
    file_count: int
    entity_count: int
    relationship_count: int
    duration_seconds: float
    errors: List[str]
    warnings: List[str]
```

**Example:**
```python
result = cf.index("/path/to/repo")
if result.success:
    print(f"Successfully indexed {result.file_count} files")
else:
    print(f"Indexing failed: {result.errors}")
```

### QueryResult

Result object from querying the knowledge base.

```python
class QueryResult:
    question: str
    answer: str
    confidence: float
    sources: List[Source]
    exploration_steps: List[ExplorationStep]
    duration_seconds: float
    token_usage: TokenUsage
```

**Example:**
```python
result = cf.query("How does caching work?")
print(f"Q: {result.question}")
print(f"A: {result.answer}")
print(f"Confidence: {result.confidence:.2f}")

for source in result.sources:
    print(f"Source: {source.file_path}:{source.line_number}")
```

### ExplorationResult

Result object from repository exploration.

```python
class ExplorationResult:
    repo_path: str
    summary: str
    insights: List[str]
    architecture_overview: str
    technology_stack: List[str]
    complexity_metrics: ComplexityMetrics
    recommendations: List[str]
    duration_seconds: float
```

### StatsResult

Result object containing knowledge base statistics.

```python
class StatsResult:
    kb_type: str
    file_count: int
    entity_count: int
    relationship_count: int
    kb_size_mb: float
    last_updated: datetime
    index_status: str
```

## Knowledge Base API

### KnowledgeBase

Abstract base class for knowledge base implementations.

```python
from cf.kb import KnowledgeBase

class KnowledgeBase(ABC):
    @abstractmethod
    def store(self, entities: List[Entity]) -> None: ...
    
    @abstractmethod
    def query(self, query: str) -> List[Result]: ...
    
    @abstractmethod
    def get_relationships(self, entity_id: str) -> List[Relationship]: ...
    
    @abstractmethod
    def stats(self) -> Dict[str, Any]: ...
```

### Creating Knowledge Bases

```python
from cf.kb import create_knowledge_base

# Vector knowledge base
vector_kb = create_knowledge_base(
    kb_type="vector",
    kb_path="./vector_kb",
    embedding_model="all-MiniLM-L6-v2"
)

# Neo4j knowledge base
neo4j_kb = create_knowledge_base(
    kb_type="neo4j",
    kb_path="./neo4j_kb",
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

# Text knowledge base
text_kb = create_knowledge_base(
    kb_type="text",
    kb_path="./text_kb"
)
```

### Entity and Relationship Classes

```python
class Entity:
    id: str
    type: str
    name: str
    content: str
    file_path: str
    line_number: int
    metadata: Dict[str, Any]

class Relationship:
    id: str
    source_id: str
    target_id: str
    type: str
    properties: Dict[str, Any]

class Source:
    file_path: str
    line_number: int
    column_number: int
    content: str
```

## LLM Integration API

### LLMProvider

Abstract base class for language model providers.

```python
from cf.llm import LLMProvider

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str: ...
    
    @abstractmethod
    def chat(self, messages: List[Message], **kwargs) -> str: ...
    
    @abstractmethod
    def embed(self, text: str) -> List[float]: ...
```

### Creating LLM Providers

```python
from cf.llm import create_llm_provider

# OpenAI provider
openai_llm = create_llm_provider(
    provider_type="openai",
    model="gpt-4",
    api_key="your-api-key"
)

# Anthropic provider
anthropic_llm = create_llm_provider(
    provider_type="anthropic",
    model="claude-3-sonnet-20240229",
    api_key="your-api-key"
)

# Local provider
local_llm = create_llm_provider(
    provider_type="local",
    base_url="http://localhost:8000/v1",
    model="local-model"
)
```

## Exploration Strategies API

### ExplorationStrategy

Abstract base class for exploration strategies.

```python
from cf.aci import ExplorationStrategy

class ExplorationStrategy(ABC):
    @abstractmethod
    def explore(self, query: str, context: Context) -> ExplorationResult: ...
```

### Available Strategies

```python
from cf.aci import ReActStrategy, PlanActStrategy, SenseActStrategy

# ReAct strategy
react = ReActStrategy(
    reasoning_steps=3,
    max_iterations=10,
    backtrack_on_failure=True
)

# Plan-Act strategy
plan_act = PlanActStrategy(
    planning_depth=3,
    execution_parallel=False,
    plan_validation=True
)

# Sense-Act strategy
sense_act = SenseActStrategy(
    observation_cycles=5,
    adaptation_threshold=0.7,
    exploration_breadth=5
)
```

## Error Handling

### Exception Hierarchy

```python
class CodeFusionError(Exception):
    """Base exception for CodeFusion"""
    pass

class ConfigurationError(CodeFusionError):
    """Configuration-related errors"""
    pass

class KnowledgeBaseError(CodeFusionError):
    """Knowledge base operation errors"""
    pass

class LLMError(CodeFusionError):
    """Language model request errors"""
    pass

class ValidationError(CodeFusionError):
    """Input validation errors"""
    pass

class ResourceError(CodeFusionError):
    """Resource access errors (files, network, etc.)"""
    pass
```

### Exception Handling Example

```python
from cf import CodeFusion
from cf.exceptions import ConfigurationError, LLMError, KnowledgeBaseError

try:
    cf = CodeFusion()
    result = cf.query("How does authentication work?")
    print(result.answer)
    
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except LLMError as e:
    print(f"LLM error: {e}")
except KnowledgeBaseError as e:
    print(f"Knowledge base error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Async API

For high-performance applications, CodeFusion provides async variants:

```python
from cf import AsyncCodeFusion

async def main():
    cf = AsyncCodeFusion()
    
    # Async indexing
    result = await cf.index_async("/path/to/repo")
    
    # Async querying
    result = await cf.query_async("How does caching work?")
    
    # Parallel queries
    questions = [
        "How does authentication work?",
        "What are the main API endpoints?",
        "How is the database configured?"
    ]
    
    results = await asyncio.gather(*[
        cf.query_async(q) for q in questions
    ])
    
    for result in results:
        print(f"Q: {result.question}")
        print(f"A: {result.answer}\n")

# Run async code
import asyncio
asyncio.run(main())
```

## Integration Examples

### Flask Integration

```python
from flask import Flask, request, jsonify
from cf import CodeFusion

app = Flask(__name__)
cf = CodeFusion()

@app.route('/index', methods=['POST'])
def index_repo():
    repo_path = request.json['repo_path']
    result = cf.index(repo_path)
    return jsonify({
        'success': result.success,
        'file_count': result.file_count,
        'entity_count': result.entity_count
    })

@app.route('/query', methods=['POST'])
def query_code():
    question = request.json['question']
    result = cf.query(question)
    return jsonify({
        'answer': result.answer,
        'confidence': result.confidence,
        'sources': [{'file': s.file_path, 'line': s.line_number} for s in result.sources]
    })
```

### Django Integration

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from cf import CodeFusion
import json

cf = CodeFusion()

@csrf_exempt
def query_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        result = cf.query(data['question'])
        return JsonResponse({
            'answer': result.answer,
            'confidence': result.confidence
        })
```

### Jupyter Notebook Integration

```python
# In a Jupyter notebook
from cf import CodeFusion
import pandas as pd

cf = CodeFusion()

# Index repository
cf.index("/path/to/repo")

# Query and display results
questions = [
    "What is the main architecture?",
    "How many API endpoints exist?",
    "What testing frameworks are used?"
]

results = []
for q in questions:
    result = cf.query(q)
    results.append({
        'question': q,
        'answer': result.answer,
        'confidence': result.confidence
    })

df = pd.DataFrame(results)
display(df)
```

## Performance Optimization

### Batch Processing

```python
from cf import CodeFusion
from concurrent.futures import ThreadPoolExecutor

cf = CodeFusion()

def process_repository(repo_path):
    return cf.index(repo_path)

# Process multiple repositories in parallel
repo_paths = ["/path/to/repo1", "/path/to/repo2", "/path/to/repo3"]

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_repository, repo_paths))

for result in results:
    print(f"Processed {result.file_count} files")
```

### Memory Management

```python
from cf import CodeFusion
from cf.config import Config

# Configure for large repositories
config = Config(
    max_file_size=524288,  # 512KB limit
    batch_size=50,         # Smaller batches
    cache_enabled=False,   # Disable caching
    max_workers=2          # Reduce workers
)

cf = CodeFusion(config)
```

## Testing Support

### Mock Providers

```python
from cf.testing import MockLLMProvider, MockKnowledgeBase

# Mock LLM for testing
mock_llm = MockLLMProvider()
mock_llm.add_response("How does auth work?", "Authentication uses JWT tokens")

# Mock knowledge base for testing
mock_kb = MockKnowledgeBase()
mock_kb.add_entity(Entity(id="1", type="function", name="login"))

# Use mocks in tests
config = Config(llm_provider=mock_llm, knowledge_base=mock_kb)
cf = CodeFusion(config)
```

## Next Steps

- Check the [CLI reference](cli.md) for command-line usage
- Review [configuration options](../config/reference.md)
- See [usage examples](../usage/examples.md) for practical applications