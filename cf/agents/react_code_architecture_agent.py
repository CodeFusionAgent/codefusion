"""
ReAct Code Architecture Agent for comprehensive code and architectural analysis.

This agent uses the ReAct pattern to systematically explore and analyze both 
code-level details and architectural patterns through reasoning, acting with tools, 
and observing results.
"""

import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from cf.aci.repo import CodeRepo
from cf.config import CfConfig
from cf.core.react_agent import ReActAgent, ReActAction, ActionType
from cf.core.exploration_memory import init_exploration_memory, get_exploration_memory
from cf.utils.logging_utils import agent_log
from cf.llm.real_llm import get_real_llm
from cf.llm.tool_registry import tool_registry


@dataclass
class CodeEntity:
    """Represents a code entity (class, function, variable, etc.)."""
    name: str
    type: str  # 'class', 'function', 'variable', 'import', 'decorator'
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    complexity: int = 0
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemComponent:
    """Represents a system component."""
    name: str
    type: str  # 'service', 'module', 'layer', 'database', 'api', 'ui'
    description: str
    responsibilities: List[str]
    dependencies: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    entities: List[CodeEntity] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitecturalPattern:
    """Represents an architectural or design pattern."""
    pattern_name: str
    pattern_type: str  # 'design', 'architectural', 'code_style'
    description: str
    components: List[str]
    evidence: List[str]
    confidence: float
    occurrences: int = 1
    benefits: List[str] = field(default_factory=list)
    trade_offs: List[str] = field(default_factory=list)


@dataclass
class DataFlow:
    """Represents data flow between components."""
    source: str
    target: str
    flow_type: str  # 'request', 'response', 'event', 'data'
    description: str
    protocols: List[str] = field(default_factory=list)
    data_types: List[str] = field(default_factory=list)


