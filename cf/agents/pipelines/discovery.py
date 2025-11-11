"""
Discovery Pipeline for CodeFusion

Responsible for finding relevant files for a given question.
Uses multiple strategies: domain detection, keyword matching, grep search, fallback.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileCandidate:
    """Represents a candidate file with relevance information"""
    path: str
    relevance_score: float
    discovery_method: str
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
    domain_info: Dict[str, Any]
    strategies_used: List[str]
    total_candidates: int
    success: bool = True
    error: Optional[str] = None

    def get_top_files(self, n: int = 50) -> List[FileCandidate]:
        """Get top N files by relevance score"""
        sorted_files = sorted(self.files, key=lambda f: f.relevance_score, reverse=True)
        return sorted_files[:n]


class DiscoveryStrategy:
    """Base class for file discovery strategies"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Execute discovery strategy and return candidates"""
        raise NotImplementedError


class DomainDetectionStrategy(DiscoveryStrategy):
    """Uses LLM to detect domain and target directories"""

    def __init__(self, config: Dict[str, Any], llm_client, repo_tools, path_map: Dict[str, Any]):
        super().__init__(config)
        self.llm = llm_client
        self.repo_tools = repo_tools
        self.path_map = path_map

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Detect domain and find files in target directories"""
        try:
            # Get repository overview
            repo_overview = self._get_repository_overview()

            # Build prompt for domain detection
            prompt = self._build_domain_detection_prompt(question, repo_overview, context)

            # Call LLM for domain detection
            response = self.llm.generate(prompt, "You are a code analysis expert identifying relevant code subsystems.")

            if response.get('success'):
                content = response.get('content', '').strip()
                domain_info = self._parse_domain_response(content)

                if domain_info and domain_info.get('target_directories'):
                    print(f"✅ [DOMAIN_DETECTION] Domain: {domain_info.get('domain', 'unknown')}")
                    print(f"   Target directories: {domain_info.get('target_directories', [])}")

                    # Find files in target directories
                    candidates = self._get_files_from_directories(domain_info['target_directories'])

                    # Store domain info in context for other strategies
                    context['domain_info'] = domain_info

                    return candidates

        except Exception as e:
            print(f"⚠️ [DOMAIN_DETECTION] Failed: {e}")

        return []

    def _get_repository_overview(self) -> str:
        """Get overview of repository structure"""
        if not self.path_map:
            return "Repository structure not available."

        # Get all directories
        dirs = [p for p, meta in self.path_map.items() if meta.get('is_dir')]

        return f"Available directories:\n" + "\n".join(f"- {d}" for d in sorted(dirs)[:50])

    def _build_domain_detection_prompt(self, question: str, repo_overview: str, context: Dict[str, Any]) -> str:
        """Build prompt for domain detection"""
        keyword_hint = ""
        if context.get('keyword_matched_dirs'):
            dirs = context['keyword_matched_dirs'][:5]
            keyword_hint = f"\nKeyword-matched directories (prioritize these): {', '.join(dirs)}\n"

        return f"""Analyze this question about a codebase: "{question}"
{keyword_hint}

{repo_overview}

Your task: Identify which subsystem/domain of the codebase this question is about and select the MOST RELEVANT directories.

Respond with JSON only:
{{
    "domain": "brief domain name (e.g., 'database-layer', 'authentication', 'routing')",
    "target_directories": ["exact/path/from/list/", "another/exact/path/"],
    "priority_files": ["specific_file.ext"],
    "external_systems": []
}}

