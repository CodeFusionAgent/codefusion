"""CodeFusion: A code understanding tool for rapid codebase exploration."""

from .aci.environment_manager import EnvironmentManager
from .aci.repo import CodeAction, CodeRepo, FileInfo, LocalCodeRepo, RemoteCodeRepo
from .config import CfConfig
from .indexer.code_indexer import CodeIndexer
from .kb.knowledge_base import (
    CodeEntity,
    CodeKB,
    CodeRelationship,
    create_knowledge_base,
)
from .llm.llm_model import CodeAnalysisLlm, LlmModel, LlmTracer, create_llm_model

__version__ = "0.0.1"
__author__ = "CodeFusion Team"
__description__ = (
    "A code understanding tool for senior developers to quickly ramp up on "
    "large codebases"
)

__all__ = [
    "CfConfig",
    "CodeRepo",
    "LocalCodeRepo",
    "RemoteCodeRepo",
    "CodeAction",
    "FileInfo",
    "EnvironmentManager",
    "CodeKB",
    "CodeEntity",
    "CodeRelationship",
    "create_knowledge_base",
    "CodeIndexer",
    "LlmModel",
    "LlmTracer",
    "CodeAnalysisLlm",
    "create_llm_model",
]
