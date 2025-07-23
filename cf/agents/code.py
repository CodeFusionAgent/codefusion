"""
CodeAgent for CodeFusion

Simple LLM-driven specialist agent that uses function calling to analyze code.
"""

from typing import Dict, List, Any
from cf.agents.base import BaseAgent


class CodeAgent(BaseAgent):
    """
    LLM-driven code analysis agent using function calling.
    """
    
    def __init__(self, repo_path: str, config: Dict[str, Any]):
        super().__init__(repo_path, config, "code")
        
        # Track conversation history for function calling loop
        self.conversation_history = []
        self.tool_results = []
        self.tools_used = set()  # Track tools used to prevent repetition
    
    def _analyze_step(self, question: str) -> str:
        """Run complete function calling loop until LLM says done"""
        
        # Initialize conversation with system message and user question
        if self.iteration == 1:
            self._initialize_conversation(question)
        
        # Log action planning phase
        self.logger.verbose_action("ACTION PLANNING PHASE", 
                                 "Since there are no code files found yet, the first step is to identify and explore the directory str...")
        
        # Run function calling loop
        loop_result = self._run_function_calling_loop()
        
        return loop_result
    
    def _initialize_conversation(self, question: str):
        """Initialize the conversation for function calling"""
        
        system_message = {
            "role": "system",
            "content": """You are a code analysis specialist. Your job is to analyze source code to answer user questions.

Available tools:
- scan_directory: Understand codebase structure
- search_files: Find relevant code files  
- read_file: Examine specific code files
- analyze_code_structure: Understand code architecture
- extract_functions: Get function information
- extract_classes: Get class information

Process:
1. Use tools strategically to find relevant code
2. Focus on source code files (not docs, tests, builds)
3. Read and analyze the most important files
4. Extract functions/classes as needed
5. When you have sufficient information, respond with your analysis

Be efficient - use tools strategically and stop when you have enough information to answer the question."""
        }
        
        user_message = {
            "role": "user", 
            "content": f"Please analyze the codebase to answer this question: {question}"
        }
        
        self.conversation_history = [system_message, user_message]
    
    def _run_function_calling_loop(self) -> str:
        """Run the actual function calling loop"""
        
        max_function_calls = 12  # Hard limit for code analysis
        function_calls_made = 0
        
        # Get available tools for function calling
        available_tools = self.tools.get_all_schemas()
        
        self.logger.verbose_progress("Using LLM function calling for intelligent tool selection", "🔧")
        self.logger.debug(f"Retrieved {len(available_tools)} tool schemas from registry")
        
        while function_calls_made < max_function_calls:
            try:
                self.logger.debug(f"Function call iteration {function_calls_made + 1}/{max_function_calls}")
                
                # Get LLM response with function calling
                self.logger.verbose_progress("Calling LLM with function calling enabled...", "📡")
                response = self.llm.generate_with_functions(
                    self._build_conversation_prompt(),
                    available_tools,
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
                    
                    # Create tool signature for loop detection
                    tool_signature = f"{tool_name}_{str(sorted(tool_params.items()))}"
                    
                    # Check for repetitive calls
                    if tool_signature in self.tools_used and tool_name == 'read_file':
                        self.logger.debug(f"Skipping repetitive tool call: {tool_name} with same params")
                        # Add a message to conversation indicating we've already done this
                        function_result_message = {
                            "role": "function",
                            "name": tool_name,
                            "content": "This file has already been analyzed in this conversation."
                        }
                        self.conversation_history.append(function_result_message)
                        continue
                    
                    self.tools_used.add(tool_signature)
                    
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
                    self.logger.debug("LLM finished, no more function calls")
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
            if files:
                file_list = [f.get('path', '') for f in files[:15]]
                return f"Found {len(files)} files: {', '.join(file_list)}"
            else:
                return "No files found"
        
        elif 'matches' in tool_result:
            # search_files result
            matches = tool_result.get('matches', [])
            if matches:
                match_summary = []
                for match in matches[:8]:
                    file_path = match.get('file', '')
                    line = match.get('line', 0)
                    content = match.get('content', '')[:80]
                    match_summary.append(f"{file_path}:{line} - {content}")
                return f"Found {len(matches)} matches:\n" + "\n".join(match_summary)
            else:
                return "No matches found"
        
        elif 'content' in tool_result:
            # read_file result
            content = tool_result.get('content', '')
            lines = len(content.split('\n'))
            # Return first part of content for LLM to analyze
            preview = content[:3000] + ("..." if len(content) > 3000 else "")
            return f"File content ({lines} lines):\n{preview}"
        
        elif 'architecture_type' in tool_result:
            # analyze_code_structure result
            arch = tool_result.get('architecture_type', 'unknown')
            complexity = tool_result.get('complexity_score', 0)
            components = tool_result.get('key_components', [])
            patterns = tool_result.get('patterns', [])
            
            result_parts = [f"Architecture: {arch}, Complexity: {complexity}/10"]
            if components:
                result_parts.append(f"Components: {', '.join(components[:5])}")
            if patterns:
                result_parts.append(f"Patterns: {', '.join(patterns[:3])}")
            
            return "\n".join(result_parts)
        
        elif 'functions' in tool_result:
            # extract_functions result
            functions = tool_result.get('functions', [])
            if functions:
                func_list = []
                for func in functions[:8]:
                    name = func.get('name', '')
                    signature = func.get('signature', '')
                    purpose = func.get('purpose', '')
                    func_list.append(f"{name}: {signature} - {purpose}")
                return f"Found {len(functions)} functions:\n" + "\n".join(func_list)
            else:
                return "No functions found"
        
        elif 'classes' in tool_result:
            # extract_classes result
            classes = tool_result.get('classes', [])
            if classes:
                class_list = []
                for cls in classes[:5]:
                    name = cls.get('name', '')
                    methods = cls.get('methods', [])
                    purpose = cls.get('purpose', '')
                    class_list.append(f"{name}: {len(methods)} methods - {purpose}")
                return f"Found {len(classes)} classes:\n" + "\n".join(class_list)
            else:
                return "No classes found"
        
        else:
            # Generic result
            return str(tool_result)[:1000]
    
    def _build_analysis_context(self, question: str) -> str:
        """Build context from previous tool results"""
        
        if not self.tool_results:
            return "This is the first analysis step. No previous information available."
        
        context_parts = ["Previous analysis steps:"]
        
        for result_info in self.tool_results[-3:]:  # Last 3 tool results
            tool_name = result_info['tool']
            tool_result = result_info['result']
            
            if tool_result.get('error'):
                context_parts.append(f"- {tool_name}: Failed - {tool_result['error']}")
            else:
                # Summarize key information from tool result
                if tool_name == 'scan_directory':
                    file_count = len(tool_result.get('files', []))
                    context_parts.append(f"- {tool_name}: Found {file_count} files")
                elif tool_name == 'search_files':
                    match_count = len(tool_result.get('matches', []))
                    if match_count > 0:
                        files = [m.get('file', '') for m in tool_result.get('matches', [])[:2]]
                        context_parts.append(f"- {tool_name}: Found {match_count} matches in files: {', '.join(files)}")
                    else:
                        context_parts.append(f"- {tool_name}: No matches found")
                elif tool_name == 'read_file':
                    file_path = result_info['params'].get('file_path', 'unknown')
                    lines = tool_result.get('lines', 0)
                    context_parts.append(f"- {tool_name}: Read {file_path} ({lines} lines)")
                elif tool_name in ['analyze_code_structure', 'extract_functions', 'extract_classes']:
                    context_parts.append(f"- {tool_name}: Analysis completed")
        
        # Add current insights summary
        if self.insights:
            context_parts.append(f"\nCurrent insights gathered: {len(self.insights)}")
            context_parts.append("Recent insights:")
            for insight in self.insights[-2:]:
                context_parts.append(f"- {insight.get('content', '')}")
        
        return "\n".join(context_parts)
    
    def _extract_insights_from_tool_result(self, tool_name: str, result: Dict[str, Any], params: Dict[str, Any]):
        """Extract insights from tool results"""
        
        if result.get('error'):
            return
        
        if tool_name == 'scan_directory':
            files = result.get('files', [])
            if files:
                file_types = {}
                for f in files:
                    ext = f.get('extension', 'unknown')
                    file_types[ext] = file_types.get(ext, 0) + 1
                
                primary_type = max(file_types.items(), key=lambda x: x[1])[0] if file_types else 'unknown'
                self.add_insight(
                    f"Codebase contains {len(files)} files, primarily {primary_type} files",
                    confidence=0.8,
                    source="directory_scan"
                )
        
        elif tool_name == 'search_files':
            matches = result.get('matches', [])
            if matches:
                files = list(set([m.get('file', '') for m in matches]))
                self.add_insight(
                    f"Found {len(matches)} relevant code matches in {len(files)} files",
                    confidence=0.7,
                    source="file_search"
                )
        
        elif tool_name == 'analyze_code_structure':
            architecture = result.get('architecture_type', 'unknown')
            complexity = result.get('complexity_score', 0)
            components = result.get('key_components', [])
            
            insight_text = f"Code architecture: {architecture}"
            if complexity > 0:
                insight_text += f", complexity: {complexity}/10"
            if components:
                insight_text += f", key components: {', '.join(components[:3])}"
            
            self.add_insight(insight_text, confidence=0.8, source="structure_analysis")
        
        elif tool_name == 'extract_functions':
            functions = result.get('functions', [])
            if functions:
                func_names = [f.get('name', '') for f in functions[:5]]
                self.add_insight(
                    f"Key functions: {', '.join(func_names)}",
                    confidence=0.7,
                    source="function_analysis"
                )
        
        elif tool_name == 'extract_classes':
            classes = result.get('classes', [])
            if classes:
                class_names = [c.get('name', '') for c in classes[:5]]
                self.add_insight(
                    f"Key classes: {', '.join(class_names)}",
                    confidence=0.7,
                    source="class_analysis"
                )
    
    def _is_analysis_complete(self, question: str) -> bool:
        """Analysis complete after one function calling loop"""
        return self.iteration >= 1
    
    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate results using the final LLM response"""
        
        if not hasattr(self, 'final_llm_response') and not self.insights:
            return {
                'success': False,
                'error': 'No code analysis completed',
                'question': question
            }
        
        # Use the LLM's final response as the narrative, or synthesize if needed
        if hasattr(self, 'final_llm_response') and self.final_llm_response:
            narrative = self.final_llm_response
        else:
            narrative = self._create_fallback_narrative()
        
        confidence = min(0.9, 0.6 + (len(self.insights) * 0.1))
        
        return {
            'success': True,
            'question': question,
            'narrative': narrative,
            'insights': self.insights,
            'confidence': confidence,
            'tools_used': len(self.tool_results),
            'function_calls_made': len([r for r in self.tool_results]),
            'agent': 'code'
        }
    
    def _summarize_tool_results(self) -> str:
        """Create brief summary of tool results"""
        
        if not self.tool_results:
            return "No tools used."
        
        summary_parts = []
        for result_info in self.tool_results:
            tool_name = result_info['tool']
            result = result_info['result']
            
            if result.get('error'):
                summary_parts.append(f"- {tool_name}: Failed")
            else:
                summary_parts.append(f"- {tool_name}: Success")
        
        return "\n".join(summary_parts)
    
    def _create_fallback_narrative(self) -> str:
        """Create simple fallback narrative"""
        
        if not self.insights:
            return "Code analysis was unable to gather sufficient information."
        
        return f"Code analysis found {len(self.insights)} key insights. " + \
               self.insights[0].get('content', 'Analysis completed.')