CRITICAL RULES:
1. target_directories MUST be copied EXACTLY from the directory list shown above
2. DO NOT modify, abbreviate, or create new paths
3. Select 2-5 most relevant directories that likely contain the implementation
4. Focus on CORE IMPLEMENTATION directories (where the main logic lives)
5. AVOID test directories, examples, build output, vendor code, and documentation"""

    def _parse_domain_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from LLM with validation"""
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                json_content = content[start:end]

                # Validate JSON size to prevent DoS
                max_json_size = self.config.get('agents', {}).get('max_llm_json_size', 10000)
                if len(json_content) > max_json_size:
                    print(f"⚠️ [DOMAIN_DETECTION] JSON response too large: {len(json_content)} chars (max: {max_json_size})")
                    return None

                # Parse JSON
                result = json.loads(json_content)

                # Validate structure
                if not isinstance(result, dict):
                    print(f"⚠️ [DOMAIN_DETECTION] Invalid JSON type: {type(result)}")
                    return None

                return result
        except json.JSONDecodeError as e:
            print(f"⚠️ [DOMAIN_DETECTION] Failed to parse JSON: {e}")
        except Exception as e:
            print(f"⚠️ [DOMAIN_DETECTION] Unexpected error parsing JSON: {e}")
        return None

    def _get_files_from_directories(self, directories: List[str]) -> List[FileCandidate]:
        """Get all source files from target directories"""
        candidates = []
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        high_relevance = thresholds.get('high_relevance', 0.95)

        for dir_path in directories:
            # Find all files in this directory
            dir_files = [path for path, meta in self.path_map.items()
                        if path.startswith(dir_path) and not meta.get('is_dir')]

            for file_path in dir_files:
                candidates.append(FileCandidate(
                    path=file_path,
                    relevance_score=high_relevance,
                    discovery_method="domain_detection",
                    metadata={'directory': dir_path}
                ))

        return candidates


class KeywordMatchingStrategy(DiscoveryStrategy):
    """Finds directories by keyword matching"""

    def __init__(self, config: Dict[str, Any], path_map: Dict[str, Any]):
        super().__init__(config)
        self.path_map = path_map

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Match keywords from question to directory names"""
        try:
            # Extract keywords from question
            question_lower = question.lower()
            words = [w.strip('?.,!:;') for w in question_lower.split()]
            min_len = self.config.get('agents', {}).get('thresholds', {}).get('min_keyword_length', 4)
            keywords = [w for w in words if len(w) > min_len]

            if not keywords:
                return []

            # Get all directories
            all_dirs = set()
            for path, metadata in self.path_map.items():
                if metadata.get('is_dir'):
                    all_dirs.add(path)

            # Score directories by keyword match quality
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            score_exact = thresholds.get('score_exact_match', 100)
            score_partial = thresholds.get('score_partial_match', 50)
            score_plural = thresholds.get('score_plural_match', 80)
            score_substring = thresholds.get('score_substring_match', 30)

            scored_dirs = []
            for dir_path in all_dirs:
                dir_name = dir_path.rstrip('/').split('/')[-1].lower()
                score = 0

                # Check each keyword
                for keyword in keywords:
                    # Exact match (highest score)
                    if keyword == dir_name:
                        score += score_exact
                    # Directory name contains keyword
                    elif keyword in dir_name:
                        score += score_partial
                    # Keyword is pluralized version or vice versa
                    elif (keyword + 's' == dir_name or keyword + 'es' == dir_name or
                          dir_name + 's' == keyword or dir_name + 'es' == keyword):
                        score += score_plural
                    # Partial match (keyword is substring)
                    elif keyword in dir_name or dir_name in keyword:
                        score += score_substring

                if score > 0:
                    scored_dirs.append((dir_path, score))

            # Sort by score descending
            scored_dirs.sort(key=lambda x: x[1], reverse=True)

            # Return top matches
            matched = [d[0] for d in scored_dirs[:5]]

            if matched:
                print(f"🔍 [KEYWORD_MATCH] Found directories for keywords {keywords}: {matched}")
                # Store in context for domain detection
                context['keyword_matched_dirs'] = matched

            # Get files from matched directories
            candidates = []
            medium_relevance = thresholds.get('medium_relevance', 0.9)

            for dir_path in matched:
                dir_files = [path for path, meta in self.path_map.items()
                            if path.startswith(dir_path) and not meta.get('is_dir')]

                for file_path in dir_files:
                    candidates.append(FileCandidate(
                        path=file_path,
                        relevance_score=medium_relevance,
                        discovery_method="keyword_matching",
                        metadata={'directory': dir_path, 'keywords': keywords}
                    ))

            return candidates

        except Exception as e:
            print(f"⚠️ [KEYWORD_MATCH] Failed: {e}")
            return []


class GrepSearchStrategy(DiscoveryStrategy):
    """Uses grep to find files with relevant content"""

    def __init__(self, config: Dict[str, Any], repo_tools):
        super().__init__(config)
        self.repo_tools = repo_tools

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Search file contents for question keywords"""
        try:
            # Extract keywords from question
            question_lower = question.lower()
            words = [w.strip('?.,!:;') for w in question_lower.split()]
            min_len = self.config.get('agents', {}).get('thresholds', {}).get('min_keyword_length', 3)
            keywords = [w for w in words if len(w) > min_len]

            if not keywords:
                return []

            # Search for each keyword
            candidates = []
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            low_relevance = thresholds.get('low_relevance', 0.7)
            grep_multiplier = thresholds.get('score_grep_multiplier', 5)

            # Limit to top keywords to avoid too many searches
            top_keywords = keywords[:3]

            for keyword in top_keywords:
                try:
                    # Use search_files tool to grep for keyword
                    search_result = self.repo_tools.execute('search_files', pattern=keyword)

                    if search_result.get('success') and search_result.get('matches'):
                        matches = search_result['matches']
                        print(f"🔍 [GREP_SEARCH] Found {len(matches)} matches for '{keyword}'")

                        for match in matches:
                            file_path = match.get('file')
                            match_count = match.get('count', 1)

                            # Score based on match count
                            relevance = min(low_relevance + (match_count * 0.01), 0.9)

                            candidates.append(FileCandidate(
                                path=file_path,
                                relevance_score=relevance,
                                discovery_method="grep_search",
                                metadata={'keyword': keyword, 'match_count': match_count}
                            ))

                except Exception as e:
                    print(f"⚠️ [GREP_SEARCH] Failed for keyword '{keyword}': {e}")
                    continue

            return candidates

        except Exception as e:
            print(f"⚠️ [GREP_SEARCH] Failed: {e}")
            return []


