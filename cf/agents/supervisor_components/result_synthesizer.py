"""
Result Synthesizer

Handles LLM synthesis and result generation for SupervisorAgent.
Converts specialist agent results into comprehensive narratives.
"""

import json
from typing import Dict, List, Any

from cf.utils.llm_parser import LLMResponseParser


class ResultSynthesizer:
    """
    Synthesizes specialist results into comprehensive narratives using LLM.

    Responsibilities:
    - Data preparation for synthesis
    - LLM prompt building
    - Result generation
    - Partial/failed response handling
    """

    def __init__(self, config: Dict[str, Any], logger, call_llm_func):
        """
        Initialize result synthesizer.

        Args:
            config: Configuration dictionary
            logger: Logger instance
            call_llm_func: Function to call LLM
        """
        self.config = config
        self.logger = logger
        self.call_llm = call_llm_func

    def generate_results(self, question: str, specialist_results: Dict[str, Any],
                        agents_completed: List[str], all_insights: List[Dict[str, Any]],
                        pass_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate final consolidated answer using LLM synthesis.

        Args:
            question: User question
            specialist_results: Results from specialist agents
            agents_completed: List of completed agents
            all_insights: All collected insights
            pass_results: Multi-pass results

        Returns:
            Final result dictionary
        """
        self.logger.verbose_synthesis("Consolidating results with LLM...")
        self.logger.verbose_separator()

        # Check if all agents failed
        all_agents_failed = all(
            not specialist_results.get(agent, {}).get('success', False)
            for agent in agents_completed
        )

        if all_agents_failed and len(agents_completed) > 0:
            self.logger.verbose("⚠️ All agents failed - generating error response", "⚠️")
            return self.generate_all_agents_failed_response(
                question, specialist_results, agents_completed
            )

        # Prepare data for LLM synthesis
        synthesis_data = self.prepare_synthesis_data(
            question, specialist_results, agents_completed, all_insights
        )

        # Use LLM to generate comprehensive narrative and title
        llm_response = self.synthesize_with_llm(question, synthesis_data)

        if not llm_response.get('success'):
            # Fallback: generate response from partial data if available
            if len(all_insights) > 0:
                return self.generate_partial_response(
                    question, synthesis_data, specialist_results,
                    agents_completed, all_insights
                )

            return {
                'success': False,
                'error': 'Failed to synthesize results with LLM',
                'question': question,
                'raw_data': synthesis_data
            }

        # Extract title and narrative from LLM response
        synthesis = llm_response.get('synthesis', {})
        thresholds = self.config.get('agents', {}).get('thresholds', {})

        # Format result with comprehensive output
        result = {
            'success': True,
            'question': question,
            'title': synthesis.get('title', 'Analysis Results'),
            'narrative': synthesis.get('narrative', 'Analysis completed.'),
            'narrative_type': synthesis.get('narrative_type', 'standard'),
            'confidence': synthesis.get('confidence', thresholds.get('medium_confidence', 0.7)),
            'insights': all_insights,
            'agents_consulted': agents_completed,
            'specialist_results': specialist_results,
            'agent': 'supervisor',
            'total_insights': len(all_insights)
        }

        # Log multi-pass completion summary
        total_passes = len([k for k in pass_results.keys() if k.startswith('pass_')])
        if total_passes > 1:
            self.logger.verbose(
                f"🏁 Multi-pass analysis complete: {total_passes} passes, {len(all_insights)} total insights", "✅"
            )

        # Log insights integration if verbose
        if len(all_insights) > 0:
            self.logger.verbose_result(True, f"Integrated {len(all_insights)} insights into narrative")

        return result

    def prepare_synthesis_data(self, question: str, specialist_results: Dict[str, Any],
                               agents_completed: List[str],
                               all_insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Prepare data summary for LLM synthesis.

        Args:
            question: User question
            specialist_results: Results from specialist agents
            agents_completed: List of completed agents
            all_insights: All collected insights

        Returns:
            Synthesis data dictionary
        """
        data = {
            'question': question,
            'agents_consulted': agents_completed,
            'total_insights': len(all_insights),
            'specialist_summaries': {},
            'analyzed_files': []  # Track which files were actually analyzed
        }

        # Summarize each specialist's findings
        for agent_type in agents_completed:
            result = specialist_results.get(agent_type, {})
            if result.get('success'):
                thresholds = self.config.get('agents', {}).get('thresholds', {})
                data['specialist_summaries'][agent_type] = {
                    'success': True,
                    'insights_count': len(result.get('insights', [])),
                    'key_findings': [
                        insight.get('content', '') for insight in result.get('insights', [])[:3]
                    ],
                    'confidence': result.get('confidence', thresholds.get('partial_confidence', 0.5))
                }

                # Extract analyzed file list from code agent for anti-hallucination
                if agent_type == 'code' and 'analyzed_file_list' in result:
                    data['analyzed_files'] = result['analyzed_file_list']
            else:
                data['specialist_summaries'][agent_type] = {
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }

        return data

    def synthesize_with_llm(self, question: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to synthesize comprehensive narrative from specialist results.

        Args:
            question: User question
            data: Synthesis data

        Returns:
            LLM synthesis result
        """
        # Build prompt for LLM synthesis
        prompt = self.build_synthesis_prompt(question, data)

        system_prompt = """You are an expert technical writer and code analyst. Your job is to synthesize information from multiple specialist agents into a comprehensive, well-structured response.

Return a JSON response with:
- title: Engaging title for the answer (use "Life of X" format if the question is about understanding how something works)
- narrative: Comprehensive narrative combining all specialist insights
- narrative_type: "life_of_x", "comparison", "analysis", or "standard"
- confidence: Overall confidence score (0.0-1.0)

🚨 CRITICAL ANTI-HALLUCINATION RULES:
1. You MUST ONLY reference files that appear in the "ANALYZED FILES" section of the prompt
2. You MUST NOT invent or fabricate file names like "application_controller.py", "validation.py", "workflow.py"
3. You MUST NOT reference files that were not analyzed (e.g., generic names like "models.py", "views.py" unless explicitly listed)
4. If the analyzed files don't fully answer the question, state what's missing rather than hallucinate
5. Every file path in your narrative MUST be from the analyzed files list
6. If you cannot provide a complete answer with the given analyzed files, say so explicitly

For "Life of X" responses, structure the narrative like this:
🏗️ **Architectural Overview:** Write a comprehensive 4-5 sentence paragraph that tells the complete story as a "Life of X" narrative describing the journey and flow of the feature from start to finish. Tell the story like: "When [trigger/input occurs], the journey begins with [entry point/component] receiving/handling this [input]. The [system/framework] relies on [underlying technology/framework] to [core process]. The process is initiated when [specific condition]. The entry point for handling [feature] is typically [specific component/class] defined in a file like '[actual_filename.py]'. This [component] uses [specific mechanism like decorators/methods/patterns] to [specific action]. For example, when [specific scenario], the [input] is directed to [specific function/method] [with actual code pattern like @decorator or function_name()]. This [mechanism] is responsible for [specific responsibility]. The actual [feature] logic is handled by [specific component/module], which leverages [specific technology/technique]. Once [condition is met], the corresponding [handler/processor] is executed. The [output/result] is then [processed/transformed] through [specific steps], completing the lifecycle." Include:
- Specific file names, class names, method names, and actual code patterns from the codebase analysis
- Real implementation details and mechanisms found by the agents
- Actual technical frameworks and design patterns used
- Concrete examples with code snippets, decorators, or function calls discovered

🛤️ **Technical Flow:** Break down the process into detailed technical steps:
   **1. Step Name:** Detailed description with technical specifics, file names, function calls
   **2. Step Name:** Detailed description with technical specifics, file names, function calls
   [Continue with comprehensive technical details for each step]

🎯 **Key Components:** List the essential pieces with detailed explanations:
   • **Component Name:** Comprehensive explanation of what it does, how it works, and its role in the system
   [Include technical implementation details for each component]

💻 **Code Examples:** Include specific implementation details from the codebase:
   • In filename.py:line: 'actual code snippet' - detailed explanation of what this does
   [Use actual code examples found by the agents]

🔧 **Usage Examples:** Include practical usage examples and patterns:
   • Common usage patterns and how developers typically implement the feature
   • Real-world examples from the codebase showing how the feature is used
   • Configuration examples, initialization patterns, or typical workflows
   • Best practices and recommended approaches found in the documentation or code

The Architecture & Flow section should be particularly rich - it's the heart of the "Life of X" narrative. Use ALL available insights from code analysis, documentation, and web research to create a thorough, engaging technical story."""

        try:
            llm_response = self.call_llm(prompt, system_prompt)

            if llm_response.get('success'):
                content = llm_response.get('content', '')

                # Try to parse JSON response
                try:
                    synthesis = LLMResponseParser.extract_json(content)
                    if synthesis:
                        return {'success': True, 'synthesis': synthesis}
                    else:
                        raise ValueError("No JSON found")

                except (json.JSONDecodeError, ValueError):
                    # Fallback: treat as plain text narrative
                    thresholds = self.config.get('agents', {}).get('thresholds', {})
                    return {
                        'success': True,
                        'synthesis': {
                            'title': 'Analysis Results',
                            'narrative': content,
                            'narrative_type': 'standard',
                            'confidence': thresholds.get('medium_confidence', 0.7)
                        }
                    }

            return {'success': False, 'error': 'LLM call failed'}

        except Exception as e:
            return {'success': False, 'error': f'Synthesis failed: {str(e)}'}

    def build_synthesis_prompt(self, question: str, data: Dict[str, Any]) -> str:
        """
        Build prompt for LLM synthesis.

        Args:
            question: User question
            data: Synthesis data

        Returns:
            Synthesis prompt string
        """
        # Build analyzed files section for anti-hallucination
        analyzed_files_section = ""
        if data.get('analyzed_files'):
            analyzed_files_section = "\n\n**ANALYZED FILES (only reference these):**\n"
            for file_path in data['analyzed_files']:
                analyzed_files_section += f"- {file_path}\n"

        prompt = f"""Please synthesize the following analysis results into a comprehensive answer:

**Question:** {question}

**Agents Consulted:** {', '.join(data['agents_consulted'])}
**Total Insights:** {data['total_insights']}
{analyzed_files_section}

**Specialist Findings:**
"""

        # Add each specialist's summary
        for agent_type, summary in data.get('specialist_summaries', {}).items():
            prompt += f"\n**{agent_type.upper()} Agent:**\n"
            if summary.get('success'):
                prompt += f"- Status: ✅ Success\n"
                prompt += f"- Insights: {summary.get('insights_count', 0)}\n"
                prompt += f"- Confidence: {summary.get('confidence', 0):.1%}\n"
                prompt += "- Key Findings:\n"
                for finding in summary.get('key_findings', []):
                    if finding:
                        prompt += f"  • {finding[:200]}{'...' if len(finding) > 200 else ''}\n"
            else:
                prompt += f"- Status: ❌ Failed\n"
                prompt += f"- Error: {summary.get('error', 'Unknown')}\n"

        prompt += """

Please create a comprehensive, well-structured response that:
1. Synthesizes insights from all successful agents
2. Provides a clear, engaging title
3. Uses appropriate narrative type (life_of_x for "how does X work" questions)
4. Only references files from the ANALYZED FILES list above
5. Includes specific technical details, file names, and code patterns from the findings
6. Maintains high confidence in the synthesis"""

        return prompt

    def generate_all_agents_failed_response(self, question: str,
                                           specialist_results: Dict[str, Any],
                                           agents_completed: List[str]) -> Dict[str, Any]:
        """
        Generate response when all agents failed.

        Args:
            question: User question
            specialist_results: Results from specialist agents
            agents_completed: List of completed agents

        Returns:
            Error response dictionary
        """
        # Collect error messages
        errors = []
        for agent_type in agents_completed:
            result = specialist_results.get(agent_type, {})
            error = result.get('error', 'Unknown error')
            timed_out = result.get('timed_out', False)
            status = "timed out" if timed_out else "failed"
            errors.append(f"- {agent_type.title()} agent {status}: {error}")

        error_summary = "\n".join(errors)

        narrative = f"""I encountered errors while trying to analyze your question: "{question}"

**Analysis Errors:**
{error_summary}

**What happened:**
All specialist agents ({', '.join(agents_completed)}) encountered issues during analysis.

**Possible causes:**
1. Repository issues (large files, access problems, corrupted files)
2. Timeout due to complex analysis or slow processing
3. Temporary infrastructure issues
4. Question complexity exceeding processing limits

**Recommendations:**
- Try rephrasing your question to be more specific
- Check if the repository is accessible and not corrupted
- Try again in a moment (if temporary issue)
- For large repositories, try focusing on a specific component
"""
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        return {
            'success': False,
            'question': question,
            'title': 'Analysis Failed - All Agents Encountered Errors',
            'narrative': narrative,
            'confidence': thresholds.get('error_confidence', 0.2),
            'insights': [],
            'agents_consulted': agents_completed,
            'specialist_results': specialist_results,
            'error': 'All agents failed',
            'agent': 'supervisor'
        }

    def generate_partial_response(self, question: str, synthesis_data: Dict[str, Any],
                                  specialist_results: Dict[str, Any],
                                  agents_completed: List[str],
                                  all_insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate response from partial insights when LLM synthesis fails.

        Args:
            question: User question
            synthesis_data: Synthesis data
            specialist_results: Results from specialist agents
            agents_completed: List of completed agents
            all_insights: All collected insights

        Returns:
            Partial response dictionary
        """
        # Build narrative from insights
        narrative_parts = [
            f"**Partial Analysis** (LLM synthesis failed, showing raw insights)\n",
            f"Question: {question}\n"
        ]

        # Add successful agent results
        for agent_type, summary in synthesis_data.get('specialist_summaries', {}).items():
            if summary.get('success'):
                narrative_parts.append(f"\n**{agent_type.title()} Agent Findings:**")
                for finding in summary.get('key_findings', []):
                    narrative_parts.append(f"- {finding}")

        # Add top insights
        if len(all_insights) > 0:
            narrative_parts.append(f"\n**Key Insights ({len(all_insights)} total):**")
            sorted_insights = sorted(all_insights, key=lambda x: x.get('confidence', 0), reverse=True)
            for i, insight in enumerate(sorted_insights[:10], 1):
                content = insight.get('content', '')
                confidence = insight.get('confidence', 0)
                narrative_parts.append(f"{i}. {content} (confidence: {confidence:.1%})")

        narrative = "\n".join(narrative_parts)

        thresholds = self.config.get('agents', {}).get('thresholds', {})
        return {
            'success': True,
            'question': question,
            'title': 'Partial Analysis Results',
            'narrative': narrative,
            'confidence': thresholds.get('partial_confidence', 0.5),
            'insights': all_insights,
            'agents_consulted': agents_completed,
            'specialist_results': specialist_results,
            'agent': 'supervisor',
            'partial': True
        }
