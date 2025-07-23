# InteractiveSessionManager API

The `InteractiveSessionManager` is the core component for creating persistent, memory-enhanced question-answer sessions with multi-agent coordination and adaptive response formats.

## Overview

The InteractiveSessionManager provides:
- **Persistent Memory**: Conversations stored with timestamp-based organization
- **Context Building**: Each question enhances understanding for subsequent queries  
- **Multi-Agent Coordination**: Intelligent selection of 1-3 specialized agents
- **Adaptive Responses**: Journey/Comparison/Explanation formats automatically detected
- **Web Search Integration**: External knowledge seamlessly woven into responses

## Class Definition

```python
from cf.core.interactive_session import InteractiveSessionManager
```

## Constructor

```python
InteractiveSessionManager(
    repo_path: str,
    config: CfConfig,
    session_dir: Optional[str] = None,
    resume_session_id: Optional[str] = None
)
```

**Parameters:**
- `repo_path` (str): Path to the repository to analyze
- `config` (CfConfig): Configuration object with LLM and agent settings
- `session_dir` (Optional[str]): Directory to store session files (default: `<repo>/.codefusion_sessions`)
- `resume_session_id` (Optional[str]): Session ID to resume previous conversation

**Example:**
```python
from cf.config import CfConfig
from cf.core.interactive_session import InteractiveSessionManager

# Create new session
config = CfConfig.from_file("config.yaml")
session = InteractiveSessionManager(
    repo_path="/path/to/repo",
    config=config,
    session_dir="./my_sessions"
)

# Resume existing session
session = InteractiveSessionManager(
    repo_path="/path/to/repo", 
    config=config,
    resume_session_id="session_20240115_143025"
)
```

## Core Methods

### ask_question()

Ask a question with full context awareness and multi-agent coordination.

```python
ask_question(question: str) -> Dict[str, Any]
```

**Parameters:**
- `question` (str): The question to ask about the codebase

**Returns:**
Dict containing:
- `format` (str): Response format ("journey", "comparison", "explanation")
- `narrative` (str): Formatted narrative response
- `agents_used` (int): Number of agents used (1-3)
- `response_time` (float): Time taken in seconds
- `insights` (List[str]): Key insights discovered
- `web_search_included` (bool): Whether web search was used

**Example:**
```python
# Journey format for process flows
result = session.ask_question("How does authentication work?")
print(f"Format: {result['format']}")  # "journey"
print(f"Agents: {result['agents_used']}")  # 3
print(result['narrative'])

# Comparison format for performance questions
result = session.ask_question("async def vs def performance?")
print(f"Format: {result['format']}")  # "comparison"
print(f"Confidence: {result['confidence_score']}")  # 92.5

# Explanation format for concepts  
result = session.ask_question("What is dependency injection?")
print(f"Format: {result['format']}")  # "explanation"
```

### start_interactive_loop()

Start the interactive CLI loop for continuous question-answer sessions.

```python
start_interactive_loop() -> None
```

**Example:**
```python
# Start interactive session (blocks until user exits)
session.start_interactive_loop()

# Interactive conversation:
# You: How does routing work?
# 🤖 [Journey format response...]
# 
# You: What about middleware?  
# 🤖 [Response building on routing knowledge...]
#
# You: exit
# Session saved to: ./sessions/repo_session_20240115_143025.json
```

### save_session()

Save the current session state to disk.

```python
save_session() -> str
```

**Returns:**
- `str`: Path to the saved session file

**Example:**
```python
session_file = session.save_session()
print(f"Session saved to: {session_file}")
# Output: ./my_sessions/repo_session_20240115_143025.json
```

### get_session_summary()

Get a summary of the current session.

```python
get_session_summary() -> Dict[str, Any]
```

**Returns:**
Dict containing:
- `session_id` (str): Unique session identifier
- `total_questions` (int): Number of questions asked
- `technologies` (List[str]): Technologies discovered
- `components` (List[str]): System components identified
- `avg_response_time` (float): Average response time
- `formats_used` (Dict[str, int]): Count of each response format used

