"""
Multi-Pass Coordinator

Manages multi-pass analysis coordination with LLM-driven decisions.
Extracted from SupervisorAgent for better maintainability and testability.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from cf.utils.llm_parser import LLMResponseParser


@dataclass
class PassState:
    """State for a single analysis pass"""
    pass_number: int
    attempt: int
    agents_to_consult: List[str]
    agents_completed: List[str]
    specialist_results: Dict[str, Any]
    insights: List[Dict[str, Any]]
    context_sharing_enabled: bool = False
    focus_areas: List[str] = field(default_factory=list)


class MultiPassCoordinator:
    """
    Coordinates multi-pass analysis with LLM-driven decision making.

    Responsibilities:
    - Track pass progression (pass 1, 2, 3...)
    - Manage retry attempts per pass
    - Decide when to move to next pass vs retry vs complete
    - Handle context sharing between passes
    - Build pass-specific prompts

    Benefits:
    - Explicit state machine
    - Testable in isolation
    - Clearer error handling
    - Easier to modify pass logic
    """

    def __init__(self, config: Dict[str, Any], llm_callback):
        """
        Initialize coordinator.

        Args:
            config: Configuration dict with pass settings
            llm_callback: Function to call LLM for decisions
        """
        self.config = config
        self.llm_callback = llm_callback

        # Multi-pass configuration
        self.pass_config = {
            'standard': {'max_passes': 3},
            'summary': {'max_passes': 2}
        }

        # Current state
        self.analysis_type = 'standard'
        self.current_pass = PassState(
            pass_number=1,
            attempt=1,
            agents_to_consult=[],
            agents_completed=[],
            specialist_results={},
            insights=[]
        )

        # Historical data
        self.pass_history: List[PassState] = []
        self.max_attempts_per_pass = 3

        # All insights across all passes
        self.all_insights: List[Dict[str, Any]] = []

    def reset_for_question(self, analysis_type: str, agents_to_consult: List[str]):
        """
        Reset coordinator for new question.

        Args:
            analysis_type: "standard" or "summary"
            agents_to_consult: List of agent names to consult
        """
        self.analysis_type = analysis_type
        self.current_pass = PassState(
            pass_number=1,
            attempt=1,
            agents_to_consult=agents_to_consult,
            agents_completed=[],
            specialist_results={},
            insights=[]
        )
        self.pass_history = []
        self.all_insights = []

    def is_pass_complete(self) -> bool:
        """Check if current pass is complete (all agents consulted)"""
        return len(self.current_pass.agents_completed) >= len(self.current_pass.agents_to_consult)

    def is_all_passes_complete(self) -> bool:
        """Check if all passes are complete"""
        max_passes = self.pass_config[self.analysis_type]['max_passes']
        return self.current_pass.pass_number >= max_passes

    def add_agent_result(self, agent_type: str, result: Dict[str, Any]):
        """
        Record result from an agent.

        Args:
            agent_type: Agent name (code, docs, web)
            result: Agent result dictionary
        """
        if agent_type not in self.current_pass.agents_completed:
            self.current_pass.agents_completed.append(agent_type)

        self.current_pass.specialist_results[agent_type] = result

        # Collect insights
        if result.get('success') and 'insights' in result:
            self.current_pass.insights.extend(result['insights'])
            self.all_insights.extend(result['insights'])

    def decide_next_action(self, question: str) -> Dict[str, str]:
        """
        Use LLM to decide next action after pass completion.

        Args:
            question: Original question

        Returns:
            Decision dict with:
            - action: "retry", "next_pass", or "complete"
            - reasoning: Explanation
            - Additional fields based on action
        """
        # Build analysis prompt
        successful_agents = len([a for a in self.current_pass.agents_completed
                                if self.current_pass.specialist_results.get(a, {}).get('success', False)])

        prompt = f"""Analyze the results of Pass {self.current_pass.pass_number} (Attempt {self.current_pass.attempt}) for this question:

Question: "{question}"
Analysis type: {self.analysis_type}
Current pass: {self.current_pass.pass_number}/{self.pass_config[self.analysis_type]['max_passes']}

Pass Results:
- Agents consulted: {len(self.current_pass.agents_completed)}/{len(self.current_pass.agents_to_consult)}
- Successful agents: {successful_agents}
- Total insights gathered: {len(self.current_pass.insights)}

Top insights:
{[insight.get('content', '')[:100] + '...' for insight in self.current_pass.insights[:3]]}

Determine the next action:
1. "retry" - If results are insufficient and retry is warranted (max {self.max_attempts_per_pass} attempts)
2. "next_pass" - If results are good enough to proceed to next pass
3. "complete" - If analysis is sufficient to generate final answer

