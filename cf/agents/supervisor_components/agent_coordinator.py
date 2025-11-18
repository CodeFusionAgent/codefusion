"""
Agent Coordinator

Handles agent consultation and coordination for SupervisorAgent.
Manages specialist agent lifecycle and result collection.
"""

from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError


class AgentCoordinator:
    """
    Coordinates consultation with specialist agents.

    Responsibilities:
    - Agent initialization and lifecycle
    - Timeout enforcement
    - Result collection
    - Context-aware prompting
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], logger,
                 shared_tool_registry, agent_registry):
        """
        Initialize agent coordinator.

        Args:
            repo_path: Path to repository
            config: Configuration dictionary
            logger: Logger instance
            shared_tool_registry: Shared tool registry
            agent_registry: Agent registry
        """
        self.repo_path = repo_path
        self.config = config
        self.logger = logger
        self._shared_tool_registry = shared_tool_registry
        self._agent_registry = agent_registry

        # Specialist agents (persistent across questions)
        self._code_agent = None
        self._docs_agent = None
        self._web_agent = None

        # Configuration
        supervisor_config = config.get('agents', {}).get('supervisor', {})
        self.agent_execution_max_workers = supervisor_config.get('agent_execution_max_workers', 1)

    def reset_agents(self):
        """Reset specialist agents for new question"""
        # Note: We keep agents persistent, so this is mainly for future use
        pass

    def consult_agent_with_timeout(self, agent_type: str, question: str,
                                   timeout_seconds: int) -> Dict[str, Any]:
        """
        Execute agent call with timeout enforcement.

        Args:
            agent_type: Type of agent ('code', 'docs', 'web')
            question: Question to ask
            timeout_seconds: Timeout in seconds

        Returns:
            Agent result dictionary
        """
        with ThreadPoolExecutor(max_workers=self.agent_execution_max_workers) as executor:
            future = executor.submit(self.get_agent_result, agent_type, question)
            try:
                return future.result(timeout=timeout_seconds)
            except FuturesTimeoutError:
                self.logger.error(f"{agent_type} agent exceeded {timeout_seconds}s timeout")
                return {
                    'success': False,
                    'error': f'Agent timeout after {timeout_seconds}s',
                    'insights': [],
                    'timed_out': True
                }
            except Exception as e:
                self.logger.error(f"{agent_type} agent execution failed: {str(e)}")
                return {
                    'success': False,
                    'error': str(e),
                    'insights': []
                }

    def get_agent_result(self, agent_type: str, question: str) -> Dict[str, Any]:
        """
        Get result from specific agent type.

        Args:
            agent_type: Type of agent ('code', 'docs', 'web')
            question: Question to ask

        Returns:
            Agent result dictionary
        """
        if agent_type == 'code':
            if not self._code_agent:
                # Import here to avoid circular dependency
                from cf.agents.code_orchestrator import CodeOrchestrator

                # Always use pipeline architecture (CodeOrchestrator)
                # Pass shared registries for cross-agent tool usage (no duplication!)
                self._code_agent = CodeOrchestrator(
                    self.repo_path,
                    self.config,
                    tool_registry=self._shared_tool_registry,
                    agent_registry=self._agent_registry
                )
                # KB agents are automatically registered in shared registry during orchestrator init

            return self._code_agent.analyze(question)

        elif agent_type == 'docs':
            if not self._docs_agent:
                # Import here to avoid circular dependency
                from cf.agents.docs import DocsAgent

                # Pass shared tool registry for cross-agent tool usage
                self._docs_agent = DocsAgent(self.repo_path, self.config,
                                              tool_registry=self._shared_tool_registry)
            return self._docs_agent.analyze(question)

        elif agent_type == 'web':
            if not self._web_agent:
                # Import here to avoid circular dependency
                from cf.agents.web import WebAgent

                # Pass shared tool registry for cross-agent tool usage
                self._web_agent = WebAgent(self.repo_path, self.config,
                                            tool_registry=self._shared_tool_registry)
            return self._web_agent.analyze(question)

        else:
            return {
                'success': False,
                'error': f'Unknown agent type: {agent_type}',
                'insights': []
            }

    def consult_agent(self, agent_type: str, question: str,
                     specialist_results: Dict[str, Any],
                     agents_completed: List[str],
                     all_insights: List[Dict[str, Any]]) -> str:
        """
        Consult a specific specialist agent.

        Args:
            agent_type: Type of agent ('code', 'docs', 'web')
            question: Question to ask
            specialist_results: Dictionary to store results
            agents_completed: List to append completed agent
            all_insights: List to append insights

        Returns:
            Status string
        """
        # Get timeout from config
        timeout_seconds = self.config.get('agents', {}).get('timeout', 300)

        # Log agent consultation
        agent_emojis = {
            'code': '🔍',
            'docs': '📚',
            'web': '🌐'
        }
        emoji = agent_emojis.get(agent_type, '❓')
        self.logger.verbose(f"Running {agent_type} analysis agent...", emoji)

        try:
            # Execute with timeout enforcement
            result = self.consult_agent_with_timeout(agent_type, question, timeout_seconds)
            specialist_results[agent_type] = result

            if result.get('success'):
                all_insights.extend(result.get('insights', []))
                self.logger.verbose_result(True, f"{agent_type.capitalize()} analysis completed")
            elif result.get('timed_out'):
                self.logger.verbose_result(False, f"{agent_type.capitalize()} analysis timed out after {timeout_seconds}s")
            else:
                self.logger.verbose_result(False, f"{agent_type.capitalize()} analysis failed: {result.get('error', 'Unknown error')}")

            agents_completed.append(agent_type)
            return f"consulted_{agent_type}_agent"

        except Exception as e:
            self.logger.error(f"{agent_type.capitalize()} agent failed: {str(e)}")
            specialist_results[agent_type] = {'success': False, 'error': str(e)}
            agents_completed.append(agent_type)
            self.logger.verbose_result(False, f"{agent_type.capitalize()} agent exception: {str(e)}")
            return f"{agent_type}_agent_failed"

    def set_code_agent_context(self, analysis_type: str, question: str):
        """
        Set context for code agent.

        Args:
            analysis_type: Type of analysis
            question: Question being asked
        """
        if self._code_agent and hasattr(self._code_agent, 'set_question_context'):
            self._code_agent.set_question_context({
                'analysis_type': analysis_type,
                'question': question
            })

    def build_context_aware_prompt(self, agent_type: str, original_question: str,
                                   pass_results: Dict[str, Any], pass_number: int) -> str:
        """
        Build context-aware prompt for agents based on previous pass results.

        Args:
            agent_type: Type of agent
            original_question: Original question
            pass_results: Previous pass results
            pass_number: Current pass number

        Returns:
            Enhanced prompt string
        """
        try:
            # Get previous pass insights
            previous_insights = []
            for pass_key, pass_data in pass_results.items():
                if pass_key != f'pass_{pass_number}':  # Exclude current pass
                    previous_insights.extend(pass_data.get('insights', []))

            if not previous_insights:
                return original_question

            # Build context summary
            context_summary = []
            for insight in previous_insights[:5]:  # Limit to top 5 insights
                content = insight.get('content', '')[:100]  # Truncate long content
                context_summary.append(f"- {content}")

            enhanced_prompt = f"""Based on previous analysis insights:
{chr(10).join(context_summary)}

