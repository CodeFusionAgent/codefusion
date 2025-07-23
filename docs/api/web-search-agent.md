# WebSearchAgent API

The `WebSearchAgent` provides intelligent web search capabilities with LLM-powered query generation and seamless integration of external knowledge into technical responses.

## Overview

The WebSearchAgent enables:
- **LLM-Powered Query Generation**: Intelligent search query crafting based on questions and codebase context
- **External Knowledge Integration**: Web search results seamlessly woven into main narrative responses
- **Relevance Filtering**: AI-driven filtering of search results for technical accuracy
- **Best Practices Enhancement**: Industry documentation and tutorials automatically included
- **No Configuration Required**: Web search automatically enabled when beneficial

## Class Definition

```python
from cf.agents.web_search_agent import WebSearchAgent
```

## Constructor

```python
WebSearchAgent(
    code_repo: CodeRepo,
    config: CfConfig
)
```

**Parameters:**
- `code_repo` (CodeRepo): Repository instance for context-aware search
- `config` (CfConfig): Configuration with web search and LLM settings

**Example:**
```python
from cf.agents.web_search_agent import WebSearchAgent
from cf.aci.repo import LocalCodeRepo
from cf.config import CfConfig

# Initialize repository and config
repo = LocalCodeRepo("/path/to/repo")
config = CfConfig.from_file("config.yaml")

# Create web search agent
web_agent = WebSearchAgent(repo, config)
```

## Core Methods

### search_for_question()

Perform intelligent web search based on a question, with LLM-powered query generation and result consolidation.

```python
search_for_question(question: str) -> Dict[str, Any]
```

**Parameters:**
- `question` (str): The question to search for online

**Returns:**
Dict containing:
- `success` (bool): Whether search completed successfully
- `results` (List[Dict]): Raw search results with metadata
- `insights` (List[Dict]): AI-processed insights with relevance scores
- `consolidated_knowledge` (str): Summary of external knowledge found
- `search_queries_used` (List[str]): Generated search queries executed

**Example:**
```python
# Technical question about framework
result = web_agent.search_for_question(
    "FastAPI production deployment best practices"
)

if result['success']:
    print(f"Found {len(result['results'])} search results")
    
    # Access consolidated insights
    for insight in result['insights']:
        print(f"Source: {insight['source']}")
        print(f"Content: {insight['content']}")
        print(f"Relevance: {insight['relevance_score']:.2f}")
        print()
    
    # Get summary of external knowledge
    print("Consolidated Knowledge:")
    print(result['consolidated_knowledge'])
```

### craft_search_queries()

Generate intelligent search queries based on question and codebase context.

```python
craft_search_queries(
    question: str,
    max_queries: int = 3
) -> List[str]
```

**Parameters:**
- `question` (str): Original question to generate queries for
- `max_queries` (int): Maximum number of queries to generate (default: 3)

**Returns:**
List of intelligently crafted search query strings

**Example:**
```python
# Generate search queries for a technical question
queries = web_agent.craft_search_queries(
    "How does FastAPI handle async database connections?"
)

print("Generated search queries:")
for i, query in enumerate(queries, 1):
    print(f"{i}. {query}")

# Output example:
# 1. FastAPI async database connection best practices
# 2. SQLAlchemy async FastAPI production setup
# 3. FastAPI async database session management tutorial
```

### process_search_results()

Process raw search results with AI to extract relevant insights and filter for technical accuracy.

```python
process_search_results(
    results: List[Dict],
    original_question: str
) -> List[Dict[str, Any]]
```

**Parameters:**
- `results` (List[Dict]): Raw search results from web search
- `original_question` (str): Original question for relevance scoring

**Returns:**
List of processed insights with relevance scoring and content extraction

**Example:**
```python
# Process raw search results
raw_results = [
    {
        'title': 'FastAPI Production Deployment Guide',
        'url': 'https://fastapi.tiangolo.com/deployment/',
        'snippet': 'Learn how to deploy FastAPI applications in production...'
    },
    # ... more results
]

insights = web_agent.process_search_results(
    raw_results,
    "FastAPI production deployment best practices"
)

for insight in insights:
    print(f"Relevance: {insight['relevance_score']:.2f}")
    print(f"Key Points: {insight['key_points']}")
    print(f"Technical Details: {insight['technical_details']}")
```

