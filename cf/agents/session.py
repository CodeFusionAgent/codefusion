"""
Session Management - Interactive Sessions and Context Management

Provides Claude Code-style interactive features:
- InteractiveSession: Maintains conversation context, handles streaming, user corrections
- ContextManager: Summarizes context when it gets too long

These enable conversational, iterative interactions similar to Claude Code.
"""

import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Iterator, Callable
from cf.utils.logger import get_logger
from cf.utils.console import StreamingResponse, StatusLine, print_response

logger = get_logger(__name__)


# ============================================================================
# Context Manager - Handles long conversation summarization
# ============================================================================

@dataclass
class ContextSummary:
    """Summary of conversation context"""
    summary_text: str
    files_mentioned: List[str]
    key_insights: List[str]
    original_turn_count: int
    timestamp: float = field(default_factory=time.time)


class ContextManager:
    """
    Manages conversation context with automatic summarization.

    When context grows too long, older turns are summarized to stay within
    token limits while preserving key information.

    Features:
    - Token estimation for context length
    - Automatic summarization of old context
    - Preservation of recent detail
    - File reference tracking
    """

    # Constants for context management
    MAX_CONTEXT_TOKENS = 100000  # Approximate token limit
    SUMMARIZE_THRESHOLD = 80000  # Start summarizing when we hit this
    KEEP_RECENT_TURNS = 5  # Always keep last N turns in full detail

    def __init__(self, llm_callback: Optional[Callable] = None):
        """
        Initialize ContextManager.

        Args:
            llm_callback: Function to call LLM for summarization (prompt, system_prompt) -> str
        """
        self.llm_callback = llm_callback
        self.summaries: List[ContextSummary] = []

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars per token average)"""
        return len(text) // 4

    def estimate_history_tokens(self, history: List[Dict]) -> int:
        """Estimate total tokens in conversation history"""
        total = 0
        for turn in history:
            total += self.estimate_tokens(turn.get('question', ''))
            total += self.estimate_tokens(turn.get('answer', ''))
            # Add tokens for context/summaries
            for summary in turn.get('file_summaries', {}).values():
                if isinstance(summary, str):
                    total += self.estimate_tokens(summary)
        return total

    def needs_summarization(self, history: List[Dict]) -> bool:
        """Check if context needs summarization"""
        return self.estimate_history_tokens(history) > self.SUMMARIZE_THRESHOLD

    def summarize_if_needed(self, history: List[Dict]) -> List[Dict]:
        """
        Summarize old context if needed, keeping recent turns detailed.

        Args:
            history: Full conversation history

        Returns:
            Optimized history with old turns summarized
        """
        if not self.needs_summarization(history) or len(history) <= self.KEEP_RECENT_TURNS:
            return history

        # Split into old and recent
        old_turns = history[:-self.KEEP_RECENT_TURNS]
        recent_turns = history[-self.KEEP_RECENT_TURNS:]

        # Summarize old turns
        summary = self._summarize_turns(old_turns)

        if summary:
            # Store summary
            self.summaries.append(summary)

            # Create a synthetic "summary" turn
            summary_turn = {
                'question': '[Previous conversation summary]',
                'answer': summary.summary_text,
                'is_summary': True,
                'files_mentioned': summary.files_mentioned,
                'original_turn_count': summary.original_turn_count
            }

            return [summary_turn] + recent_turns

        return history

    def _summarize_turns(self, turns: List[Dict]) -> Optional[ContextSummary]:
        """
        Use LLM to summarize old conversation turns.

        Args:
            turns: Old turns to summarize

        Returns:
            ContextSummary or None if summarization fails
        """
        if not self.llm_callback or not turns:
            return None

        # Build text to summarize
        text_parts = []
        files_mentioned = set()

        for turn in turns:
            text_parts.append(f"Q: {turn.get('question', '')}")
            text_parts.append(f"A: {turn.get('answer', '')[:500]}...")  # Truncate answers

            # Track files
            for file_path in turn.get('file_summaries', {}).keys():
                files_mentioned.add(file_path)

        full_text = "\n\n".join(text_parts)

        try:
            prompt = f"""Summarize this conversation history concisely, preserving:
1. Key questions asked
2. Important findings about the codebase
3. Files and components discussed
4. Any unresolved questions

Conversation:
{full_text}