**Example:**
```python
summary = session.get_session_summary()
print(f"Questions asked: {summary['total_questions']}")
print(f"Technologies: {summary['technologies']}")
print(f"Average time: {summary['avg_response_time']:.2f}s")
print(f"Formats: {summary['formats_used']}")
```

## Class Methods

### list_sessions()

List available sessions for a repository.

```python
@classmethod
list_sessions(
    cls,
    repo_path: str,
    session_dir: Optional[str] = None
) -> List[Dict[str, Any]]
```

**Parameters:**
- `repo_path` (str): Repository path to list sessions for
- `session_dir` (Optional[str]): Session directory to search

**Returns:**
List of session metadata dictionaries

**Example:**
```python
sessions = InteractiveSessionManager.list_sessions("/path/to/repo")

for session in sessions:
    print(f"ID: {session['session_id']}")
    print(f"Started: {session['started_at']}")
    print(f"Questions: {session['total_questions']}")
    print(f"Technologies: {session['technologies']}")
    print()
```

## Properties

### session_id

```python
@property
session_id -> str
```

Get the unique session identifier.

**Example:**
```python
print(f"Current session: {session.session_id}")
# Output: session_20240115_143025
```

### memory

```python
@property
memory -> ExplorationMemory
```

Access the session's memory system for context tracking.

**Example:**
```python
# Get memory statistics
stats = session.memory.get_session_stats()
print(f"Context length: {stats['context_length']}")
print(f"Key insights: {len(stats['insights'])}")

# Get enhanced context for next question
enhanced = session.memory.enhance_question_with_context(
    "What about error handling?"
)
print(f"Enhanced question: {enhanced}")
```

### supervisor

```python
@property 
supervisor -> ReActSupervisorAgent
```

Access the underlying supervisor agent.

**Example:**
```python
# Get detailed agent results
agent_results = session.supervisor.get_agent_results()
print(f"Code analysis: {agent_results.get('code_architecture')}")
print(f"Docs analysis: {agent_results.get('documentation')}")
```

## Multi-Agent Coordination

The InteractiveSessionManager automatically coordinates multiple specialized agents:

### Agent Selection Logic

```python
# Simple questions - single agent (faster)
result = session.ask_question("Where is main.py?")
# Uses supervisor agent only (~15-20s)

# Complex questions - multi-agent (comprehensive) 
result = session.ask_question("How does the authentication system work?")
# Uses code + docs + web search agents (~25-35s)
```

### Accessing Agent Results

```python
# Ask question and get detailed agent breakdown
result = session.ask_question("How does routing work?")

# Access individual agent insights
if result['agents_used'] == 3:
    agent_results = session.supervisor.get_agent_results()
    
    print("Code Analysis:")
    print(agent_results.get('code_architecture', {}).get('summary'))
    
    print("Documentation Analysis:")  
    print(agent_results.get('documentation', {}).get('summary'))
    
    print("Web Search Insights:")
    web_agent = session._get_web_search_agent()
    # Web results are automatically integrated into main narrative
```

## Adaptive Response Formats

The system automatically detects the optimal response format based on question type:

### Format Detection Examples

```python
# Journey format (Life of X) - process flows
result = session.ask_question("How does user login work?")
assert result['format'] == 'journey'
print(result['narrative'])  # Structured journey through the system

# Comparison format - performance/technical analysis
result = session.ask_question("Redis vs PostgreSQL for caching?") 
assert result['format'] == 'comparison'
print(f"Confidence: {result['confidence_score']}")

# Explanation format - conceptual questions
result = session.ask_question("What is microservices architecture?")
assert result['format'] == 'explanation'
```

### Custom Format Handling

```python
from cf.tools.narrative_utils import display_adaptive_response

# Ask question and display with optimal formatting
result = session.ask_question("How does the API work?")

# Display uses format-specific logic
display_adaptive_response(result, result['format'])
```

