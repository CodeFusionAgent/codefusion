# CLI Reference

Complete reference for CodeFusion's command-line interface.

## Global Options

These options are available for all commands:

```bash
cf [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGS]
```

### `--config, -c PATH`

Specify a custom configuration file.

**Default:** `config/default/config.yaml`

**Examples:**
```bash
cf --config my-config.yaml index /path/to/repo
cf -c production.yaml query "How does auth work?"
```

### `--verbose, -v`

Enable verbose output with detailed logging.

**Examples:**
```bash
cf --verbose index /path/to/repo
cf -v query "What are the API endpoints?"
```

### `--help`

Show help message for the command or subcommand.

**Examples:**
```bash
cf --help                    # Global help
cf index --help              # Command-specific help
```

### `--version`

Show CodeFusion version information.

**Example:**
```bash
cf --version
```

## Commands

### `index` - Index Repository

Index a repository to build the knowledge base for analysis.

```bash
cf index [OPTIONS] REPO_PATH
```

#### Arguments

**`REPO_PATH`** (required)
- **Type:** Path
- **Description:** Path to the repository to index
- **Example:** `/path/to/my-project`

#### Options

**`--strategy {react,plan_act,sense_act}`**
- **Default:** `react`
- **Description:** Exploration strategy to use during indexing
- **Examples:**
  ```bash
  cf index --strategy react /path/to/repo
  cf index --strategy plan_act /path/to/repo
  cf index --strategy sense_act /path/to/repo
  ```

**`--force, -f`**
- **Description:** Force re-indexing even if knowledge base exists
- **Example:**
  ```bash
  cf index --force /path/to/repo
  ```

**`--exclude DIR`** (repeatable)
- **Description:** Additional directories to exclude from indexing
- **Examples:**
  ```bash
  cf index --exclude build --exclude dist /path/to/repo
  cf index --exclude "test_*" /path/to/repo
  ```

**`--max-files NUMBER`**
- **Description:** Maximum number of files to index
- **Default:** No limit
- **Example:**
  ```bash
  cf index --max-files 1000 /path/to/repo
  ```

#### Output

```
🔍 Indexing repository: /path/to/repo
📁 Found 1,247 files (342 after filtering)
⚡ Processing files...
  ├─ Python files: 156 processed
  ├─ JavaScript files: 89 processed
  ├─ Configuration files: 23 processed
  └─ Documentation files: 74 processed

📊 Indexing completed in 45.2s
  ├─ Files processed: 342
  ├─ Entities extracted: 2,845
  ├─ Relationships found: 1,236
  └─ Knowledge base size: 12.4 MB

✅ Repository successfully indexed!
```

#### Examples

```bash
# Basic indexing
cf index /home/user/my-project

# Index with specific strategy
cf index --strategy plan_act /path/to/complex-project

# Force re-indexing with exclusions
cf index --force --exclude node_modules --exclude .git /path/to/repo

# Index with file limit and verbose output
cf --verbose index --max-files 500 /path/to/repo
```

### `query` - Query Knowledge Base

Ask natural language questions about the indexed codebase.

```bash
cf query [OPTIONS] QUESTION
```

#### Arguments

**`QUESTION`** (required)
- **Type:** String (quoted if contains spaces)
- **Description:** Natural language question about the code
- **Examples:**
  - `"How does authentication work?"`
  - `"What are the main API endpoints?"`
  - `"How is the database configured?"`

#### Options

**`--repo-path PATH`**
- **Description:** Repository path (if not using saved knowledge base)
- **Example:**
  ```bash
  cf query --repo-path /path/to/repo "How does caching work?"
  ```

**`--strategy {react,plan_act,sense_act}`**
- **Default:** `react`
- **Description:** Exploration strategy for answering the question
- **Examples:**
  ```bash
  cf query --strategy plan_act "How do I set up this project?"
  cf query --strategy sense_act "What architectural patterns are used?"
  ```

**`--max-depth NUMBER`**
- **Description:** Maximum exploration depth (overrides config)
- **Default:** From configuration
- **Example:**
  ```bash
  cf query --max-depth 10 "Complex architectural question"
  ```

**`--format {text,json,markdown}`**
- **Default:** `text`
- **Description:** Output format for the answer
- **Examples:**
  ```bash
  cf query --format json "How does auth work?"
  cf query --format markdown "Project structure overview"
  ```

**`--save-exploration PATH`**
- **Description:** Save detailed exploration steps to file
- **Example:**
  ```bash
  cf query --save-exploration exploration.json "Complex question"
  ```

