"""
Discovery Pipeline for CodeFusion

Responsible for finding relevant files for a given question.
Uses multiple strategies: domain detection, keyword matching, grep search, fallback.
"""

import json
import traceback
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class FileCandidate:
    """Represents a candidate file with relevance information"""
    path: str
    relevance_score: float
    discovery_method: str
    file_type: str = 'production'  # 'production', 'test', or 'utility'
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DiscoveryResult:
    """
    Result of file discovery process.

    Includes standard success/error fields for consistent error handling.
    """
    files: List[FileCandidate]
    production_files: List[FileCandidate]  # Production code files
    test_files: List[FileCandidate]        # Test files (examples, validation)
    utility_files: List[FileCandidate]     # Utility/helper files
    domain_info: Dict[str, Any]
    strategies_used: List[str]
    total_candidates: int
    success: bool = True
    error: Optional[str] = None

    def get_top_files(self, n: int = 50, prioritize_production: bool = True) -> List[FileCandidate]:
        """
        Get top N files by relevance score.

        Args:
            n: Maximum number of files to return
            prioritize_production: If True, return production files first, then test, then utility

        Returns:
            List of top N FileCandidate objects
        """
        if prioritize_production:
            # Production files first (sorted by score), then test, then utility
            sorted_production = sorted(self.production_files, key=lambda f: f.relevance_score, reverse=True)
            sorted_test = sorted(self.test_files, key=lambda f: f.relevance_score, reverse=True)
            sorted_utility = sorted(self.utility_files, key=lambda f: f.relevance_score, reverse=True)

            combined = sorted_production + sorted_test + sorted_utility
            return combined[:n]
        else:
            sorted_files = sorted(self.files, key=lambda f: f.relevance_score, reverse=True)
            return sorted_files[:n]

# Import discovery strategies
from cf.agents.pipelines.discovery_strategies import (
    DiscoveryStrategy,
    DomainDetectionStrategy,
    KeywordMatchingStrategy,
    GrepSearchStrategy,
    GraphQueryStrategy,
    SemanticSearchStrategy,
    FallbackStrategy
)