## Integration Methods

### integrate_with_narrative()

Integrate web search insights into main narrative responses (used by InteractiveSessionManager).

```python
integrate_with_narrative(
    narrative_result: Dict[str, Any],
    web_insights: List[Dict[str, Any]]
) -> Dict[str, Any]
```

**Parameters:**
- `narrative_result` (Dict): Main narrative response from other agents
- `web_insights` (List[Dict]): Processed web search insights

**Returns:**
Enhanced narrative with web insights seamlessly integrated

**Example:**
```python
# This is typically called automatically by InteractiveSessionManager
# But can be used directly for custom integrations

narrative = {
    'format': 'journey',
    'title': 'Life of Authentication',
    'sections': [...]
}

web_insights = web_agent.search_for_question(
    "JWT authentication best practices"
)['insights']

enhanced_narrative = web_agent.integrate_with_narrative(
    narrative, 
    web_insights
)

# Enhanced narrative now includes external best practices
# woven naturally into the technical explanation
```

## Configuration

### Web Search Settings

Configure web search behavior in your config file:

```yaml
# config.yaml
web_search:
  enabled: true
  search_engine: "duckduckgo"  # Currently supported: duckduckgo
  max_results_per_query: 5
  max_queries_per_question: 3
  relevance_threshold: 0.6
  search_timeout: 10  # seconds
  rate_limit_delay: 1  # seconds between queries
```

### Environment Variables

```bash
# Enable/disable web search
export CF_WEB_SEARCH_ENABLED=true

# Search configuration
export CF_WEB_SEARCH_MAX_RESULTS=5
export CF_WEB_SEARCH_TIMEOUT=10
export CF_WEB_SEARCH_RATE_LIMIT=1
```

## Advanced Usage

### Custom Query Generation

```python
from cf.llm.real_llm import get_real_llm

class CustomWebSearchAgent(WebSearchAgent):
    def craft_search_queries(self, question: str, max_queries: int = 3) -> List[str]:
        """Custom query generation with domain-specific logic."""
        
        # Detect technology stack from repository
        tech_stack = self._detect_technology_stack()
        
        # Generate tech-specific queries
        llm = get_real_llm(self.config)
        
        prompt = f"""
        Generate {max_queries} specific search queries for this question: "{question}"
        
        Context: Repository uses {', '.join(tech_stack)}
        
        Focus on:
        1. Official documentation and guides
        2. Production best practices
        3. Common pitfalls and solutions
        
        Return only the search queries, one per line.
        """
        
        response = llm.generate(prompt)
        queries = [q.strip() for q in response.split('\n') if q.strip()]
        
        return queries[:max_queries]
    
    def _detect_technology_stack(self) -> List[str]:
        """Detect technologies used in the repository."""
        files = self.code_repo.list_files()
        
        tech_indicators = {
            'FastAPI': ['main.py', 'requirements.txt contains fastapi'],
            'React': ['package.json contains react', 'src/App.js'],
            'Django': ['manage.py', 'settings.py'],
            'Node.js': ['package.json', 'server.js'],
            'Python': ['.py files'],
            'JavaScript': ['.js files', '.jsx files']
        }
        
        detected = []
        for tech, indicators in tech_indicators.items():
            if any(self._check_indicator(ind, files) for ind in indicators):
                detected.append(tech)
        
        return detected
```

### Result Filtering and Ranking

