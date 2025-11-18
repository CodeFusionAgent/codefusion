"""
Synthesis Components Module

Components for SynthesisPipeline:
- PromptBuilder: Builds synthesis prompts with various context sections
- CrossFileAnalyzer: Analyzes relationships between files
- PatternDetector: Detects design patterns from KB or code
- ExecutionTracer: Traces execution paths and call sequences
"""

from cf.agents.pipelines.synthesis_components.prompt_builder import PromptBuilder
from cf.agents.pipelines.synthesis_components.cross_file_analyzer import CrossFileAnalyzer
from cf.agents.pipelines.synthesis_components.pattern_detector import PatternDetector
from cf.agents.pipelines.synthesis_components.execution_tracer import ExecutionTracer

__all__ = [
    'PromptBuilder',
    'CrossFileAnalyzer',
    'PatternDetector',
    'ExecutionTracer'
]
