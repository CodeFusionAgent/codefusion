"""
Discovery Strategy Base Class

Base class for all file discovery strategies.
"""

from typing import Dict, List, Any, Optional
from cf.agents.pipelines.discovery import FileCandidate


class DiscoveryStrategy:
    """Base class for file discovery strategies"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def execute(self, question: str, context: Dict[str, Any]) -> List[FileCandidate]:
        """Execute discovery strategy and return candidates"""
        raise NotImplementedError
