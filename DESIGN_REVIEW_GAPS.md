# CodeFusion Design Review: Gaps and Missing Components

**Date**: 2025-11-14
**Reviewer**: Analysis of proposed multi-agent KB construction design
**Status**: Comprehensive gap analysis for modular experimentation

---

## Executive Summary

The proposed design introduces a sophisticated multi-agent architecture for knowledge base construction with experimentation capabilities. While many foundational components exist (AgentRegistry, ExperimentRunner, MetricsCollector), there are **20 critical gaps** that need addressing for full implementation.

**Critical Missing Components**: 12
**Design Clarifications Needed**: 8
**Priority 1 (Blockers)**: 6
**Priority 2 (Important)**: 9
**Priority 3 (Nice-to-have)**: 5

---

## 🔴 PRIORITY 1: Critical Blockers

### 1. Agent Protocol/Interface Definition ⚠️

**Current State**:
- `cf/agents/registry.py:27` - AgentRegistry exists but no formal agent protocol
- Agents check for `name`, `get_capabilities()`, `register_tools()`, `is_available()`
- No enforced contract

**Missing**:
```python
# cf/agents/protocols.py - NEEDS EXPANSION

from typing import Protocol, Dict, List, Any, Optional
from abc import abstractmethod

class KnowledgeAgent(Protocol):
    """
    Protocol that all KB construction agents must implement.

    This defines the contract for pluggable agents.
    """

    # MISSING: Core lifecycle methods
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize agent with configuration"""
        pass

    @abstractmethod
    def build_knowledge(self, repo_path: str) -> BuildResult:
        """Build knowledge for repository"""
        pass

    @abstractmethod
    def update_knowledge(self, changes: List[FileChange]) -> UpdateResult:
        """Incrementally update knowledge"""
        pass

    @abstractmethod
    def validate_knowledge(self) -> ValidationResult:
        """Validate KB consistency"""
        pass

    # MISSING: Dependency declaration
    @abstractmethod
    def get_dependencies(self) -> List[str]:
        """
        Return list of agent names this agent depends on.
        E.g., DependencyAnalyzer depends on StructuralAnalyzer
        """
        pass

    # MISSING: Coordination methods
    @abstractmethod
    def can_run_parallel(self, other_agent: str) -> bool:
        """Can this agent run in parallel with another?"""
        pass

    @abstractmethod
    def on_conflict(self, node_id: str, other_agent: str) -> ConflictResolution:
        """
        Handle conflict when multiple agents update same node.
        Returns: MERGE, OVERRIDE, SKIP, ERROR
        """
        pass

    # MISSING: Resource management
    @abstractmethod
    def estimate_resources(self, file_count: int) -> ResourceEstimate:
        """Estimate memory/time/tokens for file count"""
        pass
```

**Impact**: Cannot coordinate multiple agents without this protocol.

**Recommendation**: Create comprehensive `KnowledgeAgentProtocol` class.

---

### 2. Agent Coordination & Orchestration ⚠️

**Current State**: No coordination layer for KB construction agents.

**Missing**:
```python
# cf/agents/kb/coordinator.py - DOES NOT EXIST

class KBBuildCoordinator:
    """
    Orchestrates multiple KB construction agents.

    Responsibilities:
    1. Determine execution order based on dependencies
    2. Decide parallel vs sequential execution
    3. Handle partial failures
    4. Coordinate incremental updates
    """

    def __init__(self, agents: List[KnowledgeAgent], registry: AgentRegistry):
        self.agents = agents
        self.registry = registry
        self.dependency_graph = self._build_dependency_graph()

    def _build_dependency_graph(self) -> DAG:
        """
        Build dependency graph from agent.get_dependencies()

        Example:
        StructuralAgent (no deps)
        ↓
        DependencyAgent (depends on StructuralAgent)
        ↓
        PatternAgent (depends on DependencyAgent)
        LifeOfXAgent (depends on DependencyAgent)
        ↓
        SemanticAgent (depends on StructuralAgent)
        """
        pass

    def build_knowledge_base(self, repo_path: str) -> BuildResult:
        """
        Execute KB build with proper ordering.

        Algorithm:
        1. Topological sort of dependency graph
        2. For each level:
           a. Run independent agents in parallel
           b. Wait for all to complete
           c. Handle conflicts
           d. Proceed to next level
        """
        pass

    def incremental_update(self, changes: List[FileChange]) -> UpdateResult:
        """
        Propagate changes through agent pipeline.

        Example: File changes → StructuralAgent → DependencyAgent → PatternAgent
        """
        pass
```

