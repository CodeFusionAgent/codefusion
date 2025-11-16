"""
Analysis Pipeline for CodeFusion

Responsible for analyzing discovered files and extracting insights.
Supports parallel file processing and caching.
"""

import json
import time
import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field

from cf.llm.model_tiers import ModelTier


@dataclass
class FileSummary:
    """Result of analyzing a single file"""
    path: str
    content: str
    key_features: List[str]
    architectural_insights: str
    functions: List[Dict[str, Any]]
    classes: List[Dict[str, Any]]
    dependencies: List[str]
    line_count: int
    analysis_time_ms: float
    file_type: str = 'production'  # 'production', 'test', or 'utility'
    relevance_to_question: float = 0.5  # 0.0-1.0 scale, how relevant file is to the question
    cached: bool = False


@dataclass
class AnalysisResult:
    """Result of analyzing multiple files"""
    file_summaries: Dict[str, FileSummary]
    total_files_analyzed: int
    total_analysis_time_ms: float
    total_tokens_used: int
    cache_hits: int
    cache_misses: int
    filtered_irrelevant: int = 0  # Count of files filtered due to low relevance
    failed_files: List[Dict[str, Any]] = field(default_factory=list)  # Files that failed analysis with error details


class AnalysisPipeline:
    """
    Main analysis pipeline that processes discovered files.
    Uses LLM to extract insights from each file.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], llm_client, repo_tools, cache, tiered_llm=None):
        self.repo_path = repo_path
        self.config = config
        self.llm = llm_client
        self.repo_tools = repo_tools
        self.cache = cache
        self.tiered_llm = tiered_llm  # Optional tiered LLM manager

        # Parallel processing config
        self.max_workers = config.get('agents', {}).get('parallel_workers', 10)
        self.initial_max_workers = self.max_workers  # Store initial value
        self.use_parallel = config.get('agents', {}).get('parallel_analysis', True)

        # Adaptive worker count (NEW)
        self.enable_adaptive_workers = config.get('agents', {}).get('enable_adaptive_workers', True)
        self.rate_limit_detections = 0  # Track consecutive rate limit errors
        self.min_workers = 1  # Minimum workers to use

        # Metrics tracking
        self.file_analysis_metrics = []

    def _adjust_workers_for_rate_limit(self):
        """
        Reduce worker count when rate limiting is detected.

        NEW: Adaptive worker count to prevent API throttling.
        """
        if not self.enable_adaptive_workers:
            return

        self.rate_limit_detections += 1

        if self.rate_limit_detections >= 2 and self.max_workers > self.min_workers:
            # Reduce workers by 50%
            new_workers = max(self.min_workers, self.max_workers // 2)
            print(f"⚠️ [ANALYSIS] Rate limiting detected, reducing workers: {self.max_workers} → {new_workers}")
            self.max_workers = new_workers

    def _reset_rate_limit_tracking(self):
        """Reset rate limit tracking after successful batch"""
        if self.rate_limit_detections > 0:
            self.rate_limit_detections = 0
            # Gradually increase workers back (by 1 each time)
            if self.max_workers < self.initial_max_workers:
                self.max_workers = min(self.initial_max_workers, self.max_workers + 1)
                print(f"✅ [ANALYSIS] No rate limiting, increasing workers to {self.max_workers}")

    def analyze(self, file_paths: List[str], question: str, file_types: Dict[str, str] = None) -> AnalysisResult:
        """
        Analyze a list of files with LLM (supports parallel processing)

        Args:
            file_paths: List of file paths to analyze
            question: User's question for context-aware analysis
            file_types: Optional dict mapping file_path -> file_type ('production', 'test', 'utility')

        Returns:
            AnalysisResult with file summaries and metrics
        """
        # Default to production if no file types provided
        if file_types is None:
            file_types = {path: 'production' for path in file_paths}
        try:
            print(f"📄 [ANALYSIS] Analyzing {len(file_paths)} files...")
            print(f"   Mode: {'Parallel' if self.use_parallel else 'Serial'} ({self.max_workers} workers)")

            start_time = time.time()

            # Choose processing mode - use config threshold instead of hardcoded value
            min_files_for_parallel = self.config.get('agents', {}).get('parallel_min_files', 3)
            if self.use_parallel and len(file_paths) > min_files_for_parallel:
                result = self._analyze_parallel(file_paths, question, file_types)
            else:
                result = self._analyze_serial(file_paths, question, file_types)

            total_time = time.time() - start_time

            # Filter out irrelevant files based on relevance score
            result = self._filter_by_relevance(result)

            print(f"\n📊 [ANALYSIS] Summary:")
            print(f"   Files analyzed: {result.total_files_analyzed}/{len(file_paths)}")
            print(f"   Cache hits/misses: {result.cache_hits}/{result.cache_misses}")
            if result.filtered_irrelevant > 0:
                print(f"   Filtered irrelevant: {result.filtered_irrelevant} files (low relevance)")
            if len(result.failed_files) > 0:
                print(f"   ⚠️  Failed analysis: {len(result.failed_files)} files")
                for failed in result.failed_files[:3]:  # Show first 3 failures
                    print(f"      - {failed['path']}: {failed['error'][:50]}...")
                if len(result.failed_files) > 3:
                    print(f"      ... and {len(result.failed_files) - 3} more")
            print(f"   Total time: {total_time*1000:.0f}ms")
            print(f"   Total tokens: {result.total_tokens_used}")
            print(f"   Speedup: {len(file_paths)/(total_time+0.001):.1f} files/sec")

            return result

        except Exception as e:
            print(f"❌ [ANALYSIS] Pipeline failed: {e}")
            return AnalysisResult(
                file_summaries={},
                total_files_analyzed=0,
                total_analysis_time_ms=0,
                total_tokens_used=0,
                cache_hits=0,
                cache_misses=0
            )

    def _analyze_serial(self, file_paths: List[str], question: str, file_types: Dict[str, str]) -> AnalysisResult:
        """Serial file analysis (original behavior)"""
        file_summaries = {}
        total_tokens = 0
        cache_hits = 0
        cache_misses = 0
        failed_files = []

        for file_path in file_paths:
            file_type = file_types.get(file_path, 'production')
            result = self._analyze_single_file(file_path, question, file_type)
            if result:
                # Ensure stored summary is a dict (not a FileSummary object)
                summary_obj = result['summary']
                file_summaries[result['path']] = summary_obj if isinstance(summary_obj, dict) else asdict(summary_obj)
                total_tokens += result['tokens']
                if result['cached']:
                    cache_hits += 1
                else:
                    cache_misses += 1
            else:
                # Track failed file
                failed_files.append({
                    'path': file_path,
                    'error': 'Analysis failed',
                    'file_type': file_type
                })

        return AnalysisResult(
            file_summaries=file_summaries,
            total_files_analyzed=len(file_summaries),
            total_analysis_time_ms=0,
            total_tokens_used=total_tokens,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            failed_files=failed_files
        )

    def _analyze_parallel(self, file_paths: List[str], question: str, file_types: Dict[str, str]) -> AnalysisResult:
        """Parallel file analysis using ThreadPoolExecutor"""
        file_summaries = {}
        total_tokens = 0
        cache_hits = 0
        cache_misses = 0
        failed_files = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all file analysis tasks with file types
            future_to_path = {
                executor.submit(self._analyze_single_file, path, question, file_types.get(path, 'production')): path
                for path in file_paths
            }

            # Collect results as they complete
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                file_type = file_types.get(path, 'production')

                try:
                    result = future.result()
                    if result:
                        summary_obj = result['summary']
                        file_summaries[result['path']] = summary_obj if isinstance(summary_obj, dict) else asdict(summary_obj)
                        total_tokens += result['tokens']
                        if result['cached']:
                            cache_hits += 1
                        else:
                            cache_misses += 1
                    else:
                        # Track when analysis returned None
                        failed_files.append({
                            'path': path,
                            'error': 'Analysis returned None',
                            'file_type': file_type
                        })
                except Exception as e:
                    print(f"❌ [ANALYSIS] Error analyzing {path}: {e}")

                    # Track failed file with error details
                    failed_files.append({
                        'path': path,
                        'error': str(e),
                        'file_type': file_type
                    })

                    # Check if it's a rate limit error (NEW)
                    error_str = str(e).lower()
                    if 'rate limit' in error_str or '429' in error_str or 'too many requests' in error_str:
                        self._adjust_workers_for_rate_limit()

        # Reset rate limit tracking if no issues detected (NEW)
        self._reset_rate_limit_tracking()

        return AnalysisResult(
            file_summaries=file_summaries,
            total_files_analyzed=len(file_summaries),
            total_analysis_time_ms=0,
            total_tokens_used=total_tokens,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            failed_files=failed_files
        )

    def _filter_by_relevance(self, result: AnalysisResult) -> AnalysisResult:
        """
        Filter out irrelevant files based on relevance score threshold.

        Args:
            result: AnalysisResult with all analyzed files

        Returns:
            AnalysisResult with only relevant files (relevance >= threshold)
        """
        # Get relevance threshold from config (default 0.3)
        threshold = self.config.get('agents', {}).get('thresholds', {}).get('min_relevance_score', 0.3)

        # Filter file summaries
        filtered_summaries = {}
        filtered_count = 0

        for path, summary in result.file_summaries.items():
            # Handle both dict and FileSummary object
            if isinstance(summary, dict):
                relevance = summary.get('relevance_to_question', 0.5)
            else:
                relevance = getattr(summary, 'relevance_to_question', 0.5)

            if relevance >= threshold:
                filtered_summaries[path] = summary
            else:
                filtered_count += 1
                print(f"   ⚠️ [ANALYSIS] Filtered {path} (relevance: {relevance:.2f} < {threshold})")

        # Return updated result (preserve failed_files from original result)
        return AnalysisResult(
            file_summaries=filtered_summaries,
            total_files_analyzed=result.total_files_analyzed,
            total_analysis_time_ms=result.total_analysis_time_ms,
            total_tokens_used=result.total_tokens_used,
            cache_hits=result.cache_hits,
            cache_misses=result.cache_misses,
            filtered_irrelevant=filtered_count,
            failed_files=result.failed_files  # Preserve failed files list
        )

    def _analyze_single_file(self, file_path: str, question: str, file_type: str = 'production') -> Optional[Dict[str, Any]]:
        """Analyze a single file (thread-safe)"""
        try:
            file_start = time.time()

            # Check cache first
            cache_key = f"file_analysis_{file_path}"
            cached_summary = self.cache.get(cache_key)

            if cached_summary:
                print(f"✅ [ANALYSIS] Cache hit: {file_path}")
                # Coerce cached summary to dict
                cached_dict = cached_summary if isinstance(cached_summary, dict) else asdict(cached_summary)
                # Update file_type to current value (in case file was reclassified)
                cached_dict['file_type'] = file_type
                return {
                    'path': file_path,
                    'summary': cached_dict,
                    'tokens': 0,
                    'cached': True
                }

            # Read file content
            file_result = self.repo_tools.execute('read_file', file_path=file_path, include_structure=True)

            if file_result.get('error'):
                print(f"❌ [ANALYSIS] Failed to read {file_path}: {file_result['error']}")
                return None

            # Generate LLM summary
            llm_start = time.time()
            summary, llm_metrics = self._generate_file_summary(file_path, file_result, question, file_type)
            llm_duration = time.time() - llm_start

            if summary:
                # Store dict in cache for consistent downstream handling
                self.cache.set(cache_key, asdict(summary))

                # Track metrics
                self.file_analysis_metrics.append({
                    'file_path': file_path,
                    'total_duration_ms': round((time.time() - file_start) * 1000, 2),
                    'llm_duration_ms': round(llm_duration * 1000, 2),
                    'tokens': llm_metrics.get('total_tokens', 0),
                    'success': True
                })

                print(f"✅ [ANALYSIS] Analyzed {file_path} ({llm_duration*1000:.0f}ms, {llm_metrics.get('total_tokens', 0)} tokens)")

                return {
                    'path': file_path,
                    'summary': summary,
                    'tokens': llm_metrics.get('total_tokens', 0),
                    'cached': False
                }

        except Exception as e:
            print(f"❌ [ANALYSIS] Error analyzing {file_path}: {e}")

        return None

    def _generate_file_summary(self, file_path: str, file_result: Dict[str, Any], question: str, file_type: str = 'production') -> tuple:
        """
        Generate LLM summary for a single file using fast tier model.

        Args:
            file_path: Path to the file
            file_result: File content and structure from repo_tools
            question: User's question for context
            file_type: Type of file ('production', 'test', 'utility')

        Returns:
            (FileSummary, llm_metrics)
        """
        try:
            content = file_result.get('content', '')
            structure_analysis = file_result.get('structure_analysis', {})

            # Transform components into functions and classes with line numbers
            components = structure_analysis.get('components', [])
            functions = [c for c in components if c.get('type') == 'function']
            classes = [c for c in components if c.get('type') == 'class']
            structure = {
                'functions': functions,
                'classes': classes,
                'dependencies': structure_analysis.get('imports', [])
            }

            # Truncate very large files
            max_content_length = self.config.get('agents', {}).get('thresholds', {}).get('max_file_content_length', 3000)
            if len(content) > max_content_length:
                content = content[:max_content_length]

            # Use TieredLLMManager if available (fast model for file summaries)
            if self.tiered_llm:
                response_text = self.tiered_llm.summarize_file(content, file_path, question)

                # Coerce response to string for token counts and parsing
                if isinstance(response_text, dict):
                    # Prefer 'content' field if present; otherwise serialize
                    raw = response_text.get('content') if 'content' in response_text else response_text
                    content_str = raw if isinstance(raw, str) else json.dumps(raw)
                else:
                    content_str = str(response_text)

                # DEBUG: Show raw LLM response for diagnosing parsing issues
                print(f"   [DEBUG ANALYSIS] Raw LLM response for {file_path}:")
                print(f"   [DEBUG ANALYSIS]   Length: {len(content_str)} chars")
                print(f"   [DEBUG ANALYSIS]   First 200 chars: {content_str[:200]}")

                # Parse response
                summary_data = self._parse_summary_response(content_str)

                # DEBUG: Show parsed result
                print(f"   [DEBUG ANALYSIS] Parsed summary_data:")
                print(f"   [DEBUG ANALYSIS]   key_features: {summary_data.get('key_features', [])[:2]}")
                print(f"   [DEBUG ANALYSIS]   architectural_insights: {summary_data.get('architectural_insights', '')[:100]}")

                # Estimate tokens (rough approximation) with safe coercion
                prompt_tokens = len(str(content).split()) + len(str(question).split()) + 100
                completion_tokens = len(str(content_str).split())

                llm_metrics = {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens
                }
            else:
                # Fallback to old method (with method existence check)
                prompt = self._build_analysis_prompt(file_path, content, structure, question)
                system_prompt = "You are a code analysis expert. Extract key insights from code."

                # Try generate_fast first, fall back to generate if not available
                if hasattr(self.llm, 'generate_fast'):
                    response = self.llm.generate_fast(prompt, system_prompt)
                else:
                    response = self.llm.generate(prompt, system_prompt)

                # Validate response
                if not response or not response.get('success'):
                    print(f"⚠️ [ANALYSIS] LLM generation failed for {file_path}")
                    return None, {}

                summary_data = self._parse_summary_response(response.get('content', ''))
                llm_metrics = {
                    'prompt_tokens': response.get('usage', {}).get('prompt_tokens', 0),
                    'completion_tokens': response.get('usage', {}).get('completion_tokens', 0),
                    'total_tokens': response.get('usage', {}).get('total_tokens', 0)
                }

            # Extract and validate relevance score
            relevance_score = summary_data.get('relevance_score', 0.5)
            # Ensure it's a valid float between 0 and 1
            try:
                relevance_score = float(relevance_score)
                relevance_score = max(0.0, min(1.0, relevance_score))
            except (TypeError, ValueError):
                relevance_score = 0.5  # Default if invalid

            summary = FileSummary(
                path=file_path,
                content=content,
                key_features=summary_data.get('key_features', []),
                architectural_insights=summary_data.get('architectural_insights', ''),
                functions=structure.get('functions', []),
                classes=structure.get('classes', []),
                dependencies=structure.get('dependencies', []),
                line_count=file_result.get('lines', 0),
                analysis_time_ms=0,  # Will be set by caller
                file_type=file_type,
                relevance_to_question=relevance_score,
                cached=False
            )

            # DEBUG: Show what structure data we have
            print(f"   [DEBUG] {file_path}")
            print(f"   [DEBUG]   Functions count: {len(structure.get('functions', []))}")
            if structure.get('functions'):
                sample_func = structure['functions'][0]
                print(f"   [DEBUG]   Sample function: {sample_func}")
            print(f"   [DEBUG]   Classes count: {len(structure.get('classes', []))}")
            if structure.get('classes'):
                sample_class = structure['classes'][0]
                print(f"   [DEBUG]   Sample class: {sample_class}")

            return summary, llm_metrics

        except Exception as e:
            print(f"⚠️ [ANALYSIS] Failed to generate summary for {file_path}: {traceback.format_exc()}")

        return None, {}

    def _build_analysis_prompt(self, file_path: str, content: str, structure: Dict[str, Any], question: str) -> str:
        """Build prompt for file analysis"""
        functions = structure.get('functions', [])
        classes = structure.get('classes', [])

        prompt = f"""Analyze this code file in the context of the question: "{question}"

