"""
CodeOrchestrator - Pipeline-based Code Analysis Agent

Clean orchestrator that coordinates specialized pipelines:
- Discovery: Find relevant files
- Analysis: Extract insights from files
- Validation: Ensure answer quality
- Synthesis: Generate technical narratives

This replaces the monolithic CodeAgent with a modular pipeline architecture.
"""

from typing import Dict, List, Any
from cf.agents.base import BaseAgent
from cf.agents.pipelines.discovery import DiscoveryPipeline
from cf.agents.pipelines.analysis import AnalysisPipeline
from cf.agents.pipelines.validation import ValidationPipeline
from cf.agents.pipelines.synthesis import SynthesisPipeline


class CodeOrchestrator(BaseAgent):
    """
    Orchestrates multiple pipelines for code analysis.

    Clean architecture with ~200 lines vs 4,375 in monolithic CodeAgent.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any]):
        super().__init__(repo_path, config, "code_orchestrator")

        # Initialize pipelines
        self.discovery = None
        self.analysis = None
        self.validation = None
        self.synthesis = None

        # State
        self.path_map = {}
        self.discovered_files = []
        self.file_summaries = {}

    def _analyze_step(self, question: str) -> str:
        """Execute one analysis step"""

        # Step 1: Initialize path map (first iteration only)
        if self.iteration == 1:
            return self._initialize_repository()

        # Step 2: Discover relevant files
        if self.iteration == 2:
            return self._discover_files(question)

        # Step 3: Analyze discovered files
        if self.iteration == 3:
            return self._analyze_files(question)

        # Step 4: Validate and complete
        if self.iteration >= 4:
            return self._finalize_analysis(question)

        return "unknown_step"

    def _initialize_repository(self) -> str:
        """Initialize repository scan and path map"""
        try:
            print("🔍 [ORCHESTRATOR] Scanning repository...")

            # Scan repository structure
            max_depth = self.config.get('repo', {}).get('max_scan_depth', 5)
            scan_result = self.use_tool('scan_directory', max_depth=max_depth)

            if scan_result.get('error'):
                print(f"❌ [ORCHESTRATOR] Scan failed: {scan_result['error']}")
                return "scan_failed"

            # Build path map
            self.path_map = {}
            for file_info in scan_result.get('files', []):
                path = file_info.get('path', '')
                self.path_map[path] = {
                    'is_dir': file_info.get('type') == 'directory',
                    'extension': file_info.get('extension', ''),
                    'size': file_info.get('size', 0)
                }

            # Initialize pipelines now that we have path_map
            self.discovery = DiscoveryPipeline(
                self.repo_path,
                self.config,
                self.llm,
                self.tools,
                self.path_map
            )
            self.analysis = AnalysisPipeline(
                self.repo_path,
                self.config,
                self.llm,
                self.tools,
                self.cache
            )
            self.validation = ValidationPipeline(
                self.repo_path,
                self.config,
                self.tools
            )
            self.synthesis = SynthesisPipeline(
                self.repo_path,
                self.config,
                self.llm
            )

            print(f"✅ [ORCHESTRATOR] Found {len(self.path_map)} paths")
            self.add_insight(
                f"Repository scanned: {len(self.path_map)} paths indexed",
                confidence=self.get_confidence('high'),
                source="repository_scan"
            )

            return "scan_complete"

        except Exception as e:
            print(f"❌ [ORCHESTRATOR] Initialization failed: {e}")
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

            # Store results
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
                    ]
                }
            }

            print(f"✅ [ORCHESTRATOR] Answer generated and validated")
            print(f"   Validation: {'✅ PASSED' if validation_result.valid else '⚠️ ISSUES FOUND'}")

            return "finalized"

        except Exception as e:
            print(f"❌ [ORCHESTRATOR] Finalization failed: {e}")
            return "finalization_failed"

    def _is_analysis_complete(self, question: str) -> bool:
        """Check if analysis is complete"""
        # Complete after finalization step
        return self.iteration >= 4 and self.results.get('narrative')

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
