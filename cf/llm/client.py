"""
Unified LLM Client for CodeFusion

Direct API calls for better performance and reliability.
"""

import json
import os
import time
import requests
from typing import Dict, List, Any, Optional
import traceback

from cf.trace.tracer import trace_method


class LLMClient:
    """Unified LLM client using direct API calls"""

    def __init__(self, llm_config: Dict[str, Any]):
        self.model = llm_config.get('model')
        self.api_key = llm_config.get('api_key')
        self.max_tokens = llm_config.get('max_tokens', 2000)
        self.temperature = llm_config.get('temperature', 0.7)
        self.timeout = llm_config.get('timeout', 60)

        # Fast model configuration for routine tasks
        self.fast_model = llm_config.get('fast_model', self.model)
        self.fast_model_api_key = llm_config.get('fast_model_api_key', self.api_key)

        # Azure OpenAI configuration
        self.azure_config = llm_config.get('azure', {})
        self.use_azure = self.azure_config.get('enabled', False)

        if self.use_azure:
            self.azure_endpoint = self.azure_config.get('endpoint', '')
            self.azure_api_version = self.azure_config.get('api_version', '2024-02-15-preview')
            self.azure_deployment = self.azure_config.get('deployment_id', self.model)
            # For Azure, api_key can come from azure config or fallback to main api_key
            self.api_key = self.azure_config.get('api_key') or self.api_key

        # Initialize tracer if available
        self.tracer = None
        self.session_id = None

        # Determine provider from model name or config
        self.provider = self._detect_provider(self.model)
        self.fast_provider = self._detect_provider(self.fast_model)

        # Set up API endpoints
        self.api_url = self._get_api_url(self.provider)
        self.fast_api_url = self._get_api_url(self.fast_provider)

    def _detect_provider(self, model: str) -> str:
        """Detect provider from model name"""
        if model.startswith('claude-'):
            return 'anthropic'
        elif model.startswith('gpt-'):
            return 'openai'
        elif model.startswith('gemini-'):
            return 'google'
        else:
            return 'unknown'

    def _get_api_url(self, provider: str) -> str:
        """Get API URL for provider"""
        if provider == 'anthropic':
            return 'https://api.anthropic.com/v1/messages'
        elif provider == 'openai':
            return 'https://api.openai.com/v1/chat/completions'
        elif provider == 'google':
            return 'https://generativelanguage.googleapis.com/v1beta/models'
        else:
            return ''

    def set_tracer(self, tracer, session_id: str):
        """Set tracer for LLM call logging"""
        self.tracer = tracer
        self.session_id = session_id

    def _call_anthropic(self, messages: List[Dict], model: str, api_key: str,
                        api_url: str, **kwargs) -> Dict[str, Any]:
        """Direct API call to Anthropic"""
        # Extract system message if present
        system_message = None
        user_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                user_messages.append(msg)

        # Build request payload
        payload = {
            'model': model,
            'messages': user_messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
        }

        # Add system message if present
        if system_message:
            payload['system'] = system_message

        # Add temperature if specified
        if 'temperature' in kwargs and kwargs['temperature'] is not None:
            payload['temperature'] = kwargs['temperature']
        elif self.temperature is not None:
            payload['temperature'] = self.temperature

        # Make request
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        data = response.json()

        # Parse response
        content = data['content'][0]['text']
        usage = data.get('usage', {})

        return {
            'content': content,
            'usage': {
                'prompt_tokens': usage.get('input_tokens', 0),
                'completion_tokens': usage.get('output_tokens', 0),
                'total_tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            },
            'finish_reason': data.get('stop_reason', 'stop'),
            'model': model
        }

    def _call_openai(self, messages: List[Dict], model: str, api_key: str,
                     api_url: str, **kwargs) -> Dict[str, Any]:
        """Direct API call to OpenAI"""
        payload = {
            'model': model,
            'messages': messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
        }

        # Add temperature if specified
        if 'temperature' in kwargs and kwargs['temperature'] is not None:
            payload['temperature'] = kwargs['temperature']
        elif self.temperature is not None:
            payload['temperature'] = self.temperature

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        data = response.json()

        # Parse response
        choice = data['choices'][0]
        content = choice['message']['content']
        usage = data.get('usage', {})

        return {
            'content': content,
            'usage': {
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0)
            },
            'finish_reason': choice.get('finish_reason', 'stop'),
            'model': model
        }

    def _call_azure_openai(self, messages: List[Dict], model: str, api_key: str, **kwargs) -> Dict[str, Any]:
        """Direct API call to Azure OpenAI"""
        # Build Azure-specific URL
        api_url = f"{self.azure_endpoint}/openai/deployments/{self.azure_deployment}/chat/completions?api-version={self.azure_api_version}"

        payload = {
            'messages': messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
        }

        # Add temperature if specified
        if 'temperature' in kwargs and kwargs['temperature'] is not None:
            payload['temperature'] = kwargs['temperature']
        elif self.temperature is not None:
            payload['temperature'] = self.temperature

        # Azure uses api-key header instead of Authorization
        headers = {
            'api-key': api_key,
            'Content-Type': 'application/json'
        }

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        data = response.json()

        # Parse response (same format as OpenAI)
        choice = data['choices'][0]
        content = choice['message']['content']
        usage = data.get('usage', {})

        return {
            'content': content,
            'usage': {
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0)
            },
            'finish_reason': choice.get('finish_reason', 'stop'),
            'model': self.azure_deployment  # Return deployment name
        }

    @trace_method("llm_call")
    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> Dict[str, Any]:
        """Generate text response using direct API"""
        start_time = time.time()

        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            # Call appropriate provider
            if self.provider == 'anthropic':
                response_data = self._call_anthropic(
                    messages, self.model, self.api_key, self.api_url, **kwargs
                )
            elif self.provider == 'openai':
                # Check if using Azure OpenAI
                if self.use_azure:
                    response_data = self._call_azure_openai(
                        messages, self.model, self.api_key, **kwargs
                    )
                else:
                    response_data = self._call_openai(
                        messages, self.model, self.api_key, self.api_url, **kwargs
                    )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            duration = time.time() - start_time

            result = {
                'success': True,
                'content': response_data['content'],
                'model': self.model,
                'provider': response_data['model'],
                'usage': response_data['usage'],
                'finish_reason': response_data['finish_reason'],
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
            traceback.print_exc()
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

    @trace_method("llm_call_fast")
    def generate_fast(self, prompt: str, system_prompt: str = "", **kwargs) -> Dict[str, Any]:
        """Generate text response using fast model for routine tasks"""
        start_time = time.time()

        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            # Call appropriate provider for fast model
            if self.fast_provider == 'anthropic':
                response_data = self._call_anthropic(
                    messages, self.fast_model, self.fast_model_api_key,
                    self.fast_api_url, **kwargs
                )
            elif self.fast_provider == 'openai':
                # Check if using Azure OpenAI
                if self.use_azure:
                    response_data = self._call_azure_openai(
                        messages, self.fast_model, self.fast_model_api_key, **kwargs
                    )
                else:
                    response_data = self._call_openai(
                        messages, self.fast_model, self.fast_model_api_key,
                        self.fast_api_url, **kwargs
                    )
            else:
                raise ValueError(f"Unsupported fast provider: {self.fast_provider}")

            duration = time.time() - start_time

            result = {
                'success': True,
                'content': response_data['content'],
                'model': self.fast_model,
                'provider': response_data['model'],
                'usage': response_data['usage'],
                'finish_reason': response_data['finish_reason'],
                'duration': duration
            }

            # Log to tracer if available
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_generation_fast",
                    {
                        'model': self.fast_model,
                        'prompt_tokens': result['usage']['prompt_tokens'],
                        'completion_tokens': result['usage']['completion_tokens'],
                        'duration': duration,
                        'success': True
                    }
                )

            return result

        except Exception as e:
            traceback.print_exc()
            duration = time.time() - start_time

            error_result = {
                'success': False,
                'error': str(e),
                'model': self.fast_model,
                'duration': duration
            }

            # Log error to tracer
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_fast_error",
                    {
                        'model': self.fast_model,
                        'error': str(e),
                        'duration': duration
                    }
                )

            return error_result

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Estimate token count (approximation)"""
        # Simple approximation: ~4 characters per token
        return len(text) // 4

    def is_available(self) -> bool:
        """Check if LLM client is properly configured and available"""
        try:
            # Quick test call with minimal tokens
            response = self.generate("Hi", max_tokens=10)
            return response.get('success', False)
        except:
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            'model': self.model,
            'fast_model': self.fast_model,
            'provider': self.provider,
            'fast_provider': self.fast_provider,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'available': self.is_available()
        }