**Questions**:
- How do you handle circular dependencies?
- What's the conflict resolution strategy?
- How do you rollback on partial failure?

**Recommendation**: Implement DAG-based coordinator with topological sort.

---

### 3. Evaluation Dataset Format & Storage ⚠️

**Current State**:
- Eval files exist (`cf/evals/*.yaml`) but no formal schema
- No standard for "points" or grading

**Missing**:
```yaml
# Standard eval format - NOT DOCUMENTED

# cf/evals/schema.yaml
version: "1.0"
question:
  id: "q001"
  text: "How does authentication work?"
  type: "architectural"  # architectural, semantic, pattern, lifeofx
  difficulty: "medium"  # easy, medium, hard

reference_answer:
  text: |
    Authentication starts at the LoginController...
  key_components:
    - file: "apps/auth/controllers.py"
      line: 45
      relevance: 0.9
    - file: "apps/auth/models.py"
      line: 12
      relevance: 0.8

eval_criteria:
  grounding:
    points: 30
    requirements:
      - min_line_coverage: 0.15
      - min_path_accuracy: 0.8
      - min_code_blocks: 2

  accuracy:
    points: 40
    requirements:
      - mentions_login_controller: required
      - mentions_token_generation: required
      - correct_flow: true

  expressiveness:
    points: 30
    requirements:
      - min_word_count: 1500
      - has_sequence_diagram: optional
      - explains_security: required

# MISSING: Scoring logic
scoring:
  grounding_score = (criteria_met / total_criteria) * points
  accuracy_score = manual_eval or llm_eval
  expressiveness_score = weighted_average(requirements)

  total_score = grounding + accuracy + expressiveness
  max_score = 100

  grade = total_score / max_score
```

**Missing Components**:
1. Schema validation for eval datasets
2. Automatic grading for grounding/expressiveness
3. LLM-based grading for accuracy
4. Reference answer comparison logic
5. Point allocation framework

**Recommendation**: Create `cf/evals/schema.py` with dataclasses and validators.

---

### 4. LLM Task & Message Design ⚠️

**Current State**:
- `cf/llm/client.py` exists but no Message-based design
- No conversation history management

**Missing**:
```python
# cf/llm/task.py - EXISTS BUT INCOMPLETE

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Message:
    """Single message in conversation"""
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None  # For tool messages
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class LLMTask:
    """
    MISSING: Message-based design for LLM interactions

    Current LlmCompletion needs migration to this design.
    """

    def __init__(self, system_prompt: str):
        self.messages: List[Message] = [
            Message(role="system", content=system_prompt)
        ]
        self.max_history = 10  # Sliding window

    def add_user_message(self, content: str):
        """Add user message"""
        self.messages.append(Message(role="user", content=content))
        self._truncate_history()

    def add_assistant_message(self, content: str):
        """Add assistant message"""
        self.messages.append(Message(role="assistant", content=content))

    def add_tool_result(self, tool_name: str, result: Any):
        """Add tool execution result"""
        self.messages.append(Message(
            role="tool",
            name=tool_name,
            content=json.dumps(result)
        ))

    def _truncate_history(self):
        """
        MISSING: Smart history truncation

        Keep:
        - System prompt (always)
        - Recent N messages
        - Important tool results

        Strategies:
        1. Sliding window (keep last N)
        2. Summarization (LLM summarizes old messages)
        3. Importance-based (keep high-importance messages)
        """
        pass

    def get_token_count(self) -> int:
        """MISSING: Token counting for context window management"""
        pass

    def summarize_history(self) -> Message:
        """
        MISSING: Use LLM to summarize conversation history
        when context window fills up
        """
        pass
```

**Issue**: Current implementation lacks conversation management.

**Recommendation**: Migrate from `LlmCompletion` to `LLMTask` with Message design.

---

### 5. Control Flow Graph (CFG) Storage & Querying ⚠️

**Proposed**: Data flow analysis with CFG
**Current State**: No CFG extraction or storage

