# Documentation Agent

::: cf.agents.react_documentation_agent.ReActDocumentationAgent

The Documentation Agent specializes in analyzing and understanding various forms of project documentation using the ReAct pattern.

## Overview

The Documentation Agent excels at:

- Scanning and identifying documentation files
- Analyzing README files, guides, and manuals
- Extracting API documentation patterns
- Understanding project structure from docs
- Cross-referencing documentation consistency

## Usage Examples

### Basic Documentation Analysis

```python
from cf.agents.react_documentation_agent import ReActDocumentationAgent
from cf.aci.repo import LocalCodeRepo
from cf.config import CfConfig

# Initialize agent
repo = LocalCodeRepo("/path/to/repository")
config = CfConfig()
doc_agent = ReActDocumentationAgent(repo, config)

# Analyze documentation
results = doc_agent.scan_documentation("comprehensive documentation review")

print(f"Documentation files found: {len(results.get('documentation_files', []))}")
print(f"Analysis summary: {results.get('summary')}")
```

### Focused Documentation Types

```python
# API documentation analysis
api_docs = doc_agent.scan_documentation("API documentation and endpoints")

# Setup and installation guides
setup_docs = doc_agent.scan_documentation("installation and setup documentation")

# Architecture documentation
arch_docs = doc_agent.scan_documentation("system architecture and design documentation")
```

## Key Features

### Document Type Detection

The agent automatically identifies various documentation types:

- **README files**: Project overviews and quick starts
- **API Documentation**: Endpoint descriptions and usage
- **Guides**: Step-by-step instructions
- **Reference**: Technical specifications
- **Examples**: Code samples and tutorials

### Content Analysis

```python
# Access detailed analysis results
results = doc_agent.scan_documentation("complete documentation audit")

analyzed_docs = doc_agent.get_analyzed_documentation()
for file_path, analysis in analyzed_docs.items():
    print(f"File: {file_path}")
    print(f"Type: {analysis.get('doc_type')}")
    print(f"Quality Score: {analysis.get('quality_score')}")
    print(f"Key Sections: {analysis.get('sections')}")
    print("---")
```

### Documentation Quality Assessment

```python
# Get quality insights
quality_assessment = doc_agent.get_documentation_quality()

print(f"Overall Quality: {quality_assessment.get('overall_score')}")
print(f"Completeness: {quality_assessment.get('completeness')}")
print(f"Structure: {quality_assessment.get('structure_score')}")
print(f"Recommendations: {quality_assessment.get('recommendations')}")
```

## Integration Examples

### With Supervisor Agent

```python
from cf.agents.react_supervisor_agent import ReActSupervisorAgent

supervisor = ReActSupervisorAgent(repo, config)

# Documentation-focused analysis
results = supervisor.explore_repository(
    goal="evaluate documentation quality and coverage",
    focus="docs"
)

# Access documentation agent results
doc_results = supervisor.get_agent_results()['documentation']
```

### Custom Documentation Workflows

```python
def documentation_audit_workflow(repo_path: str) -> Dict[str, Any]:
    """Comprehensive documentation audit workflow."""
    repo = LocalCodeRepo(repo_path)
    config = CfConfig()
    doc_agent = ReActDocumentationAgent(repo, config)
    
    # Phase 1: Discovery
    discovery = doc_agent.scan_documentation("discover all documentation")
    
    # Phase 2: Quality Analysis
    quality = doc_agent.scan_documentation("assess documentation quality")
    
    # Phase 3: Completeness Check
    completeness = doc_agent.scan_documentation("check documentation completeness")
    
    return {
        'discovery': discovery,
        'quality': quality,
        'completeness': completeness,
        'recommendations': generate_doc_recommendations(doc_agent)
    }
```

## Advanced Features

### Custom Document Processing

```python
class CustomDocumentationAgent(ReActDocumentationAgent):
    def __init__(self, repo, config):
        super().__init__(repo, config)
        self.custom_doc_types = {
            'confluence': self._process_confluence_docs,
            'wiki': self._process_wiki_docs,
            'openapi': self._process_openapi_specs
        }
    
    def _process_confluence_docs(self, content: str) -> Dict[str, Any]:
        """Process Confluence documentation."""
        # Custom processing logic
        pass
    
    def _process_wiki_docs(self, content: str) -> Dict[str, Any]:
        """Process wiki documentation."""
        # Custom processing logic  
        pass
    
    def _process_openapi_specs(self, content: str) -> Dict[str, Any]:
        """Process OpenAPI specifications."""
        # Custom processing logic
        pass
```

### Documentation Metrics

```python
# Get comprehensive metrics
metrics = doc_agent.get_documentation_metrics()

print("Documentation Metrics:")
print(f"  Total Files: {metrics.get('total_files')}")
print(f"  Coverage Score: {metrics.get('coverage_score')}")
print(f"  Average Quality: {metrics.get('average_quality')}")
print(f"  Missing Areas: {metrics.get('missing_areas')}")
print(f"  Improvement Suggestions: {metrics.get('suggestions')}")
```

## Configuration Options

```python
from cf.core.react_config import ReActConfig

# Documentation-specific configuration
doc_config = ReActConfig(
    max_iterations=15,  # Sufficient for thorough doc analysis
    iteration_timeout=30.0,
    cache_enabled=True,
    cache_max_size=500  # Docs are typically smaller
)

doc_agent = ReActDocumentationAgent(
    repo, 
    config, 
    react_config=doc_config
)
```