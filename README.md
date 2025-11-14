# CodeFusion - AI-Powered Codebase Analysis

A **pipeline-based multi-agent system** for deep codebase exploration and technical narrative generation. CodeFusion helps software engineers ramp up on new repositories by providing architectural understanding, execution flow analysis, and grounded code explanations.

## 🎯 Problem Statement

When engineers join a new project or explore unfamiliar code, they need:
- **Architectural Understanding**: How components fit together
- **Execution Flow**: How features work end-to-end
- **Grounded Explanations**: Answers backed by actual code with line numbers
- **Quick Ramp-up**: Comprehensive narratives without reading thousands of files

**CodeFusion solves this** by analyzing code repositories and generating technical narratives that explain how systems work.

---

## 🏗️ System Architecture

### High-Level Flow

```
User Question
    ↓
SupervisorAgent (Multi-pass coordination, LLM-based routing)
    ↓
CodeOrchestrator (State-based pipeline execution)
    ├─ Discovery Pipeline (5 strategies: KB, Keywords, Domain, Grep, Fallback)
    ├─ Analysis Pipeline (Parallel file analysis with LLM)
    ├─ Synthesis Pipeline (Narrative generation with validation feedback)
    └─ Validation Pipeline (Anti-hallucination checks)
    ↓
Technical Narrative (Markdown with code references)
```

### Component Interaction

```
┌─────────────────────────────────────────────────────────────┐
│                        USER LAYER                            │
│  CLI: python -m cf.run.main ask /repo "question"            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   SUPERVISOR AGENT                           │
│  • Multi-pass coordination (1-3 passes)                     │
│  • LLM-based agent selection (code/docs/web)                │
│  • Result synthesis and caching                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  CODE ORCHESTRATOR                           │
│  State-based flow: INIT → REPO_READY → FILES_DISCOVERED     │
│                 → FILES_ANALYZED → SYNTHESIS_COMPLETE        │
└─────┬────────┬────────┬────────┬──────────────────────────┘
      │        │        │        │
┌─────▼──┐ ┌──▼──────┐ ┌▼──────┐ ┌▼────────────┐
│Discovery│ │Analysis │ │Synth- │ │Validation  │
│Pipeline │ │Pipeline │ │esis   │ │Pipeline    │
│         │ │         │ │Pipeline│ │            │
│5 Strate-│ │Parallel │ │LLM +  │ │Facts,Lines,│
│gies     │ │File     │ │Cross- │ │Paths       │
│         │ │Analysis │ │File   │ │            │
└─────┬───┘ └──┬──────┘ └┬──────┘ └┬───────────┘
      │        │         │         │
┌─────▼────────▼─────────▼─────────▼─────────────────────────┐
│                  INFRASTRUCTURE LAYER                        │
│  • Neo4j/SQLite Knowledge Base (6-layer architecture)       │
│  • Tool Registry (File ops, code analysis, KB queries)      │
│  • Tiered LLM Manager (FAST/STANDARD/ADVANCED models)       │
│  • Semantic Cache (Cross-session memory)                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 📐 Design Choices & Architecture

### 1. **Pipeline-Based Architecture**

**Why Pipelines?**
- **Modular**: Each pipeline has a single responsibility (200 LOC vs 4,375 in monolithic)
- **Testable**: Independent unit testing per pipeline
- **Config-Driven**: All behavior controlled via YAML config
- **Reusable**: Pipelines work for any repo structure

**Four Core Pipelines:**

#### **Discovery Pipeline** (`cf/agents/pipelines/discovery.py`)
**Purpose**: Find relevant files for the question

**Strategy Chain** (tries in order, highest priority first):
1. **GraphQueryStrategy**: Uses Knowledge Base for structural queries
   - KB semantic search for similar code
   - KB "Life of X" tracing (entry point → execution path)
   - KB pattern detection (finds classes/functions by name)
2. **KeywordMatchingStrategy**: Simple keyword-to-file matching
3. **DomainDetectionStrategy**: LLM infers domain (e.g., "auth" → `src/auth/`)
4. **GrepSearchStrategy**: Regex search through codebase
5. **FallbackStrategy**: Returns most recently modified files

**Design Choice**: Chain-of-responsibility pattern allows graceful degradation if KB unavailable.

#### **Analysis Pipeline** (`cf/agents/pipelines/analysis.py`)
**Purpose**: Extract structured summaries from discovered files

**Process**:
1. **Read file structure**: Parse AST, extract functions/classes/imports
2. **LLM summarization** (FAST tier): Generate key features, architectural insights
3. **Cache result**: Semantic cache prevents re-analysis

**Parallel Execution**:
- ThreadPoolExecutor with configurable workers (default: 10)
- Adaptive rate limiting: reduces workers on 429 errors
- Batch processing for large file sets

**Design Choice**: Parallel analysis reduces analysis time by 5-10x for large repos.

#### **Synthesis Pipeline** (`cf/agents/pipelines/synthesis.py`)
**Purpose**: Generate technical narrative from file summaries

**Multi-Phase Process**:
1. **Key File Selection**: Rank files by relevance (keyword match, function count)
2. **Cross-File Analysis**: Infer relationships (shared classes, dependencies, data flow)
3. **Pattern Detection**: Identify design patterns from KB or heuristics
4. **Execution Tracing**: Trace "life of X" entry point → full call chain
5. **LLM Generation** (ADVANCED tier): Build comprehensive narrative with code references
6. **Proportional Word Count**: Target = `file_count × 400-700 words` (scales with complexity)

**Design Choice**: Multi-phase preparation before LLM call produces higher quality narratives.

#### **Validation Pipeline** (`cf/agents/pipelines/validation.py`)
**Purpose**: Anti-hallucination quality assurance

**Four Validation Checks**:
1. **Line Number Validation**: Ensure line numbers exist and are within file bounds
2. **File Path Validation**: Verify all file paths mentioned actually exist
3. **Fact Verification**: Extract code claims, verify identifiers match actual code
4. **Word Count Validation**: Ensure sufficient detail (proportional to file count)

**Validation Feedback Loop**:
```
Synthesis → Validation (fails) → Store issues → Retry Synthesis (with issues)
```
- Max 2 retries per synthesis attempt
- Each retry receives specific validation errors to fix
- Prevents identical outputs on retry

**Design Choice**: Configurable thresholds adapt to different repo structures (e.g., `backend/`, `pkg/`, `cmd/`).

---

### 2. **State-Based Flow** (vs Iteration-Based)

**Why State Machines?**
- **Predictable**: Each state has well-defined transitions
- **Debuggable**: Easy to trace where pipeline failed
- **Resumable**: Can save/restore state (future feature)

**State Transitions**:
```
INIT → (scan repo) → REPO_READY
     → (discover files) → FILES_DISCOVERED
     → (analyze files) → FILES_ANALYZED
     → (synthesize + validate) → SYNTHESIS_COMPLETE
     → COMPLETE
