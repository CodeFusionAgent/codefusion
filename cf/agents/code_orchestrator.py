"""
CodeOrchestrator - Pipeline-based Code Analysis Agent

Clean orchestrator that coordinates specialized pipelines:
- Discovery: Find relevant files
- Analysis: Extract insights from files
- Validation: Ensure answer quality
- Synthesis: Generate technical narratives

This replaces the monolithic CodeAgent with a modular pipeline architecture.
Uses state-based flow for adaptive analysis.
"""

from typing import Dict, List, Any
from enum import Enum
from cf.agents.base import BaseAgent
from cf.agents.pipelines.discovery import DiscoveryPipeline
from cf.agents.pipelines.analysis import AnalysisPipeline
from cf.agents.pipelines.validation import ValidationPipeline
from cf.agents.pipelines.synthesis import SynthesisPipeline
from cf.agents.pipelines.structural import StructuralPipeline
from cf.llm.model_tiers import TieredLLMManager


class AnalysisState(Enum):
    """States for analysis workflow - enables adaptive flow"""
    INIT = "init"                        # Initial state
    REPO_READY = "repo_ready"           # Repository scanned
    FILES_DISCOVERED = "files_discovered"  # Files found
    FILES_ANALYZED = "files_analyzed"    # Files analyzed
    SYNTHESIS_COMPLETE = "synthesis_complete"  # Answer generated
    COMPLETE = "complete"                # All done


