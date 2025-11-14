# Current Implementation Architecture Map

**Date**: 2025-11-14
**Purpose**: Understand what exists before deciding on modular KB construction

---

## 📊 Executive Summary

**Current Architecture**:
- **KB Construction**: **MONOLITHIC** in `StructuralPipeline` (cf/agents/pipelines/structural.py:1)
- **Query Answering**: **MODULAR** with 4 pipelines (Discovery → Analysis → Synthesis → Validation)
- **KB Access**: **TOOL-BASED** via `StructuralKBAgent` (cf/agents/kb/structural_kb_agent.py:1)

**Key Insight**: KB construction is currently ONE large agent (StructuralPipeline) that does EVERYTHING:
- AST parsing
- Dependency graph building
- Semantic embeddings
- Pattern detection
- Life-of-X tracing

---

## 🏗️ Two Separate Architectures

### **1. Query-Answering Architecture** ✅ Already Modular

```
User Question
    ↓
SupervisorAgent (cf/agents/supervisor.py:28)
  - Intelligent agent selection (LLM-based routing)
  - Multi-pass coordination
  - Final synthesis
    ↓
CodeOrchestrator (cf/agents/code_orchestrator.py:1)
  - State-based flow (INIT → REPO_READY → FILES_DISCOVERED → FILES_ANALYZED → SYNTHESIS_COMPLETE)
    ↓
┌─────────────────────────────────────────────────────────┐
│                    4 MODULAR PIPELINES                   │
├─────────────────────────────────────────────────────────┤
│ 1. DiscoveryPipeline (cf/agents/pipelines/discovery.py) │
│    - 5 strategies: GraphQuery, Keyword, Domain, Grep,   │
│      Fallback                                            │
│    - Uses StructuralKBAgent tools for KB queries        │
│                                                          │
│ 2. AnalysisPipeline (cf/agents/pipelines/analysis.py)   │
│    - Parallel file analysis (10 workers)                │
│    - LLM summaries (FAST tier)                          │
│    - Adaptive rate limiting                             │
│                                                          │
│ 3. SynthesisPipeline (cf/agents/pipelines/synthesis.py) │
│    - Cross-file analysis                                │
│    - Pattern detection                                  │
│    - Life-of-X tracing                                  │
│    - LLM narrative generation (ADVANCED tier)           │
│                                                          │
│ 4. ValidationPipeline (cf/agents/pipelines/validation.py)│
│    - Line number validation                             │
│    - Path accuracy                                      │
│    - Fact verification                                  │
│    - Feedback loop for retries                          │
└─────────────────────────────────────────────────────────┘
    ↓
KB Query Tools (via StructuralKBAgent)
  - semantic_search
  - find_design_patterns
  - trace_execution_path
  - get_architecture_overview
```

**Status**: ✅ Well-designed, modular, working

---

### **2. KB Construction Architecture** ❌ Currently Monolithic

```
StructuralPipeline.build_knowledge_base()
(cf/agents/pipelines/structural.py:1)
│
├─ Scan repository files
│
├─ Parse in parallel (10 workers)
│  ├─ PythonASTParser (cf/knowledge/structural/ast_parser.py)
│  └─ MultiLanguageParser (cf/knowledge/structural/multi_lang_parser.py)
│
├─ Store in Neo4j/SQLite
│  ├─ Neo4jKnowledgeBase (cf/knowledge/structural/neo4j_client.py)
│  └─ SQLiteKnowledgeBase (cf/knowledge/structural/sqlite_client.py)
│
└─ Build enhanced layers (ALL IN ONE AGENT)
   ├─ Semantic Layer
   │  └─ CodeEmbedder (cf/knowledge/semantic/embeddings.py)
   │      - Generates embeddings for all functions/classes
   │
   ├─ Pattern Layer
   │  ├─ DesignPatternDetector (cf/knowledge/patterns/design_patterns.py)
   │  ├─ ArchitecturalPatternDetector (cf/knowledge/patterns/architectural_patterns.py)
   │  └─ CodeSmellDetector (cf/knowledge/patterns/code_smells.py)
   │
   └─ Life-of-X Layer
      ├─ ExecutionPathTracer (cf/knowledge/lifeofx/execution_paths.py)
      └─ DataFlowAnalyzer (cf/knowledge/lifeofx/dataflow.py)
```

