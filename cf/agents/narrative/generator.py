"""
Narrative Generator - Main Generator and Supporting Classes for Technical Narratives

This module consolidates all narrative generation components:
- NarrativeTemplates: Template repository for different narrative styles
- SectionBuilder: Builds narrative sections from context
- CrossFileAnalyzer: Analyzes relationships across multiple files
- QualityScorer: Scores narrative quality
- NarrativeGenerator: Main generator class
"""

import re
import time
from typing import Dict, List, Any, Optional, Callable, Tuple

from cf.agents.validation import validate_answer, ValidationResult
from cf.agents.utils import calculate_word_count_targets, trim_narrative_to_word_limit

from .types import (
    NarrativeStyle, QualityLevel, NarrativeContext,
    NarrativeSection, NarrativeResult, NarrativeTemplate
)


# =============================================================================
# Templates
# =============================================================================

class NarrativeTemplates:
    """Repository of narrative templates for different styles"""

    LIFE_OF_X = NarrativeTemplate(
        style=NarrativeStyle.LIFE_OF_X,
        prompt_template="""Trace the complete lifecycle of "{subject}" through the codebase.
Follow the journey from creation to completion, documenting each step with specific file and line references.""",
        section_templates={},  # LLM determines formatting
        required_sections=[],  # LLM-determined via _determine_structure
        optional_sections=[],  # LLM-determined via _determine_structure
        grounding_rules=[],  # LLM-determined via _determine_structure
        min_code_references=5,
        example_format="In `file.ext` at line 142, the component receives the request..."
    )

    ARCHITECTURE = NarrativeTemplate(
        style=NarrativeStyle.ARCHITECTURE,
        prompt_template="""Describe the architecture and design of "{subject}".
Document the structure, components, and their relationships with concrete file references.""",
        section_templates={},  # LLM determines formatting
        required_sections=[],
        optional_sections=[],
        grounding_rules=[],
        min_code_references=3,
        example_format="The component in `file.ext` coordinates..."
    )

    EXPLANATION = NarrativeTemplate(
        style=NarrativeStyle.EXPLANATION,
        prompt_template="""Explain how "{subject}" works in this codebase.
Provide a clear, educational explanation with file references and code snippets.""",
        section_templates={},
        required_sections=[],
        optional_sections=[],
        grounding_rules=[],
        min_code_references=0,  # LLM determines appropriate number
        example_format="The `method()` in `file.ext:45` performs..."
    )

    COMPARISON = NarrativeTemplate(
        style=NarrativeStyle.COMPARISON,
        prompt_template="""Compare "{subject}" in this codebase.
Provide an objective comparison with concrete code evidence.""",
        section_templates={},
        required_sections=[],
        optional_sections=[],
        grounding_rules=[],
        min_code_references=0,  # LLM determines appropriate number
        example_format="While both components inherit from Base..."
    )

    TUTORIAL = NarrativeTemplate(
        style=NarrativeStyle.TUTORIAL,
        prompt_template="""Create a tutorial for "{subject}".
Guide the reader through understanding and using this feature with practical examples.""",
        section_templates={},
        required_sections=[],
        optional_sections=[],
        grounding_rules=[],
        min_code_references=0,  # LLM determines appropriate number
        example_format="First, open `config.ext` and add..."
    )

    DEBUG_TRACE = NarrativeTemplate(
        style=NarrativeStyle.DEBUG_TRACE,
        prompt_template="""Trace the execution path for debugging "{subject}".
Follow the code path to understand behavior or identify issues with line-level analysis.""",
        section_templates={},
        required_sections=[],
        optional_sections=[],
        grounding_rules=[],
        min_code_references=0,  # LLM determines appropriate number
        example_format="At line 45, the condition evaluates..."
    )

    API_REFERENCE = NarrativeTemplate(
        style=NarrativeStyle.API_REFERENCE,
        prompt_template="""Document the API for "{subject}".
Create reference-style documentation for this interface with usage examples.""",
        section_templates={},
        required_sections=[],
        optional_sections=[],
        grounding_rules=[],
        min_code_references=0,  # LLM determines appropriate number
        example_format="```\nresult = component.method(param='value')\n```"
    )

    @classmethod
    def get_template(cls, style: NarrativeStyle) -> NarrativeTemplate:
        """Get template for a style"""
        templates = {
            NarrativeStyle.LIFE_OF_X: cls.LIFE_OF_X,
            NarrativeStyle.ARCHITECTURE: cls.ARCHITECTURE,
            NarrativeStyle.EXPLANATION: cls.EXPLANATION,
            NarrativeStyle.COMPARISON: cls.COMPARISON,
            NarrativeStyle.TUTORIAL: cls.TUTORIAL,
            NarrativeStyle.DEBUG_TRACE: cls.DEBUG_TRACE,
            NarrativeStyle.API_REFERENCE: cls.API_REFERENCE,
        }
        return templates.get(style, cls.EXPLANATION)