class CodeOrchestrator(BaseAgent):
    """
    Orchestrates multiple pipelines for code analysis.

    Clean architecture with ~200 lines vs 4,375 in monolithic CodeAgent.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any]):
        super().__init__(repo_path, config, "code_orchestrator")

        # Initialize tiered LLM manager
        self.tiered_llm = TieredLLMManager(config)

        # Initialize pipelines
        self.structural = None  # NEW - Structural KB pipeline
        self.discovery = None
        self.analysis = None
        self.validation = None
        self.synthesis = None

        # State tracking (state-based flow instead of iteration-based)
        self.current_state = AnalysisState.INIT
        self.path_map = {}
        self.discovered_files = []
        self.file_summaries = {}
        self.kb_initialized = False  # NEW - Track KB initialization

        # Adaptive discovery config
        self.discovery_attempt = 0
        self.max_discovery_attempts = 3
        self.min_files_threshold = 3  # Minimum files needed for good analysis

        # Quality feedback loop config
        self.synthesis_retry_count = 0
        self.max_synthesis_retries = 2  # Max retries if validation fails

    def reset_question_state(self):
        """
        Reset state for new question while preserving expensive resources.

        Keeps:
        - self.structural (KB pipeline and connection)
        - self.path_map (repository structure)
        - self.kb_initialized (KB status)
        - All pipelines (discovery, analysis, validation, synthesis)

        Clears:
        - Question-specific results and file lists
        - Parent class state (iteration, insights, etc.) handled by BaseAgent
        """
        # Clear question-specific state
        self.current_state = AnalysisState.INIT if not self.path_map else AnalysisState.REPO_READY
        self.discovered_files = []
        self.file_summaries = {}
        self.results = {}
        self.insights = []
        self.actions_taken = []
        self.discovery_attempt = 0
        self.synthesis_retry_count = 0

        # Note: self.iteration is reset by BaseAgent.analyze()
        # Note: self.structural, self.path_map, and pipelines are preserved

    def _detect_primary_language(self) -> str:
        """
        Detect primary programming language in repository.
        Returns: Language name or None
        """
        try:
            from pathlib import Path
            from collections import Counter

            # Count file extensions
            extensions = Counter()
            repo_path = Path(self.repo_path)

            # Language extension mapping
            lang_map = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.ts': 'TypeScript',
                '.jsx': 'JavaScript',
                '.tsx': 'TypeScript',
                '.java': 'Java',
                '.go': 'Go',
                '.rs': 'Rust',
                '.cpp': 'C++',
                '.c': 'C',
                '.cs': 'C#',
                '.rb': 'Ruby',
                '.php': 'PHP',
                '.swift': 'Swift',
                '.kt': 'Kotlin',
                '.scala': 'Scala'
            }

            # Excluded directories
            excluded_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                           'build', 'dist', 'target', 'vendor', '.idea', '.vscode'}

            # Count extensions (limit to 1000 files for speed)
            count = 0
            for path in repo_path.rglob('*'):
                if count >= 1000:
                    break

                # Skip excluded directories
                if any(excluded in path.parts for excluded in excluded_dirs):
                    continue

                if path.is_file() and path.suffix in lang_map:
                    extensions[path.suffix] += 1
                    count += 1

            if extensions:
                # Get most common extension
                most_common_ext = extensions.most_common(1)[0][0]
                return lang_map.get(most_common_ext)

        except Exception as e:
            print(f"⚠️ [LANGUAGE_DETECTION] Failed: {e}")

        return None

    def _analyze_step(self, question: str) -> str:
        """
        Execute one analysis step using state-based flow.

        State-based flow enables adaptive behavior:
        - Can retry discovery if insufficient files found
        - Can skip states if data is already available (cached)
        - Can adapt based on question complexity
        """

        # State: INIT → Initialize repository
        if self.current_state == AnalysisState.INIT:
            action = self._initialize_repository()
            if action == "scan_complete":
                self.current_state = AnalysisState.REPO_READY
            return action

        # State: REPO_READY → Discover relevant files
        elif self.current_state == AnalysisState.REPO_READY:
            action = self._discover_files(question)

            if action == "discovery_complete":
                # Check if we found enough files
                if len(self.discovered_files) >= self.min_files_threshold:
                    self.current_state = AnalysisState.FILES_DISCOVERED
                    print(f"✅ [ORCHESTRATOR] Discovery successful: {len(self.discovered_files)} files")
                else:
                    # Insufficient files - retry with broader search if attempts remain
                    self.discovery_attempt += 1
                    if self.discovery_attempt < self.max_discovery_attempts:
                        print(f"⚠️ [ORCHESTRATOR] Only {len(self.discovered_files)} files found (min: {self.min_files_threshold})")
                        print(f"   Retrying with broader search (attempt {self.discovery_attempt + 1}/{self.max_discovery_attempts})...")
                        # Reset to retry discovery with broader parameters
                        return "discovery_retry"
                    else:
                        # Max attempts reached, proceed anyway
                        print(f"⚠️ [ORCHESTRATOR] Max discovery attempts reached. Proceeding with {len(self.discovered_files)} files.")
                        self.current_state = AnalysisState.FILES_DISCOVERED if self.discovered_files else AnalysisState.COMPLETE
            return action

        # State: FILES_DISCOVERED → Analyze files
        elif self.current_state == AnalysisState.FILES_DISCOVERED:
            action = self._analyze_files(question)
            if action == "analysis_complete" and self.file_summaries:
                self.current_state = AnalysisState.FILES_ANALYZED
            return action

        # State: FILES_ANALYZED → Generate synthesis
        elif self.current_state == AnalysisState.FILES_ANALYZED:
            action = self._finalize_analysis(question)
            if action == "synthesis_complete" and self.results.get('narrative'):
                self.current_state = AnalysisState.SYNTHESIS_COMPLETE
            return action

        # State: SYNTHESIS_COMPLETE → Mark complete
        elif self.current_state == AnalysisState.SYNTHESIS_COMPLETE:
            self.current_state = AnalysisState.COMPLETE
            return "complete"

        # State: COMPLETE → Nothing more to do
        elif self.current_state == AnalysisState.COMPLETE:
            return "already_complete"

        return "unknown_state"

    def _initialize_repository(self) -> str:
        """Initialize repository scan, path map, and knowledge base"""
        try:
            print("🔍 [ORCHESTRATOR] Initializing repository...")

            # Detect repository language
            primary_language = self._detect_primary_language()
            if primary_language:
                print(f"🔍 [ORCHESTRATOR] Detected primary language: {primary_language}")
                if primary_language != 'Python':
                    print(f"⚠️ [ORCHESTRATOR] KB structural analysis currently supports Python only")
                    print(f"   Will use file-based analysis for {primary_language} code")

            # Check if KB is enabled
            kb_config = self.config.get('knowledge_base', {})
            kb_enabled = kb_config.get('enabled', False) and primary_language == 'Python'
            auto_build = kb_config.get('build', {}).get('auto_build', True)

            # Initialize structural KB pipeline if enabled
            if kb_enabled:
                try:
                    # Only create StructuralPipeline if not already initialized (critical for interactive mode!)
                    if self.structural is None:
                        print("🔍 [ORCHESTRATOR] Initializing structural knowledge base...")
                        self.structural = StructuralPipeline(self.repo_path, self.config)

                        if self.structural.is_kb_available():
                            # Check if KB exists
                            if self.structural.kb_exists():
                                print("✅ [ORCHESTRATOR] Found existing KB")

                                # Check for incremental updates
                                if kb_config.get('incremental', {}).get('enabled', True):
                                    print("🔄 [ORCHESTRATOR] Checking for file changes...")
                                    update_stats = self.structural.update_knowledge_base()

                                    if update_stats.get('changes', 0) > 0:
                                        print(f"✅ [ORCHESTRATOR] KB updated: {update_stats.get('changes', 0)} files changed")

                                # Initialize enhanced layers after loading existing KB
                                print("🔬 [ORCHESTRATOR] Initializing enhanced knowledge layers...")
                                self.structural._build_enhanced_layers()

                                self.kb_initialized = True
                            elif auto_build:
                                # Build KB for first time
                                print("🏗️ [ORCHESTRATOR] Building KB for first time (this may take 60-90 min for large repos)...")
                                build_result = self.structural.build_knowledge_base()

                                if build_result.total_files > 0:
                                    print(f"✅ [ORCHESTRATOR] KB built: {build_result.total_files} files")
                                    self.kb_initialized = True
                                else:
                                    print("⚠️ [ORCHESTRATOR] KB build returned 0 files")
                            else:
                                print("ℹ️ [ORCHESTRATOR] KB doesn't exist and auto_build is disabled")
                    else:
                        # StructuralPipeline already exists, just check for updates
                        print("✅ [ORCHESTRATOR] Using existing structural KB pipeline")
                        if self.structural.is_kb_available() and self.structural.kb_exists():
                            # Check for incremental updates
                            if kb_config.get('incremental', {}).get('enabled', True):
                                print("🔄 [ORCHESTRATOR] Checking for file changes...")
                                update_stats = self.structural.update_knowledge_base()

                                if update_stats.get('changes', 0) > 0:
                                    print(f"✅ [ORCHESTRATOR] KB updated: {update_stats.get('changes', 0)} files changed")

                except Exception as e:
                    print(f"⚠️ [ORCHESTRATOR] KB initialization failed: {e}")
                    print("   Falling back to non-KB mode")
                    self.structural = None

            # Scan repository structure (for path_map) - only if not already done
            if not self.path_map:
                print("🔍 [ORCHESTRATOR] Scanning repository structure...")
                max_depth = self.config.get('repo', {}).get('max_scan_depth', 5)
                scan_result = self.use_tool('scan_directory', max_depth=max_depth)

                if scan_result.get('error'):
                    print(f"❌ [ORCHESTRATOR] Scan failed: {scan_result['error']}")
                    return "scan_failed"

                # Build path map
                for file_info in scan_result.get('files', []):
                    path = file_info.get('path', '')
                    self.path_map[path] = {
                        'is_dir': file_info.get('type') == 'directory',
                        'extension': file_info.get('extension', ''),
                        'size': file_info.get('size', 0)
                    }
            else:
                print("✅ [ORCHESTRATOR] Using existing path map")

            # Initialize pipelines now that we have path_map and KB (only if not already created)
            if self.discovery is None:
                self.discovery = DiscoveryPipeline(
                    self.repo_path,
                    self.config,
                    self.llm,
                    self.tools,
                    self.path_map,
                    structural_pipeline=self.structural  # NEW - Pass KB pipeline
                )
            if self.analysis is None:
                self.analysis = AnalysisPipeline(
                    self.repo_path,
                    self.config,
                    self.llm,
                    self.tools,
                    self.cache,
                    tiered_llm=self.tiered_llm  # Pass tiered LLM manager
                )
            if self.validation is None:
                self.validation = ValidationPipeline(
                    self.repo_path,
                    self.config,
                    self.tools
                )
            if self.synthesis is None:
                self.synthesis = SynthesisPipeline(
                    self.repo_path,
                    self.config,
                    self.llm,
                    tiered_llm=self.tiered_llm  # Pass tiered LLM manager
                )

            print(f"✅ [ORCHESTRATOR] Found {len(self.path_map)} paths")

            if self.kb_initialized:
                kb_stats = self.structural.get_repository_stats()
                print(f"✅ [ORCHESTRATOR] KB ready: {kb_stats.get('functions', 0)} functions, {kb_stats.get('classes', 0)} classes")

            self.add_insight(
                f"Repository initialized: {len(self.path_map)} paths indexed" +
                (f", KB active with {kb_stats.get('functions', 0)} functions" if self.kb_initialized else ""),
                confidence=self.get_confidence('high'),
                source="repository_scan"
            )

            return "scan_complete"

        except Exception as e:
            print(f"❌ [ORCHESTRATOR] Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return "scan_failed"

    def _discover_files(self, question: str) -> str:
        """Discover relevant files using discovery pipeline"""
        try:
            print("🔍 [ORCHESTRATOR] Discovering relevant files...")

            # Run discovery pipeline
            max_files = self.config.get('agents', {}).get('max_files_to_analyze', 50)
            discovery_result = self.discovery.discover(question, max_files)

            # Store discovered files
            self.discovered_files = [f.path for f in discovery_result.files]

            print(f"✅ [ORCHESTRATOR] Discovered {len(self.discovered_files)} relevant files")
            print(f"   Strategies used: {', '.join(discovery_result.strategies_used)}")

            self.add_insight(
                f"File discovery complete: {len(self.discovered_files)} relevant files found using {', '.join(discovery_result.strategies_used)}",
                confidence=self.get_confidence('high'),
                source="file_discovery"
            )

            return "discovery_complete"

        except Exception as e:
            print(f"❌ [ORCHESTRATOR] Discovery failed: {e}")
            return "discovery_failed"

    def _analyze_files(self, question: str) -> str:
        """Analyze discovered files using analysis pipeline"""
        try:
            print("📄 [ORCHESTRATOR] Analyzing files...")

            # Run analysis pipeline
            analysis_result = self.analysis.analyze(self.discovered_files, question)

            # Store file summaries
            self.file_summaries = analysis_result.file_summaries

            print(f"✅ [ORCHESTRATOR] Analyzed {analysis_result.total_files_analyzed} files")
            print(f"   Cache efficiency: {analysis_result.cache_hits}/{analysis_result.cache_hits + analysis_result.cache_misses}")
            print(f"   Total tokens: {analysis_result.total_tokens_used}")

            self.add_insight(
                f"File analysis complete: {analysis_result.total_files_analyzed} files analyzed, {analysis_result.total_tokens_used} tokens used",
                confidence=self.get_confidence('high'),
                source="file_analysis"
            )

            return "analysis_complete"

        except Exception as e:
            print(f"❌ [ORCHESTRATOR] Analysis failed: {e}")
            return "analysis_failed"

    def _finalize_analysis(self, question: str) -> str:
        """Generate and validate final answer"""
        try:
            print("📝 [ORCHESTRATOR] Generating answer...")

            # Check if we have enough data
            if not self.file_summaries:
                print("⚠️ [ORCHESTRATOR] No file summaries available")

                # Store helpful error message
                self.results = {
                    'narrative': self._generate_no_files_message(question),
                    'key_files': [],
                    'confidence': 0.1,
                    'word_count': 0,
                    'validation': {'valid': False, 'grounding_score': 0.0}
                }
                return "insufficient_data"

            # Generate narrative using synthesis pipeline
            synthesis_result = self.synthesis.synthesize(
                question,
                self.file_summaries,
                self.insights
            )

            # Validate result
            validation_result = self.validation.validate(
                synthesis_result.narrative,
                self.file_summaries
            )

            # Quality feedback loop: retry if validation fails and retries remain
            if not validation_result.valid and self.synthesis_retry_count < self.max_synthesis_retries:
                self.synthesis_retry_count += 1
                print(f"⚠️ [ORCHESTRATOR] Validation failed (grounding: {validation_result.grounding_score:.1%})")
                print(f"   Retrying synthesis (attempt {self.synthesis_retry_count + 1}/{self.max_synthesis_retries + 1})...")
                print(f"   Issues: {len(validation_result.issues)} problems detected")

                # Clear previous results and retry
                self.results = {}
                return "synthesis_retry"

            # Store results (either validation passed or max retries exhausted)
            self.results = {
                'narrative': synthesis_result.narrative,
                'key_files': synthesis_result.key_files_cited,
                'confidence': synthesis_result.confidence,
                'word_count': synthesis_result.word_count,
                'validation': {
                    'valid': validation_result.valid,
                    'grounding_score': validation_result.grounding_score,
                    'line_coverage': validation_result.line_number_coverage,
                    'path_accuracy': validation_result.path_accuracy,
                    'issues': [
                        {'severity': i.severity, 'type': i.issue_type, 'message': i.message}
                        for i in validation_result.issues
                    ],
                    'retry_count': self.synthesis_retry_count
                }
            }

            if validation_result.valid:
                print(f"✅ [ORCHESTRATOR] Answer generated and validated")
                print(f"   Validation: ✅ PASSED (grounding: {validation_result.grounding_score:.1%})")
            else:
                print(f"⚠️ [ORCHESTRATOR] Answer generated with validation issues")
                print(f"   Validation: ⚠️ FAILED (grounding: {validation_result.grounding_score:.1%})")
                print(f"   Max retries exhausted ({self.synthesis_retry_count}/{self.max_synthesis_retries})")

            return "synthesis_complete"

        except Exception as e:
            print(f"❌ [ORCHESTRATOR] Finalization failed: {e}")
            return "finalization_failed"

    def _is_analysis_complete(self, question: str) -> bool:
        """
        Check if analysis is complete using state-based logic.

        More robust than iteration-based: validates actual completion criteria.
        """
        # Use config threshold instead of hardcoded value
        min_confidence = self.config.get('agents', {}).get('thresholds', {}).get('min_confidence', 0.3)

        # Must be in COMPLETE state AND have valid results
        return (
            self.current_state == AnalysisState.COMPLETE and
            self.results.get('narrative') and
            (len(self.file_summaries) > 0 or self.results.get('confidence', 0) > min_confidence)
        )

    def _generate_no_files_message(self, question: str) -> str:
        """Generate helpful message when no files found"""
        return f"""I couldn't find relevant files to answer your question: "{question}"

This could happen for several reasons:
1. The question might be about code that doesn't exist in this repository
2. The file discovery process might need broader search parameters
3. The question might be too specific or use different terminology than the codebase

Suggestions:
- Try rephrasing your question with more general terms
- Check if the feature/component exists in this codebase
- Ask about the overall architecture first to understand available components

Discovery attempts made: {self.discovery_attempt + 1}
Files discovered: {len(self.discovered_files)}
"""

    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate final results"""
        if not self.results.get('narrative'):
            # Fallback if no results generated
            return {
                'success': False,
                'answer': 'Analysis incomplete - insufficient data',
                'confidence': self.get_confidence('error'),
                'insights': self.insights,
                'files_analyzed': len(self.file_summaries)
            }

        return {
            'success': True,
            'answer': self.results['narrative'],
            'confidence': self.results['confidence'],
            'insights': self.insights,
            'files_analyzed': len(self.file_summaries),
            'key_files': self.results.get('key_files', []),
            'validation': self.results.get('validation', {}),
            'metrics': {
                'iterations': self.iteration,
                'files_discovered': len(self.discovered_files),
                'files_analyzed': len(self.file_summaries)
            }
        }
