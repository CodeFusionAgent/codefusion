"""LLM Model integration for CodeFusion using LiteLLM."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import litellm

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    litellm = None


@dataclass
class LlmMessage:
    """Represents a message in LLM conversation."""

    role: str  # "system", "user", "assistant"
    content: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class LlmResponse:
    """Represents an LLM response."""

    content: str
    model: str
    usage: Dict[str, Any]
    timestamp: datetime
    request_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "usage": self.usage,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
        }


@dataclass
class LlmTrace:
    """Represents a trace of LLM interaction."""

    request_id: str
    messages: List[LlmMessage]
    response: Optional[LlmResponse]
    start_time: datetime
    end_time: Optional[datetime]
    error: Optional[str]
    metadata: Dict[str, Any]

    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "messages": [asdict(msg) for msg in self.messages],
            "response": self.response.to_dict() if self.response else None,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms(),
            "error": self.error,
            "metadata": self.metadata,
        }


class LlmTracer:
    """Tracer for monitoring LLM interactions."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self.traces: Dict[str, LlmTrace] = {}
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    def start_trace(
        self, messages: List[LlmMessage], metadata: Dict[str, Any] = None
    ) -> str:
        """Start tracing an LLM request."""
        request_id = str(uuid.uuid4())
        trace = LlmTrace(
            request_id=request_id,
            messages=messages,
            response=None,
            start_time=datetime.now(),
            end_time=None,
            error=None,
            metadata=metadata or {},
        )
        self.traces[request_id] = trace
        self.stats["total_requests"] += 1
        return request_id

    def end_trace(
        self,
        request_id: str,
        response: Optional[LlmResponse] = None,
        error: Optional[str] = None,
    ):
        """End tracing an LLM request."""
        if request_id not in self.traces:
            return

        trace = self.traces[request_id]
        trace.end_time = datetime.now()
        trace.response = response
        trace.error = error

        if error:
            self.stats["failed_requests"] += 1
        else:
            self.stats["successful_requests"] += 1
            if response and response.usage:
                self.stats["total_tokens"] += response.usage.get("total_tokens", 0)

    def get_trace(self, request_id: str) -> Optional[LlmTrace]:
        """Get a specific trace."""
        return self.traces.get(request_id)

    def get_recent_traces(self, limit: int = 10) -> List[LlmTrace]:
        """Get recent traces."""
        sorted_traces = sorted(
            self.traces.values(), key=lambda t: t.start_time, reverse=True
        )
        return sorted_traces[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get tracing statistics."""
        return self.stats.copy()

    def save_traces(self) -> None:
        """Save traces to storage if configured."""
        if not self.storage_path:
            return

        import json
        from pathlib import Path

        storage_file = Path(self.storage_path) / "llm_traces.json"
        storage_file.parent.mkdir(parents=True, exist_ok=True)

        traces_data = [trace.to_dict() for trace in self.traces.values()]

        with open(storage_file, "w") as f:
            json.dump({"traces": traces_data, "stats": self.stats}, f, indent=2)


class LlmModel(ABC):
    """Abstract base class for LLM models."""

    def __init__(self, model_name: str, tracer: Optional[LlmTracer] = None):
        self.model_name = model_name
        self.tracer = tracer

    @abstractmethod
    def generate(self, messages: List[LlmMessage], **kwargs) -> LlmResponse:
        """Generate a response from the LLM."""
        pass

    def ask_question(
        self, question: str, context: Optional[str] = None, **kwargs
    ) -> str:
        """Ask a simple question to the LLM."""
        messages = []

        if context:
            messages.append(
                LlmMessage(
                    role="system",
                    content=f"Use the following context to answer questions:\n\n{context}",
                )
            )

        messages.append(LlmMessage(role="user", content=question))

        response = self.generate(messages, **kwargs)
        return response.content


class LiteLlmModel(LlmModel):
    """LiteLLM-based model implementation."""

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        tracer: Optional[LlmTracer] = None,
    ):
        super().__init__(model_name, tracer)

        if not LITELLM_AVAILABLE:
            raise ImportError("LiteLLM is not installed. Run: pip install litellm")

        self.api_key = api_key
        self.base_url = base_url

        # Configure LiteLLM
        if api_key:
            litellm.api_key = api_key
        if base_url:
            litellm.api_base = base_url

    def generate(self, messages: List[LlmMessage], **kwargs) -> LlmResponse:
        """Generate a response using LiteLLM."""
        # Start tracing
        request_id = None
        if self.tracer:
            request_id = self.tracer.start_trace(messages, {"model": self.model_name})

        try:
            # Convert messages to LiteLLM format
            llm_messages = []
            for msg in messages:
                llm_messages.append({"role": msg.role, "content": msg.content})

            # Set default parameters
            params = {
                "model": self.model_name,
                "messages": llm_messages,
                "temperature": kwargs.get("temperature", 0.1),
                "max_tokens": kwargs.get("max_tokens", 1000),
            }

            # Make the API call
            response = litellm.completion(**params)

            # Extract response data
            content = response.choices[0].message.content
            usage = (
                response.usage._asdict()
                if hasattr(response.usage, "_asdict")
                else dict(response.usage)
            )

            llm_response = LlmResponse(
                content=content,
                model=self.model_name,
                usage=usage,
                timestamp=datetime.now(),
                request_id=request_id or str(uuid.uuid4()),
            )

            # End tracing
            if self.tracer and request_id:
                self.tracer.end_trace(request_id, llm_response)

            return llm_response

        except Exception as e:
            # End tracing with error
            if self.tracer and request_id:
                self.tracer.end_trace(request_id, error=str(e))
            raise Exception(f"LLM generation failed: {str(e)}")


class MockLlmModel(LlmModel):
    """Mock LLM model for testing without API calls."""

    def __init__(
        self, model_name: str = "mock-model", tracer: Optional[LlmTracer] = None
    ):
        super().__init__(model_name, tracer)

    def generate(self, messages: List[LlmMessage], **kwargs) -> LlmResponse:
        """Generate a mock response."""
        # Start tracing
        request_id = None
        if self.tracer:
            request_id = self.tracer.start_trace(messages, {"model": self.model_name})

        # Create mock response based on the last user message
        user_messages = [msg for msg in messages if msg.role == "user"]
        last_message = user_messages[-1].content if user_messages else "No user message"

        mock_content = f"Mock response to: {last_message[:100]}..."

        llm_response = LlmResponse(
            content=mock_content,
            model=self.model_name,
            usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
            timestamp=datetime.now(),
            request_id=request_id or str(uuid.uuid4()),
        )

        # End tracing
        if self.tracer and request_id:
            self.tracer.end_trace(request_id, llm_response)

        return llm_response


def create_llm_model(model_type: str, model_name: str, **kwargs) -> LlmModel:
    """Factory function to create LLM model instances."""
    tracer = kwargs.get("tracer")

    if model_type == "litellm":
        return LiteLlmModel(
            model_name=model_name,
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            tracer=tracer,
        )
    elif model_type == "mock":
        return MockLlmModel(model_name=model_name, tracer=tracer)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")


class CodeAnalysisLlm:
    """High-level LLM interface for code analysis tasks."""

    def __init__(self, llm_model: LlmModel):
        self.llm = llm_model

    def explain_code(self, code: str, language: str = "unknown") -> str:
        """Get an explanation of code functionality."""
        prompt = f"""Explain what this {language} code does:

```{language}
{code}
```

Provide a clear, concise explanation of:
1. What the code does
2. Key functions or classes
3. Important patterns or algorithms used"""

        return self.llm.ask_question(prompt)

    def analyze_architecture(self, files_summary: Dict[str, str]) -> str:
        """Analyze overall architecture from file summaries."""
        context = "File summaries:\n"
        for file_path, summary in files_summary.items():
            context += f"\n{file_path}: {summary}"

        prompt = """Based on the file summaries provided, analyze the overall architecture:

1. What is the main purpose of this codebase?
2. What are the key components/modules?
3. How do the components interact?
4. What architectural patterns are used?
5. What technology stack is being used?"""

        return self.llm.ask_question(prompt, context)

    def suggest_improvements(self, code: str, language: str = "unknown") -> str:
        """Suggest improvements for code quality."""
        prompt = f"""Review this {language} code and suggest improvements:

```{language}
{code}
```

Focus on:
1. Code quality and readability
2. Performance optimizations
3. Best practices
4. Potential bugs or issues"""

        return self.llm.ask_question(prompt)

    def answer_code_question(self, question: str, code_context: str) -> str:
        """Answer a specific question about code."""
        return self.llm.ask_question(question, code_context)
