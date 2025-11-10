"""
Configuration Service

Provides centralized, validated access to configuration values.
Eliminates scattered config.get() chains throughout the codebase.
"""

from typing import Any, Dict, Optional
from pathlib import Path


class ConfigService:
    """
    Centralized configuration access with validation and defaults.

    Benefits:
    - Single source of truth for config access
    - Type-safe access methods
    - Built-in validation
    - Clear error messages for missing/invalid config

    Example:
        >>> config_service = ConfigService(config_dict)
        >>> min_confidence = config_service.get_threshold('min_confidence')
        >>> timeout = config_service.get_agent_setting('timeout', default=300)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize config service.

        Args:
            config: Raw configuration dictionary (from YAML)
        """
        self.config = config or {}
        self._validate_config()

    def _validate_config(self):
        """Validate configuration has required sections"""
        required_sections = ['llm', 'agents', 'cache', 'trace', 'logging', 'repo']

        missing_sections = [s for s in required_sections if s not in self.config]
        if missing_sections:
            print(f"⚠️ Configuration missing sections: {', '.join(missing_sections)}")
            # Add empty sections for missing ones
            for section in missing_sections:
                self.config[section] = {}

    # Agent Settings
    def get_agent_setting(self, key: str, default: Any = None) -> Any:
        """Get agent configuration value"""
        return self.config.get('agents', {}).get(key, default)

    def get_max_iterations(self) -> int:
        """Get maximum agent iterations"""
        return self.get_agent_setting('max_iterations', 20)

    def get_agent_timeout(self) -> int:
        """Get agent timeout in seconds"""
        return self.get_agent_setting('timeout', 300)

    def get_max_files_to_analyze(self) -> int:
        """Get maximum files for analysis"""
        return self.get_agent_setting('max_files_to_analyze', 50)

    # Threshold Settings
    def get_threshold(self, key: str, default: float = 0.5) -> float:
        """Get threshold value"""
        return self.config.get('agents', {}).get('thresholds', {}).get(key, default)

    def get_min_confidence(self) -> float:
        """Get minimum confidence threshold"""
        return self.get_threshold('min_confidence', 0.3)

    def get_high_confidence(self) -> float:
        """Get high confidence threshold"""
        return self.get_threshold('high_confidence', 0.8)

    def get_medium_confidence(self) -> float:
        """Get medium confidence threshold"""
        return self.get_threshold('medium_confidence', 0.7)

    def get_min_insights_for_pass(self) -> int:
        """Get minimum insights required before moving to next pass"""
        return int(self.get_threshold('min_insights_for_pass', 2))

    # Synthesis Settings
    def get_synthesis_setting(self, key: str, default: Any = None) -> Any:
        """Get synthesis configuration value"""
        return self.config.get('agents', {}).get('synthesis', {}).get(key, default)

    def get_target_narrative_min(self) -> int:
        """Get minimum target narrative word count"""
        return self.get_synthesis_setting('target_narrative_min', 3000)

    def get_target_narrative_max(self) -> int:
        """Get maximum target narrative word count"""
        return self.get_synthesis_setting('target_narrative_max', 5000)

    def get_max_key_files_cited(self) -> int:
        """Get maximum key files to cite"""
        return self.get_synthesis_setting('max_key_files_cited', 7)

    def get_min_key_files_cited(self) -> int:
        """Get minimum key files to cite"""
        return self.get_synthesis_setting('min_key_files_cited', 3)

    # Synthesis Threshold Settings
    def get_synthesis_threshold(self, key: str, default: Any = None) -> Any:
        """Get synthesis threshold value"""
        return self.config.get('agents', {}).get('synthesis_thresholds', {}).get(key, default)

    def get_word_count_tolerance(self) -> float:
        """Get word count tolerance (0.8 = accept if >= 80% of target)"""
        return self.get_synthesis_threshold('word_count_tolerance', 0.8)

    def get_line_refs_high(self) -> int:
        """Get high quality line reference count"""
        return self.get_synthesis_threshold('line_refs_high', 5)

    def get_line_refs_medium(self) -> int:
        """Get medium quality line reference count"""
        return self.get_synthesis_threshold('line_refs_medium', 3)

    def get_path_refs_high(self) -> int:
        """Get high quality path reference count"""
        return self.get_synthesis_threshold('path_refs_high', 5)

    def get_path_refs_medium(self) -> int:
        """Get medium quality path reference count"""
        return self.get_synthesis_threshold('path_refs_medium', 3)

    def get_code_blocks_min(self) -> int:
        """Get minimum code blocks for bonus"""
        return self.get_synthesis_threshold('code_blocks_min', 4)

    # Parallel Processing Settings
    def is_parallel_analysis_enabled(self) -> bool:
        """Check if parallel analysis is enabled"""
        return self.get_agent_setting('parallel_analysis', True)

    def get_parallel_workers(self) -> int:
        """Get number of parallel workers"""
        return self.get_agent_setting('parallel_workers', 10)

    def get_parallel_min_files(self) -> int:
        """Get minimum files to enable parallel processing"""
        return self.get_agent_setting('parallel_min_files', 3)

    # LLM Settings
    def get_llm_setting(self, key: str, default: Any = None) -> Any:
        """Get LLM configuration value"""
        return self.config.get('llm', {}).get(key, default)

    def get_llm_model(self) -> str:
        """Get primary LLM model"""
        return self.get_llm_setting('model', 'gpt-4o')

    def get_max_tokens(self) -> int:
        """Get max tokens for LLM"""
        return self.get_llm_setting('max_tokens', 2000)

    # Cache Settings
    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled"""
        return self.config.get('cache', {}).get('enabled', True)

    def get_cache_dir(self) -> str:
        """Get cache directory"""
        return self.config.get('cache', {}).get('cache_dir', 'cf_cache')

    def get_cache_ttl(self) -> int:
        """Get cache TTL in seconds"""
        return self.config.get('cache', {}).get('ttl', 3600)

    def get_cache_similarity_threshold(self) -> float:
        """Get semantic similarity threshold for cache"""
        return self.config.get('cache', {}).get('similarity_threshold', 0.8)

    # Trace Settings
    def is_trace_enabled(self) -> bool:
        """Check if tracing is enabled"""
        return self.config.get('trace', {}).get('enabled', True)

    def get_trace_output_dir(self) -> str:
        """Get trace output directory"""
        return self.config.get('trace', {}).get('output_dir', 'cf_trace')

    # Repository Settings
    def get_repo_setting(self, key: str, default: Any = None) -> Any:
        """Get repository configuration value"""
        return self.config.get('repo', {}).get(key, default)

    def get_max_files(self) -> int:
        """Get maximum files to scan"""
        return self.get_repo_setting('max_files', 1000)

    def get_max_file_size(self) -> int:
        """Get maximum file size in bytes"""
        return self.get_repo_setting('max_file_size', 1048576)  # 1MB

    def get_max_scan_depth(self) -> int:
        """Get maximum directory scan depth"""
        return self.get_repo_setting('max_scan_depth', 5)

    # Logging Settings
    def get_log_level(self) -> str:
        """Get logging level"""
        return self.config.get('logging', {}).get('level', 'INFO')

    def is_verbose_logging(self) -> bool:
        """Check if verbose logging is enabled"""
        return self.config.get('logging', {}).get('verbose', False)

    # Raw Config Access (for migration/compatibility)
    def get_raw_config(self) -> Dict[str, Any]:
        """Get raw configuration dictionary"""
        return self.config

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section"""
        return self.config.get(section, {})