FILE: {file_path}

STRUCTURE:
- Functions: {len(functions)} ({', '.join([f['name'] for f in functions[:5]])})
- Classes: {len(classes)} ({', '.join([c['name'] for c in classes[:5]])})

CODE (first {len(content)} chars):
```
{content}
```

Extract:
1. **Key Features**: 3-5 main features/responsibilities of this file
2. **Architectural Insights**: How does this file fit into the architecture? What patterns does it use?
3. **Relevance to Question**: How does this file relate to the question?
4. **Relevance Score**: Rate how relevant this file is to answering the question (0.0-1.0 scale)
   - 1.0 = Directly answers the question (core implementation)
   - 0.7 = Highly relevant (important supporting code)
   - 0.5 = Moderately relevant (related functionality)
   - 0.3 = Tangentially relevant (peripheral code)
   - 0.0 = Not relevant (unrelated to question)

Respond in JSON format:
{{
    "key_features": ["feature1", "feature2", "feature3"],
    "architectural_insights": "brief paragraph about architecture",
    "relevance": "how this relates to the question",
    "relevance_score": 0.8
}}"""

        return prompt

    def _parse_summary_response(self, content: Any) -> Dict[str, Any]:
        """Parse JSON response from LLM (accepts str or dict)."""
        # If already a dict, return as-is
        if isinstance(content, dict):
            return content
        try:
            text = str(content)
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                json_content = text[start:end]
                return json.loads(json_content)
        except json.JSONDecodeError as e:
            print(f"   ⚠️ [ANALYSIS] JSON parse failed: {e}")
            print(f"   [DEBUG ANALYSIS] Attempted to parse: {text[:300]}")

        # Fallback
        print(f"   ⚠️ [ANALYSIS] Using fallback response (no valid JSON found)")
        return {
            'key_features': [],
            'architectural_insights': 'Analysis failed - LLM did not return valid JSON',
            'relevance': 'Unknown',
            'relevance_score': 0.3  # Default to low relevance for failed parses
        }
