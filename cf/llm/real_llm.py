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
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or self._load_config()
        self.logger = logging.getLogger(self.__class__.__name__)
        
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
            import litellm
            
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
            prompt = self._build_reasoning_prompt(context, question, agent_type)
            response = self._call_llm(prompt)
            
            # Parse the response
            parsed_response = self._parse_reasoning_response(response)
            
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
            prompt = self._build_summary_prompt(content, summary_type, focus)
            response = self._call_llm(prompt)
            
            # Parse the response
            parsed_response = self._parse_summary_response(response)
            
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
    
    def _call_llm(self, prompt: str) -> str:
        """Make LLM API call using LiteLLM."""
        try:
            response = self.client.completion(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                timeout=self.config.timeout
            )
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"LiteLLM API call failed: {e}")
            raise
    
    def _build_reasoning_prompt(self, context: str, question: str, agent_type: str) -> str:
        """Build reasoning prompt for LLM."""
        # Check if this is a LLaMA model for special formatting
        is_llama = any(llama_indicator in self.config.model.lower() 
                      for llama_indicator in ['llama', 'meta-llama'])
        
        base_prompt = f"""You are a {agent_type} agent in a ReAct (Reasoning + Acting) framework analyzing a codebase. 

Your task is to reason about what action to take next based on the current context and goal.

CONTEXT:
{context}

QUESTION/GOAL:
{question}

Please provide your reasoning following this structure:
1. REASONING: What should I do next and why?
2. CONFIDENCE: How confident are you in this reasoning (0.0-1.0)?
3. SUGGESTED_ACTIONS: List of 2-3 specific actions to take next
4. CONTEXT_ANALYSIS: Key insights from the current context

Format your response as JSON with these keys: reasoning, confidence, suggested_actions, context_analysis.

Focus on being systematic, thorough, and adaptive based on what you've learned so far."""

        if is_llama:
            return f"<s>[INST] {base_prompt} [/INST]"
        else:
            return base_prompt
    
    def _build_summary_prompt(self, content: str, summary_type: str, focus: str) -> str:
        """Build summary prompt for LLM."""
        # Check if this is a LLaMA model for special formatting
        is_llama = any(llama_indicator in self.config.model.lower() 
                      for llama_indicator in ['llama', 'meta-llama'])
        
        base_prompt = f"""You are analyzing codebase content and need to generate a {summary_type} summary with focus on {focus}.

CONTENT TO SUMMARIZE:
{content}

Please provide a comprehensive summary following this structure:
1. SUMMARY: Clear, concise summary of the key findings
2. KEY_POINTS: List of 3-5 most important points
3. CONFIDENCE: How confident are you in this summary (0.0-1.0)?
4. CONTENT_ANALYSIS: Additional insights about the content

Format your response as JSON with these keys: summary, key_points, confidence, content_analysis.

Focus on extracting the most valuable insights and presenting them clearly."""

        if is_llama:
            return f"<s>[INST] {base_prompt} [/INST]"
        else:
            return base_prompt
    
    def _parse_reasoning_response(self, response: str) -> Dict[str, Any]:
        """Parse reasoning response from LLM."""
        try:
            # Clean response
            response = response.strip()
            
            # Remove markdown code blocks if present
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            # Try to parse as JSON first
            if response.strip().startswith('{'):
                return json.loads(response)
            
            # If not JSON, extract key information with more robust parsing
            result = {}
            lines = response.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith('1. REASONING:') or line.startswith('REASONING:'):
                    reasoning_text = line.split('REASONING:', 1)[1].strip()
                    # Look for additional lines that might be part of reasoning
                    for j in range(i+1, len(lines)):
                        next_line = lines[j].strip()
                        if next_line.startswith('2.') or next_line.startswith('CONFIDENCE:'):
                            break
                        reasoning_text += " " + next_line
                    result['reasoning'] = reasoning_text
                
                elif line.startswith('2. CONFIDENCE:') or line.startswith('CONFIDENCE:'):
                    confidence_text = line.split('CONFIDENCE:', 1)[1].strip()
                    try:
                        # Extract number from text like "0.8" or "80%" or "8/10"
                        import re
                        numbers = re.findall(r'0\.\d+|\d+%|\d+/10', confidence_text)
                        if numbers:
                            conf_str = numbers[0]
                            if '%' in conf_str:
                                result['confidence'] = float(conf_str.replace('%', '')) / 100
                            elif '/' in conf_str:
                                parts = conf_str.split('/')
                                result['confidence'] = float(parts[0]) / float(parts[1])
                            else:
                                result['confidence'] = float(conf_str)
                    except ValueError:
                        result['confidence'] = 0.8
                
                elif line.startswith('3. SUGGESTED_ACTIONS:') or line.startswith('SUGGESTED_ACTIONS:'):
                    actions_text = line.split('SUGGESTED_ACTIONS:', 1)[1].strip()
                    # Parse actions from text
                    actions = [a.strip() for a in actions_text.split(',')]
                    # Clean up actions
                    cleaned_actions = []
                    for action in actions:
                        action = action.strip('- ').strip()
                        if action:
                            cleaned_actions.append(action)
                    result['suggested_actions'] = cleaned_actions
            
            # Set defaults if not found
            if 'reasoning' not in result:
                result['reasoning'] = response
            if 'confidence' not in result:
                result['confidence'] = 0.8
            if 'suggested_actions' not in result:
                result['suggested_actions'] = ['read_file', 'search_files']
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse reasoning response: {e}")
            return {
                'reasoning': response, 
                'confidence': 0.5, 
                'suggested_actions': ['read_file'],
                'parsing_error': str(e)
            }
    
    def _parse_summary_response(self, response: str) -> Dict[str, Any]:
        """Parse summary response from LLM."""
        try:
            # Clean response
            response = response.strip()
            
            # Remove markdown code blocks if present
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            # Try to parse as JSON first
            if response.strip().startswith('{'):
                return json.loads(response)
            
            # If not JSON, extract key information
            result = {}
            lines = response.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith('1. SUMMARY:') or line.startswith('SUMMARY:'):
                    summary_text = line.split('SUMMARY:', 1)[1].strip()
                    # Look for additional lines that might be part of summary
                    for j in range(i+1, len(lines)):
                        next_line = lines[j].strip()
                        if next_line.startswith('2.') or next_line.startswith('KEY_POINTS:'):
                            break
                        summary_text += " " + next_line
                    result['summary'] = summary_text
                
                elif line.startswith('2. KEY_POINTS:') or line.startswith('KEY_POINTS:'):
                    points_text = line.split('KEY_POINTS:', 1)[1].strip()
                    # Parse key points
                    points = []
                    if points_text:
                        points.append(points_text)
                    # Look for additional bullet points
                    for j in range(i+1, len(lines)):
                        next_line = lines[j].strip()
                        if next_line.startswith('3.') or next_line.startswith('CONFIDENCE:'):
                            break
                        if next_line.startswith('-') or next_line.startswith('•'):
                            points.append(next_line.strip('- •').strip())
                    result['key_points'] = points
                
                elif line.startswith('3. CONFIDENCE:') or line.startswith('CONFIDENCE:'):
                    confidence_text = line.split('CONFIDENCE:', 1)[1].strip()
                    try:
                        import re
                        numbers = re.findall(r'0\.\d+|\d+%|\d+/10', confidence_text)
                        if numbers:
                            conf_str = numbers[0]
                            if '%' in conf_str:
                                result['confidence'] = float(conf_str.replace('%', '')) / 100
                            elif '/' in conf_str:
                                parts = conf_str.split('/')
                                result['confidence'] = float(parts[0]) / float(parts[1])
                            else:
                                result['confidence'] = float(conf_str)
                    except ValueError:
                        result['confidence'] = 0.7
            
            # Set defaults if not found
            if 'summary' not in result:
                result['summary'] = response
            if 'key_points' not in result:
                result['key_points'] = []
            if 'confidence' not in result:
                result['confidence'] = 0.7
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse summary response: {e}")
            return {
                'summary': response, 
                'key_points': [], 
                'confidence': 0.5,
                'parsing_error': str(e)
            }
    
    def _fallback_reasoning(self, context: str, question: str, agent_type: str) -> Dict[str, Any]:
        """Fallback reasoning when LLM is unavailable."""
        from .simple_llm import SimpleLLM
        simple_llm = SimpleLLM()
        result = simple_llm.reasoning(context, question, agent_type)
        result['fallback'] = True
        result['model_used'] = 'fallback'
        return result
    
    def _fallback_summary(self, content: str, summary_type: str, focus: str) -> Dict[str, Any]:
        """Fallback summary when LLM is unavailable."""
        from .simple_llm import SimpleLLM
        simple_llm = SimpleLLM()
        result = simple_llm.summarize(content, summary_type, focus)
        result['fallback'] = True
        result['model_used'] = 'fallback'
        return result
    
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


# Global instance that can be configured
real_llm = RealLLM()