**Status**: ⚠️ Monolithic - all logic in one class

**What this means**:
- Can't swap out pattern detector without modifying StructuralPipeline
- Can't A/B test different embedding models easily
- Can't run semantic + pattern layers in parallel
- Can't measure which layer contributes most to accuracy

---

## 📂 File-by-File Breakdown

### **cf/agents/** - Main Agents (Query-Answering)

| File | Lines | Purpose | Type |
|------|-------|---------|------|
| **base.py** | 255 | Abstract base for all agents | Foundation |
| **protocols.py** | 307 | Interface definitions (loose coupling) | Architecture |
| **registry.py** | 211 | Central agent registration system | Architecture |
| **supervisor.py** | 1,073 | Top-level orchestrator | Query-Answering |
| **code_orchestrator.py** | 765 | Pipeline coordinator | Query-Answering |
| **multi_pass_coordinator.py** | 365 | Multi-pass logic | Query-Answering |
| **knowledge_base.py** | 281 | Base classes for pluggable KB agents | Architecture |
| **docs.py** | 337 | Documentation specialist (DISABLED) | Query-Answering |
| **web.py** | 303 | Web search specialist (DISABLED) | Query-Answering |

**Key Insight**: Query agents are well-modularized with clear separation.

---

### **cf/agents/pipelines/** - Pipeline Components (Query-Answering)

| File | Lines | Purpose | Dependencies |
|------|-------|---------|--------------|
| **discovery.py** | 683 | Find relevant files | StructuralKBAgent tools, LLM, repo tools |
| **analysis.py** | 447 | Parallel file analysis | LLM (FAST), cache |
| **synthesis.py** | 915 | Narrative generation | LLM (ADVANCED), KB tools |
| **validation.py** | 832 | Answer validation | Repo tools, optional LLM |
| **structural.py** | 1,388 | **KB construction AND query** | Neo4j, parsers, embedders, detectors |
| **result_types.py** | 95 | Common data classes | None |

**Key Insight**: `structural.py` is the ONLY file that builds KB. It's massive (1,388 lines) and does EVERYTHING.

---

### **cf/agents/kb/** - KB Query Interface

| File | Lines | Purpose | Type |
|------|-------|---------|------|
| **structural_kb_agent.py** | 766 | Exposes KB as tools | Query-Answering |

**What it does**:
- Wraps StructuralPipeline with tool interface
- 20+ tools: `semantic_search`, `find_design_patterns`, `trace_execution_path`, etc.
- Used by DiscoveryPipeline and SynthesisPipeline

**Key Insight**: This is the ONLY way pipelines access KB (tool-based, clean interface).

---

### **cf/knowledge/** - Knowledge Base Layers

#### **knowledge/structural/** - Core Layer (AST + Graph)

| File | Purpose | Used By |
|------|---------|---------|
| **neo4j_client.py** | Neo4j CRUD operations | StructuralPipeline (KB construction) |
| **sqlite_client.py** | SQLite alternative | StructuralPipeline (KB construction) |
| **ast_parser.py** | Python AST parsing | StructuralPipeline (KB construction) |
| **multi_lang_parser.py** | JS/TS/Go/Rust parsing | StructuralPipeline (KB construction) |
| **dependency_graph.py** | Call graph builder | StructuralPipeline (KB construction) |
| **schema.py** | Data structures | Everyone |

**Role**: KB Construction foundation

---

#### **knowledge/semantic/** - Embedding Layer

| File | Purpose | Used By |
|------|---------|---------|
| **embeddings.py** | Generate code embeddings | StructuralPipeline (KB construction) |
| **similarity.py** | Semantic search | StructuralKBAgent (query-answering) |

**Models Supported**:
- OpenAI (text-embedding-small, text-embedding-large)
- Local (all-MiniLM-L6-v2, all-mpnet-base-v2)
- LiteLLM (any provider)

**Role**: Enables "find code similar to X" queries

---

#### **knowledge/patterns/** - Pattern Detection Layer

