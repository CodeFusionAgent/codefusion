"""
Standard Result Types for CodeFusion Pipelines

Provides consistent result patterns across all pipelines with built-in error handling.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineResult:
    """
    Base result type for all pipeline operations.

    Enforces consistent error handling pattern:
    - success: bool - indicates if operation succeeded
    - error: Optional[str] - error message if failed
    - metadata: Dict - additional context

    All pipeline-specific results should include these fields.
    """
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_error(cls, error_message: str, **kwargs):
        """
        Create an error result with default/empty values.

        Args:
            error_message: Description of error
            **kwargs: Pipeline-specific fields with default values

        Returns:
            Result instance with success=False and error message

        Example:
            >>> result = DiscoveryResult.create_error(
            ...     "KB not available",
            ...     files=[],
            ...     total_candidates=0
            ... )
        """
        return cls(success=False, error=error_message, **kwargs)

    @classmethod
    def create_success(cls, **kwargs):
        """
        Create a success result.

        Args:
            **kwargs: Pipeline-specific fields

        Returns:
            Result instance with success=True

        Example:
            >>> result = DiscoveryResult.create_success(
            ...     files=[candidate1, candidate2],
            ...     total_candidates=2
            ... )
        """
        return cls(success=True, **kwargs)


def create_error_result(result_class, error_message: str, **default_values):
    """
    Helper function to create standardized error results.

    Args:
        result_class: The result dataclass type
        error_message: Error description
        **default_values: Default/empty values for result fields

    Returns:
        Error result instance

    Example:
        >>> from cf.agents.pipelines.discovery import DiscoveryResult, FileCandidate
        >>> error_result = create_error_result(
        ...     DiscoveryResult,
        ...     "Discovery strategy failed",
        ...     files=[],
        ...     domain_info={},
        ...     strategies_used=[],
        ...     total_candidates=0
        ... )
    """
    return result_class(
        success=False,
        error=error_message,
        **default_values
    )
