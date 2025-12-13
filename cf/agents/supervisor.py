"""
SupervisorAgent for CodeFusion

Orchestrates CodeAgent analysis with integrated post-processing:
- LLMToolSelector for question classification
- NarrativeGenerator for enhanced narrative synthesis
- FileAnalyzer for structural file analysis
- Validation for answer grounding and accuracy
"""

import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING

# CodeFusion imports
from cf.agents.base import BaseAgent
from cf.agents.code import CodeAgent
from cf.agents.protocols import AgentRegistry
from cf.tools.registry import ToolRegistry

# Advanced analysis modules (integrated features)
from cf.agents.tool_selector import LLMToolSelector, QuestionCategory
from cf.agents.narrative import (
    NarrativeGenerator, NarrativeStyle, NarrativeContext, QualityLevel
)
from cf.agents.file_analyzer import FileAnalyzer
from cf.agents.validation import validate_answer


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that orchestrates CodeAgent and applies post-processing.

    Uses ReAct-style analysis with:
    1. LLMToolSelector for intelligent question classification
    2. CodeAgent for the main analysis via ReAct loop
    3. FileAnalyzer for enriching file structural data
    4. NarrativeGenerator for enhanced narrative synthesis
    5. Validation for answer grounding and accuracy checks
    """

    agent_name: str = "supervisor"

    def __init__(self, repo_path: str, config: Dict[str, Any]):
        # Initialize shared tool/agent registry BEFORE calling super().__init__
        self._agent_registry = AgentRegistry()
        self._shared_tool_registry = ToolRegistry(repo_path, agent_registry=self._agent_registry)

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
        4. Enhance answer with NarrativeGenerator
        5. Validate final answer
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
        if result.get('success') and result.get('answer'):
            result = self._enhance_with_narrative(question, result, question_classification)

        # Step 5: Validate the final answer
        if result.get('success') and result.get('answer'):
            result = self._validate_answer(result)

        return result

    def _enrich_with_file_analysis(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich file data with FileAnalyzer (AST parsing, complexity metrics).

        This runs FileAnalyzer on analyzed files to gather structural information
        (functions, classes, imports, complexity) for richer narratives.
        """
        try:
            files_analyzed = result.get('files_analyzed', [])
            if not files_analyzed:
                return result

            self.logger.verbose(f"Enriching {len(files_analyzed)} files with FileAnalyzer", "🔬")

            file_summaries = result.get('file_summaries', {})
            enriched_count = 0

            # Use configurable limit for file enrichment
            max_enrich = self.config.get('agents', {}).get('max_files_to_enrich', 25)
            for file_path in files_analyzed[:max_enrich]:
                try:
                    # Analyze file with FileAnalyzer
                    analysis = self.file_analyzer.analyze_file(file_path)

                    if analysis:
                        # Enrich file_summaries with structural data
                        if file_path not in file_summaries:
                            file_summaries[file_path] = {}

                        file_summaries[file_path]['structure'] = {
                            'functions': len(analysis.functions) if hasattr(analysis, 'functions') else 0,
                            'classes': len(analysis.classes) if hasattr(analysis, 'classes') else 0,
                            'imports': len(analysis.imports) if hasattr(analysis, 'imports') else 0,
                            'complexity': getattr(analysis, 'complexity', None),
                            'category': getattr(analysis, 'category', None),
                        }
                        enriched_count += 1

                except Exception as e:
                    self.logger.debug(f"FileAnalyzer failed for {file_path}: {e}")
                    continue

            result['file_summaries'] = file_summaries
            self.logger.verbose(f"Enriched {enriched_count} files with structural data", "✅")

        except Exception as e:
            self.logger.debug(f"File enrichment failed: {e}, proceeding with basic data")

        return result

    def _follow_imports(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Follow imports from analyzed files to discover additional relevant files.

        This implements a second pass that:
        1. Extracts imports from already-analyzed files
        2. Resolves internal imports to actual file paths
        3. Analyzes newly discovered files with FileAnalyzer
        4. Adds them to the result for richer context

        This helps capture constants, mappings, and configurations that are
        imported from other files in the codebase.
        """
        try:
            files_analyzed = result.get('files_analyzed', [])
            file_summaries = result.get('file_summaries', {})

            if not files_analyzed:
                return result

            # Collect all imports from analyzed files
            all_imports = set()
            for file_path in files_analyzed:
                summary = file_summaries.get(file_path, {})
                structure = summary.get('structure', {})

                # Get imports count - if we have detailed import info, use it
                if 'imports' in structure and isinstance(structure['imports'], list):
                    all_imports.update(structure['imports'])

            # Also check FileAnalyzer results for detailed imports
            for file_path in files_analyzed:
                try:
                    # Re-analyze to get import details if not cached
                    analysis = self.file_analyzer.analyze_file(file_path)
                    if analysis and hasattr(analysis, 'imports'):
                        all_imports.update(analysis.imports)
                except Exception:
                    continue

            if not all_imports:
                return result

            # Resolve imports to file paths
            repo_path = Path(self.repo_path)
            new_files = []

            for import_name in all_imports:
                # Skip external packages (stdlib and third-party)
                if self._is_external_import(import_name):
                    continue

                # Try to resolve to a file path
                resolved_path = self._resolve_import_to_path(import_name, repo_path)
                if resolved_path and resolved_path not in files_analyzed:
                    new_files.append(resolved_path)

            if not new_files:
                return result

            # Limit number of new files to analyze
            max_import_follow = self.config.get('agents', {}).get('max_import_follow', 15)
            new_files = new_files[:max_import_follow]

            self.logger.verbose(f"Following imports: discovered {len(new_files)} additional files", "🔗")

            # Analyze new files with FileAnalyzer
            for file_path in new_files:
                try:
                    analysis = self.file_analyzer.analyze_file(file_path)
                    if analysis:
                        # Add to files_analyzed
                        files_analyzed.append(file_path)

                        # Add to file_summaries with structural data
                        file_summaries[file_path] = {
                            'source': 'import_follow',
                            'structure': {
                                'functions': len(analysis.functions) if hasattr(analysis, 'functions') else 0,
                                'classes': len(analysis.classes) if hasattr(analysis, 'classes') else 0,
                                'imports': len(analysis.imports) if hasattr(analysis, 'imports') else 0,
                                'constants': getattr(analysis, 'constants', []),
                                'constant_details': [
                                    {
                                        'name': c.name,
                                        'value_repr': c.value_repr,
                                        'is_dict': c.is_dict,
                                        'is_list': c.is_list
                                    }
                                    for c in getattr(analysis, 'constant_details', [])
                                ],
                                'complexity': getattr(analysis, 'complexity', None),
                            }
                        }
                except Exception as e:
                    self.logger.debug(f"Failed to analyze imported file {file_path}: {e}")
                    continue

            result['files_analyzed'] = files_analyzed
            result['file_summaries'] = file_summaries
            result['import_followed_count'] = len(new_files)

            self.logger.verbose(f"Import following complete: added {len(new_files)} files", "✅")

        except Exception as e:
            self.logger.debug(f"Import following failed: {e}, proceeding with original files")

        return result

    def _is_external_import(self, import_name: str) -> bool:
        """Check if an import is external (stdlib or third-party).

        Uses sys.stdlib_module_names (Python 3.10+) for accurate stdlib detection,
        with a configurable third-party packages list from config.
        """
        first_part = import_name.split('.')[0]

        # Check Python standard library (Python 3.10+)
        if hasattr(sys, 'stdlib_module_names'):
            if first_part in sys.stdlib_module_names:
                return True

        # Get third-party packages from config (or use defaults)
        third_party_defaults = {
            # Web frameworks
            'django', 'flask', 'fastapi', 'starlette', 'tornado', 'aiohttp',
            # Task queues & caching
            'celery', 'redis', 'kombu', 'rq',
            # HTTP clients
            'requests', 'httpx', 'aiohttp', 'urllib3',
            # Data science
            'numpy', 'pandas', 'scipy', 'sklearn', 'tensorflow', 'torch', 'keras',
            # Testing
            'pytest', 'mock', 'unittest2', 'nose', 'coverage',
            # Cloud SDKs
            'boto3', 'botocore', 'aws', 'google', 'azure',
            # AI/LLM
            'openai', 'anthropic', 'litellm', 'langchain', 'transformers',
            # ORM & databases
            'pydantic', 'sqlalchemy', 'mongoengine', 'peewee', 'psycopg2', 'pymongo',
            # Django extras
            'rest_framework', 'corsheaders', 'whitenoise', 'gunicorn', 'dj_database_url',
            # Utilities
            'sentry_sdk', 'stripe', 'twilio', 'sendgrid', 'PIL', 'cv2', 'click', 'rich',
            # Serialization
            'yaml', 'toml', 'msgpack', 'orjson',
        }

        # Allow config override
        third_party = self.config.get('agents', {}).get('third_party_packages', third_party_defaults)
        if isinstance(third_party, list):
            third_party = set(third_party)

        return first_part in third_party

    def _resolve_import_to_path(self, import_name: str, repo_path: Path) -> Optional[str]:
        """Resolve an import name to a file path in the repo."""
        # Convert import to potential file paths
        # e.g., "app.models" -> "app/models.py" or "app/models/__init__.py"
        parts = import_name.split('.')

        # Try as a module file
        module_path = repo_path / '/'.join(parts[:-1]) / f"{parts[-1]}.py" if len(parts) > 1 else repo_path / f"{parts[0]}.py"
        if module_path.exists():
            return str(module_path)

        # Try as a package __init__.py
        package_path = repo_path / '/'.join(parts) / '__init__.py'
        if package_path.exists():
            return str(package_path)

        # Try direct path conversion
        direct_path = repo_path / f"{'/'.join(parts)}.py"
        if direct_path.exists():
            return str(direct_path)

        # Try common Django patterns (app/module.py)
        if len(parts) >= 2:
            django_path = repo_path / parts[0] / f"{parts[-1]}.py"
            if django_path.exists():
                return str(django_path)

        return None

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

            # Map question category to narrative style
            style = self._map_category_to_style(classification)

            # Build NarrativeContext from CodeAgent result
            context = NarrativeContext(
                question=question,
                files_analyzed=result.get('files_analyzed', []),
                file_summaries=result.get('file_summaries', {}),
                agent_results={'code': result},
                code_snippets=result.get('code_snippets', {}),
                execution_time=result.get('execution_time', 0.0)
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
                self.logger.verbose(
                    f"Narrative generated: style={style.value}, confidence={narrative_result.confidence:.2f}",
                    "✅"
                )

        except Exception as e:
            self.logger.debug(f"NarrativeGenerator enhancement failed: {e}, using original answer")

        return result

    def _map_category_to_style(self, classification: Optional[Any]) -> NarrativeStyle:
        """Map LLMToolSelector's question category to NarrativeStyle."""
        if not classification:
            return NarrativeStyle.EXPLANATION

        category_map = {
            QuestionCategory.LOOKUP: NarrativeStyle.EXPLANATION,
            QuestionCategory.FLOW: NarrativeStyle.LIFE_OF_X,
            QuestionCategory.ARCHITECTURE: NarrativeStyle.ARCHITECTURE,
            QuestionCategory.EXPLANATION: NarrativeStyle.EXPLANATION,
            QuestionCategory.COMPARISON: NarrativeStyle.COMPARISON,
            QuestionCategory.DEBUGGING: NarrativeStyle.DEBUG_TRACE,
            QuestionCategory.DOCUMENTATION: NarrativeStyle.API_REFERENCE,
            QuestionCategory.PERFORMANCE: NarrativeStyle.EXPLANATION,
            QuestionCategory.SECURITY: NarrativeStyle.EXPLANATION,
            QuestionCategory.REFACTORING: NarrativeStyle.EXPLANATION,
        }

        return category_map.get(classification.category, NarrativeStyle.EXPLANATION)

    def _validate_answer(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the final answer using the validation module.

        Performs structural validation (file paths, line numbers),
        content validation (grounding), and fact verification.
        """
        try:
            self.logger.verbose("Validating answer for grounding and accuracy", "🔍")

            answer = result.get('answer', '')
            file_summaries = result.get('file_summaries', {})

            # Run validation
            validation_result = validate_answer(
                answer=answer,
                file_summaries=file_summaries,
                config=self.config,
                repo_tools=None,  # Will use validation module's built-in tools
                llm_client=None   # Optional: can pass self.llm for fact verification
            )

            # Add validation results to output
            if validation_result:
                result['validation'] = {
                    'grounding_score': validation_result.get('grounding_score', 0.0),
                    'path_accuracy': validation_result.get('path_accuracy', 0.0),
                    'line_coverage': validation_result.get('line_number_coverage', 0.0),
                    'issues': validation_result.get('issues', []),
                    'validated': validation_result.get('validated', False)
                }

                score = validation_result.get('grounding_score', 0.0)
                self.logger.verbose(
                    f"Validation complete: grounding_score={score:.2f}",
                    "✅" if score > 0.7 else "⚠️"
                )

        except Exception as e:
            self.logger.debug(f"Validation failed: {e}, proceeding without validation")

        return result

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
