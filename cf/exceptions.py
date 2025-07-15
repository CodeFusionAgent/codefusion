"""Custom exceptions for CodeFusion."""


class CodeFusionError(Exception):
    """Base exception for CodeFusion."""

    pass


class ConfigurationError(CodeFusionError):
    """Raised when configuration is invalid."""

    pass


class RepositoryError(CodeFusionError):
    """Raised when repository operations fail."""

    pass


class KnowledgeBaseError(CodeFusionError):
    """Raised when knowledge base operations fail."""

    pass


class IndexingError(CodeFusionError):
    """Raised when indexing operations fail."""

    pass


class ExplorationError(CodeFusionError):
    """Raised when exploration strategies fail."""

    pass


class LlmError(CodeFusionError):
    """Raised when LLM operations fail."""

    pass


class UnsupportedLanguageError(CodeFusionError):
    """Raised when an unsupported programming language is encountered."""

    pass


class EntityNotFoundError(KnowledgeBaseError):
    """Raised when a requested entity is not found in the knowledge base."""

    pass


class RelationshipError(KnowledgeBaseError):
    """Raised when relationship operations fail."""

    pass


class TraceError(LlmError):
    """Raised when LLM tracing operations fail."""

    pass


class AnalysisError(CodeFusionError):
    """Raised when code analysis operations fail."""

    pass