class ReActCodeArchitectureAgent(ReActAgent):
    """
    Combined code and architecture agent that uses ReAct pattern for comprehensive analysis.
    
    This agent analyzes both:
    - Code-level details: functions, classes, patterns, complexity
    - Architectural patterns: system design, components, data flows
    
    ReAct Loop:
    1. Reason: Analyze what code/architecture aspect to explore next
    2. Act: Use tools to scan, read, search, analyze code and architecture
    3. Observe: Reflect on findings and build comprehensive understanding
    """
    
    def __init__(self, repo: CodeRepo, config: CfConfig):
        super().__init__(repo, config, "CodeArchitectureAgent")
        
        # Initialize exploration memory system
        self.exploration_memory = get_exploration_memory()
        if not self.exploration_memory:
            repo_path = getattr(repo, 'root_path', getattr(repo, 'repo_path', '.'))
            self.exploration_memory = init_exploration_memory(repo_path, config)
        
        # Language-specific analyzers
        self.language_analyzers = {
            'python': self._analyze_python_code,
            'javascript': self._analyze_javascript_code,
            'typescript': self._analyze_javascript_code,  # Use JS analyzer for TS
        }
        
        # Code analysis state
        self.code_files = []
        self.analyzed_files = {}
        self.code_entities = {}
        self.language_stats = defaultdict(int)
        
        # Architecture analysis state
        self.components = []
        self.patterns = []
        self.data_flows = []
        self.architectural_layers = {}
        self.system_boundaries = {}
        
        # Component identification patterns
        self.component_patterns = {
            'api': ['api', 'rest', 'graphql', 'endpoint', 'route', 'controller'],
            'service': ['service', 'manager', 'handler', 'processor', 'worker'],
            'model': ['model', 'entity', 'dto', 'schema', 'data'],
            'database': ['db', 'database', 'repository', 'dao', 'orm', 'storage'],
            'ui': ['ui', 'view', 'component', 'page', 'template', 'frontend'],
            'middleware': ['middleware', 'filter', 'interceptor', 'guard'],
            'config': ['config', 'settings', 'environment', 'constants'],
            'util': ['util', 'helper', 'common', 'shared', 'lib', 'utils'],
            'test': ['test', 'spec', 'tests', 'testing']
        }
        
        # Pattern detectors (both design and architectural)
        self.pattern_detectors = {
            # Design patterns
            'singleton': self._detect_singleton_pattern,
            'factory': self._detect_factory_pattern,
            'observer': self._detect_observer_pattern,
            'decorator': self._detect_decorator_pattern,
            'strategy': self._detect_strategy_pattern,
            'adapter': self._detect_adapter_pattern,
            'repository': self._detect_repository_pattern,
            
            # Architectural patterns
            'mvc': self._detect_mvc_pattern,
            'microservices': self._detect_microservices_pattern,
            'layered': self._detect_layered_pattern,
            'clean_architecture': self._detect_clean_architecture_pattern,
            'event_driven': self._detect_event_driven_pattern,
            
            # Code style patterns
            'naming_conventions': self._detect_naming_conventions,
            'code_organization': self._detect_code_organization,
            'dependency_injection': self._detect_dependency_injection
        }
        
        # Quality attributes to assess
        self.quality_attributes = [
            'maintainability', 'scalability', 'performance', 
            'security', 'reliability', 'testability'
        ]
    
    def _prioritize_files_by_question(self, files: List[str], question: str) -> List[str]:
        """
        Use LLM to intelligently prioritize files based on question context.
        
        Args:
            files: List of file paths to prioritize
            question: The user's question
            
        Returns:
            Files sorted by relevance to the question
        """
        if not files:
            return files
        
        try:
            real_llm = get_real_llm()
            if not real_llm or not real_llm.client:
                return self._basic_file_prioritization(files, question)
            
            # Create a concise file list for LLM analysis
            file_summary = []
            for file_path in files[:20]:  # Limit to top 20 files to avoid token limits
                filename = Path(file_path).name
                directory = str(Path(file_path).parent)
                file_summary.append(f"{file_path} (in {directory})")
            
            prompt = f"""Question: "{question}"

Available files:
{chr(10).join(file_summary)}

Based on the question, identify which files are most likely to contain relevant code. Consider:
- File names that match question keywords
- Common patterns (e.g., routing.py for routing questions, auth.py for authentication)
- Package structure and file organization
- Entry points and main application files

Return a JSON list of the TOP 5 most relevant file paths in priority order:
["most_relevant_file.py", "second_most_relevant.py", ...]

Focus on actual implementation files over tests, docs, or examples."""

            response = real_llm._call_llm(prompt)
            
            # Parse LLM response
            if isinstance(response, dict):
                content = response.get('content', '')
            else:
                content = str(response)
            
            # Try to extract JSON list from response
            json_match = re.search(r'\[(.*?)\]', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    prioritized_files = json.loads(json_str)
                    
                    # Validate that files exist in our list
                    valid_prioritized = [f for f in prioritized_files if f in files]
                    
                    # Add remaining files at the end
                    remaining_files = [f for f in files if f not in valid_prioritized]
                    
                    result = valid_prioritized + remaining_files
                    
                    agent_log(f"🎯 [CodeArchAgent] LLM prioritized files for '{question[:30]}...': {valid_prioritized[:3]}")
                    return result
                    
                except (json.JSONDecodeError, TypeError):
                    agent_log(f"⚠️  [CodeArchAgent] Failed to parse LLM file prioritization")
            
        except Exception as e:
            agent_log(f"❌ [CodeArchAgent] File prioritization failed: {e}")
        
        # Fallback: Basic heuristic prioritization
        return self._basic_file_prioritization(files, question)
    
    def _basic_file_prioritization(self, files: List[str], question: str) -> List[str]:
        """
        Generic file prioritization using basic heuristics.
        """
        question_lower = question.lower()
        
        def get_file_score(file_path: str) -> int:
            score = 0
            filename = Path(file_path).name.lower()
            file_path_lower = file_path.lower()
            
            # Boost source code files
            if file_path.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs')):
                score += 10
            
            # Check for question keywords in filename (generic matching)
            question_words = [word for word in question_lower.split() if len(word) > 2]  # Skip short words
            for word in question_words:
                if word in filename or word in file_path_lower:
                    score += 20
            
            # Prioritize main application entry points
            if filename in ['__init__.py', 'main.py', 'app.py', 'server.py', 'index.js', 'index.ts']:
                score += 15
            
            # Boost files in common important directories
            important_dirs = ['src', 'lib', 'core', 'api', 'server', 'client', 'app', 'main']
            for dir_name in important_dirs:
                if f'/{dir_name}/' in file_path_lower or file_path_lower.startswith(f'{dir_name}/'):
                    score += 10
            
            # Deprioritize test, documentation, and build files
            exclude_patterns = ['test', 'tests', 'docs', 'documentation', 'example', 'samples', 
                              '__pycache__', 'node_modules', '.git', 'build', 'dist']
            if any(exclude in file_path_lower for exclude in exclude_patterns):
                score -= 15
            
            # Deprioritize hidden files and config files unless they're source code
            if filename.startswith('.') and not filename.endswith(('.py', '.js', '.ts')):
                score -= 10
            
            return score
        
        return sorted(files, key=get_file_score, reverse=True)
    
    def _find_source_code_directories(self, scan_result: Dict[str, Any]) -> List[str]:
        """
        Identify directories that likely contain source code based on presence of __init__.py.
        
        Args:
            scan_result: Result from directory scanning
            
        Returns:
            List of directory paths that are likely Python packages
        """
        source_dirs = []
        contents = scan_result.get('contents', [])
        
        # Group contents by directory
        directories = defaultdict(list)
        for item in contents:
            if item['is_directory']:
                directories[item['path']] = []
            else:
                dir_path = str(Path(item['path']).parent)
                directories[dir_path].append(item['path'])
        
        # Find directories with __init__.py (Python packages)
        for dir_path, files in directories.items():
            if any('__init__.py' in file_path for file_path in files):
                source_dirs.append(dir_path)
                agent_log(f"📦 [CodeArchAgent] Found Python package: {dir_path}")
        
        return source_dirs
    
    def analyze_code_architecture(self, description: str) -> Dict[str, Any]:
        """
        Main entry point for comprehensive code and architecture analysis.
        
        Args:
            description: Description of what to focus on during analysis
            
        Returns:
            Comprehensive analysis results including code entities, 
            architectural patterns, and system components
        """
        # Record question in exploration memory for progressive context building
        if self.exploration_memory:
            question_record = self.exploration_memory.record_question(description)
            print(f"🧠 [ExplorationMemory] Recorded question: {question_record.question_type} (depth: {question_record.exploration_depth})")
            print(f"🎯 [ExplorationMemory] Focus areas: {', '.join(question_record.focus_areas)}")
        
        goal = f"Analyze code and architecture for: {description}"
        result = self.execute_react_loop(goal, max_iterations=25)
        
        # Cache the analysis results in exploration memory
        if self.exploration_memory and result:
            self.exploration_memory.exploration_path.discoveries.append(f"Completed analysis: {description}")
        
        return result
    
    def reason(self) -> str:
        """
        Reasoning phase: Use LLM to determine what code/architecture analysis action to take next.
        
        Returns:
            Reasoning about next action to take
        """
        
        agent_log(f"\n🧠 [CodeArchAgent] REASONING PHASE - Iteration {self.state.iteration}")
        agent_log(f"🎯 [CodeArchAgent] Goal: {self.state.goal}")
        agent_log(f"📊 [CodeArchAgent] Current state: {len(self.code_files)} files, {len(self.analyzed_files)} analyzed, {len(self.components)} components")
        
        
        # If LLM is not available, fall back to original reasoning
        real_llm = get_real_llm()
        if not real_llm or not real_llm.client:
            agent_log(f"⚠️  [CodeArchAgent] LLM not available, using fallback reasoning")
            return self._fallback_reason()
        
        agent_log(f"🤖 [CodeArchAgent] Using LLM-powered reasoning")
        
        # Build context for LLM reasoning
        context = self._build_reasoning_context()
        agent_log(f"📝 [CodeArchAgent] Built reasoning context ({len(context)} chars)")
        
        # Use LLM for reasoning
        try:
            agent_log(f"📡 [CodeArchAgent] Calling LLM for reasoning...")
            real_llm = get_real_llm()
            if real_llm and real_llm.client:
                reasoning_result = real_llm.reasoning(
                    context=context,
                    question=self.state.goal,
                    agent_type="code_architecture"
                )
            else:
                raise Exception("Real LLM not available")
            
            reasoning = reasoning_result.get('reasoning', self._fallback_reason())
            agent_log(f"✅ [CodeArchAgent] LLM reasoning completed")
            agent_log(f"💭 [CodeArchAgent] Reasoning: {reasoning[:150]}...")
            return reasoning
            
        except Exception as e:
            error_log(f"❌ [CodeArchAgent] LLM reasoning failed: {e}")
            self.logger.warning(f"LLM reasoning failed: {e}, falling back to hardcoded reasoning")
            agent_log(f"🔄 [CodeArchAgent] Falling back to hardcoded reasoning")
            return self._fallback_reason()
    
    def _build_reasoning_context(self) -> str:
        """Build context string for LLM reasoning."""
        context_parts = [
            f"Goal: {self.state.goal}",
            f"Iteration: {self.state.iteration}/{self.state.max_iterations}",
            f"Code files found: {len(self.code_files)}",
            f"Files analyzed: {len(self.analyzed_files)}",
            f"Components identified: {len(self.components)}",
            f"Patterns detected: {len(self.patterns)}",
            f"Data flows mapped: {len(self.data_flows)}"
        ]
        
        # Add recent observations
        if self.state.observations:
            context_parts.append("Recent observations:")
            for obs in self.state.observations[-3:]:
                context_parts.append(f"- {obs}")
        
        # Add current findings summary
        if self.components:
            context_parts.append("Components found:")
            for comp in self.components[:5]:
                context_parts.append(f"- {comp.name} ({comp.type})")
        
        if self.patterns:
            context_parts.append("Patterns detected:")
            for pattern in self.patterns[:5]:
                context_parts.append(f"- {pattern.pattern_name} ({pattern.pattern_type})")
        
        return "\n".join(context_parts)
    
    def _fallback_reason(self) -> str:
        """Fallback reasoning when LLM is unavailable."""
        current_context = self.state.current_context
        iteration = self.state.iteration
        
        # First iteration: Start with repository structure
        if iteration == 1:
            return "I should start by scanning the repository structure to understand both the codebase layout and architectural organization."
        
        # Early iterations: Discovery phase
        if iteration <= 3 and not self.code_files:
            return "I need to discover source code files and understand the overall project structure. I should aggressively search for Python, JavaScript, and other source files."
        
        # Force file discovery if we haven't found any yet
        if iteration <= 5 and not self.code_files:
            return "I still haven't found source code files. I need to search more aggressively using different patterns and approaches to find .py, .js, .ts files."
        
        # Code analysis phase - be more aggressive about reading files
        if self.code_files and len(self.analyzed_files) < min(10, len(self.code_files)):
            return f"I found {len(self.code_files)} code files. I should analyze multiple key files to understand both code structure and architectural patterns. Focus on core framework files."
        
        # Component identification phase
        if self.analyzed_files and len(self.components) < 3:
            return "I've analyzed some code files. Now I should identify system components and their relationships to understand the architecture."
        
        # Pattern detection phase
        if len(self.analyzed_files) >= 3 and len(self.patterns) < 5:
            return "I have good code coverage. I should now focus on detecting both design patterns and architectural patterns."
        
        # Goal-specific analysis
        if "api" in self.state.goal.lower():
            return "The goal mentions API. I should analyze API design patterns, endpoints, and how the API layer is structured both in code and architecture."
        elif "microservice" in self.state.goal.lower():
            return "The goal mentions microservices. I should look for service boundaries, communication patterns, and microservice implementation details."
        elif "database" in self.state.goal.lower():
            return "The goal mentions database. I should analyze data models, database access patterns, and data architecture both in code and design."
        elif "security" in self.state.goal.lower():
            return "The goal mentions security. I should analyze authentication patterns, authorization code, and security architectural decisions."
        elif "test" in self.state.goal.lower():
            return "The goal mentions testing. I should analyze test patterns, testing architecture, and code testability."
        
        # Deep analysis phase
        if len(self.components) >= 3 and len(self.patterns) >= 3:
            return "I have good understanding of both code and architecture. Now I should analyze quality attributes, relationships, and generate comprehensive insights."
        
        # Relationship analysis
        if self.components and not self.data_flows:
            return "I should analyze how components interact and what data flows between them to understand the system's runtime behavior."
        
        # Default reasoning
        return "I should continue analyzing the codebase systematically, focusing on both code-level details and architectural patterns."
    
    def plan_action(self, reasoning: str) -> ReActAction:
        """
        Plan the next action based on reasoning using LLM function calling.
        
        Args:
            reasoning: The reasoning output
            
        Returns:
            Action to take
        """
        print(f"\n🎯 [CodeArchAgent] ACTION PLANNING PHASE")
        print(f"💭 [CodeArchAgent] Based on reasoning: {reasoning[:100]}...")
        
        
        # If LLM is not available, fall back to original action planning
        real_llm = get_real_llm()
        if not real_llm or not real_llm.client:
            print(f"⚠️  [CodeArchAgent] LLM not available, using fallback action planning")
            return self._fallback_plan_action(reasoning)
        
        print(f"🔧 [CodeArchAgent] Using LLM function calling for intelligent tool selection")
        
        # Use LLM function calling to select tools
        try:
            # Build intelligent context using exploration memory system
            
            exploration_memory = get_exploration_memory()
            if exploration_memory:
                exploration_context = exploration_memory.get_exploration_context_for_agent()
                suggested_actions = exploration_memory.suggest_next_actions()
            else:
                exploration_context = "No exploration memory available - starting fresh exploration"
                suggested_actions = ["scan_directory", "list_files", "read_file"]
            
            # Build smart action selection logic
            files_found = len(self.code_files)
            files_analyzed = len(self.analyzed_files)
            iteration = self.state.iteration
            
            # Determine optimal next action based on progress
            if files_found == 0 and iteration <= 2:
                action_guidance = "SCAN FIRST: Use scan_directory or list_files to discover source code files (exclude .git, .github, node_modules)"
            elif files_found > 0 and files_analyzed == 0:
                action_guidance = "READ CODE: Use read_file to analyze the most relevant source files you've discovered"
            elif files_analyzed > 0 and files_analyzed < 3:
                action_guidance = "ANALYZE MORE: Continue reading key source files or use search_files to find specific patterns"
            else:
                action_guidance = "SYNTHESIZE: Use generate_summary or analyze_code for deeper pattern analysis"

            context = f"""
You are exploring a codebase to understand: {self.state.goal}

Current Reasoning: {reasoning}

Exploration Progress:
- Iteration: {self.state.iteration}/{self.state.max_iterations}  
- Code files discovered: {files_found}
- Files analyzed in depth: {files_analyzed}
- System components identified: {len(self.components)}

{exploration_context}

**SMART ACTION GUIDANCE: {action_guidance}**

**CRITICAL RULES - FOLLOW THESE EXACTLY:**
1. If iteration 1-2 AND no files found: Use scan_directory with max_depth=6 to find ALL source files
2. If iteration 3+ AND files found: STOP scanning, START reading! Use read_file on most relevant files
3. If you've scanned 3+ times: NEVER scan again, use list_files or read_file instead
4. PRIORITIZE: Source code files in main packages over test/docs/example files
5. Match question keywords to file names intelligently (e.g., "routing" → files with "route/router/routing", "auth" → files with "auth/login/security", "database" → files with "db/model/schema")

**Question Context:** {self.state.goal}
**Current Status:** Iteration {self.state.iteration}, Files found: {files_found}, Files analyzed: {files_analyzed}
**REQUIRED NEXT ACTION:** {action_guidance}

Available tools: scan_directory, list_files, read_file, search_files, analyze_code, generate_summary
"""
            
            print(f"📝 [CodeArchAgent] Built function calling context")
            
            # Get tool schemas from registry
            tool_schemas = tool_registry.get_tool_schemas()
            print(f"🔧 [CodeArchAgent] Retrieved {len(tool_schemas)} tool schemas from registry")
            
            # Call LLM with function calling
            print(f"📡 [CodeArchAgent] Calling LLM with function calling enabled...")
            response = real_llm._call_llm(context, tools=tool_schemas, tool_choice="auto")
            
            # Parse tool calling response - handle multiple formats
            import json
            tool_calls = []
            
            try:
                if isinstance(response, dict):
                    # Direct dict response
                    tool_calls = response.get('tool_calls', [])
                    print(f"✅ [CodeArchAgent] Received direct dict response from LLM")
                elif isinstance(response, str):
                    if response.startswith('{"type": "tool_calls"'):
                        # Legacy format
                        tool_response = json.loads(response)
                        tool_calls = tool_response.get('tool_calls', [])
                        print(f"✅ [CodeArchAgent] Received legacy format response from LLM")
                    elif response.startswith('{'):
                        # Try parsing as JSON
                        tool_response = json.loads(response)
                        tool_calls = tool_response.get('tool_calls', [])
                        print(f"✅ [CodeArchAgent] Received JSON response from LLM")
                    else:
                        print(f"⚠️  [CodeArchAgent] Unexpected response format: {response[:100]}")
                        raise ValueError("Unexpected response format")
                else:
                    print(f"⚠️  [CodeArchAgent] Unknown response type: {type(response)}")
                    raise ValueError("Unknown response type")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"❌ [CodeArchAgent] Failed to parse LLM response: {e}")
                print(f"🔍 [CodeArchAgent] Raw response: {response}")
                tool_calls = []
            
            if tool_calls:
                # Use the first tool call
                tool_call = tool_calls[0]
                function_name = tool_call['function_name']
                arguments = tool_call['arguments']
                
                print(f"🎯 [CodeArchAgent] LLM selected tool: {function_name}")
                print(f"📋 [CodeArchAgent] Tool arguments: {arguments}")
                
                # Map function names to ActionTypes
                action_mapping = {
                    'scan_directory': ActionType.SCAN_DIRECTORY,
                    'list_files': ActionType.LIST_FILES,
                    'read_file': ActionType.READ_FILE,
                    'search_files': ActionType.SEARCH_FILES,
                    'analyze_code': ActionType.ANALYZE_CODE,
                    'generate_summary': ActionType.LLM_SUMMARY
                }
                
                if function_name in action_mapping:
                    # ENFORCE PROGRESSION RULES: Override LLM if it's stuck in scanning loops
                    if (self.state.iteration >= 3 and 
                        function_name == 'scan_directory' and 
                        len(self.state.actions_taken) >= 2 and
                        all('scan_directory' in action for action in self.state.actions_taken[-2:])):
                        
                        print(f"🚫 [CodeArchAgent] OVERRIDING LLM: Too many scans, forcing progression to file operations")
                        # Force list_files to find actual Python files
                        action = ReActAction(
                            action_type=ActionType.LIST_FILES,
                            description="Override: List Python files to find source code after repeated scans",
                            parameters={'pattern': '*.py', 'directory': '.'},
                            expected_outcome="Find actual Python source files in repository"
                        )
                        print(f"✅ [CodeArchAgent] Created override action: list_files")
                        return action
                    
                    action = ReActAction(
                        action_type=action_mapping[function_name],
                        description=f"LLM-selected action: {function_name}",
                        parameters=arguments,
                        expected_outcome=f"Execute {function_name} with LLM-selected parameters",
                        tool_name=function_name
                    )
                    print(f"✅ [CodeArchAgent] Created LLM-driven action")
                    return action
                else:
                    print(f"❌ [CodeArchAgent] Unknown function name: {function_name}")
            else:
                print(f"❌ [CodeArchAgent] No tool calls in LLM response")
            
            # Fall back if tool calling didn't work
            print(f"🔄 [CodeArchAgent] Falling back to hardcoded action planning")
            return self._fallback_plan_action(reasoning)
            
        except Exception as e:
            print(f"❌ [CodeArchAgent] LLM function calling failed: {e}")
            self.logger.warning(f"LLM function calling failed: {e}, falling back to hardcoded action planning")
            print(f"🔄 [CodeArchAgent] Using fallback action planning")
            return self._fallback_plan_action(reasoning)
    
    def _fallback_plan_action(self, reasoning: str) -> ReActAction:
        """Fallback action planning when LLM function calling is unavailable."""
        iteration = self.state.iteration
        
        # Early iterations: Structure discovery - scan deeper and prioritize source directories
        if iteration <= 2:
            if iteration == 1:
                return ReActAction(
                    action_type=ActionType.SCAN_DIRECTORY,
                    description="Initial repository scan to identify structure and source directories",
                    parameters={'directory': '.', 'max_depth': 3},
                    expected_outcome="Understand repository structure and identify Python packages with __init__.py"
                )
            else:
                # Second iteration: scan deeper into likely source directories
                return ReActAction(
                    action_type=ActionType.SCAN_DIRECTORY,
                    description="Deep scan of repository focusing on source code directories",
                    parameters={'directory': '.', 'max_depth': 6},
                    expected_outcome="Find all source code files in nested directories and packages"
                )
        
        # Source code discovery - be more aggressive (but transition to reading once files found)
        if len(self.code_files) < 5 and iteration <= 4:
            if iteration <= 2:
                return ReActAction(
                    action_type=ActionType.LIST_FILES,
                    description="List all files to find source code",
                    parameters={'pattern': '*', 'directory': '.'},
                    expected_outcome="Identify all files including source code files"
                )
            else:
                # Try different search approaches
                return ReActAction(
                    action_type=ActionType.SEARCH_FILES,
                    description="Search for Python and source code files",
                    parameters={'pattern': '*.py', 'file_types': ['.py', '.js', '.ts'], 'max_results': 100},
                    expected_outcome="Find Python and source code files for analysis"
                )
        
        # Force transition to file reading when enough files are discovered (lowered threshold)
        if len(self.code_files) >= 5 and len(self.analyzed_files) == 0:
            agent_log(f"🎯 [CodeArchAgent] Found {len(self.code_files)} files, transitioning to file reading phase")
            unanalyzed_files = [f for f in self.code_files if f not in self.analyzed_files]
            prioritized_files = self._prioritize_files_by_question(unanalyzed_files, self.state.goal)
            file_to_analyze = prioritized_files[0] if prioritized_files else unanalyzed_files[0]
            
            return ReActAction(
                action_type=ActionType.READ_FILE,
                description=f"Read and analyze priority source file based on question context",
                parameters={'file_path': file_to_analyze, 'max_lines': 200},
                expected_outcome="Extract key code insights and architectural patterns from the most relevant file"
            )
        
        # Aggressive file reading: read files once components are identified
        if len(self.components) > 0 and self.code_files and len(self.analyzed_files) < 3:
            agent_log(f"🚀 [CodeArchAgent] Components identified, prioritizing file reading for deeper analysis")
            unanalyzed_files = [f for f in self.code_files if f not in self.analyzed_files]
            prioritized_files = self._prioritize_files_by_question(unanalyzed_files, self.state.goal)
            file_to_analyze = prioritized_files[0] if prioritized_files else unanalyzed_files[0]
            
            return ReActAction(
                action_type=ActionType.READ_FILE,
                description=f"Read priority source file to understand component implementation",
                parameters={'file_path': file_to_analyze, 'max_lines': 150},
                expected_outcome="Extract implementation details and code patterns from relevant source file"
            )
        
        # Continue reading priority files after initial analysis
        if self.code_files and len(self.analyzed_files) < 3:  # Read top 3 most relevant files
            # Use LLM to intelligently prioritize files based on the question
            unanalyzed_files = [f for f in self.code_files if f not in self.analyzed_files]
            
            if unanalyzed_files:
                # Use LLM-based prioritization
                prioritized_files = self._prioritize_files_by_question(unanalyzed_files, self.state.goal)
                file_to_analyze = prioritized_files[0] if prioritized_files else unanalyzed_files[0]
            elif self.code_files:
                # Re-analyze existing files if needed
                prioritized_files = self._prioritize_files_by_question(self.code_files, self.state.goal)
                file_to_analyze = prioritized_files[0]
            else:
                # Force search for Python files
                return ReActAction(
                    action_type=ActionType.SEARCH_FILES,
                    description="Search for Python source files",
                    parameters={'pattern': '*.py', 'file_types': ['.py'], 'max_results': 50},
                    expected_outcome="Find Python source files for analysis"
                )
            
            return ReActAction(
                action_type=ActionType.READ_FILE,
                description=f"Analyze source file for code and architecture patterns: {file_to_analyze}",
                parameters={'file_path': file_to_analyze, 'max_lines': 1000},  # Increased max lines
                expected_outcome="Understand code structure, patterns, and architectural significance"
            )
        
        # Use LLM for synthesis and insights
        return ReActAction(
            action_type=ActionType.LLM_REASONING,
            description="Use LLM to generate code and architecture insights",
            parameters={
                'context': f"Files: {len(self.analyzed_files)}, Components: {len(self.components)}, Patterns: {len(self.patterns)}",
                'question': f"What code and architectural insights can be derived for: {self.state.goal}?"
            },
            expected_outcome="Generate comprehensive code and architectural insights"
        )
    
    def observe(self, observation):
        """
        Enhanced observation phase for code and architecture analysis.
        
        Args:
            observation: Observation from the action
        """
        super().observe(observation)
        
        # Process observations for both code and architecture
        if observation.success and observation.result:
            result = observation.result
            
            # Directory scan: analyze structure for both code and architecture
            if isinstance(result, dict) and 'contents' in result:
                self._analyze_directory_structure(result['contents'])
            
            # File listing: identify source files and component files
            elif isinstance(result, dict) and 'files' in result:
                self._process_file_list(result['files'])
            
            # File reading: analyze code content and architectural significance
            elif isinstance(result, dict) and 'content' in result:
                self._analyze_file_content(result['file_path'], result['content'])
            
            # Search results: process for patterns and components
            elif isinstance(result, dict) and 'results' in result:
                self._process_search_results(result['results'])
    
    def _analyze_directory_structure(self, contents: List[Dict[str, Any]]):
        """Analyze directory structure for code organization and architectural patterns."""
        directories = [item for item in contents if item['is_directory']]
        files = [item for item in contents if not item['is_directory']]
        
        # Identify architectural layers from directory structure
        for directory in directories:
            path = directory['path']
            layer_type = self._identify_layer_type(path)
            
            if layer_type:
                self.architectural_layers[path] = layer_type
                self.logger.info(f"🏗️ Identified architectural layer: {path} -> {layer_type}")
        
        # Identify components from directory structure
        for directory in directories:
            path = directory['path']
            component_type = self._identify_component_type(path)
            
            if component_type:
                component = SystemComponent(
                    name=Path(path).name,
                    type=component_type,
                    description=f"{component_type.title()} component",
                    responsibilities=[f"Handle {component_type} operations"],
                    files=[path]
                )
                self.components.append(component)
                self.logger.info(f"🏗️ Identified component: {path} -> {component_type}")
        
        # Identify source code files with enhanced tracking
        python_files_found = 0
        for file_item in files:
            if self._is_source_code_file(file_item['path']):
                if file_item['path'] not in self.code_files:
                    self.code_files.append(file_item['path'])
                    self.language_stats[self._detect_language(file_item['path'])] += 1
                    if file_item['path'].endswith('.py'):
                        python_files_found += 1
                    agent_log(f"💾 Found source file: {file_item['path']}")
        
        # Enhanced logging for debugging file discovery
        total_files = len(files)
        total_source_files = len([f for f in files if self._is_source_code_file(f['path'])])
        agent_log(f"📊 [CodeArchAgent] Directory analysis: {total_files} total files, {total_source_files} source files, {python_files_found} Python files")
        agent_log(f"📊 [CodeArchAgent] Total code_files tracked: {len(self.code_files)}")
        
        # Log first few source files for verification
        if self.code_files:
            sample_files = self.code_files[:3]
            agent_log(f"📂 [CodeArchAgent] Sample tracked files: {sample_files}")
    
    def _process_file_list(self, files: List[Dict[str, Any]]):
        """Process file list for both code files and component identification."""
        for file_info in files:
            file_path = file_info['path']
            
            # Identify source code files
            if self._is_source_code_file(file_path):
                if file_path not in self.code_files:
                    self.code_files.append(file_path)
                    self.language_stats[self._detect_language(file_path)] += 1
                    self.logger.info(f"💾 Found source file: {file_path}")
            
            # Identify component files
            component_type = self._identify_component_type(file_path)
            if component_type:
                self._add_file_to_component(file_path, component_type)
    
    def _analyze_file_content(self, file_path: str, content: str):
        """Analyze file content for both code details and architectural significance."""
        # Code analysis
        analysis = self._analyze_code_content(file_path, content)
        self.analyzed_files[file_path] = analysis
        
        # Cache analysis in exploration memory for progressive context building
        if self.exploration_memory:
            self.exploration_memory.cache_file_analysis(file_path, analysis)
        
        # Extract code entities
        entities = self._extract_code_entities(file_path, content)
        self.code_entities[file_path] = entities
        
        # Add entities to relevant components
        self._associate_entities_with_components(file_path, entities)
        
        # Detect patterns (both design and architectural)
        patterns = self._detect_patterns_in_content(file_path, content)
        self.patterns.extend(patterns)
        
        # Analyze dependencies and data flows
        self._analyze_dependencies(file_path, content)
        self._analyze_data_flows(file_path, content)
        
        self.logger.info(f"🔍 Analyzed file: {file_path} ({analysis['language']})")
        
        # Log exploration memory status
        if self.exploration_memory:
            cache_summary = self.exploration_memory.get_cache_summary()
            print(f"📊 [ExplorationMemory] Files cached: {cache_summary['files_analyzed']}, Components: {cache_summary['components_discovered']}")
    
    def _process_search_results(self, results: List[Dict[str, Any]]):
        """Process search results for code patterns and architectural insights."""
        for result in results:
            file_path = result['file_path']
            matches = result.get('matches', [])
            
            # Process matches for both code and architecture
            for match in matches:
                content = match.get('content', '')
                line_num = match.get('line_num', 0)
                
                # Update context with findings
                self._process_search_match(file_path, content, line_num)
                
                # Detect patterns in match content
                patterns = self._detect_patterns_in_content(file_path, content)
                self.patterns.extend(patterns)
    
    def _is_source_code_file(self, file_path: str) -> bool:
        """Check if a file is source code."""
        source_extensions = [
            '.py', '.js', '.ts', '.tsx', '.jsx',
            '.java', '.c', '.cpp', '.cc', '.cxx',
            '.h', '.hpp', '.go', '.rs', '.kt',
            '.swift', '.php', '.rb', '.scala',
            '.cs', '.vb', '.clj', '.hs', '.ml'
        ]
        return any(file_path.lower().endswith(ext) for ext in source_extensions)
    
    def _analyze_code_content(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze code content for metrics and patterns."""
        lines = content.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # Basic metrics
        line_count = len(lines)
        code_line_count = len(non_empty_lines)
        comment_lines = len([line for line in lines if line.strip().startswith('#')])
        
        # Language-specific analysis
        language = self._detect_language(file_path)
        language_analysis = {}
        
        if language == 'python':
            language_analysis = self._analyze_python_code(content)
        elif language == 'javascript':
            language_analysis = self._analyze_javascript_code(content)
        
        # Complexity estimation
        complexity = self._estimate_complexity(content, language)
        
        # Extract sample code snippet for narrative using intelligent LLM analysis
        sample_code = self._extract_sample_code(content, file_path)
        
        # Use LLM tools for intelligent function and class analysis
        function_details = self._llm_analyze_functions(content, file_path)
        class_details = self._llm_analyze_classes(content, file_path)
        pattern_analysis = self._llm_detect_patterns(content, file_path)
        
        return {
            'file_path': file_path,
            'language': language,
            'line_count': line_count,
            'code_line_count': code_line_count,
            'comment_lines': comment_lines,
            'complexity': complexity,
            'language_analysis': language_analysis,
            'has_classes': 'class ' in content,
            'has_functions': 'def ' in content or 'function ' in content,
            'has_imports': 'import ' in content or 'from ' in content,
            'has_tests': 'test' in file_path.lower() or 'assert' in content,
            'sample_code': sample_code,
            'function_details': function_details,
            'class_details': class_details,
            'pattern_analysis': pattern_analysis
        }
    
    def _extract_sample_code(self, content: str, file_path: str) -> str:
        """Extract a representative sample of code for narrative purposes with richer context."""
        lines = content.split('\n')
        
        # Enhanced patterns with categories for better narrative context
        pattern_categories = {
            'main_entry': ['def main', 'if __name__', 'app.run', 'uvicorn.run'],
            'class_definitions': ['class ', 'class('],
            'api_endpoints': ['app.route', 'router.', 'api.', 'endpoint', '@route', '@api'],
            'authentication': ['def authenticate', 'def login', 'def authorize', 'def logout', '@login_required', 'jwt', 'token'],
            'data_processing': ['def process_', 'def handle_', 'def transform', 'def filter', 'def map'],
            'crud_operations': ['def get_', 'def post_', 'def put_', 'def delete_', 'def create_', 'def update_'],
            'database': ['def query', 'def save', 'session.', 'db.', 'cursor.', 'SELECT', 'INSERT', 'UPDATE'],
            'error_handling': ['try:', 'except', 'raise', 'Error', 'Exception', 'catch'],
            'configuration': ['config', 'settings', 'env', 'os.environ', 'getenv'],
            'testing': ['def test_', 'assert', 'mock', 'pytest', 'unittest'],
            'async_operations': ['async def', 'await', 'asyncio'],
            'initialization': ['def __init__', 'def setup', 'def initialize', 'def bootstrap']
        }
        
        # Find the best matching patterns with context
        best_samples = []
        
        for category, patterns in pattern_categories.items():
            for i, line in enumerate(lines):
                line_stripped = line.strip().lower()
                if any(pattern.lower() in line_stripped for pattern in patterns):
                    # Include more context for better understanding
                    start_line = max(0, i - 2)
                    end_line = min(len(lines), i + 6)
                    context_lines = lines[start_line:end_line]
                    
                    # Add docstring/comments if available
                    docstring_lines = []
                    for j in range(i + 1, min(len(lines), i + 4)):
                        next_line = lines[j].strip()
                        if next_line.startswith('"""') or next_line.startswith("'''") or next_line.startswith('#'):
                            docstring_lines.append(lines[j])
                        elif next_line and not next_line.startswith(' ') and not next_line.startswith('\t'):
                            break
                    
                    sample = {
                        'category': category,
                        'lines': context_lines + docstring_lines,
                        'line_number': i + 1,
                        'relevance_score': self._calculate_relevance_score(line, category)
                    }
                    best_samples.append(sample)
                    break  # Only take first match per category
        
        # Sort by relevance and select the best sample
        if best_samples:
            best_samples.sort(key=lambda x: x['relevance_score'], reverse=True)
            selected_sample = best_samples[0]
            
            # Format with enhanced context
            sample_lines = selected_sample['lines']
            category = selected_sample['category']
            line_num = selected_sample['line_number']
            
            # Add category context header
            formatted_sample = f"# {category.replace('_', ' ').title()} (line {line_num}):\n"
            formatted_sample += '\n'.join(sample_lines[:10])  # Limit to 10 lines
            
        else:
            # Enhanced fallback: look for imports, class definitions, or function definitions
            interesting_lines = []
            for i, line in enumerate(lines[:15]):  # Look at first 15 lines
                line_stripped = line.strip()
                if (line_stripped.startswith('import ') or 
                    line_stripped.startswith('from ') or
                    line_stripped.startswith('class ') or
                    line_stripped.startswith('def ') or
                    line_stripped.startswith('async def')):
                    interesting_lines.append(line)
                elif line_stripped and not line_stripped.startswith('#'):
                    interesting_lines.append(line)
                    
                if len(interesting_lines) >= 8:
                    break
            
            formatted_sample = f"# Code Structure:\n" + '\n'.join(interesting_lines)
        
        # Limit length but preserve code structure
        if len(formatted_sample) > 600:
            lines_in_sample = formatted_sample.split('\n')
            truncated = []
            current_length = 0
            for line in lines_in_sample:
                if current_length + len(line) > 600:
                    truncated.append('# ... (truncated for brevity)')
                    break
                truncated.append(line)
                current_length += len(line) + 1
            formatted_sample = '\n'.join(truncated)
        
        return formatted_sample
    
    def _calculate_relevance_score(self, line: str, category: str) -> float:
        """Calculate relevance score for better sample selection."""
        score = 1.0
        line_lower = line.lower()
        
        # Boost scores for high-value patterns
        if category == 'main_entry':
            score += 3.0  # Entry points are very valuable
        elif category == 'api_endpoints':
            score += 2.5  # API endpoints show functionality
        elif category == 'class_definitions':
            score += 2.0  # Classes show structure
        elif category == 'authentication':
            score += 2.0  # Security patterns are important
        elif category == 'crud_operations':
            score += 1.5  # CRUD shows data operations
        
        # Boost for functions with good names
        if any(keyword in line_lower for keyword in ['process', 'handle', 'manage', 'execute', 'create', 'get']):
            score += 0.5
            
        # Boost for documented code
        if '"""' in line or "'''" in line or line.strip().startswith('#'):
            score += 0.3
            
        return score
    
    def _llm_analyze_functions(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Use LLM to intelligently analyze function signatures and purposes."""
        try:
            # Use the LLM function analysis tool through tool registry
                
            result = tool_registry.execute_tool(
                tool_name="analyze_function_signatures",
                arguments={
                    "content": content,
                    "file_path": file_path,
                    "focus": "all"
                },
                agent_context=self
            )
            
            if result['success']:
                analysis = result['result']
                return analysis.get('functions', [])
            else:
                print(f"⚠️ [CodeArchAgent] LLM function analysis failed: {result.get('error', 'Unknown error')}")
                return self._fallback_function_analysis(content, file_path)
                
        except Exception as e:
            print(f"❌ [CodeArchAgent] LLM function analysis error: {e}")
            return self._fallback_function_analysis(content, file_path)
    
    def _llm_analyze_classes(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Use LLM to intelligently analyze class structures and hierarchies."""
        try:
            # Use the LLM class analysis tool through tool registry
                
            result = tool_registry.execute_tool(
                tool_name="analyze_class_hierarchies",
                arguments={
                    "content": content,
                    "file_path": file_path,
                    "focus": "all"
                },
                agent_context=self
            )
            
            if result['success']:
                analysis = result['result']
                return analysis.get('classes', [])
            else:
                print(f"⚠️ [CodeArchAgent] LLM class analysis failed: {result.get('error', 'Unknown error')}")
                return self._fallback_class_analysis(content, file_path)
                
        except Exception as e:
            print(f"❌ [CodeArchAgent] LLM class analysis error: {e}")
            return self._fallback_class_analysis(content, file_path)
    
    def _llm_detect_patterns(self, content: str, file_path: str) -> Dict[str, Any]:
        """Use LLM to intelligently detect architectural and design patterns."""
        try:
            # Use the LLM pattern detection tool through tool registry
                
            result = tool_registry.execute_tool(
                tool_name="detect_code_patterns",
                arguments={
                    "content": content,
                    "file_path": file_path,
                    "pattern_types": ["design_patterns", "architectural_patterns", "api_patterns"]
                },
                agent_context=self
            )
            
            if result['success']:
                analysis = result['result']
                return {
                    'patterns': analysis.get('patterns', []),
                    'architectural_insights': analysis.get('architectural_insights', []),
                    'design_principles': analysis.get('design_principles', []),
                    'summary': analysis.get('summary', '')
                }
            else:
                print(f"⚠️ [CodeArchAgent] LLM pattern detection failed: {result.get('error', 'Unknown error')}")
                return self._fallback_pattern_detection(content, file_path)
                
        except Exception as e:
            print(f"❌ [CodeArchAgent] LLM pattern detection error: {e}")
            return self._fallback_pattern_detection(content, file_path)
    
    def _fallback_function_analysis(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback function analysis when LLM is not available."""
        # Simple pattern-based extraction as fallback
        functions = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('def ') or line_stripped.startswith('async def '):
                try:
                    func_name = line_stripped.split('(')[0].replace('def ', '').replace('async ', '').strip()
                    if func_name and not func_name.startswith('_'):
                        functions.append({
                            'name': func_name,
                            'signature': line_stripped,
                            'line_number': i + 1,
                            'purpose': 'Function detected by fallback analysis'
                        })
                        
                    if len(functions) >= 5:  # Limit fallback results
                        break
                except:
                    continue
        
        return functions
    
    def _fallback_class_analysis(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback class analysis when LLM is not available."""
        # Simple pattern-based extraction as fallback
        classes = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('class ') and ':' in line_stripped:
                try:
                    class_part = line_stripped.replace('class ', '').split(':')[0]
                    class_name = class_part.split('(')[0].strip()
                    inheritance = ''
                    if '(' in class_part:
                        inheritance = class_part[class_part.find('(')+1:class_part.rfind(')')]
                    
                    if class_name:
                        classes.append({
                            'name': class_name,
                            'signature': line_stripped,
                            'line_number': i + 1,
                            'inheritance': inheritance,
                            'purpose': 'Class detected by fallback analysis'
                        })
                        
                    if len(classes) >= 3:  # Limit fallback results
                        break
                except:
                    continue
        
        return classes
    
    def _fallback_pattern_detection(self, content: str, file_path: str) -> Dict[str, Any]:
        """Fallback pattern detection when LLM is not available."""
        patterns = []
        
        # Simple pattern detection
        if 'class ' in content and 'def __init__' in content:
            patterns.append({
                'name': 'Object-Oriented Design',
                'type': 'architectural_pattern',
                'confidence': 0.6,
                'evidence': 'Classes with constructors detected'
            })
        
        if 'def main' in content or 'if __name__' in content:
            patterns.append({
                'name': 'Entry Point Pattern',
                'type': 'code_pattern',
                'confidence': 0.8,
                'evidence': 'Main function or entry point detected'
            })
        
        return {
            'patterns': patterns,
            'architectural_insights': ['Basic pattern detection performed'],
            'design_principles': ['Object-oriented principles' if 'class ' in content else 'Procedural design'],
            'summary': 'Fallback pattern detection completed'
        }
    
    def _extract_function_details(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract function signatures and docstrings for better code examples."""
        lines = content.split('\n')
        functions = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for function definitions (Python, JavaScript, TypeScript)
            if (line.startswith('def ') or 
                line.startswith('async def ') or
                'function ' in line or
                line.startswith('const ') and '=>' in line):
                
                function_info = {
                    'signature': line,
                    'line_number': i + 1,
                    'docstring': '',
                    'parameters': [],
                    'return_type': '',
                    'purpose': ''
                }
                
                # Extract function name and parameters
                if line.startswith(('def ', 'async def ')):
                    # Python function
                    try:
                        if '(' in line and ')' in line:
                            func_part = line.split('(')[0]
                            func_name = func_part.split()[-1]
                            param_part = line[line.find('(')+1:line.rfind(')')]
                            function_info['name'] = func_name
                            function_info['parameters'] = [p.strip() for p in param_part.split(',') if p.strip()]
                            
                            # Check for return type annotation
                            if '->' in line:
                                function_info['return_type'] = line.split('->')[-1].strip().rstrip(':')
                    except:
                        function_info['name'] = 'unknown'
                elif 'function ' in line:
                    # JavaScript function
                    try:
                        if 'function ' in line:
                            func_part = line.split('function ')[1].split('(')[0]
                            function_info['name'] = func_part.strip()
                    except:
                        function_info['name'] = 'unknown'
                
                # Look for docstring/comments in the next few lines
                j = i + 1
                docstring_lines = []
                while j < len(lines) and j < i + 6:
                    next_line = lines[j].strip()
                    if next_line.startswith('"""') or next_line.startswith("'''"):
                        # Python docstring
                        if next_line.count('"""') >= 2 or next_line.count("'''") >= 2:
                            # Single line docstring
                            docstring_lines.append(next_line)
                            break
                        else:
                            # Multi-line docstring start
                            quote_type = '"""' if '"""' in next_line else "'''"
                            docstring_lines.append(next_line)
                            j += 1
                            while j < len(lines):
                                doc_line = lines[j].strip()
                                docstring_lines.append(doc_line)
                                if quote_type in doc_line:
                                    break
                                j += 1
                            break
                    elif next_line.startswith('#') and len(next_line) > 2:
                        # Comment line that might describe the function
                        docstring_lines.append(next_line)
                    elif next_line.startswith('//') and len(next_line) > 3:
                        # JavaScript comment
                        docstring_lines.append(next_line)
                    elif next_line and not next_line.startswith((' ', '\t')):
                        # Non-indented line, stop looking
                        break
                    j += 1
                
                if docstring_lines:
                    function_info['docstring'] = '\n'.join(docstring_lines[:3])  # Limit to 3 lines
                    # Extract purpose from docstring
                    first_doc_line = docstring_lines[0].strip()
                    if first_doc_line:
                        # Clean up docstring markers
                        purpose = first_doc_line.replace('"""', '').replace("'''", '').replace('#', '').replace('//', '').strip()
                        function_info['purpose'] = purpose[:100]  # Limit length
                
                # Only include functions that seem important (not private/internal)
                func_name = function_info.get('name', '')
                if (func_name and 
                    not func_name.startswith('_') and 
                    len(func_name) > 2 and
                    func_name not in ['test', 'setup', 'teardown']):
                    functions.append(function_info)
                
                # Limit to top 5 functions per file
                if len(functions) >= 5:
                    break
            
            i += 1
        
        return functions
    
    def _extract_class_details(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract class definitions and key methods for better code examples."""
        lines = content.split('\n')
        classes = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for class definitions
            if line.startswith('class ') and ':' in line:
                class_info = {
                    'signature': line,
                    'line_number': i + 1,
                    'name': '',
                    'docstring': '',
                    'methods': [],
                    'inheritance': '',
                    'purpose': ''
                }
                
                # Extract class name and inheritance
                try:
                    class_part = line.replace('class ', '').split(':')[0]
                    if '(' in class_part:
                        class_name = class_part.split('(')[0].strip()
                        inheritance_part = class_part[class_part.find('(')+1:class_part.rfind(')')]
                        class_info['inheritance'] = inheritance_part.strip()
                    else:
                        class_name = class_part.strip()
                    
                    class_info['name'] = class_name
                except:
                    class_info['name'] = 'unknown'
                
                # Look for class docstring
                j = i + 1
                docstring_lines = []
                while j < len(lines) and j < i + 6:
                    next_line = lines[j].strip()
                    if next_line.startswith('"""') or next_line.startswith("'''"):
                        quote_type = '"""' if '"""' in next_line else "'''"
                        if next_line.count(quote_type) >= 2:
                            # Single line docstring
                            docstring_lines.append(next_line)
                            break
                        else:
                            # Multi-line docstring
                            docstring_lines.append(next_line)
                            j += 1
                            while j < len(lines):
                                doc_line = lines[j].strip()
                                docstring_lines.append(doc_line)
                                if quote_type in doc_line:
                                    break
                                j += 1
                            break
                    elif next_line and not next_line.startswith((' ', '\t')):
                        break
                    j += 1
                
                if docstring_lines:
                    class_info['docstring'] = '\n'.join(docstring_lines[:2])  # Limit to 2 lines
                    # Extract purpose from docstring
                    first_doc_line = docstring_lines[0].strip()
                    if first_doc_line:
                        purpose = first_doc_line.replace('"""', '').replace("'''", '').strip()
                        class_info['purpose'] = purpose[:100]
                
                # Look for key methods in the class (first few important ones)
                method_count = 0
                k = i + 1
                while k < len(lines) and method_count < 3:
                    method_line = lines[k].strip()
                    if method_line.startswith('def ') and method_count < 3:
                        # Extract method signature
                        method_name = method_line.split('(')[0].replace('def ', '').strip()
                        if not method_name.startswith('_') or method_name in ['__init__', '__str__', '__repr__']:
                            class_info['methods'].append({
                                'name': method_name,
                                'signature': method_line,
                                'line_number': k + 1
                            })
                            method_count += 1
                    elif method_line and not method_line.startswith((' ', '\t')) and 'class ' in method_line:
                        # Found another class, stop looking
                        break
                    k += 1
                
                # Only include classes that seem important
                class_name = class_info.get('name', '')
                if (class_name and 
                    len(class_name) > 2 and
                    not class_name.startswith('_')):
                    classes.append(class_info)
                
                # Limit to top 3 classes per file
                if len(classes) >= 3:
                    break
            
            i += 1
        
        return classes
    
    def _extract_code_entities(self, file_path: str, content: str) -> List[CodeEntity]:
        """Extract code entities from file content."""
        entities = []
        
        # Python AST parsing
        if file_path.endswith('.py'):
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        entities.append(CodeEntity(
                            name=node.name,
                            type='class',
                            file_path=file_path,
                            line_start=node.lineno,
                            line_end=getattr(node, 'end_lineno', node.lineno),
                            signature=f"class {node.name}",
                            docstring=ast.get_docstring(node) or None
                        ))
                    elif isinstance(node, ast.FunctionDef):
                        entities.append(CodeEntity(
                            name=node.name,
                            type='function',
                            file_path=file_path,
                            line_start=node.lineno,
                            line_end=getattr(node, 'end_lineno', node.lineno),
                            signature=f"def {node.name}",
                            docstring=ast.get_docstring(node) or None
                        ))
            except SyntaxError:
                # Fall back to regex-based extraction
                entities.extend(self._extract_entities_with_regex(file_path, content))
        else:
            # Use regex for other languages
            entities.extend(self._extract_entities_with_regex(file_path, content))
        
        return entities
    
    def _extract_entities_with_regex(self, file_path: str, content: str) -> List[CodeEntity]:
        """Extract entities using regex patterns."""
        entities = []
        lines = content.split('\n')
        
        # Language-specific patterns
        if file_path.endswith('.py'):
            # Classes and functions
            for i, line in enumerate(lines):
                if re.match(r'^class \w+', line.strip()):
                    match = re.search(r'class (\w+)', line)
                    if match:
                        entities.append(CodeEntity(
                            name=match.group(1),
                            type='class',
                            file_path=file_path,
                            line_start=i + 1,
                            line_end=i + 1,
                            signature=line.strip()
                        ))
                elif re.match(r'^def \w+', line.strip()):
                    match = re.search(r'def (\w+)', line)
                    if match:
                        entities.append(CodeEntity(
                            name=match.group(1),
                            type='function',
                            file_path=file_path,
                            line_start=i + 1,
                            line_end=i + 1,
                            signature=line.strip()
                        ))
        
        return entities
    
    def _identify_layer_type(self, path: str) -> Optional[str]:
        """Identify architectural layer type from directory path."""
        path_lower = path.lower()
        
        layer_patterns = {
            'presentation': ['ui', 'view', 'frontend', 'client', 'web', 'gui'],
            'business': ['business', 'service', 'logic', 'core', 'domain'],
            'data': ['data', 'dal', 'repository', 'storage', 'database', 'db'],
            'infrastructure': ['infrastructure', 'infra', 'external', 'adapters'],
            'api': ['api', 'rest', 'graphql', 'endpoint', 'routes'],
            'test': ['test', 'tests', 'testing', 'spec', 'e2e'],
            'config': ['config', 'configuration', 'settings', 'env']
        }
        
        for layer_type, patterns in layer_patterns.items():
            if any(pattern in path_lower for pattern in patterns):
                return layer_type
        
        return None
    
    def _identify_component_type(self, path: str) -> Optional[str]:
        """Identify component type from path."""
        path_lower = path.lower()
        
        for component_type, patterns in self.component_patterns.items():
            if any(pattern in path_lower for pattern in patterns):
                return component_type
        
        return None
    
    def _add_file_to_component(self, file_path: str, component_type: str):
        """Add file to existing component or create new component."""
        # Check if component already exists
        existing_component = None
        for component in self.components:
            if component.type == component_type:
                existing_component = component
                break
        
        if existing_component:
            existing_component.files.append(file_path)
        else:
            component = SystemComponent(
                name=f"{component_type}_component",
                type=component_type,
                description=f"{component_type.title()} component",
                responsibilities=[f"Handle {component_type} operations"],
                files=[file_path]
            )
            self.components.append(component)
            self.logger.info(f"🏗️ Created component: {component_type}")
    
    def _associate_entities_with_components(self, file_path: str, entities: List[CodeEntity]):
        """Associate code entities with system components."""
        for component in self.components:
            if file_path in component.files:
                component.entities.extend(entities)
                break
    
    def _detect_patterns_in_content(self, file_path: str, content: str) -> List[ArchitecturalPattern]:
        """Detect both design and architectural patterns in content."""
        patterns = []
        
        # Run all pattern detectors
        for pattern_name, detector in self.pattern_detectors.items():
            if detector(content):
                pattern_type = self._get_pattern_type(pattern_name)
                pattern = ArchitecturalPattern(
                    pattern_name=pattern_name,
                    pattern_type=pattern_type,
                    description=f"{pattern_name.replace('_', ' ').title()} pattern detected",
                    components=[file_path],
                    evidence=[f"Found in {file_path}"],
                    confidence=0.7
                )
                patterns.append(pattern)
                self.logger.info(f"🔍 Detected {pattern_type} pattern: {pattern_name} in {file_path}")
        
        return patterns
    
    def _get_pattern_type(self, pattern_name: str) -> str:
        """Get the type of pattern (design, architectural, or code_style)."""
        design_patterns = ['singleton', 'factory', 'observer', 'decorator', 'strategy', 'adapter', 'repository']
        architectural_patterns = ['mvc', 'microservices', 'layered', 'clean_architecture', 'event_driven']
        code_style_patterns = ['naming_conventions', 'code_organization', 'dependency_injection']
        
        if pattern_name in design_patterns:
            return 'design'
        elif pattern_name in architectural_patterns:
            return 'architectural'
        elif pattern_name in code_style_patterns:
            return 'code_style'
        else:
            return 'unknown'
    
    def _analyze_dependencies(self, file_path: str, content: str):
        """Analyze dependencies and update component relationships."""
        # Extract import statements
        imports = re.findall(r'import\s+(\w+)|from\s+(\w+)', content)
        
        # Update component dependencies
        for component in self.components:
            if file_path in component.files:
                for import_match in imports:
                    imported_module = import_match[0] or import_match[1]
                    if imported_module and imported_module not in component.dependencies:
                        component.dependencies.append(imported_module)
    
    def _analyze_data_flows(self, file_path: str, content: str):
        """Analyze data flows in the content."""
        # HTTP requests/responses
        if 'request' in content.lower() and 'response' in content.lower():
            data_flow = DataFlow(
                source=file_path,
                target="external_api",
                flow_type="request",
                description="HTTP request/response flow",
                protocols=["HTTP"]
            )
            self.data_flows.append(data_flow)
        
        # Database operations
        if any(keyword in content.lower() for keyword in ['select', 'insert', 'update', 'delete']):
            data_flow = DataFlow(
                source=file_path,
                target="database",
                flow_type="data",
                description="Database operation flow",
                protocols=["SQL"]
            )
            self.data_flows.append(data_flow)
    
    def _process_search_match(self, file_path: str, content: str, line_num: int):
        """Process individual search match."""
        # Update context with interesting matches
        if 'class ' in content:
            self.state.current_context.setdefault('classes_found', []).append(
                {'file': file_path, 'line': line_num, 'content': content}
            )
        elif 'def ' in content:
            self.state.current_context.setdefault('functions_found', []).append(
                {'file': file_path, 'line': line_num, 'content': content}
            )
        elif 'import ' in content:
            self.state.current_context.setdefault('imports_found', []).append(
                {'file': file_path, 'line': line_num, 'content': content}
            )
    
    def _analyze_python_code(self, content: str) -> Dict[str, Any]:
        """Analyze Python-specific code patterns."""
        return {
            'classes': len(re.findall(r'^class \w+', content, re.MULTILINE)),
            'functions': len(re.findall(r'^def \w+', content, re.MULTILINE)),
            'imports': len(re.findall(r'^import \w+|^from \w+', content, re.MULTILINE)),
            'decorators': len(re.findall(r'^@\w+', content, re.MULTILINE)),
            'async_functions': len(re.findall(r'^async def \w+', content, re.MULTILINE)),
            'has_main': '__main__' in content,
            'has_docstrings': '"""' in content or "'''" in content
        }
    
    def _analyze_javascript_code(self, content: str) -> Dict[str, Any]:
        """Analyze JavaScript-specific code patterns."""
        return {
            'functions': len(re.findall(r'function \w+|\w+\s*=\s*function', content)),
            'arrow_functions': len(re.findall(r'=>', content)),
            'classes': len(re.findall(r'class \w+', content)),
            'imports': len(re.findall(r'import \w+|require\(', content)),
            'exports': len(re.findall(r'export |module\.exports', content)),
            'async_functions': len(re.findall(r'async function|async \w+', content)),
            'promises': len(re.findall(r'\.then\(|\.catch\(', content))
        }
    
    def _estimate_complexity(self, content: str, language: str) -> int:
        """Estimate code complexity using simple heuristics."""
        # Count branching statements
        if_statements = len(re.findall(r'\bif\b', content))
        for_statements = len(re.findall(r'\bfor\b', content))
        while_statements = len(re.findall(r'\bwhile\b', content))
        try_statements = len(re.findall(r'\btry\b', content))
        
        # Basic complexity calculation
        complexity = 1 + if_statements + for_statements + while_statements + try_statements
        return complexity
    
    # Pattern detection methods
    def _detect_singleton_pattern(self, content: str) -> bool:
        """Detect singleton pattern."""
        return '__new__' in content and 'instance' in content.lower()
    
    def _detect_factory_pattern(self, content: str) -> bool:
        """Detect factory pattern."""
        factory_keywords = ['factory', 'create', 'builder']
        return any(keyword in content.lower() for keyword in factory_keywords) and 'class' in content.lower()
    
    def _detect_observer_pattern(self, content: str) -> bool:
        """Detect observer pattern."""
        observer_keywords = ['observer', 'notify', 'subscribe', 'event']
        return sum(1 for keyword in observer_keywords if keyword in content.lower()) >= 2
    
    def _detect_decorator_pattern(self, content: str) -> bool:
        """Detect decorator pattern."""
        return '@' in content or 'decorator' in content.lower()
    
    def _detect_strategy_pattern(self, content: str) -> bool:
        """Detect strategy pattern."""
        strategy_keywords = ['strategy', 'algorithm', 'policy']
        return any(keyword in content.lower() for keyword in strategy_keywords)
    
    def _detect_adapter_pattern(self, content: str) -> bool:
        """Detect adapter pattern."""
        adapter_keywords = ['adapter', 'wrapper', 'adapt']
        return any(keyword in content.lower() for keyword in adapter_keywords)
    
    def _detect_repository_pattern(self, content: str) -> bool:
        """Detect repository pattern."""
        repo_keywords = ['repository', 'repo', 'dao', 'data access']
        return any(keyword in content.lower() for keyword in repo_keywords)
    
    def _detect_mvc_pattern(self, content: str) -> bool:
        """Detect MVC pattern."""
        mvc_keywords = ['model', 'view', 'controller']
        return sum(1 for keyword in mvc_keywords if keyword in content.lower()) >= 2
    
    def _detect_microservices_pattern(self, content: str) -> bool:
        """Detect microservices pattern."""
        microservice_keywords = ['service', 'api', 'endpoint', 'docker', 'kubernetes']
        return sum(1 for keyword in microservice_keywords if keyword in content.lower()) >= 2
    
    def _detect_layered_pattern(self, content: str) -> bool:
        """Detect layered architecture pattern."""
        layer_keywords = ['layer', 'tier', 'business', 'presentation', 'data']
        return sum(1 for keyword in layer_keywords if keyword in content.lower()) >= 2
    
    def _detect_clean_architecture_pattern(self, content: str) -> bool:
        """Detect clean architecture pattern."""
        clean_keywords = ['clean', 'hexagonal', 'onion', 'ports', 'adapters']
        return any(keyword in content.lower() for keyword in clean_keywords)
    
    def _detect_event_driven_pattern(self, content: str) -> bool:
        """Detect event-driven pattern."""
        event_keywords = ['event', 'message', 'queue', 'publish', 'subscribe']
        return sum(1 for keyword in event_keywords if keyword in content.lower()) >= 2
    
    def _detect_naming_conventions(self, content: str) -> bool:
        """Detect naming conventions."""
        snake_case_funcs = len(re.findall(r'def [a-z_]+[a-z0-9_]*\(', content))
        camel_case_funcs = len(re.findall(r'def [a-z][a-zA-Z0-9]*\(', content))
        return snake_case_funcs > 0 or camel_case_funcs > 0
    
    def _detect_code_organization(self, content: str) -> bool:
        """Detect code organization patterns."""
        has_imports = 'import ' in content or 'from ' in content
        has_classes = 'class ' in content
        has_functions = 'def ' in content or 'function ' in content
        return has_imports and (has_classes or has_functions)
    
    def _detect_dependency_injection(self, content: str) -> bool:
        """Detect dependency injection patterns."""
        di_keywords = ['inject', 'dependency', 'container', 'provider']
        return any(keyword in content.lower() for keyword in di_keywords)
    
    def _generate_summary(self) -> str:
        """Generate a comprehensive summary of code and architecture analysis."""
        summary = f"Code & Architecture Analysis Summary:\n"
        summary += f"• Found {len(self.code_files)} source code files\n"
        summary += f"• Analyzed {len(self.analyzed_files)} files in detail\n"
        summary += f"• Identified {len(self.components)} system components\n"
        summary += f"• Detected {len(self.patterns)} patterns\n"
        summary += f"• Mapped {len(self.data_flows)} data flows\n"
        
        # Language distribution
        if self.language_stats:
            lang_summary = ', '.join(f'{lang}({count})' for lang, count in self.language_stats.items())
            summary += f"• Languages: {lang_summary}\n"
        
        # Entity count
        total_entities = sum(len(entities) for entities in self.code_entities.values())
        if total_entities > 0:
            summary += f"• Code entities: {total_entities}\n"
        
        # Component types
        if self.components:
            component_types = defaultdict(int)
            for component in self.components:
                component_types[component.type] += 1
            comp_summary = ', '.join(f'{ctype}({count})' for ctype, count in component_types.items())
            summary += f"• Components: {comp_summary}\n"
        
        # Pattern breakdown
        if self.patterns:
            pattern_types = defaultdict(int)
            for pattern in self.patterns:
                pattern_types[pattern.pattern_type] += 1
            pattern_summary = ', '.join(f'{ptype}({count})' for ptype, count in pattern_types.items())
            summary += f"• Patterns: {pattern_summary}\n"
        
        # Architectural layers
        if self.architectural_layers:
            layer_types = list(set(self.architectural_layers.values()))
            summary += f"• Layers: {', '.join(layer_types)}\n"
        
        # Cache performance
        if self.state.cache_hits > 0:
            summary += f"• Cache hits: {self.state.cache_hits}\n"
        
        if self.state.error_count > 0:
            summary += f"• Errors: {self.state.error_count}\n"
        
        return summary
    
    # Public methods for accessing analysis results
    def get_code_entities(self) -> Dict[str, List[CodeEntity]]:
        """Get all extracted code entities."""
        return self.code_entities
    
    def get_components(self) -> List[SystemComponent]:
        """Get all identified system components."""
        return self.components
    
    def get_patterns(self) -> List[ArchitecturalPattern]:
        """Get all detected patterns."""
        return self.patterns
    
    def get_data_flows(self) -> List[DataFlow]:
        """Get all mapped data flows."""
        return self.data_flows
    
    def get_analyzed_files(self) -> Dict[str, Any]:
        """Get all analyzed files."""
        return self.analyzed_files
    
    def get_language_stats(self) -> Dict[str, int]:
        """Get language distribution statistics."""
        return dict(self.language_stats)
    
    def get_architectural_layers(self) -> Dict[str, str]:
        """Get all identified architectural layers."""
        return self.architectural_layers