**Missing**:
```python
# cf/knowledge/structural/cfg_analyzer.py - DOES NOT EXIST

class ControlFlowAnalyzer:
    """
    MISSING: Extract and store Control Flow Graphs

    Needed for:
    - Data flow analysis
    - Taint tracking
    - Path exploration
    - Security analysis
    """

    def extract_cfg(self, function_ast: ast.FunctionDef) -> ControlFlowGraph:
        """Build CFG from function AST"""
        pass

    def store_cfg(self, cfg: ControlFlowGraph, function_id: str):
        """
        MISSING: How do you store CFG in Neo4j/SQLite?

        Options:
        1. Store as JSON blob in function node
        2. Create CFG nodes and edges in graph
        3. Separate CFG database

        Recommendation: Option 2 for queryability

        Nodes:
        (:CFGNode {function_id, block_id, type, code})

        Edges:
        (:CFGNode)-[:CFG_NEXT {condition}]->(:CFGNode)
        (:CFGNode)-[:CFG_BRANCH {branch_type}]->(:CFGNode)
        """
        pass

    def query_paths(
        self,
        function_id: str,
        from_var: str,
        to_var: str
    ) -> List[Path]:
        """
        MISSING: Query execution paths from variable to variable

        Example: "How does user_input reach database_query?"
        """
        pass
```

**Cypher Query Example** (missing):
```cypher
// Find all paths from variable definition to use
MATCH path = (start:CFGNode {var_def: 'user_input'})-[:CFG_NEXT*]->(end:CFGNode {var_use: 'db_query'})
WHERE start.function_id = 'authenticate'
RETURN path
```

**Recommendation**: Implement CFG extraction and graph storage.

---

### 6. Knowledge Base Consistency & Transactions ⚠️

**Issue**: Multiple agents updating KB concurrently → data corruption risk

**Missing**:
```python
# cf/knowledge/transaction.py - DOES NOT EXIST

class KBTransaction:
    """
    MISSING: Transaction support for KB updates

    Problem:
    - StructuralAgent creates Function node
    - DependencyAgent adds CALLS edges
    - SemanticAgent adds embedding
    - If SemanticAgent fails, KB is inconsistent

    Solution: Transactional updates with rollback
    """

    def __init__(self, kb_client):
        self.kb_client = kb_client
        self.operations = []
        self.committed = False

    def add_node(self, node_type: str, properties: Dict):
        """Queue node creation"""
        self.operations.append(('create_node', node_type, properties))

    def add_edge(self, from_id: str, to_id: str, edge_type: str):
        """Queue edge creation"""
        self.operations.append(('create_edge', from_id, to_id, edge_type))

    def commit(self) -> bool:
        """
        Execute all queued operations atomically.

        For Neo4j: Use Cypher transactions
        For SQLite: Use SQL transactions
        """
        try:
            self.kb_client.begin_transaction()
            for op in self.operations:
                self.kb_client.execute(op)
            self.kb_client.commit_transaction()
            self.committed = True
            return True
        except Exception as e:
            self.kb_client.rollback_transaction()
            return False

    def rollback(self):
        """Rollback all operations"""
        self.kb_client.rollback_transaction()


# Usage pattern:
def build_function_knowledge(func_ast, kb_client):
    txn = KBTransaction(kb_client)

    # Structural agent
    func_id = txn.add_node('Function', {'name': func_ast.name})

    # Dependency agent
    for call in func_ast.calls:
        txn.add_edge(func_id, call.target, 'CALLS')

    # Semantic agent
    embedding = generate_embedding(func_ast)
    txn.add_node('Embedding', {'function_id': func_id, 'vector': embedding})

    # Commit all or nothing
    if not txn.commit():
        logger.error("Failed to build function knowledge")
```

**Neo4j Support**: Already has transactions via `session.begin_transaction()`
**SQLite Support**: Has transactions via `BEGIN/COMMIT/ROLLBACK`

**Recommendation**: Implement transaction wrapper for consistency.

---

## 🟡 PRIORITY 2: Important Gaps

### 7. Tool Call Metrics & Cost Attribution

**Current State**:
- `cf/metrics/collector.py` tracks basic metrics
- `cf/tools/metrics.py` has tool-level tracking