```python
class EnhancedWebSearchAgent(WebSearchAgent):
    def process_search_results(
        self, 
        results: List[Dict], 
        original_question: str
    ) -> List[Dict[str, Any]]:
        """Enhanced result processing with custom relevance scoring."""
        
        processed = []
        
        for result in results:
            # Extract key information
            insight = {
                'url': result['url'],
                'title': result['title'],
                'content': result['snippet'],
                'source_type': self._classify_source(result['url']),
                'relevance_score': self._calculate_relevance(result, original_question),
                'technical_quality': self._assess_technical_quality(result),
                'key_points': self._extract_key_points(result['snippet'])
            }
            
            # Filter by quality thresholds
            if (insight['relevance_score'] >= 0.6 and 
                insight['technical_quality'] >= 0.5):
                processed.append(insight)
        
        # Sort by combined relevance and quality score
        processed.sort(
            key=lambda x: (x['relevance_score'] + x['technical_quality']) / 2,
            reverse=True
        )
        
        return processed
    
    def _classify_source(self, url: str) -> str:
        """Classify the source type for prioritization."""
        if 'github.com' in url:
            return 'github'
        elif any(domain in url for domain in ['stackoverflow.com', 'stackexchange.com']):
            return 'stackoverflow'
        elif any(domain in url for domain in ['.readthedocs.io', '/docs/']):
            return 'official_docs'
        elif any(domain in url for domain in ['medium.com', 'dev.to']):
            return 'blog'
        else:
            return 'other'
    
    def _calculate_relevance(self, result: Dict, question: str) -> float:
        """Calculate relevance score based on multiple factors."""
        # Implement custom relevance scoring logic
        # Consider title match, content match, source authority, etc.
        pass
```

## Error Handling

### Common Patterns

```python
from cf.agents.web_search_agent import WebSearchAgent

try:
    web_agent = WebSearchAgent(repo, config)
    result = web_agent.search_for_question("Complex technical question")
    
    if not result['success']:
        print("Web search failed, continuing without external knowledge")
        # System gracefully degrades to code+docs analysis only
    
except ImportError:
    print("Web search dependencies not available")
    print("Install with: pip install duckduckgo-search")
    # Continue without web search
    
except TimeoutError:
    print("Web search timed out")
    # Use cached results or continue without web search
    
except Exception as e:
    print(f"Web search error: {e}")
    # Log error and continue with other agents
```

### Rate Limiting and Resilience

```python
import time
from typing import Optional

class ResilientWebSearchAgent(WebSearchAgent):
    def __init__(self, code_repo, config):
        super().__init__(code_repo, config)
        self.last_search_time = 0
        self.rate_limit_delay = config.get('web_search', {}).get('rate_limit_delay', 1)
    
    def search_for_question(self, question: str) -> Dict[str, Any]:
        """Search with rate limiting and retry logic."""
        
        # Rate limiting
        time_since_last = time.time() - self.last_search_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = super().search_for_question(question)
                self.last_search_time = time.time()
                return result
                
            except Exception as e:
                if attempt == max_retries - 1:
                    return {
                        'success': False,
                        'error': str(e),
                        'results': [],
                        'insights': []
                    }
                
                # Exponential backoff
                time.sleep(2 ** attempt)
```

## Performance Optimization

### Caching Search Results

```python
import hashlib
import json
from pathlib import Path

class CachedWebSearchAgent(WebSearchAgent):
    def __init__(self, code_repo, config):
        super().__init__(code_repo, config)
        self.cache_dir = Path(config.get('web_search', {}).get('cache_dir', './web_search_cache'))
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_ttl = config.get('web_search', {}).get('cache_ttl', 3600)  # 1 hour
    
    def search_for_question(self, question: str) -> Dict[str, Any]:
        """Search with result caching."""
        
        # Generate cache key
        cache_key = hashlib.md5(question.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # Check cache
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < self.cache_ttl:
                with open(cache_file, 'r') as f:
                    cached_result = json.load(f)
                    cached_result['from_cache'] = True
                    return cached_result
        
        # Perform search
        result = super().search_for_question(question)
        
        # Cache result
        if result['success']:
            result['cached_at'] = time.time()
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        
        result['from_cache'] = False
        return result
```

### Parallel Query Execution

