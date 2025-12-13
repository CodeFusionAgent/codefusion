"""
Tool Selector Routing and Execution - Agent Routing and Execution Planning
"""

from typing import Dict, List, Any, Callable

from .types import QuestionCategory
from .planning_selection import LLMToolSelector


class AgentRouter:
    """
    Routes questions to the most appropriate agent.

    Used by SupervisorAgent to decide which specialist agents to consult.
    """

    # Agent capabilities
    AGENT_CAPABILITIES = {
        'code': {
            'description': 'Analyzes source code structure and implementation',
            'strengths': ['code_reading', 'function_analysis', 'implementation_details'],
            'best_for': [QuestionCategory.EXPLANATION, QuestionCategory.DEBUGGING,
                        QuestionCategory.LOOKUP, QuestionCategory.REFACTORING],
        },
        'kb': {
            'description': 'Queries knowledge base for structural information',
            'strengths': ['call_graphs', 'dependencies', 'cross_references'],
            'best_for': [QuestionCategory.FLOW, QuestionCategory.ARCHITECTURE],
        },
        'docs': {
            'description': 'Processes documentation and README files',
            'strengths': ['documentation', 'usage_examples', 'api_info'],
            'best_for': [QuestionCategory.DOCUMENTATION],
        },
        'web': {
            'description': 'Searches external documentation and resources',
            'strengths': ['external_docs', 'library_info', 'best_practices'],
            'best_for': [QuestionCategory.DOCUMENTATION, QuestionCategory.SECURITY],
        },
    }

    def __init__(self, llm_callback: Callable, config: Dict[str, Any]):
        """
        Initialize router.

        Args:
            llm_callback: Callable(prompt, system_prompt) -> response dict
            config: Configuration dictionary
        """
        self.llm = llm_callback
        self.config = config
        self.tool_selector = LLMToolSelector(llm_callback, config)

    def route_question(self, question: str) -> Dict[str, Any]:
        """
        Route a question to appropriate agents.

        Args:
            question: User question

        Returns:
            Routing decision with agents and rationale
        """
        classification = self.tool_selector.classify_question(question)

        agents = []
        rationale = []
        weights = {}

        # Score each agent based on classification
        for agent_name, capabilities in self.AGENT_CAPABILITIES.items():
            score = self._score_agent(agent_name, classification, capabilities)
            if score > 0.3:
                agents.append(agent_name)
                weights[agent_name] = score
                rationale.append(f"{agent_name}: {capabilities['description']} (score: {score:.2f})")

        # Sort by weight
        agents.sort(key=lambda a: weights.get(a, 0), reverse=True)

        return {
            'agents': agents,
            'weights': weights,
            'classification': {
                'category': classification.category.value,
                'complexity': classification.complexity.value,
                'needs_kb': classification.needs_kb,
                'needs_llm': classification.needs_llm,
                'needs_web': classification.needs_web,
                'key_concepts': classification.key_concepts,
            },
            'rationale': rationale,
            'reasoning': classification.reasoning,
            'confidence': classification.confidence,
        }

    def _score_agent(
        self,
        agent_name: str,
        classification,
        capabilities: Dict[str, Any]
    ) -> float:
        """Score how well an agent matches the question"""
        score = 0.0

        # Check if category is in agent's strengths
        best_for = capabilities.get('best_for', [])
        if classification.category in best_for:
            score += 0.5

        # Check suggested agents
        if agent_name in classification.suggested_agents:
            score += 0.3

        # Check specific needs
        if agent_name == 'kb' and classification.needs_kb:
            score += 0.2
        if agent_name == 'web' and classification.needs_web:
            score += 0.2

        # Code agent is always somewhat relevant
        if agent_name == 'code':
            score += 0.2

        return min(1.0, score)

    def select_primary_agent(self, question: str) -> str:
        """Select the single best agent for a question"""
        routing = self.route_question(question)
        agents = routing.get('agents', ['code'])
        return agents[0] if agents else 'code'


class ToolExecutionPlanner:
    """
    Plans and optimizes tool execution sequences.

    Considers:
    - Tool dependencies
    - Parallel execution opportunities
    - Early termination conditions
    """

    def __init__(self, tool_selector: LLMToolSelector):
        self.selector = tool_selector

    def create_execution_plan(
        self,
        question: str,
        available_tools: List[str],
        max_parallel: int = 3
    ) -> Dict[str, Any]:
        """
        Create an optimized execution plan.

        Args:
            question: User question
            available_tools: Available tools
            max_parallel: Max parallel executions

        Returns:
            Execution plan with phases
        """
        chain_plan = self.selector.plan_tool_chain(question, available_tools)

        # Group tools into phases
        phases = []
        current_phase = []

        for tool in chain_plan.tools:
            # Check dependencies
            if tool.depends_on and any(d not in [t.tool_name for t in current_phase]
                                       for d in tool.depends_on):
                # Start new phase if dependencies not met
                if current_phase:
                    phases.append(current_phase)
                    current_phase = []

            current_phase.append(tool)

            # Limit phase size
            if len(current_phase) >= max_parallel:
                phases.append(current_phase)
                current_phase = []

        if current_phase:
            phases.append(current_phase)

        return {
            'phases': [
                {
                    'phase_num': i + 1,
                    'tools': [
                        {
                            'name': t.tool_name,
                            'params': t.params,
                            'reason': t.reason,
                        }
                        for t in phase
                    ],
                    'parallel': len(phase) > 1,
                }
                for i, phase in enumerate(phases)
            ],
            'strategy': chain_plan.strategy,
            'max_iterations': chain_plan.max_iterations,
            'stop_conditions': chain_plan.stop_conditions,
            'estimated_complexity': chain_plan.estimated_complexity.value,
        }


# Factory functions

def create_tool_selector(llm_callback: Callable, config: Dict[str, Any]) -> LLMToolSelector:
    """
    Factory function to create a tool selector.

    Args:
        llm_callback: LLM callback function
        config: Configuration dictionary

    Returns:
        Configured LLMToolSelector instance
    """
    return LLMToolSelector(llm_callback, config)


def create_agent_router(llm_callback: Callable, config: Dict[str, Any]) -> AgentRouter:
    """
    Factory function to create an agent router.

    Args:
        llm_callback: LLM callback function
        config: Configuration dictionary

    Returns:
        Configured AgentRouter instance
    """
    return AgentRouter(llm_callback, config)


def create_execution_planner(
    llm_callback: Callable,
    config: Dict[str, Any]
) -> ToolExecutionPlanner:
    """
    Factory function to create an execution planner.

    Args:
        llm_callback: LLM callback function
        config: Configuration dictionary

    Returns:
        Configured ToolExecutionPlanner instance
    """
    selector = LLMToolSelector(llm_callback, config)
    return ToolExecutionPlanner(selector)