#### Output

**Text Format (default):**
```
🔍 Query: How does user authentication work?

📝 Answer:
The application uses JWT-based authentication with the following components:

1. Login endpoint (/api/auth/login) validates credentials
2. JWT tokens are generated using the jsonwebtoken library
3. Middleware (auth.js) validates tokens on protected routes
4. User sessions are managed in Redis for quick lookup

🔗 Key Files:
  ├─ src/auth/auth.js:45 - JWT token generation
  ├─ src/middleware/auth.js:12 - Token validation
  ├─ src/routes/auth.js:23 - Login endpoint
  └─ config/auth.yaml:8 - Authentication configuration

💡 Confidence: 92%
⏱️  Query completed in 3.4s
```

**JSON Format:**
```json
{
  "question": "How does user authentication work?",
  "answer": "The application uses JWT-based authentication...",
  "confidence": 0.92,
  "sources": [
    {
      "file_path": "src/auth/auth.js",
      "line_number": 45,
      "content": "function generateToken(user) { ... }"
    }
  ],
  "exploration_steps": [...],
  "duration_seconds": 3.4,
  "token_usage": {
    "prompt_tokens": 1250,
    "completion_tokens": 380,
    "total_tokens": 1630
  }
}
```

#### Examples

```bash
# Simple query
cf query "What testing frameworks are used?"

# Query with specific strategy
cf query --strategy plan_act "How do I deploy this application?"

# Query with repository path
cf query --repo-path /path/to/repo "How does error handling work?"

# Get JSON output
cf query --format json "What are the main components?" > output.json

# Deep exploration
cf query --strategy sense_act --max-depth 15 "What architectural patterns are used?"
```

### `explore` - Full Repository Exploration

Perform comprehensive exploration and analysis of a repository.

```bash
cf explore [OPTIONS] REPO_PATH
```

#### Arguments

**`REPO_PATH`** (required)
- **Type:** Path
- **Description:** Path to repository to explore
- **Example:** `/path/to/project`

#### Options

**`--strategy {react,plan_act,sense_act}`**
- **Default:** `react`
- **Description:** Exploration strategy to use
- **Example:**
  ```bash
  cf explore --strategy sense_act /path/to/complex-project
  ```

**`--output-dir PATH`**
- **Description:** Directory to save exploration artifacts
- **Default:** `./exploration_output`
- **Example:**
  ```bash
  cf explore --output-dir /tmp/exploration /path/to/repo
  ```

**`--focus AREA`** (repeatable)
- **Description:** Focus exploration on specific areas
- **Options:** `architecture`, `security`, `performance`, `testing`, `dependencies`
- **Examples:**
  ```bash
  cf explore --focus architecture --focus security /path/to/repo
  cf explore --focus performance /path/to/repo
  ```

**`--generate-report`**
- **Description:** Generate comprehensive HTML report
- **Example:**
  ```bash
  cf explore --generate-report /path/to/repo
  ```

#### Output

```
🚀 Exploring repository: /path/to/project

📊 Repository Overview:
  ├─ Type: Web Application (Node.js + React)
  ├─ Size: 1,247 files, 156,789 lines of code
  ├─ Primary languages: JavaScript (68%), Python (22%), CSS (10%)
  └─ Last updated: 2024-03-15

🏗️  Architecture Analysis:
  ├─ Pattern: Microservices with API Gateway
  ├─ Frontend: React SPA with Redux state management
  ├─ Backend: Express.js REST API
  ├─ Database: PostgreSQL with Redis caching
  └─ Authentication: JWT with OAuth2 integration

🔧 Technology Stack:
  ├─ Frontend: React 18, Redux Toolkit, Material-UI
  ├─ Backend: Node.js 18, Express.js, Passport.js
  ├─ Database: PostgreSQL 14, Redis 7
  ├─ Testing: Jest, Cypress, Supertest
  └─ Build: Webpack 5, Babel, ESLint

🔒 Security Features:
  ├─ Authentication: JWT + OAuth2 (Google, GitHub)
  ├─ Authorization: Role-based access control (RBAC)
  ├─ Input validation: Joi schema validation
  ├─ Security headers: Helmet.js middleware
  └─ Rate limiting: Express rate limiter

📈 Code Quality Metrics:
  ├─ Test coverage: 87% (target: 90%)
  ├─ Code complexity: Low-Medium
  ├─ Dependencies: 156 (12 with known vulnerabilities)
  └─ Technical debt: Moderate

💡 Key Insights:
  ├─ Well-structured codebase with clear separation of concerns
  ├─ Good test coverage but missing integration tests
  ├─ Some dependencies need security updates
  └─ Documentation could be improved

🎯 Recommendations:
  ├─ Update vulnerable dependencies (express, lodash)
  ├─ Add integration tests for critical user flows
  ├─ Implement API documentation with OpenAPI
  └─ Consider adding monitoring and observability

✅ Exploration completed in 2m 34s
📁 Report saved to: exploration_output/report.html
```

