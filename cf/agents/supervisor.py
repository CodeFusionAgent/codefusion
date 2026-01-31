"""
SupervisorAgent for CodeFusion

Orchestrates CodeAgent analysis with integrated post-processing:
- LLMToolSelector for question classification
- NarrativeGenerator for enhanced narrative synthesis
- FileAnalyzer for structural file analysis
- Validation for answer grounding and accuracy
- Subagent spawning with isolated context and parallel execution
"""

import sys
import time
import json
import traceback
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, as_completed

# CodeFusion imports
from cf.agents.base import BaseAgent, ThoroughnessLevel
from cf.agents.code import CodeAgent
from cf.agents.protocols import AgentRegistry
from cf.tools.registry import ToolRegistry

# Advanced analysis modules (integrated features)
from cf.agents.tool_selector import LLMToolSelector, QuestionCategory
from cf.agents.narrative import (
    NarrativeGenerator, NarrativeStyle, NarrativeContext, QualityLevel
)
from cf.agents.analyzer import FileAnalyzer


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that orchestrates CodeAgent and applies post-processing.

    Uses ReAct-style analysis with:
    1. LLMToolSelector for intelligent question classification
    2. CodeAgent for the main analysis via ReAct loop
    3. FileAnalyzer for enriching file structural data
    4. NarrativeGenerator for enhanced narrative synthesis (includes validation)
    """

    agent_name: str = "supervisor"

    def __init__(self, repo_path: str, config: Dict[str, Any], kb_orchestrator: Optional[Any] = None):
        # Initialize shared tool/agent registry BEFORE calling super().__init__
        self._agent_registry = AgentRegistry()
        self._shared_tool_registry = ToolRegistry(
            repo_path,
            agent_registry=self._agent_registry,
            kb_orchestrator=kb_orchestrator
        )

        # Initialize BaseAgent with shared tool registry
        super().__init__(repo_path, config, tool_registry=self._shared_tool_registry)

        # Initialize advanced analysis modules
        self._init_analysis_modules()

        # Question-specific state (reset each question)
        self.reset_question_state()

    def _init_analysis_modules(self):
        """Initialize the integrated analysis modules."""
        # LLMToolSelector: Intelligent question classification
        self.tool_selector = LLMToolSelector(
            llm_callback=self.call_llm,
            config=self.config
        )

        # NarrativeGenerator: Rich narrative generation with templates
        self.narrative_generator = NarrativeGenerator(
            llm_callback=self.call_llm,
            config=self.config,
            repo_tools=None  # Will use built-in repo tools
        )

        # FileAnalyzer: Comprehensive file analysis with AST parsing
        self.file_analyzer = FileAnalyzer(
            repo_path=self.repo_path,
            llm_callback=self.call_llm
        )

    def call_llm(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Call the LLM client to generate a response.

        Args:
            prompt: The user prompt to send to the LLM
            system_prompt: Optional system prompt for context

        Returns:
            Dict with 'success', 'content', and other response fields
        """
        try:
            result = self.llm.generate(prompt=prompt, system_prompt=system_prompt)
            return result
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return {'success': False, 'error': str(e), 'content': ''}

    def reset_question_state(self):
        """Reset state for new question."""
        self.actions_taken = []
        self.results = {}
        self.insights = []
        self.specialist_results = {}
        self._current_classification = None
        self._react_agent = None
        self._import_resolution_cache = {}  # Cache for import path resolution

    def spawn_subagent(
        self,
        prompt: str,
        thoroughness: ThoroughnessLevel = ThoroughnessLevel.MEDIUM,
        model_tier: str = 'fast'
    ) -> Dict[str, Any]:
        """
        Spawn an isolated CodeAgent subagent for exploration.

        Args:
            prompt: What to explore
            thoroughness: Depth of exploration (quick/medium/thorough)
            model_tier: LLM tier to use ('fast' for exploration)

        Returns:
            Analysis result from the subagent
        """
        subagent = CodeAgent(
            repo_path=self.repo_path,
            config=self.config,
            tool_registry=self._shared_tool_registry,
            thoroughness=thoroughness,
            isolated_context=True,
            model_tier=model_tier
        )
        return subagent.analyze(prompt)

    def spawn_parallel(
        self,
        tasks: List[Dict[str, Any]],
        max_parallel: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Spawn multiple subagents in parallel.

        Args:
            tasks: List of dicts with 'prompt' and optional 'thoroughness', 'model_tier'
            max_parallel: Max concurrent subagents (defaults to config)

        Returns:
            List of results in task order
        """
        if not tasks:
            return []

        max_workers = max_parallel or self.config.get('agents', {}).get('parallel_workers', 4)
        results = [None] * len(tasks)

        self.logger.verbose(f"Spawning {len(tasks)} parallel subagents", "🚀")

        with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as executor:
            future_to_idx = {}

            for idx, task in enumerate(tasks):
                prompt = task.get('prompt', '')
                thoroughness = task.get('thoroughness', ThoroughnessLevel.MEDIUM)
                if isinstance(thoroughness, str):
                    thoroughness = ThoroughnessLevel(thoroughness)
                model_tier = task.get('model_tier', 'fast')

                future = executor.submit(
                    self.spawn_subagent,
                    prompt,
                    thoroughness,
                    model_tier
                )
                future_to_idx[future] = idx

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    self.logger.error(f"Subagent {idx} failed: {e}")
                    results[idx] = {
                        'success': False,
                        'error': str(e),
                        'files_analyzed': [],
                        'answer': f"Exploration failed: {e}"
                    }

        return results

    def analyze(self, question: str, mode: str = "auto") -> Dict[str, Any]:
        """
        Main analysis method using ReAct-style flow.

        Args:
            question: User question to analyze
            mode: Analysis mode (kept for API compatibility, but not used)

        Returns:
            Analysis result dictionary
        """
        # Start timing
        start_time = time.time()

        # End previous tracing session before starting new one
        if hasattr(self, 'session_id') and self.session_id:
            try:
                self.tracer.end_session(self.session_id)
            except Exception:
                pass  # Ignore if session already ended

        # Start new tracing session
        self.session_id = self.tracer.start_session(f"supervisor_q_{int(time.time())}")

        # Reset state for new question
        self.reset_question_state()

        # Run ReAct-style analysis with post-processing
        result = self._analyze_react_style(question)

        # Calculate execution time
        execution_time = time.time() - start_time

        # Add timing and metadata to result
        if isinstance(result, dict):
            result['execution_time'] = execution_time
            result['analysis_mode'] = 'react'

            # Collect metrics
            try:
                metrics = self._collect_metrics()
                if metrics:
                    result['metrics'] = metrics
            except Exception as e:
                self.logger.debug(f"Failed to collect metrics: {e}")

            # Extract analyzed_file_list for display
            if result.get('files_analyzed'):
                result['analyzed_file_list'] = result['files_analyzed']

        return result

    def _analyze_react_style(self, question: str) -> Dict[str, Any]:
        """
        ReAct-style analysis using simple tool-calling loop.

        Flow:
        1. Classify question using LLMToolSelector
        2. Run CodeAgent ReAct analysis
        3. Enrich files with FileAnalyzer
        4. Enhance answer with NarrativeGenerator (includes validation)
        """
        # Step 1: Classify question using LLMToolSelector
        question_classification = None
        try:
            question_classification = self.tool_selector.classify_question(question)
            self.logger.verbose(
                f"Question classified: {question_classification.category.value}, "
                f"complexity: {question_classification.complexity.value}",
                "🎯"
            )
            self._current_classification = question_classification
        except Exception as e:
            self.logger.debug(f"Question classification failed: {e}, proceeding without")
            self._current_classification = None

        # Initialize CodeAgent if not already done
        if not self._react_agent:
            self._react_agent = CodeAgent(
                self.repo_path,
                self.config,
                tool_registry=self._shared_tool_registry
            )

        # Pass classification context to agent for smarter tool selection
        if question_classification and hasattr(self._react_agent, 'set_question_context'):
            self._react_agent.set_question_context({
                'category': question_classification.category.value,
                'complexity': question_classification.complexity.value,
                'needs_kb': question_classification.needs_kb,
                'key_concepts': question_classification.key_concepts,
                'suggested_agents': question_classification.suggested_agents
            })

        # Step 2: Run ReAct analysis
        result = self._react_agent.analyze(question)

        # Store files in specialist_results for compatibility
        if result.get('success') and result.get('files_analyzed'):
            self.specialist_results['code'] = {
                'success': True,
                'analyzed_file_list': result['files_analyzed']
            }

        # Step 3: Enrich file data with FileAnalyzer (AST parsing, complexity metrics)
        if result.get('success') and result.get('files_analyzed'):
            result = self._enrich_with_file_analysis(result)

        # Step 3.5: Follow imports to discover additional relevant files
        if result.get('success') and result.get('files_analyzed'):
            result = self._follow_imports(result)

        # Step 4: Post-process with NarrativeGenerator if analysis succeeded
        # NarrativeGenerator handles validation internally (single validation pass)
        if result.get('success') and result.get('answer'):
            result = self._enhance_with_narrative(question, result, question_classification)

        return result

    def _enrich_with_file_analysis(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich file data with FileAnalyzer (AST parsing, complexity metrics).

        This runs FileAnalyzer on analyzed files IN PARALLEL to gather structural
        information (functions, classes, imports, complexity) for richer narratives.
        """
        try:
            files_analyzed = result.get('files_analyzed', [])
            if not files_analyzed:
                return result

            # Use configurable limit for file enrichment
            max_enrich = self.config.get('agents', {}).get('max_files_to_enrich', 25)
            files_to_enrich = files_analyzed[:max_enrich]

            self.logger.verbose(f"Enriching {len(files_to_enrich)} files with FileAnalyzer (parallel)", "🔬")

            file_summaries = result.get('file_summaries', {})

            def analyze_single_file(file_path: str):
                """Analyze a single file - designed for parallel execution."""
                try:
                    analysis = self.file_analyzer.analyze_file(file_path)
                    if analysis:
                        # Extract detailed function info with line numbers
                        functions_detail = []
                        if hasattr(analysis, 'functions'):
                            for f in analysis.functions[:20]:  # Limit to 20 functions
                                functions_detail.append({
                                    'name': f.name,
                                    'line': f.start_line,
                                    'params': f.params[:5] if f.params else [],
                                    'is_method': getattr(f, 'is_method', False),
                                })

                        # Extract detailed class info with line numbers and fields
                        classes_detail = []
                        if hasattr(analysis, 'classes'):
                            for c in analysis.classes[:10]:  # Limit to 10 classes
                                classes_detail.append({
                                    'name': c.name,
                                    'line': c.start_line,
                                    'bases': c.bases[:3] if c.bases else [],
                                    'fields': (c.class_vars[:10] if c.class_vars else []),
                                    'methods': [m.name for m in c.methods[:10]] if c.methods else [],
                                })

                        # Extract constants (module-level definitions)
                        constants_detail = []
                        if hasattr(analysis, 'constants'):
                            for const in analysis.constants[:15]:  # Limit to 15 constants
                                constants_detail.append({
                                    'name': const.name,
                                    'line': const.line_number,
                                    'value': const.value_repr[:100] if const.value_repr else '',
                                    'is_dict': getattr(const, 'is_dict', False),
                                })

                        # Extract import module names for import following
                        imports_list = []
                        if hasattr(analysis, 'imports'):
                            for imp in analysis.imports:
                                if hasattr(imp, 'module'):
                                    imports_list.append(imp.module)
                                elif isinstance(imp, str):
                                    imports_list.append(imp)

                        return (file_path, {
                            'functions': functions_detail,
                            'classes': classes_detail,
                            'constants': constants_detail,
                            'imports': imports_list,
                            'complexity': getattr(analysis, 'complexity', None),
                            'category': getattr(analysis, 'category', None),
                            'line_count': getattr(analysis, 'line_count', 0),
                        })
                except Exception:
                    pass
                return None

            # Parallel file analysis with configurable workers
            parallel_workers = self.config.get('agents', {}).get('parallel_workers', 10)
            enriched_count = 0

            with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                futures = {executor.submit(analyze_single_file, fp): fp for fp in files_to_enrich}

                for future in as_completed(futures):
                    result_data = future.result()
                    if result_data:
                        file_path, structure = result_data
                        if file_path not in file_summaries:
                            file_summaries[file_path] = {}
                        file_summaries[file_path]['structure'] = structure
                        enriched_count += 1

            result['file_summaries'] = file_summaries
            self.logger.verbose(f"Enriched {enriched_count} files with structural data", "✅")

        except Exception as e:
            self.logger.debug(f"File enrichment failed: {e}, proceeding with basic data")

        return result

    def _follow_imports(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Follow imports from analyzed files to discover additional relevant files.

        This implements MULTI-LEVEL import following (3 levels by default):
        - Level 1: Follow imports from originally analyzed files
        - Level 2: Follow imports from level 1 files
        - Level 3: Follow imports from level 2 files

        This helps capture constants, mappings, and configurations that are
        imported transitively (e.g., handlers → models → constants).

        OPTIMIZATION: Uses cached import data from enrichment step (no re-analysis)
        and parallelizes analysis of new import-followed files.
        """
        try:
            files_analyzed = list(result.get('files_analyzed', []))
            file_summaries = result.get('file_summaries', {})
            all_files_seen = set(files_analyzed)  # Track all files to avoid re-analyzing

            if not files_analyzed:
                return result

            # Configuration - read from import_tracing section for depth settings
            import_tracing = self.config.get('agents', {}).get('import_tracing', {})
            max_levels = import_tracing.get('max_depth', 3)
            max_files_per_level = self.config.get('agents', {}).get('max_import_follow', 20)
            parallel_workers = self.config.get('agents', {}).get('parallel_workers', 10)
            # NOTE: No hardcoded priority keywords - LLM decides what's relevant during exploration
            repo_path = Path(self.repo_path)

            total_added = 0
            current_level_files = files_analyzed  # Start with original files

            def analyze_import_file(file_path: str):
                """Analyze a single import-followed file - designed for parallel execution."""
                try:
                    analysis = self.file_analyzer.analyze_file(file_path)
                    if analysis:
                        # Extract detailed function info with line numbers
                        functions_detail = []
                        if hasattr(analysis, 'functions'):
                            for f in analysis.functions[:15]:
                                functions_detail.append({
                                    'name': f.name,
                                    'line': f.start_line,
                                    'params': f.params[:5] if f.params else [],
                                })

                        # Extract detailed class info with line numbers and fields
                        classes_detail = []
                        if hasattr(analysis, 'classes'):
                            for c in analysis.classes[:8]:
                                classes_detail.append({
                                    'name': c.name,
                                    'line': c.start_line,
                                    'bases': c.bases[:3] if c.bases else [],
                                    'fields': (c.class_vars[:10] if c.class_vars else []),
                                })

                        # Extract constants (module-level definitions)
                        constants_detail = []
                        if hasattr(analysis, 'constants'):
                            for const in analysis.constants[:20]:
                                constants_detail.append({
                                    'name': const.name,
                                    'line': const.line_number,
                                    'value': const.value_repr[:150] if const.value_repr else '',
                                    'is_dict': getattr(const, 'is_dict', False),
                                })

                        # Extract imports for next level (critical for multi-level following)
                        imports_list = []
                        if hasattr(analysis, 'imports'):
                            imports_list = analysis.imports[:30]

                        return (file_path, {
                            'source': 'import_follow',
                            'structure': {
                                'functions': functions_detail,
                                'classes': classes_detail,
                                'constants': constants_detail,
                                'imports': imports_list,  # Include for next level
                                'complexity': getattr(analysis, 'complexity', None),
                                'line_count': getattr(analysis, 'line_count', 0),
                            }
                        })
                except Exception:
                    pass
                return None

            # Multi-level import following loop
            for level in range(1, max_levels + 1):
                # Collect imports from current level files
                level_imports = set()
                for file_path in current_level_files:
                    summary = file_summaries.get(file_path, {})
                    structure = summary.get('structure', {})
                    imports_data = structure.get('imports', [])
                    if isinstance(imports_data, list):
                        level_imports.update(imports_data)

                if not level_imports:
                    break

                # Resolve imports to file paths (excluding already seen)
                new_files = []
                for import_name in level_imports:
                    if self._is_external_import(import_name):
                        continue
                    resolved_path = self._resolve_import_to_path(import_name, repo_path)
                    if resolved_path and resolved_path not in all_files_seen:
                        new_files.append(resolved_path)
                        all_files_seen.add(resolved_path)

                if not new_files:
                    break

                # Limit files per level - no hardcoded keyword prioritization
                # LLM will decide relevance during exploration phase
                new_files = new_files[:max_files_per_level]

                self.logger.verbose(
                    f"Import level {level}: discovered {len(new_files)} files", "🔗"
                )

                # Parallel analysis of import-followed files
                level_analyzed = []
                with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                    futures = {executor.submit(analyze_import_file, fp): fp for fp in new_files}
                    for future in as_completed(futures):
                        result_data = future.result()
                        if result_data:
                            file_path, summary_data = result_data
                            files_analyzed.append(file_path)
                            file_summaries[file_path] = summary_data
                            level_analyzed.append(file_path)
                            total_added += 1

                # Prepare for next level (use files just analyzed)
                current_level_files = level_analyzed

                if not level_analyzed:
                    break

            result['files_analyzed'] = files_analyzed
            result['file_summaries'] = file_summaries
            result['import_followed_count'] = total_added

            self.logger.verbose(
                f"Import following complete: added {total_added} files across {max_levels} levels", "✅"
            )

        except Exception as e:
            self.logger.debug(f"Import following failed: {e}, proceeding with original files")

        return result

    def _is_external_import(self, import_name: str) -> bool:
        """Check if an import is external (stdlib or third-party).

        Uses sys.stdlib_module_names (Python 3.10+) for stdlib detection.
        For third-party, uses resolution: if import can't be resolved in repo, it's external.
        This is language-agnostic and doesn't require hardcoded package lists.
        """
        first_part = import_name.split('.')[0]

        # Check Python standard library (Python 3.10+)
        if hasattr(sys, 'stdlib_module_names'):
            if first_part in sys.stdlib_module_names:
                return True

        # Language-agnostic approach: if it can't be resolved in repo, it's external
        # This avoids hardcoding language-specific package lists
        resolved_path = self._resolve_import_to_path(import_name, Path(self.repo_path))
        return resolved_path is None

    def _resolve_import_to_path(self, import_name: str, repo_path: Path) -> Optional[str]:
        """Resolve an import name to a file path in the repo (with caching)."""
        # Check cache first
        if import_name in self._import_resolution_cache:
            return self._import_resolution_cache[import_name]

        # Simple file system check - glob for any matching file
        parts = import_name.split('.')
        base_path = repo_path / '/'.join(parts)

        # Check if directory or any file with this name exists
        result = None
        if base_path.is_dir():
            result = str(base_path)
        else:
            # Glob for any file with this name
            matches = list(base_path.parent.glob(f"{base_path.name}.*")) if base_path.parent.exists() else []
            if matches:
                result = str(matches[0])

        # Cache the result (even if None, to avoid re-checking)
        self._import_resolution_cache[import_name] = result
        return result

    def _enhance_with_narrative(
        self,
        question: str,
        result: Dict[str, Any],
        classification: Optional[Any]
    ) -> Dict[str, Any]:
        """
        Enhance CodeAgent's answer with NarrativeGenerator post-processing.

        Maps question classification to appropriate narrative style and
        generates a structured, well-formatted response.
        """
        try:
            self.logger.verbose("Enhancing answer with NarrativeGenerator", "📝")

            # Let LLM determine narrative style based on question
            style = self._map_category_to_style(classification, question)

            # Build NarrativeContext from CodeAgent result
            # Pass base_answer so NarrativeGenerator refines instead of regenerating
            context = NarrativeContext(
                question=question,
                files_analyzed=result.get('files_analyzed', []),
                file_summaries=result.get('file_summaries', {}),
                agent_results={'code': result},
                code_snippets=result.get('code_snippets', {}),
                execution_time=result.get('execution_time', 0.0),
                base_answer=result.get('answer', '')  # Pass CodeAgent's answer for refinement
            )

            # Generate enhanced narrative
            narrative_result = self.narrative_generator.generate(
                context=context,
                style=style,
                quality=QualityLevel.STANDARD
            )

            # Update result with enhanced narrative
            if narrative_result and narrative_result.narrative:
                result['original_answer'] = result.get('answer', '')
                result['answer'] = narrative_result.narrative
                result['narrative_style'] = style.value
                result['narrative_confidence'] = narrative_result.confidence

                # Extract validation from NarrativeResult (single validation pass)
                if hasattr(narrative_result, 'validation') and narrative_result.validation:
                    result['validation'] = narrative_result.validation
                    validation = narrative_result.validation
                    # Log validation results for visibility
                    print(f"📊 [supervisor] Validation: grounding={validation.grounding_score:.2f}, "
                          f"refs={validation.file_line_ref_count}, valid={validation.valid}")
                    if validation.issues:
                        for issue in validation.issues[:3]:  # Show first 3 issues
                            print(f"   ⚠️ [{issue.severity}] {issue.issue_type}: {issue.message[:100]}")

                self.logger.verbose(
                    f"Narrative refined: style={style.value}, confidence={narrative_result.confidence:.2f}",
                    "✅"
                )
            else:
                print(f"⚠️ [supervisor] NarrativeGenerator returned empty result, using CodeAgent answer")

        except Exception as e:
            # Log at visible level so failures are noticed
            print(f"⚠️ [supervisor] NarrativeGenerator failed: {e}, using original answer")
            traceback.print_exc()

        return result

    def _map_category_to_style(self, classification: Optional[Any], question: str = "") -> NarrativeStyle:
        """
        Determine narrative style based on question and classification.

        Uses LLM to select appropriate style rather than hardcoded mapping.
        Falls back to EXPLANATION if LLM selection fails.
        """
        if not classification and not question:
            return NarrativeStyle.EXPLANATION

        # Let LLM determine the best narrative style based on question context
        try:
            if self._llm_client:
                style_prompt = f"""Given this question about code: "{question}"

Select the most appropriate narrative style for the response:
- LIFE_OF_X: For tracing how data/requests flow through the system
- ARCHITECTURE: For explaining system structure and components
- EXPLANATION: For explaining how something works
- COMPARISON: For comparing different approaches or components
- DEBUG_TRACE: For tracing execution paths for debugging
- API_REFERENCE: For documenting APIs and interfaces
- TUTORIAL: For step-by-step guides

Respond with ONLY the style name (e.g., "EXPLANATION")."""

                response = self._llm_client.chat(
                    style_prompt,
                    "You are a technical writing style selector. Respond with only the style name.",
                    max_tokens=20
                )

                if response.get('success'):
                    style_name = response.get('content', '').strip().upper()
                    # Try to match to enum
                    for style in NarrativeStyle:
                        if style.name == style_name or style_name in style.name:
                            return style

        except Exception:
            pass  # Fall through to default

        # Default fallback
        return NarrativeStyle.EXPLANATION

    def _collect_metrics(self) -> Dict[str, Any]:
        """
        Collect all available metrics from various sources.

        Returns:
            Dictionary with aggregated metrics
        """
        metrics = {}

        # Get tool metrics from shared tool registry
        if self._shared_tool_registry:
            try:
                tool_metrics = self._shared_tool_registry.get_metrics()
                if tool_metrics:
                    metrics['tools'] = tool_metrics
            except Exception as e:
                self.logger.debug(f"Failed to collect tool metrics: {e}")

        # Get KB layer metrics from agent registry
        if self._agent_registry:
            try:
                kb_metrics = self._agent_registry.get_metrics_summary()
                if kb_metrics:
                    metrics['kb_layers'] = kb_metrics
            except Exception as e:
                self.logger.debug(f"Failed to collect KB metrics: {e}")

        # Extract code agent metrics from specialist results
        if 'code' in self.specialist_results:
            code_result = self.specialist_results['code']
            if code_result.get('success'):
                if 'analyzed_file_list' in code_result:
                    metrics['files_analyzed'] = len(code_result['analyzed_file_list'])

        return metrics
