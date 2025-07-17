"""
Configuration for ReAct agents and loops.

This module provides configurable parameters for ReAct agent behavior,
including iteration limits, timeouts, and error handling settings.
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class ReActConfig:
    """Configuration for ReAct agent behavior."""
    
    # Loop parameters
    max_iterations: int = 20
    iteration_timeout: float = 30.0  # seconds per iteration
    total_timeout: float = 600.0  # seconds for entire loop
    
    # Error handling
    max_errors: int = 10
    max_consecutive_errors: int = 3
    error_recovery_enabled: bool = True
    circuit_breaker_threshold: int = 5
    
    # Stuck detection
    stuck_detection_enabled: bool = True
    max_same_action_repeats: int = 3
    loop_detection_window: int = 10
    
    # Tool parameters
    tool_timeout: float = 15.0  # seconds per tool call
    max_tool_retries: int = 2
    tool_validation_enabled: bool = True
    
    # Cache parameters
    cache_enabled: bool = True
    cache_max_size: int = 1000
    cache_ttl: int = 3600  # seconds
    
    # Logging and tracing
    tracing_enabled: bool = True
    trace_directory: Optional[str] = None
    log_level: str = "INFO"
    verbose_logging: bool = False
    
    # LLM parameters
    llm_reasoning_enabled: bool = True
    llm_reasoning_threshold: int = 5  # Use LLM after this many iterations
    llm_summary_enabled: bool = True
    
    # Performance parameters
    parallel_tools_enabled: bool = False
    max_parallel_tools: int = 3
    
    @classmethod
    def from_env(cls) -> 'ReActConfig':
        """Create configuration from environment variables."""
        return cls(
            # Loop parameters
            max_iterations=int(os.getenv('CF_REACT_MAX_ITERATIONS', '20')),
            iteration_timeout=float(os.getenv('CF_REACT_ITERATION_TIMEOUT', '30.0')),
            total_timeout=float(os.getenv('CF_REACT_TOTAL_TIMEOUT', '600.0')),
            
            # Error handling
            max_errors=int(os.getenv('CF_REACT_MAX_ERRORS', '10')),
            max_consecutive_errors=int(os.getenv('CF_REACT_MAX_CONSECUTIVE_ERRORS', '3')),
            error_recovery_enabled=os.getenv('CF_REACT_ERROR_RECOVERY', 'true').lower() == 'true',
            circuit_breaker_threshold=int(os.getenv('CF_REACT_CIRCUIT_BREAKER_THRESHOLD', '5')),
            
            # Stuck detection
            stuck_detection_enabled=os.getenv('CF_REACT_STUCK_DETECTION', 'true').lower() == 'true',
            max_same_action_repeats=int(os.getenv('CF_REACT_MAX_SAME_ACTION_REPEATS', '3')),
            loop_detection_window=int(os.getenv('CF_REACT_LOOP_DETECTION_WINDOW', '10')),
            
            # Tool parameters
            tool_timeout=float(os.getenv('CF_REACT_TOOL_TIMEOUT', '15.0')),
            max_tool_retries=int(os.getenv('CF_REACT_MAX_TOOL_RETRIES', '2')),
            tool_validation_enabled=os.getenv('CF_REACT_TOOL_VALIDATION', 'true').lower() == 'true',
            
            # Cache parameters
            cache_enabled=os.getenv('CF_REACT_CACHE_ENABLED', 'true').lower() == 'true',
            cache_max_size=int(os.getenv('CF_REACT_CACHE_MAX_SIZE', '1000')),
            cache_ttl=int(os.getenv('CF_REACT_CACHE_TTL', '3600')),
            
            # Logging and tracing
            tracing_enabled=os.getenv('CF_REACT_TRACING_ENABLED', 'true').lower() == 'true',
            trace_directory=os.getenv('CF_REACT_TRACE_DIR'),
            log_level=os.getenv('CF_REACT_LOG_LEVEL', 'INFO'),
            verbose_logging=os.getenv('CF_REACT_VERBOSE_LOGGING', 'false').lower() == 'true',
            
            # LLM parameters
            llm_reasoning_enabled=os.getenv('CF_REACT_LLM_REASONING', 'true').lower() == 'true',
            llm_reasoning_threshold=int(os.getenv('CF_REACT_LLM_REASONING_THRESHOLD', '5')),
            llm_summary_enabled=os.getenv('CF_REACT_LLM_SUMMARY', 'true').lower() == 'true',
            
            # Performance parameters
            parallel_tools_enabled=os.getenv('CF_REACT_PARALLEL_TOOLS', 'false').lower() == 'true',
            max_parallel_tools=int(os.getenv('CF_REACT_MAX_PARALLEL_TOOLS', '3'))
        )
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ReActConfig':
        """Create configuration from dictionary."""
        return cls(**config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'max_iterations': self.max_iterations,
            'iteration_timeout': self.iteration_timeout,
            'total_timeout': self.total_timeout,
            'max_errors': self.max_errors,
            'max_consecutive_errors': self.max_consecutive_errors,
            'error_recovery_enabled': self.error_recovery_enabled,
            'circuit_breaker_threshold': self.circuit_breaker_threshold,
            'stuck_detection_enabled': self.stuck_detection_enabled,
            'max_same_action_repeats': self.max_same_action_repeats,
            'loop_detection_window': self.loop_detection_window,
            'tool_timeout': self.tool_timeout,
            'max_tool_retries': self.max_tool_retries,
            'tool_validation_enabled': self.tool_validation_enabled,
            'cache_enabled': self.cache_enabled,
            'cache_max_size': self.cache_max_size,
            'cache_ttl': self.cache_ttl,
            'tracing_enabled': self.tracing_enabled,
            'trace_directory': self.trace_directory,
            'log_level': self.log_level,
            'verbose_logging': self.verbose_logging,
            'llm_reasoning_enabled': self.llm_reasoning_enabled,
            'llm_reasoning_threshold': self.llm_reasoning_threshold,
            'llm_summary_enabled': self.llm_summary_enabled,
            'parallel_tools_enabled': self.parallel_tools_enabled,
            'max_parallel_tools': self.max_parallel_tools
        }
    
    def update_from_dict(self, updates: Dict[str, Any]):
        """Update configuration from dictionary."""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def validate(self) -> bool:
        """Validate configuration parameters."""
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        
        if self.iteration_timeout <= 0:
            raise ValueError("iteration_timeout must be positive")
        
        if self.total_timeout <= 0:
            raise ValueError("total_timeout must be positive")
        
        if self.max_errors <= 0:
            raise ValueError("max_errors must be positive")
        
        if self.max_consecutive_errors <= 0:
            raise ValueError("max_consecutive_errors must be positive")
        
        if self.circuit_breaker_threshold <= 0:
            raise ValueError("circuit_breaker_threshold must be positive")
        
        if self.max_same_action_repeats <= 0:
            raise ValueError("max_same_action_repeats must be positive")
        
        if self.loop_detection_window <= 0:
            raise ValueError("loop_detection_window must be positive")
        
        if self.tool_timeout <= 0:
            raise ValueError("tool_timeout must be positive")
        
        if self.max_tool_retries < 0:
            raise ValueError("max_tool_retries must be non-negative")
        
        if self.cache_max_size <= 0:
            raise ValueError("cache_max_size must be positive")
        
        if self.cache_ttl <= 0:
            raise ValueError("cache_ttl must be positive")
        
        if self.llm_reasoning_threshold <= 0:
            raise ValueError("llm_reasoning_threshold must be positive")
        
        if self.max_parallel_tools <= 0:
            raise ValueError("max_parallel_tools must be positive")
        
        return True
    
    def get_performance_profile(self) -> str:
        """Get a performance profile description."""
        if self.max_iterations <= 10 and self.tool_timeout <= 10:
            return "fast"
        elif self.max_iterations <= 30 and self.tool_timeout <= 30:
            return "balanced"
        else:
            return "thorough"
    
    def apply_performance_profile(self, profile: str):
        """Apply a predefined performance profile."""
        if profile == "fast":
            self.max_iterations = 10
            self.iteration_timeout = 15.0
            self.total_timeout = 300.0
            self.tool_timeout = 10.0
            self.max_errors = 5
            self.cache_max_size = 500
            
        elif profile == "balanced":
            self.max_iterations = 20
            self.iteration_timeout = 30.0
            self.total_timeout = 600.0
            self.tool_timeout = 15.0
            self.max_errors = 10
            self.cache_max_size = 1000
            
        elif profile == "thorough":
            self.max_iterations = 50
            self.iteration_timeout = 60.0
            self.total_timeout = 1800.0
            self.tool_timeout = 30.0
            self.max_errors = 20
            self.cache_max_size = 2000
            
        else:
            raise ValueError(f"Unknown performance profile: {profile}")


# Global configuration instance
react_config = ReActConfig.from_env()