"""
Narrative Generator - Main Generator Class for Technical Narratives
"""

import re
import time
from typing import Dict, List, Any, Optional, Callable, Tuple

from cf.agents.validation import validate_answer
from cf.agents.utils import calculate_word_count_targets

from .types import (
    NarrativeStyle, QualityLevel, NarrativeContext,
    NarrativeSection, NarrativeResult, NarrativeTemplate
)
from .templates import NarrativeTemplates
from .builders import SectionBuilder, CrossFileAnalyzer
from .scoring import QualityScorer


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

        # Determine word count targets
        file_count = len(context.files_analyzed)
        min_words, max_words = calculate_word_count_targets(file_count, self.config)

        # For higher quality, do cross-file analysis
        flow_analysis = None
        if quality in [QualityLevel.HIGH, QualityLevel.PUBLICATION]:
            subject = self._extract_subject(context.question)
            flow_analysis = self.cross_file_analyzer.analyze_flow(context, subject)

        # Build sections
        sections = self._build_sections(context, template, flow_analysis)

        # Generate full narrative
        narrative = self._generate_narrative(
            context, template, sections, min_words, max_words
        )

        # For publication quality, do multiple refinement passes
        if quality == QualityLevel.PUBLICATION:
            narrative = self._refine_narrative(narrative, context, template)

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
        """Extract the main subject from a question"""
        # Remove question words
        subject = re.sub(
            r'^(how does|what is|where is|explain|describe|trace)\s+',
            '',
            question.lower()
        )
        # Remove trailing punctuation
        subject = re.sub(r'[?!.,]+$', '', subject)
        return subject.strip()

    def _build_sections(
        self,
        context: NarrativeContext,
        template: NarrativeTemplate,
        flow_analysis: Optional[Dict[str, Any]]
    ) -> List[NarrativeSection]:
        """Build narrative sections"""
        sections = []

        # Build required sections
        for section_name in template.required_sections:
            section_template = template.section_templates.get(section_name, '')
            section = self.section_builder.build_section(
                section_name,
                context,
                section_template,
                focus=flow_analysis.get('entry_points', [None])[0] if flow_analysis else None
            )
            sections.append(section)

        # Build optional sections if we have relevant content
        for section_name in template.optional_sections:
            if self._should_include_section(section_name, context, flow_analysis):
                section_template = template.section_templates.get(section_name, '')
                section = self.section_builder.build_section(
                    section_name,
                    context,
                    section_template
                )
                if section.confidence > 0.5:
                    sections.append(section)

        return sections

    def _should_include_section(
        self,
        section_name: str,
        context: NarrativeContext,
        flow_analysis: Optional[Dict[str, Any]]
    ) -> bool:
        """Determine if an optional section should be included"""
        if section_name == 'error_handling':
            # Include if any files mention error handling
            return any('error' in f.lower() or 'exception' in f.lower()
                      for f in context.files_analyzed)
        elif section_name == 'data_flow' and flow_analysis:
            # Include if we have a meaningful call graph
            return len(flow_analysis.get('call_graph', {})) > 2
        elif section_name == 'patterns':
            # Include if we found design patterns
            return bool(context.kb_insights.get('patterns'))
        return False

    def _generate_narrative(
        self,
        context: NarrativeContext,
        template: NarrativeTemplate,
        sections: List[NarrativeSection],
        min_words: int,
        max_words: int
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
{chr(10).join(f'- {rule}' for rule in template.grounding_rules)}

Minimum code references: {template.min_code_references}
Example format: {template.example_format}

Section drafts to integrate and expand:
{sections_text}

Files Analyzed ({len(context.files_analyzed)}):
{chr(10).join(f'- {f}' for f in context.files_analyzed[:30])}

{file_context}

{agent_context}

{kb_context}

Generate a {min_words}-{max_words} word technical narrative that:
1. Directly answers the question with specific evidence
2. References specific files and line numbers (format: `file.py:123`)
3. Includes relevant code snippets in ```language blocks
4. Explains how components work together
5. Uses clear, technical language
6. Avoids uncertain language (probably, might, could)

Structure:
- Clear introduction answering the question directly
- Detailed explanations with grounded code references
- Code snippets showing actual implementation
- Summary of key points"""

        response = self.llm(prompt, self._get_system_prompt(template.style))
        narrative = response.get('content', '') if response.get('success') else ''

        if not narrative:
            narrative = self._generate_fallback(context, sections)

        return narrative

    def _refine_narrative(
        self,
        narrative: str,
        context: NarrativeContext,
        template: NarrativeTemplate
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
{chr(10).join(f'- {rule}' for rule in template.grounding_rules)}

Return the improved narrative."""

        response = self.llm(
            prompt,
            system_prompt="You are a technical editor improving code analysis narratives for publication."
        )

        refined = response.get('content', '') if response.get('success') else narrative
        return refined if len(refined) > len(narrative) * 0.5 else narrative

    def _build_file_context(self, context: NarrativeContext) -> str:
        """Build file summaries context"""
        if not context.file_summaries:
            return "No file summaries available."

        parts = ["File Summaries:"]
        for file_path, summary in list(context.file_summaries.items())[:15]:
            if isinstance(summary, dict):
                lines = summary.get('line_count', 0)
                functions = summary.get('functions', [])
                classes = summary.get('classes', [])
                func_names = [f.get('name', '') for f in functions[:5] if isinstance(f, dict)]
                class_names = [c.get('name', '') for c in classes[:3] if isinstance(c, dict)]

                parts.append(f"\n{file_path} ({lines} lines):")
                if func_names:
                    parts.append(f"  Functions: {', '.join(func_names)}")
                if class_names:
                    parts.append(f"  Classes: {', '.join(class_names)}")

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
7. Structure content with clear headers and logical flow"""

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

        # Match patterns like `filename.py` or filename.py:123
        patterns = [
            r'`([^`]+\.(?:py|js|ts|java|go|rs|cpp|c|h))`',
            r'(\S+\.(?:py|js|ts|java|go|rs|cpp|c|h)):\d+',
            r'In\s+`?(\S+\.(?:py|js|ts|java|go|rs|cpp|c|h))`?',
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

        # Pattern for file:line
        pattern = r'(\S+\.(?:py|js|ts|java|go|rs|cpp|c|h)):(\d+)'
        matches = re.findall(pattern, narrative)

        for file_path, line_num in matches:
            references.append((file_path, int(line_num)))

        return references