```

**Design Choice**: State-based flow eliminates infinite loops and clarifies pipeline progress.

---

### 3. **Knowledge Base Architecture**

#### **6-Layer Knowledge Base**

Each layer builds on the previous, enabling progressively sophisticated queries:

**Layer 1: Repository Layer**
- **Stores**: File paths, sizes, modification times, extensions
- **Purpose**: Fast file discovery and filtering
- **Query**: "Find all Python files in `src/auth/`"

**Layer 2: Structural Layer** (AST-based)
- **Stores**: Functions, classes, methods, parameters, return types, imports
- **Purpose**: Understand code structure without reading content
- **Query**: "Find all classes implementing `BaseHandler`"
- **Why AST?**: Parsing code into Abstract Syntax Trees gives accurate structure regardless of formatting

**Layer 3: Dependency Layer** (Graph relationships)
- **Stores**: Function calls, class inheritance, import dependencies
- **Purpose**: Trace execution paths and understand relationships
- **Query**: "Show call chain from `login()` to database"

**Layer 4: Semantic Layer** (Embeddings)
- **Stores**: Code embeddings from `sentence-transformers` (local model)
- **Purpose**: Find semantically similar code
- **Query**: "Find code similar to authentication flow"
- **Why Local Embeddings?**: No external API calls, faster, free

**Layer 5: Pattern Layer** (Design patterns & code smells)
- **Stores**: Detected patterns (Singleton, Factory, MVC) and anti-patterns (God Class, Long Method)
- **Purpose**: Architectural understanding and quality assessment
- **Query**: "Show all Singleton classes"

**Layer 6: Life-of-X Layer** (Execution tracing)
- **Stores**: Entry points, execution paths, data flow nodes
- **Purpose**: Answer "How does X work?" questions
- **Query**: "Trace student application from submission to enrollment"

#### **Neo4j vs SQLite Backend**

**Why Two Backends?**
- **SQLite**: Zero setup, perfect for quick start and small repos
- **Neo4j**: Optimized for graph queries, essential for large repos

**Neo4j Design Choice**:
- **What it stores**: Nodes (files, functions, classes) + Edges (calls, imports, inherits)
- **Why graph database?**:
  - Recursive queries (call chains of any depth)
  - Pattern matching (`MATCH (a)-[:CALLS*1..5]->(b)` finds 1-5 hop call chains)
  - Fast traversals (index-free adjacency)
- **When to use**: Production deployments, repos >10K files, deep architectural analysis

**SQLite Design Choice**:
- **What it stores**: Same data, but in relational tables with JSON columns for nested data
- **Why relational?**: Simple, portable, no external dependencies
- **When to use**: Development, testing, small repos (<10K files)

**Example: Call Chain Query**

Neo4j (native graph):
```cypher
MATCH (start:Function {name: 'login'})-[:CALLS*1..10]->(end:Function)
RETURN path
```

SQLite (emulated graph):
```sql
WITH RECURSIVE call_chain AS (
  SELECT source, target, 1 as depth FROM function_calls WHERE source = 'login'
  UNION ALL
  SELECT fc.source, fc.target, cc.depth + 1
  FROM function_calls fc JOIN call_chain cc ON fc.source = cc.target
  WHERE cc.depth < 10
)
SELECT * FROM call_chain;
```

---

### 4. **Tool Registry System**

**Purpose**: Provides tools for agents and pipelines to interact with codebase

**Core Tools** (`cf/tools/registry.py`):

| Tool | Purpose | Used By | Example |
|------|---------|---------|---------|
| `scan_directory` | Recursive file system scan | Discovery Pipeline | Find all `.py` files |
| `read_file` | Read file with encoding detection | Analysis Pipeline | Extract file content |
| `search_files` | Grep-based content search | Discovery Pipeline | Find "def authenticate" |
| `analyze_code` | AST parsing + structure extraction | Analysis Pipeline | Extract functions/classes |
| `kb_query` | Knowledge Base structural queries | Discovery Pipeline | Find call chains |
| `kb_semantic_search` | Embedding-based similarity | Discovery Pipeline | Find similar code |
| `kb_lifeofx_trace` | Execution path tracing | Synthesis Pipeline | Trace request handling |

**Why Tool Registry?**
- **Abstraction**: Pipelines don't know implementation details
- **Schema-based**: Each tool has JSON schema for validation
- **Testable**: Mock tools for unit tests
- **Extensible**: Add tools without modifying pipelines

**Design Choice**: Tools are functions, not classes, for simplicity and composability.

---

### 5. **Tiered LLM Strategy**

**Problem**: Using expensive models (GPT-4) for all tasks wastes money

**Solution**: Route tasks to appropriate model tiers

**Three Tiers**:

| Tier | Model | Cost/1M Tokens | Use Cases |
|------|-------|----------------|-----------|
| **FAST** | gpt-4.1-mini | $0.25 | File summaries, classification, simple questions |
| **STANDARD** | gpt-5 | $2.50 | General analysis, moderate reasoning |
| **ADVANCED** | gpt-5 | $3.00 | Final synthesis, complex reasoning, narrative generation |

**Design Choice**: Saves 60-80% on LLM costs while maintaining quality where it matters.

**Usage Example**:
- Analysis Pipeline uses **FAST** tier (summarize 100 files = $0.05)
- Synthesis Pipeline uses **ADVANCED** tier (generate narrative = $0.30)
- Total: $0.35 instead of $3.00 if all used ADVANCED

---

### 6. **Validation Feedback Loop**

**Problem**: LLMs hallucinate file paths and line numbers

**Solution**: Validate narrative, provide specific errors to LLM on retry

**Feedback Loop**:
```
Attempt 1: Generate narrative
          ↓
       Validate (grounding: 100%, line coverage: 8%, word count: 1100)
          ↓
       FAIL (line coverage < 10%, word count < 1200)
          ↓
       Store issues: [
         "Line coverage too low: 8% (need 10%)",
         "Word count too short: 1100 words (need 1200-2100)"
       ]
          ↓
