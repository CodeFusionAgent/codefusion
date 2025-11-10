# Pipeline Architecture for CodeFusion

## Overview

This directory contains the new **pipeline architecture** for CodeFusion, designed to replace the monolithic `CodeAgent` with modular, testable, and maintainable components.

## Architecture

### Pipeline Architecture (Current)
- **Files**: 5 modular pipeline files
- **Total Lines**: ~1,200 lines (73% reduction)
- **Structure**: Orchestrator + 4 specialized pipelines
- **Benefits**:
  - Each pipeline is independently testable
  - Clear separation of concerns
  - Easy to add parallelism (Phase 2)
  - Simple to debug and maintain
  - Config-driven behavior throughout

## Pipeline Stages

### 1. Discovery Pipeline (`discovery.py`)
**Purpose**: Find relevant files for a question

**Strategies**:
- `KeywordMatchingStrategy`: Match question keywords to directory names
- `DomainDetectionStrategy`: Use LLM to detect domain and target directories
- `GrepSearchStrategy`: Search file contents for keywords
- `FallbackStrategy`: Generic file discovery if other strategies fail

**Output**: `DiscoveryResult` with ranked `FileCandidate` objects

**Lines**: ~370 lines (was ~800 lines in code.py)

### 2. Analysis Pipeline (`analysis.py`)
**Purpose**: Analyze discovered files and extract insights

**Features**:
- LLM-powered file summarization
- Caching support (semantic cache)
- Metrics tracking (tokens, time)
- Uses fast model for cost efficiency

**Output**: `AnalysisResult` with `FileSummary` objects

**Lines**: ~240 lines (was ~1,200 lines in code.py)

### 3. Validation Pipeline (`validation.py`)
**Purpose**: Validate generated answers for quality

**Checks**:
- Line number references (grounding)
- File path accuracy
- Claim validation (no ungrounded statements)
- Coverage metrics

**Output**: `ValidationResult` with issues and scores

**Lines**: ~230 lines (was ~600 lines in code.py)

### 4. Synthesis Pipeline (`synthesis.py`)
**Purpose**: Generate final technical narratives

**Features**:
- Config-driven narrative generation
- Completeness evaluation with LLM
- Confidence scoring based on references
- Target length enforcement

**Output**: `SynthesisResult` with narrative and metadata

**Lines**: ~240 lines (was ~800 lines in code.py)

### 5. Orchestrator (`code_orchestrator.py`)
**Purpose**: Coordinate all pipelines

**Flow**:
1. Initialize repository scan
2. Discover relevant files
3. Analyze files
4. Generate and validate answer

**Lines**: ~250 lines (vs 4,375 in original)

## Key Improvements

### 1. Modularity
Each pipeline is self-contained with clear inputs and outputs. No circular dependencies.

### 2. Testability
```python
# Easy to test individual pipelines
discovery = DiscoveryPipeline(repo_path, config, llm, tools, path_map)
result = discovery.discover("How does auth work?")
assert len(result.files) > 0
```

### 3. Maintainability
- Small, focused files (~200-370 lines each)
- Clear responsibilities
- Easy to locate and fix bugs
- Simple to add new features

### 4. Configuration-Driven
All thresholds, parameters, and behavior controlled via `config.yaml`

### 5. Parallel Processing Ready (Phase 2)
The pipeline architecture naturally supports parallelism

## Migration Plan

### Phase 1: Extract Pipelines ✅ (COMPLETED)
- [x] Create `discovery.py` with all discovery strategies
- [x] Create `analysis.py` with file analysis logic
- [x] Create `validation.py` with validation logic
- [x] Create `synthesis.py` with narrative generation
- [x] Create `code_orchestrator.py` as coordinator
- [x] **Integrate with SupervisorAgent**
- [x] **Export from modules** - Added to `cf/__init__.py` and `cf/agents/__init__.py`

### Phase 2: Add Parallelism ✅ (COMPLETED)
- [x] Add async/await support to analysis pipeline
- [x] Implement parallel file processing
- [x] Add batch processing for large codebases
- [x] Benchmark performance improvements

### Phase 3: Tool-First Architecture ✅ (COMPLETED)
- [x] Enforce tool-first pattern in DiscoveryPipeline
- [x] Update CodeOrchestrator to use tools only
- [x] Remove hardcoded keyword patterns from structural.py
- [x] Replace intent detection with pure LLM approach

### Phase 4: Deprecation ✅ (COMPLETED)
- [x] Update documentation
- [x] Remove legacy CodeAgent (4,402 lines)
- [x] Remove use_pipeline_architecture toggle
- [x] Clean up imports and exports
