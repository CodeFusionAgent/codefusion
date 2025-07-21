"""Tools package for CodeFusion advanced exploration."""

from cf.tools.narrative_utils import extract_key_entity, display_life_of_x_narrative, display_comparison_analysis, should_consolidate_multi_agent_results, generate_llm_driven_narrative, detect_response_format
from cf.tools.web_search import WebSearchTool, web_search_general, web_search_documentation, web_search_code_examples, web_search_comparison

__all__ = [
    "extract_key_entity",
    "display_life_of_x_narrative",
    "display_comparison_analysis",
    "should_consolidate_multi_agent_results",
    "generate_llm_driven_narrative",
    "detect_response_format",
    "WebSearchTool",
    "web_search_general", 
    "web_search_documentation",
    "web_search_code_examples",
    "web_search_comparison"
]