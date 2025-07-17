"""
ReAct Architecture Agent for system design analysis and architectural pattern detection.

This agent uses the ReAct pattern to systematically explore and analyze system architecture
through reasoning, acting with tools, and observing results.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from ..aci.repo import CodeRepo
from ..config import CfConfig
from ..core.react_agent import ReActAgent, ReActAction, ActionType


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
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitecturalPattern:
    """Represents an architectural pattern."""
    pattern_name: str
    description: str
    components: List[str]
    evidence: List[str]
    confidence: float
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


class ReActArchitectureAgent(ReActAgent):
    """
    Architecture agent that uses ReAct pattern for systematic architectural analysis.
    
    ReAct Loop:
    1. Reason: Analyze what architectural aspects to explore next
    2. Act: Use tools to scan, analyze, and understand system design
    3. Observe: Reflect on findings and build architectural understanding
    """
    
    def __init__(self, repo: CodeRepo, config: CfConfig):
        super().__init__(repo, config, "ArchitectureAgent")
        
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
            'util': ['util', 'helper', 'common', 'shared', 'lib', 'utils']
        }
        
        # Pattern detection strategies
        self.pattern_detectors = {
            'mvc': self._detect_mvc_pattern,
            'microservices': self._detect_microservices_pattern,
            'layered': self._detect_layered_pattern,
            'repository': self._detect_repository_pattern,
            'factory': self._detect_factory_pattern,
            'observer': self._detect_observer_pattern,
            'singleton': self._detect_singleton_pattern,
            'adapter': self._detect_adapter_pattern,
            'decorator': self._detect_decorator_pattern,
            'strategy': self._detect_strategy_pattern
        }
        
        # Quality attributes to assess
        self.quality_attributes = [
            'maintainability', 'scalability', 'performance', 
            'security', 'reliability', 'testability'
        ]
    
    def map_architecture(self, description: str) -> Dict[str, Any]:
        """
        Main entry point for architecture mapping using ReAct pattern.
        
        Args:
            description: Description of what to focus on during analysis
            
        Returns:
            Comprehensive architectural analysis results
        """
        goal = f"Map architecture for: {description}"
        return self.execute_react_loop(goal, max_iterations=18)
    
    def reason(self) -> str:
        """
        Reasoning phase: Determine what architectural analysis action to take next.
        
        Returns:
            Reasoning about next action to take
        """
        current_context = self.state.current_context
        iteration = self.state.iteration
        
        # First iteration: Start with high-level structure analysis
        if iteration == 1:
            return "I should start by understanding the overall repository structure to identify architectural layers and major components."
        
        # Early iterations: Focus on component discovery
        if iteration <= 3 and not self.components:
            return "I need to identify system components by scanning the directory structure and looking for architectural patterns."
        
        # If we have some components but need more context
        if self.components and len(self.components) < 3:
            return f"I found {len(self.components)} components but need to discover more. Let me analyze code files to understand the system better."
        
        # Focus on understanding relationships and data flows
        if self.components and not self.data_flows:
            return "I have identified components. Now I should analyze how they interact and what data flows between them."
        
        # Pattern detection phase
        if len(self.components) >= 3 and not self.patterns:
            return "I have good component coverage. Now I should detect architectural patterns and design principles used in the system."
        
        # Goal-specific analysis
        if "microservice" in self.state.goal.lower():
            return "The goal mentions microservices. I should look for service boundaries, communication patterns, and deployment structures."
        elif "api" in self.state.goal.lower():
            return "The goal mentions API. I should analyze API design, endpoints, and how the API layer is structured."
        elif "database" in self.state.goal.lower():
            return "The goal mentions database. I should analyze data models, database access patterns, and data architecture."
        elif "security" in self.state.goal.lower():
            return "The goal mentions security. I should analyze authentication, authorization, and security patterns."
        
        # Deep analysis phase
        if len(self.components) >= 3 and self.patterns:
            return "I have good understanding of components and patterns. Now I should analyze quality attributes and architectural decisions."
        
        # Default reasoning
        return "I should continue analyzing the architecture systematically, focusing on understanding the system design and its implications."
    
    def plan_action(self, reasoning: str) -> ReActAction:
        """
        Plan the next action based on reasoning.
        
        Args:
            reasoning: The reasoning output
            
        Returns:
            Action to take
        """
        iteration = self.state.iteration
        
        # Early iterations: Structure analysis
        if iteration <= 2:
            return ReActAction(
                action_type=ActionType.SCAN_DIRECTORY,
                description="Scan repository structure for architectural analysis",
                parameters={'directory': '.', 'max_depth': 4},
                expected_outcome="Understand overall system structure and identify main components"
            )
        
        # Component discovery phase
        if not self.components and iteration <= 5:
            return ReActAction(
                action_type=ActionType.LIST_FILES,
                description="List files to identify architectural components",
                parameters={'pattern': '*', 'directory': '.'},
                expected_outcome="Identify files that represent different architectural components"
            )
        
        # Analyze main application files
        if iteration <= 6:
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for main application entry points",
                parameters={'pattern': 'main', 'file_types': ['.py', '.js', '.java', '.go'], 'max_results': 10},
                expected_outcome="Find main application files and understand entry points"
            )
        
        # Configuration analysis
        if iteration <= 8:
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for configuration files",
                parameters={'pattern': 'config', 'file_types': ['.yaml', '.yml', '.json', '.toml', '.ini'], 'max_results': 15},
                expected_outcome="Understand system configuration and deployment patterns"
            )
        
        # API analysis
        if "api" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for API-related files and patterns",
                parameters={'pattern': 'api', 'file_types': ['.py', '.js', '.java', '.go'], 'max_results': 20},
                expected_outcome="Understand API architecture and endpoints"
            )
        
        # Service discovery
        if "service" in self.state.goal.lower() or "microservice" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for service-related patterns",
                parameters={'pattern': 'service', 'file_types': ['.py', '.js', '.java', '.go'], 'max_results': 20},
                expected_outcome="Identify services and service boundaries"
            )
        
        # Database analysis
        if "database" in self.state.goal.lower() or "data" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for database and data access patterns",
                parameters={'pattern': 'model', 'file_types': ['.py', '.js', '.java', '.go'], 'max_results': 20},
                expected_outcome="Understand data models and database architecture"
            )
        
        # Read important architectural files
        if self.components and iteration <= 12:
            # Look for architecture documentation
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for architecture documentation",
                parameters={'pattern': 'architecture', 'file_types': ['.md', '.txt', '.rst'], 'max_results': 5},
                expected_outcome="Find architectural documentation and design decisions"
            )
        
        # Analyze specific component files
        if self.components and iteration <= 15:
            component_files = []
            for component in self.components:
                component_files.extend(component.files)
            
            if component_files:
                return ReActAction(
                    action_type=ActionType.READ_FILE,
                    description=f"Read component file: {component_files[0]}",
                    parameters={'file_path': component_files[0], 'max_lines': 200},
                    expected_outcome="Understand component implementation and patterns"
                )
        
        # Use LLM for synthesis
        return ReActAction(
            action_type=ActionType.LLM_REASONING,
            description="Use LLM to synthesize architectural insights",
            parameters={
                'context': f"Components: {len(self.components)}, Patterns: {len(self.patterns)}, Goal: {self.state.goal}",
                'question': "What architectural insights can be derived from the current analysis?"
            },
            expected_outcome="Generate architectural insights and recommendations"
        )
    
    def observe(self, observation):
        """
        Enhanced observation phase for architectural analysis.
        
        Args:
            observation: Observation from the action
        """
        super().observe(observation)
        
        # Process architecture-specific observations
        if observation.success and observation.result:
            result = observation.result
            
            # If we scanned a directory, analyze structure
            if isinstance(result, dict) and 'contents' in result:
                self._analyze_directory_structure(result['contents'])
            
            # If we listed files, identify component files
            elif isinstance(result, dict) and 'files' in result:
                self._identify_component_files(result['files'])
            
            # If we searched files, analyze patterns
            elif isinstance(result, dict) and 'results' in result:
                self._analyze_search_results(result['results'])
            
            # If we read a file, analyze its architectural significance
            elif isinstance(result, dict) and 'content' in result:
                self._analyze_file_content(result['file_path'], result['content'])
    
    def _analyze_directory_structure(self, contents: List[Dict[str, Any]]):
        """Analyze directory structure for architectural patterns."""
        directories = [item for item in contents if item['is_directory']]
        
        # Identify architectural layers
        for directory in directories:
            path = directory['path']
            layer_type = self._identify_layer_type(path)
            
            if layer_type:
                self.architectural_layers[path] = layer_type
                self.logger.info(f"🏗️ Identified layer: {path} -> {layer_type}")
        
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
    
    def _identify_component_files(self, files: List[Dict[str, Any]]):
        """Identify component files from file list."""
        for file_info in files:
            file_path = file_info['path']
            component_type = self._identify_component_type(file_path)
            
            if component_type:
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
                    self.logger.info(f"🏗️ Identified component file: {file_path} -> {component_type}")
    
    def _analyze_search_results(self, results: List[Dict[str, Any]]):
        """Analyze search results for architectural patterns."""
        for result in results:
            file_path = result['file_path']
            matches = result.get('matches', [])
            
            # Analyze matches for architectural patterns
            for match in matches:
                content = match.get('content', '')
                self._detect_patterns_in_content(file_path, content)
    
    def _analyze_file_content(self, file_path: str, content: str):
        """Analyze file content for architectural insights."""
        # Detect architectural patterns in the content
        self._detect_patterns_in_content(file_path, content)
        
        # Analyze imports and dependencies
        self._analyze_dependencies(file_path, content)
        
        # Analyze data flows
        self._analyze_data_flows(file_path, content)
    
    def _detect_patterns_in_content(self, file_path: str, content: str):
        """Detect architectural patterns in content."""
        # Run all pattern detectors
        for pattern_name, detector in self.pattern_detectors.items():
            if detector(content):
                pattern = ArchitecturalPattern(
                    pattern_name=pattern_name,
                    description=f"{pattern_name.title()} pattern detected",
                    components=[file_path],
                    evidence=[f"Found in {file_path}"],
                    confidence=0.7
                )
                self.patterns.append(pattern)
                self.logger.info(f"🔍 Detected pattern: {pattern_name} in {file_path}")
    
    def _analyze_dependencies(self, file_path: str, content: str):
        """Analyze dependencies and relationships."""
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
        # Look for HTTP requests/responses
        if 'request' in content.lower() and 'response' in content.lower():
            data_flow = DataFlow(
                source=file_path,
                target="external_api",
                flow_type="request",
                description="HTTP request/response flow",
                protocols=["HTTP"]
            )
            self.data_flows.append(data_flow)
        
        # Look for database operations
        if any(keyword in content.lower() for keyword in ['select', 'insert', 'update', 'delete']):
            data_flow = DataFlow(
                source=file_path,
                target="database",
                flow_type="data",
                description="Database operation flow",
                protocols=["SQL"]
            )
            self.data_flows.append(data_flow)
    
    # Pattern detection methods
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
    
    def _detect_repository_pattern(self, content: str) -> bool:
        """Detect repository pattern."""
        repo_keywords = ['repository', 'repo', 'dao', 'data access']
        return any(keyword in content.lower() for keyword in repo_keywords)
    
    def _detect_factory_pattern(self, content: str) -> bool:
        """Detect factory pattern."""
        factory_keywords = ['factory', 'create', 'builder']
        return any(keyword in content.lower() for keyword in factory_keywords) and 'class' in content.lower()
    
    def _detect_observer_pattern(self, content: str) -> bool:
        """Detect observer pattern."""
        observer_keywords = ['observer', 'notify', 'subscribe', 'event']
        return sum(1 for keyword in observer_keywords if keyword in content.lower()) >= 2
    
    def _detect_singleton_pattern(self, content: str) -> bool:
        """Detect singleton pattern."""
        return '__new__' in content and 'instance' in content.lower()
    
    def _detect_adapter_pattern(self, content: str) -> bool:
        """Detect adapter pattern."""
        adapter_keywords = ['adapter', 'wrapper', 'adapt']
        return any(keyword in content.lower() for keyword in adapter_keywords)
    
    def _detect_decorator_pattern(self, content: str) -> bool:
        """Detect decorator pattern."""
        return '@' in content or 'decorator' in content.lower()
    
    def _detect_strategy_pattern(self, content: str) -> bool:
        """Detect strategy pattern."""
        strategy_keywords = ['strategy', 'algorithm', 'policy']
        return any(keyword in content.lower() for keyword in strategy_keywords)
    
    def _generate_summary(self) -> str:
        """Generate a comprehensive summary of architecture analysis."""
        summary = f"Architecture Analysis Summary:\\n"
        summary += f"• Identified {len(self.components)} system components\\n"
        summary += f"• Detected {len(self.patterns)} architectural patterns\\n"
        summary += f"• Mapped {len(self.data_flows)} data flows\\n"
        summary += f"• Found {len(self.architectural_layers)} architectural layers\\n"
        
        # Component types
        if self.components:
            component_types = defaultdict(int)
            for component in self.components:
                component_types[component.type] += 1
            
            comp_summary = ', '.join(f'{ctype}({count})' for ctype, count in component_types.items())
            summary += f"• Component types: {comp_summary}\\n"
        
        # Pattern types
        if self.patterns:
            pattern_names = [pattern.pattern_name for pattern in self.patterns]
            summary += f"• Patterns found: {', '.join(set(pattern_names))}\\n"
        
        # Architectural layers
        if self.architectural_layers:
            layer_types = list(set(self.architectural_layers.values()))
            summary += f"• Architectural layers: {', '.join(layer_types)}\\n"
        
        # Cache performance
        if self.state.cache_hits > 0:
            summary += f"• Cache hits: {self.state.cache_hits}\\n"
        
        if self.state.error_count > 0:
            summary += f"• Errors encountered: {self.state.error_count}\\n"
        
        return summary
    
    def get_components(self) -> List[SystemComponent]:
        """Get all identified system components."""
        return self.components
    
    def get_patterns(self) -> List[ArchitecturalPattern]:
        """Get all detected architectural patterns."""
        return self.patterns
    
    def get_data_flows(self) -> List[DataFlow]:
        """Get all mapped data flows."""
        return self.data_flows
    
    def get_architectural_layers(self) -> Dict[str, str]:
        """Get all identified architectural layers."""
        return self.architectural_layers