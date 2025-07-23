"""
Real LLM interface for CodeFusion agents using LiteLLM for unified provider support.

This module provides LLM API calls through LiteLLM which supports:
- OpenAI (gpt-3.5-turbo, gpt-4, etc.)
- Anthropic (claude-3-sonnet, claude-3-opus, etc.) 
- LLaMA via various providers (together_ai, replicate, ollama, etc.)
- Many other providers
"""

import json
import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

try:
    import litellm
except ImportError:
    litellm = None

from cf.utils.logging_utils import llm_log, error_log
from cf.llm.prompt_templates import PromptBuilder
from cf.llm.response_parser import response_parser, REASONING_SCHEMA, SUMMARY_SCHEMA, LIFE_OF_X_SCHEMA
from cf.llm.simple_llm import SimpleLLM


@dataclass
class LLMConfig:
    """Configuration for LLM providers using LiteLLM."""
    model: str  # e.g., "gpt-3.5-turbo", "claude-3-sonnet-20240229", "together_ai/meta-llama/Llama-2-7b-chat-hf"
    api_key: str = ""
    api_base: str = ""  # For custom endpoints
    max_tokens: int = 1000
    temperature: float = 0.7
    timeout: int = 30


class RealLLM:
    """
    Real LLM interface using LiteLLM for unified provider access.
    
    Supports all major providers through LiteLLM:
    - OpenAI: "gpt-3.5-turbo", "gpt-4", etc.
    - Anthropic: "claude-3-sonnet-20240229", "claude-3-opus-20240229", etc.
    - LLaMA via Together AI: "together_ai/meta-llama/Llama-2-7b-chat-hf"
    - LLaMA via Replicate: "replicate/meta/llama-2-7b-chat"
    - LLaMA via Ollama: "ollama/llama2"
    - And many more
    """
    
    def __init__(self, config: Optional[LLMConfig] = None, cf_config: Optional[Dict[str, Any]] = None):
        # Use CodeFusion config if provided, otherwise load from environment
        if cf_config and 'llm' in cf_config:
            llm_config = cf_config['llm']
            self.config = LLMConfig(
                model=llm_config.get('model', 'claude-3-sonnet-20240229'),
                api_key=llm_config.get('api_key', ''),
                max_tokens=llm_config.get('max_tokens', 1000),
                temperature=llm_config.get('temperature', 0.7)
            )
        else:
            self.config = config or self._load_config()
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize prompt builder and response parser
        self.prompt_builder = PromptBuilder()
        self.response_parser = response_parser
        
        # Initialize LiteLLM
        self.client = None
        self._init_litellm()
    
    def _load_config(self) -> LLMConfig:
        """Load LLM configuration from environment variables."""
        model = os.getenv('CF_LLM_MODEL', 'gpt-3.5-turbo')
        api_key = os.getenv('CF_LLM_API_KEY', '')
        api_base = os.getenv('CF_LLM_API_BASE', '')
        
        # Set provider-specific environment variables for LiteLLM
        if api_key:
            if 'gpt' in model or 'openai' in model:
                os.environ['OPENAI_API_KEY'] = api_key
            elif 'claude' in model or 'anthropic' in model:
                os.environ['ANTHROPIC_API_KEY'] = api_key
            elif 'together_ai' in model:
                os.environ['TOGETHER_AI_API_KEY'] = api_key
            elif 'replicate' in model:
                os.environ['REPLICATE_API_TOKEN'] = api_key
        
        return LLMConfig(
            model=model,
            api_key=api_key,
            api_base=api_base,
            max_tokens=int(os.getenv('CF_LLM_MAX_TOKENS', '1000')),
            temperature=float(os.getenv('CF_LLM_TEMPERATURE', '0.7')),
            timeout=int(os.getenv('CF_LLM_TIMEOUT', '30'))
        )
    
    def _init_litellm(self):
        """Initialize LiteLLM."""
        try:
            
            # Configure LiteLLM
            if self.config.api_base:
                litellm.api_base = self.config.api_base
            
            # Set timeout
            litellm.request_timeout = self.config.timeout
            
            # Test the model only if API key is provided
            if self.config.api_key:
                try:
                    test_response = litellm.completion(
                        model=self.config.model,
                        messages=[{"role": "user", "content": "Hello"}],
                        max_tokens=10,
                        temperature=0.1
                    )
                    self.client = litellm
                    self.logger.info(f"LiteLLM initialized successfully with model: {self.config.model}")
                except Exception as e:
                    self.logger.warning(f"LiteLLM test failed for model {self.config.model}: {e}")
                    self.client = None
            else:
                # Skip test if no API key provided, but still set up client for future use
                self.client = litellm
                self.logger.info(f"LiteLLM configured for model {self.config.model} (no API key test)")
                
        except ImportError:
            self.logger.error("LiteLLM package not installed. Install with: pip install litellm")
            self.client = None
        except Exception as e:
            self.logger.error(f"Failed to initialize LiteLLM: {e}")
            self.client = None
    
    def reasoning(self, context: str, question: str, agent_type: str = 'general') -> Dict[str, Any]:
        """
        Generate reasoning response using LiteLLM.
        
        Args:
            context: Current context/state
            question: Question to reason about
            agent_type: Type of agent requesting reasoning
            
        Returns:
            Reasoning response with suggested actions
        """
        if not self.client:
            return self._fallback_reasoning(context, question, agent_type)
        
        try:
            prompt = self.prompt_builder.build_reasoning_prompt(context, question, agent_type, self.config.model)
            response = self._call_llm(prompt)
            
            # Parse the response
            parsed_response = self.response_parser.parse_response(response, REASONING_SCHEMA)
            
            return {
                'reasoning': parsed_response.get('reasoning', response),
                'confidence': parsed_response.get('confidence', 0.8),
                'suggested_actions': parsed_response.get('suggested_actions', ['read_file', 'search_files']),
                'context_analysis': parsed_response.get('context_analysis', {}),
                'model_used': self.config.model,
                'raw_response': response
            }
            
        except Exception as e:
            self.logger.error(f"LLM reasoning failed: {e}")
            return self._fallback_reasoning(context, question, agent_type)
    
    def summarize(self, content: str, summary_type: str = 'general', focus: str = 'all') -> Dict[str, Any]:
        """
        Generate summary using LiteLLM.
        
        Args:
            content: Content to summarize
            summary_type: Type of summary to generate
            focus: Focus area for the summary
            
        Returns:
            Summary response
        """
        if not self.client:
            return self._fallback_summary(content, summary_type, focus)
        
        try:
            prompt = self.prompt_builder.build_summary_prompt(content, summary_type, focus, self.config.model)
            response = self._call_llm(prompt)
            
            # Parse the response
            parsed_response = self.response_parser.parse_response(response, SUMMARY_SCHEMA)
            
            return {
                'summary': parsed_response.get('summary', response),
                'key_points': parsed_response.get('key_points', []),
                'confidence': parsed_response.get('confidence', 0.7),
                'focus': focus,
                'content_analysis': parsed_response.get('content_analysis', {}),
                'model_used': self.config.model,
                'raw_response': response
            }
            
        except Exception as e:
            self.logger.error(f"LLM summarization failed: {e}")
            return self._fallback_summary(content, summary_type, focus)
    
    def generate_life_of_x_narrative(self, question: str, insights: Dict[str, Any], components: List[Dict], flows: List[Dict], code_examples: List[Dict] = None, key_entity: str = None) -> Dict[str, Any]:
        """
        Generate a "Life of X" narrative - a comprehensive architectural story following a feature/request through the entire system.
        
        Args:
            question: The user's question (e.g., "How does authentication work?")
            insights: Collected insights from agents
            components: System components involved
            flows: Data/control flows identified
            code_examples: Code examples to illustrate points
            
        Returns:
            Life of X narrative response
        """
        if not self.client:
            return self._fallback_life_of_x_narrative(question, insights, components, flows, code_examples, key_entity)
        
        try:
            # Use provided key entity or fallback to generic term
            if not key_entity:
                key_entity = "Request"
            
            # Format data for prompt
            insights_str = self.prompt_builder.format_insights(insights)
            components_str = self.prompt_builder.format_components(components)
            flows_str = self.prompt_builder.format_flows(flows)
            code_examples_str = self.prompt_builder.format_code_examples(code_examples or [])
            
            prompt = self.prompt_builder.build_life_of_x_prompt(
                question, insights_str, components_str, flows_str, 
                code_examples_str, key_entity, self.config.model
            )
            
            # Use longer context for narrative generation
            original_max_tokens = self.config.max_tokens
            self.config.max_tokens = min(2000, original_max_tokens * 2)
            
            response = self._call_llm(prompt)
            
            # Restore original max tokens
            self.config.max_tokens = original_max_tokens
            
            # Parse the response
            parsed_response = self.response_parser.parse_response(response, LIFE_OF_X_SCHEMA)
            
            # Enhanced fallback if parsing failed
            narrative = parsed_response.get('narrative', response)
            if not narrative or len(narrative.strip()) < 50:  # If narrative is too short or empty
                self.logger.warning("LLM response parsing resulted in minimal narrative, enhancing...")
                narrative = self._enhance_narrative_from_insights(question, insights, components, flows)
            
            return {
                'narrative': narrative,
                'journey_stages': parsed_response.get('journey_stages', self._default_journey_stages()),
                'key_components': parsed_response.get('key_components', [comp.get('name', 'Component') for comp in components[:5]]),
                'flow_summary': parsed_response.get('flow_summary', self._generate_flow_summary(question, components, flows)),
                'code_insights': parsed_response.get('code_insights', self._generate_code_insights(insights)),
                'confidence': parsed_response.get('confidence', 0.8),
                'model_used': self.config.model,
                'raw_response': response
            }
            
        except Exception as e:
            self.logger.error(f"LLM Life of X narrative generation failed: {e}")
            return self._fallback_life_of_x_narrative(question, insights, components, flows, code_examples, key_entity)
    
    def _call_llm(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None, tool_choice: str = "auto") -> str:
        """Make LLM API call using LiteLLM with optional tool calling."""
        try:
            # Log LLM call initiation
            llm_log(f"\n🧠 [LLM] Starting API call to {self.config.model}")
            llm_log(f"📝 [LLM] Prompt length: {len(prompt)} characters")
            if tools:
                llm_log(f"🔧 [LLM] Function calling enabled with {len(tools)} tools: {[t['function']['name'] for t in tools]}")
                self.logger.info(f"LLM function calling with tools: {[t['function']['name'] for t in tools]}")
            else:
                llm_log(f"💬 [LLM] Standard text completion (no function calling)")
                self.logger.info("LLM standard text completion")
            
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Base completion parameters
            completion_params = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "timeout": self.config.timeout
            }
            
            # Add tool calling if tools are provided and model supports it
            if tools and self._supports_tool_calling():
                completion_params["tools"] = tools
                completion_params["tool_choice"] = tool_choice
                llm_log(f"✅ [LLM] Model {self.config.model} supports function calling")
                self.logger.info(f"Model {self.config.model} supports function calling with {len(tools)} tools")
            elif tools:
                llm_log(f"⚠️  [LLM] Model {self.config.model} does not support function calling, using text completion")
                self.logger.warning(f"Model {self.config.model} does not support function calling")
            
            # Make the API call
            llm_log(f"📡 [LLM] Making API call to {self.config.model}...")
            self.logger.info(f"Making LiteLLM API call: model={self.config.model}, max_tokens={self.config.max_tokens}")
            
            response = self.client.completion(**completion_params)
            
            # Log response details
            llm_log(f"✅ [LLM] Received response from {self.config.model}")
            if hasattr(response, 'usage') and response.usage:
                llm_log(f"📊 [LLM] Token usage: {response.usage}")
                self.logger.info(f"LLM token usage: {response.usage}")
            
            # Handle tool calling response
            if tools and hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                llm_log(f"🔧 [LLM] Processing function calling response with {len(response.choices[0].message.tool_calls)} tool calls")
                self.logger.info(f"Processing {len(response.choices[0].message.tool_calls)} tool calls from LLM")
                return self._handle_tool_calls_response(response)
            else:
                response_content = response.choices[0].message.content
                llm_log(f"💬 [LLM] Standard text response received ({len(response_content)} chars)")
                self.logger.info(f"Standard LLM text response: {len(response_content)} characters")
                return response_content
            
        except Exception as e:
            error_log(f"❌ [LLM] API call failed: {e}")
            self.logger.error(f"LiteLLM API call failed: {e}")
            raise
    
    def _supports_tool_calling(self) -> bool:
        """Check if the current model supports tool calling."""
        tool_calling_models = [
            'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o',
            'claude-3-sonnet-20240229', 'claude-3-opus-20240229', 'claude-3-haiku-20240307'
        ]
        return any(model in self.config.model for model in tool_calling_models)
    
    def _handle_tool_calls_response(self, response) -> str:
        """Handle response with tool calls."""
        tool_calls = response.choices[0].message.tool_calls
        tool_results = []
        
        
        llm_log(f"🔧 [LLM] Parsing {len(tool_calls)} tool calls from LLM response")
        
        for i, tool_call in enumerate(tool_calls, 1):
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            llm_log(f"  📋 [LLM] Tool Call {i}: {function_name}")
            llm_log(f"       Arguments: {function_args}")
            self.logger.info(f"Tool call {i}: {function_name} with args: {function_args}")
            
            tool_results.append({
                "tool_call_id": tool_call.id,
                "function_name": function_name,
                "arguments": function_args,
                "requires_execution": True
            })
        
        # Return structured tool call information
        structured_response = {
            "type": "tool_calls",
            "tool_calls": tool_results,
            "original_message": response.choices[0].message.content or ""
        }
        
        llm_log(f"✅ [LLM] Structured tool call response prepared")
        self.logger.info(f"Tool calls structured for execution: {len(tool_results)} calls")
        
        return json.dumps(structured_response)
    
    def _enhance_narrative_from_insights(self, question: str, insights: Dict[str, Any], components: List[Dict], flows: List[Dict]) -> str:
        """Generate enhanced narrative from available insights."""
        from cf.tools.narrative_utils import extract_key_entity
        key_entity = extract_key_entity(question)
        
        narrative = f"Life of {key_entity}:\n\n"
        narrative += f"When exploring '{question}', here's what we discovered:\n\n"
        
        # Add insights from agents
        if insights:
            narrative += "🔍 **Analysis Results:**\n"
            for agent_name, agent_data in insights.items():
                if isinstance(agent_data, dict) and agent_data.get('summary'):
                    narrative += f"• **{agent_name.title()}**: {agent_data['summary']}\n"
            narrative += "\n"
        
        # Add component information if available
        if components:
            narrative += f"🏗️ **System Components Identified:**\n"
            for comp in components[:3]:
                name = comp.get('name', 'Unknown Component')
                comp_type = comp.get('type', 'component')
                narrative += f"• {name} ({comp_type})\n"
            narrative += "\n"
        
        # Add architectural insights based on actual findings, not assumptions
        narrative += f"💡 **Architectural Analysis:**\n"
        
        # Extract insights from what was actually discovered
        architectural_patterns = []
        if insights:
            for agent_name, agent_data in insights.items():
                if isinstance(agent_data, dict):
                    summary = agent_data.get('summary', '')
                    if 'files' in summary or 'components' in summary:
                        architectural_patterns.append("• Multi-component architecture with modular organization")
                    if 'patterns' in summary:
                        architectural_patterns.append("• Design patterns detected in the implementation")
                    if agent_name == 'documentation' and 'documentation' in summary:
                        architectural_patterns.append("• Well-documented system with architectural guides")
        
        if architectural_patterns:
            narrative += '\n'.join(architectural_patterns) + '\n'
        else:
            narrative += "• System architecture follows common software engineering principles\n"
            narrative += "• Component-based design with separation of concerns\n"
            narrative += "• Modular structure supporting maintainability and extensibility\n"
        
        narrative += "\n"
        
        # Add code examples from insights if available
        if insights:
            code_examples_found = False
            for agent_name, agent_data in insights.items():
                if isinstance(agent_data, dict) and agent_name == 'code_architecture':
                    analyzed_files = agent_data.get('analyzed_files', {})
                    if analyzed_files:
                        narrative += "**🔍 Code Examples Found:**\n"
                        code_examples_found = True
                        
                        for file_path, file_analysis in list(analyzed_files.items())[:2]:  # Max 2 files
                            if isinstance(file_analysis, dict):
                                sample_code = file_analysis.get('sample_code', '')
                                functions = file_analysis.get('functions', [])
                                classes = file_analysis.get('classes', [])
                                
                                if sample_code and len(sample_code.strip()) > 30:
                                    narrative += f"```python\n# From {file_path}\n"
                                    # Include relevant lines (not imports)
                                    lines = sample_code.strip().split('\n')
                                    meaningful_lines = []
                                    for line in lines[:8]:
                                        if (line.strip() and 
                                            not line.strip().startswith('import ') and
                                            not line.strip().startswith('from ') and
                                            not line.strip().startswith('#')):
                                            meaningful_lines.append(line)
                                        if len(meaningful_lines) >= 4:
                                            break
                                    narrative += '\n'.join(meaningful_lines[:4]) + '\n```\n\n'
                                
                                elif functions or classes:
                                    narrative += f"**{file_path}**: "
                                    if classes:
                                        narrative += f"Classes: {', '.join(classes[:3])}"
                                    if functions:
                                        if classes:
                                            narrative += f" | Functions: {', '.join(functions[:3])}"
                                        else:
                                            narrative += f"Functions: {', '.join(functions[:3])}"
                                    narrative += "\n"
                        
                        if not code_examples_found:
                            narrative += "\n"
            
            if not code_examples_found:
                narrative += "💡 *Code examples would enhance this analysis - suggest analyzing key source files*\n\n"
        
        return narrative
    
    def _default_journey_stages(self) -> List[str]:
        """Get default journey stages for Life of X narratives."""
        return [
            "Request Initiation",
            "Routing & Processing", 
            "Business Logic Execution",
            "Response Generation"
        ]
    
    def _generate_flow_summary(self, question: str, components: List[Dict], flows: List[Dict]) -> str:
        """Generate flow summary from available data."""
        from cf.tools.narrative_utils import extract_key_entity
        key_entity = extract_key_entity(question)
        
        if components and flows:
            return f"The {key_entity} flows through {len(components)} system components via {len(flows)} data pathways."
        elif components:
            return f"Analysis identified {len(components)} key system components involved in {key_entity}."
        else:
            return f"Completed architectural analysis of {key_entity} processing flow."
    
    def _generate_code_insights(self, insights: Dict[str, Any]) -> List[str]:
        """Generate code insights from agent analysis."""
        code_insights = []
        
        for agent_name, agent_data in insights.items():
            if isinstance(agent_data, dict):
                if agent_name == 'code_architecture':
                    # Extract actual analyzed files and their content
                    analyzed_files = agent_data.get('analyzed_files', {})
                    if analyzed_files:
                        for file_path, file_analysis in analyzed_files.items():
                            if isinstance(file_analysis, dict):
                                # Add function insights
                                functions = file_analysis.get('functions', [])
                                if functions:
                                    code_insights.append(f"📁 {file_path}: Found {len(functions)} functions")
                                    for func in functions[:2]:  # Top 2 functions
                                        code_insights.append(f"  • {func} - core functionality")
                                
                                # Add class insights  
                                classes = file_analysis.get('classes', [])
                                if classes:
                                    code_insights.append(f"📁 {file_path}: Found {len(classes)} classes")
                                    for cls in classes[:2]:  # Top 2 classes
                                        code_insights.append(f"  • {cls} - key component")
                                
                                # Add sample code if available
                                sample_code = file_analysis.get('sample_code', '')
                                if sample_code and len(sample_code.strip()) > 50:
                                    code_insights.append(f"📄 Code example from {file_path}:")
                                    # Include first few lines of meaningful code
                                    lines = sample_code.strip().split('\n')
                                    meaningful_lines = [line for line in lines[:5] if line.strip() and not line.strip().startswith('#')]
                                    if meaningful_lines:
                                        code_insights.append("```python")
                                        code_insights.extend(meaningful_lines[:3])
                                        code_insights.append("```")
                    
                    summary = agent_data.get('summary', '')
                    if 'files' in summary:
                        code_insights.append("✅ Code structure analysis completed")
                    if 'components' in summary:
                        code_insights.append("✅ System components identified and mapped")
                    if 'patterns' in summary:
                        code_insights.append("✅ Architectural patterns detected")
                        
                elif agent_name == 'documentation':
                    summary = agent_data.get('summary', '')
                    if 'documentation' in summary:
                        code_insights.append("📚 Documentation analysis provides implementation context")
        
        if not code_insights:
            code_insights = [
                "🔍 System architecture analysis completed",
                "🏗️ Component relationships mapped", 
                "📊 Processing flow documented"
            ]
        
        return code_insights
    
    def _fallback_reasoning(self, context: str, question: str, agent_type: str) -> Dict[str, Any]:
        """Fallback reasoning when LLM is unavailable."""
        simple_llm = SimpleLLM()
        result = simple_llm.reasoning(context, question, agent_type)
        result['fallback'] = True
        result['model_used'] = 'fallback'
        return result
    
    def _fallback_summary(self, content: str, summary_type: str, focus: str) -> Dict[str, Any]:
        """Fallback summary when LLM is unavailable."""
        simple_llm = SimpleLLM()
        result = simple_llm.summarize(content, summary_type, focus)
        result['fallback'] = True
        result['model_used'] = 'fallback'
        return result
    
    def _fallback_life_of_x_narrative(self, question: str, insights: Dict[str, Any], components: List[Dict], flows: List[Dict], code_examples: List[Dict] = None, key_entity: str = None) -> Dict[str, Any]:
        """Fallback Life of X narrative when LLM is unavailable."""
        # Extract key entity for narrative
        from cf.tools.narrative_utils import extract_key_entity
        key_entity = extract_key_entity(question)
        
        # Create a basic narrative structure
        narrative = f"Life of {key_entity}:\n\n"
        narrative += f"When exploring '{question}', we can trace the journey through the system:\n\n"
        
        # Add component information
        if components:
            narrative += "The request flows through these key components:\n"
            for i, comp in enumerate(components[:5], 1):
                narrative += f"{i}. {comp.get('name', 'Unknown')} ({comp.get('type', 'component')})\n"
            narrative += "\n"
        
        # Add flow information
        if flows:
            narrative += "The data flows through these pathways:\n"
            for i, flow in enumerate(flows[:5], 1):
                narrative += f"{i}. {flow.get('source', 'Unknown')} → {flow.get('target', 'Unknown')}\n"
            narrative += "\n"
        
        # Add insights
        if insights:
            narrative += "🔍 **Analysis Results:**\n"
            for agent_name, agent_insights in insights.items():
                if isinstance(agent_insights, dict) and agent_insights.get('summary'):
                    # Clean up the summary for better display
                    summary = agent_insights['summary'].replace('\\n', '\n').replace('\\\\n', '\n')
                    narrative += f"• **{agent_name.title()}**: {summary}\n"
            narrative += "\n"
        
        # Add architectural guidance based on question
        narrative += f"💡 **Understanding {key_entity}:**\n"
        if "routing" in question.lower():
            narrative += "• Route handling typically involves URL pattern matching\n"
            narrative += "• Request processing through middleware layers\n"
            narrative += "• Response generation and formatting\n"
        elif "authentication" in question.lower() or "auth" in question.lower():
            narrative += "• User credential validation\n"
            narrative += "• Session or token management\n" 
            narrative += "• Authorization and access control\n"
        elif "api" in question.lower():
            narrative += "• Request parsing and validation\n"
            narrative += "• Business logic execution\n"
            narrative += "• Response serialization\n"
        else:
            narrative += "• Request initiation and processing\n"
            narrative += "• Data transformation and validation\n"
            narrative += "• Result generation and delivery\n"
        narrative += "\n"
        
        narrative += "This provides a comprehensive overview of how the system handles this type of request."
        
        return {
            'narrative': narrative,
            'journey_stages': [
                "Initial Request",
                "Component Processing", 
                "Data Flow",
                "Final Response"
            ],
            'key_components': [comp.get('name', 'Unknown') for comp in components[:5]] if components else [],
            'flow_summary': f"The {key_entity} flows through {len(components)} components and {len(flows)} data pathways." if components and flows else "Basic flow analysis completed.",
            'code_insights': [
                "Repository structure analysis completed",
                "Component architecture documented",
                "System flow patterns identified",
                "📝 Note: Install 'litellm' package for enhanced code analysis with LLM integration"
            ],
            'confidence': 0.5,
            'fallback': True,
            'model_used': 'fallback'
        }
    
    def get_supported_models(self) -> Dict[str, List[str]]:
        """Get list of supported models by provider."""
        return {
            'openai': [
                'gpt-4',
                'gpt-4-turbo',
                'gpt-3.5-turbo',
                'gpt-3.5-turbo-16k'
            ],
            'anthropic': [
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229', 
                'claude-3-haiku-20240307'
            ],
            'llama_together_ai': [
                'together_ai/meta-llama/Llama-2-7b-chat-hf',
                'together_ai/meta-llama/Llama-2-13b-chat-hf',
                'together_ai/meta-llama/Llama-2-70b-chat-hf',
                'together_ai/meta-llama/Code-Llama-7b-Python-hf',
                'together_ai/meta-llama/Code-Llama-13b-Python-hf'
            ],
            'llama_replicate': [
                'replicate/meta/llama-2-7b-chat',
                'replicate/meta/llama-2-13b-chat',
                'replicate/meta/llama-2-70b-chat',
                'replicate/meta/code-llama-7b-python',
                'replicate/meta/code-llama-13b-python'
            ],
            'llama_ollama': [
                'ollama/llama2',
                'ollama/llama2:7b',
                'ollama/llama2:13b',
                'ollama/codellama',
                'ollama/codellama:7b'
            ]
        }


# Global instance that can be configured - will be initialized by supervisor
_real_llm_instance = None

def get_real_llm() -> Optional[RealLLM]:
    """Get the current real_llm instance."""
    return _real_llm_instance

def init_real_llm(cf_config: Optional[Dict[str, Any]] = None) -> Optional[RealLLM]:
    """Initialize the global real_llm instance with CodeFusion config."""
    global _real_llm_instance
    
    # Don't initialize if litellm is not available
    if litellm is None:
        print("📝 Note: Install 'litellm' package for enhanced LLM capabilities")
        return None
    
    try:
        instance = RealLLM(cf_config=cf_config)
        # Only set global real_llm if the client is properly initialized
        if instance.client is not None:
            _real_llm_instance = instance
            # Update the module-level variable for imports
            import sys
            sys.modules[__name__].real_llm = instance
            return _real_llm_instance
        else:
            print("⚠️  LLM not configured (no API key), using fallback mode")
            return None
    except Exception as e:
        print(f"⚠️  Failed to initialize LLM: {e}, using fallback mode")
        return None

# For backward compatibility - this will be updated by init_real_llm
real_llm = None