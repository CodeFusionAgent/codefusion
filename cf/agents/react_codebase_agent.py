"""
ReAct Codebase Agent for comprehensive source code analysis.

This agent uses the ReAct pattern to systematically explore and analyze source code
through reasoning, acting with tools, and observing results.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict

from ..aci.repo import CodeRepo
from ..config import CfConfig
from ..core.react_agent import ReActAgent, ReActAction, ActionType


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
class CodePattern:
    """Represents a code pattern or convention."""
    pattern_type: str
    description: str
    examples: List[str]
    confidence: float
    occurrences: int


class ReActCodebaseAgent(ReActAgent):
    """
    Codebase agent that uses ReAct pattern for systematic code analysis.
    
    ReAct Loop:
    1. Reason: Analyze what code to explore next
    2. Act: Use tools to scan, read, search, or analyze code
    3. Observe: Reflect on findings and plan next steps
    """
    
    def __init__(self, repo: CodeRepo, config: CfConfig):
        super().__init__(repo, config, "CodebaseAgent")
        
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
        self.code_patterns = []
        self.dependency_graph = {}
        self.language_stats = defaultdict(int)
        
        # Pattern detection
        self.pattern_detectors = {
            'design_patterns': self._detect_design_patterns,
            'naming_conventions': self._detect_naming_conventions,
            'architectural_patterns': self._detect_architectural_patterns,
            'code_smells': self._detect_code_smells
        }
    
    def analyze_codebase(self, description: str) -> Dict[str, Any]:
        """
        Main entry point for codebase analysis using ReAct pattern.
        
        Args:
            description: Description of what to focus on during analysis
            
        Returns:
            Comprehensive codebase analysis results
        """
        goal = f"Analyze codebase for: {description}"
        return self.execute_react_loop(goal, max_iterations=20)
    
    def reason(self) -> str:
        """
        Reasoning phase: Determine what code analysis action to take next.
        
        Returns:
            Reasoning about next action to take
        """
        current_context = self.state.current_context
        iteration = self.state.iteration
        
        # First iteration: Start with directory scan to understand structure
        if iteration == 1:
            return "I should start by scanning the repository structure to understand the codebase layout and identify source code files."
        
        # Early iterations: Focus on discovery
        if iteration <= 3 and not self.code_files:
            return "I need to identify source code files by scanning directories and looking for common programming language extensions."
        
        # If we have code files but haven't analyzed them yet
        if self.code_files and not self.analyzed_files:
            return f"I found {len(self.code_files)} code files. Now I should analyze the most important ones to understand the codebase structure."
        
        # If we have some analysis but need more depth
        if self.analyzed_files and len(self.analyzed_files) < 5:
            return "I've analyzed some files but need to dive deeper. Let me examine more files and look for patterns and dependencies."
        
        # Focus on specific goal-related analysis
        if "api" in self.state.goal.lower():
            return "The goal mentions API. I should search for API-related patterns, endpoints, and routing code."
        elif "database" in self.state.goal.lower():
            return "The goal mentions database. I should search for database models, queries, and data access patterns."
        elif "test" in self.state.goal.lower():
            return "The goal mentions testing. I should search for test files and testing patterns."
        elif "config" in self.state.goal.lower():
            return "The goal mentions configuration. I should search for configuration files and settings."
        
        # If we have good coverage, focus on patterns and relationships
        if len(self.analyzed_files) >= 5:
            return "I have analyzed multiple files. Now I should look for patterns, dependencies, and architectural insights."
        
        # Default reasoning
        return "I should continue analyzing the codebase systematically, focusing on files that are most relevant to the goal."
    
    def plan_action(self, reasoning: str) -> ReActAction:
        """
        Plan the next action based on reasoning.
        
        Args:
            reasoning: The reasoning output
            
        Returns:
            Action to take
        """
        iteration = self.state.iteration
        
        # Early iterations: Directory scanning and file discovery
        if iteration <= 2:
            return ReActAction(
                action_type=ActionType.SCAN_DIRECTORY,
                description="Scan repository for source code files",
                parameters={'directory': '.', 'max_depth': 3},
                expected_outcome="Understand repository structure and find source code"
            )
        
        # Find source code files if not found yet
        if not self.code_files and iteration <= 4:
            return ReActAction(
                action_type=ActionType.LIST_FILES,
                description="List source code files",
                parameters={'pattern': '.py', 'directory': '.'},
                expected_outcome="Identify Python source files"
            )
        
        # Analyze high-priority source files
        if self.code_files and len(self.analyzed_files) < 5:
            # Prioritize main files, __init__.py, and files with 'main' in name
            priority_files = [f for f in self.code_files if 'main' in f.lower() or '__init__' in f.lower()]
            if priority_files:
                file_to_analyze = priority_files[0]
            else:
                file_to_analyze = self.code_files[0]
            
            return ReActAction(
                action_type=ActionType.READ_FILE,
                description=f"Read and analyze source file: {file_to_analyze}",
                parameters={'file_path': file_to_analyze, 'max_lines': 500},
                expected_outcome="Understand code structure and extract entities"
            )
        
        # Goal-specific searches
        if "api" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for API-related code patterns",
                parameters={'pattern': 'api', 'file_types': ['.py', '.js', '.ts'], 'max_results': 20},
                expected_outcome="Find API endpoints, routes, and handlers"
            )
        
        elif "class" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for class definitions",
                parameters={'pattern': 'class ', 'file_types': ['.py', '.js', '.ts', '.java'], 'max_results': 20},
                expected_outcome="Find class definitions and OOP patterns"
            )
        
        elif "function" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for function definitions",
                parameters={'pattern': 'def ', 'file_types': ['.py'], 'max_results': 20},
                expected_outcome="Find function definitions and analyze structure"
            )
        
        elif "import" in self.state.goal.lower() or "dependency" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for import statements",
                parameters={'pattern': 'import ', 'file_types': ['.py', '.js', '.ts'], 'max_results': 30},
                expected_outcome="Understand dependencies and module structure"
            )
        
        # Analyze specific files for patterns
        if self.analyzed_files:
            return ReActAction(
                action_type=ActionType.ANALYZE_CODE,
                description="Analyze code patterns and complexity",
                parameters={'file_path': list(self.analyzed_files.keys())[0], 'analysis_type': 'patterns'},
                expected_outcome="Extract code patterns and complexity metrics"
            )
        
        # Default: Use LLM reasoning
        return ReActAction(
            action_type=ActionType.LLM_REASONING,
            description="Use LLM to determine next code analysis step",
            parameters={
                'context': str(self.state.current_context),
                'question': f"What should I analyze next for: {self.state.goal}?"
            },
            expected_outcome="Get guidance on next analysis step"
        )
    
    def observe(self, observation):
        """
        Enhanced observation phase for codebase analysis.
        
        Args:
            observation: Observation from the action
        """
        super().observe(observation)
        
        # Process code-specific observations
        if observation.success and observation.result:
            result = observation.result
            
            # If we scanned a directory, extract source code files
            if isinstance(result, dict) and 'contents' in result:
                for item in result['contents']:
                    if not item['is_directory'] and self._is_source_code_file(item['path']):
                        if item['path'] not in self.code_files:
                            self.code_files.append(item['path'])
                            self.language_stats[self._detect_language(item['path'])] += 1
                            self.logger.info(f"💾 Found source file: {item['path']}")
            
            # If we listed files, filter for source code
            elif isinstance(result, dict) and 'files' in result:
                for file_info in result['files']:
                    if self._is_source_code_file(file_info['path']):
                        if file_info['path'] not in self.code_files:
                            self.code_files.append(file_info['path'])
                            self.language_stats[self._detect_language(file_info['path'])] += 1
                            self.logger.info(f"💾 Found source file: {file_info['path']}")
            
            # If we read a file, analyze its code content
            elif isinstance(result, dict) and 'content' in result:
                file_path = result['file_path']
                content = result['content']
                
                # Analyze the code content
                analysis = self._analyze_code_content(file_path, content)
                self.analyzed_files[file_path] = analysis
                
                # Extract code entities
                entities = self._extract_code_entities(file_path, content)
                self.code_entities[file_path] = entities
                
                # Detect patterns
                patterns = self._detect_patterns_in_file(file_path, content)
                self.code_patterns.extend(patterns)
                
                self.logger.info(f"🔍 Analyzed code file: {file_path}")
            
            # If we searched files, process the results
            elif isinstance(result, dict) and 'results' in result:
                for search_result in result['results']:
                    file_path = search_result['file_path']
                    matches = search_result.get('matches', [])
                    
                    # Process search matches
                    if matches:
                        self._process_search_matches(file_path, matches)
                        self.logger.info(f"🔍 Found {len(matches)} matches in {file_path}")
    
    def _is_source_code_file(self, file_path: str) -> bool:
        """Check if a file is source code."""
        # Common source code extensions
        source_extensions = [
            '.py', '.js', '.ts', '.tsx', '.jsx',
            '.java', '.c', '.cpp', '.cc', '.cxx',
            '.h', '.hpp', '.go', '.rs', '.kt',
            '.swift', '.php', '.rb', '.scala',
            '.cs', '.vb', '.clj', '.hs', '.ml'
        ]
        
        return any(file_path.lower().endswith(ext) for ext in source_extensions)
    
    def _analyze_code_content(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze code content and extract metrics."""
        lines = content.split('\\n')
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
            'has_tests': 'test' in file_path.lower() or 'assert' in content
        }
    
    def _extract_code_entities(self, file_path: str, content: str) -> List[CodeEntity]:
        """Extract code entities from file content."""
        entities = []
        lines = content.split('\\n')
        
        # Extract Python classes and functions
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
        lines = content.split('\\n')
        
        # Python patterns
        if file_path.endswith('.py'):
            # Class definitions
            for i, line in enumerate(lines):
                if re.match(r'^class \\w+', line.strip()):
                    class_name = re.search(r'class (\\w+)', line).group(1)
                    entities.append(CodeEntity(
                        name=class_name,
                        type='class',
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1,
                        signature=line.strip()
                    ))
                
                # Function definitions
                elif re.match(r'^def \\w+', line.strip()):
                    func_name = re.search(r'def (\\w+)', line).group(1)
                    entities.append(CodeEntity(
                        name=func_name,
                        type='function',
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=i + 1,
                        signature=line.strip()
                    ))
        
        return entities
    
    def _detect_patterns_in_file(self, file_path: str, content: str) -> List[CodePattern]:
        """Detect code patterns in a file."""
        patterns = []
        
        # Detect design patterns
        if 'class' in content and 'def __init__' in content:
            patterns.append(CodePattern(
                pattern_type='design_pattern',
                description='Constructor pattern detected',
                examples=[file_path],
                confidence=0.8,
                occurrences=1
            ))
        
        # Detect naming conventions
        if re.search(r'def [a-z_]+[a-z0-9_]*\\(', content):
            patterns.append(CodePattern(
                pattern_type='naming_convention',
                description='Snake case function naming',
                examples=[file_path],
                confidence=0.9,
                occurrences=len(re.findall(r'def [a-z_]+[a-z0-9_]*\\(', content))
            ))
        
        # Detect architectural patterns
        if 'api' in content.lower() and ('route' in content.lower() or 'endpoint' in content.lower()):
            patterns.append(CodePattern(
                pattern_type='architectural_pattern',
                description='API/REST pattern detected',
                examples=[file_path],
                confidence=0.7,
                occurrences=1
            ))
        
        return patterns
    
    def _process_search_matches(self, file_path: str, matches: List[Dict[str, Any]]):
        """Process search matches and update context."""
        for match in matches:
            line_content = match.get('content', '')
            line_num = match.get('line_num', 0)
            
            # Update context with interesting matches
            if 'class ' in line_content:
                self.state.current_context.setdefault('classes_found', []).append(
                    {'file': file_path, 'line': line_num, 'content': line_content}
                )
            elif 'def ' in line_content:
                self.state.current_context.setdefault('functions_found', []).append(
                    {'file': file_path, 'line': line_num, 'content': line_content}
                )
            elif 'import ' in line_content:
                self.state.current_context.setdefault('imports_found', []).append(
                    {'file': file_path, 'line': line_num, 'content': line_content}
                )
    
    def _analyze_python_code(self, content: str) -> Dict[str, Any]:
        """Analyze Python-specific code patterns."""
        analysis = {
            'classes': len(re.findall(r'^class \\w+', content, re.MULTILINE)),
            'functions': len(re.findall(r'^def \\w+', content, re.MULTILINE)),
            'imports': len(re.findall(r'^import \\w+|^from \\w+', content, re.MULTILINE)),
            'decorators': len(re.findall(r'^@\\w+', content, re.MULTILINE)),
            'async_functions': len(re.findall(r'^async def \\w+', content, re.MULTILINE)),
            'has_main': '__main__' in content,
            'has_docstrings': '\"\"\"' in content or "'''" in content
        }
        
        return analysis
    
    def _analyze_javascript_code(self, content: str) -> Dict[str, Any]:
        """Analyze JavaScript-specific code patterns."""
        analysis = {
            'functions': len(re.findall(r'function \\w+|\\w+\\s*=\\s*function', content)),
            'arrow_functions': len(re.findall(r'=>', content)),
            'classes': len(re.findall(r'class \\w+', content)),
            'imports': len(re.findall(r'import \\w+|require\\(', content)),
            'exports': len(re.findall(r'export |module\\.exports', content)),
            'async_functions': len(re.findall(r'async function|async \\w+', content)),
            'promises': len(re.findall(r'\\.then\\(|\\.catch\\(', content))
        }
        
        return analysis
    
    def _estimate_complexity(self, content: str, language: str) -> int:
        """Estimate code complexity using simple heuristics."""
        # Count branching statements
        if_statements = len(re.findall(r'\\bif\\b', content))
        for_statements = len(re.findall(r'\\bfor\\b', content))
        while_statements = len(re.findall(r'\\bwhile\\b', content))
        try_statements = len(re.findall(r'\\btry\\b', content))
        
        # Basic complexity calculation
        complexity = 1 + if_statements + for_statements + while_statements + try_statements
        
        return complexity
    
    def _detect_design_patterns(self, content: str) -> List[CodePattern]:
        """Detect design patterns in code."""
        patterns = []
        
        # Singleton pattern
        if 'class' in content and '__new__' in content:
            patterns.append(CodePattern(
                pattern_type='singleton',
                description='Singleton pattern detected',
                examples=[],
                confidence=0.7,
                occurrences=1
            ))
        
        # Factory pattern
        if 'create' in content.lower() and 'class' in content:
            patterns.append(CodePattern(
                pattern_type='factory',
                description='Factory pattern detected',
                examples=[],
                confidence=0.6,
                occurrences=1
            ))
        
        return patterns
    
    def _detect_naming_conventions(self, content: str) -> List[CodePattern]:
        """Detect naming conventions in code."""
        patterns = []
        
        # Check for consistent naming
        snake_case_funcs = len(re.findall(r'def [a-z_]+[a-z0-9_]*\\(', content))
        camel_case_funcs = len(re.findall(r'def [a-z][a-zA-Z0-9]*\\(', content))
        
        if snake_case_funcs > camel_case_funcs:
            patterns.append(CodePattern(
                pattern_type='naming_convention',
                description='Snake case naming convention',
                examples=[],
                confidence=0.9,
                occurrences=snake_case_funcs
            ))
        
        return patterns
    
    def _detect_architectural_patterns(self, content: str) -> List[CodePattern]:
        """Detect architectural patterns in code."""
        patterns = []
        
        # MVC pattern
        if any(keyword in content.lower() for keyword in ['model', 'view', 'controller']):
            patterns.append(CodePattern(
                pattern_type='mvc',
                description='MVC pattern detected',
                examples=[],
                confidence=0.6,
                occurrences=1
            ))
        
        return patterns
    
    def _detect_code_smells(self, content: str) -> List[CodePattern]:
        """Detect code smells."""
        patterns = []
        
        # Long functions (heuristic)
        lines = content.split('\\n')
        current_function_length = 0
        in_function = False
        
        for line in lines:
            if line.strip().startswith('def '):
                in_function = True
                current_function_length = 0
            elif in_function:
                current_function_length += 1
                if current_function_length > 50:  # Arbitrary threshold
                    patterns.append(CodePattern(
                        pattern_type='code_smell',
                        description='Long function detected',
                        examples=[],
                        confidence=0.8,
                        occurrences=1
                    ))
                    in_function = False
            
            if line.strip() == '':
                in_function = False
        
        return patterns
    
    def _generate_summary(self) -> str:
        """Generate a comprehensive summary of codebase analysis."""
        if not self.code_files:
            return "No source code files found in the repository."
        
        summary = f"Codebase Analysis Summary:\\n"
        summary += f"• Found {len(self.code_files)} source code files\\n"
        summary += f"• Analyzed {len(self.analyzed_files)} files in detail\\n"
        summary += f"• Extracted {sum(len(entities) for entities in self.code_entities.values())} code entities\\n"
        summary += f"• Detected {len(self.code_patterns)} code patterns\\n"
        
        # Language distribution
        if self.language_stats:
            lang_summary = ', '.join(f'{lang}({count})' for lang, count in self.language_stats.items())
            summary += f"• Languages: {lang_summary}\\n"
        
        # Entity types
        if self.code_entities:
            entity_types = defaultdict(int)
            for entities in self.code_entities.values():
                for entity in entities:
                    entity_types[entity.type] += 1
            
            if entity_types:
                entity_summary = ', '.join(f'{etype}({count})' for etype, count in entity_types.items())
                summary += f"• Entities: {entity_summary}\\n"
        
        # Pattern types
        if self.code_patterns:
            pattern_types = defaultdict(int)
            for pattern in self.code_patterns:
                pattern_types[pattern.pattern_type] += 1
            
            pattern_summary = ', '.join(f'{ptype}({count})' for ptype, count in pattern_types.items())
            summary += f"• Patterns: {pattern_summary}\\n"
        
        # Cache performance
        if self.state.cache_hits > 0:
            summary += f"• Cache hits: {self.state.cache_hits}\\n"
        
        if self.state.error_count > 0:
            summary += f"• Errors encountered: {self.state.error_count}\\n"
        
        return summary
    
    def get_code_entities(self) -> Dict[str, List[CodeEntity]]:
        """Get all extracted code entities."""
        return self.code_entities
    
    def get_code_patterns(self) -> List[CodePattern]:
        """Get all detected code patterns."""
        return self.code_patterns
    
    def get_analyzed_files(self) -> Dict[str, Any]:
        """Get all analyzed files."""
        return self.analyzed_files
    
    def get_language_stats(self) -> Dict[str, int]:
        """Get language distribution statistics."""
        return dict(self.language_stats)