| File | Purpose | Used By |
|------|---------|---------|
| **design_patterns.py** | Detect Singleton, Factory, Observer, etc. | StructuralPipeline (KB construction) |
| **architectural_patterns.py** | Detect MVC, Repository, Layered | StructuralPipeline (KB construction) |
| **code_smells.py** | Detect God Class, Long Method | StructuralPipeline (KB construction) |

**Patterns Detected**:
- **Creational**: Singleton, Factory, Builder, Prototype, AbstractFactory
- **Structural**: Adapter, Decorator, Proxy, Facade, Composite
- **Behavioral**: Observer, Strategy, Command, Template, State
- **Architectural**: MVC, Layered, Repository, Microservice
- **Code Smells**: God Class, Long Method, Feature Envy, Lazy Class, Data Class

**Role**: Enables "find all singleton patterns" queries

---

#### **knowledge/lifeofx/** - Execution Tracing Layer

| File | Purpose | Used By |
|------|---------|---------|
| **execution_paths.py** | Trace call chains | StructuralPipeline (KB construction) |
| **dataflow.py** | Trace data flow | StructuralPipeline (KB construction) |

**Capabilities**:
- Entry-to-exit execution paths
- Request-to-response lifecycles
- Step-by-step narratives
- Data transformation tracking

**Role**: Enables "How does user login work?" queries

---

#### **knowledge/incremental/** - Update Management

| File | Purpose | Used By |
|------|---------|---------|
| **file_watcher.py** | Detect file changes | StructuralPipeline (KB updates) |
| **differential.py** | Incremental KB updates | StructuralPipeline (KB updates) |

**Performance**: 5 changed files in 5 seconds (vs 90 min full rebuild)

---

## 🔍 Deep Dive: StructuralPipeline (The Monolith)

**File**: `cf/agents/pipelines/structural.py` (1,388 lines)

### **What it does**:

```python
class StructuralPipeline:
    """
    ONE class that does EVERYTHING for KB construction:
    1. Repository scanning
    2. AST parsing (Python, JS, TS, Go, etc.)
    3. Neo4j/SQLite storage
    4. Semantic embeddings
    5. Pattern detection
    6. Life-of-X tracing
    7. Incremental updates
    8. Query interface
    """

    def build_knowledge_base(self, repo_path: str):
        """
        Full KB construction (one-time, expensive)

        Steps:
        1. Scan repository files
        2. Parse in parallel (10 workers)
           - PythonASTParser for .py files
           - MultiLanguageParser for others
        3. Store in Neo4j graph:
           - File nodes
           - Function nodes
           - Class nodes
           - CALLS edges
           - IMPORTS edges
           - INHERITS edges
        4. Build enhanced layers:
           - Semantic: Generate embeddings (CodeEmbedder)
           - Patterns: Detect patterns (DesignPatternDetector)
           - Life-of-X: Build execution traces (ExecutionPathTracer)
        """
        pass

    def _build_enhanced_layers(self):
        """
        Build semantic, pattern, and life-of-x layers

        ALL IN THIS ONE METHOD (lines 800-1100)
        """
        # Semantic layer
        embedder = CodeEmbedder(...)
        for function in all_functions:
            embedding = embedder.embed(function)
            store_embedding(embedding)

        # Pattern layer
        pattern_detector = DesignPatternDetector(...)
        patterns = pattern_detector.detect(classes)
        store_patterns(patterns)

        # Life-of-X layer
        tracer = ExecutionPathTracer(...)
        paths = tracer.trace(entry_points)
        store_paths(paths)

    def find_files_for_question(self, question: str):
        """
        Query interface (used by StructuralKBAgent)

        Uses all layers:
        - Semantic search
        - Pattern matching
        - Life-of-X tracing
        """
        pass
```

### **Problems with Monolithic Design**:

1. **Can't A/B Test**: Want to compare `all-MiniLM-L6-v2` vs `all-mpnet-base-v2`? Must modify StructuralPipeline code.

2. **Can't Measure Impact**: Does pattern detection help or hurt? Can't disable it without code changes.

3. **Can't Parallelize**: Semantic and Pattern layers could run in parallel, but currently sequential.

4. **Can't Swap Implementations**: Want to try a different pattern detector? Must modify StructuralPipeline.

5. **Testing Complexity**: 1,388 lines in one class makes unit testing difficult.

---