Attempt 2: Generate narrative WITH issues shown to LLM
          ↓
       Validate (grounding: 100%, line coverage: 12%, word count: 1250)
          ↓
       PASS ✅
```

**Design Choice**: Bidirectional feedback improves quality without human intervention.

**Configurable Thresholds** (`config.yaml`):
- `min_line_coverage: 0.10` (10% of sentences must cite code)
- `min_path_accuracy: 0.5` (50% of file paths must be valid)
- `min_identifier_match: 0.2` (20% of code identifiers must match actual code)
- `max_file_line_gap_chars: 100` (file path and line number must be within 100 chars)

---

### 7. **Multi-Pass Coordination**

**Problem**: Single-pass analysis may miss details

**Solution**: Supervisor orchestrates multiple passes with context sharing

**Pass Strategy**:
- **Pass 1**: Initial discovery and high-level understanding
- **Pass 2**: Deep dive into key components (informed by Pass 1 results)
- **Pass 3**: Integration and edge cases (only if needed)

**Context Sharing Decision** (LLM-based):
- After each pass, LLM analyzes results and decides:
  - **Complete**: All information gathered, synthesize answer
  - **Next Pass**: Need more detail, share context with next agent
  - **Retry**: Agent failed, retry current pass

**Design Choice**: Adaptive multi-pass prevents both under-analysis and over-analysis.

---

## 🚀 Quick Start

### Installation

```bash
# 1. Clone and enter directory
cd codefusion

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -e .

