"""ACI (Agent Computer Interface) module for CodeFusion.

This module provides the interface between agents and the computer system,
focusing on simple repository access for human-like exploration.
"""

from .repo import CodeAction, CodeRepo, FileInfo, LocalCodeRepo, RemoteCodeRepo

__all__ = [
    "CodeRepo",
    "LocalCodeRepo", 
    "RemoteCodeRepo",
    "CodeAction",
    "FileInfo",
]