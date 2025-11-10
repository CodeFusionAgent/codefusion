"""
LlmTask - Message-Based LLM Interface

Replaces raw string prompts with Message objects for:
- Conversation history tracking
- Multi-turn reasoning
- Better context management
"""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class MessageRole(Enum):
    """Message roles in conversation"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """
    A single message in a conversation.

    Replaces raw strings with structured data.
    """
    role: MessageRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, str]:
        """Convert to API format"""
        return {
            'role': self.role.value,
            'content': self.content
        }


@dataclass
class ConversationHistory:
    """
    Maintains conversation history for multi-turn interactions.

    Enables:
    - Context retention across calls
    - Multi-turn reasoning
    - Conversation replay
    """
    messages: List[Message] = field(default_factory=list)
    max_history: int = 10  # Limit history to prevent token overflow

    def add_message(self, role: MessageRole, content: str, metadata: Dict[str, Any] = None):
        """Add a message to history"""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)

        # Prune history if too long (keep system messages)
        if len(self.messages) > self.max_history:
            system_messages = [m for m in self.messages if m.role == MessageRole.SYSTEM]
            recent_messages = [m for m in self.messages if m.role != MessageRole.SYSTEM][-self.max_history:]
            self.messages = system_messages + recent_messages

    def get_messages(self) -> List[Dict[str, str]]:
        """Get messages in API format"""
        return [m.to_dict() for m in self.messages]

    def clear(self):
        """Clear conversation history"""
        self.messages = []

    def get_last_user_message(self) -> Optional[Message]:
        """Get the last user message"""
        for msg in reversed(self.messages):
            if msg.role == MessageRole.USER:
                return msg
        return None

    def get_last_assistant_message(self) -> Optional[Message]:
        """Get the last assistant message"""
        for msg in reversed(self.messages):
            if msg.role == MessageRole.ASSISTANT:
                return msg
        return None

    def count_tokens_estimate(self) -> int:
        """Estimate total tokens in history"""
        total_chars = sum(len(m.content) for m in self.messages)
        return total_chars // 4  # Rough approximation


class LlmTask:
    """
    Message-based LLM interface with conversation history.

    Replaces raw generate(prompt, system_prompt) with:
    - Structured Message objects
    - Automatic history management
    - Multi-turn support

    Example usage:
        task = LlmTask(llm_client)

        # Set context
        task.set_system_message("You are a code analysis assistant.")

        # Multi-turn conversation
        response1 = task.ask("What is this function doing?")
        response2 = task.ask("Can you explain line 5 in more detail?")
        # History is automatically maintained

        # Access history
        history = task.get_history()
    """

    def __init__(self, llm_client, max_history: int = 10):
        """
        Initialize LlmTask.

        Args:
            llm_client: LLMClient instance
            max_history: Maximum messages to keep in history
        """
        self.llm_client = llm_client
        self.history = ConversationHistory(max_history=max_history)
        self._system_message: Optional[Message] = None
        self._metrics = {
            'total_calls': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'total_time': 0.0
        }

    def set_system_message(self, content: str, metadata: Dict[str, Any] = None):
        """
        Set system message for conversation context.

        Args:
            content: System message content
            metadata: Optional metadata
        """
        self._system_message = Message(
            role=MessageRole.SYSTEM,
            content=content,
            metadata=metadata or {}
        )

    def ask(self, user_message: str, metadata: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Ask a question and get response (with history).

        Args:
            user_message: User's question/prompt
            metadata: Optional metadata for this message
            **kwargs: Additional arguments for LLM (temperature, max_tokens, etc.)

        Returns:
            Response dictionary with content, usage, etc.
        """
        # Build messages list
        messages = []

        # Add system message if set
        if self._system_message:
            messages.append(self._system_message.to_dict())

        # Add history
        messages.extend(self.history.get_messages())

        # Add current user message
        user_msg = Message(
            role=MessageRole.USER,
            content=user_message,
            metadata=metadata or {}
        )
        messages.append(user_msg.to_dict())

        # Call LLM with messages
        start_time = time.time()

        # Use the underlying client's _call_* methods directly with messages
        provider = self.llm_client.provider
        if provider == 'anthropic':
            response_data = self.llm_client._call_anthropic(
                messages,
                self.llm_client.model,
                self.llm_client.api_key,
                self.llm_client.api_url,
                **kwargs
            )
        elif provider == 'openai':
            response_data = self.llm_client._call_openai(
                messages,
                self.llm_client.model,
                self.llm_client.api_key,
                self.llm_client.api_url,
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        duration = time.time() - start_time

        # Update metrics
        self._metrics['total_calls'] += 1
        self._metrics['total_tokens'] += response_data['usage']['total_tokens']
        self._metrics['total_time'] += duration

        # Estimate cost (rough approximation)
        cost_estimate = self._estimate_cost(
            response_data['usage']['prompt_tokens'],
            response_data['usage']['completion_tokens'],
            provider
        )
        self._metrics['total_cost'] += cost_estimate

        # Add user message to history
        self.history.add_message(
            MessageRole.USER,
            user_message,
            metadata or {}
        )

        # Add assistant response to history
        self.history.add_message(
            MessageRole.ASSISTANT,
            response_data['content'],
            {'usage': response_data['usage'], 'duration': duration}
        )

        return {
            'success': True,
            'content': response_data['content'],
            'model': response_data['model'],
            'usage': response_data['usage'],
            'finish_reason': response_data['finish_reason'],
            'duration': duration,
            'cost_estimate': cost_estimate
        }

    def ask_fast(self, user_message: str, metadata: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Ask using fast model (for routine tasks).

        Args:
            user_message: User's question/prompt
            metadata: Optional metadata
            **kwargs: Additional LLM arguments

        Returns:
            Response dictionary
        """
        # Build messages
        messages = []

        if self._system_message:
            messages.append(self._system_message.to_dict())

        messages.extend(self.history.get_messages())

        user_msg = Message(
            role=MessageRole.USER,
            content=user_message,
            metadata=metadata or {}
        )
        messages.append(user_msg.to_dict())

        # Call fast model
        start_time = time.time()

        provider = self.llm_client.fast_provider
        if provider == 'anthropic':
            response_data = self.llm_client._call_anthropic(
                messages,
                self.llm_client.fast_model,
                self.llm_client.fast_model_api_key,
                self.llm_client.fast_api_url,
                **kwargs
            )
        elif provider == 'openai':
            response_data = self.llm_client._call_openai(
                messages,
                self.llm_client.fast_model,
                self.llm_client.fast_model_api_key,
                self.llm_client.fast_api_url,
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported fast provider: {provider}")

        duration = time.time() - start_time

        # Update metrics
        self._metrics['total_calls'] += 1
        self._metrics['total_tokens'] += response_data['usage']['total_tokens']
        self._metrics['total_time'] += duration

        cost_estimate = self._estimate_cost(
            response_data['usage']['prompt_tokens'],
            response_data['usage']['completion_tokens'],
            provider,
            is_fast=True
        )
        self._metrics['total_cost'] += cost_estimate

        # Add to history
        self.history.add_message(MessageRole.USER, user_message, metadata or {})
        self.history.add_message(
            MessageRole.ASSISTANT,
            response_data['content'],
            {'usage': response_data['usage'], 'duration': duration, 'fast_model': True}
        )

        return {
            'success': True,
            'content': response_data['content'],
            'model': response_data['model'],
            'usage': response_data['usage'],
            'finish_reason': response_data['finish_reason'],
            'duration': duration,
            'cost_estimate': cost_estimate
        }

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int,
                      provider: str, is_fast: bool = False) -> float:
        """
        Estimate cost of LLM call.

        Args:
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            provider: LLM provider
            is_fast: Whether fast model was used

        Returns:
            Estimated cost in dollars
        """
        # Rough cost estimates (per 1M tokens)
        costs = {
            'openai': {
                'prompt': 2.50 / 1_000_000,  # GPT-4o
                'completion': 10.00 / 1_000_000
            },
            'openai_fast': {
                'prompt': 0.15 / 1_000_000,  # GPT-4o-mini
                'completion': 0.60 / 1_000_000
            },
            'anthropic': {
                'prompt': 3.00 / 1_000_000,  # Claude Sonnet
                'completion': 15.00 / 1_000_000
            },
            'anthropic_fast': {
                'prompt': 0.25 / 1_000_000,  # Claude Haiku
                'completion': 1.25 / 1_000_000
            }
        }

        key = f"{provider}_fast" if is_fast else provider
        if key not in costs:
            return 0.0

        cost_config = costs[key]
        return (prompt_tokens * cost_config['prompt'] +
                completion_tokens * cost_config['completion'])

    def get_history(self) -> List[Message]:
        """Get conversation history"""
        return self.history.messages.copy()

    def clear_history(self):
        """Clear conversation history"""
        self.history.clear()

    def reset(self):
        """Reset task (clear history and metrics)"""
        self.history.clear()
        self._metrics = {
            'total_calls': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'total_time': 0.0
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get task metrics"""
        return {
            **self._metrics,
            'messages_in_history': len(self.history.messages),
            'estimated_history_tokens': self.history.count_tokens_estimate()
        }

    def replay_conversation(self) -> List[Dict[str, Any]]:
        """
        Get conversation in readable format for debugging.

        Returns:
            List of message dictionaries
        """
        return [
            {
                'role': msg.role.value,
                'content': msg.content,
                'timestamp': msg.timestamp,
                'metadata': msg.metadata
            }
            for msg in self.history.messages
        ]
