# God Class Refactoring Plan

**Status**: Ready for Implementation
**Estimated Effort**: 2-3 weeks
**Priority**: HIGH (Critical for long-term maintainability)

---

## Executive Summary

The CodeFusion codebase contains 6 "god classes" that violate the Single Responsibility Principle (SRP). While the current architecture is sound, these large classes reduce maintainability, testability, and make the codebase harder to understand.

This plan outlines a systematic approach to refactor these classes into smaller, focused components using established design patterns.

---

## God Classes Identified

| File | Lines | Responsibilities | Severity |
|------|-------|------------------|----------|
| `supervisor.py` | 1,118 | Agent coordination, synthesis, caching, state management, multi-pass logic | **CRITICAL** |
| `synthesis.py` | 1,064 | Prompt generation, validation, cross-file analysis, pattern detection, execution tracing | **HIGH** |
| `validation.py` | 889 | 6 validation types, fact verification, pattern matching, LLM verification | **HIGH** |
| `code_orchestrator.py` | 781 | State machine, file discovery, analysis, synthesis, validation coordination | MEDIUM |
| `query_engine.py` | 573 | 7 discovery strategies, scoring, ranking | MEDIUM |
| `discovery.py` | Large | Multiple discovery implementations | MEDIUM |

---

## Refactoring Strategy

### Phase 1: Supervisor.py (Week 1)

**Current Structure** (1,118 lines):
```python
class SupervisorAgent:
    # Agent coordination (200 lines)
    # Multi-pass logic (300 lines)
    # Synthesis orchestration (250 lines)
    # Caching (100 lines)
    # State management (200 lines)
    # Error handling (68 lines)
```

**Target Structure**:
```python
# cf/agents/supervisor/coordinator.py
class AgentCoordinator:
    """Manages agent selection and execution"""
    def select_agents(question) -> List[str]
    def execute_agents(agents, question) -> Dict

# cf/agents/supervisor/pass_manager.py
class PassManager:
    """Handles multi-pass analysis logic"""
    def should_continue(pass_num, insights) -> bool
    def coordinate_pass(pass_num, question) -> PassResult
    def aggregate_passes() -> Dict

# cf/agents/supervisor/synthesis_orchestrator.py
class SynthesisOrchestrator:
    """Orchestrates final synthesis"""
    def prepare_synthesis_data(insights) -> Dict
    def synthesize_with_llm(data, question) -> Dict
    def format_final_result(synthesis) -> Dict

# cf/agents/supervisor/cache_manager.py
class CacheManager:
    """Manages semantic caching"""
    def get_cached_result(question) -> Optional[Dict]
    def cache_result(question, result) -> None
    def _generate_cache_key(question) -> str

# cf/agents/supervisor/supervisor.py (THIN ORCHESTRATOR)
class SupervisorAgent:
    """Main coordinator - delegates to managers"""
    def __init__(self):
        self.agent_coordinator = AgentCoordinator(...)
        self.pass_manager = PassManager(...)
        self.synthesis_orchestrator = SynthesisOrchestrator(...)
        self.cache_manager = CacheManager(...)

    def analyze(self, question):
        # Thin delegation logic only
        cached = self.cache_manager.get_cached_result(question)
        if cached:
            return cached

        agents = self.agent_coordinator.select_agents(question)
        results = self.agent_coordinator.execute_agents(agents, question)

        synthesis = self.synthesis_orchestrator.synthesize(results)

        self.cache_manager.cache_result(question, synthesis)
        return synthesis
```

**Refactoring Steps**:
1. Extract `CacheManager` (simplest, 100 lines)
2. Extract `AgentCoordinator` (200 lines)
3. Extract `PassManager` (300 lines)
4. Extract `SynthesisOrchestrator` (250 lines)
5. Refactor main `SupervisorAgent` to delegate (150 lines remaining)
6. Update tests for each extracted class

**Benefits**:
- Each class has single responsibility
- Easier to test in isolation
- Can swap implementations (e.g., different cache backends)
- Clearer understanding of supervisor flow

---

### Phase 2: Synthesis.py (Week 2)

**Current Structure** (1,064 lines):
```python
class SynthesisPipeline:
    # Prompt generation (200 lines)
    # Cross-file analysis (250 lines)
    # Pattern detection integration (150 lines)
    # Execution tracing integration (150 lines)
    # Test insights integration (100 lines)
    # Validation integration (150 lines)
    # LLM interaction (64 lines)
```

