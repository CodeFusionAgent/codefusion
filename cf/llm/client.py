"""
Unified LLM Client for CodeFusion

Direct API calls for better performance and reliability.
Includes retry logic with exponential backoff for rate limiting.
"""

import json
import os
import time
import requests
from typing import Dict, List, Any, Optional, Callable
import traceback

from cf.trace.tracer import trace_method


class LLMClient:
    """Unified LLM client using direct API calls with retry logic and per-model configurations"""

    def __init__(self, llm_config: Dict[str, Any]):
        # Global settings
        self.max_tokens = llm_config.get('max_tokens', 2000)
        self.temperature = llm_config.get('temperature', 0.7)
        self.timeout = llm_config.get('timeout', 60)

        # Retry configuration
        self.max_retries = llm_config.get('max_retries', 3)
        self.retry_delay = llm_config.get('retry_delay_seconds', 2)
        self.use_exponential_backoff = llm_config.get('use_exponential_backoff', True)

        # Per-model configurations
        self.model_configs = llm_config.get('models', {})

        # Backward compatibility: support old config format
        self.model = llm_config.get('model')
        self.api_key = llm_config.get('api_key')

        # Initialize tracer if available
        self.tracer = None
        self.session_id = None

    def _get_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific model.

        Supports per-model configs with fallback to environment variables.

        Args:
            model_name: Model identifier (e.g., "gpt-4o", "claude-sonnet-4-5")

        Returns:
            Model configuration dict with provider, endpoint, API keys, etc.
        """
        # Check if model has specific config
        if model_name in self.model_configs:
            config = self.model_configs[model_name].copy()

            # Fallback to environment variables for API keys
            provider = config.get('provider', self._detect_provider(model_name))

            if provider == 'azure':
                # Azure: subscription_key or AZURE_OPENAI_API_KEY
                if not config.get('subscription_key'):
                    config['subscription_key'] = os.getenv('AZURE_OPENAI_API_KEY', '')
            elif provider == 'anthropic':
                # Anthropic: api_key or ANTHROPIC_API_KEY
                if not config.get('api_key'):
                    config['api_key'] = os.getenv('ANTHROPIC_API_KEY', '')
            elif provider == 'gemini':
                # Google: api_key or GOOGLE_API_KEY
                if not config.get('api_key'):
                    config['api_key'] = os.getenv('GOOGLE_API_KEY', '')
            elif provider in ['openai', 'openai-compatible']:
                # OpenAI: api_key or OPENAI_API_KEY
                if not config.get('api_key'):
                    config['api_key'] = os.getenv('OPENAI_API_KEY', '')

            config['provider'] = provider
            return config

        # Fallback: auto-detect provider and use defaults
        provider = self._detect_provider(model_name)
        config = {
            'provider': provider,
            'model_name': model_name
        }

        if provider == 'anthropic':
            config['api_key'] = os.getenv('ANTHROPIC_API_KEY', self.api_key or '')
            config['base_url'] = 'https://api.anthropic.com/v1/'
        elif provider == 'openai':
            config['api_key'] = os.getenv('OPENAI_API_KEY', self.api_key or '')
            config['base_url'] = 'https://api.openai.com/v1/chat/completions'
        elif provider == 'gemini':
            config['api_key'] = os.getenv('GOOGLE_API_KEY', '')
            config['base_url'] = 'https://generativelanguage.googleapis.com/v1beta/openai/'

        return config

    def _detect_provider(self, model: str) -> str:
        """Detect provider from model name"""
        if not model:
            return 'unknown'
        if model.startswith('claude-'):
            return 'anthropic'
        elif model.startswith('gpt-'):
            return 'openai'  # Could be Azure or standard OpenAI
        elif model.startswith('gemini-'):
            return 'gemini'
        elif 'llama' in model.lower():
            return 'openai-compatible'
        else:
            return 'openai-compatible'  # Default to OpenAI-compatible

    def set_tracer(self, tracer, session_id: str):
        """Set tracer for LLM call logging"""
        self.tracer = tracer
        self.session_id = session_id

    def _retry_with_backoff(self, api_call: Callable, *args, **kwargs) -> Dict[str, Any]:
        """
        Retry API calls with exponential backoff on rate limit errors.

        NEW: Addresses API rate limiting issues with parallel workers.

        Args:
            api_call: The API call function to retry
            *args, **kwargs: Arguments to pass to the API call

        Returns:
            API response dict

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return api_call(*args, **kwargs)

            except requests.exceptions.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response else None

                # Retry on rate limit (429) or server errors (5xx)
                if status_code in [429, 500, 502, 503, 504]:
                    if attempt < self.max_retries:
                        # Calculate delay with exponential backoff
                        if self.use_exponential_backoff:
                            delay = self.retry_delay * (2 ** attempt)  # 2s, 4s, 8s
                        else:
                            delay = self.retry_delay

                        print(f"⚠️ API rate limit/error (HTTP {status_code}), retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})...")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"❌ API call failed after {self.max_retries} retries")
                        raise

                # Don't retry on other errors (auth, bad request, etc.)
                raise

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.retry_delay if not self.use_exponential_backoff else self.retry_delay * (2 ** attempt)
                    print(f"⚠️ Network error, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ API call failed after {self.max_retries} retries")
                    raise

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception

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

        # Make request with retry logic
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }

        def make_request():
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        data = self._retry_with_backoff(make_request)

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

        def make_request():
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        data = self._retry_with_backoff(make_request)

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
        """Direct API call to Azure OpenAI (backward compatibility)"""
        # Build Azure-specific URL using old config format
        api_url = f"{self.azure_endpoint}/openai/deployments/{self.azure_deployment}/chat/completions?api-version={self.azure_api_version}"
        return self._call_azure_openai_custom(messages, self.azure_deployment, api_key, api_url, **kwargs)

    def _call_azure_openai_custom(self, messages: List[Dict], deployment: str, api_key: str, api_url: str, **kwargs) -> Dict[str, Any]:
        """Direct API call to Azure OpenAI with custom URL"""
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

        def make_request():
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        data = self._retry_with_backoff(make_request)

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
            'model': deployment  # Return deployment name
        }

    def _call_with_model_config(self, messages: List[Dict], model_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call LLM API using per-model configuration.

        Args:
            messages: Chat messages
            model_name: Model identifier
            **kwargs: Override parameters (max_tokens, temperature)

        Returns:
            Response dict with content, usage, etc.
        """
        # Get model-specific configuration
        model_config = self._get_model_config(model_name)
        provider = model_config.get('provider')

        if provider == 'anthropic':
            api_key = model_config.get('api_key', '')
            base_url = model_config.get('base_url', 'https://api.anthropic.com/v1/')
            api_url = f"{base_url.rstrip('/')}/messages"
            return self._call_anthropic(messages, model_name, api_key, api_url, **kwargs)

        elif provider == 'azure':
            endpoint = model_config.get('endpoint', '')
            deployment = model_config.get('deployment', model_name)
            api_key = model_config.get('subscription_key', '')
            api_version = model_config.get('api_version', '2024-02-15-preview')

            # Build Azure URL
            api_url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

            # Use modified Azure call that accepts custom URL
            return self._call_azure_openai_custom(messages, deployment, api_key, api_url, **kwargs)

        elif provider in ['openai', 'openai-compatible', 'gemini']:
            api_key = model_config.get('api_key', '')
            base_url = model_config.get('base_url', 'https://api.openai.com/v1/chat/completions')

            # For OpenAI-compatible APIs, ensure URL ends with /chat/completions
            if not base_url.endswith('/chat/completions'):
                base_url = f"{base_url.rstrip('/')}/chat/completions"

            return self._call_openai(messages, model_name, api_key, base_url, **kwargs)

        else:
            raise ValueError(f"Unsupported provider '{provider}' for model '{model_name}'")

    @trace_method("llm_call")
    def generate(self, prompt: str, system_prompt: str = "", model: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generate text response using direct API with per-model configuration.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            model: Model to use (optional, defaults to self.model)
            **kwargs: Override parameters (max_tokens, temperature)

        Returns:
            Response dict with content, usage, duration, etc.
        """
        start_time = time.time()
        model_name = model or self.model

        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            # Call with per-model configuration
            response_data = self._call_with_model_config(messages, model_name, **kwargs)

            duration = time.time() - start_time

            result = {
                'success': True,
                'content': response_data['content'],
                'model': model_name,
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
                        'model': model_name,
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
                'model': model_name,
                'duration': duration
            }

            # Log error to tracer
            if self.tracer and self.session_id:
                self.tracer.log_event(
                    self.session_id,
                    "llm_error",
                    {
                        'model': model_name,
                        'error': str(e),
                        'duration': duration
                    }
                )

            return error_result

    @trace_method("llm_call_fast")
    def generate_fast(self, prompt: str, system_prompt: str = "", model: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generate text response using fast model for routine tasks.

        Delegates to generate() with per-model configuration support.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            model: Fast model to use (optional, will auto-detect from tiers config)
            **kwargs: Override parameters (max_tokens, temperature)

        Returns:
            Response dict with content, usage, duration, etc.
        """
        # Use provided model or try to detect fast model from tier config
        fast_model = model or self.model

        # Delegate to generate() which handles per-model config
        return self.generate(prompt, system_prompt, model=fast_model, **kwargs)

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
