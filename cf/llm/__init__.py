"""LLM interfaces for CodeFusion."""

from .simple_llm import SimpleLLM, llm

try:
    from .real_llm import RealLLM, real_llm
    __all__ = [
        "SimpleLLM",
        "llm",
        "RealLLM", 
        "real_llm",
    ]
except ImportError:
    # LiteLLM not available
    __all__ = [
        "SimpleLLM",
        "llm",
    ]