# =============================================================================
# Section Builder
# =============================================================================

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
        """
        Get keywords for section relevance.

        Derives keywords from section name rather than hardcoding specific
        architectural patterns. LLM determines actual relevance in context.
        """
        # Split section name into keywords (e.g., 'entry_point' -> ['entry', 'point'])
        # This avoids hardcoding framework-specific or architecture-specific terms
        return section_name.split('_')

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


# =============================================================================
# Cross-File Analyzer
# =============================================================================

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
        """
        Identify processing stages using call graph structure.

        Uses call graph position rather than hardcoded keywords to determine
        stage membership. This avoids assumptions about naming conventions.
        """
        stages = []

        # Entry points: functions not called by any other function in the graph
        all_callees = set()
        for callees in call_graph.values():
            all_callees.update(callees)
        entry_functions = [f for f in call_graph.keys() if f not in all_callees]

        # Exit points: functions that don't call other functions
        exit_functions = [f for f, callees in call_graph.items() if not callees]

        # Processing: everything in between (called by others and calls others)
        process_functions = [f for f in call_graph.keys()
                           if f not in entry_functions and f not in exit_functions]

        if entry_functions:
            stages.append({'stage': 'entry', 'functions': entry_functions})
        if process_functions:
            stages.append({'stage': 'processing', 'functions': process_functions})
        if exit_functions:
            stages.append({'stage': 'output', 'functions': exit_functions})

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


# =============================================================================
# Quality Scorer
# =============================================================================

