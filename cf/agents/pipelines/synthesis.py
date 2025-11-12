"""
Synthesis Pipeline for CodeFusion

Responsible for generating final technical narratives from analyzed data.
All parameters are config-driven for maximum flexibility.
"""

import json
import re
import time
import traceback
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from cf.llm.model_tiers import ModelTier


@dataclass
class SynthesisResult:
    """Result of synthesis process"""
    narrative: str
    key_files_cited: List[str]
    confidence: float
    word_count: int
    synthesis_time_ms: float


class SynthesisPipeline:
    """
    Main synthesis pipeline that generates final technical narratives.
    Uses LLM to synthesize insights from file summaries.
    """

    def __init__(self, repo_path: str, config: Dict[str, Any], llm_client, tiered_llm=None, kb_client=None):
        self.repo_path = repo_path
        self.config = config
        self.llm = llm_client
        self.tiered_llm = tiered_llm  # Optional tiered LLM manager
        self.kb = kb_client  # Optional KB for pattern detection

        # Compile regex patterns for validation performance (ISSUE #9 fix)
        # Single pass through narrative instead of multiple findall() calls
        self.validation_pattern = re.compile(
            r'(?P<line_ref>line[s]?\s+\d+|L\d+)|'  # Line references
            r'(?P<path_ref>[\w/.-]+\.\w+)|'        # File paths
            r'(?P<code_block>```)|'                # Code blocks
            r'(?P<section>^#+\s+)',                # Section headers
            re.IGNORECASE | re.MULTILINE
        )

    def synthesize(self, question: str, file_summaries: Dict[str, Any], insights: List[Dict[str, Any]],
                   architectural_analysis=None) -> SynthesisResult:
        """
        Generate final technical narrative

        Args:
            question: User's question
            file_summaries: Analyzed file summaries
            insights: List of insights collected during analysis

        Returns:
            SynthesisResult with narrative and metadata
        """
        try:
            print("📝 [SYNTHESIS] Generating narrative...")

            start_time = time.time()

            # Get synthesis parameters from config
            synthesis_config = self.config.get('agents', {}).get('synthesis', {})
            target_min = synthesis_config.get('target_narrative_min', 3000)
            target_max = synthesis_config.get('target_narrative_max', 5000)
            max_files = synthesis_config.get('max_key_files_cited', 7)
            min_files = synthesis_config.get('min_key_files_cited', 3)

            # Select key files to cite (highest relevance)
            key_files = self._select_key_files(file_summaries, max_files)

            # Classify question type for appropriate synthesis strategy
            question_type = 'standard'
            if self.tiered_llm:
                classification = self.tiered_llm.classify_question(question)
                question_type = classification.get('type', 'standard')
                print(f"   Question type: {question_type} (confidence: {classification.get('confidence', 0):.2f})")

            # Detect patterns from KB (NEW)
            detected_patterns = self._detect_patterns_from_kb(file_summaries)

            # Trace execution paths for "how" questions (NEW)
            execution_paths = None
            if question_type in ['how_it_works', 'explain', 'flow']:
                execution_paths = self._trace_execution_paths(question, file_summaries, architectural_analysis)

            # Build synthesis prompt
            prompt = self._build_synthesis_prompt(
                question,
                key_files,
                file_summaries,
                insights,
                target_min,
                target_max,
                detected_patterns,
                architectural_analysis,
                execution_paths
            )

            # Use tiered LLM for synthesis (advanced tier for quality)
            if self.tiered_llm:
                # Use the detailed prompt we built with line number requirements
                # instead of letting synthesize_answer create its own generic prompt
                response = self.tiered_llm.generate(
                    prompt=prompt,
                    tier=ModelTier.ADVANCED,
                    max_tokens=2000
                )
                # Coerce response to string
                if isinstance(response, dict):
                    narrative = response.get('content', str(response))
                else:
                    narrative = str(response)
                narrative = narrative.strip()
                word_count = len(narrative.split())
            else:
                # Fallback to old method
                response = self.llm.generate(prompt, "You are a technical documentation expert. Write comprehensive, accurate narratives.")

                if not response.get('success'):
                    raise Exception("Synthesis failed")

                narrative = response.get('content', '').strip()
                word_count = len(narrative.split())

            # Calculate confidence based on completeness
            confidence = self._calculate_synthesis_confidence(
                narrative,
                file_summaries,
                target_min,
                target_max
            )

            synthesis_time = time.time() - start_time

            print(f"✅ [SYNTHESIS] Generated narrative:")
            print(f"   Words: {word_count} (target: {target_min}-{target_max})")
            print(f"   Key files: {len(key_files)}")
            print(f"   Confidence: {confidence:.2f}")
            print(f"   Time: {synthesis_time*1000:.0f}ms")

            return SynthesisResult(
                narrative=narrative,
                key_files_cited=key_files,
                confidence=confidence,
                word_count=word_count,
                synthesis_time_ms=round(synthesis_time * 1000, 2)
            )

        except Exception as e:
            print(f"❌ [SYNTHESIS] Failed: {e}")
            print(traceback.format_exc())

        # Return fallback result
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        return SynthesisResult(
            narrative="Synthesis failed - insufficient data",
            key_files_cited=[],
            confidence=thresholds.get('error_confidence', 0.2),
            word_count=0,
            synthesis_time_ms=0
        )

    def _select_key_files(self, file_summaries: Dict[str, Any], max_files: int) -> List[str]:
        """Select most relevant files to cite"""
        # Sort by relevance if available, otherwise just take first N
        files = list(file_summaries.keys())[:max_files]
        return files

    def _build_synthesis_prompt(self,
                                question: str,
                                key_files: List[str],
                                file_summaries: Dict[str, Any],
                                insights: List[Dict[str, Any]],
                                target_min: int,
                                target_max: int,
                                detected_patterns: List[Dict[str, Any]] = None,
                                architectural_analysis=None,
                                execution_paths: List[Dict[str, Any]] = None) -> str:
        """Build prompt for synthesis"""

        # Prepare file summaries text
        summaries_text = ""

        # DEBUG: Log what we're receiving
        print(f"   [DEBUG SYNTHESIS] Building prompt with {len(key_files)} key files")

        for file_path in key_files:
            summary = file_summaries.get(file_path, {})

            # DEBUG: Log summary structure
            print(f"   [DEBUG SYNTHESIS] File: {file_path}")
            print(f"   [DEBUG SYNTHESIS]   Summary type: {type(summary)}")
            if isinstance(summary, dict):
                print(f"   [DEBUG SYNTHESIS]   Functions: {len(summary.get('functions', []))} items")
                if summary.get('functions'):
                    print(f"   [DEBUG SYNTHESIS]   First function: {summary['functions'][0]}")
                print(f"   [DEBUG SYNTHESIS]   Classes: {len(summary.get('classes', []))} items")
                if summary.get('classes'):
                    print(f"   [DEBUG SYNTHESIS]   First class: {summary['classes'][0]}")

            if isinstance(summary, dict):
                summaries_text += f"\n\n## {file_path}\n"
                summaries_text += f"Key Features: {', '.join(summary.get('key_features', []))}\n"
                summaries_text += f"Architecture: {summary.get('architectural_insights', '')}\n"

                # Include function/class info with line numbers
                # IMPORTANT: Make it crystal clear which file these line numbers belong to
                functions = summary.get('functions', [])
                classes = summary.get('classes', [])
                if functions:
                    summaries_text += f"Functions in {file_path}:\n"
                    for f in functions[:5]:
                        func_name = f.get('name', 'unknown')
                        func_line = f.get('line', '?')
                        summaries_text += f"  - {func_name} at line {func_line}\n"
                    print(f"   [DEBUG SYNTHESIS]   Generated {len(functions[:5])} function refs for {file_path}")
                if classes:
                    summaries_text += f"Classes in {file_path}:\n"
                    for c in classes[:5]:
                        class_name = c.get('name', 'unknown')
                        class_line = c.get('line', '?')
                        summaries_text += f"  - {class_name} at line {class_line}\n"
                    print(f"   [DEBUG SYNTHESIS]   Generated {len(classes[:5])} class refs for {file_path}")

                # Include test information if available (test-aware analysis)
                test_info = summary.get('test_info', {})
                if test_info.get('has_tests'):
                    summaries_text += f"\nTest Coverage: {test_info.get('test_count', 0)} tests\n"

                    usage_examples = test_info.get('usage_examples', [])
                    if usage_examples:
                        summaries_text += "Usage Examples:\n"
                        for ex in usage_examples[:3]:
                            summaries_text += f"  - {ex}\n"

                    edge_cases = test_info.get('edge_cases', [])
                    if edge_cases:
                        summaries_text += "Edge Cases Tested:\n"
                        for ec in edge_cases[:3]:
                            summaries_text += f"  - {ec}\n"

        # Prepare insights text
        insights_text = ""
        for insight in insights[:20]:  # Limit insights
            content = insight.get('content', '')
            if content:
                insights_text += f"- {content}\n"

        # Prepare patterns text (NEW)
        patterns_text = ""
        if detected_patterns:
            patterns_text = "\n\nDETECTED DESIGN PATTERNS:\n"
            for pattern in detected_patterns:
                patterns_text += f"- {pattern.get('name', 'Unknown')}: {pattern.get('description', '')}\n"
                if pattern.get('files'):
                    patterns_text += f"  Files: {', '.join(pattern['files'][:3])}\n"

        # Prepare architectural summary (NEW)
        arch_text = ""
        if architectural_analysis:
            arch_text = f"\n\nARCHITECTURAL SUMMARY:\n{architectural_analysis.architectural_summary}\n"
            if architectural_analysis.entry_points:
                arch_text += f"\nEntry Points: {', '.join([e.name for e in architectural_analysis.entry_points[:3]])}\n"
            if architectural_analysis.core_abstractions:
                arch_text += f"Core Abstractions: {', '.join([a.name for a in architectural_analysis.core_abstractions[:3]])}\n"

        # Prepare execution paths (NEW - Life-of-X integration)
        paths_text = ""
        if execution_paths:
            paths_text = "\n\nEXECUTION PATHS TRACED:\n"
            for i, path in enumerate(execution_paths[:3], 1):  # Limit to 3 paths
                paths_text += f"\nPath {i}: {path.get('name', 'Unknown flow')}\n"
                steps = path.get('steps', [])
                for step in steps[:10]:  # Limit to 10 steps per path
                    paths_text += f"  → {step.get('function', 'unknown')} ({step.get('file', '')}:{step.get('line', '?')})\n"
                if len(steps) > 10:
                    paths_text += f"  ... ({len(steps) - 10} more steps)\n"

        # Build list of valid file paths for the LLM to reference
        file_paths_list = "\n".join([f"  - {fp}" for fp in key_files])

        # DEBUG: Show snippet of summaries_text that will go in prompt
        print(f"   [DEBUG SYNTHESIS] summaries_text snippet (first 500 chars):")
        print(f"   {summaries_text[:500]}")
        print(f"   [DEBUG SYNTHESIS] Total summaries_text length: {len(summaries_text)} chars")

        prompt = f"""Generate a comprehensive technical narrative answering this question:

QUESTION: "{question}"

You have analyzed {len(file_summaries)} files and gathered the following insights:

ANALYZED FILE PATHS (use these exact paths in your narrative):
{file_paths_list}

KEY FILES ANALYZED:
{summaries_text}

INSIGHTS:
{insights_text}
{patterns_text}
{arch_text}
{paths_text}

TASK: Write a detailed technical narrative that explains HOW the system works, not just WHAT it does.

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
- If execution paths are provided, MUST trace the flow step-by-step
- AVOID generic statements without code references
- AVOID just listing files without explaining their role

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

    def _calculate_synthesis_confidence(self,
                                       narrative: str,
                                       file_summaries: Dict[str, Any],
                                       target_min: int,
                                       target_max: int) -> float:
        """Calculate confidence score for synthesis"""
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        base_confidence = thresholds.get('base_confidence', 0.6)
        confidence_increment = thresholds.get('confidence_increment', 0.05)
        max_confidence = thresholds.get('max_confidence', 0.9)

        confidence = base_confidence

        # Check word count (±20% of target)
        word_count = len(narrative.split())
        # Get synthesis quality thresholds from config
        synthesis_thresholds = self.config.get('agents', {}).get('synthesis_thresholds', {})
        word_count_tolerance = synthesis_thresholds.get('word_count_tolerance', 0.8)
        line_refs_high = synthesis_thresholds.get('line_refs_high', 5)
        line_refs_medium = synthesis_thresholds.get('line_refs_medium', 3)
        path_refs_high = synthesis_thresholds.get('path_refs_high', 5)
        path_refs_medium = synthesis_thresholds.get('path_refs_medium', 3)
        code_blocks_min = synthesis_thresholds.get('code_blocks_min', 4)
        sections_min = synthesis_thresholds.get('sections_min', 3)

        target_mid = (target_min + target_max) / 2
        if target_min <= word_count <= target_max:
            confidence += confidence_increment * 2
        elif word_count >= target_mid * word_count_tolerance:
            confidence += confidence_increment

        # Single-pass regex matching for performance (optimized for large narratives)
        # Count all pattern types in one iteration instead of multiple findall() calls
        line_refs = 0
        path_refs = 0
        code_blocks = 0
        sections = 0

        for match in self.validation_pattern.finditer(narrative):
            if match.group('line_ref'):
                line_refs += 1
            elif match.group('path_ref'):
                path_refs += 1
            elif match.group('code_block'):
                code_blocks += 1
            elif match.group('section'):
                sections += 1

        # Evaluate line references
        if line_refs >= line_refs_high:
            confidence += confidence_increment * 2
        elif line_refs >= line_refs_medium:
            confidence += confidence_increment

        # Evaluate file path references
        if path_refs >= path_refs_high:
            confidence += confidence_increment * 2
        elif path_refs >= path_refs_medium:
            confidence += confidence_increment

        # Evaluate code examples
        if code_blocks >= code_blocks_min:
            confidence += confidence_increment

        # Evaluate structural markers
        if sections >= sections_min:
            confidence += confidence_increment

        return min(confidence, max_confidence)

    def evaluate_completeness(self, narrative: str, question: str, file_summaries: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to evaluate if narrative fully answers the question

        Returns:
            Dict with completeness score and missing components
        """
        try:
            print("🔍 [SYNTHESIS] Evaluating completeness...")

            prompt = f"""Evaluate if this technical narrative fully answers the question.

QUESTION: "{question}"

NARRATIVE:
{narrative[:2000]}  # First 2000 chars

TASK: Assess completeness and identify missing components.

Respond with JSON only:
{{
    "completeness_score": 0.0-1.0,
    "fully_answers": true/false,
    "missing_components": ["component1", "component2"],
    "reasoning": "brief explanation"
}}

If completeness_score < 0.7, list specific missing components.
If >= 0.7, return empty missing_components array."""

            response = self.llm.generate_fast(prompt, "You are a technical documentation evaluator.")

            if response.get('success'):
                content = response.get('content', '').strip()
                try:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        result = json.loads(content[start:end])
                        print(f"✅ [SYNTHESIS] Completeness: {result.get('completeness_score', 0):.2f}")
                        return result
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            print(f"⚠️ [SYNTHESIS] Completeness evaluation failed: {e}")

        # Fallback
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        return {
            'completeness_score': thresholds.get('base_confidence', 0.6),
            'fully_answers': True,
            'missing_components': [],
            'reasoning': 'Evaluation unavailable'
        }

    def _detect_patterns_from_kb(self, file_summaries: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect design patterns using KB (if available) or from file summaries.

        NEW: Integrates pattern detection into synthesis so narratives mention
        patterns like "The system uses Factory pattern for ..."
        """
        patterns = []

        # Try KB pattern detection first
        if self.kb and hasattr(self.kb, 'detect_patterns'):
            try:
                file_paths = list(file_summaries.keys())
                kb_patterns = self.kb.detect_patterns(file_paths)
                if kb_patterns:
                    print(f"   🎨 Detected {len(kb_patterns)} patterns from KB")
                    return kb_patterns
            except Exception as e:
                print(f"   ⚠️ KB pattern detection failed: {e}")

        # Fallback: Detect patterns from file summaries
        pattern_keywords = {
            'Singleton Pattern': ['singleton', 'single instance', '_instance = None'],
            'Factory Pattern': ['factory', 'create_', 'make_', 'builder'],
            'Observer Pattern': ['observer', 'listener', 'subscribe', 'event'],
            'Strategy Pattern': ['strategy', 'algorithm', 'policy'],
            'Decorator Pattern': ['@decorator', 'wrapper', '@wraps'],
            'Repository Pattern': ['repository', 'data access', 'dao'],
            'MVC Pattern': ['model', 'view', 'controller'],
        }

        pattern_files = {}
        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            content = summary.get('content', '').lower()
            features = ' '.join(str(f).lower() for f in summary.get('key_features', []))
            insights = summary.get('architectural_insights', '').lower()
            combined = f"{content} {features} {insights}"

            for pattern_name, keywords in pattern_keywords.items():
                if any(kw in combined for kw in keywords):
                    if pattern_name not in pattern_files:
                        pattern_files[pattern_name] = []
                    pattern_files[pattern_name].append(file_path)

        # Convert to pattern dicts
        for pattern_name, files in pattern_files.items():
            if len(files) >= 1:
                patterns.append({
                    'name': pattern_name,
                    'description': f"Detected in {len(files)} file(s)",
                    'files': files[:3],
                    'confidence': min(0.5 + len(files) * 0.1, 0.9)
                })

        if patterns:
            print(f"   🎨 Detected {len(patterns)} patterns from summaries")

        return patterns

    def _trace_execution_paths(self,
                               question: str,
                               file_summaries: Dict[str, Any],
                               architectural_analysis=None) -> List[Dict[str, Any]]:
        """
        Trace execution paths for "how does X work?" questions.

        NEW: Uses KB's Life-of-X layer to trace call chains and data flow,
        providing step-by-step execution paths in narratives.
        """
        paths = []

        # Try KB execution path tracing first
        if self.kb and hasattr(self.kb, 'trace_execution_path'):
            try:
                print("   🔄 Tracing execution paths from KB...")

                # Extract potential entry function names from question and architectural analysis
                entry_functions = self._extract_entry_functions(question, architectural_analysis)

                for entry_func in entry_functions[:3]:  # Limit to 3 entry points
                    try:
                        # Trace execution path from entry function
                        max_depth = self.config.get('agents', {}).get('max_execution_trace_depth', 10)
                        traced_path = self.kb.trace_execution_path(
                            entry_point=entry_func,
                            max_depth=max_depth
                        )

                        if traced_path and traced_path.get('steps'):
                            paths.append({
                                'name': f"Flow from {entry_func}",
                                'entry_point': entry_func,
                                'steps': traced_path.get('steps', []),
                                'depth': len(traced_path.get('steps', []))
                            })
                    except Exception as e:
                        print(f"   ⚠️ Failed to trace path from {entry_func}: {e}")

                if paths:
                    print(f"   ✅ Traced {len(paths)} execution paths")
                    return paths

            except Exception as e:
                print(f"   ⚠️ KB execution path tracing failed: {e}")

        # Fallback: Extract call sequences from file summaries
        print("   🔄 Extracting call sequences from summaries...")
        paths = self._extract_call_sequences_from_summaries(question, file_summaries)

        if paths:
            print(f"   ✅ Extracted {len(paths)} call sequences from code")

        return paths

    def _extract_entry_functions(self, question: str, architectural_analysis=None) -> List[str]:
        """Extract potential entry function names from question and architecture"""
        entry_functions = []

        # From architectural analysis
        if architectural_analysis and architectural_analysis.entry_points:
            for entry_point in architectural_analysis.entry_points:
                # Extract function names from details
                if 'functions' in entry_point.details:
                    entry_functions.extend(entry_point.details['functions'][:2])

        # From question keywords
        # Look for function-like words in question
        words = re.findall(r'\b[a-z_][a-z0-9_]*\b', question.lower())
        relevant_words = [w for w in words if len(w) > 4 and w not in ['does', 'work', 'what', 'where', 'when', 'which']]

        # Common entry point patterns
        entry_patterns = ['main', 'run', 'execute', 'start', 'init', 'handle', 'process']
        for word in relevant_words:
            for pattern in entry_patterns:
                if pattern in word:
                    entry_functions.append(word)

        return list(set(entry_functions))[:5]  # Deduplicate and limit

    def _extract_call_sequences_from_summaries(self,
                                               question: str,
                                               file_summaries: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fallback: Extract call sequences by analyzing function calls in code.

        This is less accurate than KB tracing but provides some flow information.
        """
        sequences = []

        # Look for function call patterns in code
        call_pattern = re.compile(r'(\w+)\s*\([^)]*\)')  # function_name(args)

        for file_path, summary in file_summaries.items():
            if not isinstance(summary, dict):
                continue

            content = summary.get('content', '')
            functions = summary.get('functions', [])

            # For each function, extract its call sequence
            for func_info in functions[:3]:  # Limit to 3 functions per file
                if not isinstance(func_info, dict):
                    continue

                func_name = func_info.get('name', '')
                if not func_name:
                    continue

                # Find function calls within this function (simplified)
                # In real implementation, would need to parse function body
                called_functions = call_pattern.findall(content)
                if called_functions:
                    steps = [
                        {
                            'function': func_name,
                            'file': file_path,
                            'line': func_info.get('line', 0)
                        }
                    ]

                    # Add called functions (up to 5)
                    for called_func in called_functions[:5]:
                        if called_func != func_name:  # Avoid self-references
                            steps.append({
                                'function': called_func,
                                'file': file_path,  # Simplified - might be in different file
                                'line': '?'
                            })

                    if len(steps) > 1:  # At least 2 steps (caller + callee)
                        sequences.append({
                            'name': f"Calls from {func_name}",
                            'entry_point': func_name,
                            'steps': steps,
                            'depth': len(steps)
                        })

        return sequences[:3]  # Limit to 3 sequences