class DiscoveryPipeline:
    """Main pipeline for discovering relevant files for a question"""

    def __init__(self, repo_path: str, config: Dict[str, Any], llm_client, repo_tools, path_map: Dict[str, Any], tool_registry=None):
        self.repo_path = repo_path
        self.config = config
        self.llm = llm_client
        self.repo_tools = repo_tools
        self.path_map = path_map
        self.tool_registry = tool_registry

        # Initialize strategies
        self.strategies = []

        # Add graph query strategy first if KB is enabled and available via tools
        kb_config = config.get('knowledge_base', {})
        discovery_config = kb_config.get('discovery', {})

        if (kb_config.get('enabled', False) and
            discovery_config.get('use_kb_queries', True) and
            tool_registry is not None):
            # GraphQueryStrategy is highest priority when KB tools are available
            self.strategies.append(GraphQueryStrategy(config, tool_registry))
            print("✅ [DISCOVERY] Enabled KB graph query strategy via tools (highest priority)")

        # Add standard strategies
        self.strategies.extend([
            KeywordMatchingStrategy(config, path_map),
            DomainDetectionStrategy(config, llm_client, repo_tools, path_map),
            GrepSearchStrategy(config, repo_tools),
        ])

        self.fallback = FallbackStrategy(config, repo_tools, path_map)

    def _classify_file_types_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """
        Classify files as production, test, or utility using LLM.

        Args:
            file_paths: List of file paths to classify

        Returns:
            Dictionary mapping file_path -> file_type ('production', 'test', 'utility')
        """
        if not file_paths:
            return {}

        # Build prompt for batch classification
        paths_str = "\n".join([f"- {path}" for path in file_paths])
        prompt = f"""Classify these file paths as production, test, or utility:

{paths_str}

Classifications:
- production: Main business logic, application code, core functionality
- test: Test files, specs, test utilities (these show concrete examples of execution flow)
- utility: Helpers, constants, config, serializers, factories, migrations, admin files

Respond with JSON only (one entry per file):
{{
  "path/to/file1.py": "production",
  "path/to/file2.py": "test",
  "path/to/file3.py": "utility"
}}"""

        try:
            # Use fast LLM for cost efficiency
            response = self.llm.generate(prompt, "You are classifying file types. Return only valid JSON.")

            if response.get('success'):
                content = response.get('content', '').strip()

                # Extract JSON
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    json_content = content[start:end]
                    classifications = json.loads(json_content)

                    # Validate all paths are classified
                    result = {}
                    for path in file_paths:
                        result[path] = classifications.get(path, 'production')  # Default to production

                    return result

        except Exception as e:
            print(f"⚠️ [DISCOVERY] File type classification failed: {e}")

        # Fallback: all files are production
        return {path: 'production' for path in file_paths}

    def discover(self, question: str, max_files: int = 50, question_context: Dict[str, Any] = None) -> DiscoveryResult:
        """
        Execute all discovery strategies and return ranked file candidates

        Args:
            question: The user's question
            max_files: Maximum number of files to return
            question_context: Optional LLM classification from supervisor (replaces hardcoded patterns)

        Returns:
            DiscoveryResult with ranked file candidates
        """
        context = {}

        # Add question context from supervisor (LLM classification) to eliminate hardcoded patterns
        if question_context:
            context['question_context'] = question_context

        all_candidates = []
        strategies_used = []

        # Execute each strategy
        for strategy in self.strategies:
            try:
                candidates = strategy.execute(question, context)
                if candidates:
                    all_candidates.extend(candidates)
                    strategies_used.append(strategy.__class__.__name__)
                    # Pass results to next strategy as context
                    context[strategy.__class__.__name__] = candidates
            except Exception as e:
                print(f"⚠️ [DISCOVERY] Strategy {strategy.__class__.__name__} failed: {e}")
                continue

        # If no candidates found, use fallback
        if not all_candidates:
            print("🔄 [DISCOVERY] Using fallback strategy")
            all_candidates = self.fallback.execute(question, context)
            strategies_used.append("FallbackStrategy")

        # Deduplicate and rank candidates
        unique_files = self._deduplicate_candidates(all_candidates)
        ranked_files = self._rank_candidates(unique_files)

        # Get top files first (before classification to avoid unnecessary LLM calls)
        top_files = ranked_files[:max_files]

        # Classify file types using LLM (batch classification for efficiency)
        file_paths = [f.path for f in top_files]
        classifications = self._classify_file_types_batch(file_paths)

        # Update file_type on each candidate
        for candidate in top_files:
            candidate.file_type = classifications.get(candidate.path, 'production')

        # Separate files by type
        production = [f for f in top_files if f.file_type == 'production']
        test = [f for f in top_files if f.file_type == 'test']
        utility = [f for f in top_files if f.file_type == 'utility']

        print(f"📊 [DISCOVERY] File breakdown: {len(production)} production, {len(test)} test, {len(utility)} utility")

        return DiscoveryResult(
            files=top_files,
            production_files=production,
            test_files=test,
            utility_files=utility,
            domain_info=context.get('domain_info', {}),
            strategies_used=strategies_used,
            total_candidates=len(all_candidates)
        )

    def expand(self, missing_components: List[str], current_files: List[str]) -> DiscoveryResult:
        """
        Expand file discovery based on missing components

        Args:
            missing_components: Components that were identified as missing
            current_files: Files already analyzed

        Returns:
            DiscoveryResult with additional file candidates
        """
        # Build expansion query from missing components
        expansion_query = " ".join(missing_components)

        # Use grep search to find files mentioning these components
        grep_strategy = GrepSearchStrategy(self.config, self.repo_tools)
        candidates = grep_strategy.execute(expansion_query, {'exclude_files': current_files})

        # Filter out already analyzed files
        new_candidates = [c for c in candidates if c.path not in current_files]

        # Classify file types using LLM
        if new_candidates:
            file_paths = [f.path for f in new_candidates]
            classifications = self._classify_file_types_batch(file_paths)

            # Update file_type on each candidate
            for candidate in new_candidates:
                candidate.file_type = classifications.get(candidate.path, 'production')

        # Separate files by type
        production = [f for f in new_candidates if f.file_type == 'production']
        test = [f for f in new_candidates if f.file_type == 'test']
        utility = [f for f in new_candidates if f.file_type == 'utility']

        return DiscoveryResult(
            files=new_candidates,
            production_files=production,
            test_files=test,
            utility_files=utility,
            domain_info={},
            strategies_used=['GrepSearchStrategy (expansion)'],
            total_candidates=len(new_candidates)
        )

    def _deduplicate_candidates(self, candidates: List[FileCandidate]) -> List[FileCandidate]:
        """Remove duplicate files, keeping highest relevance score"""
        seen = {}
        for candidate in candidates:
            if candidate.path not in seen or candidate.relevance_score > seen[candidate.path].relevance_score:
                seen[candidate.path] = candidate
        return list(seen.values())

    def _rank_candidates(self, candidates: List[FileCandidate]) -> List[FileCandidate]:
        """Rank candidates by relevance score"""
        return sorted(candidates, key=lambda c: c.relevance_score, reverse=True)
