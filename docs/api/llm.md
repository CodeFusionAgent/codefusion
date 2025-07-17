# LLM Integration

The CodeFusion ReAct framework provides comprehensive Language Model integration for AI-powered reasoning and analysis.

## Real LLM Provider

::: cf.llm.real_llm.RealLLM

::: cf.llm.real_llm.LLMConfig

## Overview

The LLM integration supports multiple providers through LiteLLM:

- **OpenAI**: GPT-4, GPT-3.5-turbo, and other models
- **Anthropic**: Claude 3 Opus, Sonnet, and Haiku
- **LLaMA**: Via Together AI, Replicate, or Ollama
- **Other Providers**: 100+ models via LiteLLM

## Basic Usage

### OpenAI Integration

```python
from cf.llm.real_llm import RealLLM, LLMConfig
import os

# Configure OpenAI
os.environ['CF_LLM_MODEL'] = 'gpt-4'
os.environ['CF_LLM_API_KEY'] = 'your-openai-api-key'

# Initialize LLM
llm = RealLLM()

# Use for reasoning
reasoning_result = llm.reasoning(
    context="Current codebase analysis state",
    question="What should I examine next for security vulnerabilities?",
    agent_type="codebase"
)

print(f"Reasoning: {reasoning_result['reasoning']}")
print(f"Confidence: {reasoning_result['confidence']}")
print(f"Suggested Actions: {reasoning_result['suggested_actions']}")
```

### Anthropic Integration

```python
# Configure Anthropic Claude
os.environ['CF_LLM_MODEL'] = 'claude-3-sonnet-20240229'
os.environ['CF_LLM_API_KEY'] = 'your-anthropic-api-key'

llm = RealLLM()

# Use for summarization
summary_result = llm.summarize(
    content="Large codebase analysis results...",
    summary_type="comprehensive",
    focus="security patterns"
)

print(f"Summary: {summary_result['summary']}")
print(f"Key Points: {summary_result['key_points']}")
```

### LLaMA Integration

```python
# Configure LLaMA via Together AI
os.environ['CF_LLM_MODEL'] = 'together_ai/meta-llama/Llama-2-7b-chat-hf'
os.environ['CF_LLM_API_KEY'] = 'your-together-ai-key'

llm = RealLLM()

# LLaMA models use special prompt formatting automatically
result = llm.reasoning(
    context="Repository analysis context",
    question="Analyze the architectural patterns",
    agent_type="architecture"
)
```

## Advanced Configuration

### Custom LLM Configuration

```python
# Detailed configuration
config = LLMConfig(
    model="gpt-4",
    api_key="your-api-key",
    api_base="https://custom-endpoint.com/v1",  # Optional custom endpoint
    max_tokens=2000,
    temperature=0.3,  # Lower for more focused analysis
    timeout=60
)

llm = RealLLM(config)
```

### Environment Variable Configuration

```python
# Set via environment variables
import os

# Model selection
os.environ['CF_LLM_MODEL'] = 'gpt-4'
os.environ['CF_LLM_API_KEY'] = 'your-api-key'

# Performance tuning
os.environ['CF_LLM_MAX_TOKENS'] = '1500'
os.environ['CF_LLM_TEMPERATURE'] = '0.2'
os.environ['CF_LLM_TIMEOUT'] = '45'

# Custom endpoint (optional)
os.environ['CF_LLM_API_BASE'] = 'https://custom-api.com/v1'

llm = RealLLM()  # Automatically loads from environment
```

## Supported Models

### OpenAI Models

```python
# Get available OpenAI models
supported_models = llm.get_supported_models()['openai']
print("OpenAI Models:", supported_models)
# ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-3.5-turbo-16k']
```

### Anthropic Models

```python
# Claude models
anthropic_models = llm.get_supported_models()['anthropic']
print("Anthropic Models:", anthropic_models)
# ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']
```

### LLaMA Models

```python
# LLaMA via different providers
together_models = llm.get_supported_models()['llama_together_ai']
replicate_models = llm.get_supported_models()['llama_replicate']
ollama_models = llm.get_supported_models()['llama_ollama']
```

## Fallback System

### Simple LLM Fallback

::: cf.llm.simple_llm.SimpleLLM

```python
# Automatic fallback when real LLM is unavailable
llm = RealLLM()

# If LiteLLM is not installed or API key is missing,
# automatically falls back to SimpleLLM
result = llm.reasoning(
    context="Analysis context",
    question="What to do next?",
    agent_type="general"
)

# Check if fallback was used
if result.get('fallback'):
    print("Using fallback reasoning system")
```