**Missing**:
```python
# cf/tools/metrics.py - NEEDS ENHANCEMENT

class ToolMetrics:
    """MISSING: Per-tool cost attribution"""

    def record_tool_call(
        self,
        tool_name: str,
        agent_name: str,  # MISSING: Which agent called it?
        duration: float,
        tokens: int,
        cost: float,  # MISSING: Cost calculation
        success: bool
    ):
        """
        Record tool call with attribution.

        Enables answering:
        - Which agent uses the most tokens?
        - Which tools are most expensive?
        - Cost breakdown by query type
        """
        pass

    def get_cost_by_agent(self) -> Dict[str, float]:
        """MISSING: Cost breakdown by agent"""
        pass

    def get_cost_by_tool(self) -> Dict[str, float]:
        """MISSING: Cost breakdown by tool"""
        pass

    def estimate_query_cost(
        self,
        query_type: str,
        file_count: int
    ) -> CostEstimate:
        """
        MISSING: Predict cost before executing query

        Uses historical data to estimate cost
        """
        pass
```

**Recommendation**: Add cost attribution to metrics system.

---

### 8. Tracer Class with Hierarchy

**Current State**:
- `cf/trace/tracer.py` exists with basic tracing
- `cf/trace/langfuse_plugin.py` for Langfuse integration

**Missing**:
```python
# cf/trace/tracer.py - NEEDS ENHANCEMENT

class Tracer:
    """
    MISSING: Hierarchical span support

    Current implementation lacks:
    1. Parent-child span relationships
    2. Distributed tracing correlation
    3. Sampling strategy
    """

    def start_span(
        self,
        name: str,
        parent_span_id: Optional[str] = None,  # MISSING
        agent_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Span:
        """
        MISSING: Create child spans for nested operations

        Example hierarchy:
        supervisor_analyze (root)
        ├─ code_orchestrator_answer
        │  ├─ discovery_pipeline_discover
        │  ├─ analysis_pipeline_analyze (parallel)
        │  │  ├─ analyze_file_1
        │  │  ├─ analyze_file_2
        │  │  └─ analyze_file_3
        │  ├─ synthesis_pipeline_synthesize
        │  └─ validation_pipeline_validate
        ├─ llm_call_gpt5 (multiple)
        └─ kb_query_semantic_search (multiple)
        """
        pass

    def end_span(self, span: Span, success: bool = True):
        """End span and propagate to parent"""
        pass

    def get_trace_tree(self, root_span_id: str) -> TraceTree:
        """
        MISSING: Reconstruct hierarchical trace

        Returns tree structure for visualization
        """
        pass
```

**Recommendation**: Add parent-child span relationships.

---

### 9. Incremental Update Coordination

**Current State**:
- `cf/knowledge/incremental/file_watcher.py` detects changes
- `cf/knowledge/incremental/differential.py` applies changes

**Missing**:
```python
# cf/knowledge/incremental/coordinator.py - DOES NOT EXIST

class IncrementalUpdateCoordinator:
    """
    MISSING: Coordinate incremental updates across agents

    Problem:
    - File changed → need to update Structural + Dependency + Semantic + Pattern
    - What if Structural succeeds but Semantic fails?
    - How do you maintain consistency?
    """

    def propagate_changes(
        self,
        file_changes: List[FileChange],
        agents: List[KnowledgeAgent]
    ) -> UpdateResult:
        """
        Algorithm:
        1. Determine affected agents (based on file type, change type)
        2. Execute in dependency order
        3. Use transactions for consistency
        4. Rollback on failure

        Example:
        - Python file modified
        - Run: StructuralAgent → DependencyAgent → PatternAgent
        - Skip: DocumentationAgent (only for .md files)
        """
        pass

    def compute_affected_agents(
        self,
        changes: List[FileChange]
    ) -> List[str]:
        """
        MISSING: Which agents need to run for these changes?

        Rules:
        - Code change → Structural, Dependency, Semantic, Pattern
        - Test change → Structural, TestAnalysis
        - Doc change → Documentation
        - Config change → Structural
        """
        pass
```

**Recommendation**: Implement smart incremental update routing.

---

### 10. Query Planner for Multi-Layer KB

**Current State**: No unified query planner

