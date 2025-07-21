"""LLM interfaces for CodeFusion."""

from cf.llm.simple_llm import SimpleLLM, llm

try:
    from cf.llm.real_llm import RealLLM, real_llm
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