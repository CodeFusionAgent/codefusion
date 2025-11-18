"""
Supervisor Manager Components

Extracted manager classes from SupervisorAgent god class refactoring.
Each manager handles a specific responsibility following Single Responsibility Principle.
"""

from cf.agents.managers.coordination import CoordinationManager
from cf.agents.managers.synthesis import SynthesisEngine
from cf.agents.managers.context import ContextManager

__all__ = [
    'CoordinationManager',
    'SynthesisEngine',
    'ContextManager',
]
