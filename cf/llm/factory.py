"""
LLM Factory for creating LLM client instances

Simple factory pattern for creating LLM clients.
"""

from typing import Dict, Any
from cf.llm.client import LLMClient


class LLMFactory:
    """Factory for creating LLM client instances"""

    @staticmethod
    def create_llm(model_name: str, config: Dict[str, Any]) -> LLMClient:
        """
        Create an LLM client instance.

        Args:
            model_name: Name of the model to use
            config: LLM configuration dictionary

        Returns:
            LLMClient instance configured for the specified model
        """
        # Override model in config
        llm_config = config.copy()
        llm_config['model'] = model_name

        return LLMClient(llm_config)