**Missing**:
```python
# cf/knowledge/query_planner.py - DOES NOT EXIST

class KBQueryPlanner:
    """
    MISSING: Optimize queries across KB layers

    Problem: Query might need data from multiple layers
    - "Find singleton patterns" → Structural + Pattern layers
    - "Find similar authentication code" → Semantic + Structural layers
    - "Trace login flow" → Life-of-X + Dependency layers

    Solution: Query planner that:
    1. Analyzes query requirements
    2. Determines which layers to query
    3. Optimizes query order
    4. Caches intermediate results
    """

    def plan_query(self, query: str) -> QueryPlan:
        """
        Create execution plan for query.

        Example:
        Query: "Find all factory pattern implementations"

        Plan:
        1. Pattern Layer: Get factory pattern instances
        2. For each instance:
           a. Structural Layer: Get class details
           b. Semantic Layer: Get similar classes
        3. Aggregate results
        """
        pass

    def execute_plan(self, plan: QueryPlan) -> QueryResult:
        """Execute query plan with caching"""
        pass
```

**Recommendation**: Create query planner for multi-layer optimization.

---

### 11. Agent Configuration Schema

**Current State**: `cf/configs/config.yaml` has global config

**Missing**:
```yaml
# cf/configs/config.yaml - ADD AGENT SECTION

agents:
  # Existing config...

  # MISSING: Per-agent configuration
  knowledge_agents:
    structural_analyzer:
      enabled: true
      parallel_workers: 10
      languages: ["python", "javascript", "typescript"]
      extract_docstrings: true
      extract_type_hints: true

    dependency_analyzer:
      enabled: true
      depends_on: ["structural_analyzer"]
      max_depth: 10
      detect_cycles: true
      analyze_imports: true
      analyze_calls: true
      analyze_inheritance: true

    semantic_analyzer:
      enabled: true
      depends_on: ["structural_analyzer"]
      embedding_model: "all-MiniLM-L6-v2"
      batch_size: 100
      cache_embeddings: true

    pattern_recognizer:
      enabled: true
      depends_on: ["dependency_analyzer"]
      detect_design_patterns: true
      detect_anti_patterns: true
      confidence_threshold: 0.7
      llm_validation: true

    lifeofx_tracer:
      enabled: true
      depends_on: ["dependency_analyzer"]
      max_trace_depth: 20
      max_paths: 10
      detect_long_chains: true

    data_flow_analyzer:
      enabled: false  # Experimental
      depends_on: ["structural_analyzer"]
      taint_tracking: true
      security_analysis: true
```

**Recommendation**: Add per-agent configuration section.

---

### 12. Reference Answer Comparison Logic

**Current State**: No implementation for comparing generated answers to reference

**Missing**:
```python
# cf/evals/comparator.py - DOES NOT EXIST

class AnswerComparator:
    """
    MISSING: Compare generated answer to reference answer

    Used for:
    1. Automatic eval grading
    2. LLM feedback on improvements
    """

    def compare_answers(
        self,
        generated: str,
        reference: str,
        criteria: EvalCriteria
    ) -> ComparisonResult:
        """
        Compare answers on multiple dimensions.

        Returns:
        - Similarity score (semantic, BLEU, ROUGE)
        - Missing components
        - Extra components
        - Grounding comparison
        - Suggestions for improvement
        """
        pass

    def get_llm_feedback(
        self,
        generated: str,
        reference: str,
        question: str
    ) -> LLMFeedback:
        """
        MISSING: Ask LLM what could be improved

        Prompt:
        "Given this question: {question}
         Generated answer: {generated}
         Reference answer: {reference}

         What could be improved in the generated answer to make it closer to the reference?
         What key points are missing?
         What is included that shouldn't be?"
        """
        pass

    def extract_key_components(self, answer: str) -> List[Component]:
        """
        MISSING: Extract key components mentioned

        E.g., file paths, class names, function names, concepts
        """
        pass

    def compute_grounding_delta(
        self,
        generated: str,
        reference: str
    ) -> GroundingDelta:
        """
        MISSING: Compare grounding quality

        Returns:
        - generated_line_coverage vs reference_line_coverage
        - generated_path_accuracy vs reference_path_accuracy
        - generated_code_blocks vs reference_code_blocks
        """
        pass
```

**Recommendation**: Implement multi-dimensional answer comparison.

---

### 13. Conflict Resolution Strategy

**Current State**: No conflict handling between agents

