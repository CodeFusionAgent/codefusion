"""
Tool Name Resolver for CodeFusion

Handles dynamic tool name resolution with fallback strategies.
Extracted from ToolRegistry for better testability and maintainability.
"""

from typing import Dict, Callable, List, Optional


class ToolNameResolver:
    """
    Resolves tool names using multiple fallback strategies.

    Handles:
    - Exact name matches
    - Suffix matches (e.g., 'find_files' → 'kb_find_files')
    - Substring matches
    - Special case handling for common patterns
    """

    def resolve(self, tool_name: str, available_tools: Dict[str, Callable]) -> Optional[str]:
        """
        Resolve tool name to actual registered name.

        Args:
            tool_name: Tool name to resolve
            available_tools: Dictionary of available tools

        Returns:
            Resolved tool name if found, None otherwise

        Resolution Strategy:
        1. Exact match (fastest path)
        2. Suffix match (handles agent-prefixed tools)
        3. Special case matching (e.g., KB discovery suffix)
        4. Substring match (fallback)
        """
        # Fast path: exact match
        if tool_name in available_tools:
            return tool_name

        # Try resolution strategies
        try:
            keys = list(available_tools.keys())
            candidates = self._find_candidates(tool_name, keys)

            # Return if we found exactly one match
            if len(candidates) == 1:
                return candidates[0]

            # Multiple candidates or no candidates - return None
            return None

        except Exception:
            # Fail gracefully on any exception
            return None

    def _find_candidates(self, tool_name: str, available_keys: List[str]) -> List[str]:
        """
        Find candidate tool names using multiple strategies.

        Args:
            tool_name: Tool name to search for
            available_keys: List of available tool names

        Returns:
            List of candidate matches
        """
        candidates = []

        # Strategy 1: Exact suffix match (common pattern for agent-prefixed tools)
        # E.g., 'semantic_search' → 'structural_kb_semantic_search'
        candidates = [n for n in available_keys if n.endswith(tool_name)]
        if candidates:
            return candidates

        # Strategy 2: Special case for common KB discovery tool suffix
        # Handles the pattern where multiple agents might have 'find_files_for_question'
        if tool_name.endswith('_find_files_for_question'):
            suffix = '_find_files_for_question'
            candidates = [n for n in available_keys if n.endswith(suffix)]
            if candidates:
                return candidates

        # Strategy 3: Substring match (fallback)
        # E.g., 'find_files' matches 'kb_find_files_for_question'
        candidates = [n for n in available_keys if tool_name in n]

        return candidates

    def get_resolution_error(self, tool_name: str, available_tools: Dict[str, Callable]) -> Dict:
        """
        Generate helpful error message for unresolved tool.

        Args:
            tool_name: Tool name that failed to resolve
            available_tools: Dictionary of available tools

        Returns:
            Error dictionary with helpful information
        """
        # Find similar tool names for suggestions
        similar_tools = self._find_similar_tools(tool_name, list(available_tools.keys()))

        error_msg = f'Tool "{tool_name}" not found'

        if similar_tools:
            error_msg += f'. Did you mean: {", ".join(similar_tools[:3])}?'

        return {
            'error': error_msg,
            'similar_tools': similar_tools[:5],
            'available_tools': list(available_tools.keys())
        }

    def _find_similar_tools(self, tool_name: str, available_keys: List[str]) -> List[str]:
        """
        Find tool names similar to the requested name.

        Uses simple substring matching for suggestions.

        Args:
            tool_name: Tool name to search for
            available_keys: List of available tool names

        Returns:
            List of similar tool names
        """
        # Split tool_name into words and find tools containing those words
        words = tool_name.replace('_', ' ').split()

        similar = []
        for key in available_keys:
            # Check if any word from tool_name is in the available key
            if any(word in key for word in words if len(word) > 2):
                similar.append(key)

        return sorted(similar)  # Sort for consistency
