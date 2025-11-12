"""
Unified LLM Client for CodeFusion

Uses provider-specific SDKs for better reliability and features.
Includes retry logic with exponential backoff for rate limiting.
"""

import json
import os
import time
import requests
from typing import Dict, List, Any, Optional, Callable
import traceback
import hashlib
import random
from cf.trace.tracer import trace_method

# Import provider SDKs
try:
    from openai import OpenAI, AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LLMClient:
    """Unified LLM client using direct API calls with retry logic and per-model configurations"""

    def __init__(self, llm_config: Dict[str, Any]):
        # Global settings
        self.max_tokens = llm_config.get('max_tokens', 2000)
        # Do not set a default temperature; many provider deployments only allow default (1) or reject custom values
        self.temperature = llm_config.get('temperature', None)
        self.timeout = llm_config.get('timeout', 60)

        # Retry configuration
        self.max_retries = llm_config.get('max_retries', 3)
        self.retry_delay = llm_config.get('retry_delay_seconds', 2)
        self.use_exponential_backoff = llm_config.get('use_exponential_backoff', True)

        # Per-model configurations
        self.model_configs = llm_config.get('models', {})

        # Tiered models (fast/standard/advanced) for auto-selection when model is not specified
        self.tiers = llm_config.get('tiers', {})

        # Backward compatibility: support old config format
        self.model = llm_config.get('model')
        self.api_key = llm_config.get('api_key')

        # Initialize tracer if available
        self.tracer = None
        self.session_id = None

    def _get_tier_model(self, tier_name: str) -> Optional[str]:
        """Get model configured for a given tier (e.g., 'fast', 'standard', 'advanced')."""
        try:
            tier_cfg = self.tiers.get(tier_name, {})
            model = tier_cfg.get('model')
            return model
        except Exception:
            return None

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

        Handles both SDK exceptions and legacy requests exceptions.

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

            except Exception as e:
                last_exception = e

                # Check if it's a retryable error
                should_retry = False
                error_type = "unknown"

                # Handle OpenAI SDK exceptions
                if OPENAI_AVAILABLE and hasattr(e, 'status_code'):
                    status_code = getattr(e, 'status_code', None)
                    if status_code in [429, 500, 502, 503, 504]:
                        should_retry = True
                        error_type = f"HTTP {status_code}"

                # Handle Anthropic SDK exceptions
                elif ANTHROPIC_AVAILABLE and 'anthropic' in str(type(e).__module__):
                    error_str = str(e).lower()
                    if 'rate' in error_str or '429' in error_str or '5' in str(getattr(e, 'status_code', '')):
                        should_retry = True
                        error_type = "rate limit/server error"

                # Handle legacy requests exceptions
                elif hasattr(e, 'response'):
                    status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                    if status_code in [429, 500, 502, 503, 504]:
                        should_retry = True
                        error_type = f"HTTP {status_code}"

                # Handle timeout/connection errors
                elif 'timeout' in str(type(e).__name__).lower() or 'connection' in str(type(e).__name__).lower():
                    should_retry = True
                    error_type = "network error"

                if should_retry and attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    if self.use_exponential_backoff:
                        delay = self.retry_delay * (2 ** attempt)  # 2s, 4s, 8s
                    else:
                        delay = self.retry_delay

                    print(f"⚠️ API {error_type}, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})...")
                    time.sleep(delay)
                    continue
                elif should_retry:
                    print(f"❌ API call failed after {self.max_retries} retries")
                    raise
                else:
                    # Don't retry on other errors (auth, bad request, etc.)
                    raise

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception

    def _call_anthropic(self, messages: List[Dict], model: str, api_key: str,
                        api_url: str, **kwargs) -> Dict[str, Any]:
        """Call Anthropic API using their SDK"""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")

        # Extract system message if present
        system_message = None
        user_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                user_messages.append(msg)

        # Initialize Anthropic client
        client = Anthropic(api_key=api_key, base_url=api_url.rsplit('/', 1)[0] if '/messages' in api_url else api_url)

        # Build request parameters
        params = {
            'model': model,
            'messages': user_messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
        }

        # Add system message if present
        if system_message:
            params['system'] = system_message

        # Add temperature only if explicitly provided (some models reject non-default values)
        if 'temperature' in kwargs and kwargs['temperature'] is not None:
            params['temperature'] = kwargs['temperature']

        # Make request with retry logic
        def make_request():
            response = client.messages.create(**params)
            return response

        data = self._retry_with_backoff(make_request)

        # Parse response
        content = data.content[0].text
        usage = data.usage

        return {
            'content': content,
            'usage': {
                'prompt_tokens': usage.input_tokens,
                'completion_tokens': usage.output_tokens,
                'total_tokens': usage.input_tokens + usage.output_tokens
            },
            'finish_reason': data.stop_reason,
            'model': model
        }

    def _call_openai(self, messages: List[Dict], model: str, api_key: str,
                     api_url: str, **kwargs) -> Dict[str, Any]:
        """Call OpenAI API using their SDK"""
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Install with: pip install openai")

        # Initialize OpenAI client with base_url (supports OpenAI-compatible APIs)
        # Extract base URL (remove /chat/completions suffix if present)
        base_url = api_url.rsplit('/chat/completions', 1)[0] if '/chat/completions' in api_url else api_url
        client = OpenAI(api_key=api_key, base_url=base_url)

        # Build request parameters
        params = {
            'model': model,
            'messages': messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
        }

        # Add temperature if specified
        if 'temperature' in kwargs and kwargs['temperature'] is not None:
            params['temperature'] = kwargs['temperature']

        # Make request with retry logic
        def make_request():
            response = client.chat.completions.create(**params)
            return response

        data = self._retry_with_backoff(make_request)

        # Parse response
        choice = data.choices[0]
        content = choice.message.content
        usage = data.usage

        return {
            'content': content,
            'usage': {
                'prompt_tokens': usage.prompt_tokens,
                'completion_tokens': usage.completion_tokens,
                'total_tokens': usage.total_tokens
            },
            'finish_reason': choice.finish_reason,
            'model': model
        }

    def _call_azure_openai(self, messages: List[Dict], model: str, api_key: str, **kwargs) -> Dict[str, Any]:
        """Direct API call to Azure OpenAI (backward compatibility)"""
        # Build Azure-specific URL using old config format
        api_url = f"{self.azure_endpoint}/openai/deployments/{self.azure_deployment}/chat/completions?api-version={self.azure_api_version}"
        return self._call_azure_openai_custom(messages, self.azure_deployment, api_key, api_url, **kwargs)

    def _call_azure_openai_custom(self, messages: List[Dict], deployment: str, api_key: str, api_url: str, **kwargs) -> Dict[str, Any]:
        """Call Azure OpenAI API using their SDK"""
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Install with: pip install openai")

        # Extract endpoint and API version from URL
        # URL format: https://{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={version}
        import re
        endpoint_match = re.match(r'(https://[^/]+)', api_url)
        version_match = re.search(r'api-version=([^&]+)', api_url)

        endpoint = endpoint_match.group(1) if endpoint_match else api_url.split('/openai')[0]
        api_version = version_match.group(1) if version_match else '2024-02-15-preview'

        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )

        # Build request parameters
        params = {
            'model': deployment,  # Azure uses deployment name
            'messages': messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
        }

        # Add temperature if specified
        if 'temperature' in kwargs and kwargs['temperature'] is not None:
            params['temperature'] = kwargs['temperature']
        elif self.temperature is not None:
            params['temperature'] = self.temperature

        # Make request with retry logic
        def make_request():
            response = client.chat.completions.create(**params)
            return response

        data = self._retry_with_backoff(make_request)

        # Parse response (same format as OpenAI)
        choice = data.choices[0]
        content = choice.message.content
        usage = data.usage

        return {
            'content': content,
            'usage': {
                'prompt_tokens': usage.prompt_tokens,
                'completion_tokens': usage.completion_tokens,
                'total_tokens': usage.total_tokens
            },
            'finish_reason': choice.finish_reason,
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
        # Resolve model: explicit arg > configured default > STANDARD tier > any configured model
        model_name = model or self.model or self._get_tier_model('standard')
        if not model_name:
            # Fallback: pick the first configured model if available
            model_name = next(iter(self.model_configs.keys()), None)
        if not model_name:
            raise ValueError("No model specified and no tier/configured models available. Configure llm.tiers.standard.model or pass model explicitly.")

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
        # Use provided model or FAST tier model by default (do not require llm.model)
        fast_model = model or self._get_tier_model('fast') or self.model
        if not fast_model:
            # As a last resort, try STANDARD tier
            fast_model = self._get_tier_model('standard') or next(iter(self.model_configs.keys()), None)
        if not fast_model:
            raise ValueError("No fast/standard model configured. Set llm.tiers.fast.model or pass model explicitly.")

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
        """Get information about configured models"""
        return {
            'default_model': self.model,
            'configured_models': list(self.model_configs.keys()),
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'use_exponential_backoff': self.use_exponential_backoff
        }

    def embed_text(self, text: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Return a deterministic local embedding vector for the given text.

        This prevents failures when semantic cache requests embeddings and no
        external embedding API is configured. It's a lightweight fallback using
        a hash-seeded pseudo-random generator to produce stable vectors.

        Args:
            text: Input text to embed
            model: Optional embedding model name (ignored for local fallback)

        Returns:
            Dict with 'success' and 'embedding' (list[float])
        """
        try:

            # Produce a stable seed from text
            seed_int = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
            rng = random.Random(seed_int)

            # Generate a 128-dim vector with values in [-1, 1]
            dim = 128
            embedding = [rng.uniform(-1.0, 1.0) for _ in range(dim)]

            return {
                'success': True,
                'embedding': embedding,
                'model': model or 'local-fallback-embedding-128d'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
