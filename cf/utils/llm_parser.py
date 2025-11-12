"""
LLM Response Parser Utility

Centralized parsing and validation of LLM JSON responses.
Eliminates duplicate JSON extraction logic across the codebase.
"""

import json
from typing import Dict, Any, Optional, Union


class LLMResponseParser:
    """
    Utility class for parsing LLM responses.

    Handles common patterns:
    - JSON extraction from markdown code blocks
    - Fallback parsing strategies
    - Validation and error handling
    """

    @staticmethod
    def extract_json(content: str, fallback: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from LLM response.

        Handles multiple formats:
        - Plain JSON: {"key": "value"}
        - Markdown code block: ```json\n{...}\n```
        - Markdown without language: ```\n{...}\n```
        - JSON embedded in text

        Args:
            content: LLM response content
            fallback: Default value if parsing fails

        Returns:
            Parsed JSON dict or fallback value

        Example:
            >>> parser = LLMResponseParser()
            >>> content = "Here's the analysis:\n```json\n{\"type\": \"search\"}\n```"
            >>> result = parser.extract_json(content)
            >>> result
            {'type': 'search'}
        """
        if not content or not isinstance(content, str):
            return fallback

        content = content.strip()

        # Strategy 1: Direct JSON (most common)
        if content.startswith('{'):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

        # Strategy 2: Extract from markdown code blocks
        # Pattern: ```json\n{...}\n``` or ```\n{...}\n```
        if '```' in content:
            # Find code block
            start_markers = ['```json\n', '```\n', '```']
            end_marker = '\n```'

            for start_marker in start_markers:
                if start_marker in content:
                    start_idx = content.find(start_marker) + len(start_marker)
                    end_idx = content.find(end_marker, start_idx)

                    if end_idx != -1:
                        json_str = content[start_idx:end_idx].strip()
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            continue

        # Strategy 3: Find first {...} or [...]
        start = content.find('{')
        if start == -1:
            start = content.find('[')

        if start >= 0:
            # Find matching closing bracket
            if content[start] == '{':
                end = content.rfind('}') + 1
            else:
                end = content.rfind(']') + 1

            if end > start:
                json_str = content[start:end]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        # All strategies failed
        return fallback

    @staticmethod
    def extract_json_with_validation(
        content: str,
        required_keys: list = None,
        fallback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract and validate JSON from LLM response.

        Args:
            content: LLM response content
            required_keys: List of required keys in JSON
            fallback: Default value if parsing fails or validation fails

        Returns:
            Validated JSON dict or fallback value

        Example:
            >>> result = LLMResponseParser.extract_json_with_validation(
            ...     '{"type": "search", "term": "auth"}',
            ...     required_keys=['type'],
            ...     fallback={'type': 'unknown'}
            ... )
        """
        result = LLMResponseParser.extract_json(content, fallback)

        if result is None:
            return fallback if fallback else {}

        # Validate required keys
        if required_keys:
            missing_keys = [key for key in required_keys if key not in result]
            if missing_keys:
                print(f"⚠️ Missing required keys in LLM response: {missing_keys}")
                return fallback if fallback else {}

        return result

    @staticmethod
    def safe_parse_llm_response(
        llm_response: Dict[str, Any],
        required_keys: list = None,
        fallback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Safely parse LLM response dictionary.

        Handles both the LLM client response format and direct content.

        Args:
            llm_response: LLM response dict with 'success' and 'content' keys
            required_keys: List of required keys in parsed JSON
            fallback: Default value if parsing fails

        Returns:
            Parsed JSON dict or fallback value

        Example:
            >>> llm_response = {
            ...     'success': True,
            ...     'content': '{"type": "search", "term": "auth"}'
            ... }
            >>> result = LLMResponseParser.safe_parse_llm_response(
            ...     llm_response,
            ...     required_keys=['type'],
            ...     fallback={'type': 'unknown'}
            ... )
        """
        if not llm_response or not llm_response.get('success'):
            return fallback if fallback else {}

        content = llm_response.get('content', '')
        if not content:
            return fallback if fallback else {}

        return LLMResponseParser.extract_json_with_validation(
            content,
            required_keys=required_keys,
            fallback=fallback
        )

    @staticmethod
    def extract_list(content: str, fallback: Optional[list] = None) -> list:
        """
        Extract list from LLM response.

        Args:
            content: LLM response content
            fallback: Default value if parsing fails

        Returns:
            Parsed list or fallback value

        Example:
            >>> content = '["item1", "item2", "item3"]'
            >>> result = LLMResponseParser.extract_list(content)
            >>> result
            ['item1', 'item2', 'item3']
        """
        if not content or not isinstance(content, str):
            return fallback if fallback else []

        # Try direct JSON parsing
        content = content.strip()
        if content.startswith('['):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

        # Try extracting from {...} if it contains a list field
        json_obj = LLMResponseParser.extract_json(content)
        if json_obj:
            # Check for common list field names
            for key in ['items', 'list', 'results', 'data', 'values']:
                if key in json_obj and isinstance(json_obj[key], list):
                    return json_obj[key]

        return fallback if fallback else []
