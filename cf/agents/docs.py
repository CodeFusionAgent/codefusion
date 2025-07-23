"""
DocsAgent for CodeFusion

LLM-driven specialist agent with proper function calling loop.
"""

from typing import Dict, List, Any
from cf.agents.base import BaseAgent


class DocsAgent(BaseAgent):
    """
    Documentation analysis agent with true function calling loop.
    """
    
    def __init__(self, repo_path: str, config: Dict[str, Any]):
        super().__init__(repo_path, config, "docs")
        
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
                                 "Analyzing documentation files to understand the system architecture and find relevant guides...")
        
        # Run function calling loop
        loop_result = self._run_function_calling_loop()
        
        return loop_result
    
    def _initialize_conversation(self, question: str):
        """Initialize the conversation for function calling"""
        
        system_message = {
            "role": "system",
            "content": """You are a documentation analysis specialist. Your job is to analyze documentation files to answer user questions.

Available tools:
- scan_directory: Find documentation files and directories  
- search_files: Search for specific terms in documentation
- read_file: Read documentation files
- analyze_code_structure: Analyze code examples in docs

Process:
1. Use tools to systematically find and analyze documentation
2. Focus on README files, docs/, guides, tutorials
3. Search for relevant content
4. Read the most important documentation files
5. When you have sufficient information, respond with your analysis

Be efficient - use tools strategically and stop when you have enough information to answer the question."""
        }
        
        user_message = {
            "role": "user", 
            "content": f"Please analyze the documentation to answer this question: {question}"
        }
        
        self.conversation_history = [system_message, user_message]
    
    def _run_function_calling_loop(self) -> str:
        """Run the actual function calling loop"""
        
        max_function_calls = 10  # Hard limit to prevent infinite loops
        function_calls_made = 0
        
        # Get available tools (exclude web tools for docs agent)
        all_tools = self.tools.get_all_schemas()
        doc_tools = [tool for tool in all_tools if tool['function']['name'] not in ['web_search', 'search_documentation']]
        
        self.logger.verbose_progress("Using LLM function calling for intelligent tool selection", "🔧")
        self.logger.debug(f"Retrieved {len(doc_tools)} tool schemas from registry")
        
        while function_calls_made < max_function_calls:
            try:
                self.logger.debug(f"Function call iteration {function_calls_made + 1}/{max_function_calls}")
                
                # Get LLM response with function calling
                if function_calls_made == 0:
                    self.logger.verbose_progress("Calling LLM with function calling enabled...", "📡")
                response = self.llm.generate_with_functions(
                    self._build_conversation_prompt(),
                    doc_tools,
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
        
        # Format based on tool type
        if 'files' in tool_result:
            # scan_directory result
            files = tool_result.get('files', [])
            doc_files = [f for f in files if self._is_doc_file(f.get('path', ''))]
            
            if doc_files:
                file_list = [f.get('path', '') for f in doc_files[:10]]
                return f"Found {len(doc_files)} documentation files: {', '.join(file_list)}"
            else:
                return f"Found {len(files)} files but no documentation files"
        
        elif 'matches' in tool_result:
            # search_files result
            matches = tool_result.get('matches', [])
            if matches:
                match_summary = []
                for match in matches[:5]:
                    file_path = match.get('file', '')
                    line = match.get('line', 0)
                    content = match.get('content', '')[:100]
                    match_summary.append(f"{file_path}:{line} - {content}")
                return f"Found {len(matches)} matches:\n" + "\n".join(match_summary)
            else:
                return "No matches found"
        
        elif 'content' in tool_result:
            # read_file result
            content = tool_result.get('content', '')
            lines = len(content.split('\n'))
            # Return first part of content for LLM to analyze
            preview = content[:2000] + ("..." if len(content) > 2000 else "")
            return f"File content ({lines} lines):\n{preview}"
        
        else:
            # Generic result
            return str(tool_result)
    
    def _is_doc_file(self, file_path: str) -> bool:
        """Check if file is documentation"""
        if not file_path:
            return False
        
        file_lower = file_path.lower()
        
        doc_patterns = [
            'readme', 'changelog', 'license', 'contributing', 'guide', 'tutorial',
            'docs', 'documentation', 'manual', 'help', 'getting-started',
            'quickstart', 'install', 'setup', 'usage', 'api'
        ]
        
        doc_extensions = ['.md', '.txt', '.rst', '.adoc']
        
        return (any(pattern in file_lower for pattern in doc_patterns) or
                any(file_lower.endswith(ext) for ext in doc_extensions))
    
    def _extract_insights_from_tool_result(self, tool_name: str, result: Dict[str, Any], params: Dict[str, Any]):
        """Extract insights from tool results"""
        
        if result.get('error'):
            return
        
        if tool_name == 'scan_directory':
            files = result.get('files', [])
            doc_files = [f for f in files if self._is_doc_file(f.get('path', ''))]
            
            if doc_files:
                readme_files = [f for f in doc_files if 'readme' in f.get('path', '').lower()]
                insight = f"Found {len(doc_files)} documentation files"
                if readme_files:
                    insight += f" including {len(readme_files)} README files"
                self.add_insight(insight, confidence=0.8, source="doc_discovery")
        
        elif tool_name == 'search_files':
            matches = result.get('matches', [])
            if matches:
                doc_matches = [m for m in matches if self._is_doc_file(m.get('file', ''))]
                if doc_matches:
                    pattern = params.get('pattern', '')
                    unique_files = list(set([m.get('file', '') for m in doc_matches]))
                    self.add_insight(
                        f"Found '{pattern}' in {len(doc_matches)} places across {len(unique_files)} documentation files",
                        confidence=0.7,
                        source="doc_search"
                    )
        
        elif tool_name == 'read_file':
            file_path = params.get('file_path', '')
            content = result.get('content', '')
            
            if content and self._is_doc_file(file_path):
                lines = len(content.split('\n'))
                confidence = 0.9 if 'readme' in file_path.lower() else 0.7
                self.add_insight(
                    f"Analyzed documentation file {file_path} ({lines} lines)",
                    confidence=confidence,
                    source="doc_content"
                )
    
    def _is_analysis_complete(self, question: str) -> bool:
        """Analysis complete after one function calling loop"""
        return self.iteration >= 1
    
    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate results using the final LLM response"""
        
        if not hasattr(self, 'final_llm_response') and not self.insights:
            return {
                'success': False,
                'error': 'No documentation analysis completed',
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
            'agent': 'docs'
        }
    
    def _create_fallback_narrative(self) -> str:
        """Create fallback narrative"""
        if not self.insights:
            return "Documentation analysis found no relevant information."
        
        return f"Documentation analysis completed with {len(self.insights)} insights. " + \
               self.insights[0].get('content', '')
