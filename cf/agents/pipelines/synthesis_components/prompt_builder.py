"""
Prompt Builder for Synthesis Pipeline

Handles construction of synthesis prompts with various context sections.
"""

from typing import Dict, List, Any


class PromptBuilder:
    """Builds synthesis prompts with file summaries, patterns, architecture, etc."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Load display limits from config
        synthesis_config = config.get('agents', {}).get('synthesis', {})
        self.max_functions_per_file = synthesis_config.get('max_functions_per_file', 5)
        self.max_classes_per_file = synthesis_config.get('max_classes_per_file', 5)
        self.max_usage_examples = synthesis_config.get('max_usage_examples', 3)
        self.max_edge_cases = synthesis_config.get('max_edge_cases', 3)
        self.max_pattern_files = synthesis_config.get('max_pattern_files', 3)
        self.max_entry_points = synthesis_config.get('max_entry_points', 3)
        self.max_core_abstractions = synthesis_config.get('max_core_abstractions', 3)
        self.max_execution_paths = synthesis_config.get('max_execution_paths', 3)
        self.max_steps_per_path = synthesis_config.get('max_steps_per_path', 10)
        self.max_shared_abstractions = synthesis_config.get('max_shared_abstractions', 5)
        self.max_files_per_abstraction = synthesis_config.get('max_files_per_abstraction', 2)
        self.max_dependencies = synthesis_config.get('max_dependencies', 5)
        self.max_data_flows = synthesis_config.get('max_data_flows', 5)
        self.max_validation_errors = synthesis_config.get('max_validation_errors', 5)
        self.max_validation_warnings = synthesis_config.get('max_validation_warnings', 5)
        self.max_insights = synthesis_config.get('max_insights', 20)

    def build_synthesis_prompt(self,
                              question: str,
                              key_files: List[str],
                              file_summaries: Dict[str, Any],
                              insights: List[Dict[str, Any]],
                              target_min: int,
                              target_max: int,
                              detected_patterns: List[Dict[str, Any]] = None,
                              architectural_analysis=None,
                              execution_paths: List[Dict[str, Any]] = None,
                              validation_issues: List[Dict[str, Any]] = None,
                              cross_file_relationships: Dict[str, Any] = None) -> str:
        """Build prompt for synthesis"""

        print(f"   [DEBUG SYNTHESIS] Building prompt with {len(key_files)} key files")

        # Use helper methods to build each section
        summaries_text = self._format_file_summaries_by_type(key_files, file_summaries)

        # Build insights text
        insights_text = ""
        for insight in insights[:self.max_insights]:
            content = insight.get('content', '')
            if content:
                insights_text += f"- {content}\n"

        # Build additional context sections using helper methods
        patterns_text = self._build_patterns_text(detected_patterns)
        arch_text = self._build_architectural_text(architectural_analysis)
        paths_text = self._build_execution_paths_text(execution_paths)
        relationships_text = self._build_relationships_text(cross_file_relationships)
        feedback_text = self._build_validation_feedback_text(validation_issues)

        # Build list of valid file paths for LLM reference
        file_paths_list = "\n".join([f"  - {fp}" for fp in key_files])

        # DEBUG logging
        print(f"   [DEBUG SYNTHESIS] summaries_text length: {len(summaries_text)} chars")

        prompt = f"""Generate a comprehensive technical narrative answering this question:

QUESTION: "{question}"

You have analyzed {len(file_summaries)} files and gathered the following insights:

ANALYZED FILE PATHS (use these exact paths in your narrative):
{file_paths_list}

🚨 CRITICAL - ANTI-HALLUCINATION RULES:
1. You MUST ONLY reference files listed above in "ANALYZED FILE PATHS"
2. You MUST NOT invent or make up file names like "ApplicationController.py" or "ApplicationService.py"
3. You MUST NOT reference files that were not analyzed (e.g., "views.py", "models.py", "services.py")
4. If the analyzed files don't fully answer the question, explicitly state what's missing
5. Every file path in your narrative MUST be from the list above
6. If you cannot provide a complete answer with the given files, say so rather than hallucinate

⚠️  If you reference ANY file not in the "ANALYZED FILE PATHS" list above, your answer will be REJECTED.

KEY FILES ANALYZED:
{summaries_text}

📂 FILE TYPE GUIDANCE:
The files above are organized by type to help you structure your narrative:
- **MAIN IMPLEMENTATION FILES**: Use these to explain HOW the system works (core business logic)
- **TEST FILES**: Use these to provide CONCRETE EXAMPLES of execution flow and usage patterns
- **UTILITY FILES**: Use these to explain supporting infrastructure

STRUCTURE YOUR NARRATIVE:
1. First, explain the main implementation using production files
2. Then, illustrate with concrete examples from test files (if available)
3. Finally, mention supporting utilities that assist the main logic

INSIGHTS:
{insights_text}
{patterns_text}
{arch_text}
{paths_text}
{relationships_text}
{feedback_text}
TASK: Write a detailed technical narrative that explains HOW the system works, not just WHAT it does.
Use ONLY the analyzed files above. If they don't fully answer the question, acknowledge the limitation.

