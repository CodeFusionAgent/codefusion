"""
Logging utilities for CodeFusion with configurable output control.
"""

import os
from typing import Optional

class CodeFusionLogger:
    """Centralized logging utility that respects configuration settings."""
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        
        # Get logging settings from config or environment
        logging_config = self.config.get('logging', {})
        
        self.enable_execution_logs = (
            logging_config.get('enable_execution_logs', False) or
            os.getenv('CF_ENABLE_LOGS', '').lower() in ['true', '1', 'yes', 'on'] or
            os.getenv('CF_ENABLE_EXECUTION_LOGS', '').lower() in ['true', '1', 'yes', 'on']
        )
        
        self.enable_llm_logs = (
            logging_config.get('enable_llm_logs', False) or
            os.getenv('CF_ENABLE_LOGS', '').lower() in ['true', '1', 'yes', 'on'] or
            os.getenv('CF_ENABLE_LLM_LOGS', '').lower() in ['true', '1', 'yes', 'on']
        )
        
        self.enable_tool_logs = (
            logging_config.get('enable_tool_logs', False) or
            os.getenv('CF_ENABLE_LOGS', '').lower() in ['true', '1', 'yes', 'on'] or
            os.getenv('CF_ENABLE_TOOL_LOGS', '').lower() in ['true', '1', 'yes', 'on']
        )
        
        self.enable_agent_logs = (
            logging_config.get('enable_agent_logs', False) or
            os.getenv('CF_ENABLE_LOGS', '').lower() in ['true', '1', 'yes', 'on'] or
            os.getenv('CF_ENABLE_AGENT_LOGS', '').lower() in ['true', '1', 'yes', 'on']
        )
        
        self.show_progress = logging_config.get('show_progress', True)
    
    def execution_log(self, message: str):
        """Log execution flow messages."""
        if self.enable_execution_logs:
            print(message)
    
    def llm_log(self, message: str):
        """Log LLM-related messages."""
        if self.enable_llm_logs:
            print(message)
    
    def tool_log(self, message: str):
        """Log tool execution messages."""
        if self.enable_tool_logs:
            print(message)
    
    def agent_log(self, message: str):
        """Log agent reasoning/action messages."""
        if self.enable_agent_logs:
            print(message)
    
    def progress(self, message: str):
        """Show progress messages (usually always shown unless disabled)."""
        if self.show_progress:
            print(message)
    
    def info(self, message: str):
        """Always show important informational messages."""
        print(message)
    
    def error(self, message: str):
        """Always show error messages."""
        print(message)


# Global logger instance that can be configured
cf_logger: Optional[CodeFusionLogger] = None

def init_cf_logger(config: Optional[dict] = None):
    """Initialize the global CodeFusion logger."""
    global cf_logger
    cf_logger = CodeFusionLogger(config)
    return cf_logger

def get_cf_logger() -> CodeFusionLogger:
    """Get the global CodeFusion logger, initializing if needed."""
    global cf_logger
    if cf_logger is None:
        cf_logger = CodeFusionLogger()
    return cf_logger

# Convenience functions for different log types
def execution_log(message: str):
    get_cf_logger().execution_log(message)

def llm_log(message: str):
    get_cf_logger().llm_log(message)

def tool_log(message: str):
    get_cf_logger().tool_log(message)

def agent_log(message: str):
    get_cf_logger().agent_log(message)

def progress_log(message: str):
    get_cf_logger().progress(message)

def info_log(message: str):
    get_cf_logger().info(message)

def error_log(message: str):
    get_cf_logger().error(message)