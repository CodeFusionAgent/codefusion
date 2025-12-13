"""
Narrative Builders - Section and Cross-File Analysis for Narratives
"""

from typing import Dict, List, Any, Optional, Callable, Tuple

from .types import NarrativeContext, NarrativeSection


class SectionBuilder:
    """Builds narrative sections from context"""

    def __init__(self, llm_callback: Callable, config: Dict[str, Any]):
        self.llm = llm_callback
        self.config = config

    def build_section(
        self,
        section_name: str,
        context: NarrativeContext,
        template: str,
        focus: Optional[str] = None
    ) -> NarrativeSection:
        """Build a single narrative section"""
        # Find relevant files for this section
        relevant_files = self._find_relevant_files(section_name, context, focus)

        # Extract code snippets
        snippets = self._extract_snippets(relevant_files, context)

        # Generate section content
        prompt = f"""Generate the "{section_name}" section for a code analysis narrative.

Question: {context.question}
Focus: {focus or section_name}

Relevant files:
{chr(10).join(f'- {f}' for f in relevant_files[:10])}

Code snippets:
{self._format_snippets(snippets)}

Template to follow:
{template}

Requirements:
- Reference specific files with line numbers
- Include relevant code snippets
- Be precise and factual
- Avoid speculation"""

        response = self.llm(
            prompt,
            system_prompt="You are writing a technical code analysis section. Be precise and grounded."
        )

        content = response.get('content', '') if response.get('success') else ''

        return NarrativeSection(
            title=section_name.replace('_', ' ').title(),
            content=content,
            file_references=relevant_files,
            code_snippets=[(f, s) for f, s in snippets[:5]],
            confidence=0.8 if content else 0.3
        )

    def _find_relevant_files(
        self,
        section_name: str,
        context: NarrativeContext,
        focus: Optional[str]
    ) -> List[str]:
        """Find files relevant to a section"""
        # Use keywords to filter files
        keywords = self._section_keywords(section_name)
        if focus:
            keywords.extend(focus.lower().split())

        relevant = []
        for file_path in context.files_analyzed:
            file_lower = file_path.lower()
            summary = context.file_summaries.get(file_path, {})

            # Check file name
            if any(kw in file_lower for kw in keywords):
                relevant.append(file_path)
                continue

            # Check functions/classes in summary
            if isinstance(summary, dict):
                functions = [f.get('name', '').lower() for f in summary.get('functions', [])]
                classes = [c.get('name', '').lower() for c in summary.get('classes', [])]
                if any(kw in ' '.join(functions + classes) for kw in keywords):
                    relevant.append(file_path)

        return relevant[:15]

    def _section_keywords(self, section_name: str) -> List[str]:
        """Get keywords for section relevance"""
        keyword_map = {
            'entry_point': ['main', 'entry', 'start', 'init', 'run', 'execute'],
            'processing': ['process', 'handle', 'execute', 'analyze', 'transform'],
            'data_flow': ['flow', 'data', 'transfer', 'pass', 'pipe', 'stream'],
            'output': ['output', 'result', 'return', 'response', 'complete'],
            'overview': ['overview', 'main', 'core', 'base', 'root'],
            'components': ['component', 'module', 'agent', 'handler', 'service'],
            'patterns': ['pattern', 'factory', 'singleton', 'observer', 'strategy'],
            'purpose': ['purpose', 'goal', 'reason', 'why', 'objective'],
            'how_it_works': ['work', 'implement', 'logic', 'algorithm', 'process'],
        }
        return keyword_map.get(section_name, section_name.split('_'))

    def _extract_snippets(
        self,
        files: List[str],
        context: NarrativeContext
    ) -> List[Tuple[str, str]]:
        """Extract code snippets from context"""
        snippets = []
        for file_path in files:
            if file_path in context.code_snippets:
                snippets.append((file_path, context.code_snippets[file_path]))
        return snippets

    def _format_snippets(self, snippets: List[Tuple[str, str]]) -> str:
        """Format snippets for prompt"""
        parts = []
        for file_path, code in snippets[:5]:
            # Limit snippet size
            lines = code.split('\n')[:30]
            code_preview = '\n'.join(lines)
            parts.append(f"```\n# {file_path}\n{code_preview}\n```")
        return '\n\n'.join(parts) if parts else "No code snippets available."