class QualityScorer:
    """Scores narrative quality - LLM-driven, no hardcoded weights"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def score(
        self,
        narrative: str,
        context: NarrativeContext,
        validation: ValidationResult
    ) -> Tuple[float, Dict[str, float]]:
        """Score narrative quality - uses validation result from LLM"""
        # Quality scoring is based on validation, not hardcoded weights
        grounding = validation.grounding_score if validation else 0.5
        total = grounding  # LLM-driven validation determines quality

        return total, {'grounding': grounding}


# =============================================================================
# Narrative Generator
# =============================================================================

class NarrativeGenerator:
    """
    Generates comprehensive technical narratives from code analysis.

    Supports multiple narrative styles:
    - 'life_of_x': Traces execution flow of a concept
    - 'architecture': Describes system architecture
    - 'explanation': Explains how something works
    - 'comparison': Compares different implementations
    - 'tutorial': Step-by-step guide
    - 'debug_trace': Debugging walkthrough
    - 'api_reference': API documentation style
    """

    def __init__(self, llm_callback: Callable, config: Dict[str, Any], repo_tools=None):
        """
        Initialize narrative generator.

        Args:
            llm_callback: Callable(prompt, system_prompt) -> response dict
            config: Configuration dictionary
            repo_tools: Optional repository tools for validation
        """
        self.llm = llm_callback
        self.config = config
        self.repo_tools = repo_tools
        self.section_builder = SectionBuilder(llm_callback, config)
        self.quality_scorer = QualityScorer(config)
        self.cross_file_analyzer = CrossFileAnalyzer(llm_callback, config)

    def generate(
        self,
        context: NarrativeContext,
        style: NarrativeStyle = NarrativeStyle.EXPLANATION,
        quality: QualityLevel = QualityLevel.STANDARD
    ) -> NarrativeResult:
        """
        Generate a narrative from analysis context.

        Args:
            context: NarrativeContext with all gathered information
            style: Narrative style to use
            quality: Quality level for generation

        Returns:
            NarrativeResult with narrative and validation
        """
        start_time = time.time()

        # Get template for style
        template = NarrativeTemplates.get_template(style)

        # LLM determines structure during generation - no pre-planning
        dynamic_sections = []
        dynamic_grounding_rules = []

        # Determine word count targets
        file_count = len(context.files_analyzed)
        min_words, max_words = calculate_word_count_targets(file_count, self.config)

        # For higher quality, do cross-file analysis
        flow_analysis = None
        if quality in [QualityLevel.HIGH, QualityLevel.PUBLICATION]:
            subject = self._extract_subject(context.question)
            flow_analysis = self.cross_file_analyzer.analyze_flow(context, subject)

        # Build sections using LLM-determined sections
        sections = self._build_sections(
            context, template, flow_analysis, dynamic_sections
        )

        # Check if we have a base answer from CodeAgent to refine
        # This avoids double synthesis - CodeAgent already generated an answer,
        # we just need to refine/enhance it rather than regenerate from scratch
        if context.base_answer:
            # REFINE MODE: Use CodeAgent's answer as base, just enhance it
            narrative = self._refine_narrative(
                context.base_answer, context, template, dynamic_grounding_rules
            )
        else:
            # GENERATE MODE: No base answer, generate from scratch
            narrative = self._generate_narrative(
                context, template, sections, min_words, max_words, dynamic_grounding_rules
            )

            # For publication quality, do additional refinement pass
            if quality == QualityLevel.PUBLICATION:
                narrative = self._refine_narrative(
                    narrative, context, template, dynamic_grounding_rules
                )

        # Enforce hard word limit (safety net for over-generation)
        # Only trim if significantly over max_words (20% tolerance)
        word_count = len(narrative.split())
        trim_threshold = int(max_words * 1.2)
        if word_count > trim_threshold:
            narrative = trim_narrative_to_word_limit(narrative, max_words)

        # Extract metadata
        title = self._extract_title(narrative, context.question)
        summary = self._extract_summary(narrative)
        files_referenced = self._extract_file_references(narrative, context.files_analyzed)
        code_references = self._extract_code_references(narrative)

        # Validate narrative
        validation = validate_answer(
            narrative,
            context.file_summaries,
            self.config,
            self.repo_tools,
            self.llm
        )

        # Score quality
        quality_score, score_breakdown = self.quality_scorer.score(
            narrative, context, validation
        )

        # Calculate confidence
        confidence = self._calculate_confidence(validation, context, quality_score)

        generation_time = time.time() - start_time

        return NarrativeResult(
            narrative=narrative,
            title=title,
            summary=summary,
            sections=sections,
            confidence=confidence,
            validation=validation,
            word_count=len(narrative.split()),
            files_referenced=files_referenced,
            code_references=code_references,
            generation_time=generation_time,
            style=style,
            quality_score=quality_score
        )

    def _extract_subject(self, question: str) -> str:
        """Extract the main subject from a question - just clean punctuation."""
        # Remove trailing punctuation only, let LLM interpret the question
        subject = re.sub(r'[?!.,]+$', '', question)
        return subject.strip()

    def _build_sections(
        self,
        context: NarrativeContext,
        template: NarrativeTemplate,
        flow_analysis: Optional[Dict[str, Any]],
        dynamic_sections: List[str]
    ) -> List[NarrativeSection]:
        """Build narrative sections using LLM-determined section list."""
        sections = []

        # Build sections determined by LLM
        for section_name in dynamic_sections:
            section_template = template.section_templates.get(section_name, '')
            section = self.section_builder.build_section(
                section_name,
                context,
                section_template,
                focus=flow_analysis.get('entry_points', [None])[0] if flow_analysis else None
            )
            if section.confidence > 0.3:  # Include if reasonably confident
                sections.append(section)

        return sections

    def _should_include_section(
        self,
        section_name: str,
        context: NarrativeContext,
        flow_analysis: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Determine if an optional section should be included.

        Always returns True - let LLM decide relevance based on content.
        No hardcoded heuristics about filename patterns or data structure sizes.
        """
        # Let LLM determine section relevance based on actual content analysis
        return True

    def _generate_narrative(
        self,
        context: NarrativeContext,
        template: NarrativeTemplate,
        sections: List[NarrativeSection],
        min_words: int,
        max_words: int,
        grounding_rules: List[str]
    ) -> str:
        """Generate the full narrative from sections"""
        # Build context from sections
        sections_text = '\n\n'.join(
            f"## {s.title}\n{s.content}" for s in sections if s.content
        )

        # Build file context
        file_context = self._build_file_context(context)

        # Build agent results context
        agent_context = self._build_agent_context(context)

        # Build KB insights context
        kb_context = self._build_kb_context(context)

        prompt = f"""Generate a comprehensive technical narrative answering this question:

Question: {context.question}

Style: {template.style.value}

GROUNDING REQUIREMENTS (CRITICAL):
{chr(10).join(f'- {rule}' for rule in grounding_rules)}

Minimum code references: {template.min_code_references}
Example format: {template.example_format}

Section drafts to integrate and expand:
{sections_text}

Files Analyzed ({len(context.files_analyzed)}):
{chr(10).join(f'- {f}' for f in context.files_analyzed[:30])}

{file_context}

{agent_context}

{kb_context}

CRITICAL LENGTH REQUIREMENT: Generate EXACTLY {min_words}-{max_words} words. Do NOT exceed {max_words} words.
Be concise. Prioritize depth over breadth. Focus on the MOST important aspects only.

The narrative MUST:
1. Directly answer the question with specific evidence
2. Reference specific files and line numbers (format: `filename.py:123`) - USE THE LINE NUMBERS FROM FILE ANALYSIS ABOVE
3. Include 2-3 focused code snippets in ```language blocks
4. Explain how key components work together
5. Include any constants, configuration values, and mappings you discovered during analysis
6. Use clear, technical language without speculation

CRITICAL - Line Reference Format Examples:
- "The `process_request` function (path/to/handlers.py:45) handles..."
- "Configuration is defined in `CONFIG` (path/to/config.py:12)"
- "The `BaseClass` (path/to/models.py:28) contains the core fields..."

Structure (keep each section brief):
- Short introduction (1-2 sentences) answering the question directly
- Core explanation with grounded code references (bulk of content) - cite file:line for EVERY claim
- 1-2 key code snippets showing critical implementation
- Optional: Include a "Where to Look" section if there are multiple files worth exploring
- Optional: Include a "Practical Gotchas" section if there are non-obvious constraints or pitfalls
- Brief summary (2-3 sentences)

Use your judgment on which optional sections are appropriate based on the question and content.
Do NOT force sections that aren't relevant to the question or don't add value.

REMEMBER: Stay under {max_words} words. Quality over quantity."""

        response = self.llm(prompt, self._get_system_prompt(template.style))
        narrative = response.get('content', '') if response.get('success') else ''

        if not narrative:
            narrative = self._generate_fallback(context, sections)

        return narrative

    def _refine_narrative(
        self,
        narrative: str,
        context: NarrativeContext,
        template: NarrativeTemplate,
        grounding_rules: List[str]
    ) -> str:
        """Refine narrative for publication quality"""
        prompt = f"""Review and improve this technical narrative for publication quality.

Original:
{narrative}

Improvements needed:
1. Add more specific file:line references where claims lack grounding
2. Ensure all code snippets are accurate and well-formatted
3. Improve flow and transitions between sections
4. Eliminate any uncertain or speculative language
5. Verify all file references exist in: {', '.join(context.files_analyzed[:20])}

Grounding requirements:
{chr(10).join(f'- {rule}' for rule in grounding_rules)}

Return the improved narrative."""

        response = self.llm(
            prompt,
            system_prompt="You are a technical editor improving code analysis narratives for publication."
        )

        refined = response.get('content', '') if response.get('success') else narrative
        return refined if len(refined) > len(narrative) * 0.5 else narrative

    def _build_file_context(self, context: NarrativeContext) -> str:
        """Build file summaries context with detailed line references"""
        if not context.file_summaries:
            return "No file summaries available."

        parts = ["FILE ANALYSIS (use these line numbers for references):"]
        for file_path, summary in list(context.file_summaries.items())[:20]:
            if isinstance(summary, dict):
                lines = summary.get('line_count', 0)
                functions = summary.get('functions', [])
                classes = summary.get('classes', [])
                constants = summary.get('constants', [])

                # Extract short filename for display
                short_path = file_path.split('/')[-1] if '/' in file_path else file_path

                parts.append(f"\n📄 {short_path} ({lines} lines):")

                # Format functions with line numbers
                if functions:
                    func_items = []
                    for f in functions[:8]:
                        if isinstance(f, dict):
                            name = f.get('name', '')
                            line = f.get('line', 0)
                            if name and line:
                                func_items.append(f"{name}:{line}")
                            elif name:
                                func_items.append(name)
                    if func_items:
                        parts.append(f"  Functions: {', '.join(func_items)}")

                # Format classes with line numbers and key info
                if classes:
                    for c in classes[:4]:
                        if isinstance(c, dict):
                            name = c.get('name', '')
                            line = c.get('line', 0)
                            fields = c.get('fields', [])
                            methods = c.get('methods', [])
                            if name:
                                class_info = f"  Class {name}"
                                if line:
                                    class_info += f":{line}"
                                if fields:
                                    class_info += f" - fields: {', '.join(fields[:5])}"
                                if methods:
                                    class_info += f" - methods: {', '.join(methods[:5])}"
                                parts.append(class_info)

                # Format constants with line numbers and values
                if constants:
                    const_items = []
                    for const in constants[:10]:
                        if isinstance(const, dict):
                            name = const.get('name', '')
                            line = const.get('line', 0)
                            value = const.get('value', '')
                            if name:
                                if line and value:
                                    const_items.append(f"{name}:{line}={value[:50]}")
                                elif line:
                                    const_items.append(f"{name}:{line}")
                                elif value:
                                    const_items.append(f"{name}={value[:50]}")
                                else:
                                    const_items.append(name)
                    if const_items:
                        parts.append(f"  Constants: {', '.join(const_items)}")

        return '\n'.join(parts)

    def _build_agent_context(self, context: NarrativeContext) -> str:
        """Build agent results context"""
        if not context.agent_results:
            return ""

        parts = ["Agent Analysis Results:"]
        for agent_name, result in context.agent_results.items():
            if isinstance(result, dict):
                answer = result.get('answer', result.get('narrative', ''))[:500]
                files = result.get('files_analyzed', [])
                parts.append(f"\n[{agent_name}]: {answer}...")
                if files:
                    parts.append(f"  Files: {', '.join(files[:5])}")

        return '\n'.join(parts)

    def _build_kb_context(self, context: NarrativeContext) -> str:
        """Build knowledge base insights context"""
        if not context.kb_insights:
            return ""

        parts = ["Knowledge Base Insights:"]
        for insight_type, data in context.kb_insights.items():
            if data:
                parts.append(f"\n{insight_type}: {str(data)[:300]}...")

        return '\n'.join(parts)

    def _get_system_prompt(self, style: NarrativeStyle) -> str:
        """Get system prompt for narrative generation"""
        style_guidance = {
            NarrativeStyle.LIFE_OF_X: "Focus on tracing execution flow step by step, like following a packet through a network.",
            NarrativeStyle.ARCHITECTURE: "Focus on structure, components, design patterns, and how pieces fit together.",
            NarrativeStyle.EXPLANATION: "Focus on clear, educational explanations that build understanding progressively.",
            NarrativeStyle.COMPARISON: "Focus on objective, side-by-side comparison with specific code evidence.",
            NarrativeStyle.TUTORIAL: "Focus on practical, step-by-step instructions with working examples.",
            NarrativeStyle.DEBUG_TRACE: "Focus on precise execution flow, decision points, and variable states.",
            NarrativeStyle.API_REFERENCE: "Focus on complete, accurate API documentation with signatures and examples.",
        }

        guidance = style_guidance.get(style, style_guidance[NarrativeStyle.EXPLANATION])

        return f"""You are a technical writer creating grounded code analysis narratives.

{guidance}

CRITICAL Rules:
1. ALWAYS reference specific files and line numbers for every claim
2. NEVER speculate or use uncertain language (probably, might, could, likely)
3. ONLY discuss files you've been given information about
4. Use exact function/class names from the code
5. Include actual code snippets, not descriptions of code
6. Format code with proper markdown syntax highlighting
7. Structure content with clear headers and logical flow
8. Explain WHY code is designed this way, not just WHAT it does"""

    def _generate_fallback(
        self,
        context: NarrativeContext,
        sections: List[NarrativeSection]
    ) -> str:
        """Generate fallback narrative when LLM fails"""
        files = context.files_analyzed[:10]
        file_list = '\n'.join(f'- {f}' for f in files)

        sections_text = '\n\n'.join(
            f"## {s.title}\n{s.content}" for s in sections if s.content
        )

        return f"""# Analysis of: {context.question}

## Files Analyzed
{file_list}

{sections_text if sections_text else 'Analysis details could not be generated.'}

---
This analysis examined {len(context.files_analyzed)} files.
"""

    def _extract_title(self, narrative: str, question: str) -> str:
        """Extract or generate title for narrative"""
        lines = narrative.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line.startswith('#'):
                return line.lstrip('#').strip()
            if len(line) > 20 and len(line) < 100 and not line.startswith('-'):
                return line

        # Generate title from question
        if 'how does' in question.lower():
            return f"How {question.split('how does')[-1].strip().rstrip('?').title()} Works"
        if 'what is' in question.lower():
            return f"Understanding {question.split('what is')[-1].strip().rstrip('?').title()}"
        return "Code Analysis Results"

    def _extract_summary(self, narrative: str) -> str:
        """Extract summary from narrative"""
        # Try to find an introduction/overview section
        sections = re.split(r'^##\s+', narrative, flags=re.MULTILINE)
        if len(sections) > 1:
            # First section after title is often intro
            intro = sections[1] if len(sections) > 1 else sections[0]
            # Get first paragraph
            paragraphs = intro.split('\n\n')
            for p in paragraphs:
                p = p.strip()
                if len(p) > 50 and not p.startswith('#') and not p.startswith('```'):
                    return p[:300] + '...' if len(p) > 300 else p

        # Fallback: first meaningful paragraph
        paragraphs = narrative.split('\n\n')
        for p in paragraphs:
            p = p.strip()
            if len(p) > 50 and not p.startswith('#') and not p.startswith('```'):
                return p[:300] + '...' if len(p) > 300 else p

        return ""

    def _calculate_confidence(
        self,
        validation,
        context: NarrativeContext,
        quality_score: float
    ) -> float:
        """Calculate confidence score"""
        base = 0.4

        # Validation contributes up to 0.25
        if validation.valid:
            base += 0.15
        base += validation.grounding_score * 0.1

        # Quality score contributes up to 0.2
        base += quality_score * 0.2

        # File coverage contributes up to 0.15
        if context.files_analyzed:
            file_bonus = min(0.15, len(context.files_analyzed) * 0.01)
            base += file_bonus

        return min(0.95, base)

    def _extract_file_references(
        self,
        narrative: str,
        analyzed_files: List[str]
    ) -> List[str]:
        """Extract files referenced in the narrative"""
        referenced = set()

        # Build extension pattern from analyzed files (dynamic, not hardcoded)
        extensions = {f.split('.')[-1] for f in analyzed_files if '.' in f}
        if not extensions:
            extensions = {'py', 'js', 'ts'}  # minimal fallback
        ext_pattern = '|'.join(re.escape(ext) for ext in extensions)

        # Match patterns like `filename.ext` or filename.ext:123
        patterns = [
            rf'`([^`]+\.(?:{ext_pattern}))`',
            rf'(\S+\.(?:{ext_pattern})):\d+',
            rf'In\s+`?(\S+\.(?:{ext_pattern}))`?',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, narrative)
            for match in matches:
                # Check if it's in analyzed files
                for analyzed in analyzed_files:
                    if match in analyzed or analyzed.endswith(match):
                        referenced.add(analyzed)
                        break

        return list(referenced)

    def _extract_code_references(
        self,
        narrative: str
    ) -> List[Tuple[str, int]]:
        """Extract file:line references from narrative"""
        references = []

        # Pattern for file:line - use generic extension (1-4 chars)
        # No hardcoded extension list; validation happens elsewhere
        pattern = r'(\S+\.\w{1,4}):(\d+)'
        matches = re.findall(pattern, narrative)

        for file_path, line_num in matches:
            references.append((file_path, int(line_num)))

        return references
