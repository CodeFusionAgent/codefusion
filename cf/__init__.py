"""CodeFusion: A ReAct (Reasoning + Acting) framework for intelligent code exploration and analysis."""

from .aci.repo import CodeAction, CodeRepo, FileInfo, LocalCodeRepo, RemoteCodeRepo
from .config import CfConfig
from .agents.react_supervisor_agent import ReActSupervisorAgent
from .core.react_agent import ReActAgent, ReActAction, ReActObservation, ActionType

__version__ = "0.1.0"
__author__ = "CodeFusion Team"
__description__ = (
    "ReAct framework for systematic code exploration through reasoning, acting, and observing. "
    "Enables multi-agent collaborative analysis of codebases with LLM-powered intelligence."
)

__all__ = [
    "CfConfig",
    "CodeRepo",
    "LocalCodeRepo",
    "RemoteCodeRepo", 
    "CodeAction",
    "FileInfo",
    "ReActSupervisorAgent",
    "ReActAgent",
    "ReActAction", 
    "ReActObservation",
    "ActionType",
]