Provide JSON response:
{{"action": "retry|next_pass|complete", "reasoning": "why", "context_sharing": true/false, "focus_areas": ["area1", ...]}}
"""

        # Get LLM decision
        try:
            llm_response = self.llm_callback(prompt, "You are analyzing multi-pass coordination. Return JSON only.")

            result = LLMResponseParser.safe_parse_llm_response(
                llm_response,
                required_keys=['action'],
                fallback=self._get_fallback_decision()
            )

            return result

        except Exception as e:
            print(f"⚠️ LLM decision failed: {e}, using fallback")
            return self._get_fallback_decision()

    def _get_fallback_decision(self) -> Dict[str, Any]:
        """Get fallback decision if LLM fails"""
        min_insights = self.config.get('agents', {}).get('thresholds', {}).get('min_insights_for_pass', 2)
        current_insights = len(self.current_pass.insights)

        # For summary, always proceed to Pass 2 if on Pass 1
        if self.analysis_type == 'summary' and self.current_pass.pass_number == 1:
            return {
                'action': 'next_pass',
                'reasoning': 'Summary Pass 1 complete, proceeding to Pass 2 (fallback)',
                'context_sharing': True,
                'focus_areas': []
            }

        # Retry if insufficient insights
        if current_insights < min_insights and self.current_pass.attempt < self.max_attempts_per_pass:
            return {
                'action': 'retry',
                'reasoning': f'Insufficient insights ({current_insights} < {min_insights}), retrying (fallback)',
                'retry_reason': 'Low insight count',
                'context_sharing': False,
                'focus_areas': []
            }

        # Move to next pass if available
        if self.current_pass.pass_number < self.pass_config[self.analysis_type]['max_passes']:
            return {
                'action': 'next_pass',
                'reasoning': 'Proceeding to next pass (fallback)',
                'context_sharing': True,
                'focus_areas': []
            }

        # Otherwise complete
        return {
            'action': 'complete',
            'reasoning': 'Max passes reached (fallback)',
            'context_sharing': False,
            'focus_areas': []
        }

    def retry_current_pass(self, retry_reason: str):
        """
        Retry current pass with same agents.

        Args:
            retry_reason: Reason for retry
        """
        # Save current pass to history
        self.pass_history.append(self.current_pass)

        # Increment attempt
        new_attempt = self.current_pass.attempt + 1

        # Reset for retry
        self.current_pass = PassState(
            pass_number=self.current_pass.pass_number,
            attempt=new_attempt,
            agents_to_consult=self.current_pass.agents_to_consult.copy(),
            agents_completed=[],
            specialist_results={},
            insights=[]
        )

        print(f"🔄 Retrying Pass {self.current_pass.pass_number} (Attempt {new_attempt}): {retry_reason}")

    def start_next_pass(self, context_sharing: bool = False, focus_areas: List[str] = None):
        """
        Start next pass.

        Args:
            context_sharing: Whether to share context from previous pass
            focus_areas: Specific areas to focus on
        """
        # Save current pass to history
        self.pass_history.append(self.current_pass)

        # Create new pass
        new_pass_number = self.current_pass.pass_number + 1

        self.current_pass = PassState(
            pass_number=new_pass_number,
            attempt=1,
            agents_to_consult=self.current_pass.agents_to_consult.copy(),
            agents_completed=[],
            specialist_results={} if not context_sharing else self.current_pass.specialist_results.copy(),
            insights=[],
            context_sharing_enabled=context_sharing,
            focus_areas=focus_areas or []
        )

        print(f"🚀 Starting Pass {new_pass_number}/{self.pass_config[self.analysis_type]['max_passes']}")
        print(f"🔗 Context sharing: {'✅ Enabled' if context_sharing else '❌ Disabled'}")
        if focus_areas:
            print(f"🎯 Focus areas: {', '.join(focus_areas)}")

    def build_enhanced_question(self, agent_type: str, original_question: str) -> str:
        """
        Build pass-specific enhanced question for an agent.

        Args:
            agent_type: Agent name
            original_question: Original user question

        Returns:
            Enhanced question with context
        """
        if self.analysis_type == 'summary':
            return self._build_summary_pass_question(agent_type, original_question)
        elif self.current_pass.context_sharing_enabled and self.current_pass.pass_number > 1:
            return self._build_context_aware_question(agent_type, original_question)
        else:
            return original_question

    def _build_summary_pass_question(self, agent_type: str, original_question: str) -> str:
        """Build pass-specific question for summary analysis"""
        if self.current_pass.pass_number == 1:
            return f"PASS 1 - High-level overview: {original_question}. Focus on overall structure and organization."
        elif self.current_pass.pass_number == 2:
            # Get brief context from Pass 1
            pass1_context = self._get_brief_pass_context(1)
            return f"PASS 2 - Detailed analysis: {original_question}. Previous context: {pass1_context}. Now provide deep technical insights."
        else:
            return original_question

    def _build_context_aware_question(self, agent_type: str, original_question: str) -> str:
        """Build context-aware question with insights from previous passes"""
        previous_insights = []
        for pass_state in self.pass_history:
            previous_insights.extend(pass_state.insights)

        if not previous_insights:
            return original_question

        # Build context summary (top 5 insights)
        context_lines = []
        for insight in previous_insights[:5]:
            content = insight.get('content', '')[:100]
            context_lines.append(f"- {content}")

        enhanced = f"""Based on previous analysis insights:
{chr(10).join(context_lines)}

Now focusing on {agent_type} analysis, please address: {original_question}

Consider how your findings relate to or build upon the previous insights."""

        return enhanced

    def _get_brief_pass_context(self, pass_number: int) -> str:
        """Get brief context from specific pass"""
        if pass_number > len(self.pass_history):
            return "No previous context"

        pass_state = self.pass_history[pass_number - 1]
        insights = pass_state.insights

        if not insights:
            return "No previous insights"

        # Get top 3 insights, truncated
        context_parts = []
        for insight in insights[:3]:
            content = insight.get('content', '')
            content = content[:80] + '...' if len(content) > 80 else content
            context_parts.append(content)

        return '; '.join(context_parts)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of coordination state"""
        return {
            'analysis_type': self.analysis_type,
            'current_pass': self.current_pass.pass_number,
            'current_attempt': self.current_pass.attempt,
            'total_passes_completed': len(self.pass_history),
            'total_insights': len(self.all_insights),
            'agents_to_consult': self.current_pass.agents_to_consult,
            'agents_completed': self.current_pass.agents_completed,
            'context_sharing': self.current_pass.context_sharing_enabled,
            'focus_areas': self.current_pass.focus_areas
        }