**Missing**:
```python
# cf/agents/kb/conflict_resolver.py - DOES NOT EXIST

class ConflictResolver:
    """
    MISSING: Handle conflicts when multiple agents update same node

    Scenarios:
    1. StructuralAgent sets function complexity = 5
       PatternAgent sets function complexity = 7 (more detailed analysis)
       → Which value to keep?

    2. DependencyAgent adds edge: func1 CALLS func2
       SemanticAgent adds edge: func1 SIMILAR_TO func2
       → No conflict (different edge types)

    3. PatternAgent: class X is Singleton (confidence 0.8)
       LLMAgent: class X is Factory (confidence 0.6)
       → Conflict! Keep higher confidence? Both? Flag for review?
    """

    def resolve_property_conflict(
        self,
        node_id: str,
        property_name: str,
        agent_a: str,
        value_a: Any,
        agent_b: str,
        value_b: Any
    ) -> ConflictResolution:
        """
        Resolve property conflicts.

        Strategies:
        1. Priority-based: Agent priority order
        2. Confidence-based: Higher confidence wins
        3. Merge: Combine values (e.g., average numbers)
        4. Flag: Mark as conflicting, require manual resolution
        5. Latest-wins: Most recent update wins
        """
        pass

    def get_agent_priority(self, agent_name: str) -> int:
        """
        MISSING: Agent priority configuration

        Example:
        StructuralAgent (priority 1, deterministic)
        DependencyAgent (priority 2, deterministic)
        PatternAgent (priority 5, heuristic)
        SemanticAgent (priority 7, LLM-based)

        Lower priority = higher authority
        """
        pass
```

**Recommendation**: Implement configurable conflict resolution.

---

### 14. Data Flow Analysis Storage Schema

**Proposed**: Taint analysis, data flow graphs
**Current State**: No storage schema defined

**Missing Neo4j Schema**:
```cypher
# MISSING: Data flow nodes and edges

# Nodes
(:DataFlowNode {
  id: str,
  function_id: str,
  variable: str,
  definition_line: int,
  type: str  # SOURCE, SINK, TRANSFORMER
})

(:TaintSource {
  variable: str,
  source_type: str  # USER_INPUT, FILE_READ, NETWORK
})

(:TaintSink {
  variable: str,
  sink_type: str  # SQL_QUERY, COMMAND_EXEC, FILE_WRITE
})

# Edges
(:DataFlowNode)-[:FLOWS_TO {via_operation: str}]->(:DataFlowNode)
(:TaintSource)-[:TAINTS]->(:DataFlowNode)
(:DataFlowNode)-[:REACHES]->(:TaintSink)

# Queries
// Find all taint paths from user input to SQL query
MATCH path = (source:TaintSource {source_type: 'USER_INPUT'})-[:TAINTS|FLOWS_TO*]->(sink:TaintSink {sink_type: 'SQL_QUERY'})
RETURN path
```

**Recommendation**: Define data flow schema for Neo4j/SQLite.

---

### 15. Documentation Synthesis Agent Implementation

**Proposed**: Documentation Synthesis Agent
**Current State**: Mentioned but not detailed

**Missing**:
```python
# cf/agents/kb/documentation_agent.py - PLACEHOLDER ONLY

class DocumentationSynthesisAgent(KnowledgeAgent):
    """
    MISSING: Full implementation

    Responsibilities:
    1. Extract documentation from code comments
    2. Parse README, docs/ directory
    3. Link documentation to code nodes
    4. Generate architectural diagrams
    5. Create decision records
    """

    def extract_inline_docs(self, source_code: str) -> List[DocString]:
        """Extract docstrings, comments, type hints"""
        pass

    def parse_markdown_docs(self, doc_path: str) -> DocumentationGraph:
        """
        Parse markdown documentation.

        Extract:
        - Headers → sections
        - Code blocks → examples
        - Links → references
        - Diagrams → visual representations
        """
        pass

    def link_docs_to_code(
        self,
        docs: DocumentationGraph,
        code_kb: StructuralKB
    ) -> List[DocumentationLink]:
        """
        MISSING: Link documentation mentions to code nodes

        Example:
        README mentions "AuthController" → Link to cf/controllers/auth.py:45
        """
        pass

    def generate_architecture_diagram(
        self,
        module: str
    ) -> Diagram:
        """
        MISSING: Generate architecture diagrams from KB

        Use KB structure to create:
        - Component diagrams
        - Sequence diagrams
        - Class diagrams

        Output: Mermaid, PlantUML, or SVG
        """
        pass
```

