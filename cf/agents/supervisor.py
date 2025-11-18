"""
SupervisorAgent for CodeFusion

Orchestrates all specialist agents and uses LLM to generate comprehensive narratives.
Resets state for each new question.
"""

import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# CodeFusion imports - all at top per PEP 8
from cf.agents.base import BaseAgent
from cf.agents.multi_pass_coordinator import MultiPassCoordinator
from cf.agents.registry import AgentRegistry
from cf.agents.supervisor_components.agent_coordinator import AgentCoordinator
from cf.agents.supervisor_components.result_synthesizer import ResultSynthesizer
from cf.cache.semantic import SemanticCache
from cf.llm.model_tiers import TieredLLMManager, ModelTier
from cf.tools.registry import ToolRegistry
from cf.utils.llm_parser import LLMResponseParser


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that consults all specialists and synthesizes responses with LLM.
    """
    
    def __init__(self, repo_path: str, config: Dict[str, Any]):
        # Initialize shared tool/agent registry BEFORE calling super().__init__
        # so that supervisor and all specialist agents share the same registry
        self._agent_registry = AgentRegistry()
        self._shared_tool_registry = ToolRegistry(repo_path, agent_registry=self._agent_registry)

        # Initialize BaseAgent with shared tool registry
        super().__init__(repo_path, config, "supervisor", tool_registry=self._shared_tool_registry)

        # Initialize extracted coordination and synthesis components
        self.agent_coordinator = AgentCoordinator(
            repo_path, config, self.logger,
            self._shared_tool_registry, self._agent_registry
        )
        self.result_synthesizer = ResultSynthesizer(config, self.logger, self.call_llm)

        # Question-specific state (reset each question)
        self.reset_question_state()

        # Multi-pass coordinator (handles complex state management)
        self.pass_coordinator = MultiPassCoordinator(self.config, self.call_llm)

    def reset_question_state(self):
        """Reset state for new question"""
        self.agents_to_consult = []  # Will be determined intelligently based on question
        self.actions_taken = []
        self.results = {}
        self.insights = []

        # Analysis type tracking
        self.analysis_type = None  # Will be determined by LLM
        self.repo_cache_status = None  # 'new' or 'existing'

        # Multi-pass coordinator handles: pass_number, attempts, context_sharing, etc.
        # No need to track these separately anymore

        # Backward-compatibility shim for existing SupervisorAgent logic that still
        # references pass-related attributes directly (pending full migration to
        # MultiPassCoordinator). These ensure attributes exist to prevent AttributeError.

        # Load supervisor config for pass management
        supervisor_config = self.config.get('agents', {}).get('supervisor', {})

        self.pass_config = supervisor_config.get('pass_config', {
            'standard': {'max_passes': 3},
            'summary': {'max_passes': 2},
            'life_of_x': {'max_passes': 2}
        })
        self.pass_number = 1
        self.current_pass_attempt = 1
        self.max_pass_attempts = supervisor_config.get('max_pass_attempts', 3)
        self.agents_completed = []
        self.specialist_results = {}
        self.all_insights = []
        self.pass_results = {}
        self.all_passes_complete = False
        self.context_sharing_decision = False

        # Cache is already initialized by BaseAgent.__init__()
        # Just track if it's enabled for checking later
        self.cache_enabled = self.config.get('cache', {}).get('enabled', True)

    def _select_agents_for_question(self, question: str) -> List[str]:
        """
        Intelligently select which specialist agents to consult based on question.

        Uses LLM (fast tier) for intelligent routing to save time and cost.
        Falls back to all agents if LLM routing fails.
        """
        # Check if tiered LLM is available for intelligent routing
        if hasattr(self, '_code_agent') and hasattr(self._code_agent, 'tiered_llm') and self._code_agent.tiered_llm:
            tiered_llm = self._code_agent.tiered_llm
        else:
            # Fallback: initialize tiered LLM if not available
            try:
                tiered_llm = TieredLLMManager(self.config)
            except Exception:
                # If tiered LLM fails, use code agent as safe fallback (docs and web disabled)
                self.logger.verbose("Tiered LLM not available - using code agent", "⚠️")
                return ['code']

        # Use fast tier model to intelligently route question
        prompt = f"""You are an intelligent agent router for a codebase analysis system.