# 4. Set API key
export OPENAI_API_KEY="your-openai-api-key"  # Or Azure keys
```

### Knowledge Base Setup

#### **Option 1: SQLite (Recommended for Quick Start)**

Zero setup required - just run:

```bash
python -m cf.run.main ask /path/to/repo "How does authentication work?"
```

SQLite KB is automatically created at `.codefusion/knowledge.db`

#### **Option 2: Neo4j (Recommended for Production)**

For large repos or production use:

```bash
# Start Neo4j with Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest

# Configure CodeFusion
export NEO4J_PASSWORD="your-password"

# Update config.yaml
nano cf/configs/config.yaml
```

Set `knowledge_base.type: neo4j` in config, then run:

```bash
python -m cf.run.main ask /path/to/repo "How does authentication work?"
```

First run builds KB (5-30 minutes), subsequent runs are instant.

---

## 💡 Usage Examples

### Basic Question

```bash
python -m cf.run.main ask /path/to/repo "How does user authentication work?"
```

### Life-of-X Question

```bash
python -m cf.run.main ask /path/to/repo "Trace a student application from submission to enrollment"
```

### Architectural Question

```bash
python -m cf.run.main ask /path/to/repo "What design patterns are used?"
```

### With Verbose Logging

```bash
python -m cf.run.main --verbose ask /path/to/repo "How does routing work?"
```

---

## 📊 Output Format

CodeFusion generates technical narratives with:

- **Architectural Overview**: High-level system design
- **Component Interactions**: How pieces fit together
- **Code References**: File paths and line numbers for every claim
- **Execution Flow**: Step-by-step process traces
- **Design Patterns**: Identified architectural patterns
- **Cross-File Analysis**: Relationships and dependencies

**Example Output**:
```markdown
# Life of a Student Application: From Submission to Enrollment

## Architectural Overview
When a student submits an application, the journey begins with the
ApplicationController component receiving the submission through an
endpoint defined in `apps/enrollment/controllers.py` at line 45...

## Key Components

**ApplicationManager** (`apps/enrollment/managers.py:4`)
- Filters active (non-archived) applications
- Provides `get_queryset()` method at line 5 for database queries
- Implements Repository pattern for data access

**GradingTasks** (`apps/gradebook/tasks.py:7`)
- Celery async tasks for grade computation
- `task_compute_grades_for_cohort()` processes entire cohorts
- Integrates with Django management commands

## Component Interactions

The submission flows through...
```

---

## 🔧 Configuration

Key configuration sections in `cf/configs/config.yaml`:

### LLM Tiers
```yaml
llm:
  tiers:
    fast:
      model: "gpt-4.1-mini"
      cost_per_1m: 0.25
    advanced:
      model: "gpt-5"
      cost_per_1m: 3.00
