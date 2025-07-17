"""
ReAct (Reasoning + Acting) Agent Base Class

This module provides the foundation for agents that follow the ReAct pattern:
- Reason: Think about what to do next
- Act: Execute actions using available tools
- Observe: Reflect on the results and plan next steps
"""

import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set
from enum import Enum
from pathlib import Path

from ..config import CfConfig
from ..aci.repo import CodeRepo
from .react_config import ReActConfig, react_config
from .react_tracing import ReActTracer, tracer


class ActionType(Enum):
    """Types of actions an agent can take."""
    SCAN_DIRECTORY = "scan_directory"
    LIST_FILES = "list_files"
    READ_FILE = "read_file"
    SEARCH_FILES = "search_files"
    ANALYZE_CODE = "analyze_code"
    LLM_REASONING = "llm_reasoning"
    LLM_SUMMARY = "llm_summary"
    CACHE_LOOKUP = "cache_lookup"
    CACHE_STORE = "cache_store"


@dataclass
class ReActState:
    """Current state of the ReAct loop."""
    goal: str
    current_context: Dict[str, Any] = field(default_factory=dict)
    observations: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 20
    reasoning_history: List[str] = field(default_factory=list)
    tool_results: Dict[str, Any] = field(default_factory=dict)
    cache_hits: int = 0
    error_count: int = 0
    stuck_detection: List[str] = field(default_factory=list)


@dataclass
class ReActAction:
    """An action to be taken by the agent."""
    action_type: ActionType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    tool_name: str = ""


@dataclass
class ReActObservation:
    """Observation from an action."""
    action_taken: str
    result: Any
    success: bool
    insight: str
    confidence: float = 0.0
    suggests_next_action: Optional[str] = None
    goal_progress: float = 0.0  # 0.0 to 1.0