**Recommendation**: Full implementation with diagram generation.

---

## 🟢 PRIORITY 3: Nice-to-Have

### 16. Statistical Significance Testing

**Current State**: `cf/experiments/experiment_runner.py` compares variants

**Missing**:
```python
# cf/experiments/statistics.py - DOES NOT EXIST

class StatisticalAnalyzer:
    """
    MISSING: Statistical significance testing

    Problem: Is variant A actually better than B, or just random chance?
    """

    def t_test(
        self,
        variant_a_scores: List[float],
        variant_b_scores: List[float]
    ) -> TTestResult:
        """
        Perform t-test to determine if difference is significant.

        Returns:
        - p_value: Probability difference is due to chance
        - significant: True if p < 0.05
        - effect_size: Cohen's d
        """
        pass

    def min_sample_size(
        self,
        expected_difference: float,
        power: float = 0.8
    ) -> int:
        """
        MISSING: How many queries needed for reliable results?

        Power analysis to determine minimum sample size
        """
        pass
```

**Recommendation**: Add scipy/numpy for statistical tests.

---

### 17. KB Versioning & Rollback

**Current State**: No versioning support

**Missing**:
```python
# cf/knowledge/versioning.py - DOES NOT EXIST

class KBVersionControl:
    """
    MISSING: Version control for knowledge base

    Use cases:
    1. Rollback after bad update
    2. Compare KB before/after agent changes
    3. A/B test different KB build strategies
    """

    def create_snapshot(self, label: str) -> SnapshotID:
        """Create KB snapshot"""
        pass

    def rollback_to(self, snapshot_id: SnapshotID):
        """Rollback KB to previous state"""
        pass

    def diff_snapshots(
        self,
        snapshot_a: SnapshotID,
        snapshot_b: SnapshotID
    ) -> KBDiff:
        """Compare two KB versions"""
        pass
```

**Recommendation**: Implement for production use.

---

### 18. Real-time Metrics Dashboard

**Current State**: Metrics collected but no visualization

**Missing**:
```python
# cf/metrics/dashboard.py - DOES NOT EXIST

class MetricsDashboard:
    """
    MISSING: Real-time metrics visualization

    Features:
    - Live token usage
    - Cost tracking
    - Agent performance
    - Error rates
    - Query latency
    """

    def start_server(self, port: int = 8080):
        """Start web dashboard"""
        pass

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get current metrics for UI"""
        pass
```

**Recommendation**: Build with Streamlit or Gradio.

---

### 19. Distributed Agent Execution

**Current State**: Single-process execution

**Missing**:
```python
# cf/agents/distributed.py - DOES NOT EXIST

class DistributedAgentExecutor:
    """
    MISSING: Distribute agent execution across machines

    For very large codebases (100K+ files):
    - Shard files across workers
    - Parallel KB construction
    - Aggregate results
    """

    def distribute_work(
        self,
        files: List[str],
        agent: KnowledgeAgent,
        workers: int
    ) -> List[Future]:
        """Distribute work using Ray or Celery"""
        pass
```

**Recommendation**: Use Ray for distributed execution.

---

### 20. Security & Privacy Layer

**Current State**: No security features

**Missing**:
```python
# cf/security/scanner.py - DOES NOT EXIST

class SecurityScanner:
    """
    MISSING: Security and privacy features

    1. PII detection in code/comments
    2. Secret detection (API keys, passwords)
    3. Taint analysis for security vulnerabilities
    4. Access control for different KB layers
    """

    def detect_pii(self, code: str) -> List[PIIMatch]:
        """Detect personally identifiable information"""
        pass

    def detect_secrets(self, code: str) -> List[Secret]:
        """Detect hardcoded secrets"""
        pass

    def analyze_security_risks(
        self,
        function_id: str
    ) -> List[SecurityRisk]:
        """
        Analyze security risks using data flow.

        Example: User input flows to SQL query without sanitization
        """
        pass
```

**Recommendation**: Integrate with existing security tools.

---

## 📊 Gap Summary Table

