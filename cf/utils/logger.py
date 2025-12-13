"""
Logging utility for CodeFusion

Provides both technical logging (DEBUG/INFO/etc) and user-friendly verbose progress logging.
"""

import logging
import sys
from typing import Optional, Dict, Any


class CodeFusionLogger:
    """Enhanced logger with both technical and verbose user-friendly logging"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.config = config or {}

        # Setup technical logger (don't add cf. prefix if already present)
        logger_name = name if name.startswith('cf.') else f"cf.{name}"
        self.logger = logging.getLogger(logger_name)

        # Get logging configuration
        log_config = self.config.get('logging', {})
        self.verbose_enabled = log_config.get('verbose', False)

        # Configure technical logging if not already done
        if not self.logger.handlers:
            self._configure_technical_logging(log_config)

    def _configure_technical_logging(self, log_config: Dict[str, Any]) -> None:
        """Configure technical logging (DEBUG, INFO, etc.)"""
        level = getattr(logging, log_config.get('level', 'INFO').upper())
        format_str = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(format_str)
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(level)
    
    # Technical logging methods
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Technical debug logging"""
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Technical info logging"""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Technical warning logging"""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Technical error logging"""
        self.logger.error(msg, *args, **kwargs)

    # User-friendly verbose logging methods
    def verbose(self, msg: str, emoji: str = "🔍") -> None:
        """User-friendly progress logging (only if verbose enabled)"""
        if self.verbose_enabled:
            print(f"{emoji} [{self.name.title()}Agent] {msg}")

    def verbose_action(self, action: str, details: str = "") -> None:
        """Log agent action with details"""
        if self.verbose_enabled:
            msg = f"ACTION PLANNING PHASE"
            if details:
                msg += f"\n💭 [{self.name.title()}Agent] Based on reasoning: {details[:100]}..."
            print(f"🎯 [{self.name.title()}Agent] {msg}")

    def verbose_tool_call(self, tool_name: str, params: Dict[str, Any]) -> None:
        """Log tool call details"""
        if self.verbose_enabled:
            print(f"🎯 [{self.name.title()}Agent] LLM selected tool: {tool_name}")
            print(f"📋 [{self.name.title()}Agent] Tool arguments: {params}")

    def verbose_result(self, success: bool, details: str = "") -> None:
        """Log operation result"""
        if self.verbose_enabled:
            if success:
                print(f"✅ [{self.name.title()}Agent] {details or 'Operation completed'}")
            else:
                print(f"❌ [{self.name.title()}Agent] {details or 'Operation failed'}")

    def verbose_memory(self, operation: str, details: str) -> None:
        """Log memory operations"""
        if self.verbose_enabled:
            print(f"🧠 [{self.name.title()}Agent] {operation}: {details}")

    def verbose_progress(self, msg: str, emoji: str = "🔧") -> None:
        """Log progress messages"""
        if self.verbose_enabled:
            print(f"{emoji} [{self.name.title()}Agent] {msg}")

    def verbose_synthesis(self, msg: str) -> None:
        """Log synthesis operations"""
        if self.verbose_enabled:
            print(f"🤖 {msg}")

    def verbose_separator(self, length: int = 60) -> None:
        """Print separator line"""
        if self.verbose_enabled:
            print("=" * length)


def get_logger(name: str, config: Optional[Dict[str, Any]] = None) -> CodeFusionLogger:
    """Get or create a CodeFusion logger"""
    return CodeFusionLogger(name, config)