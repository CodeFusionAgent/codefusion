"""
Discovery Strategies for CodeFusion
"""

from typing import Dict, List, Any, Optional
from cf.agents.pipelines.discovery import FileCandidate
from cf.agents.pipelines.discovery_strategies.discovery_strategy import DiscoveryStrategy
import json


class DomainDetectionStrategy(DiscoveryStrategy):
    """Uses LLM to detect domain and target directories"""

    def __init__(self, config: Dict[str, Any], llm_client, repo_tools, path_map: Dict[str, Any]):
        super().__init__(config)
        self.llm = llm_client
        self.repo_tools = repo_tools
        self.path_map = path_map

        # Load discovery config
        discovery_config = config.get('agents', {}).get('discovery', {})
        self.default_max_files = discovery_config.get('default_max_files', 50)
        self.max_directories_display = discovery_config.get('max_directories_display', 50)
        self.max_keyword_matched_dirs = discovery_config.get('max_keyword_matched_dirs', 5)
        self.max_matched_dirs_return = discovery_config.get('max_matched_dirs_return', 5)
        self.top_keywords_for_grep = discovery_config.get('top_keywords_for_grep', 3)
        self.relevance_increment = discovery_config.get('relevance_increment', 0.01)
        self.max_relevance_score = discovery_config.get('max_relevance_score', 0.9)
        self.truncate_tools_display = discovery_config.get('truncate_tools_display', 30)
        self.kb_query_max_results = discovery_config.get('kb_query_max_results', 100)
        self.similarity_to_relevance_factor = discovery_config.get('similarity_to_relevance_factor', 100)

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

        return f"Available directories:\n" + "\n".join(f"- {d}" for d in sorted(dirs)[:self.max_directories_display])

    def _build_domain_detection_prompt(self, question: str, repo_overview: str, context: Dict[str, Any]) -> str:
        """Build prompt for domain detection"""
        keyword_hint = ""
        if context.get('keyword_matched_dirs'):
            dirs = context['keyword_matched_dirs'][:self.max_keyword_matched_dirs]
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