class GraphQueryStrategy(DiscoveryStrategy):
    """
    Uses structural knowledge base graph queries for file discovery.

    UPDATED: Now uses tool_registry instead of direct pipeline access.
    Enforces tool-first design pattern.
    """

    def __init__(self, config: Dict[str, Any], tool_registry):
        super().__init__(config)
        self.tool_registry = tool_registry

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Query KB graph for relevant files using tool registry"""
        try:
            if not self.tool_registry:
                print("⚠️ [GRAPH_QUERY] Tool registry not available, skipping")
                return []

            print("🔍 [GRAPH_QUERY] Querying knowledge base via tools...")

            # Extract LLM question classification from supervisor (if available)
            question_context = context.get('question_context', {})

            # Use tool registry to call KB discovery tool
            # Tool name: structural_kb_find_files_for_question (prefixed by registry)
            result = self.tool_registry.execute(
                'structural_kb_find_files_for_question',
                question=question,
                max_results=100,
                question_context=question_context  # Pass LLM classification
            )

            if not result.get('success'):
                error = result.get('error', 'Unknown error')
                print(f"⚠️ [GRAPH_QUERY] KB tool failed: {error}")
                return []

            file_paths = result.get('file_paths', [])

            if not file_paths:
                print("⚠️ [GRAPH_QUERY] No files found via graph queries")
                return []

            # Convert to FileCandidate objects
            candidates = []
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            high_relevance = thresholds.get('high_relevance', 0.95)

            for file_path in file_paths:
                candidates.append(FileCandidate(
                    path=file_path,
                    relevance_score=high_relevance,  # KB queries are highly relevant
                    discovery_method="graph_query_tool",  # Updated to indicate tool usage
                    metadata={'query_type': 'structural_kb', 'via_tools': True}
                ))

            print(f"✅ [GRAPH_QUERY] Found {len(candidates)} files via KB tools")
            return candidates

        except Exception as e:
            print(f"⚠️ [GRAPH_QUERY] Failed: {e}")
            import traceback
            traceback.print_exc()
            return []


class SemanticSearchStrategy(DiscoveryStrategy):
    """
    Semantic similarity search strategy using code embeddings.

    NEW: Finds files based on semantic similarity rather than just keywords.
    Example: "authentication" will find "login", "credentials", "session" files.
    """

    def __init__(self, config: Dict[str, Any], kb_client=None):
        super().__init__(config)
        self.kb = kb_client

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Find files using semantic similarity search"""
        try:
            if not self.kb:
                print("⚠️ [SEMANTIC_SEARCH] KB not available, skipping")
                return []

            # Check if KB has semantic search capability
            if not hasattr(self.kb, 'semantic_search'):
                print("⚠️ [SEMANTIC_SEARCH] KB does not support semantic search")
                return []

            print("🔍 [SEMANTIC_SEARCH] Finding semantically similar files...")

            # Perform semantic search
            top_k = self.config.get('agents', {}).get('semantic_search_top_k', 20)
            results = self.kb.semantic_search(question, top_k=top_k)

            if not results:
                print("⚠️ [SEMANTIC_SEARCH] No results found")
                return []

            # Convert to FileCandidate objects
            candidates = []
            thresholds = self.config.get('agents', {}).get('thresholds', {})

            for result in results:
                # Result format: {'file_path': str, 'similarity': float, 'snippet': str}
                file_path = result.get('file_path', '')
                similarity = result.get('similarity', 0.0)

                if not file_path:
                    continue

                # Map similarity (0-1) to relevance score (0-100)
                relevance = similarity * 100

                # Only include if above minimum threshold
                min_similarity = self.config.get('agents', {}).get('min_semantic_similarity', 0.5)
                if similarity >= min_similarity:
                    candidates.append(FileCandidate(
                        path=file_path,
                        relevance_score=relevance,
                        discovery_method="semantic_search",
                        metadata={
                            'similarity': similarity,
                            'snippet': result.get('snippet', '')[:200]
                        }
                    ))

            print(f"✅ [SEMANTIC_SEARCH] Found {len(candidates)} semantically similar files")
            return candidates

        except Exception as e:
            print(f"⚠️ [SEMANTIC_SEARCH] Failed: {e}")
            import traceback
            traceback.print_exc()
            return []


