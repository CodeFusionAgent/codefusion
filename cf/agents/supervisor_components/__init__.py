"""
Supervisor Components Module

Components for SupervisorAgent orchestration:
- AgentCoordinator: Handles agent consultation and coordination
- ResultSynthesizer: Synthesizes specialist results into narratives
"""

from cf.agents.supervisor_components.agent_coordinator import AgentCoordinator
from cf.agents.supervisor_components.result_synthesizer import ResultSynthesizer

__all__ = [
    'AgentCoordinator',
    'ResultSynthesizer'
]