## 🎯 Your Proposed Modular Design

**What you want**:

```
KBBuildCoordinator
    ↓
1. StructuralAnalysisAgent (no dependencies)
   - AST parsing
   - Graph storage
   ↓
2. DependencyAnalysisAgent (depends on Structural)
   - Call graph building
   - Import analysis
   ↓
3. Run in parallel:
   ├─ SemanticAnalysisAgent (depends on Structural)
   │  - Embedding generation
   │
   └─ PatternRecognitionAgent (depends on Dependency)
      - Design pattern detection
   ↓
4. LifeOfXAgent (depends on Dependency)
   - Execution tracing
```

### **How this would work**:

1. **Split StructuralPipeline** into 5 separate agents:
   ```
   StructuralPipeline (1,388 lines)
       ↓
   StructuralAnalysisAgent (300 lines) - AST parsing
   DependencyAnalysisAgent (250 lines) - Call graphs
   SemanticAnalysisAgent (200 lines) - Embeddings
   PatternRecognitionAgent (300 lines) - Pattern detection
   LifeOfXAgent (250 lines) - Execution tracing
   ```

2. **Create KBBuildCoordinator**:
   ```python
   class KBBuildCoordinator:
       def build_kb(self, repo_path: str):
           # 1. Run structural (foundational)
           structural_result = structural_agent.build(repo_path)

           # 2. Run dependency (needs structural)
           dependency_result = dependency_agent.build(repo_path)

           # 3. Run semantic + pattern in parallel (independent)
           with ThreadPoolExecutor() as executor:
               semantic_future = executor.submit(semantic_agent.build)
               pattern_future = executor.submit(pattern_agent.build)
               semantic_result = semantic_future.result()
               pattern_result = pattern_future.result()

           # 4. Run life-of-x (needs dependency)
           lifeofx_result = lifeofx_agent.build(repo_path)
   ```

3. **Enable Experimentation**:
   ```yaml
   # config.yaml
   knowledge_agents:
     structural_analyzer:
       enabled: true

     semantic_analyzer:
       enabled: true
       embedding_model: "all-MiniLM-L6-v2"  # Easy to swap!

     pattern_recognizer:
       enabled: false  # Easy to disable for A/B test!

     lifeofx_tracer:
       enabled: true
   ```

4. **Run Experiments**:
   ```python
   # Does pattern detection help?
   variant_a = ExperimentConfig(
       name="with_patterns",
       config={'knowledge_agents': {'pattern_recognizer': {'enabled': True}}}
   )
   variant_b = ExperimentConfig(
       name="without_patterns",
       config={'knowledge_agents': {'pattern_recognizer': {'enabled': False}}}
   )

   runner.run_experiment(query="Find factory patterns", variants=[variant_a, variant_b])
   ```

---

## 🔬 What is CFG-Based Taint Tracking?

### **CFG = Control Flow Graph**

A CFG represents all possible execution paths through a function.

**Example Function**:
```python
def authenticate(username, password):
    # Block 1 (Entry)
    user = db.query(f"SELECT * FROM users WHERE name='{username}'")  # SQL injection risk!

    # Block 2 (Conditional)
    if user is None:
        return False  # Block 3 (Exit 1)

    # Block 4
    if check_password(user, password):
        return True   # Block 5 (Exit 2)
    else:
        return False  # Block 6 (Exit 3)
```

**CFG Representation**:
```
[Entry: Block 1]
    ↓
[Conditional: Block 2]
    ├─ (user is None) → [Exit 1: Block 3]
    └─ (user exists) → [Block 4]
                           ├─ (password valid) → [Exit 2: Block 5]
                           └─ (password invalid) → [Exit 3: Block 6]
```

---

### **Taint Tracking**

**Purpose**: Track how untrusted data (user input) flows through the code.

**Example - SQL Injection Detection**:

1. **Mark taint source**: `username` parameter is TAINTED (user input)
2. **Trace data flow**: `username` → string interpolation → `db.query()`
3. **Check if reaches sink**: SQL query without sanitization = **VULNERABLE**