Available specialist agents:
- code: Analyzes source code, implementation details, architecture, how things work

NOTE: Currently in CODE-ONLY mode:
- Documentation analysis: DISABLED (will integrate later)
- Web search: DISABLED (focusing on codebase analysis only)

Question: "{question}"

The code agent will handle this question using the 6-layer knowledge base:
1. Structural layer (AST, graph analysis)
2. Semantic layer (embeddings, similarity search)
3. Dependency layer (call graphs, imports)
4. Patterns layer (design patterns, code smells)
5. Life-of-X layer (execution tracing, data flow)

Return JSON confirming code agent will handle this:
{{"agents": ["code"], "reasoning": "Code agent will analyze using multi-layer KB"}}
"""

        try:
            supervisor_config = self.config.get('agents', {}).get('supervisor', {})
            response = tiered_llm.generate(
                prompt=prompt,
                tier=ModelTier.FAST,
                temperature=supervisor_config.get('coordination_temperature', 0.1),
                max_tokens=supervisor_config.get('coordination_max_tokens', 150)
            )

            # Parse JSON response
            result = LLMResponseParser.extract_json(response, fallback={'agents': ['code']})
            selected_agents = result.get('agents', ['code'])
            reasoning = result.get('reasoning', '')

            # Validate agents (docs and web disabled for code-only KB focus)
            valid_agents = ['code']
            selected_agents = [a for a in selected_agents if a in valid_agents]

            if not selected_agents:
                selected_agents = ['code']  # Default fallback

            self.logger.verbose(f"Selected agents: {', '.join(selected_agents)} - {reasoning}", "🎯")
            return selected_agents

        except Exception as e:
            self.logger.verbose(f"Agent selection failed: {e} - using default [code]", "⚠️")

        # Fallback: use code agent as most versatile default
        return ['code']

    def analyze(self, question: str) -> Dict[str, Any]:
        """
        Override analyze to reset state for each new question
        """
        # Start timing
        start_time = time.time()

        # End previous tracing session before starting new one
        if hasattr(self, 'session_id') and self.session_id:
            try:
                self.tracer.end_session(self.session_id)
            except Exception:
                pass  # Ignore if session already ended

        # Start new tracing session
        self.session_id = self.tracer.start_session(f"supervisor_q_{int(time.time())}")

        # Call parent analyze method (which will call reset_question_state automatically)
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

            # Intelligently select which agents to consult based on question
            self.agents_to_consult = self._select_agents_for_question(question)

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
    
    def _consult_agent_with_timeout(self, agent_type: str, question: str, timeout_seconds: int) -> Dict[str, Any]:
        """Execute agent call with timeout enforcement"""
        with ThreadPoolExecutor(max_workers=self.agent_execution_max_workers) as executor:
            future = executor.submit(self._get_agent_result, agent_type, question)
            try:
                return future.result(timeout=timeout_seconds)
            except FuturesTimeoutError:
                self.logger.error(f"{agent_type} agent exceeded {timeout_seconds}s timeout")
                return {
                    'success': False,
                    'error': f'Agent timeout after {timeout_seconds}s',
                    'insights': [],
                    'timed_out': True
                }
            except Exception as e:
                self.logger.error(f"{agent_type} agent execution failed: {str(e)}")
                return {
                    'success': False,
                    'error': str(e),
                    'insights': []
                }

    def _get_agent_result(self, agent_type: str, question: str) -> Dict[str, Any]:
        """Get result from specific agent type"""
        if agent_type == 'code':
            if not self._code_agent:
                # Always use pipeline architecture (CodeOrchestrator)
                # Pass shared registries for cross-agent tool usage (no duplication!)
                self._code_agent = CodeOrchestrator(
                    self.repo_path,
                    self.config,
                    tool_registry=self._shared_tool_registry,
                    agent_registry=self._agent_registry
                )
                # KB agents are automatically registered in shared registry during orchestrator init

            # Pass LLM question classification to code agent to eliminate hardcoded patterns
            if hasattr(self._code_agent, 'set_question_context'):
                self._code_agent.set_question_context({
                    'analysis_type': self.analysis_type,
                    'question': question
                })

            return self._code_agent.analyze(question)
        elif agent_type == 'docs':
            if not self._docs_agent:
                # Pass shared tool registry for cross-agent tool usage
                self._docs_agent = DocsAgent(self.repo_path, self.config,
                                              tool_registry=self._shared_tool_registry)
            return self._docs_agent.analyze(question)
        elif agent_type == 'web':
            if not self._web_agent:
                # Pass shared tool registry for cross-agent tool usage
                self._web_agent = WebAgent(self.repo_path, self.config,
                                            tool_registry=self._shared_tool_registry)
            return self._web_agent.analyze(question)
        else:
            return {'success': False, 'error': f'Unknown agent type: {agent_type}', 'insights': []}

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
        """Get insights from code analysis specialist - delegates to AgentCoordinator"""
        # Set code agent context if needed
        self.agent_coordinator.set_code_agent_context(self.analysis_type, question)

        # Delegate to agent coordinator
        return self.agent_coordinator.consult_agent(
            'code', question,
            self.specialist_results,
            self.agents_completed,
            self.all_insights
        )
    
    def _consult_docs_agent(self, question: str) -> str:
        """Get insights from documentation specialist - delegates to AgentCoordinator"""
        return self.agent_coordinator.consult_agent(
            'docs', question,
            self.specialist_results,
            self.agents_completed,
            self.all_insights
        )
    
    def _consult_web_agent(self, question: str) -> str:
        """Get insights from web search specialist - delegates to AgentCoordinator"""
        return self.agent_coordinator.consult_agent(
            'web', question,
            self.specialist_results,
            self.agents_completed,
            self.all_insights
        )
    
    def _is_analysis_complete(self, question: str) -> bool:
        """Check if all multi-pass coordination is complete"""
        # Multi-pass logic: only complete when all passes are done
        # Don't exit just because current pass agents are done
        return self.all_passes_complete
    
    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate final consolidated answer - delegates to ResultSynthesizer"""
        # Delegate to result synthesizer
        result = self.result_synthesizer.generate_results(
            question,
            self.specialist_results,
            self.agents_completed,
            self.all_insights,
            self.pass_results
        )

        # Cache the result for future use
        if result.get('success'):
            self._cache_analysis_result(question, result)

        return result
    
    def _prepare_synthesis_data(self, question: str) -> Dict[str, Any]:
        """Prepare data summary for LLM synthesis"""

        data = {
            'question': question,
            'agents_consulted': self.agents_completed,
            'total_insights': len(self.all_insights),
            'specialist_summaries': {},
            'analyzed_files': []  # Track which files were actually analyzed
        }

        # Summarize each specialist's findings
        for agent_type in self.agents_completed:
            result = self.specialist_results.get(agent_type, {})
            if result.get('success'):
                thresholds = self.config.get('agents', {}).get('thresholds', {})
                data['specialist_summaries'][agent_type] = {
                    'success': True,
                    'insights_count': len(result.get('insights', [])),
                    'key_findings': [insight.get('content', '') for insight in result.get('insights', [])[:3]],
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
    
    def _build_synthesis_prompt(self, question: str, data: Dict[str, Any]) -> str:
        """Build prompt for LLM synthesis"""

        # Build analyzed files section for anti-hallucination
        analyzed_files_section = ""
        if data.get('analyzed_files'):
            analyzed_files_section = "\n\n**ANALYZED FILES (only reference these):**\n"
            for file_path in data['analyzed_files']:
                analyzed_files_section += f"- {file_path}\n"

        prompt = f"""Please synthesize the following analysis results into a comprehensive answer:

**User Question:** {question}
{analyzed_files_section}
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
- "life_of_x": Questions asking about process flows, execution paths, how something works end-to-end (e.g., "How does authentication work?", "What happens when a user submits a form?", "Trace the request flow")
- "standard": Specific technical questions, debugging, what-is questions, feature explanations (e.g., "What is class X?", "Where is function Y defined?")
- "summary": Repository overviews, architecture analysis, project understanding, code organization (e.g., "What is this codebase?", "Explain the architecture")

Provide JSON response with:
- analysis_type: "life_of_x", "standard", or "summary"
- reasoning: Brief explanation of why this type was chosen
"""

        system_prompt = """You are an analysis coordinator. Classify questions as:
- "life_of_x": Process flow questions about how things work end-to-end
- "standard": Specific technical questions about implementation, usage, debugging
- "summary": Questions about overall project structure, architecture, organization, overview

Return JSON format only."""
        
        try:
            llm_response = self.call_llm(prompt, system_prompt)
            
            if llm_response.get('success'):

                result = LLMResponseParser.extract_json_with_validation(
                    llm_response.get('content', ''),
                    required_keys=['analysis_type'],
                    fallback={'analysis_type': 'standard', 'reasoning': 'JSON parse failed'}
                )
                self.analysis_type = result.get('analysis_type', 'standard')
                return {'success': True, 'analysis_type': self.analysis_type, 'reasoning': result.get('reasoning', '')}
            
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
        """Check if similar analysis exists in cache using existing methods"""
        if not self.cache_enabled or not self.cache:
            return False
            
        try:
            # Generate a simple cache key for this repo + question
            repo_name = Path(self.repo_path).name
            question_hash = hashlib.md5(question.lower().encode()).hexdigest()[:8]
            cache_key = f"{repo_name}_{question_hash}"
            
            # Set LLM client for semantic similarity if available
            if hasattr(self, 'llm_client') and self.llm_client:
                self.cache.set_llm_client(self.llm_client)
            
            # Try to get cached result using existing get() method
            cached_result = self.cache.get(cache_key, question)
            
            has_cache = cached_result is not None
            if has_cache:
                self.logger.verbose(f"💾 Cache hit for: {question[:50]}...", "✅")
            else:
                self.logger.verbose(f"💾 Cache miss for: {question[:50]}...", "❌")
            
            return has_cache
            
        except Exception as e:
            self.logger.error(f"Cache check failed: {e}")
            return False
    
    
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
                self.all_passes_complete = True
                self.logger.verbose(f"✅ All passes complete - Pass {self.pass_number}/{self.pass_config[self.analysis_type]['max_passes']}", "🏁")
                return "all_passes_complete"
                
        except Exception as e:
            self.logger.error(f"Pass completion handling failed: {str(e)}")
            self.all_passes_complete = True
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

                analysis = LLMResponseParser.extract_json(
                    llm_response.get('content', ''),
                    fallback=None
                )
                if analysis:
                    return analysis
                # JSON parse failed, fall through to fallback logic
                self.logger.error("JSON parse failed, using fallback logic")
            else:
                # LLM call failed, fall through to fallback logic
                self.logger.error("LLM call failed, using fallback logic")
            
            # Fallback logic (runs when LLM fails or JSON parsing fails)
            # Use config threshold instead of hardcoded value
            min_insights_threshold = self.config.get('agents', {}).get('thresholds', {}).get('min_insights_for_pass', 2)

            # Check if code agent has already provided a sufficient answer with passing validation
            # If so, complete instead of continuing to next pass
            code_result = self.specialist_results.get('code', {})
            has_valid_answer = (
                code_result.get('success') and
                code_result.get('answer') and
                code_result.get('validation', {}).get('valid', False)
            )

            if has_valid_answer:
                return {'action': 'complete', 'reasoning': 'Code agent provided valid answer with passing validation (fallback)'}

            # For summary questions, always proceed to Pass 2 if we're on Pass 1
            if self.analysis_type == 'summary' and self.pass_number == 1:
                return {'action': 'next_pass', 'reasoning': 'Summary Pass 1 complete, proceeding to Pass 2 (fallback)', 'context_sharing': True}
            elif current_insights < min_insights_threshold and self.current_pass_attempt < self.max_pass_attempts:
                return {'action': 'retry', 'reasoning': f'Insufficient insights ({current_insights} < {min_insights_threshold}), retrying (fallback)', 'retry_reason': 'Low insight count'}
            elif self.pass_number < self.pass_config[self.analysis_type]['max_passes']:
                return {'action': 'next_pass', 'reasoning': 'Proceeding to next pass (fallback)', 'context_sharing': True}
            else:
                return {'action': 'complete', 'reasoning': 'Max passes reached (fallback)'}
                
        except Exception as e:
            self.logger.error(f"Pass analysis failed: {str(e)}")
            # Even on exception, use fallback logic instead of immediately completing
            # Use config threshold instead of hardcoded value
            min_insights_threshold = self.config.get('agents', {}).get('thresholds', {}).get('min_insights_for_pass', 2)

            # Check if code agent has already provided a sufficient answer with passing validation
            # If so, complete instead of continuing to next pass
            code_result = self.specialist_results.get('code', {})
            has_valid_answer = (
                code_result.get('success') and
                code_result.get('answer') and
                code_result.get('validation', {}).get('valid', False)
            )

            if has_valid_answer:
                return {'action': 'complete', 'reasoning': f'Code agent provided valid answer despite exception: {str(e)}'}

            # For summary questions, always proceed to Pass 2 if we're on Pass 1
            if self.analysis_type == 'summary' and self.pass_number == 1:
                return {'action': 'next_pass', 'reasoning': f'Summary Pass 1 complete despite exception, proceeding to Pass 2: {str(e)}', 'context_sharing': True}
            elif current_insights < min_insights_threshold and self.current_pass_attempt < self.max_pass_attempts:
                return {'action': 'retry', 'reasoning': f'Exception occurred, retrying (insights: {current_insights} < {min_insights_threshold}): {str(e)}', 'retry_reason': 'Analysis exception'}
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
        
        # Log the enhanced question being sent to agent
        if len(enhanced_question) != len(question):
            self.logger.verbose(f"📝 Enhanced question for {agent_type}: {enhanced_question[:100]}...", "🔧")
        
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
    
    def _generate_all_agents_failed_response(self, question: str) -> Dict[str, Any]:
        """Generate response when all agents failed"""
        # Collect error messages
        errors = []
        for agent_type in self.agents_completed:
            result = self.specialist_results.get(agent_type, {})
            error = result.get('error', 'Unknown error')
            timed_out = result.get('timed_out', False)
            status = "timed out" if timed_out else "failed"
            errors.append(f"- {agent_type.title()} agent {status}: {error}")

        error_summary = "\n".join(errors)

        narrative = f"""I encountered errors while trying to analyze your question: "{question}"

**Analysis Errors:**
{error_summary}

**What happened:**
All specialist agents ({', '.join(self.agents_completed)}) encountered issues during analysis.

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
            'agents_consulted': self.agents_completed,
            'specialist_results': self.specialist_results,
            'error': 'All agents failed',
            'agent': 'supervisor'
        }

    def _generate_partial_response(self, question: str, synthesis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response from partial insights when LLM synthesis fails"""
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
        if len(self.all_insights) > 0:
            narrative_parts.append(f"\n**Key Insights ({len(self.all_insights)} total):**")
            sorted_insights = sorted(self.all_insights, key=lambda x: x.get('confidence', 0), reverse=True)
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
            'insights': self.all_insights,
            'agents_consulted': self.agents_completed,
            'specialist_results': self.specialist_results,
            'agent': 'supervisor',
            'partial': True
        }

    def _cache_analysis_result(self, question: str, result: Dict[str, Any]):
        """Cache analysis result for future use"""
        if not self.cache_enabled or not self.cache:
            return
            
        try:
            # Generate the same cache key used for checking
            repo_name = Path(self.repo_path).name
            question_hash = hashlib.md5(question.lower().encode()).hexdigest()[:8]
            cache_key = f"{repo_name}_{question_hash}"
            
            # Prepare metadata
            metadata = {
                'repo_path': self.repo_path,
                'analysis_type': self.analysis_type,
                'total_insights': len(self.all_insights),
                'agents_consulted': result.get('agents_consulted', []),
                'pass_count': len([k for k in self.pass_results.keys() if k.startswith('pass_')])
            }
            
            # Cache using existing set() method
            self.cache.set(cache_key, result, question, metadata)
            
            self.logger.verbose(f"💾 Cached analysis result: {cache_key}", "💿")
            
        except Exception as e:
            self.logger.error(f"Failed to cache result: {e}")