class ReActCache:
    """Caching system for ReAct agents with optional persistence."""
    
    def __init__(self, max_size: int = 1000, cache_dir: Optional[str] = None, ttl: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}  # key -> {value, timestamp, access_time}
        self.max_size = max_size
        self.ttl = ttl  # time to live in seconds
        self.cache_dir = Path(cache_dir) if cache_dir else None
        
        # Create cache directory if specified
        if self.cache_dir:
            self.cache_dir.mkdir(exist_ok=True)
            self._load_persistent_cache()
        
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self.cache:
            cache_entry = self.cache[key]
            current_time = time.time()
            
            # Check if expired
            if current_time - cache_entry['timestamp'] > self.ttl:
                del self.cache[key]
                return None
            
            # Update access time
            cache_entry['access_time'] = current_time
            return cache_entry['value']
        
        return None
    
    def set(self, key: str, value: Any):
        """Set cached value."""
        current_time = time.time()
        
        # Remove expired entries
        self._cleanup_expired()
        
        # Remove LRU if at capacity
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        self.cache[key] = {
            'value': value,
            'timestamp': current_time,
            'access_time': current_time
        }
        
        # Persist if cache directory is set
        if self.cache_dir:
            self._persist_entry(key, self.cache[key])
    
    def clear(self):
        """Clear all cached values."""
        self.cache.clear()
        if self.cache_dir:
            # Clear persistent cache files
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
    
    def _cleanup_expired(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if current_time - entry['timestamp'] > self.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
            if self.cache_dir:
                cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
                if cache_file.exists():
                    cache_file.unlink()
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self.cache:
            return
        
        lru_key = min(self.cache.keys(), key=lambda k: self.cache[k]['access_time'])
        del self.cache[lru_key]
        
        if self.cache_dir:
            cache_file = self.cache_dir / f"{self._hash_key(lru_key)}.json"
            if cache_file.exists():
                cache_file.unlink()
    
    def _load_persistent_cache(self):
        """Load cache from persistent storage."""
        if not self.cache_dir.exists():
            return
        
        current_time = time.time()
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cache_entry = json.load(f)
                
                # Check if expired
                if current_time - cache_entry['timestamp'] > self.ttl:
                    cache_file.unlink()
                    continue
                
                # Reconstruct key from filename (this is a simplified approach)
                key = cache_file.stem
                self.cache[key] = cache_entry
                
            except Exception as e:
                # Remove corrupted cache files
                cache_file.unlink()
    
    def _persist_entry(self, key: str, entry: Dict[str, Any]):
        """Persist a cache entry to disk."""
        try:
            cache_file = self.cache_dir / f"{self._hash_key(key)}.json"
            with open(cache_file, 'w') as f:
                json.dump(entry, f, default=str)
        except Exception:
            # Silently fail persistence - cache still works in memory
            pass
    
    def _hash_key(self, key: str) -> str:
        """Create a safe filename from cache key."""
        import hashlib
        return hashlib.md5(key.encode()).hexdigest()


class ReActAgent(ABC):
    """
    Base class for ReAct agents that can reason, act, and observe.
    """
    
    def __init__(self, repo: CodeRepo, config: CfConfig, agent_name: str, react_config_param: Optional[ReActConfig] = None):
        self.repo = repo
        self.config = config
        self.agent_name = agent_name
        self.react_config = react_config_param or react_config
        self.logger = logging.getLogger(f"ReAct.{agent_name}")
        
        # ReAct state management
        self.state = ReActState(goal="", max_iterations=self.react_config.max_iterations)
        
        # Initialize persistent cache with configuration
        cache_dir = None
        if self.react_config.cache_enabled and self.react_config.trace_directory:
            cache_dir = str(Path(self.react_config.trace_directory) / "cache")
        
        self.cache = ReActCache(
            max_size=self.react_config.cache_max_size,
            cache_dir=cache_dir,
            ttl=self.react_config.cache_ttl
        )
        
        # Error handling
        self.error_patterns: Set[str] = set()
        self.recovery_strategies: Dict[str, Callable] = {}
        self.max_same_action_repeats = self.react_config.max_same_action_repeats
        self.consecutive_errors = 0
        
        # Tracing
        self.session_id: Optional[str] = None
        self.tracer = tracer if self.react_config.tracing_enabled else None
        
        # Available tools
        self.tools = {
            ActionType.SCAN_DIRECTORY: self._tool_scan_directory,
            ActionType.LIST_FILES: self._tool_list_files,
            ActionType.READ_FILE: self._tool_read_file,
            ActionType.SEARCH_FILES: self._tool_search_files,
            ActionType.ANALYZE_CODE: self._tool_analyze_code,
            ActionType.LLM_REASONING: self._tool_llm_reasoning,
            ActionType.LLM_SUMMARY: self._tool_llm_summary,
            ActionType.CACHE_LOOKUP: self._tool_cache_lookup,
            ActionType.CACHE_STORE: self._tool_cache_store,
        }
        
        # Initialize recovery strategies
        self._setup_recovery_strategies()
    
    def execute_react_loop(self, goal: str, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute the main ReAct loop: Reason → Act → Observe.
        
        Args:
            goal: The goal to achieve
            max_iterations: Maximum number of iterations (uses config default if None)
            
        Returns:
            Final results and insights
        """
        max_iterations = max_iterations or self.react_config.max_iterations
        self.state = ReActState(goal=goal, max_iterations=max_iterations)
        self.logger.info(f"🎯 Starting ReAct loop for: {goal}")
        
        # Start tracing session
        if self.tracer:
            self.session_id = self.tracer.start_session(self.agent_name, goal)
        
        start_time = time.time()
        total_timeout = start_time + self.react_config.total_timeout
        
        try:
            while not self._is_goal_achieved() and self.state.iteration < max_iterations:
                # Check total timeout
                if time.time() > total_timeout:
                    self.logger.warning(f"⏰ Total timeout ({self.react_config.total_timeout}s) reached")
                    break
                
                self.state.iteration += 1
                iteration_start = time.time()
                iteration_timeout = iteration_start + self.react_config.iteration_timeout
                
                self.logger.info(f"🔄 ReAct Iteration {self.state.iteration}")
                
                try:
                    # REASON: What should I do next?
                    reason_start = time.time()
                    reasoning = self.reason()
                    reason_duration = time.time() - reason_start
                    self.state.reasoning_history.append(reasoning)
                    
                    if self.tracer:
                        self.tracer.trace_phase(self.session_id, 'reason', self.state.iteration, 
                                              {'reasoning': reasoning}, reason_duration)
                    
                    # Check iteration timeout
                    if time.time() > iteration_timeout:
                        self.logger.warning(f"⏰ Iteration timeout reached")
                        break
                    
                    # ACT: Take the reasoned action
                    act_start = time.time()
                    action = self.plan_action(reasoning)
                    observation = self.act(action)
                    act_duration = time.time() - act_start
                    
                    if self.tracer:
                        self.tracer.trace_phase(self.session_id, 'act', self.state.iteration, 
                                              {'action': action.description, 'success': observation.success}, 
                                              act_duration, observation.success, 
                                              None if observation.success else observation.insight)
                    
                    # OBSERVE: Reflect on what happened
                    observe_start = time.time()
                    self.observe(observation)
                    observe_duration = time.time() - observe_start
                    
                    if self.tracer:
                        self.tracer.trace_phase(self.session_id, 'observe', self.state.iteration, 
                                              {'insight': observation.insight, 'goal_progress': observation.goal_progress}, 
                                              observe_duration)
                    
                    # Reset consecutive errors on success
                    if observation.success:
                        self.consecutive_errors = 0
                    else:
                        self.consecutive_errors += 1
                        
                        # Check for too many consecutive errors
                        if self.consecutive_errors >= self.react_config.max_consecutive_errors:
                            self.logger.error(f"❌ Too many consecutive errors ({self.consecutive_errors})")
                            break
                    
                    # Check for getting stuck
                    if self._detect_stuck_loop():
                        self.logger.warning("🔄 Detected stuck loop, attempting recovery")
                        if not self._attempt_recovery():
                            self.logger.error("❌ Recovery failed, stopping")
                            break
                    
                except Exception as e:
                    self.logger.error(f"❌ Error in iteration {self.state.iteration}: {e}")
                    self.state.error_count += 1
                    self.consecutive_errors += 1
                    
                    if self.tracer:
                        self.tracer.trace_phase(self.session_id, 'error', self.state.iteration, 
                                              {'error': str(e)}, 0.0, False, str(e))
                    
                    if not self.react_config.error_recovery_enabled or self.state.error_count >= self.react_config.max_errors:
                        break
                
                # Brief pause to prevent overwhelming
                time.sleep(0.1)
            
            # Generate final results
            final_results = self._generate_final_results(time.time() - start_time)
            
            # End tracing session
            if self.tracer:
                self.tracer.end_session(self.session_id, final_results)
            
            return final_results
            
        except Exception as e:
            self.logger.error(f"❌ ReAct loop failed: {e}")
            error_results = self._generate_error_results(str(e), time.time() - start_time)
            
            # End tracing session with error
            if self.tracer:
                self.tracer.end_session(self.session_id, error_results)
            
            return error_results
    
    @abstractmethod
    def reason(self) -> str:
        """
        Reasoning phase: Think about what to do next based on current state.
        
        Returns:
            Reasoning about next action
        """
        pass
    
    @abstractmethod
    def plan_action(self, reasoning: str) -> ReActAction:
        """
        Plan the next action based on reasoning.
        
        Args:
            reasoning: The reasoning output
            
        Returns:
            Action to take
        """
        pass
    
    def act(self, action: ReActAction) -> ReActObservation:
        """
        Execute an action using available tools with validation and retry logic.
        
        Args:
            action: Action to execute
            
        Returns:
            Observation from the action
        """
        self.logger.info(f"🎬 Acting: {action.description}")
        
        # Validate action parameters if enabled
        if self.react_config.tool_validation_enabled:
            validation_error = self._validate_action_parameters(action)
            if validation_error:
                return ReActObservation(
                    action_taken=action.description,
                    result=None,
                    success=False,
                    insight=f"Parameter validation failed: {validation_error}",
                    confidence=0.0
                )
        
        # Try executing with retries
        for attempt in range(self.react_config.max_tool_retries + 1):
            try:
                # Check if we have the tool
                if action.action_type not in self.tools:
                    return ReActObservation(
                        action_taken=action.description,
                        result=None,
                        success=False,
                        insight=f"Tool {action.action_type} not available",
                        confidence=0.0
                    )
                
                # Execute the tool with timeout
                tool_func = self.tools[action.action_type]
                start_time = time.time()
                
                result = self._execute_tool_with_timeout(tool_func, action.parameters)
                
                execution_time = time.time() - start_time
                
                # Validate result if enabled
                if self.react_config.tool_validation_enabled:
                    validation_result = self._validate_tool_result(action, result)
                    if not validation_result['valid']:
                        if attempt < self.react_config.max_tool_retries:
                            self.logger.warning(f"⚠️ Tool result validation failed, retrying ({attempt + 1}/{self.react_config.max_tool_retries})")
                            continue
                        else:
                            return ReActObservation(
                                action_taken=action.description,
                                result=result,
                                success=False,
                                insight=f"Result validation failed: {validation_result['error']}",
                                confidence=0.0
                            )
                
                # Record the successful action
                self.state.actions_taken.append(action.description)
                self.state.tool_results[action.action_type.value] = result
                
                # Create observation
                observation = ReActObservation(
                    action_taken=action.description,
                    result=result,
                    success=True,
                    insight=self._generate_insight(action, result),
                    confidence=self._calculate_confidence(action, result)
                )
                
                # Log execution time if significant
                if execution_time > 1.0:
                    self.logger.info(f"⏱️ Tool execution took {execution_time:.2f}s")
                
                return observation
                
            except Exception as e:
                self.logger.error(f"❌ Action failed (attempt {attempt + 1}): {e}")
                
                # If we have retries left, try recovery
                if attempt < self.react_config.max_tool_retries:
                    recovery_action = self._attempt_tool_recovery(action, str(e))
                    if recovery_action:
                        self.logger.info(f"🔧 Attempting recovery: {recovery_action}")
                        time.sleep(0.5)  # Brief pause before retry
                        continue
                
                # Final failure
                self.state.error_count += 1
                return ReActObservation(
                    action_taken=action.description,
                    result=None,
                    success=False,
                    insight=f"Action failed after {attempt + 1} attempts: {str(e)}",
                    confidence=0.0
                )
    
    def observe(self, observation: ReActObservation):
        """
        Observation phase: Reflect on the action result and update state.
        
        Args:
            observation: Observation from the action
        """
        self.logger.info(f"👁️ Observing: {observation.insight}")
        
        # Add to observations
        self.state.observations.append(observation.insight)
        
        # Update context based on observation
        self._update_context(observation)
        
        # Check for goal progress
        if observation.goal_progress > 0:
            self.logger.info(f"📈 Goal progress: {observation.goal_progress:.1%}")
    
    def _is_goal_achieved(self) -> bool:
        """Check if the goal has been achieved."""
        # This is a simple heuristic - subclasses can override
        return len(self.state.observations) > 0 and any(
            "completed" in obs.lower() or "achieved" in obs.lower() 
            for obs in self.state.observations[-3:]
        )
    
    def _detect_stuck_loop(self) -> bool:
        """Detect if the agent is stuck in a loop."""
        if len(self.state.actions_taken) < 5:  # Require more actions before detecting
            return False
        
        # Check for repeated actions (same action 4+ times in a row)
        recent_actions = self.state.actions_taken[-4:]
        if len(set(recent_actions)) == 1:  # Same action repeated 4 times
            return True
        
        # Check for oscillating between two actions (more conservative)
        if len(self.state.actions_taken) >= 6:
            last_six = self.state.actions_taken[-6:]
            # Check if pattern repeats 3 times
            if (last_six[0] == last_six[2] == last_six[4] and 
                last_six[1] == last_six[3] == last_six[5]):
                return True
        
        return False
    
    def _attempt_recovery(self):
        """Attempt to recover from stuck state."""
        recovery_action = self._get_recovery_action()
        if recovery_action:
            self.logger.info(f"🔧 Attempting recovery: {recovery_action}")
            # Add some randomness to break the loop
            self.state.current_context['recovery_attempt'] = time.time()
            self.state.stuck_detection.append(recovery_action)
    
    def _get_recovery_action(self) -> Optional[str]:
        """Get a recovery action based on current state."""
        if len(self.state.stuck_detection) > 3:
            return "escalate_to_human"
        
        recent_actions = self.state.actions_taken[-3:]
        if all("read_file" in action for action in recent_actions):
            return "switch_to_directory_scan"
        elif all("scan_directory" in action for action in recent_actions):
            return "switch_to_file_search"
        else:
            return "try_llm_reasoning"
    
    # Tool implementations
    def _tool_scan_directory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Scan a directory and return its contents."""
        directory = params.get('directory', '.')
        max_depth = params.get('max_depth', 2)
        
        cache_key = f"scan_dir_{directory}_{max_depth}"
        cached = self.cache.get(cache_key)
        if cached:
            self.state.cache_hits += 1
            return cached
        
        try:
            contents = []
            for file_info in self.repo.walk_repository():
                if file_info.path.startswith(directory):
                    # Calculate depth
                    depth = len(Path(file_info.path).relative_to(Path(directory)).parts) - 1
                    if depth <= max_depth:
                        contents.append({
                            'path': file_info.path,
                            'is_directory': file_info.is_directory,
                            'size': file_info.size if not file_info.is_directory else 0
                        })
            
            result = {
                'directory': directory,
                'contents': contents,
                'total_files': len([c for c in contents if not c['is_directory']]),
                'total_directories': len([c for c in contents if c['is_directory']])
            }
            
            self.cache.set(cache_key, result)
            return result
            
        except Exception as e:
            return {'error': str(e), 'directory': directory}
    
    def _tool_list_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List files matching criteria."""
        pattern = params.get('pattern', '*')
        directory = params.get('directory', '.')
        
        cache_key = f"list_files_{pattern}_{directory}"
        cached = self.cache.get(cache_key)
        if cached:
            self.state.cache_hits += 1
            return cached
        
        try:
            files = []
            for file_info in self.repo.walk_repository():
                if not file_info.is_directory and file_info.path.startswith(directory):
                    # Simple pattern matching
                    if pattern == '*' or pattern in file_info.path:
                        files.append({
                            'path': file_info.path,
                            'size': file_info.size,
                            'extension': Path(file_info.path).suffix
                        })
            
            result = {
                'pattern': pattern,
                'directory': directory,
                'files': files,
                'count': len(files)
            }
            
            self.cache.set(cache_key, result)
            return result
            
        except Exception as e:
            return {'error': str(e), 'pattern': pattern}
    
    def _tool_read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read a file's contents."""
        file_path = params.get('file_path', '')
        max_lines = params.get('max_lines', 100)
        
        cache_key = f"read_file_{file_path}_{max_lines}"
        cached = self.cache.get(cache_key)
        if cached:
            self.state.cache_hits += 1
            return cached
        
        try:
            content = self.repo.read_file(file_path)
            lines = content.split('\n')
            
            if len(lines) > max_lines:
                content = '\n'.join(lines[:max_lines])
                truncated = True
            else:
                truncated = False
            
            result = {
                'file_path': file_path,
                'content': content,
                'line_count': len(lines),
                'truncated': truncated,
                'size': len(content)
            }
            
            self.cache.set(cache_key, result)
            return result
            
        except Exception as e:
            return {'error': str(e), 'file_path': file_path}
    
    def _tool_search_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for patterns in files."""
        pattern = params.get('pattern', '')
        file_types = params.get('file_types', [])
        max_results = params.get('max_results', 50)
        
        cache_key = f"search_files_{pattern}_{','.join(file_types)}_{max_results}"
        cached = self.cache.get(cache_key)
        if cached:
            self.state.cache_hits += 1
            return cached
        
        try:
            results = []
            for file_info in self.repo.walk_repository():
                if file_info.is_directory:
                    continue
                
                # Check file type filter
                if file_types and not any(file_info.path.endswith(ft) for ft in file_types):
                    continue
                
                try:
                    content = self.repo.read_file(file_info.path)
                    if pattern.lower() in content.lower():
                        # Find line numbers
                        lines = content.split('\n')
                        matching_lines = []
                        for i, line in enumerate(lines):
                            if pattern.lower() in line.lower():
                                matching_lines.append({'line_num': i+1, 'content': line.strip()})
                        
                        results.append({
                            'file_path': file_info.path,
                            'matches': matching_lines[:10],  # Limit matches per file
                            'total_matches': len(matching_lines)
                        })
                        
                        if len(results) >= max_results:
                            break
                            
                except Exception:
                    continue  # Skip files that can't be read
            
            result = {
                'pattern': pattern,
                'file_types': file_types,
                'results': results,
                'total_files_searched': len(results)
            }
            
            self.cache.set(cache_key, result)
            return result
            
        except Exception as e:
            return {'error': str(e), 'pattern': pattern}
    
    def _tool_analyze_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code structure."""
        file_path = params.get('file_path', '')
        analysis_type = params.get('analysis_type', 'basic')
        
        cache_key = f"analyze_code_{file_path}_{analysis_type}"
        cached = self.cache.get(cache_key)
        if cached:
            self.state.cache_hits += 1
            return cached
        
        try:
            content = self.repo.read_file(file_path)
            
            # Basic analysis
            lines = content.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            
            result = {
                'file_path': file_path,
                'total_lines': len(lines),
                'non_empty_lines': len(non_empty_lines),
                'estimated_complexity': len(non_empty_lines) // 10,  # Simple heuristic
                'language': self._detect_language(file_path),
                'key_patterns': self._extract_key_patterns(content)
            }
            
            self.cache.set(cache_key, result)
            return result
            
        except Exception as e:
            return {'error': str(e), 'file_path': file_path}
    
    def _tool_llm_reasoning(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM for reasoning about the current state."""
        context = params.get('context', '')
        question = params.get('question', '')
        agent_type = params.get('agent_type', self.agent_name.lower())
        
        # Try real LLM first, fallback to simple LLM
        try:
            from ..llm.real_llm import real_llm
            result = real_llm.reasoning(context, question, agent_type)
            return result
        except Exception as e:
            self.logger.warning(f"Real LLM failed, using fallback: {e}")
            # Fallback to simple reasoning
            from ..llm.simple_llm import llm
            try:
                result = llm.reasoning(context, question, agent_type)
                result['fallback'] = True
                return result
            except Exception as e2:
                return {
                    'reasoning': f"Based on the context, I should focus on {question}",
                    'confidence': 0.5,
                    'suggested_actions': ['read_file', 'search_files', 'analyze_code'],
                    'error': str(e2),
                    'fallback': True
                }
    
    def _tool_llm_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to generate summaries."""
        content = params.get('content', '')
        summary_type = params.get('summary_type', 'general')
        focus = params.get('focus', 'all')
        
        # Try real LLM first, fallback to simple LLM
        try:
            from ..llm.real_llm import real_llm
            result = real_llm.summarize(content, summary_type, focus)
            return result
        except Exception as e:
            self.logger.warning(f"Real LLM failed, using fallback: {e}")
            # Fallback to simple summarization
            from ..llm.simple_llm import llm
            try:
                result = llm.summarize(content, summary_type, focus)
                result['fallback'] = True
                return result
            except Exception as e2:
                return {
                    'summary': f"Summary of {summary_type}: Key findings from the analyzed content.",
                    'key_points': ['Analysis completed', 'Patterns identified', 'Insights extracted'],
                    'confidence': 0.5,
                    'error': str(e2),
                    'fallback': True
                }
    
    def _tool_cache_lookup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Look up value in cache."""
        key = params.get('key', '')
        value = self.cache.get(key)
        
        return {
            'key': key,
            'found': value is not None,
            'value': value
        }
    
    def _tool_cache_store(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Store value in cache."""
        key = params.get('key', '')
        value = params.get('value', None)
        
        self.cache.set(key, value)
        
        return {
            'key': key,
            'stored': True
        }
    
    # Helper methods
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.md': 'markdown',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json'
        }
        return language_map.get(ext, 'unknown')
    
    def _extract_key_patterns(self, content: str) -> List[str]:
        """Extract key patterns from code content."""
        patterns = []
        
        # Look for common patterns
        if 'class ' in content:
            patterns.append('contains_classes')
        if 'def ' in content or 'function ' in content:
            patterns.append('contains_functions')
        if 'import ' in content or 'from ' in content:
            patterns.append('has_imports')
        if 'TODO' in content or 'FIXME' in content:
            patterns.append('has_todos')
        
        return patterns
    
    def _generate_insight(self, action: ReActAction, result: Any) -> str:
        """Generate insight from action result."""
        if isinstance(result, dict) and 'error' in result:
            return f"Action failed: {result['error']}"
        
        if action.action_type == ActionType.SCAN_DIRECTORY:
            return f"Scanned directory with {result.get('total_files', 0)} files"
        elif action.action_type == ActionType.READ_FILE:
            return f"Read file with {result.get('line_count', 0)} lines"
        elif action.action_type == ActionType.SEARCH_FILES:
            return f"Found {len(result.get('results', []))} files matching pattern"
        else:
            return f"Completed {action.action_type.value}"
    
    def _calculate_confidence(self, action: ReActAction, result: Any) -> float:
        """Calculate confidence in the action result."""
        if isinstance(result, dict) and 'error' in result:
            return 0.0
        
        # Simple confidence calculation
        if action.action_type in [ActionType.READ_FILE, ActionType.SCAN_DIRECTORY]:
            return 0.9
        elif action.action_type == ActionType.SEARCH_FILES:
            return 0.8 if len(result.get('results', [])) > 0 else 0.3
        else:
            return 0.7
    
    def _update_context(self, observation: ReActObservation):
        """Update context based on observation."""
        if observation.success:
            self.state.current_context['last_successful_action'] = observation.action_taken
            self.state.current_context['last_result'] = observation.result
        else:
            self.state.current_context['last_error'] = observation.insight
    
    def _setup_recovery_strategies(self):
        """Set up recovery strategies for different error conditions."""
        self.recovery_strategies = {
            'file_not_found': self._recover_file_not_found,
            'permission_denied': self._recover_permission_denied,
            'timeout': self._recover_timeout,
            'infinite_loop': self._recover_infinite_loop
        }
    
    def _recover_file_not_found(self):
        """Recover from file not found error."""
        self.logger.info("🔧 Recovering from file not found - switching to directory scan")
        return ReActAction(
            action_type=ActionType.SCAN_DIRECTORY,
            description="Scan directory to find available files",
            parameters={'directory': '.', 'max_depth': 1}
        )
    
    def _recover_permission_denied(self):
        """Recover from permission denied error."""
        self.logger.info("🔧 Recovering from permission denied - trying different approach")
        return ReActAction(
            action_type=ActionType.LIST_FILES,
            description="List files to find accessible ones",
            parameters={'directory': '.', 'pattern': '*'}
        )
    
    def _recover_timeout(self):
        """Recover from timeout error."""
        self.logger.info("🔧 Recovering from timeout - using cached results")
        return ReActAction(
            action_type=ActionType.CACHE_LOOKUP,
            description="Look up cached results",
            parameters={'key': 'last_successful_scan'}
        )
    
    def _recover_infinite_loop(self):
        """Recover from infinite loop."""
        self.logger.info("🔧 Recovering from infinite loop - using LLM reasoning")
        return ReActAction(
            action_type=ActionType.LLM_REASONING,
            description="Use LLM to break out of loop",
            parameters={'context': str(self.state.current_context), 'question': 'How to proceed?'}
        )
    
    def _generate_final_results(self, execution_time: float) -> Dict[str, Any]:
        """Generate final results from the ReAct loop."""
        return {
            'goal': self.state.goal,
            'iterations': self.state.iteration,
            'execution_time': execution_time,
            'observations': self.state.observations,
            'actions_taken': self.state.actions_taken,
            'reasoning_history': self.state.reasoning_history,
            'cache_hits': self.state.cache_hits,
            'error_count': self.state.error_count,
            'final_context': self.state.current_context,
            'goal_achieved': self._is_goal_achieved(),
            'summary': self._generate_summary()
        }
    
    def _generate_error_results(self, error: str, execution_time: float) -> Dict[str, Any]:
        """Generate error results."""
        return {
            'goal': self.state.goal,
            'error': error,
            'execution_time': execution_time,
            'iterations': self.state.iteration,
            'observations': self.state.observations,
            'actions_taken': self.state.actions_taken,
            'goal_achieved': False,
            'summary': f"Failed to achieve goal: {error}"
        }
    
    def _validate_action_parameters(self, action: ReActAction) -> Optional[str]:
        """Validate action parameters."""
        try:
            # Basic parameter validation
            if not action.parameters:
                return None
            
            # Check required parameters for each action type
            if action.action_type == ActionType.READ_FILE:
                if 'file_path' not in action.parameters:
                    return "file_path parameter required for READ_FILE"
                file_path = action.parameters['file_path']
                if not file_path or not isinstance(file_path, str):
                    return "file_path must be a non-empty string"
            
            elif action.action_type == ActionType.SCAN_DIRECTORY:
                if 'directory' in action.parameters:
                    directory = action.parameters['directory']
                    if not isinstance(directory, str):
                        return "directory must be a string"
            
            elif action.action_type == ActionType.SEARCH_FILES:
                if 'pattern' not in action.parameters:
                    return "pattern parameter required for SEARCH_FILES"
                pattern = action.parameters['pattern']
                if not pattern or not isinstance(pattern, str):
                    return "pattern must be a non-empty string"
            
            elif action.action_type == ActionType.LLM_REASONING:
                if 'question' not in action.parameters:
                    return "question parameter required for LLM_REASONING"
            
            return None  # Valid parameters
            
        except Exception as e:
            return f"Parameter validation error: {e}"
    
    def _validate_tool_result(self, action: ReActAction, result: Any) -> Dict[str, Any]:
        """Validate tool execution result."""
        try:
            # Check for error in result
            if isinstance(result, dict) and 'error' in result:
                return {'valid': False, 'error': f"Tool returned error: {result['error']}"}
            
            # Check for None result
            if result is None:
                return {'valid': False, 'error': "Tool returned None result"}
            
            # Action-specific validation
            if action.action_type == ActionType.READ_FILE:
                if isinstance(result, dict):
                    if 'content' not in result:
                        return {'valid': False, 'error': "READ_FILE result missing content"}
                    if not result.get('content'):
                        return {'valid': False, 'error': "READ_FILE returned empty content"}
            
            elif action.action_type == ActionType.SCAN_DIRECTORY:
                if isinstance(result, dict):
                    if 'contents' not in result:
                        return {'valid': False, 'error': "SCAN_DIRECTORY result missing contents"}
            
            elif action.action_type == ActionType.SEARCH_FILES:
                if isinstance(result, dict):
                    if 'results' not in result:
                        return {'valid': False, 'error': "SEARCH_FILES result missing results"}
            
            return {'valid': True, 'error': None}
            
        except Exception as e:
            return {'valid': False, 'error': f"Result validation error: {e}"}
    
    def _execute_tool_with_timeout(self, tool_func: Callable, parameters: Dict[str, Any]) -> Any:
        """Execute tool function with timeout."""
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Tool execution timed out after {self.react_config.tool_timeout}s")
        
        # Set up timeout only on Unix systems
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(self.react_config.tool_timeout))
        
        try:
            result = tool_func(parameters)
            return result
        finally:
            # Clean up timeout
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
    
    def _attempt_tool_recovery(self, action: ReActAction, error: str) -> Optional[str]:
        """Attempt to recover from tool execution error."""
        error_lower = error.lower()
        
        if 'file not found' in error_lower or 'no such file' in error_lower:
            return 'file_not_found'
        elif 'permission denied' in error_lower:
            return 'permission_denied'
        elif 'timeout' in error_lower:
            return 'timeout'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'network_error'
        else:
            return 'generic_error'

    @abstractmethod
    def _generate_summary(self) -> str:
        """Generate a summary of the agent's work."""
        pass