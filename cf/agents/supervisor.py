"""
SupervisorAgent for CodeFusion

Orchestrates all specialist agents and uses LLM to generate comprehensive narratives.
Resets state for each new question.
"""

import time
from typing import Dict, List, Any
from cf.agents.base import BaseAgent


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that consults all specialists and synthesizes responses with LLM.
    """
    
    def __init__(self, repo_path: str, config: Dict[str, Any]):
        super().__init__(repo_path, config, "supervisor")
        
        # Specialist agents (persistent across questions)
        self._code_agent = None
        self._docs_agent = None
        self._web_agent = None
        
        # Question-specific state (reset each question)
        self._reset_question_state()
    
    def _reset_question_state(self):
        """Reset state for new question"""
        self.agents_to_consult = ['code', 'docs', 'web']
        self.agents_completed = []
        self.all_insights = []
        self.specialist_results = {}
        self.iteration = 0
        self.actions_taken = []
        self.results = {}
        self.insights = []
    
    def analyze(self, question: str) -> Dict[str, Any]:
        """
        Override analyze to reset state for each new question
        """
        # Start timing
        start_time = time.time()
        
        # Reset state for new question
        self._reset_question_state()
        
        # Start new tracing session
        self.session_id = self.tracer.start_session(f"supervisor_q_{int(time.time())}")
        
        # Call parent analyze method
        result = super().analyze(question)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Add timing information to result
        if isinstance(result, dict):
            result['execution_time'] = execution_time
        
        return result
    
    def _analyze_step(self, question: str) -> str:
        """Execute one analysis step - consult next available agent"""
        
        # Log initial processing
        if self.iteration == 1:
            self.logger.verbose(f"Processing: {question}", "📝")
            self.logger.verbose("Analyzing question and building context...", "🧠")
            self.logger.verbose("Coordinating multiple specialized agents...", "🤖")
        
        # Consult agents in order
        for agent_type in self.agents_to_consult:
            if agent_type not in self.agents_completed:
                return self._consult_agent(agent_type, question)
        
        return "all_agents_consulted"
    
    def _consult_agent(self, agent_type: str, question: str) -> str:
        """Consult a specific specialist agent"""
        
        if agent_type == 'code':
            return self._consult_code_agent(question)
        elif agent_type == 'docs':
            return self._consult_docs_agent(question)
        elif agent_type == 'web':
            return self._consult_web_agent(question)
        else:
            return f"unknown_agent_{agent_type}"
    
    def _consult_code_agent(self, question: str) -> str:
        """Get insights from code analysis specialist"""
        self.logger.verbose("Running code analysis agent...", "🔍")
        
        if not self._code_agent:
            from cf.agents.code import CodeAgent
            self._code_agent = CodeAgent(self.repo_path, self.config)
        
        try:
            result = self._code_agent.analyze(question)
            self.specialist_results['code'] = result
            
            if result.get('success'):
                self.all_insights.extend(result.get('insights', []))
                self.logger.verbose_result(True, "Code analysis completed")
            else:
                self.logger.verbose_result(False, f"Code analysis failed: {result.get('error', 'Unknown error')}")
                
            self.agents_completed.append('code')
            return "consulted_code_agent"
            
        except Exception as e:
            self.logger.error(f"Code agent failed: {str(e)}")
            self.specialist_results['code'] = {'success': False, 'error': str(e)}
            self.agents_completed.append('code')
            self.logger.verbose_result(False, f"Code agent exception: {str(e)}")
            return "code_agent_failed"
    
    def _consult_docs_agent(self, question: str) -> str:
        """Get insights from documentation specialist"""
        self.logger.verbose("Running documentation agent...", "📚")
        
        if not self._docs_agent:
            from cf.agents.docs import DocsAgent
            self._docs_agent = DocsAgent(self.repo_path, self.config)
        
        try:
            result = self._docs_agent.analyze(question)
            self.specialist_results['docs'] = result
            
            if result.get('success'):
                self.all_insights.extend(result.get('insights', []))
                self.logger.verbose_result(True, "Documentation analysis completed")
            else:
                self.logger.verbose_result(False, f"Documentation analysis failed: {result.get('error', 'Unknown error')}")
                
            self.agents_completed.append('docs')
            return "consulted_docs_agent"
            
        except Exception as e:
            self.logger.error(f"Docs agent failed: {str(e)}")
            self.specialist_results['docs'] = {'success': False, 'error': str(e)}
            self.agents_completed.append('docs')
            self.logger.verbose_result(False, f"Docs agent exception: {str(e)}")
            return "docs_agent_failed"
    
    def _consult_web_agent(self, question: str) -> str:
        """Get insights from web search specialist"""
        self.logger.verbose("Running web search agent...", "🌐")
        
        if not self._web_agent:
            from cf.agents.web import WebAgent
            self._web_agent = WebAgent(self.repo_path, self.config)
        
        try:
            result = self._web_agent.analyze(question)
            self.specialist_results['web'] = result
            
            if result.get('success'):
                self.all_insights.extend(result.get('insights', []))
                self.logger.verbose_result(True, "Web search completed")
            else:
                self.logger.verbose_result(False, f"Web search failed: {result.get('error', 'Unknown error')}")
                
            self.agents_completed.append('web')
            return "consulted_web_agent"
            
        except Exception as e:
            self.logger.error(f"Web agent failed: {str(e)}")
            self.specialist_results['web'] = {'success': False, 'error': str(e)}
            self.agents_completed.append('web')
            self.logger.verbose_result(False, f"Web agent exception: {str(e)}")
            return "web_agent_failed"
    
    def _is_analysis_complete(self, question: str) -> bool:
        """Check if all specialist agents have been consulted"""
        return len(self.agents_completed) >= len(self.agents_to_consult)
    
    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate final consolidated answer using LLM synthesis"""
        
        self.logger.verbose_synthesis("Consolidating results with LLM...")
        self.logger.verbose_separator()
        
        # Prepare data for LLM synthesis
        synthesis_data = self._prepare_synthesis_data(question)
        
        # Use LLM to generate comprehensive narrative and title
        llm_response = self._synthesize_with_llm(question, synthesis_data)
        
        if not llm_response.get('success'):
            return {
                'success': False,
                'error': 'Failed to synthesize results with LLM',
                'question': question,
                'raw_data': synthesis_data
            }
        
        # Extract title and narrative from LLM response
        synthesis = llm_response.get('synthesis', {})
        
        # Format result with comprehensive output
        result = {
            'success': True,
            'question': question,
            'title': synthesis.get('title', 'Analysis Results'),
            'narrative': synthesis.get('narrative', 'Analysis completed.'),
            'narrative_type': synthesis.get('narrative_type', 'standard'),
            'confidence': synthesis.get('confidence', 0.7),
            'insights': self.all_insights,
            'agents_consulted': self.agents_completed,
            'specialist_results': self.specialist_results,
            'agent': 'supervisor',
            'total_insights': len(self.all_insights)
        }
        
        # Log insights integration if verbose
        if len(self.all_insights) > 0:
            self.logger.verbose_result(True, f"Integrated {len(self.all_insights)} insights into narrative")
        
        return result
    
    def _prepare_synthesis_data(self, question: str) -> Dict[str, Any]:
        """Prepare data summary for LLM synthesis"""
        
        data = {
            'question': question,
            'agents_consulted': self.agents_completed,
            'total_insights': len(self.all_insights),
            'specialist_summaries': {}
        }
        
        # Summarize each specialist's findings
        for agent_type in self.agents_completed:
            result = self.specialist_results.get(agent_type, {})
            if result.get('success'):
                data['specialist_summaries'][agent_type] = {
                    'success': True,
                    'insights_count': len(result.get('insights', [])),
                    'key_findings': [insight.get('content', '') for insight in result.get('insights', [])[:3]],
                    'confidence': result.get('confidence', 0.5)
                }
            else:
                data['specialist_summaries'][agent_type] = {
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }
        
        return data
    
    def _synthesize_with_llm(self, question: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to synthesize comprehensive narrative from specialist results"""
        
        # Build prompt for LLM synthesis
        prompt = self._build_synthesis_prompt(question, data)
        
        system_prompt = """You are an expert technical writer and code analyst. Your job is to synthesize information from multiple specialist agents into a comprehensive, well-structured response.

Return a JSON response with:
- title: Engaging title for the answer (use "Life of X" format if the question is about understanding how something works)
- narrative: Comprehensive narrative combining all specialist insights
- narrative_type: "life_of_x", "comparison", "analysis", or "standard" 
- confidence: Overall confidence score (0.0-1.0)

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
                import json
                content = llm_response.get('content', '')
                
                # Try to parse JSON response
                try:
                    if content.startswith('{'):
                        synthesis = json.loads(content)
                    else:
                        # Extract JSON from markdown
                        start = content.find('{')
                        end = content.rfind('}') + 1
                        if start >= 0 and end > start:
                            synthesis = json.loads(content[start:end])
                        else:
                            raise ValueError("No JSON found")
                    
                    return {'success': True, 'synthesis': synthesis}
                    
                except json.JSONDecodeError:
                    # Fallback: treat as plain text narrative
                    return {
                        'success': True,
                        'synthesis': {
                            'title': 'Analysis Results',
                            'narrative': content,
                            'narrative_type': 'standard',
                            'confidence': 0.7
                        }
                    }
            
            return {'success': False, 'error': 'LLM call failed'}
            
        except Exception as e:
            return {'success': False, 'error': f'Synthesis failed: {str(e)}'}
    
    def _build_synthesis_prompt(self, question: str, data: Dict[str, Any]) -> str:
        """Build prompt for LLM synthesis"""
        
        prompt = f"""Please synthesize the following analysis results into a comprehensive answer:

**User Question:** {question}

**Analysis Summary:**
- Agents consulted: {', '.join(data['agents_consulted'])}
- Total insights gathered: {data['total_insights']}

**Specialist Results:**
"""
        
        for agent_type, summary in data['specialist_summaries'].items():
            if summary['success']:
                prompt += f"\n**{agent_type.title()} Agent:**"
                prompt += f"\n- Found {summary['insights_count']} insights"
                prompt += f"\n- Confidence: {summary['confidence']:.1%}"
                prompt += f"\n- Key findings:"
                for finding in summary['key_findings']:
                    prompt += f"\n  • {finding}"
            else:
                prompt += f"\n**{agent_type.title()} Agent:** Failed - {summary['error']}"
        
        prompt += f"\n\n**Top Insights Across All Agents:**"
        
        # Add top insights sorted by confidence
        sorted_insights = sorted(self.all_insights, key=lambda x: x.get('confidence', 0), reverse=True)
        for insight in sorted_insights[:5]:
            prompt += f"\n• {insight.get('content', '')} (confidence: {insight.get('confidence', 0):.1%})"
        
        prompt += f"\n\nPlease create a comprehensive, well-structured response that synthesizes these findings into a clear answer to the user's question."
        
        return prompt