```python
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

class ParallelWebSearchAgent(WebSearchAgent):
    async def search_for_question_async(self, question: str) -> Dict[str, Any]:
        """Async version with parallel query execution."""
        
        # Generate search queries
        queries = self.craft_search_queries(question)
        
        # Execute searches in parallel
        async with aiohttp.ClientSession() as session:
            search_tasks = [
                self._execute_search_async(session, query)
                for query in queries
            ]
            
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Process and consolidate results
        all_results = []
        for results in search_results:
            if not isinstance(results, Exception) and results:
                all_results.extend(results)
        
        # Process with AI for insights
        insights = self.process_search_results(all_results, question)
        
        return {
            'success': len(all_results) > 0,
            'results': all_results,
            'insights': insights,
            'consolidated_knowledge': self._consolidate_insights(insights),
            'search_queries_used': queries
        }
```

## Integration Examples

### With InteractiveSessionManager

The WebSearchAgent is automatically integrated into InteractiveSessionManager:

```python
from cf.core.interactive_session import InteractiveSessionManager

# Web search automatically enabled
session = InteractiveSessionManager(repo_path, config)

# Questions that benefit from external knowledge automatically trigger web search
result = session.ask_question("FastAPI production deployment best practices")

# Web search insights are seamlessly woven into the narrative
print(result['narrative'])  # Contains both code analysis and web search insights
print(f"Web search used: {result['web_search_included']}")
```

### Standalone Usage

```python
# Direct web search agent usage
web_agent = WebSearchAgent(repo, config)

# Search for external knowledge
search_result = web_agent.search_for_question(
    "React performance optimization techniques"
)

if search_result['success']:
    print(f"Found {len(search_result['results'])} relevant sources")
    
    # Access structured insights
    for insight in search_result['insights']:
        print(f"\n📚 {insight['source']}")
        print(f"Relevance: {insight['relevance_score']:.2f}")
        print(f"Key Points: {', '.join(insight['key_points'])}")
        
    # Get consolidated summary
    print(f"\n📋 Summary:")
    print(search_result['consolidated_knowledge'])
```

### Custom Integration

```python
from cf.agents.react_supervisor_agent import ReActSupervisorAgent
from cf.agents.web_search_agent import WebSearchAgent

# Manual multi-agent coordination with web search
supervisor = ReActSupervisorAgent(repo, config)
web_agent = WebSearchAgent(repo, config)

# Get code and docs analysis
code_docs_result = supervisor.explore_repository(
    goal="How does caching work?",
    focus="all"
)

# Get external knowledge
web_search_result = web_agent.search_for_question(
    "Redis caching best practices Python"
)

# Manually integrate results
if web_search_result['success']:
    enhanced_result = web_agent.integrate_with_narrative(
        code_docs_result,
        web_search_result['insights']
    )
    print("Enhanced response with external knowledge:")
    print(enhanced_result['narrative'])
```

## Best Practices

### Query Optimization

```python
# Good: Specific, technical queries
queries = [
    "FastAPI async database connection pooling",
    "SQLAlchemy async session management FastAPI",
    "FastAPI production database configuration"
]

# Avoid: Vague, generic queries
bad_queries = [
    "database",
    "python web framework",
    "how to code"
]
```

### Result Quality Assessment

```python
# Prioritize high-quality sources
source_priority = {
    'official_docs': 1.0,      # Official documentation
    'github': 0.9,             # GitHub repositories and issues
    'stackoverflow': 0.8,      # Stack Overflow answers
    'blog': 0.6,               # Technical blogs
    'other': 0.4               # Other sources
}

# Filter by technical depth
min_relevance_score = 0.6
min_technical_quality = 0.5
```

### Rate Limiting and Ethics

```python
# Respect search engine rate limits
rate_limit_delay = 1  # Second between searches
max_queries_per_question = 3
search_timeout = 10  # Seconds

# Be a good citizen
user_agent = "CodeFusion/1.0 (Educational Code Analysis Tool)"
```

## Related APIs

- **[Interactive Session Manager](interactive-session.md)** - Automatic web search integration
- **[Multi-Agent Coordinator](multi-agent-coordinator.md)** - Agent selection and coordination
- **[Narrative Utils](narrative-utils.md)** - Response formatting and integration
- **[ReAct Supervisor Agent](supervisor-agent.md)** - Traditional multi-agent coordination