REQUIREMENTS:
1. Length: MINIMUM {target_min} words (aim for {target_max} words for comprehensive coverage)
2. Format: Markdown with clear sections
3. Style: Educational "Life of X" narrative format
4. Grounding: Include specific file paths and line number references in EVERY paragraph
5. Depth: Explain HOW code works, not just WHAT it does
6. Structure:
   - Start with overview/context
   - Explain main flow/architecture
   - Detail key components and their interactions
   - Include code examples where relevant
   - Conclude with summary of how everything connects

CRITICAL REQUIREMENTS:
- MUST include specific file paths (e.g., "src/auth/models.py")
- MUST include line number references (e.g., "at line 123", "on line 45", "lines 100-150")
- MUST explain HOW code works (algorithms, data flow, patterns)
- MUST be technically accurate and grounded in analyzed code
- MUST mention detected design patterns where relevant
- MUST explain how files work TOGETHER (use Cross-File Architecture section above)
- If execution paths are provided, MUST trace the flow step-by-step
- AVOID generic statements without code references
- AVOID just listing files without explaining their role
- AVOID analyzing files in isolation - explain their relationships and interactions

⚠️  CRITICAL: When mentioning line numbers, ALWAYS include the file path in the SAME sentence.
    - Line numbers without file paths are INVALID and will fail validation
    - Use format: "file_path line NUMBER" or "file_path at line NUMBER"

REQUIRED FORMAT EXAMPLES:
✅ GOOD: "The authentication flow starts in cf/auth/login.py at line 45 where the login() function validates credentials."
✅ GOOD: "The UserModel class is defined in cf/models/user.py at line 23 with fields for username and email."
✅ GOOD: "In apps/enrollment/managers.py, the ApplicationManager class (line 4) filters active applications."
❌ BAD: "The authentication flow handles user login." (no file path, no line number)
❌ BAD: "The UserModel class at line 23 defines the user data structure." (no file path)
❌ BAD: "Line 45 validates credentials." (no file path)

Every major statement about code MUST reference the specific file path AND line number where that code exists.
File paths MUST appear in or near the same sentence as the line numbers they reference.

