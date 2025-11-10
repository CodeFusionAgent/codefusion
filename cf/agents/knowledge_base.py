"""
Knowledge Base Agent Base Classes

Provides base classes for building pluggable knowledge agents:
- KnowledgeAgent: Base class for tool-based agents
- AnalysisStrategy: Base class for swappable analysis strategies
- AgentResult: Standard result format

These enable modular experimentation and A/B testing.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """Standard result format for all agent operations"""
    success: bool
    data: Any
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class KnowledgeAgent(ABC):
    """
    Base class for pluggable knowledge agents.

    Knowledge agents provide specialized capabilities through tools:
    - Query capabilities (semantic search, pattern detection, etc.)
    - Analysis layers (dataflow, execution tracing, etc.)
    - Custom search strategies

    This design enables:
    - Runtime registration of new agents
    - A/B testing: "Does AST help/hinder certain queries?"
    - Modular experimentation with different configurations

    Example:
        class MyAgent(KnowledgeAgent):
            def __init__(self, config):
                super().__init__("my_agent", config)

            def get_capabilities(self):
                return ['custom_analysis']

            def register_tools(self):
                return {
                    'analyze': self._analyze,
                    'search': self._search
                }

            def _analyze(self, query: str) -> Dict[str, Any]:
                # Implementation
                return {'success': True, 'results': [...]}
    """

    def __init__(self, name: str, config: Dict[str, Any] = None):
        """
        Initialize knowledge agent.

        Args:
            name: Unique agent identifier (used for tool prefixing)
            config: Agent-specific configuration
        """
        self.name = name
        self.config = config or {}
        self.enabled = config.get('enabled', True) if config else True
        self._metrics = {
            'calls': 0,
            'tokens': 0,
            'time': 0.0,
            'errors': 0
        }

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get list of capabilities this agent provides.

        Capabilities are used for agent discovery and filtering.

        Returns:
            List of capability identifiers
            Examples: 'semantic_search', 'pattern_detection', 'security_analysis'
        """
        pass

    @abstractmethod
    def register_tools(self) -> Dict[str, Callable]:
        """
        Register tools that this agent provides.

        Tools should be named WITHOUT the agent prefix. The registry will
        automatically prefix them as: {agent_name}_{tool_name}

        Returns:
            Dictionary mapping tool names (unprefixed) to callable functions

        Example:
            return {
                'search': self._search,          # Becomes: my_agent_search
                'analyze': self._analyze,        # Becomes: my_agent_analyze
                'get_metrics': self._get_metrics # Becomes: my_agent_get_metrics
            }
        """
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get OpenAPI-style schemas for tools (for LLM function calling).

        Tool names in schemas MUST include the agent prefix to match
        the registered tool names: {agent_name}_{tool_name}

        Returns:
            List of tool schemas

        Example:
            return [{
                'type': 'function',
                'function': {
                    'name': f'{self.name}_search',  # Must include prefix!
                    'description': 'Search for information',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'query': {'type': 'string', 'description': 'Search query'}
                        },
                        'required': ['query']
                    }
                }
            }]
        """
        return []

    def get_prefixed_tool_name(self, tool_name: str) -> str:
        """
        Helper to get the prefixed tool name.

        Use this in get_tool_schemas() to ensure consistency.

        Args:
            tool_name: Unprefixed tool name

        Returns:
            Prefixed tool name: {agent_name}_{tool_name}
        """
        return f"{self.name}_{tool_name}"

    def initialize(self) -> bool:
        """
        Initialize agent (build indexes, load models, etc.).

        Called by AgentRegistry when agent is first registered.

        Returns:
            True if successful, False otherwise
        """
        return True

    def is_available(self) -> bool:
        """
        Check if agent is available and ready.

        Returns:
            True if agent can process requests, False otherwise
        """
        return self.enabled

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get agent performance metrics.

        Returns:
            Dictionary with metrics (calls, tokens, time, errors)
        """
        return self._metrics.copy()

    def _record_call(self, tokens: int = 0, time_taken: float = 0.0, error: bool = False):
        """
        Record a tool call for metrics tracking.

        Args:
            tokens: Number of tokens used (for LLM calls)
            time_taken: Time taken in seconds
            error: Whether an error occurred
        """
        self._metrics['calls'] += 1
        self._metrics['tokens'] += tokens
        self._metrics['time'] += time_taken
        if error:
            self._metrics['errors'] += 1


class AnalysisStrategy(ABC):
    """
    Base class for swappable analysis strategies.

    Strategies enable A/B testing different approaches:
    - AST-based vs. LLM-based pattern detection
    - Graph queries vs. semantic search
    - Different embedding models
    - Rule-based vs. ML-based detection

    Example:
        class ASTPatternStrategy(AnalysisStrategy):
            def __init__(self, config):
                super().__init__("ast_patterns", config)

            def analyze(self, code: str) -> AgentResult:
                # AST-based pattern detection
                patterns = detect_patterns_with_ast(code)
                return AgentResult(
                    success=True,
                    data=patterns,
                    confidence=0.9
                )

        class LLMPatternStrategy(AnalysisStrategy):
            def __init__(self, config):
                super().__init__("llm_patterns", config)

            def analyze(self, code: str) -> AgentResult:
                # LLM-based pattern detection
                patterns = detect_patterns_with_llm(code)
                return AgentResult(
                    success=True,
                    data=patterns,
                    confidence=0.8
                )

        # A/B test both approaches
        variants = [
            ExperimentConfig("ast", config_with_ast),
            ExperimentConfig("llm", config_with_llm)
        ]
        results = runner.run_experiment(query, variants, factory)
    """

    def __init__(self, name: str, config: Dict[str, Any] = None):
        """
        Initialize analysis strategy.

        Args:
            name: Strategy name
            config: Strategy-specific configuration
        """
        self.name = name
        self.config = config or {}

    @abstractmethod
    def analyze(self, input_data: Any, **kwargs) -> AgentResult:
        """
        Perform analysis using this strategy.

        Args:
            input_data: Data to analyze
            **kwargs: Strategy-specific parameters

        Returns:
            AgentResult with analysis results
        """
        pass

    def get_cost_estimate(self, input_data: Any) -> float:
        """
        Estimate cost of analysis (in dollars).

        Used for cost/benefit comparisons in A/B testing.

        Args:
            input_data: Data to analyze

        Returns:
            Estimated cost in dollars
        """
        return 0.0