**Target Structure** (Strategy Pattern):
```python
# cf/agents/pipelines/synthesis/strategies/base.py
class SynthesisStrategy(ABC):
    @abstractmethod
    def synthesize(self, file_summaries, question) -> Dict:
        pass

# cf/agents/pipelines/synthesis/strategies/narrative_strategy.py
class NarrativeStrategy(SynthesisStrategy):
    """Generates "Life of X" technical narratives"""
    def synthesize(self, file_summaries, question) -> Dict:
        # Standard synthesis logic

# cf/agents/pipelines/synthesis/strategies/pattern_enhanced_strategy.py
class PatternEnhancedStrategy(SynthesisStrategy):
    """Adds pattern detection to synthesis"""
    def synthesize(self, file_summaries, question) -> Dict:
        patterns = self._detect_patterns(file_summaries)
        narrative = self._generate_with_patterns(patterns)
        return narrative

# cf/agents/pipelines/synthesis/strategies/execution_tracing_strategy.py
class ExecutionTracingStrategy(SynthesisStrategy):
    """Adds execution path tracing to synthesis"""
    def synthesize(self, file_summaries, question) -> Dict:
        execution_paths = self._trace_paths(file_summaries)
        narrative = self._generate_with_paths(execution_paths)
        return narrative

# cf/agents/pipelines/synthesis/analyzer.py
class CrossFileAnalyzer:
    """Analyzes relationships across files"""
    def analyze(self, file_summaries) -> Dict:
        shared_abstractions = self._find_shared_abstractions()
        dependencies = self._infer_dependencies()
        data_flow = self._analyze_data_flow()
        return {
            'shared_abstractions': shared_abstractions,
            'dependencies': dependencies,
            'data_flow': data_flow
        }

# cf/agents/pipelines/synthesis/synthesis_pipeline.py (COORDINATOR)
class SynthesisPipeline:
    """Coordinates synthesis strategies"""
    def __init__(self, config, llm):
        self.strategies = {
            'narrative': NarrativeStrategy(llm),
            'pattern_enhanced': PatternEnhancedStrategy(llm),
            'execution_tracing': ExecutionTracingStrategy(llm)
        }
        self.cross_file_analyzer = CrossFileAnalyzer()

    def synthesize(self, file_summaries, question):
        # Analyze cross-file relationships
        relationships = self.cross_file_analyzer.analyze(file_summaries)

        # Select strategy based on question type
        strategy = self._select_strategy(question)

        # Synthesize with selected strategy
        result = strategy.synthesize(file_summaries, question, relationships)

        return result
```

**Refactoring Steps**:
1. Extract `CrossFileAnalyzer` (250 lines)
2. Create base `SynthesisStrategy` abstract class
3. Extract `NarrativeStrategy` (core logic)
4. Extract `PatternEnhancedStrategy` (pattern detection)
5. Extract `ExecutionTracingStrategy` (execution paths)
6. Refactor main `SynthesisPipeline` to coordinate strategies (200 lines)
7. Update tests for each strategy

**Benefits**:
- Easy to add new synthesis strategies
- Each strategy can be tested independently
- Can compose strategies (e.g., pattern + execution tracing)
- Clear separation between cross-file analysis and synthesis

---

### Phase 3: Validation.py (Week 2-3)

**Current Structure** (889 lines):
```python
class ValidationPipeline:
    # Line number validation (100 lines)
    # File path accuracy (150 lines)
    # Grounding check (200 lines)
    # File hallucination detection (150 lines)
    # Word count validation (50 lines)
    # Fact verification (239 lines)
```