Generate the narrative now:"""

        return prompt

    def _format_file_summaries_by_type(self, key_files: List[str], file_summaries: Dict[str, Any]) -> str:
        """
        Format file summaries grouped by type (production/test/utility).

        Args:
            key_files: List of file paths to format
            file_summaries: Dict mapping file_path -> summary

        Returns:
            Formatted summaries text with sections
        """
        # Separate files by type
        production_files = []
        test_files = []
        utility_files = []

        for file_path in key_files:
            summary = file_summaries.get(file_path, {})
            file_type = summary.get('file_type', 'production') if isinstance(summary, dict) else getattr(summary, 'file_type', 'production')

            if file_type == 'production':
                production_files.append(file_path)
            elif file_type == 'test':
                test_files.append(file_path)
            else:
                utility_files.append(file_path)

        # Helper to format a single file
        def format_file_summary(file_path: str, summary: Any) -> str:
            """Format a single file summary with functions/classes"""
            text = f"\n\n## {file_path}\n"

            if isinstance(summary, dict):
                text += f"Key Features: {', '.join(summary.get('key_features', []))}\n"
                text += f"Architecture: {summary.get('architectural_insights', '')}\n"

                # Include function/class info with line numbers
                functions = summary.get('functions', [])
                classes = summary.get('classes', [])
                if functions:
                    text += f"Functions in {file_path}:\n"
                    for f in functions[:self.max_functions_per_file]:
                        func_name = f.get('name', 'unknown')
                        func_line = f.get('line', '?')
                        text += f"  - {func_name} at line {func_line}\n"
                if classes:
                    text += f"Classes in {file_path}:\n"
                    for c in classes[:self.max_classes_per_file]:
                        class_name = c.get('name', 'unknown')
                        class_line = c.get('line', '?')
                        text += f"  - {class_name} at line {class_line}\n"

            return text

        # Build summaries by type
        summaries_text = ""

        # Section 1: Production Files
        if production_files:
            summaries_text += "\n\n# MAIN IMPLEMENTATION FILES (Production Code)\n"
            summaries_text += "These files contain the core business logic and main implementation:\n"
            for file_path in production_files:
                summary = file_summaries.get(file_path, {})
                if isinstance(summary, dict):
                    summaries_text += format_file_summary(file_path, summary)

                    # Include test information if available
                    test_info = summary.get('test_info', {})
                    if test_info.get('has_tests'):
                        summaries_text += f"\nTest Coverage: {test_info.get('test_count', 0)} tests\n"

                        usage_examples = test_info.get('usage_examples', [])
                        if usage_examples:
                            summaries_text += "Usage Examples:\n"
                            for ex in usage_examples[:self.max_usage_examples]:
                                summaries_text += f"  - {ex}\n"

                        edge_cases = test_info.get('edge_cases', [])
                        if edge_cases:
                            summaries_text += "Edge Cases Tested:\n"
                            for ec in edge_cases[:self.max_edge_cases]:
                                summaries_text += f"  - {ec}\n"

        # Section 2: Test Files
        if test_files:
            summaries_text += "\n\n# TEST FILES (Concrete Usage Examples)\n"
            summaries_text += "These files show how the production code is used in practice:\n"
            for file_path in test_files:
                summary = file_summaries.get(file_path, {})
                if isinstance(summary, dict):
                    summaries_text += format_file_summary(file_path, summary)

        # Section 3: Utility Files
        if utility_files:
            summaries_text += "\n\n# UTILITY FILES (Supporting Infrastructure)\n"
            summaries_text += "These files provide supporting functionality:\n"
            for file_path in utility_files:
                summary = file_summaries.get(file_path, {})
                if isinstance(summary, dict):
                    summaries_text += format_file_summary(file_path, summary)

        return summaries_text

    def _build_patterns_text(self, detected_patterns: List[Dict[str, Any]]) -> str:
        """Build text describing detected design patterns."""
        if not detected_patterns:
            return ""

        text = "\n\nDETECTED DESIGN PATTERNS:\n"
        for pattern in detected_patterns:
            text += f"- {pattern.get('name', 'Unknown')}: {pattern.get('description', '')}\n"
            if pattern.get('files'):
                text += f"  Files: {', '.join(pattern['files'][:self.max_pattern_files])}\n"
        return text

    def _build_architectural_text(self, architectural_analysis) -> str:
        """Build text describing architectural summary."""
        if not architectural_analysis:
            return ""

        text = f"\n\nARCHITECTURAL SUMMARY:\n{architectural_analysis.architectural_summary}\n"
        if architectural_analysis.entry_points:
            text += f"\nEntry Points: {', '.join([e.name for e in architectural_analysis.entry_points[:self.max_entry_points]])}\n"
        if architectural_analysis.core_abstractions:
            text += f"Core Abstractions: {', '.join([a.name for a in architectural_analysis.core_abstractions[:self.max_core_abstractions]])}\n"
        return text

    def _build_execution_paths_text(self, execution_paths: List[Dict[str, Any]]) -> str:
        """Build text describing execution paths traced."""
        if not execution_paths:
            return ""

        text = "\n\nEXECUTION PATHS TRACED:\n"
        for i, path in enumerate(execution_paths[:self.max_execution_paths], 1):
            text += f"\nPath {i}: {path.get('name', 'Unknown flow')}\n"
            steps = path.get('steps', [])
            for step in steps[:self.max_steps_per_path]:
                text += f"  → {step.get('function', 'unknown')} ({step.get('file', '')}:{step.get('line', '?')})\n"
            if len(steps) > self.max_steps_per_path:
                text += f"  ... ({len(steps) - self.max_steps_per_path} more steps)\n"
        return text

    def _build_relationships_text(self, cross_file_relationships: Dict[str, Any]) -> str:
        """Build text describing cross-file relationships."""
        if not cross_file_relationships:
            return ""

        text = "\n\nCROSS-FILE ARCHITECTURE:\n"

        shared = cross_file_relationships.get('shared_abstractions', [])
        if shared:
            text += "\nShared Abstractions (used across files):\n"
            for abstraction in shared[:self.max_shared_abstractions]:
                name = abstraction.get('name', 'unknown')
                files = abstraction.get('files', [])
                text += f"  - {name}: used in {', '.join(files[:self.max_files_per_abstraction])}\n"

        deps = cross_file_relationships.get('dependencies', [])
        if deps:
            text += "\nComponent Dependencies:\n"
            for dep in deps[:self.max_dependencies]:
                from_file = dep.get('from', '')
                to_file = dep.get('to', '')
                rel_type = dep.get('relationship', '')
                text += f"  - {from_file} → {to_file} ({rel_type})\n"

        flows = cross_file_relationships.get('data_flow', [])
        if flows:
            text += "\nData Flow Roles:\n"
            for flow in flows[:self.max_data_flows]:
                file = flow.get('file', '')
                role = flow.get('role', '')
                text += f"  - {file}: {role}\n"

        return text

    def _build_validation_feedback_text(self, validation_issues: List[Dict[str, Any]]) -> str:
        """Build text with validation feedback from previous attempt."""
        if not validation_issues:
            return ""

        text = "\n\n🚨 VALIDATION FEEDBACK FROM PREVIOUS ATTEMPT:\n"
        text += "Your previous narrative had the following issues that MUST be fixed:\n\n"

        # Group issues by type
        errors = [issue for issue in validation_issues if issue.get('severity') == 'error']
        warnings = [issue for issue in validation_issues if issue.get('severity') == 'warning']

        if errors:
            text += "CRITICAL ERRORS (must fix):\n"
            for i, issue in enumerate(errors[:self.max_validation_errors], 1):
                text += f"  {i}. {issue.get('message', 'Unknown error')}\n"

        if warnings:
            text += "\nWARNINGS (should fix):\n"
            for i, issue in enumerate(warnings[:self.max_validation_warnings], 1):
                text += f"  {i}. {issue.get('message', 'Unknown warning')}\n"

        text += "\n⚠️  IMPORTANT: Address ALL errors above in your new narrative.\n"
        text += "Pay special attention to word count and line number coverage requirements.\n\n"

        return text
