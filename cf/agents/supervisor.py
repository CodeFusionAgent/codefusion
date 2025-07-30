"""
SupervisorAgent for CodeFusion

Orchestrates all specialist agents and uses LLM to generate comprehensive narratives.
Resets state for each new question.
"""

import time
import json
from typing import Dict, List, Any
from cf.agents.base import BaseAgent
from cf.cache.semantic import SemanticCache


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
        
        # Multi-pass coordination state
        self.analysis_type = None  # Will be determined by LLM
        self.pass_number = 1
        self.current_pass_attempt = 1
        self.max_pass_attempts = 3  # Retry mechanism
        self.pass_results = {}  # Store results from each pass
        self.repo_cache_status = None  # 'new' or 'existing'
        self.context_sharing_decision = None  # LLM decides per pass
        
        # Multi-pass configuration
        self.pass_config = {
            'standard': {'max_passes': 3},
            'summary': {'max_passes': 2}
        }
    
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
        """Execute one analysis step with multi-pass coordination"""
        
        # Initialize analysis on first iteration
        if self.iteration == 1:
            self.logger.verbose(f"Processing: {question}", "📝")
            
            # Determine analysis type and cache status using LLM
            analysis_setup = self._setup_analysis_strategy(question)
            if not analysis_setup.get('success'):
                return "analysis_setup_failed"
            
            self.logger.verbose(f"Analysis type: {self.analysis_type}, Pass {self.pass_number}/{self.pass_config[self.analysis_type]['max_passes']}", "🎯")
            
            # Log cache strategy results
            cache_strategy = analysis_setup.get('cache_strategy', {})
            if cache_strategy.get('has_cache'):
                self.logger.verbose("✅ Found similar analysis in cache", "💾")
            elif cache_strategy.get('has_summary_cache'):
                self.logger.verbose("✅ Found repository summary in cache", "💾")
            else:
                self.logger.verbose("❌ No relevant cache found - proceeding with fresh analysis", "💾")
        
        # Check if current pass is complete
        if len(self.agents_completed) >= len(self.agents_to_consult):
            return self._handle_pass_completion(question)
        
        # Consult next agent in current pass
        for agent_type in self.agents_to_consult:
            if agent_type not in self.agents_completed:
                return self._consult_agent_with_context(agent_type, question)
        
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
        
        # Log multi-pass completion summary
        total_passes = len([k for k in self.pass_results.keys() if k.startswith('pass_')])
        if total_passes > 1:
            self.logger.verbose(f"🏁 Multi-pass analysis complete: {total_passes} passes, {len(self.all_insights)} total insights", "✅")
        
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
    
    def _setup_analysis_strategy(self, question: str) -> Dict[str, Any]:
        """Use LLM to determine analysis type, then check cache strategy"""
        try:
            # Step 1: Determine analysis type based purely on question content
            analysis_type_result = self._determine_analysis_type(question)
            if not analysis_type_result.get('success'):
                return analysis_type_result
            
            # Step 2: Check cache and determine strategy
            cache_strategy = self._determine_cache_strategy(question)
            
            self.logger.verbose(f"Strategy: {analysis_type_result.get('reasoning', 'No reasoning provided')}", "🧠")
            if cache_strategy.get('has_cache'):
                self.logger.verbose("Similar analysis found in cache", "💾")
            
            return {'success': True, 'strategy': analysis_type_result, 'cache_strategy': cache_strategy}
            
        except Exception as e:
            self.logger.error(f"Analysis strategy setup failed: {str(e)}")
            self.analysis_type = 'standard'
            return {'success': False, 'error': str(e)}
    
    def _determine_analysis_type(self, question: str) -> Dict[str, Any]:
        """Pure LLM decision on analysis type based on question content"""
        prompt = f"""Analyze this question and determine the analysis type:

Question: "{question}"

Determine if this is:
- "standard": Specific technical questions, debugging, how-to questions, feature explanations
- "summary": Repository overviews, architecture analysis, project understanding, code organization

Provide JSON response with:
- analysis_type: "standard" or "summary"  
- reasoning: Brief explanation of why this type was chosen
"""
        
        system_prompt = """You are an analysis coordinator. Classify questions as:
- "standard": Specific technical questions about implementation, usage, debugging
- "summary": Questions about overall project structure, architecture, organization, overview

Return JSON format only."""
        
        try:
            llm_response = self.call_llm(prompt, system_prompt)
            
            if llm_response.get('success'):
                try:
                    result = json.loads(llm_response.get('content', '{}'))
                    self.analysis_type = result.get('analysis_type', 'standard')
                    return {'success': True, 'analysis_type': self.analysis_type, 'reasoning': result.get('reasoning', '')}
                except json.JSONDecodeError:
                    self.analysis_type = 'standard'
                    return {'success': True, 'analysis_type': 'standard', 'reasoning': 'JSON parse failed, using fallback'}
            
            self.analysis_type = 'standard'
            return {'success': True, 'analysis_type': 'standard', 'reasoning': 'LLM call failed, using fallback'}
            
        except Exception as e:
            self.analysis_type = 'standard'
            return {'success': False, 'error': str(e)}
    
    def _determine_cache_strategy(self, question: str) -> Dict[str, Any]:
        """Determine strategy based on cache existence for any question type"""
        try:
            # Check if similar analysis exists in cache
            has_cache = self._check_similar_analysis_cache(question)
            
            strategy = {
                'has_cache': has_cache,
                'action': 'use_cache' if has_cache else 'new_analysis'
            }
            
            # For standard questions, check if repository summary/overview exists in cache
            if self.analysis_type == 'standard' and not has_cache:
                has_summary_cache = self._check_similar_analysis_cache("repository overview architecture summary structure")
                strategy['has_summary_cache'] = has_summary_cache
                if not has_summary_cache:
                    self.logger.verbose("Standard question may need repository context - no summary in cache", "📋")
            
            return strategy
            
        except Exception as e:
            return {'has_cache': False, 'action': 'new_analysis', 'error': str(e)}
    
    def _check_similar_analysis_cache(self, question: str) -> bool:
        """Check if similar analysis exists in cache"""
        try:
            # Create a cache instance for supervisor agent
            cache = SemanticCache('supervisor', {'enabled': True, 'cache_dir': 'cf_cache'})
            
            return cache.has_similar_analysis(self.repo_path, question)
            
        except Exception:
            return False  # Fallback to no cache
    
    
    def _handle_pass_completion(self, question: str) -> str:
        """Handle completion of current pass and decide next action"""
        try:
            # Store current pass results
            self.pass_results[f'pass_{self.pass_number}'] = {
                'agents_completed': self.agents_completed.copy(),
                'specialist_results': self.specialist_results.copy(),
                'insights': self.all_insights.copy(),
                'attempt': self.current_pass_attempt
            }
            
            # Use LLM to analyze pass results and decide next action
            pass_analysis = self._analyze_pass_results(question)
            
            action = pass_analysis.get('action', 'complete')
            self.logger.verbose(f"📊 Pass {self.pass_number} analysis decision: {action} - {pass_analysis.get('reasoning', 'No reason provided')}", "🤔")
            
            if action == 'retry' and self.current_pass_attempt < self.max_pass_attempts:
                return self._retry_current_pass(question, pass_analysis.get('retry_reason', 'Results insufficient'))
            
            elif action == 'next_pass' and self.pass_number < self.pass_config[self.analysis_type]['max_passes']:
                return self._start_next_pass(question, pass_analysis)
            
            else:
                # All passes complete or max attempts reached
                return "all_passes_complete"
                
        except Exception as e:
            self.logger.error(f"Pass completion handling failed: {str(e)}")
            return "all_passes_complete"  # Fallback to completion
    
    def _analyze_pass_results(self, question: str) -> Dict[str, Any]:
        """Use LLM to analyze current pass results and determine next action"""
        try:
            # Prepare current pass summary
            current_insights = len(self.all_insights)
            successful_agents = len([agent for agent in self.agents_completed 
                                   if self.specialist_results.get(agent, {}).get('success', False)])
            
            prompt = f"""Analyze the results of Pass {self.pass_number} (Attempt {self.current_pass_attempt}) for this question:

Question: "{question}"
Analysis type: {self.analysis_type}
Current pass: {self.pass_number}/{self.pass_config[self.analysis_type]['max_passes']}

Pass Results:
- Agents consulted: {len(self.agents_completed)}/{len(self.agents_to_consult)}
- Successful agents: {successful_agents}
- Total insights gathered: {current_insights}
- Agent success details: {[(agent, self.specialist_results.get(agent, {}).get('success', False)) for agent in self.agents_completed]}

Top insights from this pass:
{[insight.get('content', '')[:100] + '...' for insight in self.all_insights[:3]]}

Determine the next action:
1. "retry" - If results are insufficient and retry is warranted
2. "next_pass" - If results are good enough to proceed to next pass
3. "complete" - If analysis is sufficient to generate final answer

Provide JSON response with:
- action: "retry", "next_pass", or "complete"
- reasoning: Why this action was chosen
- retry_reason: If retry, what specifically needs improvement
- context_sharing: If next_pass, whether to share current results with next pass agents (true/false)
- focus_areas: If next_pass, what areas should be emphasized (array of strings)
"""
            
            system_prompt = f"""You are analyzing the quality of a multi-pass analysis system. 
For {self.analysis_type} analysis, evaluate if current pass results are sufficient or need improvement.
Consider insight quality, agent success rates, and question complexity.
Return JSON format only."""
            
            llm_response = self.call_llm(prompt, system_prompt)
            
            if llm_response.get('success'):
                try:
                    analysis = json.loads(llm_response.get('content', '{}'))
                    return analysis
                except json.JSONDecodeError:
                    # JSON parse failed, fall through to fallback logic
                    self.logger.error("JSON parse failed, using fallback logic")
            else:
                # LLM call failed, fall through to fallback logic
                self.logger.error("LLM call failed, using fallback logic")
            
            # Fallback logic (runs when LLM fails or JSON parsing fails)
            # For summary questions, always proceed to Pass 2 if we're on Pass 1
            if self.analysis_type == 'summary' and self.pass_number == 1:
                return {'action': 'next_pass', 'reasoning': 'Summary Pass 1 complete, proceeding to Pass 2 (fallback)', 'context_sharing': True}
            elif current_insights < 2 and self.current_pass_attempt < self.max_pass_attempts:
                return {'action': 'retry', 'reasoning': 'Insufficient insights, retrying (fallback)', 'retry_reason': 'Low insight count'}
            elif self.pass_number < self.pass_config[self.analysis_type]['max_passes']:
                return {'action': 'next_pass', 'reasoning': 'Proceeding to next pass (fallback)', 'context_sharing': True}
            else:
                return {'action': 'complete', 'reasoning': 'Max passes reached (fallback)'}
                
        except Exception as e:
            self.logger.error(f"Pass analysis failed: {str(e)}")
            # Even on exception, use fallback logic instead of immediately completing
            # For summary questions, always proceed to Pass 2 if we're on Pass 1
            if self.analysis_type == 'summary' and self.pass_number == 1:
                return {'action': 'next_pass', 'reasoning': f'Summary Pass 1 complete despite exception, proceeding to Pass 2: {str(e)}', 'context_sharing': True}
            elif current_insights < 2 and self.current_pass_attempt < self.max_pass_attempts:
                return {'action': 'retry', 'reasoning': f'Exception occurred, retrying: {str(e)}', 'retry_reason': 'Analysis exception'}
            elif self.pass_number < self.pass_config[self.analysis_type]['max_passes']:
                return {'action': 'next_pass', 'reasoning': f'Exception occurred, proceeding: {str(e)}', 'context_sharing': True}
            else:
                return {'action': 'complete', 'reasoning': f'Exception occurred, completing: {str(e)}'}
    
    def _retry_current_pass(self, question: str, retry_reason: str) -> str:
        """Retry current pass with improved strategy"""
        self.current_pass_attempt += 1
        self.logger.verbose(f"Retrying Pass {self.pass_number} (Attempt {self.current_pass_attempt}): {retry_reason}", "🔄")
        
        # Reset agents for retry
        self.agents_completed = []
        self.specialist_results = {}
        # Keep insights from previous attempts but don't reset
        
        return "pass_retry_initiated"
    
    def _start_next_pass(self, question: str, pass_analysis: Dict[str, Any]) -> str:
        """Start the next pass with context sharing decision"""
        self.pass_number += 1
        self.current_pass_attempt = 1
        
        # LLM-determined context sharing decision
        self.context_sharing_decision = pass_analysis.get('context_sharing', False)
        focus_areas = pass_analysis.get('focus_areas', [])
        
        self.logger.verbose(f"🚀 Starting Pass {self.pass_number}/{self.pass_config[self.analysis_type]['max_passes']}", "➡️")
        self.logger.verbose(f"🔗 Context sharing: {'✅ Enabled' if self.context_sharing_decision else '❌ Disabled'}", "➡️")
        if focus_areas:
            self.logger.verbose(f"🎯 Focus areas: {', '.join(focus_areas)}", "➡️")
        
        # Reset agents for next pass
        self.agents_completed = []
        # Keep specialist_results if context sharing, otherwise reset
        if not self.context_sharing_decision:
            self.specialist_results = {}
        
        return "next_pass_initiated"
    
    def _consult_agent_with_context(self, agent_type: str, question: str) -> str:
        """Consult agent with pass-specific and context-aware prompting"""
        
        # Build pass-specific question based on analysis type and pass number
        if self.analysis_type == 'summary':
            enhanced_question = self._build_summary_pass_specific_question(agent_type, question)
            self.logger.verbose(f"📝 {agent_type.upper()} Agent - Pass {self.pass_number} summary focus", "🎯")
        elif self.context_sharing_decision and self.pass_number > 1:
            enhanced_question = self._build_context_aware_prompt(agent_type, question)
            self.logger.verbose(f"📝 {agent_type.upper()} Agent - Context sharing enabled", "🔗")
        else:
            enhanced_question = question
            self.logger.verbose(f"📝 {agent_type.upper()} Agent - Standard question", "❓")
        
        # Use existing agent consultation logic
        return self._consult_agent(agent_type, enhanced_question)
    
    def _build_context_aware_prompt(self, agent_type: str, original_question: str) -> str:
        """Build context-aware prompt for agents based on previous pass results"""
        try:
            # Get previous pass insights
            previous_insights = []
            for pass_key, pass_data in self.pass_results.items():
                if pass_key != f'pass_{self.pass_number}':  # Exclude current pass
                    previous_insights.extend(pass_data.get('insights', []))
            
            if not previous_insights:
                return original_question
            
            # Build context summary
            context_summary = []
            for insight in previous_insights[:5]:  # Limit to top 5 insights
                content = insight.get('content', '')[:100]  # Truncate long content
                context_summary.append(f"- {content}")
            
            enhanced_prompt = f"""Based on previous analysis insights:
{chr(10).join(context_summary)}

Now focusing on {agent_type} analysis, please address: {original_question}

Consider how your findings relate to or build upon the previous insights."""
            
            return enhanced_prompt
            
        except Exception as e:
            self.logger.error(f"Context-aware prompt building failed: {str(e)}")
            return original_question
    
    def _build_summary_pass_specific_question(self, agent_type: str, original_question: str) -> str:
        """Build simplified pass-specific questions for summary analysis"""
        try:
            if self.pass_number == 1:
                enhanced_question = f"PASS 1 - High-level overview: {original_question}. Focus on overall structure and organization."
                self.logger.verbose(f"🔍 Pass 1 Focus: High-level overview and structure", "📋")
                return enhanced_question
            elif self.pass_number == 2:
                pass1_context = self._get_brief_pass1_context()
                enhanced_question = f"PASS 2 - Detailed analysis: {original_question}. Previous context: {pass1_context}. Now provide deep technical insights."
                self.logger.verbose(f"🔬 Pass 2 Focus: Detailed analysis with context from Pass 1", "📋")
                self.logger.verbose(f"📝 Pass 1 Context: {pass1_context[:100]}{'...' if len(pass1_context) > 100 else ''}", "🔗")
                return enhanced_question
            else:
                return original_question
                
        except Exception as e:
            self.logger.error(f"Summary pass question building failed: {str(e)}")
            return original_question
    
    def _get_brief_pass1_context(self) -> str:
        """Get a brief summary of Pass 1 results for Pass 2 context"""
        try:
            if 'pass_1' not in self.pass_results:
                return "No previous context"
            
            pass1_data = self.pass_results['pass_1']
            insights = pass1_data.get('insights', [])
            
            if not insights:
                return "No previous insights"
            
            # Get top 3 insights, truncated
            context_parts = []
            for insight in insights[:3]:
                content = insight.get('content', '')[:80] + '...' if len(insight.get('content', '')) > 80 else insight.get('content', '')
                context_parts.append(content)
            
            return '; '.join(context_parts)
            
        except Exception:
            return "Context unavailable"