class FallbackStrategy(DiscoveryStrategy):
    """Fallback strategy when other strategies find nothing"""

    def __init__(self, config: Dict[str, Any], repo_tools, path_map: Dict[str, Any]):
        super().__init__(config)
        self.repo_tools = repo_tools
        self.path_map = path_map

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Use generic patterns to find files"""
        try:
            print("🔄 [FALLBACK] Using generic file discovery")

            # Get all source files from path_map
            candidates = []
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            minimal_relevance = thresholds.get('minimal_relevance', 0.5)

            # Get source code extensions from config
            repo_config = self.config.get('repo', {})
            source_extensions = set(repo_config.get('source_code_extensions', []))

            for path, metadata in self.path_map.items():
                if metadata.get('is_dir'):
                    continue

                # Check if it's a source file
                ext = path.split('.')[-1] if '.' in path else ''
                if ext in source_extensions:
                    candidates.append(FileCandidate(
                        path=path,
                        relevance_score=minimal_relevance,
                        discovery_method="fallback",
                        metadata={'extension': ext}
                    ))

            # Limit to prevent overwhelming analysis
            max_fallback_files = self.config.get('agents', {}).get('max_fallback_files', 100)
            if len(candidates) > max_fallback_files:
                print(f"⚠️ [FALLBACK] Limiting to {max_fallback_files} files (found {len(candidates)})")
                candidates = candidates[:max_fallback_files]

            print(f"✅ [FALLBACK] Found {len(candidates)} source files")
            return candidates

        except Exception as e:
            print(f"⚠️ [FALLBACK] Failed: {e}")
            return []


class DiscoveryPipeline:
    """
    Main discovery pipeline that orchestrates multiple strategies
    to find relevant files for a question.

    UPDATED: Now uses tool_registry instead of direct structural_pipeline access.
    Enforces tool-first design pattern.
    """

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

        return DiscoveryResult(
            files=ranked_files[:max_files],
            domain_info=context.get('DomainDetectionStrategy', {}),
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

        return DiscoveryResult(
            files=new_candidates,
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