**CFG-Based Taint Tracking**:
```python
class TaintAnalyzer:
    def track_taint(self, function_cfg: ControlFlowGraph, taint_source: str):
        """
        Track how tainted data flows through CFG

        Algorithm:
        1. Start with taint_source (e.g., 'username')
        2. Follow all CFG paths
        3. Mark variables as tainted if derived from taint_source
        4. Report if tainted data reaches dangerous sink (SQL, shell, file write)
        """
        tainted = {taint_source}

        for block in cfg.blocks:
            for operation in block.operations:
                # If operation uses tainted variable
                if operation.uses_any(tainted):
                    # Result becomes tainted
                    tainted.add(operation.result)

                    # Check if dangerous sink
                    if operation.is_sql_query() or operation.is_shell_command():
                        report_vulnerability(operation, tainted)
```

**Output**:
```
⚠️ SECURITY VULNERABILITY: SQL Injection
Path: username (user input) → db.query() (unsanitized)
File: auth.py:45
Recommendation: Use parameterized queries
```

---

### **Why CFG + Taint Tracking is Powerful**

**Current System** (Call Graph Only):
```
authenticate() CALLS db.query()
```
- Knows that `authenticate` calls `db.query`
- Doesn't know WHAT DATA is passed

**With CFG + Taint Tracking**:
```
authenticate() CALLS db.query(username)
  ↓
username is TAINTED (user input)
  ↓
db.query() receives TAINTED data
  ↓
⚠️ SQL injection risk!
```

---

### **How to Store CFG in Neo4j**

**Nodes**:
```cypher
(:CFGNode {
  function_id: "authenticate",
  block_id: 1,
  type: "entry",  // entry, conditional, exit
  code: "user = db.query(...)",
  line_number: 45
})
```

**Edges**:
```cypher
(:CFGNode)-[:CFG_NEXT {condition: "user is None"}]->(:CFGNode)
(:CFGNode)-[:CFG_BRANCH {branch_type: "true_branch"}]->(:CFGNode)
```

**Taint Tracking**:
```cypher
(:Variable {name: "username", tainted: true})-[:FLOWS_TO]->(:Variable {name: "query"})
(:Variable {name: "query"})-[:USED_IN]->(:Operation {type: "sql_query", safe: false})
```

**Query for Vulnerabilities**:
```cypher
// Find all paths from tainted input to unsafe SQL
MATCH path = (source:Variable {tainted: true})-[:FLOWS_TO*]->(sink:Operation {type: "sql_query", safe: false})
RETURN path
```

---

### **Current System vs With CFG**

| Feature | Current (Call Graph) | With CFG + Taint |
|---------|---------------------|------------------|
| Knows function calls | ✅ Yes | ✅ Yes |
| Knows execution paths | ❌ No | ✅ Yes |
| Knows data flow | ❌ No | ✅ Yes |
| Detects SQL injection | ❌ No | ✅ Yes |
| Traces variable values | ❌ No | ✅ Yes |
| Security analysis | ❌ Limited | ✅ Comprehensive |

---

## 🎯 Summary

### **Current State**:
- ✅ Query-answering is modular (4 pipelines)
- ⚠️ KB construction is monolithic (StructuralPipeline does everything)
- ❌ No CFG-based taint tracking

### **Your Proposed Changes**:
1. **Modular KB Construction**: Split StructuralPipeline into 5 agents
2. **CFG + Taint Tracking**: Add security analysis capabilities
3. **Experimentation**: A/B test different KB strategies

### **Benefits of Going Modular**:
- 🧪 Easy A/B testing (does pattern detection help?)
- 📊 Measure impact of each layer
- ⚡ Parallelize independent layers (semantic + pattern)
- 🔄 Swap implementations without code changes
- 🧹 Better code organization (300 LOC/agent vs 1,388 LOC monolith)

### **Evaluation Pipeline**:
- ✅ Separate from synthesis (you confirmed)
- ✅ Answer Comparator is P2, not P1
- ✅ Focus on KB construction modularity first

---

## ❓ Next Decision Point

**Do you want to split StructuralPipeline into modular agents?**

**If YES**:
- We need KBBuildCoordinator
- We need agent protocol (dependencies, conflict resolution)
- We need per-agent configuration

**If NO**:
- Current monolithic design works fine
- Focus on CFG + taint tracking instead
- Skip P1 gaps #1, #2, #8

**Your call!** 🎯