## Session Persistence

### Automatic Persistence

```python
# Sessions are automatically saved after each question
session = InteractiveSessionManager("/path/to/repo", config)

result1 = session.ask_question("How does routing work?")
# Session automatically saved with routing context

result2 = session.ask_question("What about middleware?") 
# Question enhanced with routing knowledge from previous context
# Session updated with middleware insights
```

### Manual Session Management

```python
# Save session manually
session_file = session.save_session()

# Load session by ID
resumed_session = InteractiveSessionManager(
    repo_path="/path/to/repo",
    config=config, 
    resume_session_id="session_20240115_143025"
)

# Continue conversation with full context
result = resumed_session.ask_question("Tell me more about error handling")
# Uses all previous conversation context
```

### Session File Format

Session files are stored as JSON with comprehensive metadata:

```json
{
  "session_id": "session_20240115_143025",
  "repo_path": "/path/to/repo",
  "started_at": "2024-01-15T14:30:25",
  "last_updated": "2024-01-15T15:45:12", 
  "total_questions": 5,
  "questions_and_responses": [
    {
      "question": "How does routing work?",
      "response": {...},
      "format": "journey",
      "agents_used": 3,
      "response_time": 28.3,
      "timestamp": "2024-01-15T14:32:15"
    }
  ],
  "discovered_technologies": ["FastAPI", "Starlette", "Pydantic"],
  "discovered_components": ["Router", "Dependencies", "Middleware"],
  "session_insights": ["Uses async/await", "JWT authentication", "Redis caching"]
}
```

## Web Search Integration

### Automatic Web Search

```python
# Web search automatically triggered for questions needing external knowledge
result = session.ask_question("FastAPI production best practices")
# Automatically includes web search insights woven into response

assert result['web_search_included'] == True
print("Web search insights integrated naturally into narrative")
```

### Web Search Configuration

```python
# Configure web search behavior
config = CfConfig({
    'web_search': {
        'enabled': True,
        'max_results_per_query': 5,
        'relevance_threshold': 0.6,
        'search_timeout': 10
    }
})

session = InteractiveSessionManager("/path/to/repo", config)
```

## Error Handling

### Common Patterns

```python
from cf.core.interactive_session import InteractiveSessionManager

try:
    session = InteractiveSessionManager(
        repo_path="/path/to/repo",
        config=config
    )
    
    result = session.ask_question("Complex analysis question")
    
except FileNotFoundError:
    print("Repository path not found")
except TimeoutError:
    print("Question analysis timed out - try simpler question")
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Try: pip install duckduckgo-search")
except Exception as e:
    print(f"Session error: {e}")
    # Fallback to basic analysis
```

### Graceful Degradation

```python
# The system gracefully degrades when components fail
try:
    result = session.ask_question("Question requiring web search")
except Exception as web_error:
    print(f"Web search failed: {web_error}")
    # System continues with code+docs analysis only
    # Result still contains useful insights
```

## Performance Considerations

### Response Time Optimization

```python
# Configure for faster responses
fast_config = CfConfig({
    'multi_agent': {
        'complexity_threshold': 0.8,  # Use single agent more often
        'agent_timeout': 60
    },
    'web_search': {
        'max_results_per_query': 3
    }
})

# Configure for comprehensive analysis
thorough_config = CfConfig({
    'multi_agent': {
        'complexity_threshold': 0.5,  # Use multi-agent more often
        'agent_timeout': 180
    },
    'web_search': {
        'max_results_per_query': 8
    }
})
```

### Memory Management

```python
# Monitor session memory usage
stats = session.memory.get_session_stats()
print(f"Context length: {stats['context_length']}")
print(f"Memory items: {len(stats['insights'])}")

# Clean up old sessions
import os
from pathlib import Path

session_dir = Path("./my_sessions")
old_sessions = [
    f for f in session_dir.glob("*.json") 
    if f.stat().st_mtime < (time.time() - 86400 * 30)  # 30 days old
]

for old_session in old_sessions:
    os.remove(old_session)
    print(f"Cleaned up old session: {old_session}")
```

