"""
WebAgent for CodeFusion

LLM-driven specialist agent for web search and external research with function calling loop.
"""

from typing import Dict, List, Any
from cf.agents.base import BaseAgent


class WebAgent(BaseAgent):
    """
    Web research agent with true function calling loop.
    """
    
    def __init__(self, repo_path: str, config: Dict[str, Any]):
        super().__init__(repo_path, config, "web")
        
        # Track conversation history for function calling loop
        self.conversation_history = []
        self.tool_results = []
    
    def _analyze_step(self, question: str) -> str:
        """Run complete function calling loop until LLM says done"""
        
        # Initialize conversation with system message and user question
        if self.iteration == 1:
            self._initialize_conversation(question)
        
        # Log action planning phase
        self.logger.verbose_action("ACTION PLANNING PHASE", 
                                 "Searching the web for external documentation and related information about the topic...")
        
        # Run function calling loop
        loop_result = self._run_function_calling_loop()
        
        return loop_result
    
    def _initialize_conversation(self, question: str):
        """Initialize the conversation for function calling"""
        
        system_message = {
            "role": "system",
            "content": """You are a web research specialist. Your job is to search the web for information to answer user questions.

Available tools:
- web_search: Search the web for general information
- search_documentation: Search for official documentation and guides

Process:
1. Use web_search to find relevant information
2. Use search_documentation when looking for official docs
3. Gather information from multiple sources if needed
4. When you have sufficient information, respond with your analysis

Focus on finding accurate, up-to-date information from reliable sources."""
        }
        
        user_message = {
            "role": "user", 
            "content": f"Please search the web to answer this question: {question}"
        }
        
        self.conversation_history = [system_message, user_message]
    
    def _run_function_calling_loop(self) -> str:
        """Run the actual function calling loop"""
        
        max_function_calls = 6  # Hard limit for web searches
        function_calls_made = 0
        
        # Get available web tools only
        all_tools = self.tools.get_all_schemas()
        web_tools = [tool for tool in all_tools if tool['function']['name'] in ['web_search', 'search_documentation']]
        
        self.logger.verbose_progress("Using LLM function calling for intelligent tool selection", "🔧")
        self.logger.debug(f"Retrieved {len(web_tools)} web tool schemas from registry")
        
        while function_calls_made < max_function_calls:
            try:
                self.logger.debug(f"Function call iteration {function_calls_made + 1}/{max_function_calls}")
                
                # Get LLM response with function calling
                if function_calls_made == 0:
                    self.logger.verbose_progress("Calling LLM with function calling enabled...", "📡")
                response = self.llm.generate_with_functions(
                    self._build_conversation_prompt(),
                    web_tools,
                    ""  # System prompt already in conversation history
                )
                
                if not response.get('success'):
                    self.logger.debug(f"LLM call failed: {response.get('error', 'Unknown error')}")
                    break
                
                # Add LLM response to conversation
                assistant_message = {
                    "role": "assistant",
                    "content": response.get('content', '')
                }
                
                # Check if LLM wants to make a function call
                if response.get('function_call'):
                    function_calls_made += 1
                    
                    # Execute the function call
                    func_call = response['function_call']
                    tool_name = func_call['name']
                    tool_params = func_call['arguments']
                    
                    self.logger.verbose_tool_call(tool_name, tool_params)
                    
                    # Add function call to assistant message
                    assistant_message['function_call'] = func_call
                    self.conversation_history.append(assistant_message)
                    
                    # Execute the tool
                    self.logger.debug(f"Executing tool {tool_name} with params: {tool_params}")
                    tool_result = self.use_tool(tool_name, **tool_params)
                    self.logger.debug(f"Tool result success: {not tool_result.get('error')}")
                    
                    # Store for tracking
                    self.tool_results.append({
                        'tool': tool_name,
                        'params': tool_params,
                        'result': tool_result
                    })
                    
                    # Extract insights
                    self._extract_insights_from_tool_result(tool_name, tool_result, tool_params)
                    
                    # Add function result to conversation
                    function_result_message = {
                        "role": "function",
                        "name": tool_name,
                        "content": self._format_tool_result_for_llm(tool_result)
                    }
                    self.conversation_history.append(function_result_message)
                    
                    # Continue loop - LLM will see the result and decide what to do next
                    continue
                    
                else:
                    # No function call - LLM is done
                    self.conversation_history.append(assistant_message)
                    
                    # Store the final response for synthesis
                    self.final_llm_response = response.get('content', '')
                    
                    return f"function_calling_complete_after_{function_calls_made}_calls"
                
            except Exception as e:
                self.add_insight(
                    f"Function calling loop error: {str(e)}",
                    confidence=0.2,
                    source="function_calling_error"
                )
                break
        
        return f"function_calling_stopped_at_limit_{function_calls_made}"
    
    def _build_conversation_prompt(self) -> str:
        """Build prompt from conversation history"""
        
        # Convert conversation history to a single prompt for LLM
        prompt_parts = []
        
        for message in self.conversation_history[1:]:  # Skip system message
            role = message['role']
            content = message['content']
            
            if role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
                if message.get('function_call'):
                    func_call = message['function_call']
                    prompt_parts.append(f"[Called function: {func_call['name']} with params: {func_call['arguments']}]")
            elif role == 'function':
                prompt_parts.append(f"Function {message['name']} result: {content}")
        
        return "\n\n".join(prompt_parts)
    
    def _format_tool_result_for_llm(self, tool_result: Dict[str, Any]) -> str:
        """Format tool result for LLM consumption"""
        
        if tool_result.get('error'):
            return f"Error: {tool_result['error']}"
        
        # Format web search results
        if 'results' in tool_result:
            results = tool_result.get('results', [])
            query = tool_result.get('query', '') or tool_result.get('topic', '')
            
            if results:
                result_summary = []
                for result in results[:5]:
                    title = result.get('title', 'No title')
                    snippet = result.get('snippet', 'No description')
                    url = result.get('url', '')
                    source = result.get('source', 'Web')
                    
                    result_summary.append(f"**{title}** ({source})\n{snippet}\nURL: {url}")
                
                return f"Search results for '{query}' ({len(results)} found):\n\n" + "\n\n".join(result_summary)
            else:
                return f"No results found for '{query}'"
        
        else:
            # Generic result
            return str(tool_result)[:1500]
    
    def _extract_insights_from_tool_result(self, tool_name: str, result: Dict[str, Any], params: Dict[str, Any]):
        """Extract insights from web search tool results"""
        
        if result.get('error'):
            return
        
        if tool_name in ['web_search', 'search_documentation']:
            results = result.get('results', [])
            query = params.get('query', '') or params.get('topic', '')
            
            if results:
                # Count reliable sources
                reliable_sources = [r for r in results if any(domain in r.get('url', '').lower() 
                                                            for domain in ['github.com', '.org', 'docs.', 'documentation', 'stackoverflow'])]
                
                insight = f"Found {len(results)} web results for '{query}'"
                if reliable_sources:
                    insight += f" including {len(reliable_sources)} from reliable sources"
                
                confidence = 0.8 if reliable_sources else 0.6
                self.add_insight(insight, confidence=confidence, source="web_search")
                
                # Add insight about top result if it looks reliable
                if results:
                    top_result = results[0]
                    title = top_result.get('title', 'No title')
                    source = top_result.get('source', 'unknown source')
                    
                    # Higher confidence for known reliable sources
                    result_confidence = 0.8 if any(domain in top_result.get('url', '').lower() 
                                                 for domain in ['github.com', '.org', 'docs.', 'stackoverflow']) else 0.6
                    
                    self.add_insight(
                        f"Top result: {title} from {source}",
                        confidence=result_confidence,
                        source="web_result"
                    )
    
    def _is_analysis_complete(self, question: str) -> bool:
        """Analysis complete after one function calling loop"""
        return self.iteration >= 1
    
    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate results using the final LLM response"""
        
        # Check if we have any tool results from web search
        if not hasattr(self, 'final_llm_response') and not self.insights and not self.tool_results:
            return {
                'success': False,
                'error': 'No web research completed',
                'question': question
            }
        
        # Use the LLM's final response as the narrative, or synthesize if needed
        if hasattr(self, 'final_llm_response') and self.final_llm_response:
            narrative = self.final_llm_response
        else:
            narrative = self._create_fallback_narrative()
        
        confidence = min(0.9, 0.5 + (len(self.insights) * 0.1))
        
        return {
            'success': True,
            'question': question,
            'narrative': narrative,
            'insights': self.insights,
            'confidence': confidence,
            'tools_used': len(self.tool_results),
            'function_calls_made': len([r for r in self.tool_results]),
            'agent': 'web'
        }
    
    def _create_fallback_narrative(self) -> str:
        """Create fallback narrative"""
        if self.tool_results:
            # Use tool results to create narrative
            search_count = len([r for r in self.tool_results if r['tool'] in ['web_search', 'search_documentation']])
            if search_count > 0:
                return f"Web research completed {search_count} searches and found relevant information about the topic."
        
        if not self.insights:
            return "Web research found no relevant information."
        
        return f"Web research completed with {len(self.insights)} insights. " + \
               self.insights[0].get('content', '')