#### Examples

```bash
# Basic exploration
cf explore /path/to/project

# Focused exploration
cf explore --focus security --focus performance /path/to/repo

# Generate detailed report
cf explore --generate-report --output-dir ./reports /path/to/repo

# Deep exploration with sense-act
cf explore --strategy sense_act /path/to/complex-project
```

### `stats` - Knowledge Base Statistics

Display statistics and information about the knowledge base.

```bash
cf stats [OPTIONS]
```

#### Options

**`--repo-path PATH`**
- **Description:** Repository path to show stats for
- **Example:**
  ```bash
  cf stats --repo-path /path/to/repo
  ```

**`--format {text,json,table}`**
- **Default:** `text`
- **Description:** Output format for statistics
- **Example:**
  ```bash
  cf stats --format json
  ```

**`--detailed, -d`**
- **Description:** Show detailed breakdown by file type
- **Example:**
  ```bash
  cf stats --detailed
  ```

#### Output

**Text Format:**
```
📊 Knowledge Base Statistics

🗂️  General:
  ├─ Repository: /path/to/my-project
  ├─ Knowledge base type: Vector (FAISS)
  ├─ Last indexed: 2024-03-15 14:32:18
  └─ Index status: Up to date

📁 Files:
  ├─ Total files: 1,247
  ├─ Indexed files: 342
  ├─ Excluded files: 905
  └─ Average file size: 2.4 KB

🔍 Entities:
  ├─ Total entities: 2,845
  ├─ Functions: 1,234 (43%)
  ├─ Classes: 456 (16%)
  ├─ Variables: 789 (28%)
  ├─ Imports: 234 (8%)
  └─ Comments: 132 (5%)

🔗 Relationships:
  ├─ Total relationships: 1,236
  ├─ Function calls: 567 (46%)
  ├─ Class inheritance: 89 (7%)
  ├─ Variable usage: 345 (28%)
  └─ Import dependencies: 235 (19%)

💾 Storage:
  ├─ Knowledge base size: 12.4 MB
  ├─ Vector embeddings: 8.9 MB
  ├─ Metadata: 2.1 MB
  └─ Index files: 1.4 MB

⚡ Performance:
  ├─ Average query time: 1.2s
  ├─ Cache hit rate: 78%
  └─ Memory usage: 156 MB
```

**JSON Format:**
```json
{
  "repository": "/path/to/my-project",
  "kb_type": "vector",
  "last_indexed": "2024-03-15T14:32:18Z",
  "status": "up_to_date",
  "files": {
    "total": 1247,
    "indexed": 342,
    "excluded": 905,
    "average_size_kb": 2.4
  },
  "entities": {
    "total": 2845,
    "by_type": {
      "functions": 1234,
      "classes": 456,
      "variables": 789,
      "imports": 234,
      "comments": 132
    }
  },
  "relationships": {
    "total": 1236,
    "by_type": {
      "function_calls": 567,
      "class_inheritance": 89,
      "variable_usage": 345,
      "import_dependencies": 235
    }
  },
  "storage": {
    "total_size_mb": 12.4,
    "embeddings_mb": 8.9,
    "metadata_mb": 2.1,
    "index_mb": 1.4
  },
  "performance": {
    "avg_query_time_s": 1.2,
    "cache_hit_rate": 0.78,
    "memory_usage_mb": 156
  }
}
```

#### Examples

```bash
# Basic stats
cf stats

# Stats for specific repository
cf stats --repo-path /path/to/repo

# Detailed breakdown
cf stats --detailed

# JSON output for processing
cf stats --format json > stats.json
```

### `demo` - Run Demonstration

Run a demonstration of CodeFusion capabilities on a sample repository.

```bash
cf demo [OPTIONS] REPO_PATH
```

#### Arguments

**`REPO_PATH`** (required)
- **Type:** Path
- **Description:** Path to repository for demonstration
- **Example:** `/path/to/demo/project`

#### Options

**`--interactive, -i`**
- **Description:** Run interactive demo with user prompts
- **Example:**
  ```bash
  cf demo --interactive /path/to/repo
  ```

