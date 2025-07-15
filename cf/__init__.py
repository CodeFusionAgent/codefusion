"""CodeFusion: A code understanding tool for rapid codebase exploration."""

from .config import CfConfig
from .aci.repo import CodeRepo, LocalCodeRepo, RemoteCodeRepo, CodeAction, FileInfo
from .aci.environment_manager import EnvironmentManager
from .kb.knowledge_base import CodeKB, CodeEntity, CodeRelationship, create_knowledge_base
from .indexer.code_indexer import CodeIndexer
from .llm.llm_model import LlmModel, LlmTracer, CodeAnalysisLlm, create_llm_model

__version__ = "0.0.1"
__author__ = "CodeFusion Team"
__description__ = "A code understanding tool for senior developers to quickly ramp up on large codebases"

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
    "create_llm_model"
]