class CrossFileAnalyzer:
    """Analyzes relationships across multiple files"""

    def __init__(self, llm_callback: Callable, config: Dict[str, Any]):
        self.llm = llm_callback
        self.config = config

    def analyze_flow(
        self,
        context: NarrativeContext,
        subject: str
    ) -> Dict[str, Any]:
        """Analyze flow of a subject across files"""
        # Find files mentioning the subject
        relevant_files = []
        for file_path, summary in context.file_summaries.items():
            if self._mentions_subject(summary, subject):
                relevant_files.append(file_path)

        # Build call graph
        call_graph = self._build_call_graph(relevant_files, context)

        # Identify flow stages
        stages = self._identify_stages(call_graph, subject)

        return {
            'relevant_files': relevant_files,
            'call_graph': call_graph,
            'stages': stages,
            'entry_points': self._find_entry_points(call_graph),
            'exit_points': self._find_exit_points(call_graph),
        }

    def _mentions_subject(self, summary: Any, subject: str) -> bool:
        """Check if summary mentions the subject"""
        if not isinstance(summary, dict):
            return False

        subject_lower = subject.lower()
        text_to_check = []

        # Check functions
        for func in summary.get('functions', []):
            if isinstance(func, dict):
                text_to_check.append(func.get('name', '').lower())
                text_to_check.append(func.get('docstring', '').lower())

        # Check classes
        for cls in summary.get('classes', []):
            if isinstance(cls, dict):
                text_to_check.append(cls.get('name', '').lower())
                text_to_check.append(cls.get('docstring', '').lower())

        return any(subject_lower in text for text in text_to_check)

    def _build_call_graph(
        self,
        files: List[str],
        context: NarrativeContext
    ) -> Dict[str, List[str]]:
        """Build call graph from file summaries"""
        graph = {}
        for file_path in files:
            summary = context.file_summaries.get(file_path, {})
            if isinstance(summary, dict):
                for func in summary.get('functions', []):
                    if isinstance(func, dict):
                        func_name = func.get('name', '')
                        # Use dependencies if available
                        callees = context.dependencies.get(func_name, [])
                        graph[func_name] = callees
        return graph

    def _identify_stages(
        self,
        call_graph: Dict[str, List[str]],
        subject: str
    ) -> List[Dict[str, Any]]:
        """Identify processing stages"""
        stages = []

        # Entry points (nothing calls them or they're main/run)
        entry_functions = [f for f in call_graph.keys()
                         if any(kw in f.lower() for kw in ['main', 'run', 'start', 'init', 'entry'])]

        # Processing functions
        process_functions = [f for f in call_graph.keys()
                           if any(kw in f.lower() for kw in ['process', 'handle', 'execute', 'analyze'])]

        # Output functions
        output_functions = [f for f in call_graph.keys()
                          if any(kw in f.lower() for kw in ['return', 'output', 'respond', 'complete'])]

        if entry_functions:
            stages.append({'stage': 'entry', 'functions': entry_functions})
        if process_functions:
            stages.append({'stage': 'processing', 'functions': process_functions})
        if output_functions:
            stages.append({'stage': 'output', 'functions': output_functions})

        return stages

    def _find_entry_points(self, call_graph: Dict[str, List[str]]) -> List[str]:
        """Find entry points (functions not called by others)"""
        all_callees = set()
        for callees in call_graph.values():
            all_callees.update(callees)

        return [f for f in call_graph.keys() if f not in all_callees]

    def _find_exit_points(self, call_graph: Dict[str, List[str]]) -> List[str]:
        """Find exit points (functions that don't call others)"""
        return [f for f, callees in call_graph.items() if not callees]