**Target Structure** (Validator Pattern):
```python
# cf/agents/pipelines/validation/validators/base.py
class Validator(ABC):
    @abstractmethod
    def validate(self, answer, context) -> ValidationResult:
        pass

@dataclass
class ValidationResult:
    valid: bool
    issues: List[ValidationIssue]
    score: float
    details: Dict[str, Any]

# cf/agents/pipelines/validation/validators/line_number_validator.py
class LineNumberValidator(Validator):
    """Validates line number references are within bounds"""
    def validate(self, answer, context) -> ValidationResult:
        # Extract file+line pairs
        # Validate against actual file lengths
        # Return validation result

# cf/agents/pipelines/validation/validators/file_path_validator.py
class FilePathValidator(Validator):
    """Validates file paths match analyzed files"""
    def validate(self, answer, context) -> ValidationResult:
        # Extract file references
        # Check against analyzed file list
        # Flag any hallucinations

# cf/agents/pipelines/validation/validators/grounding_validator.py
class GroundingValidator(Validator):
    """Validates claims are grounded in code"""
    def validate(self, answer, context) -> ValidationResult:
        # Check references have code backing
        # Calculate grounding score

# cf/agents/pipelines/validation/validators/fact_validator.py
class FactValidator(Validator):
    """Verifies facts match actual code"""
    def validate(self, answer, context) -> ValidationResult:
        # Extract claims with line references
        # Read actual code at those lines
        # Verify claims match reality

# cf/agents/pipelines/validation/validators/word_count_validator.py
class WordCountValidator(Validator):
    """Validates narrative length is appropriate"""
    def validate(self, answer, context) -> ValidationResult:
        # Check word count proportional to file count

# cf/agents/pipelines/validation/validators/hallucination_detector.py
class HallucinationDetector(Validator):
    """Detects file hallucinations (CRITICAL)"""
    def validate(self, answer, context) -> ValidationResult:
        # Extract all file references
        # Flag any NOT in analyzed set
        # Check common hallucination patterns

# cf/agents/pipelines/validation/validation_pipeline.py (COORDINATOR)
class ValidationPipeline:
    """Coordinates validation checks"""
    def __init__(self, config):
        self.validators = [
            LineNumberValidator(config),
            FilePathValidator(config),
            GroundingValidator(config),
            HallucinationDetector(config),  # CRITICAL first
            WordCountValidator(config),
            FactValidator(config)  # Expensive, run last
        ]

    def validate(self, answer, file_summaries):
        context = {'file_summaries': file_summaries, ...}

        all_issues = []
        scores = {}

        for validator in self.validators:
            result = validator.validate(answer, context)
            all_issues.extend(result.issues)
            scores[validator.name] = result.score

            # Early exit if critical validation fails
            if not result.valid and validator.is_critical:
                break

        return ValidationResult(
            valid=len([i for i in all_issues if i.severity == 'error']) == 0,
            issues=all_issues,
            scores=scores
        )
```

**Refactoring Steps**:
1. Create base `Validator` abstract class
2. Extract `HallucinationDetector` (150 lines) - **MOST CRITICAL**
3. Extract `LineNumberValidator` (100 lines)
4. Extract `FilePathValidator` (150 lines)
5. Extract `GroundingValidator` (200 lines)
6. Extract `FactValidator` (239 lines)
7. Extract `WordCountValidator` (50 lines)
8. Refactor main `ValidationPipeline` to coordinate (100 lines)
9. Update tests for each validator

**Benefits**:
- Each validator can be tested independently
- Easy to add new validators
- Can configure which validators run
- Clear validation priority (critical validators first)
- Can run validators in parallel for performance

---

### Phase 4: Remaining Classes (Week 3)

**code_orchestrator.py** (781 lines):
Already has reasonable structure with state machine. Minor cleanup:
- Extract file discovery into `DiscoveryCoordinator` (100 lines)
- Extract analysis into `AnalysisCoordinator` (150 lines)
- Keep state machine in main class (400 lines is acceptable)

**query_engine.py** (573 lines):
Already using strategy pattern well. Minor cleanup:
- Extract each strategy into separate file
- Keep main coordinator (200 lines is acceptable)

**discovery.py**:
- Split into separate strategy files
- Keep main coordinator

---

## Testing Strategy

### Unit Tests
Each extracted class gets its own test file:
```
tests/agents/supervisor/
├── test_agent_coordinator.py
├── test_pass_manager.py
├── test_synthesis_orchestrator.py
└── test_cache_manager.py

tests/agents/pipelines/synthesis/
├── test_narrative_strategy.py
├── test_pattern_enhanced_strategy.py
├── test_execution_tracing_strategy.py
└── test_cross_file_analyzer.py

tests/agents/pipelines/validation/
├── test_line_number_validator.py
├── test_file_path_validator.py
├── test_grounding_validator.py
├── test_hallucination_detector.py
├── test_fact_validator.py
└── test_word_count_validator.py
```

### Integration Tests
Keep existing integration tests, update paths:
```python
# Test full supervisor flow
def test_supervisor_full_analysis():
    supervisor = SupervisorAgent(config)
    result = supervisor.analyze("How does authentication work?")
    assert result['success']
    assert len(result['narrative']) > 500

# Test full synthesis flow
def test_synthesis_full_pipeline():
    synthesis = SynthesisPipeline(config, llm)
    result = synthesis.synthesize(file_summaries, question)
    assert result['narrative_type'] == 'life_of_x'

# Test full validation flow
def test_validation_full_pipeline():
    validation = ValidationPipeline(config)
    result = validation.validate(answer, file_summaries)
    assert result.valid or len(result.issues) > 0
```

