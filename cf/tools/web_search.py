"""
Web Search Tool for CodeFusion

Provides web search capabilities to enhance code analysis with external documentation,
tutorials, and examples.
"""

import json
import re
import requests
from typing import Dict, List, Any, Optional
from urllib.parse import quote_plus
import logging

from cf.utils.logging_utils import tool_log, error_log


class WebSearchTool:
    """Web search tool for gathering external information."""
    
    def __init__(self, search_engine: str = "duckduckgo", max_results: int = 5):
        self.search_engine = search_engine
        self.max_results = max_results
        self.logger = logging.getLogger(__name__)
    
    def search(self, query: str, filter_keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Search the web for information related to the query.
        
        Args:
            query: Search query
            filter_keywords: Keywords to filter results (e.g., ['docs', 'tutorial', 'example'])
            
        Returns:
            Search results with summaries
        """
        tool_log(f"🌐 [WebSearch] Searching for: {query}")
        
        try:
            if self.search_engine == "duckduckgo":
                results = self._search_duckduckgo(query)
            else:
                results = self._search_fallback(query)
            
            # Filter and enhance results
            filtered_results = self._filter_and_enhance_results(results, filter_keywords)
            
            tool_log(f"✅ [WebSearch] Found {len(filtered_results)} relevant results")
            
            return {
                "success": True,
                "query": query,
                "results": filtered_results,
                "summary": self._generate_search_summary(filtered_results, query)
            }
            
        except Exception as e:
            error_log(f"❌ [WebSearch] Search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "summary": f"Web search failed for query: {query}"
            }
    
    def _search_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo with multiple generic strategies."""
        all_results = []
        
        # Strategy 1: Try DuckDuckGo Instant Answer API with query variations
        try:
            instant_results = self._duckduckgo_instant_search(query)
            all_results.extend(instant_results)
        except Exception as e:
            tool_log(f"⚠️  DuckDuckGo Instant API failed: {e}")
        
        # Strategy 2: If no results, try HTML search with generic terms
        if not all_results:
            try:
                html_results = self._duckduckgo_html_search(query)
                all_results.extend(html_results)
            except Exception as e:
                tool_log(f"⚠️  DuckDuckGo HTML search failed: {e}")
        
        return all_results[:self.max_results] if all_results else self._search_fallback(query)
    
    def _duckduckgo_instant_search(self, query: str) -> List[Dict[str, Any]]:
        """Use DuckDuckGo Instant Answer API with generic query variations."""
        all_results = []
        
        # Generic query variations that work for any technology
        query_variations = [
            query,
            f"{query} documentation",
            f"{query} tutorial guide",
            f"{query} official docs"
        ]
        
        url = "https://api.duckduckgo.com/"
        
        for q in query_variations[:2]:  # Try first 2 variations
            params = {
                "q": q,
                "format": "json",
                "pretty": 1,
                "no_redirect": 1,
                "skip_disambig": 1
            }
            
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                query_results = self._parse_duckduckgo_results(data, q)
                all_results.extend(query_results)
                
                # If we got good results, stop trying variations
                if len(query_results) >= 2:
                    break
                    
            except Exception as e:
                tool_log(f"❌ Query variation '{q}' failed: {e}")
                continue
        
        return all_results
    
    def _duckduckgo_html_search(self, query: str) -> List[Dict[str, Any]]:
        """Generic HTML search fallback."""
        url = "https://html.duckduckgo.com/html/"
        params = {"q": f"{query} documentation"}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; CodeFusion/1.0)'
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Generic fallback result
            return [{
                "title": f"Search Results for: {query}",
                "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}+documentation",
                "snippet": f"Documentation and tutorials for {query}",
                "source": "DuckDuckGo",
                "type": "search_results"
            }]
        except:
            return []
    
    def _parse_duckduckgo_results(self, data: dict, query: str) -> List[Dict[str, Any]]:
        """Parse DuckDuckGo API response into structured results."""
        results = []
        
        # Get main abstract if available
        if data.get("Abstract"):
            results.append({
                "title": data.get("AbstractText", "Main Result"),
                "url": data.get("AbstractURL", ""),
                "snippet": data.get("Abstract", ""),
                "source": data.get("AbstractSource", "DuckDuckGo"),
                "type": "abstract"
            })
        
        # Get related topics
        for topic in data.get("RelatedTopics", [])[:3]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", "")[:50],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                    "source": "DuckDuckGo Related",
                    "type": "related"
                })
        
        # Get definition if available
        if data.get("Definition"):
            results.append({
                "title": f"Definition: {data.get('DefinitionSource', 'Unknown')}",
                "url": data.get("DefinitionURL", ""),
                "snippet": data.get("Definition", ""),
                "source": data.get("DefinitionSource", "Unknown"),
                "type": "definition"
            })
        
        return results
    
    def _search_fallback(self, query: str) -> List[Dict[str, Any]]:
        """Basic fallback when primary search fails."""
        return [{
            "title": f"Search suggestion for: {query}",
            "url": f"https://www.google.com/search?q={quote_plus(query + ' documentation')}",
            "snippet": f"Suggested search for {query} documentation and examples",
            "source": "Search Engine",
            "type": "suggestion"
        }]
    
    def _filter_and_enhance_results(self, results: List[Dict[str, Any]], filter_keywords: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Filter and enhance search results."""
        if not filter_keywords:
            return results[:self.max_results]
        
        filtered = []
        for result in results:
            # Check if result contains any filter keywords
            text_to_check = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
            if any(keyword.lower() in text_to_check for keyword in filter_keywords):
                filtered.append(result)
        
        # If no filtered results, return original results
        if not filtered:
            filtered = results
        
        return filtered[:self.max_results]
    
    def _generate_search_summary(self, results: List[Dict[str, Any]], query: str) -> str:
        """Generate a summary of search results."""
        if not results:
            return f"No web search results found for: {query}"
        
        summary_parts = [f"Found {len(results)} web results for '{query}':"]
        
        for i, result in enumerate(results[:3], 1):
            title = result.get("title", "Unknown")
            source = result.get("source", "Unknown")
            summary_parts.append(f"{i}. {title} ({source})")
        
        return "\n".join(summary_parts)
    
    def search_documentation(self, technology: str, topic: str) -> Dict[str, Any]:
        """Search for specific documentation about a technology/framework."""
        query = f"{technology} {topic} documentation tutorial"
        filter_keywords = ["docs", "documentation", "tutorial", "guide", "api", "reference"]
        return self.search(query, filter_keywords)
    
    def search_code_examples(self, technology: str, use_case: str) -> Dict[str, Any]:
        """Search for code examples related to a specific use case."""
        query = f"{technology} {use_case} code example implementation"
        filter_keywords = ["example", "code", "implementation", "tutorial", "github", "stackoverflow"]
        return self.search(query, filter_keywords)
    
    def search_comparison(self, tech1: str, tech2: str) -> Dict[str, Any]:
        """Search for comparisons between two technologies."""
        query = f"{tech1} vs {tech2} comparison differences"
        filter_keywords = ["vs", "comparison", "difference", "comparison", "versus"]
        return self.search(query, filter_keywords)


# Web search tool functions for tool registry
def web_search_general(args: Dict[str, Any], agent_context: Any = None) -> Dict[str, Any]:
    """General web search tool function."""
    query = args["query"]
    max_results = args.get("max_results", 5)
    filter_keywords = args.get("filter_keywords", None)
    
    search_tool = WebSearchTool(max_results=max_results)
    return search_tool.search(query, filter_keywords)


def web_search_documentation(args: Dict[str, Any], agent_context: Any = None) -> Dict[str, Any]:
    """Documentation-focused web search tool function."""
    technology = args["technology"]
    topic = args["topic"]
    
    search_tool = WebSearchTool()
    return search_tool.search_documentation(technology, topic)


def web_search_code_examples(args: Dict[str, Any], agent_context: Any = None) -> Dict[str, Any]:
    """Code examples web search tool function."""
    technology = args["technology"]
    use_case = args["use_case"]
    
    search_tool = WebSearchTool()
    return search_tool.search_code_examples(technology, use_case)


def web_search_comparison(args: Dict[str, Any], agent_context: Any = None) -> Dict[str, Any]:
    """Technology comparison web search tool function."""
    tech1 = args["tech1"]
    tech2 = args["tech2"]
    
    search_tool = WebSearchTool()
    return search_tool.search_comparison(tech1, tech2)