Now focusing on {agent_type} analysis, please address: {original_question}

Consider how your findings relate to or build upon the previous insights."""

            return enhanced_prompt

        except Exception as e:
            self.logger.error(f"Context-aware prompt building failed: {str(e)}")
            return original_question

    def build_summary_pass_specific_question(self, agent_type: str, original_question: str,
                                            pass_number: int, pass_results: Dict[str, Any]) -> str:
        """
        Build simplified pass-specific questions for summary analysis.

        Args:
            agent_type: Type of agent
            original_question: Original question
            pass_number: Current pass number
            pass_results: Pass results dictionary

        Returns:
            Enhanced question string
        """
        try:
            if pass_number == 1:
                enhanced_question = f"PASS 1 - High-level overview: {original_question}. Focus on overall structure and organization."
                self.logger.verbose(f"🔍 Pass 1 Focus: High-level overview and structure", "📋")
                return enhanced_question
            elif pass_number == 2:
                pass1_context = self._get_brief_pass1_context(pass_results)
                enhanced_question = f"PASS 2 - Detailed analysis: {original_question}. Previous context: {pass1_context}. Now provide deep technical insights."
                self.logger.verbose(f"🔬 Pass 2 Focus: Detailed analysis with context from Pass 1", "📋")
                self.logger.verbose(f"📝 Pass 1 Context: {pass1_context[:100]}{'...' if len(pass1_context) > 100 else ''}", "🔗")
                return enhanced_question
            else:
                return original_question

        except Exception as e:
            self.logger.error(f"Summary pass question building failed: {str(e)}")
            return original_question

    def _get_brief_pass1_context(self, pass_results: Dict[str, Any]) -> str:
        """
        Get a brief summary of Pass 1 results for Pass 2 context.

        Args:
            pass_results: Pass results dictionary

        Returns:
            Brief context string
        """
        try:
            if 'pass_1' not in pass_results:
                return "No previous context"

            pass1_data = pass_results['pass_1']
            insights = pass1_data.get('insights', [])

            if not insights:
                return "No previous insights"

            # Get top 3 insights, truncated
            context_parts = []
            for insight in insights[:3]:
                content = insight.get('content', '')[:80] + '...' if len(insight.get('content', '')) > 80 else insight.get('content', '')
                context_parts.append(content)

            return '; '.join(context_parts)

        except Exception:
            return "Context unavailable"
