"""
BaseAgent - Clean, Simple Base Class

Provides common functionality for all CodeFusion agents:
- Tool access via registry
- LLM interface 
- Tracing via decorators (clean!)
- Simple caching
- Loop detection and recovery
"""

import time
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path

from cf.tools.registry import ToolRegistry
from cf.llm.client import LLMClient
from cf.trace.tracer import Tracer, trace_method
from cf.cache.semantic import SemanticCache
from cf.utils.logger import get_logger


class BaseAgent(ABC):
    """
    Base class for all CodeFusion agents.
    
    Clean design with decorator-based tracing.
    """
    
    def __init__(self, repo_path: str, config: Dict[str, Any], agent_name: str):
        self.repo_path = repo_path
        self.config = config
        self.agent_name = agent_name
        
        # Setup logging
        self.logger = get_logger(agent_name, config)
        
        # Core components
        self.tools = ToolRegistry(repo_path)
        self.llm = LLMClient(config.get('llm', {}))
        self.tracer = Tracer(agent_name, config.get('trace', {}))
        self.cache = SemanticCache(agent_name, config.get('cache', {}))

        # Connect components
        self.llm.set_tracer(self.tracer, f"{agent_name}_session")
        self.cache.set_llm_client(self.llm)
        self.tools.llm_tools.set_llm_client(self.llm)        
        
        # Agent state
        self.iteration = 0
        self.max_iterations = config.get('agents', {}).get('max_iterations', 10)
        self.actions_taken = []
        self.results = {}
        self.insights = []
        
        # Start tracing session
        self.session_id = self.tracer.start_session(f"{agent_name}_analysis")
    
    @trace_method("tool_call")
    def use_tool(self, tool_name: str, **params) -> Dict[str, Any]:
        """Use a tool with caching and metrics tracking"""
        # Check cache first
        cache_key = f"{tool_name}_{json.dumps(params, sort_keys=True)}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            cached_result['cached'] = True
            return cached_result

        # Execute tool
        result = self.tools.execute(tool_name, **params)

        # Cache successful results
        if not result.get('error'):
            self.cache.set(cache_key, result)

        # Track tool usage for metrics (if agent has tracking)
        if hasattr(self, 'tool_results'):
            self.tool_results.append({
                'tool': tool_name,
                'params': params,
                'result': result
            })
        if hasattr(self, 'tools_used'):
            self.tools_used.add(tool_name)

        return result
    
    @trace_method("llm_call")
    def call_llm(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Call LLM"""
        return self.llm.generate(prompt, system_prompt)

    def call_llm_fast(self, prompt: str, system_prompt: str = "", temperature: float = None, **kwargs) -> Dict[str, Any]:
        """Call LLM using fast model for routine tasks (file summaries, completeness checks)

        This method uses a faster, cheaper model (e.g., gpt-4o-mini) configured
        in the llm.fast_model setting. Falls back to main model if not configured.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Optional temperature override (0.0-1.0, lower = more deterministic)
            **kwargs: Additional arguments passed to LLM

        Use this for:
        - File summaries
        - Completeness evaluation
        - Simple analysis tasks

        Keep main model for:
        - Final synthesis
        - Complex reasoning
        - Answer generation
        """
        if temperature is not None:
            kwargs['temperature'] = temperature
        return self.llm.generate_fast(prompt, system_prompt, **kwargs)

    @trace_method("loop_detection")
    def detect_loop(self) -> bool:
        """Detect if agent is stuck in a loop"""
        if len(self.actions_taken) < 3:
            return False
        
        # Check for repeated actions
        recent_actions = self.actions_taken[-3:]
        return len(set(recent_actions)) <= 1
    
    @trace_method("loop_detection")
    def recover_from_loop(self) -> bool:
        """Attempt recovery from stuck state"""
        # Simple recovery: force completion
        return True
    
    @trace_method("analysis")
    def analyze(self, question: str) -> Dict[str, Any]:
        """
        Main analysis method - runs the agent's analysis loop
        
        Args:
            question: The user's question
            
        Returns:
            Analysis results with insights, data, confidence
        """
        try:
            # Main analysis loop
            while self.iteration < self.max_iterations:
                self.iteration += 1
                
                # Loop detection
                if self.detect_loop():
                    if not self.recover_from_loop():
                        break
                
                # Execute one analysis step
                action_taken = self._analyze_step(question)
                self.actions_taken.append(action_taken)
                
                # Check if analysis is complete
                if self._is_analysis_complete(question):
                    break
            
            # Generate final results
            result = self._generate_results(question)
            result['iterations'] = self.iteration
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'iterations': self.iteration
            }
        
        finally:
            self.tracer.end_session(self.session_id)
    
    @abstractmethod
    def _analyze_step(self, question: str) -> str:
        """Execute one analysis step. Return description of action taken."""
        pass
    
    @abstractmethod
    def _is_analysis_complete(self, question: str) -> bool:
        """Check if analysis is complete."""
        pass
    
    @abstractmethod
    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate final analysis results."""
        pass
    
    def get_confidence(self, level: str) -> float:
        """Get confidence value from config by level name

        Args:
            level: One of 'high', 'medium', 'low', 'error', 'partial', 'max'

        Returns:
            Confidence value from config
        """
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        confidence_map = {
            'high': thresholds.get('high_confidence', 0.8),
            'medium': thresholds.get('medium_confidence', 0.7),
            'low': thresholds.get('low_confidence', 0.6),
            'error': thresholds.get('error_confidence', 0.2),
            'partial': thresholds.get('partial_confidence', 0.5),
            'max': thresholds.get('max_confidence', 0.9)
        }
        return confidence_map.get(level, thresholds.get('high_confidence', 0.8))

    def add_insight(self, content: str, confidence: float = None, source: str = ""):
        """Add an insight to results

        Args:
            content: Insight content
            confidence: Confidence score (0.0-1.0), defaults to high_confidence from config
            source: Source of insight
        """
        # Use config default if not specified
        if confidence is None:
            confidence = self.get_confidence('high')

        self.insights.append({
            'content': content,
            'confidence': confidence,
            'source': source or self.agent_name,
            'timestamp': time.time()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of agent analysis"""
        return {
            'agent': self.agent_name,
            'insights': len(self.insights),
            'iterations': self.iteration,
            'results': self.results
        }