| # | Gap | Priority | Complexity | Existing Code | Recommendation |
|---|-----|----------|------------|---------------|----------------|
| 1 | Agent Protocol | P1 | Medium | Partial (protocols.py exists) | Expand protocol |
| 2 | Agent Coordinator | P1 | High | None | Implement DAG coordinator |
| 3 | Eval Dataset Schema | P1 | Medium | YAML files exist | Add schema validation |
| 4 | LLM Task Design | P1 | Medium | task.py exists | Migrate to Message design |
| 5 | CFG Storage | P1 | High | None | Implement CFG extraction |
| 6 | KB Transactions | P1 | Medium | DB clients exist | Add transaction wrapper |
| 7 | Tool Metrics | P2 | Low | metrics.py exists | Add cost attribution |
| 8 | Tracer Hierarchy | P2 | Medium | tracer.py exists | Add span hierarchy |
| 9 | Incremental Updates | P2 | High | Partial (file_watcher exists) | Add coordinator |
| 10 | Query Planner | P2 | High | None | Implement planner |
| 11 | Agent Config | P2 | Low | config.yaml exists | Add agent section |
| 12 | Answer Comparison | P2 | Medium | None | Implement comparator |
| 13 | Conflict Resolution | P2 | Medium | None | Implement resolver |
| 14 | Data Flow Schema | P2 | High | None | Define schema |
| 15 | Docs Agent | P2 | High | Placeholder exists | Full implementation |
| 16 | Statistics | P3 | Low | None | Add scipy |
| 17 | KB Versioning | P3 | Medium | None | Implement snapshots |
| 18 | Dashboard | P3 | Medium | None | Build with Streamlit |
| 19 | Distributed Exec | P3 | High | None | Use Ray |
| 20 | Security | P3 | Medium | None | Integrate security tools |

---

## 🎯 Implementation Roadmap

### Phase 1: Foundation (P1 items)
1. **Week 1-2**: Agent Protocol & Coordinator
2. **Week 2-3**: LLM Task Migration
3. **Week 3-4**: Eval Dataset Schema & Comparison
4. **Week 4-5**: KB Transactions & CFG Storage

### Phase 2: Enhancement (P2 items)
5. **Week 6-7**: Tool Metrics & Tracer Hierarchy
6. **Week 7-8**: Incremental Update Coordination
7. **Week 8-9**: Query Planner & Conflict Resolution
8. **Week 9-10**: Data Flow Analysis & Documentation Agent

### Phase 3: Production (P3 items)
9. **Week 11-12**: Statistics, Versioning, Dashboard
10. **Week 12+**: Distributed Execution, Security (as needed)

---

## ✅ What's Already Well-Designed

**Strengths of current design:**
1. ✅ AgentRegistry - Solid plugin architecture
2. ✅ ExperimentRunner - Good A/B testing framework
3. ✅ MetricsCollector - Comprehensive metrics tracking
4. ✅ Pipeline Architecture - Clean separation of concerns
5. ✅ Multi-tier LLM - Cost-effective strategy
6. ✅ Validation Feedback - Anti-hallucination measures
7. ✅ 6-Layer KB - Well-structured knowledge organization

---

## 🚀 Quick Wins

**Implement these first for immediate value:**
1. **Agent Configuration Schema** (2 days) - Enables experimentation
2. **Tool Cost Attribution** (3 days) - Answers "does AST help?" questions
3. **Answer Comparator** (1 week) - Enables automatic eval grading
4. **Agent Protocol Expansion** (1 week) - Unblocks multi-agent coordination

---

## 📝 Questions to Resolve

1. **Agent Dependencies**: Linear chain or DAG? Can Pattern + Semantic run in parallel?
2. **Conflict Resolution**: Priority-based or confidence-based default?
3. **CFG Storage**: Nodes in graph DB or JSON blobs?
4. **Transaction Scope**: Per-agent or per-file?
5. **Eval Grading**: Fully automated or human-in-the-loop for accuracy?
6. **KB Versioning**: Git-like diffs or snapshot-based?
7. **Distributed Execution**: When is it needed? (codebase size threshold)
8. **Security Priority**: Must-have or nice-to-have?

---

## 📚 References

- Current AgentRegistry: `cf/agents/registry.py`
- Current ExperimentRunner: `cf/experiments/experiment_runner.py`
- Current MetricsCollector: `cf/metrics/collector.py`
- Current Tracer: `cf/trace/tracer.py`
- Proposed Design: (User-provided design document)

---

**Next Steps**: Prioritize P1 gaps and create implementation tickets.