Provide a concise summary (max 500 words) that captures the essential context."""

            response = self.llm_callback(
                prompt,
                system_prompt="You summarize conversations concisely while preserving key technical details."
            )

            # Extract key insights from summary
            key_insights = []
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('- ') or line.startswith('* '):
                    key_insights.append(line[2:])

            return ContextSummary(
                summary_text=response,
                files_mentioned=list(files_mentioned),
                key_insights=key_insights[:10],  # Limit insights
                original_turn_count=len(turns)
            )

        except Exception as e:
            logger.warning(f"Context summarization failed: {e}")
            return None

    def get_context_for_prompt(self, history: List[Dict], max_tokens: int = 50000) -> str:
        """
        Build context string for LLM prompt from history.

        Args:
            history: Conversation history
            max_tokens: Maximum tokens to include

        Returns:
            Formatted context string
        """
        optimized = self.summarize_if_needed(history)

        parts = []
        token_count = 0

        for turn in reversed(optimized):  # Start from most recent
            turn_text = ""

            if turn.get('is_summary'):
                turn_text = f"[Previous context summary]\n{turn['answer']}\n"
            else:
                turn_text = f"User: {turn.get('question', '')}\nAssistant: {turn.get('answer', '')}\n"

            turn_tokens = self.estimate_tokens(turn_text)
            if token_count + turn_tokens > max_tokens:
                break

            parts.insert(0, turn_text)
            token_count += turn_tokens

        return "\n---\n".join(parts)


# ============================================================================
# Interactive Session - Claude Code-style conversation management
# ============================================================================

@dataclass
class SessionMessage:
    """A single message in the session"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamChunk:
    """A chunk of streamed response"""
    content: str
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class InteractiveSession:
    """
    Manages an interactive conversation session with the codebase.

    Features:
    - Conversation history tracking
    - Streaming response support
    - User correction handling
    - Context management with auto-summarization
    - File context tracking

    Usage:
        session = InteractiveSession(repo_path, config)

        # Ask a question
        for chunk in session.ask_streaming("How does auth work?"):
            print(chunk.content, end='')

        # Refine with correction
        session.refine("Actually, focus on JWT tokens specifically")

        # Continue conversation
        for chunk in session.ask_streaming("What about refresh tokens?"):
            print(chunk.content, end='')
    """

    def __init__(
        self,
        repo_path: str,
        config: Dict[str, Any],
        llm_callback: Optional[Callable] = None,
        supervisor: Optional[Any] = None  # SupervisorAgent reference
    ):
        """
        Initialize an interactive session.

        Args:
            repo_path: Path to repository
            config: Configuration dictionary
            llm_callback: Function for LLM calls
            supervisor: Reference to SupervisorAgent for analysis
        """
        self.repo_path = repo_path
        self.config = config
        self.llm_callback = llm_callback
        self.supervisor = supervisor

        # Session state
        self.session_id = f"session_{int(time.time())}"
        self.history: List[Dict] = []
        self.messages: List[SessionMessage] = []
        self.file_context: Dict[str, Any] = {}  # Cached file summaries
        self.kb_context: Dict[str, Any] = {}  # KB query results

        # Context management
        self.context_manager = ContextManager(llm_callback)

        # Session metadata
        self.created_at = time.time()
        self.last_activity = time.time()
        self.total_questions = 0

        logger.info(f"Created interactive session: {self.session_id}")

    def ask(self, question: str, mode: str = "auto") -> str:
        """
        Ask a question and get a complete response.

        Args:
            question: User's question
            mode: Analysis mode ('fast', 'comprehensive', 'auto')

        Returns:
            Complete response string
        """
        # Collect all chunks
        response_parts = []
        for chunk in self.ask_streaming(question, mode):
            response_parts.append(chunk.content)

        return "".join(response_parts)

    def ask_streaming(self, question: str, mode: str = "auto") -> Iterator[StreamChunk]:
        """
        Ask a question and stream the response.

        Args:
            question: User's question
            mode: Analysis mode

        Yields:
            StreamChunk objects as response is generated
        """
        self.last_activity = time.time()
        self.total_questions += 1

        # Add user message
        self.messages.append(SessionMessage(role='user', content=question))

        # Build context from history
        context = self._build_conversation_context()

        try:
            # Use supervisor for analysis if available
            if self.supervisor:
                yield StreamChunk(content="Analyzing codebase...\n", metadata={'phase': 'discovery'})

                # Get full response from supervisor
                result = self.supervisor.analyze(
                    question=question,
                    mode=mode,
                    context=context
                )

                answer = result.get('answer', result.get('narrative', ''))

                # Stream the response in chunks (simulated)
                chunk_size = 100
                for i in range(0, len(answer), chunk_size):
                    chunk = answer[i:i + chunk_size]
                    yield StreamChunk(
                        content=chunk,
                        is_final=(i + chunk_size >= len(answer)),
                        metadata={'phase': 'response'}
                    )

                # Store in history
                self._add_to_history(question, answer, result)

            else:
                # Fallback: Just echo back
                yield StreamChunk(
                    content=f"[No supervisor configured] Question: {question}",
                    is_final=True
                )

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield StreamChunk(
                content=f"\n\nError: {str(e)}",
                is_final=True,
                metadata={'error': True}
            )

    def ask_rich(self, question: str, mode: str = "auto") -> str:
        """
        Ask a question with Rich-formatted streaming output.

        Args:
            question: User's question
            mode: Analysis mode

        Returns:
            Complete response string
        """
        response_content = ""

        with StatusLine("Analyzing codebase...") as status:
            for chunk in self.ask_streaming(question, mode):
                if chunk.metadata.get('phase') == 'discovery':
                    status.update("Discovering relevant files...")
                elif chunk.metadata.get('phase') == 'response':
                    response_content += chunk.content

        # Display final response with Rich formatting
        if response_content:
            print_response(response_content, title="Answer")

        return response_content

    def refine(self, correction: str) -> str:
        """
        Refine the last response based on user correction.

        Args:
            correction: User's correction or clarification

        Returns:
            Refined response
        """
        if not self.history:
            return "No previous question to refine."

        last_turn = self.history[-1]
        original_question = last_turn.get('question', '')
        original_answer = last_turn.get('answer', '')

        # Build refined question
        refined_question = f"""Based on my previous question "{original_question}",
I'd like to refine: {correction}

Previous answer context:
{original_answer[:500]}...

Please provide a refined answer."""

        return self.ask(refined_question, mode="fast")

    def _build_conversation_context(self) -> Dict[str, Any]:
        """Build context from conversation history"""
        return {
            'history_summary': self.context_manager.get_context_for_prompt(self.history),
            'files_discussed': list(self.file_context.keys()),
            'kb_context': self.kb_context,
            'turn_count': len(self.history)
        }

    def _add_to_history(self, question: str, answer: str, result: Dict):
        """Add a Q&A turn to history"""
        turn = {
            'question': question,
            'answer': answer,
            'timestamp': time.time(),
            'file_summaries': result.get('file_summaries', {}),
            'files_analyzed': result.get('files_analyzed', [])
        }

        self.history.append(turn)
        self.messages.append(SessionMessage(role='assistant', content=answer))

        # Update file context
        for file_path, summary in result.get('file_summaries', {}).items():
            self.file_context[file_path] = summary

    def get_history(self) -> List[Dict]:
        """Get conversation history"""
        return self.history.copy()

    def clear_history(self):
        """Clear conversation history"""
        self.history.clear()
        self.messages.clear()
        self.file_context.clear()
        self.kb_context.clear()
        logger.info(f"Cleared history for session {self.session_id}")

    def export_session(self) -> Dict[str, Any]:
        """Export session state for persistence"""
        return {
            'session_id': self.session_id,
            'repo_path': self.repo_path,
            'created_at': self.created_at,
            'last_activity': self.last_activity,
            'total_questions': self.total_questions,
            'history': self.history,
            'file_context': {k: str(v)[:500] for k, v in self.file_context.items()},
            'context_summaries': [
                {
                    'summary': s.summary_text,
                    'files': s.files_mentioned,
                    'original_turns': s.original_turn_count
                }
                for s in self.context_manager.summaries
            ]
        }

    @classmethod
    def from_export(cls, data: Dict[str, Any], config: Dict,
                    llm_callback=None, supervisor=None) -> 'InteractiveSession':
        """Restore session from exported state"""
        session = cls(
            repo_path=data['repo_path'],
            config=config,
            llm_callback=llm_callback,
            supervisor=supervisor
        )
        session.session_id = data['session_id']
        session.created_at = data['created_at']
        session.last_activity = data['last_activity']
        session.total_questions = data['total_questions']
        session.history = data['history']
        session.file_context = data.get('file_context', {})

        return session
