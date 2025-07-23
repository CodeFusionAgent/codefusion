"""
Unified LLM Client for CodeFusion

Clean interface using LiteLLM with tracing support.
"""

import json
import time
from typing import Dict, List, Any, Optional

try:
    import litellm
    from litellm import completion, embedding
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

from cf.trace.tracer import trace_method


class LLMClient:
    """Unified LLM client using LiteLLM with tracing"""
    
    def __init__(self, llm_config: Dict[str, Any]):
        if not LITELLM_AVAILABLE:
            raise ImportError("LiteLLM not available. Install with: pip install litellm")
        
        self.model = llm_config.get('model', 'gpt-4o')
        self.api_key = llm_config.get('api_key')
        self.max_tokens = llm_config.get('max_tokens', 2000)
        self.temperature = llm_config.get('temperature', 0.7)
        self.timeout = llm_config.get('timeout', 30)
        
        # Initialize tracer if available
        self.tracer = None
        self.session_id = None
        
        # Set API key in environment if provided
        if self.api_key:
            import os
            if self.model.startswith('gpt-'):
                os.environ['OPENAI_API_KEY'] = self.api_key
            elif self.model.startswith('claude-'):
                os.environ['ANTHROPIC_API_KEY'] = self.api_key
            elif self.model.startswith('gemini-'):
                os.environ['GOOGLE_API_KEY'] = self.api_key
        
        # Configure LiteLLM
        litellm.set_verbose = False  # Disable debugging for clean output
        litellm.drop_params = True  # Drop unsupported params automatically
    
    def set_tracer(self, tracer, session_id: str):
        """Set tracer for LLM call logging"""
        self.tracer = tracer
        self.session_id = session_id
    
    @trace_method("llm_call")
    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Dict[str, Any]:
        """Generate text response using LiteLLM"""
        start_time = time.time()
        
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            # Count input tokens
            input_tokens = self.count_tokens(prompt + (system_prompt or ""))
            
            # Call LiteLLM
            response = completion(
                model=self.model,
                messages=messages,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
                timeout=self.timeout,
                **kwargs
            )
            
            duration = time.time() - start_time
            
            result = {
                'success': True,
                'content': response.choices[0].message.content,
                'model': self.model,
                'provider': response.model,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens if response.usage else input_tokens,
                    'completion_tokens': response.usage.completion_tokens if response.usage else 0,
                    'total_tokens': response.usage.total_tokens if response.usage else input_tokens
                },
                'finish_reason': response.choices[0].finish_reason,
                'duration': duration
            }
            
            # Log to tracer if available
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_generation",
                    {
                        'model': self.model,
                        'prompt_tokens': result['usage']['prompt_tokens'],
                        'completion_tokens': result['usage']['completion_tokens'],
                        'duration': duration,
                        'success': True
                    }
                )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            error_result = {
                'success': False,
                'error': str(e),
                'model': self.model,
                'duration': duration
            }
            
            # Log error to tracer
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_error",
                    {
                        'model': self.model,
                        'error': str(e),
                        'duration': duration
                    }
                )
            
            return error_result
    
    @trace_method("llm_function_call")
    def generate_with_functions(self, prompt: str, functions: List[Dict], system_prompt: str = "") -> Dict[str, Any]:
        """Generate response with function calling support"""
        start_time = time.time()
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Functions are already in OpenAI format: {"type": "function", "function": {...}}
            # Just pass them directly to LiteLLM
            tools = functions
            
            input_tokens = self.count_tokens(prompt + (system_prompt or ""))
            
            response = completion(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout
            )
            
            duration = time.time() - start_time
            
            result = {
                'success': True,
                'content': response.choices[0].message.content,
                'model': self.model,
                'provider': response.model,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens if response.usage else input_tokens,
                    'completion_tokens': response.usage.completion_tokens if response.usage else 0,
                    'total_tokens': response.usage.total_tokens if response.usage else input_tokens
                },
                'finish_reason': response.choices[0].finish_reason,
                'duration': duration
            }
            
            # Check for tool calls
            function_called = None
            if response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                function_called = tool_call.function.name
                result['function_call'] = {
                    'name': function_called,
                    'arguments': json.loads(tool_call.function.arguments)
                }
            
            # Log to tracer
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_function_call",
                    {
                        'model': self.model,
                        'functions_available': len(functions),
                        'function_called': function_called,
                        'prompt_tokens': result['usage']['prompt_tokens'],
                        'completion_tokens': result['usage']['completion_tokens'],
                        'duration': duration,
                        'success': True
                    }
                )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            error_result = {
                'success': False,
                'error': f'Function calling failed: {str(e)}',
                'model': self.model,
                'duration': duration
            }
            
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_function_error",
                    {
                        'model': self.model,
                        'error': str(e),
                        'duration': duration
                    }
                )
            
            return error_result
    
    @trace_method("llm_embedding")
    def embed_text(self, text: str) -> Dict[str, Any]:
        """Generate text embeddings for semantic search"""
        start_time = time.time()
        
        try:
            # Use OpenAI embedding model by default
            embedding_model = "text-embedding-ada-002"
            
            response = embedding(
                model=embedding_model,
                input=[text]
            )
            
            duration = time.time() - start_time
            
            result = {
                'success': True,
                'embedding': response.data[0].embedding,
                'model': embedding_model,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens if response.usage else 0,
                    'total_tokens': response.usage.total_tokens if response.usage else 0
                },
                'duration': duration
            }
            
            # Log to tracer
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_embedding",
                    {
                        'model': embedding_model,
                        'text_length': len(text),
                        'tokens': result['usage']['total_tokens'],
                        'duration': duration,
                        'success': True
                    }
                )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            error_result = {
                'success': False,
                'error': f'Embedding failed: {str(e)}',
                'duration': duration
            }
            
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_embedding_error",
                    {
                        'error': str(e),
                        'duration': duration
                    }
                )
            
            return error_result
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens using LiteLLM's token counter"""
        try:
            return litellm.token_counter(
                model=model or self.model,
                text=text
            )
        except:
            # Fallback approximation
            return len(text) // 4
    
    def is_available(self) -> bool:
        """Check if LLM client is properly configured and available"""
        try:
            # Quick test call with minimal tokens
            response = self.generate("Hi", max_tokens=1)
            return response.get('success', False)
        except:
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            'model': self.model,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'available': self.is_available(),
            'litellm_version': getattr(litellm, '__version__', 'unknown')
        }
    
    def get_supported_models(self) -> List[str]:
        """Get list of models supported by LiteLLM"""
        try:
            return litellm.model_list
        except:
            return [
                'gpt-4o', 'gpt-4', 'gpt-3.5-turbo',
                'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
                'gemini-pro', 'gemini-1.5-pro'
            ]