## Integration with ReAct Agents

### In Agent Implementation

```python
from cf.core.react_agent import ReActAgent, ActionType

class LLMEnhancedAgent(ReActAgent):
    def reason(self) -> str:
        """Use LLM for enhanced reasoning."""
        # Get LLM reasoning
        llm_result = self.llm.reasoning(
            context=str(self.state.current_context),
            question=f"How to achieve: {self.state.goal}",
            agent_type=self.agent_name
        )
        
        # Combine with rule-based reasoning
        if llm_result['confidence'] > 0.7:
            return llm_result['reasoning']
        else:
            return self._fallback_reasoning()
    
    def _generate_summary(self) -> str:
        """LLM-powered summary generation."""
        summary_result = self.llm.summarize(
            content=str(self.state.observations),
            summary_type="agent_summary",
            focus=self.state.goal
        )
        return summary_result['summary']
```

### Custom Prompts

```python
class CustomLLMAgent(ReActAgent):
    def _create_custom_prompt(self, context: str, question: str) -> str:
        """Create domain-specific prompts."""
        if self.agent_name == "security":
            return f"""
            You are a security analysis expert. Given the context:
            {context}
            
            Security Question: {question}
            
            Focus on:
            1. Potential vulnerabilities
            2. Security best practices
            3. Risk assessment
            4. Mitigation strategies
            
            Provide your analysis in JSON format.
            """
        
        return super()._build_reasoning_prompt(context, question, self.agent_name)
```

## Error Handling

### Robust LLM Usage

```python
def safe_llm_reasoning(llm: RealLLM, context: str, question: str) -> Dict[str, Any]:
    """Safe LLM reasoning with comprehensive error handling."""
    try:
        result = llm.reasoning(context, question, "general")
        
        # Validate result
        if not result.get('reasoning'):
            raise ValueError("Invalid LLM response")
        
        return result
        
    except Exception as e:
        # Log error and use fallback
        print(f"LLM reasoning failed: {e}")
        
        # Use simple fallback
        from cf.llm.simple_llm import SimpleLLM
        fallback_llm = SimpleLLM()
        return fallback_llm.reasoning(context, question, "general")
```

### Rate Limiting and Retries

```python
import time
from typing import Optional

class RateLimitedLLM:
    def __init__(self, base_llm: RealLLM, rate_limit: float = 1.0):
        self.llm = base_llm
        self.rate_limit = rate_limit
        self.last_call = 0
    
    def reasoning(self, context: str, question: str, agent_type: str, retries: int = 3) -> Dict[str, Any]:
        """Rate-limited reasoning with retries."""
        for attempt in range(retries):
            try:
                # Enforce rate limit
                time_since_last = time.time() - self.last_call
                if time_since_last < self.rate_limit:
                    time.sleep(self.rate_limit - time_since_last)
                
                result = self.llm.reasoning(context, question, agent_type)
                self.last_call = time.time()
                
                return result
                
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                time.sleep(2 ** attempt)  # Exponential backoff
```

## Performance Optimization

### Caching Integration

```python
from cf.core.react_agent import ReActCache

class CachedLLM:
    def __init__(self, base_llm: RealLLM, cache_dir: str = "./llm_cache"):
        self.llm = base_llm
        self.cache = ReActCache(max_size=1000, cache_dir=cache_dir, ttl=3600)
    
    def reasoning(self, context: str, question: str, agent_type: str) -> Dict[str, Any]:
        """Cached LLM reasoning."""
        # Create cache key
        cache_key = f"reasoning_{hash(context + question + agent_type)}"
        
        # Check cache
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Get fresh result
        result = self.llm.reasoning(context, question, agent_type)
        
        # Cache result
        self.cache.set(cache_key, result)
        
        return result
```

### Batch Processing

```python
def batch_llm_analysis(llm: RealLLM, analysis_requests: List[Dict]) -> List[Dict]:
    """Process multiple LLM requests efficiently."""
    results = []
    
    for request in analysis_requests:
        try:
            if request['type'] == 'reasoning':
                result = llm.reasoning(
                    request['context'],
                    request['question'],
                    request['agent_type']
                )
            elif request['type'] == 'summary':
                result = llm.summarize(
                    request['content'],
                    request['summary_type'],
                    request['focus']
                )
            
            results.append({
                'request_id': request.get('id'),
                'result': result,
                'success': True
            })
            
        except Exception as e:
            results.append({
                'request_id': request.get('id'),
                'error': str(e),
                'success': False
            })
    
    return results
```