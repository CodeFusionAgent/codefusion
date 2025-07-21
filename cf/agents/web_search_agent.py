"""
Web Search Agent for CodeFusion

A specialized agent that consolidates all web search functionality and provides
intelligent web search capabilities for code analysis enhancement.
"""

import json
import re
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from cf.aci.repo import CodeRepo
from cf.config import CfConfig
from cf.core.react_agent import ReActAgent, ReActAction, ActionType
from cf.utils.logging_utils import agent_log, progress_log, error_log
from cf.tools.web_search import WebSearchTool
from cf.llm.real_llm import get_real_llm


@dataclass
class WebSearchResult:
    """Represents a web search result."""
    title: str
    url: str
    snippet: str
    source: str
    relevance_score: float = 0.0
    search_query: str = ""
    type: str = "general"


class WebSearchAgent(ReActAgent):
    """
    Web Search Agent that consolidates all web search functionality.
    Moved logic from InteractiveSessionManager to avoid duplication.
    """
    
    def __init__(self, repo: CodeRepo, config: CfConfig):
        super().__init__(repo, config, "WebSearchAgent")
        self.web_search_tool = WebSearchTool(max_results=5)
        
    def reason(self) -> str:
        """Generate reasoning for current state (ReAct abstract method)."""
        iteration = self.state.iteration
        goal = self.state.goal
        
        if iteration == 0:
            return f"I need to search the web for information about: {goal}. I should start by analyzing the question to determine the best search strategy."
        elif iteration == 1:
            return "Based on my analysis, I should perform targeted web searches for relevant documentation and resources."
        elif iteration == 2:
            return "I should analyze the search results and extract the most relevant insights for the question."
        else:
            return "I should consolidate all web search findings into actionable insights."
    
    def plan_action(self, reasoning: str) -> ReActAction:
        """Plan the next action to take (ReAct abstract method)."""
        iteration = self.state.iteration
        
        if iteration == 0:
            return ReActAction(
                action_type=ActionType.LLM_REASONING,
                description="Analyze question and plan web search strategy",
                parameters={"analysis_type": "web_search_planning"},
                tool_name="analyze_search_strategy"
            )
        elif iteration == 1:
            return ReActAction(
                action_type=ActionType.LLM_REASONING,
                description="Execute web searches for documentation and examples",
                parameters={"search_type": "comprehensive_web_search"},
                tool_name="execute_web_searches"
            )
        else:
            return ReActAction(
                action_type=ActionType.LLM_SUMMARY,
                description="Consolidate web search results into insights",
                parameters={"consolidation_type": "web_insights"},
                tool_name="consolidate_web_results"
            )
    
    def _generate_summary(self, focus: str = "web_search") -> Dict[str, Any]:
        """Generate summary of web search analysis (ReAct abstract method)."""
        search_results = self.state.tool_results.get('execute_web_searches', {})
        consolidation_results = self.state.tool_results.get('consolidate_web_results', {})
        
        total_results = search_results.get('total_results', 0)
        insights = consolidation_results.get('insights', [])
        search_queries = search_results.get('search_queries', [])
        
        return {
            "agent_name": "WebSearchAgent",
            "focus": focus,
            "summary": f"Executed {len(search_queries)} web searches and found {total_results} relevant results",
            "web_search_insights": insights,
            "search_queries_used": search_queries,
            "total_web_results": total_results,
            "iterations": self.state.iteration,
            "success": total_results > 0,
            "confidence": min(0.9, total_results / 10.0),  # Scale confidence with results found
            "insights": insights,
            "results": search_results.get('results', [])
        }
        
    def search_for_question(self, question: str, narrative_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main entry point - performs comprehensive web search for a question.
        Uses ReAct pattern for systematic web search analysis.
        
        Args:
            question: The question to search for
            narrative_result: Optional narrative context
            
        Returns:
            Web search results with insights
        """
        agent_log(f"🌐 [WebSearchAgent] Starting web search for: {question}")
        
        # Perform web search directly (simplified approach)
        try:
            # Step 1: Analyze search strategy
            search_queries = self._craft_search_queries_with_llm(question, narrative_result or {})
            
            # Step 2: Execute web searches
            all_results = []
            for query in search_queries[:2]:  # Limit to 2 searches
                progress_log(f"🔍 [WebSearchAgent] Searching: {query}")
                results = self.web_search_tool.search(query, filter_keywords=['docs', 'documentation', 'tutorial'])
                
                if results['success'] and results['results']:
                    all_results.extend(results['results'])
            
            # Step 3: Try LLM fallback if no results
            if not all_results:
                progress_log("🤖 [WebSearchAgent] Using LLM to generate documentation suggestions...")
                llm_results = self._generate_llm_documentation_suggestions(search_queries[0] if search_queries else question)
                if llm_results:
                    all_results.extend(llm_results)
            
            # Step 4: Extract insights
            insights = self._extract_insights_from_search_results(all_results, question) if all_results else []
            
            return {
                "success": len(all_results) > 0,
                "results": all_results,
                "insights": insights,
                "total_results": len(all_results),
                "search_queries": search_queries,
                "summary": f"Found {len(all_results)} relevant web results from {len(search_queries)} queries"
            }
            
        except Exception as e:
            error_log(f"❌ [WebSearchAgent] Web search failed: {e}")
            return {
                "success": False,
                "results": [],
                "insights": [],
                "error": f"Web search failed: {str(e)}"
            }
    
    def _execute_action(self, action: ReActAction) -> Dict[str, Any]:
        """Execute the specified action (ReAct method)."""
        try:
            if action.tool_name == "analyze_search_strategy":
                return self._analyze_search_strategy()
            elif action.tool_name == "execute_web_searches":
                return self._execute_web_searches()
            elif action.tool_name == "consolidate_web_results":
                return self._consolidate_web_results()
            else:
                return {"success": False, "error": f"Unknown tool: {action.tool_name}"}
        except Exception as e:
            error_log(f"❌ [WebSearchAgent] Action execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _analyze_search_strategy(self) -> Dict[str, Any]:
        """Analyze the question and plan search strategy."""
        question = self.state.current_context.get("question", "")
        
        # Use LLM to craft search queries based on the question
        search_queries = self._craft_search_queries_with_llm(question, {})
        
        progress_log(f"🎯 [WebSearchAgent] Planned {len(search_queries)} search queries")
        
        return {
            "success": True,
            "search_queries": search_queries,
            "strategy": "LLM-driven query generation",
            "query_count": len(search_queries)
        }
    
    def _execute_web_searches(self) -> Dict[str, Any]:
        """Execute the planned web searches."""
        strategy_result = self.state.tool_results.get('analyze_search_strategy', {})
        search_queries = strategy_result.get('search_queries', [])
        question = self.state.current_context.get("question", "")
        
        if not search_queries:
            # Fallback search queries
            search_queries = [f"{question} documentation", f"{question} tutorial"]
        
        all_results = []
        
        for query in search_queries[:2]:  # Limit to 2 searches
            progress_log(f"🔍 [WebSearchAgent] Searching: {query}")
            results = self.web_search_tool.search(query, filter_keywords=['docs', 'documentation', 'tutorial'])
            
            if results['success'] and results['results']:
                all_results.extend(results['results'])
        
        # If no results from primary search, try LLM-powered fallback
        if not all_results:
            progress_log("🤖 [WebSearchAgent] Using LLM to generate documentation suggestions...")
            llm_results = self._generate_llm_documentation_suggestions(search_queries[0] if search_queries else question)
            if llm_results:
                all_results.extend(llm_results)
        
        progress_log(f"✅ [WebSearchAgent] Found {len(all_results)} web search results")
        
        return {
            "success": True,
            "results": all_results,
            "total_results": len(all_results),
            "search_queries": search_queries,
            "queries_executed": len(search_queries)
        }
    
    def _consolidate_web_results(self) -> Dict[str, Any]:
        """Consolidate web search results into actionable insights."""
        search_result = self.state.tool_results.get('execute_web_searches', {})
        all_results = search_result.get('results', [])
        question = self.state.current_context.get("question", "")
        
        if not all_results:
            return {
                "success": False,
                "insights": [],
                "error": "No web search results to consolidate"
            }
        
        # Extract insights from search results
        insights = self._extract_insights_from_search_results(all_results, question)
        
        progress_log(f"💡 [WebSearchAgent] Extracted {len(insights)} insights from web results")
        
        return {
            "success": True,
            "insights": insights,
            "total_results": len(all_results),
            "insights_count": len(insights),
            "summary": f"Consolidated {len(all_results)} web results into {len(insights)} actionable insights"
        }
    
    def _craft_search_queries_with_llm(self, question: str, narrative_result: Dict[str, Any]) -> List[str]:
        """
        Use LLM to craft targeted search queries.
        Moved from InteractiveSessionManager to consolidate logic.
        """
        try:
            real_llm = get_real_llm()
            if not real_llm or not real_llm.client:
                return []
            
            # Extract technologies from question
            tech_keywords = self._extract_tech_keywords(question)
            
            tech_list = ', '.join(tech_keywords) if tech_keywords else 'None specific'
            
            prompt = f"""Based on this question: "{question}"
            
Technologies mentioned: {tech_list}

Generate 2-3 focused web search queries that would find the most relevant documentation and examples to enhance understanding of this question. Focus on official documentation, architectural guides, and comparison articles.

Return only the search queries, one per line, without explanations."""
            
            response = real_llm._call_llm(prompt)
            
            if isinstance(response, dict):
                content = response.get('content', '')
            else:
                content = str(response)
            
            # Parse search queries from response
            queries = []
            for line in content.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and len(line) > 10:
                    queries.append(line)
            
            return queries[:3]  # Limit to 3 queries
            
        except Exception as e:
            # Fallback to basic queries if LLM fails
            tech_keywords = self._extract_tech_keywords(question)
            if len(tech_keywords) >= 2:
                return [f"{tech_keywords[0]} {tech_keywords[1]} comparison documentation"]
            elif tech_keywords:
                return [f"{tech_keywords[0]} documentation tutorial"]
            return []
    
    def _generate_llm_documentation_suggestions(self, query: str) -> List[Dict[str, Any]]:
        """
        Use LLM to generate documentation suggestions when web search fails.
        Moved from InteractiveSessionManager to consolidate logic.
        """
        try:
            real_llm = get_real_llm()
            if not real_llm or not real_llm.client:
                return []
            
            prompt = f"""Query: "{query}"

Generate 3-5 relevant documentation links and resources for this query. Consider:
- Official documentation sites
- Tutorial resources  
- Community guides
- API references

Return a JSON array with this format:
[
  {{
    "title": "Resource Title",
    "url": "https://example.com/docs",
    "snippet": "Brief description of what this resource covers",
    "source": "Source Name"
  }}
]

Focus on high-quality, official documentation sources."""

            response = real_llm._call_llm(prompt)
            
            # Parse LLM response
            if isinstance(response, dict):
                content = response.get('content', '')
            else:
                content = str(response)
            
            # Extract JSON array from response
            json_match = re.search(r'\[(.*?)\]', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    llm_results = json.loads(json_str)
                    
                    # Validate and format results
                    formatted_results = []
                    for result in llm_results:
                        if isinstance(result, dict) and result.get('title') and result.get('url'):
                            formatted_results.append({
                                "title": result.get('title', 'Unknown'),
                                "url": result.get('url', ''),
                                "snippet": result.get('snippet', ''),
                                "source": result.get('source', 'LLM Generated'),
                                "type": "llm_documentation"
                            })
                    
                    return formatted_results
                        
                except (json.JSONDecodeError, TypeError):
                    error_log(f"⚠️  Failed to parse LLM documentation suggestions")
            
        except Exception as e:
            error_log(f"❌ LLM documentation suggestions failed: {e}")
        
        return []
    
    def _extract_insights_from_search_results(self, results: List[Dict[str, Any]], question: str) -> List[str]:
        """
        Extract actionable insights from web search results.
        Moved from InteractiveSessionManager to consolidate logic.
        """
        insights = []
        
        for result in results[:3]:  # Top 3 results
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            source = result.get('source', '')
            
            if title and snippet:
                insight = f"According to {source}, {snippet[:120]}..."
                insights.append(insight)
        
        return insights
    
    def _extract_tech_keywords(self, text: str) -> List[str]:
        """
        Extract technology keywords from text.
        Moved from InteractiveSessionManager to consolidate logic.
        """
        tech_keywords = [
            'fastapi', 'starlette', 'django', 'flask', 'python', 'javascript', 'typescript',
            'react', 'vue', 'angular', 'node', 'express', 'postgres', 'mysql', 'redis',
            'docker', 'kubernetes', 'aws', 'api', 'rest', 'graphql', 'websocket'
        ]
        
        text_lower = text.lower()
        found_keywords = [keyword for keyword in tech_keywords if keyword in text_lower]
        return found_keywords
    
    def search_documentation(self, technology: str, topic: str) -> Dict[str, Any]:
        """Search for specific documentation about a technology/framework."""
        question = f"How does {topic} work in {technology}?"
        return self.search_for_question(question)
    
    def search_code_examples(self, technology: str, use_case: str) -> Dict[str, Any]:
        """Search for code examples related to a specific use case."""
        question = f"Show me {technology} {use_case} code examples"
        return self.search_for_question(question)
    
    def search_comparison(self, tech1: str, tech2: str) -> Dict[str, Any]:
        """Search for comparisons between two technologies."""
        question = f"Compare {tech1} vs {tech2} differences"
        return self.search_for_question(question)