---

## Migration Strategy

### Backward Compatibility
Maintain old interfaces during migration:
```python
# cf/agents/supervisor.py
class SupervisorAgent:
    """
    Main coordinator - REFACTORED into modular components.

    Old interface preserved for backward compatibility.
    """
    def __init__(self, repo_path, config):
        # New modular implementation
        self.agent_coordinator = AgentCoordinator(...)
        self.pass_manager = PassManager(...)
        # ... but old interface still works

    def analyze(self, question):
        # Delegates to new components
        return self._new_analyze_impl(question)
```

### Feature Flags
Use config to enable/disable refactored components:
```yaml
# config.yaml
refactoring:
  use_modular_supervisor: true  # Enable refactored supervisor
  use_strategy_synthesis: true  # Enable strategy-based synthesis
  use_validator_pipeline: true  # Enable validator pattern
```

### Gradual Rollout
1. Week 1: Implement + test `SupervisorAgent` refactoring
2. Week 2: Implement + test `SynthesisPipeline` refactoring
3. Week 3: Implement + test `ValidationPipeline` refactoring
4. Week 4: Production testing + monitoring

---

## Metrics & Success Criteria

### Before Refactoring
```
supervisor.py:    1,118 lines, 7 responsibilities
synthesis.py:     1,064 lines, 6 responsibilities
validation.py:      889 lines, 6 responsibilities
```

### After Refactoring Target
```
supervisor/
  supervisor.py:       150 lines (orchestrator)
  agent_coordinator.py: 200 lines
  pass_manager.py:     300 lines
  synthesis_orchestrator.py: 250 lines
  cache_manager.py:    100 lines

synthesis/
  synthesis_pipeline.py: 200 lines (coordinator)
  strategies/
    narrative_strategy.py: 300 lines
    pattern_enhanced_strategy.py: 200 lines
    execution_tracing_strategy.py: 200 lines
  analyzer.py: 250 lines

validation/
  validation_pipeline.py: 100 lines (coordinator)
  validators/
    hallucination_detector.py: 150 lines
    line_number_validator.py: 100 lines
    file_path_validator.py: 150 lines
    grounding_validator.py: 200 lines
    fact_validator.py: 239 lines
    word_count_validator.py: 50 lines
```

### Success Metrics
- ✅ No file > 500 lines
- ✅ Each class has single responsibility
- ✅ Test coverage ≥ 80% for each extracted class
- ✅ All existing tests still pass
- ✅ No performance regression (< 5% slower)
- ✅ Maintainability Index improved (reduced complexity)

---

## Risk Mitigation

### Risks
1. **Breaking existing functionality** - Extensive testing required
2. **Performance regression** - Monitor after each refactoring
3. **Increased complexity** - More files to navigate
4. **Backward compatibility** - Must maintain old interfaces

### Mitigations
1. Comprehensive test suite before starting
2. Performance benchmarks before/after each phase
3. Clear documentation and directory structure
4. Maintain old interfaces, deprecate gradually
5. Feature flags to enable/disable refactored components
6. Rollback plan for each phase

---

## Estimated Timeline

| Phase | Task | Effort | Timeline |
|-------|------|--------|----------|
| **Phase 1** | Extract supervisor components | 5 days | Week 1 |
| | Unit tests for each component | 2 days | Week 1 |
| **Phase 2** | Extract synthesis strategies | 5 days | Week 2 |
| | Unit tests for strategies | 2 days | Week 2 |
| **Phase 3** | Extract validation validators | 4 days | Week 2-3 |
| | Unit tests for validators | 2 days | Week 3 |
| **Phase 4** | Cleanup remaining classes | 2 days | Week 3 |
| | Integration testing | 2 days | Week 3 |
| **Total** | | **24 days** | **3 weeks** |

---

## Next Steps

1. **This Week**: Complete remaining quick wins (magic numbers, duplicate code)
2. **Next Week**: Start Phase 1 (Supervisor refactoring)
3. **Following 2 Weeks**: Complete Phases 2-4
4. **Post-Refactoring**: Update documentation, celebrate success!

---

## Conclusion

This refactoring will significantly improve:
- **Maintainability**: Smaller, focused classes are easier to understand
- **Testability**: Each component can be tested in isolation
- **Extensibility**: Easy to add new strategies/validators
- **Clarity**: Clear separation of concerns

The investment of 2-3 weeks will pay off in reduced technical debt, easier onboarding for new developers, and faster feature development in the future.

**Recommendation**: Proceed with this plan starting next week.