## Integration Examples

### Web Application Integration

```python
from flask import Flask, request, jsonify
from cf.core.interactive_session import InteractiveSessionManager

app = Flask(__name__)
sessions = {}  # In production, use proper session storage

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.json
    session_id = data.get('session_id')
    question = data.get('question')
    repo_path = data.get('repo_path')
    
    # Get or create session
    if session_id not in sessions:
        sessions[session_id] = InteractiveSessionManager(
            repo_path=repo_path,
            config=config,
            session_dir=f"./sessions/{session_id}"
        )
    
    session = sessions[session_id]
    
    try:
        result = session.ask_question(question)
        return jsonify({
            'success': True,
            'format': result['format'],
            'narrative': result['narrative'], 
            'agents_used': result['agents_used'],
            'response_time': result['response_time']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sessions/<session_id>/summary')
def get_session_summary(session_id):
    if session_id in sessions:
        summary = sessions[session_id].get_session_summary()
        return jsonify(summary)
    return jsonify({'error': 'Session not found'}), 404
```

### Batch Processing

```python
import asyncio
from pathlib import Path

async def process_repository_questions(repo_path, questions):
    """Process multiple questions for a repository in sequence."""
    
    session = InteractiveSessionManager(
        repo_path=repo_path,
        config=config,
        session_dir=f"./batch_sessions/{Path(repo_path).name}"
    )
    
    results = []
    for question in questions:
        try:
            result = session.ask_question(question)
            results.append({
                'question': question,
                'format': result['format'],
                'agents_used': result['agents_used'],
                'response_time': result['response_time'],
                'insights': result['insights']
            })
            
            # Brief pause between questions
            await asyncio.sleep(1)
            
        except Exception as e:
            results.append({
                'question': question,
                'error': str(e)
            })
    
    # Save final session
    session_file = session.save_session()
    print(f"Batch session saved: {session_file}")
    
    return results

# Usage
questions = [
    "How does the application start up?",
    "What is the authentication system?", 
    "How are database connections managed?",
    "What is the error handling strategy?"
]

results = asyncio.run(
    process_repository_questions("/path/to/repo", questions)
)
```

## Best Practices

### Session Organization

```python
# Organize sessions by project/topic
session = InteractiveSessionManager(
    repo_path="/path/to/fastapi-project",
    config=config,
    session_dir="./sessions/fastapi-exploration"
)

# Use descriptive session directories
session = InteractiveSessionManager(
    repo_path="/path/to/microservice",
    config=config, 
    session_dir="./sessions/microservice-architecture-review"
)
```

### Question Progression

```python
# Start broad, then focus
session = InteractiveSessionManager(repo_path, config)

# 1. Architecture overview
result1 = session.ask_question("What is the overall architecture?")

# 2. Focus on specific area (builds on architecture knowledge)
result2 = session.ask_question("How does the user management system work?")

# 3. Performance analysis (leverages previous understanding)
result3 = session.ask_question("What are the performance bottlenecks?")

# 4. Specific implementation details
result4 = session.ask_question("Show me the authentication flow implementation")
```

### Resource Management

```python
# Use context manager for automatic cleanup
class SessionManager:
    def __init__(self, repo_path, config):
        self.repo_path = repo_path
        self.config = config
        self.session = None
    
    def __enter__(self):
        self.session = InteractiveSessionManager(
            self.repo_path, 
            self.config
        )
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.save_session()

# Usage
with SessionManager(repo_path, config) as session:
    result = session.ask_question("How does this work?")
    # Session automatically saved on exit
```

## Related APIs

- **[Multi-Agent Coordinator](multi-agent-coordinator.md)** - Agent selection and consolidation
- **[Web Search Agent](web-search-agent.md)** - External knowledge integration
- **[Exploration Memory](memory-system.md)** - Context tracking and persistence
- **[Narrative Utils](narrative-utils.md)** - Response formatting and display