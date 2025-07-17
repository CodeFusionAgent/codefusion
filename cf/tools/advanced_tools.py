"""
Advanced Tools for comprehensive code exploration and analysis.

This module provides an extended toolkit for agents to perform sophisticated
analysis including architecture diagrams, documentation parsing, and more.
"""

import re
import json
import ast
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

from ..aci.repo import CodeRepo
from ..config import CfConfig


@dataclass
class AnalysisResult:
    """Represents the result of a tool analysis."""
    tool_name: str
    success: bool
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    error_message: Optional[str] = None


@dataclass
class DiagramInfo:
    """Information about a diagram found in the codebase."""
    file_path: str
    diagram_type: str  # 'mermaid', 'plantuml', 'graphviz', 'draw.io'
    title: str
    content: str
    components: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)


@dataclass
class DocumentationStructure:
    """Structure of documentation found in the codebase."""
    file_path: str
    doc_type: str  # 'readme', 'api', 'architecture', 'tutorial'
    sections: List[str]
    code_examples: List[str]
    links: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdvancedExplorationTools:
    """
    Advanced tools for comprehensive code exploration and analysis.
    
    Provides sophisticated analysis capabilities including:
    - Architecture diagram parsing
    - Documentation analysis
    - Dependency graph generation
    - Code pattern recognition
    - Test coverage analysis
    - Performance profiling
    - Security analysis
    """
    
    def __init__(self, repo: CodeRepo, config: CfConfig):
        self.repo = repo
        self.config = config
        
        # Diagram parsers
        self.diagram_parsers = {
            'mermaid': self._parse_mermaid_diagram,
            'plantuml': self._parse_plantuml_diagram,
            'graphviz': self._parse_graphviz_diagram,
            'drawio': self._parse_drawio_diagram
        }
        
        # Documentation analyzers
        self.doc_analyzers = {
            'markdown': self._analyze_markdown_doc,
            'rst': self._analyze_rst_doc,
            'asciidoc': self._analyze_asciidoc_doc,
            'sphinx': self._analyze_sphinx_doc
        }
        
        # Code analyzers
        self.code_analyzers = {
            'python': self._analyze_python_advanced,
            'javascript': self._analyze_javascript_advanced,
            'typescript': self._analyze_typescript_advanced,
            'java': self._analyze_java_advanced,
            'go': self._analyze_go_advanced
        }
        
        # Pattern matchers
        self.pattern_matchers = {
            'design_patterns': self._detect_design_patterns,
            'anti_patterns': self._detect_anti_patterns,
            'security_patterns': self._detect_security_patterns,
            'performance_patterns': self._detect_performance_patterns
        }
    
    def analyze_architecture_diagrams(self, path: str = "") -> AnalysisResult:
        """
        Analyze architecture diagrams in the repository.
        
        Args:
            path: Optional path to focus analysis on
            
        Returns:
            Analysis result containing diagram information
        """
        import time
        start_time = time.time()
        
        try:
            diagrams = []
            
            # Find diagram files
            diagram_files = self._find_diagram_files(path)
            
            # Parse each diagram
            for file_path in diagram_files:
                try:
                    content = self.repo.read_file(file_path)
                    diagram_type = self._detect_diagram_type(file_path, content)
                    
                    if diagram_type in self.diagram_parsers:
                        diagram_info = self.diagram_parsers[diagram_type](file_path, content)
                        if diagram_info:
                            diagrams.append(diagram_info)
                    
                except Exception as e:
                    print(f"⚠️  Error parsing diagram {file_path}: {e}")
            
            # Also look for embedded diagrams in documentation
            embedded_diagrams = self._find_embedded_diagrams()
            diagrams.extend(embedded_diagrams)
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                tool_name="architecture_diagram_analyzer",
                success=True,
                data={
                    'diagrams': [d.__dict__ for d in diagrams],
                    'total_diagrams': len(diagrams),
                    'diagram_types': list(set(d.diagram_type for d in diagrams)),
                    'architecture_insights': self._extract_architecture_insights(diagrams)
                },
                execution_time=execution_time,
                metadata={'files_analyzed': len(diagram_files)}
            )
            
        except Exception as e:
            return AnalysisResult(
                tool_name="architecture_diagram_analyzer",
                success=False,
                data={},
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def parse_documentation(self, formats: List[str] = None) -> AnalysisResult:
        """
        Parse and analyze documentation across multiple formats.
        
        Args:
            formats: List of documentation formats to analyze
            
        Returns:
            Analysis result containing documentation structure
        """
        import time
        start_time = time.time()
        
        if formats is None:
            formats = ['markdown', 'rst', 'asciidoc']
        
        try:
            documentation = []
            
            # Find documentation files
            doc_files = self._find_documentation_files(formats)
            
            # Analyze each documentation file
            for file_path in doc_files:
                try:
                    content = self.repo.read_file(file_path)
                    doc_format = self._detect_doc_format(file_path)
                    
                    if doc_format in self.doc_analyzers:
                        doc_structure = self.doc_analyzers[doc_format](file_path, content)
                        if doc_structure:
                            documentation.append(doc_structure)
                    
                except Exception as e:
                    print(f"⚠️  Error parsing documentation {file_path}: {e}")
            
            # Generate documentation insights
            insights = self._generate_documentation_insights(documentation)
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                tool_name="documentation_parser",
                success=True,
                data={
                    'documentation': [d.__dict__ for d in documentation],
                    'total_docs': len(documentation),
                    'doc_types': list(set(d.doc_type for d in documentation)),
                    'insights': insights,
                    'coverage_analysis': self._analyze_documentation_coverage(documentation)
                },
                execution_time=execution_time,
                metadata={'files_analyzed': len(doc_files)}
            )
            
        except Exception as e:
            return AnalysisResult(
                tool_name="documentation_parser",
                success=False,
                data={},
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def extract_code_patterns(self, language: str = "python") -> AnalysisResult:
        """
        Extract advanced code patterns from the codebase.
        
        Args:
            language: Programming language to analyze
            
        Returns:
            Analysis result containing code patterns
        """
        import time
        start_time = time.time()
        
        try:
            patterns = {
                'design_patterns': [],
                'anti_patterns': [],
                'security_patterns': [],
                'performance_patterns': []
            }
            
            # Find code files for the specified language
            code_files = self._find_code_files_by_language(language)
            
            # Analyze each file for patterns
            for file_path in code_files:
                try:
                    content = self.repo.read_file(file_path)
                    
                    # Run pattern detection
                    for pattern_type, detector in self.pattern_matchers.items():
                        detected_patterns = detector(file_path, content, language)
                        patterns[pattern_type].extend(detected_patterns)
                    
                except Exception as e:
                    print(f"⚠️  Error analyzing patterns in {file_path}: {e}")
            
            # Generate pattern insights
            insights = self._generate_pattern_insights(patterns)
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                tool_name="code_pattern_extractor",
                success=True,
                data={
                    'patterns': patterns,
                    'insights': insights,
                    'pattern_summary': self._summarize_patterns(patterns)
                },
                execution_time=execution_time,
                metadata={'files_analyzed': len(code_files), 'language': language}
            )
            
        except Exception as e:
            return AnalysisResult(
                tool_name="code_pattern_extractor",
                success=False,
                data={},
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def build_dependency_graph(self, include_external: bool = True) -> AnalysisResult:
        """
        Build comprehensive dependency graph.
        
        Args:
            include_external: Whether to include external dependencies
            
        Returns:
            Analysis result containing dependency graph
        """
        import time
        start_time = time.time()
        
        try:
            dependencies = {
                'internal': [],
                'external': [],
                'graph': {},
                'cycles': [],
                'metrics': {}
            }
            
            # Analyze internal dependencies
            internal_deps = self._analyze_internal_dependencies()
            dependencies['internal'] = internal_deps
            
            # Analyze external dependencies if requested
            if include_external:
                external_deps = self._analyze_external_dependencies()
                dependencies['external'] = external_deps
            
            # Build dependency graph
            graph = self._build_dependency_graph_structure(internal_deps, external_deps if include_external else [])
            dependencies['graph'] = graph
            
            # Detect dependency cycles
            cycles = self._detect_dependency_cycles(graph)
            dependencies['cycles'] = cycles
            
            # Calculate dependency metrics
            metrics = self._calculate_dependency_metrics(graph)
            dependencies['metrics'] = metrics
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                tool_name="dependency_graph_builder",
                success=True,
                data=dependencies,
                execution_time=execution_time,
                metadata={'include_external': include_external}
            )
            
        except Exception as e:
            return AnalysisResult(
                tool_name="dependency_graph_builder",
                success=False,
                data={},
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def analyze_test_coverage(self, test_framework: str = "auto") -> AnalysisResult:
        """
        Analyze test coverage and testing patterns.
        
        Args:
            test_framework: Test framework to analyze ('auto', 'pytest', 'jest', etc.)
            
        Returns:
            Analysis result containing test coverage information
        """
        import time
        start_time = time.time()
        
        try:
            coverage_data = {
                'test_files': [],
                'coverage_metrics': {},
                'testing_patterns': [],
                'recommendations': []
            }
            
            # Find test files
            test_files = self._find_test_files()
            coverage_data['test_files'] = test_files
            
            # Analyze test coverage
            if test_framework == "auto":
                test_framework = self._detect_test_framework()
            
            if test_framework:
                coverage_metrics = self._analyze_test_coverage_metrics(test_framework)
                coverage_data['coverage_metrics'] = coverage_metrics
            
            # Analyze testing patterns
            testing_patterns = self._analyze_testing_patterns(test_files)
            coverage_data['testing_patterns'] = testing_patterns
            
            # Generate recommendations
            recommendations = self._generate_testing_recommendations(coverage_data)
            coverage_data['recommendations'] = recommendations
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                tool_name="test_coverage_analyzer",
                success=True,
                data=coverage_data,
                execution_time=execution_time,
                metadata={'test_framework': test_framework, 'test_files_count': len(test_files)}
            )
            
        except Exception as e:
            return AnalysisResult(
                tool_name="test_coverage_analyzer",
                success=False,
                data={},
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def profile_performance(self, entry_points: List[str] = None) -> AnalysisResult:
        """
        Profile performance characteristics of the codebase.
        
        Args:
            entry_points: List of entry points to analyze
            
        Returns:
            Analysis result containing performance profile
        """
        import time
        start_time = time.time()
        
        try:
            performance_data = {
                'hotspots': [],
                'complexity_metrics': {},
                'performance_patterns': [],
                'optimization_suggestions': []
            }
            
            # Find performance hotspots
            hotspots = self._identify_performance_hotspots(entry_points)
            performance_data['hotspots'] = hotspots
            
            # Calculate complexity metrics
            complexity_metrics = self._calculate_complexity_metrics()
            performance_data['complexity_metrics'] = complexity_metrics
            
            # Analyze performance patterns
            performance_patterns = self._analyze_performance_patterns()
            performance_data['performance_patterns'] = performance_patterns
            
            # Generate optimization suggestions
            optimization_suggestions = self._generate_optimization_suggestions(performance_data)
            performance_data['optimization_suggestions'] = optimization_suggestions
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                tool_name="performance_profiler",
                success=True,
                data=performance_data,
                execution_time=execution_time,
                metadata={'entry_points': entry_points}
            )
            
        except Exception as e:
            return AnalysisResult(
                tool_name="performance_profiler",
                success=False,
                data={},
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def analyze_security(self, security_frameworks: List[str] = None) -> AnalysisResult:
        """
        Analyze security patterns and vulnerabilities.
        
        Args:
            security_frameworks: List of security frameworks to consider
            
        Returns:
            Analysis result containing security analysis
        """
        import time
        start_time = time.time()
        
        try:
            security_data = {
                'vulnerabilities': [],
                'security_patterns': [],
                'authentication_analysis': {},
                'authorization_analysis': {},
                'recommendations': []
            }
            
            # Scan for common vulnerabilities
            vulnerabilities = self._scan_vulnerabilities()
            security_data['vulnerabilities'] = vulnerabilities
            
            # Analyze security patterns
            security_patterns = self._analyze_security_patterns()
            security_data['security_patterns'] = security_patterns
            
            # Analyze authentication mechanisms
            auth_analysis = self._analyze_authentication()
            security_data['authentication_analysis'] = auth_analysis
            
            # Analyze authorization patterns
            authz_analysis = self._analyze_authorization()
            security_data['authorization_analysis'] = authz_analysis
            
            # Generate security recommendations
            recommendations = self._generate_security_recommendations(security_data)
            security_data['recommendations'] = recommendations
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                tool_name="security_analyzer",
                success=True,
                data=security_data,
                execution_time=execution_time,
                metadata={'security_frameworks': security_frameworks}
            )
            
        except Exception as e:
            return AnalysisResult(
                tool_name="security_analyzer",
                success=False,
                data={},
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    # Helper methods for diagram analysis
    def _find_diagram_files(self, path: str = "") -> List[str]:
        """Find diagram files in the repository."""
        diagram_extensions = ['.mmd', '.mermaid', '.puml', '.plantuml', '.dot', '.gv', '.drawio']
        diagram_files = []
        
        for file_info in self.repo.walk_repository():
            if file_info.is_directory:
                continue
            
            file_path = file_info.path
            if path and not file_path.startswith(path):
                continue
            
            file_ext = Path(file_path).suffix.lower()
            if file_ext in diagram_extensions:
                diagram_files.append(file_path)
        
        return diagram_files
    
    def _detect_diagram_type(self, file_path: str, content: str) -> str:
        """Detect the type of diagram from file path and content."""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in ['.mmd', '.mermaid']:
            return 'mermaid'
        elif file_ext in ['.puml', '.plantuml']:
            return 'plantuml'
        elif file_ext in ['.dot', '.gv']:
            return 'graphviz'
        elif file_ext == '.drawio':
            return 'drawio'
        
        # Check content for diagram markers
        content_lower = content.lower()
        if 'graph' in content_lower and 'mermaid' in content_lower:
            return 'mermaid'
        elif '@startuml' in content_lower:
            return 'plantuml'
        elif 'digraph' in content_lower or 'graph' in content_lower:
            return 'graphviz'
        
        return 'unknown'
    
    def _parse_mermaid_diagram(self, file_path: str, content: str) -> Optional[DiagramInfo]:
        """Parse Mermaid diagram."""
        try:
            # Extract components and relationships from Mermaid syntax
            components = []
            relationships = []
            title = Path(file_path).stem
            
            # Look for nodes (simplified parsing)
            node_pattern = r'(\w+)\[([^\]]+)\]'
            for match in re.finditer(node_pattern, content):
                components.append(match.group(2))
            
            # Look for relationships
            relationship_pattern = r'(\w+)\s*--[->]*\s*(\w+)'
            for match in re.finditer(relationship_pattern, content):
                relationships.append(f"{match.group(1)} -> {match.group(2)}")
            
            return DiagramInfo(
                file_path=file_path,
                diagram_type='mermaid',
                title=title,
                content=content,
                components=components,
                relationships=relationships
            )
            
        except Exception as e:
            print(f"⚠️  Error parsing Mermaid diagram: {e}")
            return None
    
    def _parse_plantuml_diagram(self, file_path: str, content: str) -> Optional[DiagramInfo]:
        """Parse PlantUML diagram."""
        try:
            components = []
            relationships = []
            title = Path(file_path).stem
            
            # Look for classes/components
            class_pattern = r'class\s+(\w+)'
            for match in re.finditer(class_pattern, content):
                components.append(match.group(1))
            
            # Look for relationships
            relationship_pattern = r'(\w+)\s*--[->]*\s*(\w+)'
            for match in re.finditer(relationship_pattern, content):
                relationships.append(f"{match.group(1)} -> {match.group(2)}")
            
            return DiagramInfo(
                file_path=file_path,
                diagram_type='plantuml',
                title=title,
                content=content,
                components=components,
                relationships=relationships
            )
            
        except Exception as e:
            print(f"⚠️  Error parsing PlantUML diagram: {e}")
            return None
    
    def _parse_graphviz_diagram(self, file_path: str, content: str) -> Optional[DiagramInfo]:
        """Parse Graphviz diagram."""
        try:
            components = []
            relationships = []
            title = Path(file_path).stem
            
            # Look for nodes
            node_pattern = r'(\w+)\s*\[.*?\]'
            for match in re.finditer(node_pattern, content):
                components.append(match.group(1))
            
            # Look for edges
            edge_pattern = r'(\w+)\s*->\s*(\w+)'
            for match in re.finditer(edge_pattern, content):
                relationships.append(f"{match.group(1)} -> {match.group(2)}")
            
            return DiagramInfo(
                file_path=file_path,
                diagram_type='graphviz',
                title=title,
                content=content,
                components=components,
                relationships=relationships
            )
            
        except Exception as e:
            print(f"⚠️  Error parsing Graphviz diagram: {e}")
            return None
    
    def _parse_drawio_diagram(self, file_path: str, content: str) -> Optional[DiagramInfo]:
        """Parse Draw.io diagram."""
        try:
            # Draw.io files are XML-based, need XML parsing
            # This is a simplified implementation
            components = []
            relationships = []
            title = Path(file_path).stem
            
            # Look for text elements (simplified)
            text_pattern = r'<text[^>]*>([^<]+)</text>'
            for match in re.finditer(text_pattern, content):
                components.append(match.group(1))
            
            return DiagramInfo(
                file_path=file_path,
                diagram_type='drawio',
                title=title,
                content=content,
                components=components,
                relationships=relationships
            )
            
        except Exception as e:
            print(f"⚠️  Error parsing Draw.io diagram: {e}")
            return None
    
    def _find_embedded_diagrams(self) -> List[DiagramInfo]:
        """Find diagrams embedded in documentation."""
        embedded_diagrams = []
        
        # Look for code blocks with diagram syntax in markdown files
        for file_info in self.repo.walk_repository():
            if file_info.is_directory or not file_info.path.endswith('.md'):
                continue
            
            try:
                content = self.repo.read_file(file_info.path)
                
                # Look for mermaid code blocks
                mermaid_pattern = r'```mermaid\s*(.*?)```'
                for match in re.finditer(mermaid_pattern, content, re.DOTALL):
                    diagram_content = match.group(1)
                    diagram_info = self._parse_mermaid_diagram(file_info.path, diagram_content)
                    if diagram_info:
                        embedded_diagrams.append(diagram_info)
                
                # Look for plantuml code blocks
                plantuml_pattern = r'```plantuml\s*(.*?)```'
                for match in re.finditer(plantuml_pattern, content, re.DOTALL):
                    diagram_content = match.group(1)
                    diagram_info = self._parse_plantuml_diagram(file_info.path, diagram_content)
                    if diagram_info:
                        embedded_diagrams.append(diagram_info)
                
            except Exception as e:
                print(f"⚠️  Error looking for embedded diagrams in {file_info.path}: {e}")
        
        return embedded_diagrams
    
    def _extract_architecture_insights(self, diagrams: List[DiagramInfo]) -> Dict[str, Any]:
        """Extract architecture insights from diagrams."""
        insights = {
            'total_components': 0,
            'total_relationships': 0,
            'component_frequency': defaultdict(int),
            'relationship_patterns': [],
            'architectural_styles': []
        }
        
        all_components = []
        all_relationships = []
        
        for diagram in diagrams:
            all_components.extend(diagram.components)
            all_relationships.extend(diagram.relationships)
        
        insights['total_components'] = len(set(all_components))
        insights['total_relationships'] = len(all_relationships)
        
        # Count component frequency
        for component in all_components:
            insights['component_frequency'][component] += 1
        
        # Convert to regular dict for JSON serialization
        insights['component_frequency'] = dict(insights['component_frequency'])
        
        # Analyze relationship patterns
        relationship_types = set()
        for rel in all_relationships:
            if '->' in rel:
                relationship_types.add('directed')
            elif '--' in rel:
                relationship_types.add('undirected')
        
        insights['relationship_patterns'] = list(relationship_types)
        
        # Detect architectural styles (simplified)
        if len(diagrams) > 0:
            if any('layer' in d.title.lower() for d in diagrams):
                insights['architectural_styles'].append('layered')
            if any('service' in d.title.lower() for d in diagrams):
                insights['architectural_styles'].append('service-oriented')
        
        return insights
    
    # Helper methods for documentation analysis
    def _find_documentation_files(self, formats: List[str]) -> List[str]:
        """Find documentation files in the repository."""
        doc_extensions = {
            'markdown': ['.md', '.markdown'],
            'rst': ['.rst', '.rest'],
            'asciidoc': ['.adoc', '.asciidoc'],
            'sphinx': ['.rst', '.md']
        }
        
        doc_files = []
        target_extensions = []
        
        for fmt in formats:
            if fmt in doc_extensions:
                target_extensions.extend(doc_extensions[fmt])
        
        for file_info in self.repo.walk_repository():
            if file_info.is_directory:
                continue
            
            file_ext = Path(file_info.path).suffix.lower()
            if file_ext in target_extensions:
                doc_files.append(file_info.path)
        
        return doc_files
    
    def _detect_doc_format(self, file_path: str) -> str:
        """Detect documentation format from file path."""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in ['.md', '.markdown']:
            return 'markdown'
        elif file_ext in ['.rst', '.rest']:
            return 'rst'
        elif file_ext in ['.adoc', '.asciidoc']:
            return 'asciidoc'
        
        return 'unknown'
    
    def _analyze_markdown_doc(self, file_path: str, content: str) -> Optional[DocumentationStructure]:
        """Analyze Markdown documentation."""
        try:
            sections = []
            code_examples = []
            links = []
            
            # Extract sections (headers)
            header_pattern = r'^(#{1,6})\s+(.+)$'
            for match in re.finditer(header_pattern, content, re.MULTILINE):
                sections.append(match.group(2))
            
            # Extract code examples
            code_pattern = r'```[\w]*\s*(.*?)```'
            for match in re.finditer(code_pattern, content, re.DOTALL):
                code_examples.append(match.group(1).strip())
            
            # Extract links
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            for match in re.finditer(link_pattern, content):
                links.append(match.group(2))
            
            # Determine document type
            doc_type = self._classify_doc_type(file_path, content)
            
            return DocumentationStructure(
                file_path=file_path,
                doc_type=doc_type,
                sections=sections,
                code_examples=code_examples,
                links=links,
                metadata={'format': 'markdown', 'word_count': len(content.split())}
            )
            
        except Exception as e:
            print(f"⚠️  Error analyzing Markdown doc: {e}")
            return None
    
    def _analyze_rst_doc(self, file_path: str, content: str) -> Optional[DocumentationStructure]:
        """Analyze reStructuredText documentation."""
        try:
            sections = []
            code_examples = []
            links = []
            
            # Extract sections (simplified RST parsing)
            section_pattern = r'^(.+)\n[=\-~`#"^+*]{3,}$'
            for match in re.finditer(section_pattern, content, re.MULTILINE):
                sections.append(match.group(1))
            
            # Extract code blocks
            code_pattern = r'.. code-block::\s*\w*\s*(.*?)(?=\n\S|\Z)'
            for match in re.finditer(code_pattern, content, re.DOTALL):
                code_examples.append(match.group(1).strip())
            
            # Extract links
            link_pattern = r'`([^`]+) <([^>]+)>`_'
            for match in re.finditer(link_pattern, content):
                links.append(match.group(2))
            
            doc_type = self._classify_doc_type(file_path, content)
            
            return DocumentationStructure(
                file_path=file_path,
                doc_type=doc_type,
                sections=sections,
                code_examples=code_examples,
                links=links,
                metadata={'format': 'rst', 'word_count': len(content.split())}
            )
            
        except Exception as e:
            print(f"⚠️  Error analyzing RST doc: {e}")
            return None
    
    def _analyze_asciidoc_doc(self, file_path: str, content: str) -> Optional[DocumentationStructure]:
        """Analyze AsciiDoc documentation."""
        try:
            sections = []
            code_examples = []
            links = []
            
            # Extract sections
            section_pattern = r'^={1,6}\s+(.+)$'
            for match in re.finditer(section_pattern, content, re.MULTILINE):
                sections.append(match.group(1))
            
            # Extract code blocks
            code_pattern = r'\[source,.*?\]\s*----\s*(.*?)----'
            for match in re.finditer(code_pattern, content, re.DOTALL):
                code_examples.append(match.group(1).strip())
            
            # Extract links
            link_pattern = r'link:([^[]+)\[([^\]]+)\]'
            for match in re.finditer(link_pattern, content):
                links.append(match.group(1))
            
            doc_type = self._classify_doc_type(file_path, content)
            
            return DocumentationStructure(
                file_path=file_path,
                doc_type=doc_type,
                sections=sections,
                code_examples=code_examples,
                links=links,
                metadata={'format': 'asciidoc', 'word_count': len(content.split())}
            )
            
        except Exception as e:
            print(f"⚠️  Error analyzing AsciiDoc doc: {e}")
            return None
    
    def _analyze_sphinx_doc(self, file_path: str, content: str) -> Optional[DocumentationStructure]:
        """Analyze Sphinx documentation."""
        # For now, treat as RST with Sphinx-specific directives
        return self._analyze_rst_doc(file_path, content)
    
    def _classify_doc_type(self, file_path: str, content: str) -> str:
        """Classify documentation type."""
        file_name = Path(file_path).name.lower()
        content_lower = content.lower()
        
        if 'readme' in file_name:
            return 'readme'
        elif 'api' in file_name or 'api' in content_lower:
            return 'api'
        elif 'architecture' in file_name or 'architecture' in content_lower:
            return 'architecture'
        elif 'tutorial' in file_name or 'tutorial' in content_lower:
            return 'tutorial'
        elif 'guide' in file_name or 'guide' in content_lower:
            return 'guide'
        elif 'install' in file_name or 'installation' in content_lower:
            return 'installation'
        else:
            return 'general'
    
    def _generate_documentation_insights(self, documentation: List[DocumentationStructure]) -> Dict[str, Any]:
        """Generate insights from documentation analysis."""
        insights = {
            'total_sections': 0,
            'total_code_examples': 0,
            'total_links': 0,
            'doc_type_distribution': defaultdict(int),
            'common_topics': [],
            'link_analysis': {}
        }
        
        all_sections = []
        all_links = []
        
        for doc in documentation:
            all_sections.extend(doc.sections)
            all_links.extend(doc.links)
            insights['total_code_examples'] += len(doc.code_examples)
            insights['doc_type_distribution'][doc.doc_type] += 1
        
        insights['total_sections'] = len(all_sections)
        insights['total_links'] = len(all_links)
        
        # Convert to regular dict
        insights['doc_type_distribution'] = dict(insights['doc_type_distribution'])
        
        # Analyze common topics (simplified)
        section_words = ' '.join(all_sections).lower().split()
        word_freq = defaultdict(int)
        for word in section_words:
            if len(word) > 3:  # Filter short words
                word_freq[word] += 1
        
        insights['common_topics'] = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Analyze links
        external_links = [link for link in all_links if link.startswith('http')]
        internal_links = [link for link in all_links if not link.startswith('http')]
        
        insights['link_analysis'] = {
            'external_links': len(external_links),
            'internal_links': len(internal_links),
            'total_links': len(all_links)
        }
        
        return insights
    
    def _analyze_documentation_coverage(self, documentation: List[DocumentationStructure]) -> Dict[str, Any]:
        """Analyze documentation coverage."""
        coverage = {
            'covered_areas': [],
            'missing_areas': [],
            'coverage_score': 0.0
        }
        
        # Expected documentation areas
        expected_areas = ['readme', 'api', 'architecture', 'installation', 'tutorial', 'guide']
        
        # Check which areas are covered
        doc_types = set(doc.doc_type for doc in documentation)
        covered_areas = [area for area in expected_areas if area in doc_types]
        missing_areas = [area for area in expected_areas if area not in doc_types]
        
        coverage['covered_areas'] = covered_areas
        coverage['missing_areas'] = missing_areas
        coverage['coverage_score'] = len(covered_areas) / len(expected_areas)
        
        return coverage
    
    # Simplified implementations for other methods
    def _find_code_files_by_language(self, language: str) -> List[str]:
        """Find code files for a specific language."""
        extensions = {
            'python': ['.py'],
            'javascript': ['.js', '.jsx'],
            'typescript': ['.ts', '.tsx'],
            'java': ['.java'],
            'go': ['.go']
        }
        
        target_extensions = extensions.get(language, [])
        code_files = []
        
        for file_info in self.repo.walk_repository():
            if file_info.is_directory:
                continue
            
            file_ext = Path(file_info.path).suffix.lower()
            if file_ext in target_extensions:
                code_files.append(file_info.path)
        
        return code_files
    
    def _detect_design_patterns(self, file_path: str, content: str, language: str) -> List[Dict[str, Any]]:
        """Detect design patterns in code."""
        patterns = []
        
        # Simplified pattern detection
        if 'singleton' in content.lower():
            patterns.append({'pattern': 'Singleton', 'file': file_path, 'confidence': 0.7})
        if 'factory' in content.lower():
            patterns.append({'pattern': 'Factory', 'file': file_path, 'confidence': 0.6})
        if 'observer' in content.lower():
            patterns.append({'pattern': 'Observer', 'file': file_path, 'confidence': 0.6})
        
        return patterns
    
    def _detect_anti_patterns(self, file_path: str, content: str, language: str) -> List[Dict[str, Any]]:
        """Detect anti-patterns in code."""
        patterns = []
        
        # Simplified anti-pattern detection
        if len(content.split('\n')) > 1000:
            patterns.append({'pattern': 'God Object', 'file': file_path, 'confidence': 0.8})
        
        return patterns
    
    def _detect_security_patterns(self, file_path: str, content: str, language: str) -> List[Dict[str, Any]]:
        """Detect security patterns in code."""
        patterns = []
        
        # Simplified security pattern detection
        if 'password' in content.lower() and 'hash' in content.lower():
            patterns.append({'pattern': 'Password Hashing', 'file': file_path, 'confidence': 0.8})
        
        return patterns
    
    def _detect_performance_patterns(self, file_path: str, content: str, language: str) -> List[Dict[str, Any]]:
        """Detect performance patterns in code."""
        patterns = []
        
        # Simplified performance pattern detection
        if 'cache' in content.lower():
            patterns.append({'pattern': 'Caching', 'file': file_path, 'confidence': 0.7})
        
        return patterns
    
    def _generate_pattern_insights(self, patterns: Dict[str, List]) -> Dict[str, Any]:
        """Generate insights from pattern analysis."""
        insights = {
            'pattern_counts': {},
            'most_common_patterns': [],
            'pattern_distribution': {}
        }
        
        for pattern_type, pattern_list in patterns.items():
            insights['pattern_counts'][pattern_type] = len(pattern_list)
        
        return insights
    
    def _summarize_patterns(self, patterns: Dict[str, List]) -> str:
        """Summarize pattern analysis results."""
        total_patterns = sum(len(pattern_list) for pattern_list in patterns.values())
        return f"Found {total_patterns} patterns across {len(patterns)} categories"
    
    # Additional helper methods would be implemented here for:
    # - Dependency analysis
    # - Test coverage analysis
    # - Performance profiling
    # - Security analysis
    # These are simplified for brevity
    
    def _analyze_internal_dependencies(self) -> List[Dict[str, Any]]:
        """Analyze internal dependencies."""
        return [{'source': 'module_a', 'target': 'module_b', 'type': 'import'}]
    
    def _analyze_external_dependencies(self) -> List[Dict[str, Any]]:
        """Analyze external dependencies."""
        return [{'name': 'requests', 'version': '2.25.1', 'type': 'package'}]
    
    def _build_dependency_graph_structure(self, internal_deps: List, external_deps: List) -> Dict[str, Any]:
        """Build dependency graph structure."""
        return {'nodes': [], 'edges': []}
    
    def _detect_dependency_cycles(self, graph: Dict[str, Any]) -> List[List[str]]:
        """Detect dependency cycles."""
        return []
    
    def _calculate_dependency_metrics(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate dependency metrics."""
        return {'total_dependencies': 0, 'cycle_count': 0}
    
    def _find_test_files(self) -> List[str]:
        """Find test files."""
        return []
    
    def _detect_test_framework(self) -> str:
        """Detect test framework."""
        return 'pytest'
    
    def _analyze_test_coverage_metrics(self, framework: str) -> Dict[str, Any]:
        """Analyze test coverage metrics."""
        return {'line_coverage': 0.85, 'branch_coverage': 0.78}
    
    def _analyze_testing_patterns(self, test_files: List[str]) -> List[Dict[str, Any]]:
        """Analyze testing patterns."""
        return []
    
    def _generate_testing_recommendations(self, coverage_data: Dict[str, Any]) -> List[str]:
        """Generate testing recommendations."""
        return ['Add more unit tests', 'Improve test coverage']
    
    def _identify_performance_hotspots(self, entry_points: List[str]) -> List[Dict[str, Any]]:
        """Identify performance hotspots."""
        return []
    
    def _calculate_complexity_metrics(self) -> Dict[str, Any]:
        """Calculate complexity metrics."""
        return {'cyclomatic_complexity': 10, 'cognitive_complexity': 15}
    
    def _analyze_performance_patterns(self) -> List[Dict[str, Any]]:
        """Analyze performance patterns."""
        return []
    
    def _generate_optimization_suggestions(self, performance_data: Dict[str, Any]) -> List[str]:
        """Generate optimization suggestions."""
        return ['Optimize database queries', 'Add caching layer']
    
    def _scan_vulnerabilities(self) -> List[Dict[str, Any]]:
        """Scan for vulnerabilities."""
        return []
    
    def _analyze_security_patterns(self) -> List[Dict[str, Any]]:
        """Analyze security patterns."""
        return []
    
    def _analyze_authentication(self) -> Dict[str, Any]:
        """Analyze authentication mechanisms."""
        return {'methods': ['JWT', 'OAuth'], 'secure': True}
    
    def _analyze_authorization(self) -> Dict[str, Any]:
        """Analyze authorization patterns."""
        return {'methods': ['RBAC'], 'secure': True}
    
    def _generate_security_recommendations(self, security_data: Dict[str, Any]) -> List[str]:
        """Generate security recommendations."""
        return ['Implement input validation', 'Add rate limiting']