**`--scenario SCENARIO`**
- **Description:** Run specific demo scenario
- **Options:** `onboarding`, `code_review`, `architecture`, `debugging`
- **Example:**
  ```bash
  cf demo --scenario onboarding /path/to/repo
  ```

#### Output

```
🎭 CodeFusion Demo

🚀 Welcome to CodeFusion! Let's explore what this tool can do.

Repository: /path/to/demo/project
Demo scenario: General overview

Step 1: Repository Indexing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%
✅ Indexed 89 files in 8.2 seconds

Step 2: Basic Code Understanding
❓ Question: "What type of application is this?"
💡 Answer: This is a Flask web application with a React frontend...

Step 3: Architecture Analysis  
❓ Question: "What is the overall architecture?"
💡 Answer: The application follows a client-server architecture...

Step 4: Development Workflow
❓ Question: "How do I run this application locally?"
💡 Answer: To run this application locally, follow these steps...

🎉 Demo completed! CodeFusion has successfully:
  ├─ Analyzed your codebase structure
  ├─ Understood the technology stack
  ├─ Provided insights about the architecture
  └─ Explained the development workflow

Next steps:
  • Try asking your own questions with: cf query "your question"
  • Explore the full repository with: cf explore /path/to/repo
  • Check configuration options with: cf --help
```

#### Examples

```bash
# Basic demo
cf demo /path/to/sample/repo

# Interactive demo
cf demo --interactive /path/to/repo

# Specific scenario
cf demo --scenario architecture /path/to/complex/project
```

## Environment Variables

These environment variables can override configuration settings:

### API Keys
```bash
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export AZURE_OPENAI_API_KEY="your-azure-key"
```

### Neo4j Configuration
```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"
```

### CodeFusion Settings
```bash
export CF_LLM_MODEL="gpt-4"
export CF_KB_TYPE="neo4j"
export CF_MAX_EXPLORATION_DEPTH="10"
export CF_VERBOSE="true"
export CF_DEBUG="true"
```

## Exit Codes

CodeFusion uses standard exit codes:

- **0**: Success
- **1**: General error
- **2**: Misuse of shell command (invalid arguments)
- **3**: Configuration error
- **4**: Resource error (file not found, permission denied)
- **5**: LLM provider error
- **6**: Knowledge base error

## Shell Completion

Enable shell completion for better CLI experience:

### Bash
```bash
# Add to ~/.bashrc
eval "$(_CF_COMPLETE=bash_source cf)"
```

### Zsh
```bash
# Add to ~/.zshrc
eval "$(_CF_COMPLETE=zsh_source cf)"
```

### Fish
```bash
# Add to ~/.config/fish/config.fish
eval (env _CF_COMPLETE=fish_source cf)
```

## Configuration File Integration

All CLI commands respect the configuration hierarchy:

1. Command-line options (highest priority)
2. Configuration file (--config)
3. Environment variables
4. Default values (lowest priority)

### Example with Configuration
```bash
# Use custom config
cf --config production.yaml query "How does deployment work?"

# Override specific settings
cf --config base.yaml --verbose query "Complex question"
```

## Debugging and Troubleshooting

### Verbose Mode
```bash
# Enable detailed output
cf --verbose index /path/to/repo
cf -v query "debug question"
```

### Debug Mode
```bash
# Enable debug logging
export CF_DEBUG=1
cf query "question"
```

### Configuration Validation
```bash
# Test configuration
cf --config my-config.yaml stats
```

### Performance Profiling
```bash
# Time command execution
time cf index /path/to/large/repo

# Monitor memory usage
/usr/bin/time -v cf index /path/to/repo
```

## Examples by Use Case

### Development Workflow
```bash
# Quick project understanding
cf explore /path/to/new/project
cf query "How do I run tests?"
cf query "What's the deployment process?"
```

### Code Review
```bash
# Analyze changes
cf index /path/to/updated/repo
cf query "What are potential security issues?"
cf query "Are there any code quality concerns?"
```

### Onboarding
```bash
# New team member workflow
cf demo --scenario onboarding /path/to/project
cf query "What technologies are used?"
cf query "How is the codebase structured?"
```

### Architecture Analysis
```bash
# Deep architectural exploration
cf explore --strategy sense_act --focus architecture /path/to/repo
cf query --strategy sense_act "What design patterns are used?"
```

## Next Steps

- Learn about [configuration options](../config/reference.md)
- See the [Python API reference](api.md)
- Check [usage examples](../usage/examples.md)