```

### Validation Thresholds
```yaml
agents:
  thresholds:
    min_line_coverage: 0.10  # 10% of sentences cite code
    min_path_accuracy: 0.5   # 50% of paths must be valid

  validation:
    min_identifier_match: 0.2  # 20% identifier match threshold
    max_file_line_gap_chars: 100  # Prevent cross-paragraph pairing
    file_path_prefixes:  # Configurable for any repo structure
      - apps
      - src
      - backend
      - pkg
```

### Synthesis Settings
```yaml
agents:
  synthesis:
    words_per_file_min: 400  # Proportional word count
    words_per_file_max: 700
    target_narrative_min: 1200  # Absolute minimum
```

---

## 📁 Project Structure

```
cf/
├── agents/                    # Agent layer
│   ├── supervisor.py         # Multi-pass coordination
│   ├── code_orchestrator.py  # Pipeline orchestration
│   └── pipelines/            # Specialized pipelines
│       ├── discovery.py      # File discovery (5 strategies)
│       ├── analysis.py       # Parallel file analysis
│       ├── synthesis.py      # Narrative generation
│       └── validation.py     # Quality assurance
│
├── agents/kb/                # Knowledge Base layer
│   ├── structural_kb_agent.py # KB interface
│   ├── sqlite_adapter.py     # SQLite backend
│   ├── neo4j_adapter.py      # Neo4j backend
│   └── structural_analysis.py # AST parsing
│
├── tools/                    # Tool layer
│   ├── registry.py          # Tool registration
│   ├── repo_tools.py        # File operations
│   └── kb_tools.py          # KB queries
│
├── llm/                     # LLM integration
│   ├── client.py           # LiteLLM wrapper
│   └── model_tiers.py      # Tiered routing
│
├── cache/                  # Caching layer
│   └── semantic.py        # Semantic cache
│
└── configs/
    └── config.yaml        # All configuration
```

---

## 🎯 Design Principles

1. **Config-Driven**: No hardcoded values, everything in YAML
2. **Modular Pipelines**: Single responsibility, independently testable
3. **State-Based Flow**: Predictable, debuggable, resumable
4. **Validation Feedback**: Iterative quality improvement
5. **Cost-Optimized**: Tiered LLM strategy saves 60-80%
6. **Graceful Degradation**: Fallback strategies at every level
7. **Extensible**: Add tools/pipelines without core changes

---

## 📈 Performance

### Typical Analysis Times

| Repo Size | Files Analyzed | KB Build Time | Query Time |
|-----------|---------------|---------------|------------|
| Small (100-500 files) | 3-5 | 1-3 min | 10-20s |
| Medium (500-2K files) | 3-7 | 5-10 min | 15-30s |
| Large (2K-10K files) | 5-10 | 15-30 min | 20-40s |

**Note**: KB build is one-time, subsequent queries use cached KB.

### Cost Estimates

Average per-question cost with tiered LLM:
- File analysis (FAST): $0.03-0.10
- Narrative synthesis (ADVANCED): $0.20-0.40
- **Total: $0.25-0.50 per question**

Without tiered LLM (all ADVANCED): $2.00-3.00 per question

---

## 🔍 Troubleshooting

### KB Not Found

```bash
# Force KB rebuild
rm -rf .codefusion/
python -m cf.run.main ask /repo "question"
```

### Validation Failures

```bash
# Check validation thresholds in config.yaml
nano cf/configs/config.yaml

# Lower thresholds if needed
min_line_coverage: 0.08  # from 0.10
min_identifier_match: 0.15  # from 0.20
```

### Low Line Coverage

Add more file path prefixes to match your repo structure:

```yaml
validation:
  file_path_prefixes:
    - your_custom_prefix
    - another_prefix
```

---

## 📚 Documentation

- [Architecture Analysis](./ARCHITECTURE_ANALYSIS.md) - Detailed design review
- [Configuration Reference](./cf/configs/config.yaml) - All settings explained

---

## 🤝 Contributing

Contributions welcome! Focus areas:
1. New discovery strategies
2. Additional design pattern detectors
3. Improved validation heuristics
4. Enhanced cross-file analysis

---

## 📜 License

Apache 2.0 License

---

**Built with a pipeline-based architecture for systematic, intelligent code exploration.**
