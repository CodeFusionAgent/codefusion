"""
ReAct Documentation Agent for comprehensive documentation analysis.

This agent uses the ReAct pattern to systematically explore and analyze documentation
through reasoning, acting with tools, and observing results.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..aci.repo import CodeRepo
from ..config import CfConfig
from ..core.react_agent import ReActAgent, ReActAction, ActionType


class ReActDocumentationAgent(ReActAgent):
    """
    Documentation agent that uses ReAct pattern for systematic documentation analysis.
    
    ReAct Loop:
    1. Reason: Analyze what documentation to explore next
    2. Act: Use tools to scan, read, or search documentation
    3. Observe: Reflect on findings and plan next steps
    """
    
    def __init__(self, repo: CodeRepo, config: CfConfig):
        super().__init__(repo, config, "DocumentationAgent")
        
        # Documentation-specific patterns
        self.doc_patterns = {
            'readme': ['README.md', 'readme.md', 'README.rst', 'readme.rst', 'README.txt'],
            'api_docs': ['API.md', 'api.md', 'docs/api.md', 'docs/API.md'],
            'architecture': ['ARCHITECTURE.md', 'architecture.md', 'docs/architecture.md'],
            'contributing': ['CONTRIBUTING.md', 'contributing.md', 'CONTRIBUTE.md'],
            'changelog': ['CHANGELOG.md', 'changelog.md', 'CHANGES.md', 'HISTORY.md'],
            'license': ['LICENSE', 'LICENSE.md', 'license.md', 'LICENSE.txt'],
            'install': ['INSTALL.md', 'install.md', 'INSTALLATION.md', 'installation.md'],
            'usage': ['USAGE.md', 'usage.md', 'docs/usage.md', 'docs/USAGE.md'],
            'examples': ['EXAMPLES.md', 'examples.md', 'docs/examples.md']
        }
        
        # Documentation analysis state
        self.found_docs = []
        self.analyzed_docs = {}
        self.documentation_insights = []
        self.key_sections = []
        
    def scan_documentation(self, description: str) -> Dict[str, Any]:
        """
        Main entry point for documentation scanning using ReAct pattern.
        
        Args:
            description: Description of what to focus on during scanning
            
        Returns:
            Comprehensive documentation analysis results
        """
        goal = f"Analyze documentation for: {description}"
        return self.execute_react_loop(goal, max_iterations=15)
    
    def reason(self) -> str:
        """
        Reasoning phase: Determine what documentation action to take next.
        
        Returns:
            Reasoning about next action to take
        """
        current_context = self.state.current_context
        iteration = self.state.iteration
        
        # First iteration: Start with directory scan to find documentation
        if iteration == 1:
            return "I should start by scanning the repository structure to identify documentation files. This will give me an overview of what documentation exists."
        
        # If we haven't found documentation files yet, scan more thoroughly
        if not self.found_docs and iteration <= 3:
            return "I haven't found documentation files yet. Let me scan more directories and look for common documentation patterns."
        
        # If we have documentation files but haven't analyzed them
        if self.found_docs and not self.analyzed_docs:
            return f"I found {len(self.found_docs)} documentation files. Now I should read and analyze the most important ones, starting with README files."
        
        # If we have some analysis but need more depth
        if self.analyzed_docs and len(self.analyzed_docs) < 3:
            return "I've analyzed some documentation but need to dive deeper. Let me search for specific patterns and sections relevant to the goal."
        
        # If we have good coverage, focus on synthesis
        if len(self.analyzed_docs) >= 3:
            return "I have analyzed multiple documentation files. Now I should synthesize the information and look for specific details related to the goal."
        
        # Default reasoning
        return "I should continue analyzing documentation systematically, focusing on files that are most relevant to the goal."
    
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
                description="Scan repository for documentation files",
                parameters={'directory': '.', 'max_depth': 3},
                expected_outcome="Find documentation files and directory structure"
            )
        
        # Find documentation files if not found yet
        if not self.found_docs and iteration <= 4:
            return ReActAction(
                action_type=ActionType.LIST_FILES,
                description="List files to find documentation",
                parameters={'pattern': '.md', 'directory': '.'},
                expected_outcome="Identify markdown and documentation files"
            )
        
        # Read high-priority documentation files
        if self.found_docs and not self.analyzed_docs:
            # Prioritize README files
            readme_files = [f for f in self.found_docs if 'readme' in f.lower()]
            if readme_files:
                return ReActAction(
                    action_type=ActionType.READ_FILE,
                    description=f"Read README file: {readme_files[0]}",
                    parameters={'file_path': readme_files[0], 'max_lines': 200},
                    expected_outcome="Understand project overview and main documentation"
                )
            else:
                return ReActAction(
                    action_type=ActionType.READ_FILE,
                    description=f"Read documentation file: {self.found_docs[0]}",
                    parameters={'file_path': self.found_docs[0], 'max_lines': 200},
                    expected_outcome="Understand documentation content"
                )
        
        # Search for specific patterns related to the goal
        if "api" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for API documentation patterns",
                parameters={'pattern': 'api', 'file_types': ['.md', '.rst', '.txt'], 'max_results': 10},
                expected_outcome="Find API-related documentation"
            )
        
        elif "architecture" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for architecture documentation",
                parameters={'pattern': 'architecture', 'file_types': ['.md', '.rst', '.txt'], 'max_results': 10},
                expected_outcome="Find architecture documentation"
            )
        
        elif "install" in self.state.goal.lower() or "setup" in self.state.goal.lower():
            return ReActAction(
                action_type=ActionType.SEARCH_FILES,
                description="Search for installation/setup documentation",
                parameters={'pattern': 'install', 'file_types': ['.md', '.rst', '.txt'], 'max_results': 10},
                expected_outcome="Find installation and setup instructions"
            )
        
        # Default: Use LLM reasoning to determine next step
        return ReActAction(
            action_type=ActionType.LLM_REASONING,
            description="Use LLM to determine next documentation analysis step",
            parameters={
                'context': str(self.state.current_context),
                'question': f"What should I analyze next for: {self.state.goal}?"
            },
            expected_outcome="Get guidance on next analysis step"
        )
    
    def observe(self, observation):
        """
        Enhanced observation phase for documentation analysis.
        
        Args:
            observation: Observation from the action
        """
        super().observe(observation)
        
        # Process documentation-specific observations
        if observation.success and observation.result:
            result = observation.result
            
            # If we scanned a directory, extract documentation files
            if isinstance(result, dict) and 'contents' in result:
                for item in result['contents']:
                    if not item['is_directory'] and self._is_documentation_file(item['path']):
                        if item['path'] not in self.found_docs:
                            self.found_docs.append(item['path'])
                            self.logger.info(f"📄 Found documentation: {item['path']}")
            
            # If we listed files, filter for documentation
            elif isinstance(result, dict) and 'files' in result:
                for file_info in result['files']:
                    if self._is_documentation_file(file_info['path']):
                        if file_info['path'] not in self.found_docs:
                            self.found_docs.append(file_info['path'])
                            self.logger.info(f"📄 Found documentation: {file_info['path']}")
            
            # If we read a file, analyze its content
            elif isinstance(result, dict) and 'content' in result:
                file_path = result['file_path']
                content = result['content']
                
                # Analyze the documentation content
                analysis = self._analyze_documentation_content(file_path, content)
                self.analyzed_docs[file_path] = analysis
                
                # Extract key insights
                insights = self._extract_insights(file_path, content, analysis)
                self.documentation_insights.extend(insights)
                
                self.logger.info(f"📋 Analyzed documentation: {file_path}")
            
            # If we searched files, process the results
            elif isinstance(result, dict) and 'results' in result:
                for search_result in result['results']:
                    file_path = search_result['file_path']
                    if file_path not in self.found_docs:
                        self.found_docs.append(file_path)
                        self.logger.info(f"🔍 Found through search: {file_path}")
    
    def _is_documentation_file(self, file_path: str) -> bool:
        """Check if a file is likely documentation."""
        path_lower = file_path.lower()
        
        # Check against known documentation patterns
        for doc_type, patterns in self.doc_patterns.items():
            for pattern in patterns:
                if pattern.lower() in path_lower:
                    return True
        
        # Check file extensions
        doc_extensions = ['.md', '.rst', '.txt', '.adoc', '.wiki']
        if any(path_lower.endswith(ext) for ext in doc_extensions):
            return True
        
        # Check for documentation keywords in path
        doc_keywords = ['doc', 'readme', 'manual', 'guide', 'help']
        if any(keyword in path_lower for keyword in doc_keywords):
            return True
        
        return False
    
    def _analyze_documentation_content(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze documentation content and extract structure."""
        lines = content.split('\n')
        
        # Extract headings
        headings = []
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.strip('#').strip()
                headings.append({
                    'level': level,
                    'title': title,
                    'line_num': i + 1
                })
        
        # Classify content type
        content_type = self._classify_documentation_type(file_path, content)
        
        # Extract code blocks
        code_blocks = re.findall(r'```(\\w+)?\\s*(.*?)```', content, re.DOTALL)
        
        # Extract links
        links = re.findall(r'\\[(.*?)\\]\\((.*?)\\)', content)
        
        # Calculate metrics
        word_count = len(content.split())
        line_count = len(lines)
        
        return {
            'file_path': file_path,
            'content_type': content_type,
            'headings': headings,
            'code_blocks': len(code_blocks),
            'links': links,
            'word_count': word_count,
            'line_count': line_count,
            'has_installation': 'install' in content.lower(),
            'has_usage': 'usage' in content.lower() or 'example' in content.lower(),
            'has_api': 'api' in content.lower(),
            'has_architecture': 'architecture' in content.lower() or 'design' in content.lower()
        }
    
    def _classify_documentation_type(self, file_path: str, content: str) -> str:
        """Classify the type of documentation."""
        path_lower = file_path.lower()
        content_lower = content.lower()
        
        if 'readme' in path_lower:
            return 'readme'
        elif 'api' in path_lower or 'api' in content_lower:
            return 'api'
        elif 'architecture' in path_lower or 'architecture' in content_lower:
            return 'architecture'
        elif 'install' in path_lower or 'setup' in content_lower:
            return 'installation'
        elif 'usage' in path_lower or 'example' in content_lower:
            return 'usage'
        elif 'contributing' in path_lower:
            return 'contributing'
        elif 'changelog' in path_lower:
            return 'changelog'
        elif 'license' in path_lower:
            return 'license'
        else:
            return 'general'
    
    def _extract_insights(self, file_path: str, content: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key insights from documentation content."""
        insights = []
        
        # Insight about content type
        insights.append({
            'type': 'content_classification',
            'content': f"This is {analysis['content_type']} documentation",
            'confidence': 0.9,
            'source': file_path
        })
        
        # Insight about structure
        if analysis['headings']:
            insights.append({
                'type': 'structure',
                'content': f"Well-structured with {len(analysis['headings'])} sections",
                'confidence': 0.8,
                'source': file_path
            })
        
        # Insight about technical content
        if analysis['code_blocks'] > 0:
            insights.append({
                'type': 'technical_content',
                'content': f"Contains {analysis['code_blocks']} code examples",
                'confidence': 0.9,
                'source': file_path
            })
        
        # Insight about completeness
        completeness_score = 0
        if analysis['has_installation']: completeness_score += 1
        if analysis['has_usage']: completeness_score += 1
        if analysis['has_api']: completeness_score += 1
        if analysis['has_architecture']: completeness_score += 1
        
        insights.append({
            'type': 'completeness',
            'content': f"Documentation completeness score: {completeness_score}/4",
            'confidence': 0.7,
            'source': file_path
        })
        
        return insights
    
    def _generate_summary(self) -> str:
        """Generate a comprehensive summary of documentation analysis."""
        if not self.found_docs:
            return "No documentation files found in the repository."
        
        summary = f"Documentation Analysis Summary:\\n"
        summary += f"• Found {len(self.found_docs)} documentation files\\n"
        summary += f"• Analyzed {len(self.analyzed_docs)} files in detail\\n"
        summary += f"• Generated {len(self.documentation_insights)} insights\\n"
        
        # Summarize by type
        if self.analyzed_docs:
            types = [analysis['content_type'] for analysis in self.analyzed_docs.values()]
            type_counts = {t: types.count(t) for t in set(types)}
            summary += f"• Document types: {', '.join(f'{t}({c})' for t, c in type_counts.items())}\\n"
        
        # Key findings
        key_findings = []
        for insight in self.documentation_insights:
            if insight['confidence'] > 0.8:
                key_findings.append(insight['content'])
        
        if key_findings:
            summary += f"• Key findings: {'; '.join(key_findings[:3])}\\n"
        
        # Cache performance
        if self.state.cache_hits > 0:
            summary += f"• Cache hits: {self.state.cache_hits}\\n"
        
        if self.state.error_count > 0:
            summary += f"• Errors encountered: {self.state.error_count}\\n"
        
        return summary
    
    def get_documentation_insights(self) -> List[Dict[str, Any]]:
        """Get all documentation insights."""
        return self.documentation_insights
    
    def get_analyzed_docs(self) -> Dict[str, Any]:
        """Get all analyzed documentation."""
        return self.analyzed_docs
    
    def get_found_docs(self) -> List[str]:
        """Get list of found documentation files."""
        return self.found_docs