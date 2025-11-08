"""
Analysis Pipeline for CodeFusion

Responsible for analyzing discovered files and extracting insights.
Supports parallel file processing and caching.
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


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


class AnalysisPipeline:
    """
    Main analysis pipeline that processes discovered files.
    Uses LLM to extract insights from each file.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], llm_client, repo_tools, cache):
        self.repo_path = repo_path
        self.config = config
        self.llm = llm_client
        self.repo_tools = repo_tools
        self.cache = cache

        # Metrics tracking
        self.file_analysis_metrics = []

    def analyze(self, file_paths: List[str], question: str) -> AnalysisResult:
        """
        Analyze a list of files with LLM

        Args:
            file_paths: List of file paths to analyze
            question: User's question for context-aware analysis

        Returns:
            AnalysisResult with file summaries and metrics
        """
        try:
            print(f"📄 [ANALYSIS] Analyzing {len(file_paths)} files...")

            file_summaries = {}
            total_tokens = 0
            cache_hits = 0
            cache_misses = 0
            start_time = time.time()

            for file_path in file_paths:
                try:
                    file_start = time.time()

                    # Check cache first
                    cache_key = f"file_analysis_{file_path}"
                    cached_summary = self.cache.get(cache_key)

                    if cached_summary:
                        print(f"✅ [ANALYSIS] Cache hit: {file_path}")
                        file_summaries[file_path] = cached_summary
                        cache_hits += 1
                        continue

                    cache_misses += 1

                    # Read file content
                    read_start = time.time()
                    file_result = self.repo_tools.execute('read_file', file_path=file_path, include_structure=True)
                    read_duration = time.time() - read_start

                    if file_result.get('error'):
                        print(f"❌ [ANALYSIS] Failed to read {file_path}: {file_result['error']}")
                        continue

                    # Generate LLM summary
                    llm_start = time.time()
                    summary, llm_metrics = self._generate_file_summary(file_path, file_result, question)
                    llm_duration = time.time() - llm_start

                    if summary:
                        file_summaries[file_path] = summary
                        self.cache.set(cache_key, summary)

                        total_tokens += llm_metrics.get('total_tokens', 0)

                        # Track metrics
                        self.file_analysis_metrics.append({
                            'file_path': file_path,
                            'read_duration_ms': round(read_duration * 1000, 2),
                            'llm_duration_ms': round(llm_duration * 1000, 2),
                            'total_duration_ms': round((time.time() - file_start) * 1000, 2),
                            'tokens': llm_metrics.get('total_tokens', 0),
                            'success': True
                        })

                        print(f"✅ [ANALYSIS] Analyzed {file_path} ({llm_duration*1000:.0f}ms, {llm_metrics.get('total_tokens', 0)} tokens)")

                except Exception as e:
                    print(f"❌ [ANALYSIS] Error analyzing {file_path}: {e}")
                    continue

            total_time = time.time() - start_time

            print(f"\n📊 [ANALYSIS] Summary:")
            print(f"   Files analyzed: {len(file_summaries)}/{len(file_paths)}")
            print(f"   Cache hits/misses: {cache_hits}/{cache_misses}")
            print(f"   Total time: {total_time*1000:.0f}ms")
            print(f"   Total tokens: {total_tokens}")

            return AnalysisResult(
                file_summaries=file_summaries,
                total_files_analyzed=len(file_summaries),
                total_analysis_time_ms=round(total_time * 1000, 2),
                total_tokens_used=total_tokens,
                cache_hits=cache_hits,
                cache_misses=cache_misses
            )

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

    def _generate_file_summary(self, file_path: str, file_result: Dict[str, Any], question: str) -> tuple:
        """
        Generate LLM summary for a single file

        Returns:
            (FileSummary, llm_metrics)
        """
        try:
            content = file_result.get('content', '')
            structure = file_result.get('structure', {})

            # Truncate very large files
            max_content_length = self.config.get('agents', {}).get('thresholds', {}).get('max_file_content_length', 3000)
            if len(content) > max_content_length:
                content = content[:max_content_length]

            # Build analysis prompt
            prompt = self._build_analysis_prompt(file_path, content, structure, question)

            # Call LLM (use fast model for file summaries)
            response = self.llm.generate_fast(prompt, "You are a code analysis expert. Extract key insights from code.")

            if response.get('success'):
                # Parse LLM response
                summary_data = self._parse_summary_response(response.get('content', ''))

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
                    cached=False
                )

                llm_metrics = {
                    'prompt_tokens': response.get('usage', {}).get('prompt_tokens', 0),
                    'completion_tokens': response.get('usage', {}).get('completion_tokens', 0),
                    'total_tokens': response.get('usage', {}).get('total_tokens', 0)
                }

                return summary, llm_metrics

        except Exception as e:
            print(f"⚠️ [ANALYSIS] Failed to generate summary for {file_path}: {e}")

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

Respond in JSON format:
{{
    "key_features": ["feature1", "feature2", "feature3"],
    "architectural_insights": "brief paragraph about architecture",
    "relevance": "how this relates to the question"
}}"""

        return prompt

    def _parse_summary_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON response from LLM"""
        import json

        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                json_content = content[start:end]
                return json.loads(json_content)
        except json.JSONDecodeError:
            pass

        # Fallback
        return {
            'key_features': [],
            'architectural_insights': 'Analysis failed',
            'relevance': 'Unknown'
        }
