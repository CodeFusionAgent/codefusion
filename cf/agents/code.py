"""
CodeAgent for CodeFusion

Simple LLM-driven specialist agent that uses function calling to analyze code.
"""

import os
import time
import json
import fnmatch
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
        
        # File analysis metrics tracking
        self.file_analysis_metrics = []
    
    def _analyze_step(self, question: str) -> str:
        """Run enhanced 3-pass summarization strategy with cached structure prerequisite"""
        
        # Prerequisite: Ensure repository structure is cached and up-to-date
        if self.iteration == 1:
            structure_status = self._ensure_repository_structure_cached()
            if structure_status != "structure_ready":
                # Call scan function to build/update structure
                self._scan_repository_structure(question)
        
        if self.iteration == 1:
            # Pass 1: Question-focused file analysis using cached structure
            print(f"🎯 [CODE_AGENT] Pass 1: Question-focused file analysis...")
            self.logger.verbose_action("PASS 1 - QUESTION-FOCUSED FILE ANALYSIS", 
                                     "Analyzing files relevant to the question using cached structure...")
            
            return self._question_focused_file_analysis(question)
            
        elif self.iteration == 2:
            # Pass 2: Per-module summarization using file summaries
            print(f"📦 [CODE_AGENT] Pass 2: Per-module summarization...")
            return self._generate_module_summaries(question)
            
        elif self.iteration == 3:
            # Pass 3: Project-level feature flows and life of X summaries
            print(f"🚀 [CODE_AGENT] Pass 3: Project-level feature flow analysis...")
            return self._generate_project_feature_flows(question)
            
        else:
            return "analysis_complete"
    
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
        
        # Include system message for Pass 3 (contains detailed analysis context)
        for message in self.conversation_history:
            role = message['role']
            content = message['content']
            
            if role == 'system':
                prompt_parts.append(f"System Context: {content}")
            elif role == 'user':
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
        """Analysis complete after 3 passes: structure+files, modules, project features"""
        return self.iteration >= 3
    
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
    
    def _scan_repository_structure(self, question: str) -> str:
        """Step 1: Scan repository to discover files and structure"""
        try:
            print(f"🔍 [CODE_AGENT] Scanning repository structure...")
            
            # Use scan_directory tool to get repository structure
            max_depth = self.config.get('repo', {}).get('max_scan_depth', 5)
            scan_result = self.use_tool('scan_directory', max_depth=max_depth)
            
            if scan_result.get('error'):
                print(f"❌ [CODE_AGENT] Scan failed: {scan_result['error']}")
                self.add_insight(f"Repository scan failed: {scan_result['error']}", confidence=0.3, source="scan_error")
                return "scan_failed"
            
            # Store discovered files for next step
            self.discovered_files = scan_result.get('files', [])
            self.file_summaries = {}  # Will store per-file LLM summaries
            self.directory_summaries = {}  # Will store per-directory summaries
            
            print(f"✅ [CODE_AGENT] Found {len(self.discovered_files)} files")
            
            # Add insight about repository structure
            if self.discovered_files:
                file_types = {}
                for f in self.discovered_files:
                    ext = f.get('extension', 'unknown')
                    file_types[ext] = file_types.get(ext, 0) + 1
                
                primary_type = max(file_types.items(), key=lambda x: x[1])[0] if file_types else 'unknown'
                self.add_insight(
                    f"Repository contains {len(self.discovered_files)} files, primarily {primary_type} files. File types: {dict(file_types)}",
                    confidence=0.8,
                    source="repository_scan"
                )
            
            return "scan_complete"
            
        except Exception as e:
            print(f"❌ [CODE_AGENT] Scan exception: {e}")
            self.add_insight(f"Repository scan error: {str(e)}", confidence=0.2, source="scan_exception")
            return "scan_failed"
    
    def _analyze_files_with_llm(self, question: str) -> str:
        """Step 2: Analyze each important file with LLM to generate per-file summaries"""
        try:
            if not hasattr(self, 'discovered_files') or not self.discovered_files:
                print(f"❌ [CODE_AGENT] No files to analyze")
                return "no_files_found"
            
            # Filter files for analysis (focus on source code)
            important_files = self._filter_important_files(self.discovered_files)
            print(f"📄 [CODE_AGENT] Analyzing {len(important_files)} important files...")
            
            analyzed_count = 0
            
            for file_info in important_files:  # Process all important files
                file_path = file_info.get('path', '')
                
                try:
                    print(f"📄 [CODE_AGENT] Analyzing file: {file_path}")
                    
                    # Start timing the file analysis flow
                    file_start_time = time.time()
                    
                    # Read file content - time this step
                    read_start_time = time.time()
                    file_result = self.use_tool('read_file', file_path=file_path, include_structure=True)
                    read_duration = time.time() - read_start_time
                    
                    if file_result.get('error'):
                        print(f"❌ [CODE_AGENT] Failed to read {file_path}: {file_result['error']}")
                        continue
                    
                    # Generate LLM summary for this file - time this step and capture tokens
                    llm_start_time = time.time()
                    file_summary, llm_metrics = self._generate_file_summary_with_llm(file_path, file_result, question)
                    llm_duration = time.time() - llm_start_time
                    
                    total_duration = time.time() - file_start_time
                    
                    # Log detailed metrics
                    metrics = {
                        'file_path': file_path,
                        'file_size_bytes': file_result.get('size', 0),
                        'file_lines': file_result.get('lines', 0),
                        'read_duration_ms': round(read_duration * 1000, 2),
                        'llm_duration_ms': round(llm_duration * 1000, 2),
                        'total_duration_ms': round(total_duration * 1000, 2),
                        'prompt_tokens': llm_metrics.get('prompt_tokens', 0),
                        'completion_tokens': llm_metrics.get('completion_tokens', 0),
                        'total_tokens': llm_metrics.get('total_tokens', 0),
                        'success': file_summary is not None
                    }
                    
                    self.file_analysis_metrics.append(metrics)
                    
                    # Print detailed per-file metrics
                    print(f"\n📊 [CODE_AGENT] Per-file metrics: {file_path}")  
                    print(f"   🛠️  Tool call (read_file): {read_duration*1000:.1f}ms")
                    print(f"   📖 File read time: {read_duration*1000:.1f}ms") 
                    print(f"   🤖 LLM summary generation: {llm_duration*1000:.1f}ms")
                    print(f"   ⏱️  Total file processing: {total_duration*1000:.1f}ms")
                    print(f"   🎯 Token usage: {llm_metrics.get('prompt_tokens', 0)} prompt → {llm_metrics.get('completion_tokens', 0)} completion = {llm_metrics.get('total_tokens', 0)} total")
                    print(f"   📄 File size: {file_result.get('size', 0)} bytes, {file_result.get('lines', 0)} lines")
                    print(f"   {'─' * 80}")
                    
                    if file_summary:
                        self.file_summaries[file_path] = file_summary
                        analyzed_count += 1
                        print(f"✅ [CODE_AGENT] Summarized {file_path}")
                        
                        # Add architectural insight for this file - focus on meaningful discoveries
                        architectural_insight = file_summary.get('architectural_insights', '')
                        if architectural_insight and architectural_insight != 'LLM analysis failed - manual review needed':
                            self.add_insight(
                                f"File {file_path}: {architectural_insight}",
                                confidence=0.8,
                                source=f"architectural_analysis_{file_path}"
                            )
                        elif file_summary.get('key_features') and len(file_summary['key_features']) > 0:
                            # Fallback to key features if architectural insights are missing
                            key_feature = file_summary['key_features'][0]
                            if key_feature and not any(generic in key_feature.lower() for generic in ['initializes', 'defines', 'contains', 'implements']):
                                self.add_insight(
                                    f"File {file_path}: {key_feature}",
                                    confidence=0.6,
                                    source=f"feature_analysis_{file_path}"
                                )
                        # Skip adding insights for files with no meaningful architectural discoveries
                    else:
                        print(f"❌ [CODE_AGENT] Failed to summarize {file_path}")
                    
                except Exception as e:
                    print(f"❌ [CODE_AGENT] Error analyzing {file_path}: {e}")
                    continue
            
            print(f"✅ [CODE_AGENT] Analyzed {analyzed_count} files successfully")
            
            # Print summary metrics
            if self.file_analysis_metrics:
                total_files = len(self.file_analysis_metrics)
                successful_files = len([m for m in self.file_analysis_metrics if m['success']])
                total_read_time = sum(m['read_duration_ms'] for m in self.file_analysis_metrics)
                total_llm_time = sum(m['llm_duration_ms'] for m in self.file_analysis_metrics)
                total_tokens = sum(m['total_tokens'] for m in self.file_analysis_metrics)
                total_prompt_tokens = sum(m['prompt_tokens'] for m in self.file_analysis_metrics)
                total_completion_tokens = sum(m['completion_tokens'] for m in self.file_analysis_metrics)
                
                print(f"\n📊 [CODE_AGENT] File Analysis Metrics Summary:")
                print(f"   📁 Files processed: {successful_files}/{total_files}")
                print(f"   ⏱️  Total read time: {total_read_time:.1f}ms")
                print(f"   🤖 Total LLM time: {total_llm_time:.1f}ms")
                print(f"   🎯 Total tokens: {total_tokens} ({total_prompt_tokens} → {total_completion_tokens})")
                print(f"   📈 Avg tokens/file: {total_tokens/successful_files:.0f}" if successful_files > 0 else "")
                print(f"   🚀 Avg LLM time/file: {total_llm_time/successful_files:.1f}ms" if successful_files > 0 else "")
            
            if analyzed_count > 0:
                self.add_insight(
                    f"Completed detailed analysis of {analyzed_count} important files with LLM-generated summaries",
                    confidence=0.8,
                    source="file_analysis_complete"
                )
                return "files_analyzed"
            else:
                return "no_files_analyzed"
                
        except Exception as e:
            print(f"❌ [CODE_AGENT] File analysis exception: {e}")
            return "file_analysis_failed"
    
    def _generate_directory_summaries(self, question: str) -> str:
        """Step 3: Generate per-directory summaries from file summaries"""
        try:
            if not hasattr(self, 'file_summaries') or not self.file_summaries:
                print(f"❌ [CODE_AGENT] No file summaries to aggregate")
                return "no_summaries_to_aggregate"
            
            # Group files by directory
            directory_files = {}
            for file_path, summary in self.file_summaries.items():
                directory = '/'.join(file_path.split('/')[:-1]) or 'root'
                if directory not in directory_files:
                    directory_files[directory] = []
                directory_files[directory].append({'file': file_path, 'summary': summary})
            
            print(f"📁 [CODE_AGENT] Generating summaries for {len(directory_files)} directories...")
            
            # Generate directory summaries with LLM
            for directory, files in directory_files.items():
                try:
                    print(f"📁 [CODE_AGENT] Summarizing directory: {directory}")
                    
                    dir_summary = self._generate_directory_summary_with_llm(directory, files, question)
                    
                    if dir_summary:
                        self.directory_summaries[directory] = dir_summary
                        
                        # Add architectural insight for this directory
                        patterns = dir_summary.get('patterns', [])
                        relationships = dir_summary.get('relationships', [])
                        
                        # Focus on architectural discoveries rather than file counts
                        if patterns and isinstance(patterns, list):
                            pattern_list = [str(p) for p in patterns[:2]]  # Top 2 patterns, ensure strings
                            pattern_text = ', '.join(pattern_list)
                            self.add_insight(
                                f"Directory {directory}: Implements {pattern_text}",
                                confidence=0.8,
                                source=f"directory_patterns_{directory}"
                            )
                        elif relationships:
                            relationship_text = relationships[0] if isinstance(relationships, list) else str(relationships)[:100]
                            self.add_insight(
                                f"Directory {directory}: {relationship_text}",
                                confidence=0.7,
                                source=f"directory_relationships_{directory}"
                            )
                        elif dir_summary.get('main_purpose') and 'source code' not in dir_summary['main_purpose'].lower():
                            # Only add purpose if it's not generic
                            self.add_insight(
                                f"Directory {directory}: {dir_summary['main_purpose']}",
                                confidence=0.6,
                                source=f"directory_purpose_{directory}"
                            )
                        # Skip directories with no meaningful architectural insights
                        
                        print(f"✅ [CODE_AGENT] Summarized directory: {directory}")
                
                except Exception as e:
                    print(f"❌ [CODE_AGENT] Error summarizing directory {directory}: {e}")
                    continue
            
            # Generate final architectural overview
            self._generate_architectural_overview(question)
            
            return "directory_summaries_complete"
            
        except Exception as e:
            print(f"❌ [CODE_AGENT] Directory summary exception: {e}")
            return "directory_summary_failed"
    
    def _filter_important_files(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter files for analysis - only analyze source code files, not documentation files"""
        
        processed_files = []
        
        # Get file extension lists from configuration
        repo_config = self.config.get('repo', {})
        source_code_extensions = set(repo_config.get('source_code_extensions', []))
        config_extensions = set(repo_config.get('config_extensions', []))
        doc_extensions = set(repo_config.get('documentation_extensions', []))
        
        print(f"🔍 [CODE_AGENT] Filtering files for source code analysis...")
        print(f"📋 [CODE_AGENT] Source code extensions: {sorted(source_code_extensions)}")
        print(f"⚙️ [CODE_AGENT] Config extensions: {sorted(config_extensions)}")
        print(f"📚 [CODE_AGENT] Documentation extensions (will skip): {sorted(doc_extensions)}")
        
        doc_files_skipped = 0
        
        for file_info in files:
            file_path = file_info.get('path', '')
            file_name = file_path.split('/')[-1]
            file_ext = file_info.get('extension', '').lower()
            
            # Skip test, spec, build, tutorial, example directories
            if any(skip in file_path.lower() for skip in [
                'test', 'spec', 'build', 'dist', '__pycache__', '.git', '.pyc', '.pyo',
                'tutorial', 'example', 'sample', 'demo', 'docs_src'
            ]):
                continue
            
            # Skip extremely large files
            if file_info.get('size', 0) > 200000:  # 200KB limit
                continue
            
            # Skip non-text files
            if not file_info.get('is_text', False):
                continue
                
            # SKIP documentation files - these should go to DocsAgent
            if file_ext in doc_extensions:
                doc_files_skipped += 1
                print(f"📄 [CODE_AGENT] Skipping documentation file: {file_path} (for DocsAgent)")
                continue
            
            # Accept source code files
            if file_ext in source_code_extensions:
                processed_files.append(file_info)
                print(f"🔧 [CODE_AGENT] Including source file: {file_path}")
                continue
                
            # Accept configuration files (relevant for architecture)
            if file_ext in config_extensions:
                processed_files.append(file_info)
                print(f"⚙️ [CODE_AGENT] Including config file: {file_path}")
                continue
                
            # Skip other file types
            print(f"❓ [CODE_AGENT] Skipping unknown file type: {file_path} ({file_ext})")
        
        if doc_files_skipped > 0:
            print(f"📚 [CODE_AGENT] Skipped {doc_files_skipped} documentation files (should be handled by DocsAgent)")
        
        print(f"🎯 [CODE_AGENT] Selected {len(processed_files)} source code files for analysis")
        
        # Sort by path for consistent processing order
        sorted_files = sorted(processed_files, key=lambda x: x.get('path', ''))
        
        # Apply configurable limit for performance control
        max_files = self.config.get('repo', {}).get('max_analysis_files', 50)
        if len(sorted_files) > max_files:
            print(f"⚡ [CODE_AGENT] Limiting to {max_files} files for performance (configurable in repo.max_analysis_files)")
            sorted_files = sorted_files[:max_files]
        
        return sorted_files
    
    def _generate_file_summary_with_llm(self, file_path: str, file_result: Dict[str, Any], question: str) -> tuple:
        """Generate LLM-powered summary for a single file with token metrics"""
        try:
            content = file_result.get('content', '')
            structure = file_result.get('structure_analysis', {})
            
            # Build prompt for file analysis with focus on architectural significance and technical detail
            prompt = f"""Analyze this source code file and provide detailed technical insights focused on architectural significance:

File: {file_path}
Content:
{content[:4000]}{"..." if len(content) > 4000 else ""}

Structure Info: {structure}

Provide a JSON response with:
- overview: What makes this file architecturally significant, its role in data/request flow, and technical approach
- purpose: The specific architectural role and how it fits in the overall system processing pipeline
- classes: Array of objects with "name", "methods" (key method names), and "role" (what it does in the flow)
- functions: Array of objects with "name", "signature" (parameters/return), and "purpose" (technical role in processing)
- key_features: Technical patterns, algorithms, data transformations, or design innovations
- dependencies: Critical imports that show integration points and architectural dependencies
- data_flow: How data enters this file, gets processed/transformed, and exits (input → processing → output)
- complexity: "low", "medium", or "high"
- architectural_insights: Technical patterns, system design, and how this file enables the overall architecture
- integration_points: How this file connects to other system components

Focus on technical implementation details, data flow, and specific classes/functions that drive the system.
Context: {question}"""

            system_prompt = "You are a software architecture expert. Focus on architectural significance, design patterns, and unique technical aspects. Avoid obvious descriptions. Provide insights in JSON format."
            
            response = self.call_llm(prompt, system_prompt)
            
            # Extract token metrics from the response
            llm_metrics = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0
            }
            
            if response.get('usage'):
                llm_metrics = {
                    'prompt_tokens': response['usage'].get('prompt_tokens', 0),
                    'completion_tokens': response['usage'].get('completion_tokens', 0),
                    'total_tokens': response['usage'].get('total_tokens', 0)
                }
            
            if response.get('success'):
                try:
                    content = response.get('content', '{}')
                    # Try to extract JSON from response
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        summary = json.loads(content[start:end])
                        return summary, llm_metrics
                except json.JSONDecodeError:
                    # Fallback to simple summary
                    fallback_summary = {
                        'overview': f"Analysis of {file_path}",
                        'purpose': 'Source code file',
                        'classes': [],
                        'functions': [],
                        'key_features': [content[:200]],
                        'dependencies': [],
                        'complexity': 'unknown',
                        'architectural_insights': 'LLM analysis failed - manual review needed'
                    }
                    return fallback_summary, llm_metrics
            
            return None, llm_metrics
            
        except Exception as e:
            print(f"❌ [CODE_AGENT] LLM file summary error for {file_path}: {e}")
            return None, {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    
    def _generate_directory_summary_with_llm(self, directory: str, files: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
        """Generate LLM-powered summary for a directory"""
        try:
            # Prepare file summaries for the directory
            file_summaries_text = []
            for file_info in files:
                file_path = file_info['file']
                summary = file_info['summary']
                file_summaries_text.append(f"- {file_path}: {summary.get('overview', 'No summary')}")
            
            prompt = f"""Analyze this directory and its files to provide a directory-level summary:

Directory: {directory}
Files in directory:
{chr(10).join(file_summaries_text)}

Provide a JSON response with:
- overview: What this directory contains and its role (1-2 sentences)
- main_purpose: The primary responsibility of this directory
- key_files: Most important files and why they're important
- patterns: Common patterns or architectural decisions
- relationships: How this directory relates to others

Focus on understanding this directory's role in answering: {question}"""

            system_prompt = "You are a software architecture expert. Analyze directory structures and provide architectural insights in JSON format."
            
            response = self.call_llm(prompt, system_prompt)
            
            if response.get('success'):
                try:
                    content = response.get('content', '{}')
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        summary = json.loads(content[start:end])
                        return summary
                except json.JSONDecodeError:
                    pass
            
            # Fallback summary
            return {
                'overview': f"Directory {directory} contains {len(files)} analyzed files",
                'main_purpose': 'Source code organization',
                'key_files': [f['file'] for f in files[:3]],
                'patterns': [],
                'relationships': []
            }
            
        except Exception as e:
            print(f"❌ [CODE_AGENT] LLM directory summary error for {directory}: {e}")
            return None
    
    def _generate_architectural_overview(self, question: str):
        """Generate final architectural overview from all summaries"""
        try:
            if not self.directory_summaries:
                return
            
            # Create architectural insight
            directories = list(self.directory_summaries.keys())
            total_files = sum(len(self.file_summaries) for _ in self.directory_summaries)
            
            architectural_summary = f"Repository architecture: {len(directories)} main directories analyzed, {total_files} files processed. "
            architectural_summary += f"Key directories: {', '.join(directories[:5])}"
            
            self.add_insight(
                architectural_summary,
                confidence=0.9,
                source="architectural_overview"
            )
            
        except Exception as e:
            print(f"❌ [CODE_AGENT] Architectural overview error: {e}")
    
    def _ensure_repository_structure_cached(self) -> str:
        """Ensure repository structure is cached with tree + flat map"""
        cache_key = f"repo_structure_{self.repo_path}"
        
        # Check cached structure
        cached_structure = None
        if hasattr(self, 'cache') and self.cache:
            cached_structure = self.cache.get(cache_key)
        
        # Check if refresh needed
        if not cached_structure or self._needs_structure_refresh(cached_structure):
            print(f"🏗️ [CODE_AGENT] Building repository structure...")
            structure = self._build_repository_structure()
            
            # Cache the structure
            if hasattr(self, 'cache') and self.cache:
                self.cache.set(cache_key, structure)
        else:
            print(f"✅ [CODE_AGENT] Using cached repository structure")
            structure = cached_structure
        
        # Load into instance variables
        self.repo_tree = structure['tree']
        self.path_map = structure['path_map'] 
        
        return "structure_ready"
    
    def _needs_structure_refresh(self, cached_structure: dict) -> bool:
        """Check if structure needs refresh"""
        cached_timestamp = cached_structure.get('timestamp', 0)
        current_mtime = os.path.getmtime(self.repo_path)
        return current_mtime > cached_timestamp
    
    def _build_repository_structure(self) -> dict:
        """Build both tree structure and flat path map"""
        excluded_dirs = set(self.config.get('repo', {}).get('excluded_dirs', []))
        text_extensions = set(self.config.get('repo', {}).get('text_extensions', []))
        
        tree = {}
        path_map = {}  # flat map: path -> metadata
        
        def process_path(path: str, parent_tree: dict):
            name = os.path.basename(path)
            stat = os.stat(path)
            is_dir = os.path.isdir(path)
            
            # Add to flat map
            rel_path = os.path.relpath(path, self.repo_path)
            path_map[rel_path] = {
                'last_modified_time': stat.st_mtime,
                'is_dir': is_dir,
                'size': stat.st_size if not is_dir else 0,
                'extension': os.path.splitext(path)[1].lower() if not is_dir else '',
                'is_text': os.path.splitext(path)[1].lower() in text_extensions if not is_dir else False
            }
            
            # Add to tree
            parent_tree[name] = {
                'is_dir': is_dir,
                'children': {} if is_dir else None
            }
            
            # Recurse for directories
            if is_dir:
                try:
                    for child_name in os.listdir(path):
                        if child_name.startswith('.') or child_name in excluded_dirs:
                            continue
                        child_path = os.path.join(path, child_name)
                        process_path(child_path, parent_tree[name]['children'])
                except PermissionError:
                    pass
        
        # Build from root
        for item in os.listdir(self.repo_path):
            if item.startswith('.') or item in excluded_dirs:
                continue
            item_path = os.path.join(self.repo_path, item)
            process_path(item_path, tree)
        
        return {
            'tree': tree,
            'path_map': path_map,
            'timestamp': time.time()
        }
    
    def _question_focused_file_analysis(self, question: str) -> str:
        """Pass 1: Question-focused file discovery and analysis"""
        # Initialize analysis state
        self.file_summaries = {}
        self.directory_summaries = {}
        self.discovered_files = []  # Only files discovered through question-focused search
        
        print(f"🎯 [CODE_AGENT] Starting question-focused analysis: {question}")
        
        # Step 1: Let LLM determine search strategy based on question
        search_strategy = self._determine_search_strategy(question)
        if not search_strategy:
            # Fallback to default strategy when LLM fails
            print(f"🔄 [CODE_AGENT] Using fallback search strategy")
            search_strategy = self._get_fallback_strategy(question)
        
        # Step 2: Execute targeted file discovery based on strategy
        relevant_files = self._execute_targeted_discovery(search_strategy)
        if not relevant_files:
            return "no_relevant_files_found"
        
        # Step 3: Analyze only the discovered relevant files
        return self._analyze_relevant_files(relevant_files, question)
    
    def _determine_search_strategy(self, question: str) -> dict:
        """Use LLM to determine what files/patterns to look for based on question"""
        try:
            # Get high-level repository overview for context
            repo_overview = self._get_repository_overview()
            
            prompt = f"""Based on this question about a codebase: "{question}"

Repository overview:
{repo_overview}

You must find the CORE IMPLEMENTATION SOURCE CODE files (not documentation, tutorials, or examples) to answer this question.

EXCLUDE these directories from your search:
- Documentation: docs/, documentation/ 
- Examples/Tutorials: examples/, tutorials/, docs_src/, sample/, demo/
- Tests: tests/, test/, spec/, __tests__/
- Build artifacts: build/, dist/, target/, out/

FOCUS ON finding core implementation files:
- Request processing → routing, controllers, handlers, middleware, requests, responses
- Web frameworks → main app files, routing, middleware, responses, exceptions, dependencies  
- API frameworks → controllers, handlers, routing, serializers, validators
- Core logic → main, app, core, service, base, index files

For "{question}" - search for framework CORE FILES only.

Determine the search strategy to find relevant CORE SOURCE CODE files. Respond with JSON:
{{
    "keywords": ["routing", "controller", "handler", "middleware"],
    "file_patterns": ["*routing*", "*controller*", "*handler*", "*middleware*", "main*", "app*"],
    "directories": ["src/", "lib/", "app/", "framework_name/"],
    "search_terms": ["class", "function", "def", "async def"],
    "strategy": "focused"
}}

CRITICAL: 
- Target core implementation files only
- Avoid tutorial, example, and test directories  
- Focus on the main framework/library source code"""
            
            response = self.llm.generate(prompt, "You are a code analysis expert. Determine optimal search strategy.")
            
            if response.get('success'):
                content = response.get('content', '').strip()
                if content and content != "Hello! How can I assist you today?":
                    try:
                        # Try to find JSON in the response
                        start = content.find('{')
                        end = content.rfind('}') + 1
                        if start >= 0 and end > start:
                            json_content = content[start:end]
                            strategy = json.loads(json_content)
                            print(f"🔍 [CODE_AGENT] Search strategy: {strategy.get('strategy', 'unknown')}")
                            return strategy
                    except json.JSONDecodeError:
                        pass
                
                print(f"⚠️ [CODE_AGENT] Invalid LLM response: {content[:100]}...")
            
        except Exception as e:
            print(f"⚠️ [CODE_AGENT] Strategy determination failed: {e}")
        
        return None
    
    def _get_fallback_strategy(self, question: str) -> dict:
        """Generate fallback search strategy based on question keywords"""
        question_lower = question.lower()
        
        # Extract keywords from question
        keywords = []
        patterns = []
        directories = []
        search_terms = []
        
        # Framework-specific patterns (FastAPI, Django, Flask, etc.)
        framework_detected = False
        if 'fastapi' in question_lower:
            keywords.extend(['applications', 'routing', 'requests', 'middleware', 'responses'])
            patterns.extend(['applications.py', 'routing.py', 'requests.py', '*middleware*'])
            directories.extend(['fastapi/', 'middleware/', 'security/'])
            framework_detected = True
        
        # Common programming concepts and their file patterns
        if 'request' in question_lower or 'http' in question_lower:
            keywords.extend(['request', 'http', 'handler', 'route'])
            patterns.extend(['*request*', '*handler*', '*route*', 'routing.py', 'applications.py'])
            search_terms.extend(['request', 'handler', 'route'])
        
        if 'processing' in question_lower or 'process' in question_lower:
            keywords.extend(['process', 'middleware', 'pipeline'])
            patterns.extend(['*process*', '*middleware*', 'routing.py', 'applications.py'])
            search_terms.extend(['process', 'middleware'])
        
        if 'authentication' in question_lower or 'auth' in question_lower:
            keywords.extend(['auth', 'login', 'security'])
            patterns.extend(['*auth*', '*security*'])
            directories.extend(['auth/', 'security/'])
        
        if 'routing' in question_lower or 'route' in question_lower:
            keywords.extend(['route', 'router', 'endpoint', 'routing'])
            patterns.extend(['*route*', '*router*', 'routing.py', 'applications.py'])
            search_terms.extend(['route', 'router'])
        
        # Default patterns for general code exploration - include common framework files
        if not keywords:
            keywords = ['main', 'app', 'core', 'base', 'applications', 'routing']
            patterns = ['main*', 'app*', '*core*', 'applications.py', 'routing.py']
        
        # Always add core framework directories for broader coverage
        if framework_detected or any(fw in question_lower for fw in ['fastapi', 'django', 'flask', 'express']):
            directories.extend(['src/', 'lib/', 'core/', 'app/'])
        
        return {
            'keywords': keywords,  # No arbitrary limits - let LLM decide scope
            'file_patterns': patterns,  # No arbitrary limits
            'directories': directories,
            'search_terms': search_terms,
            'strategy': 'focused'
        }
    
    def _get_repository_overview(self) -> str:
        """Get brief repository overview from cached structure"""
        if not hasattr(self, 'repo_tree'):
            return "Repository structure not available"
        
        # Get top-level directories and file types
        top_dirs = list(self.repo_tree.keys())[:10]
        
        # Get file type distribution from path_map
        file_types = {}
        for path, metadata in self.path_map.items():
            if not metadata['is_dir']:
                ext = metadata['extension']
                file_types[ext] = file_types.get(ext, 0) + 1
        
        overview = f"Top directories: {', '.join(top_dirs)}\n"
        overview += f"File types: {dict(list(file_types.items())[:5])}"
        return overview
    
    def _execute_targeted_discovery(self, strategy: dict) -> list:
        """Execute targeted file discovery based on search strategy"""
        relevant_files = []
        
        try:
            # Search by keywords in file paths
            keywords = strategy.get('keywords', [])
            for keyword in keywords:
                matching_files = self._find_files_by_keyword(keyword)
                relevant_files.extend(matching_files)
            
            # Search by file patterns
            patterns = strategy.get('file_patterns', [])
            for pattern in patterns:
                matching_files = self._find_files_by_pattern(pattern)
                relevant_files.extend(matching_files)
            
            # Search in specific directories
            directories = strategy.get('directories', [])
            for directory in directories:
                dir_files = self._find_files_in_directory(directory)
                relevant_files.extend(dir_files)
            
            # Search by content if search terms provided
            search_terms = strategy.get('search_terms', [])
            if search_terms:
                content_files = self._find_files_by_content(search_terms)
                relevant_files.extend(content_files)
            
            # Remove duplicates - let LLM strategy determine scope, not hardcoded limits
            unique_files = list({f['path']: f for f in relevant_files}.values())
            
            print(f"📁 [CODE_AGENT] Found {len(unique_files)} relevant files")
            return unique_files
            
        except Exception as e:
            print(f"❌ [CODE_AGENT] Targeted discovery failed: {e}")
            return []
    
    def _find_files_by_keyword(self, keyword: str) -> list:
        """Find files containing keyword in path"""
        matching_files = []
        for path, metadata in self.path_map.items():
            if not metadata['is_dir'] and keyword.lower() in path.lower():
                matching_files.append({
                    'path': path,
                    'size': metadata['size'],
                    'extension': metadata['extension'],
                    'is_text': metadata['is_text']
                })
        return matching_files
    
    def _find_files_by_pattern(self, pattern: str) -> list:
        """Find files matching pattern (simplified glob-like)"""
        matching_files = []
        for path, metadata in self.path_map.items():
            if not metadata['is_dir'] and fnmatch.fnmatch(path, pattern):
                matching_files.append({
                    'path': path,
                    'size': metadata['size'],
                    'extension': metadata['extension'],
                    'is_text': metadata['is_text']
                })
        return matching_files
    
    def _find_files_in_directory(self, directory: str) -> list:
        """Find files in specific directory"""
        matching_files = []
        for path, metadata in self.path_map.items():
            if not metadata['is_dir'] and path.startswith(directory):
                matching_files.append({
                    'path': path,
                    'size': metadata['size'],
                    'extension': metadata['extension'],
                    'is_text': metadata['is_text']
                })
        return matching_files
    
    def _find_files_by_content(self, search_terms: list) -> list:
        """Find files containing search terms (uses existing search_files tool)"""
        try:
            all_matches = []
            for term in search_terms:
                search_result = self.use_tool('search_files', pattern=term, max_results=50)
                if search_result.get('matches'):
                    for match in search_result['matches']:
                        file_path = match.get('file', '')
                        if file_path in self.path_map:
                            metadata = self.path_map[file_path]
                            all_matches.append({
                                'path': file_path,
                                'size': metadata['size'],
                                'extension': metadata['extension'],
                                'is_text': metadata['is_text']
                            })
            return all_matches
        except Exception as e:
            print(f"⚠️ [CODE_AGENT] Content search failed: {e}")
            return []
    
    def _analyze_relevant_files(self, relevant_files: list, question: str) -> str:
        """Analyze only the relevant files discovered through question-focused search"""
        self.discovered_files = relevant_files  # Set for compatibility with existing code
        
        # Apply filtering to ensure we only analyze source code files, not documentation
        filtered_files = self._filter_important_files(relevant_files)
        
        if len(filtered_files) != len(relevant_files):
            skipped_count = len(relevant_files) - len(filtered_files)
            print(f"📚 [CODE_AGENT] Filtered out {skipped_count} documentation files from question-focused discovery")
        
        # Reuse existing file analysis logic with metrics
        return self._analyze_files_with_metrics(filtered_files, question, "relevant file")
    
    def _analyze_files_with_metrics(self, files_to_analyze: list, question: str, file_type: str = "file") -> str:
        """Analyze files with comprehensive metrics tracking using repo tools"""
        print(f"📄 [CODE_AGENT] Analyzing {len(files_to_analyze)} {file_type}s...")
        
        # Initialize metrics tracking using repo tools
        if not hasattr(self, 'file_analysis_metrics'):
            self.file_analysis_metrics = []
        
        analyzed_count = 0
        
        for file_info in files_to_analyze:
            file_path = file_info.get('path', '')
            
            try:
                print(f"📄 [CODE_AGENT] Analyzing {file_type}: {file_path}")
                
                # Start metrics tracking using repo tools
                file_metrics = self.tools.repo_tools.start_file_analysis_metrics(file_path)
                
                # Read file content - track timing
                file_metrics['read_start_time'] = time.time()
                file_result = self.use_tool('read_file', file_path=file_path, include_structure=True)
                file_metrics = self.tools.repo_tools.track_file_read_metrics(file_metrics, file_result)
                
                if file_result.get('error'):
                    print(f"❌ [CODE_AGENT] Failed to read {file_path}: {file_result['error']}")
                    file_metrics = self.tools.repo_tools.finalize_file_metrics(file_metrics, success=False)
                    self.file_analysis_metrics.append(file_metrics)
                    continue
                
                # Generate LLM summary - track timing and tokens
                file_metrics['llm_start_time'] = time.time()
                file_summary, llm_metrics = self._generate_file_summary_with_llm(file_path, file_result, question)
                file_metrics = self.tools.repo_tools.track_llm_metrics(file_metrics, llm_metrics)
                
                # Finalize metrics
                file_metrics = self.tools.repo_tools.finalize_file_metrics(file_metrics, success=file_summary is not None)
                self.file_analysis_metrics.append(file_metrics)
                
                # Print per-file metrics using repo tools
                self.tools.repo_tools.print_file_metrics(file_metrics)
                
                if file_summary:
                    self.file_summaries[file_path] = file_summary
                    analyzed_count += 1
                    print(f"✅ [CODE_AGENT] Summarized {file_path}")
                    
                    # Add architectural insights
                    architectural_insight = file_summary.get('architectural_insights', '')
                    if architectural_insight and architectural_insight != 'LLM analysis failed - manual review needed':
                        self.add_insight(
                            f"File {file_path}: {architectural_insight}",
                            confidence=0.8,
                            source=f"question_focused_analysis_{file_path}"
                        )
                    elif file_summary.get('key_features') and len(file_summary['key_features']) > 0:
                        # Fallback to key features if architectural insights are missing
                        key_feature = file_summary['key_features'][0]
                        if key_feature and not any(generic in key_feature.lower() for generic in ['initializes', 'defines', 'contains', 'implements']):
                            self.add_insight(
                                f"File {file_path}: {key_feature}",
                                confidence=0.6,
                                source=f"feature_analysis_{file_path}"
                            )
                else:
                    print(f"❌ [CODE_AGENT] Failed to summarize {file_path}")
                    
            except Exception as e:
                print(f"❌ [CODE_AGENT] Error analyzing {file_path}: {e}")
                # Ensure metrics are finalized even on error
                if 'file_metrics' in locals():
                    file_metrics = self.tools.repo_tools.finalize_file_metrics(file_metrics, success=False)
                    self.file_analysis_metrics.append(file_metrics)
                continue
        
        print(f"✅ [CODE_AGENT] Analyzed {analyzed_count} files successfully")
        
        # Print summary metrics using repo tools
        self.tools.repo_tools.print_summary_metrics(self.file_analysis_metrics, "CODE_AGENT")
        
        if analyzed_count > 0:
            self.add_insight(
                f"Question-focused analysis completed: {analyzed_count} relevant files analyzed",
                confidence=0.9,
                source="question_focused_complete"
            )
            return "question_focused_analysis_complete"
        else:
            return "no_files_analyzed"
    
    def _generate_module_summaries(self, question: str) -> str:
        """Pass 2: Generate per-module summaries using file summaries as input"""
        return self._generate_directory_summaries(question)
    
    def _generate_project_feature_flows(self, question: str) -> str:
        """Pass 3: Generate project-level feature flows - use LLM with tool calls"""
        # Initialize conversation with context from previous passes
        self._initialize_feature_flow_conversation(question)
        # Let LLM determine question type and generate appropriate response using available tools
        return self._run_function_calling_loop()
    
    def _initialize_feature_flow_conversation(self, question: str):
        """Initialize conversation for feature flow analysis with context"""
        
        # Build detailed context from previous passes
        context_parts = []
        
        # Add detailed file analysis context
        if hasattr(self, 'file_summaries') and self.file_summaries:
            context_parts.append(f"=== ANALYZED FILES ({len(self.file_summaries)} files) ===")
            for file_path, summary in self.file_summaries.items():
                context_parts.append(f"**{file_path}**:")
                context_parts.append(f"  - Purpose: {summary.get('purpose', 'Unknown')}")
                context_parts.append(f"  - Overview: {summary.get('overview', 'No overview')}")
                if summary.get('architectural_insights'):
                    context_parts.append(f"  - Architecture: {summary.get('architectural_insights')}")
                if summary.get('classes'):
                    classes = summary.get('classes', [])
                    if isinstance(classes, list) and len(classes) > 0:
                        class_names = [str(c.get('name', c)) if isinstance(c, dict) else str(c) for c in classes[:3]]
                        context_parts.append(f"  - Key Classes: {', '.join(class_names)}")
                if summary.get('functions'):
                    functions = summary.get('functions', [])
                    if isinstance(functions, list) and len(functions) > 0:
                        func_names = [str(f.get('name', f)) if isinstance(f, dict) else str(f) for f in functions[:3]]
                        context_parts.append(f"  - Key Functions: {', '.join(func_names)}")
            context_parts.append("")
            
        # Add directory analysis context
        if hasattr(self, 'directory_summaries') and self.directory_summaries:
            context_parts.append(f"=== MODULE ANALYSIS ({len(self.directory_summaries)} directories) ===")
            for directory, summary in self.directory_summaries.items():
                context_parts.append(f"**{directory}/ directory**:")
                context_parts.append(f"  - Purpose: {summary.get('main_purpose', 'Unknown')}")
                context_parts.append(f"  - Overview: {summary.get('overview', 'No overview')}")
                if summary.get('patterns'):
                    patterns = summary.get('patterns', [])
                    if isinstance(patterns, list) and len(patterns) > 0:
                        context_parts.append(f"  - Patterns: {', '.join(patterns[:3])}")
                if summary.get('relationships'):
                    relationships = summary.get('relationships', [])
                    if isinstance(relationships, list) and len(relationships) > 0:
                        context_parts.append(f"  - Relationships: {relationships[0]}")
                    elif isinstance(relationships, str):
                        context_parts.append(f"  - Relationships: {relationships}")
            context_parts.append("")
        
        # Add key insights
        if self.insights:
            context_parts.append(f"=== KEY INSIGHTS ({len(self.insights)} insights) ===")
            for insight in self.insights[:10]:  # Top 10 insights
                context_parts.append(f"- {insight.get('content', 'No content')} (confidence: {insight.get('confidence', 0)*100:.0f}%)")
            context_parts.append("")
        
        context = "\n".join(context_parts) if context_parts else "Previous analysis completed"
        
        system_message = {
            "role": "system",
            "content": f"""You are a software architecture expert answering: "{question}"

ANALYZED CODEBASE CONTEXT:
{context}

CRITICAL INSTRUCTIONS:
1. **USE ONLY THE ANALYZED CODE ABOVE** - Do not provide generic explanations about frameworks or libraries
2. **Reference specific files** from the analysis with their actual paths and names
3. **Connect architectural insights** from the analyzed files to answer the question
4. **Build on the module analysis** to show how directories work together
5. **Use the key insights** to highlight important architectural patterns discovered

**Response Format for "{question}":**

**OVERVIEW & NARRATIVE** (2-3 detailed paragraphs):
- What this codebase is, its core purpose, and architectural philosophy
- **COMPLETE TECHNICAL FLOW** - trace data/request journey from start to finish with technical detail:
  * Entry points: Which specific files/classes initiate the process
  * Data transformation pipeline: How data flows between components and gets transformed
  * Component interactions: Which classes call which methods and how they coordinate
  * Completion mechanisms: How the process finalizes and what patterns enable scalability

**IMPLEMENTATION DETAILS** - Connect concepts to specific analyzed code with technical depth:
- **Step 1: [Process Name/Entry Point]**
  * **What**: Technical description of what happens (initialization, setup, etc.)
  * **Where**: `specific_file.py` → `Class.method()` with exact class/function names from analysis
  * **How**: Implementation approach, key algorithms, data structures used
  * **Classes/Functions**: List specific classes and methods that handle this step
  * **Data Flow**: What data enters, how it's processed, what gets passed to next step

- **Step 2: [Next Process/Transformation]** 
  * **What**: Next phase technical description (processing, middleware, etc.)
  * **Where**: `module/file.py` → specific classes and their methods
  * **How**: Concrete implementation details and integration mechanisms
  * **Classes/Functions**: Key components with their roles and responsibilities
  * **Data Flow**: How data transforms and moves through this stage

- **Step 3: [Final Process/Output]**
  * **What**: Final phase technical operations (response generation, cleanup, etc.)
  * **Where**: Final classes/functions from analysis with method signatures
  * **How**: How everything connects, error handling, and completion logic
  * **Classes/Functions**: Terminal components and their specific behaviors
  * **Data Flow**: Final data transformations and output generation

Continue with **Step 4, Step 5**, etc. as needed based on the complexity of the system being analyzed.

REQUIREMENTS:
- Reference ONLY files from the analysis above
- Use architectural insights and patterns discovered
- **INCLUDE SPECIFIC CLASS/FUNCTION NAMES** from the file analysis (e.g., `ClassName.method()`, `function_name()`)
- **SHOW DATA/REQUEST FLOW** through specific components with technical detail
- Show how the analyzed files and modules work together with class-level detail
- Connect module summaries to the overall flow using specific method calls and data transformations
- Include confidence levels from insights where relevant
- **USE THE ENHANCED TECHNICAL DETAILS**: data_flow, integration_points, classes with methods, functions with signatures

DO NOT: 
- Provide generic framework documentation
- Use vague descriptions like "handles data" - be specific about which classes/methods
- Skip the technical flow details - show the actual data journey
USE ONLY THE SPECIFIC CODE ANALYSIS PROVIDED WITH TECHNICAL DEPTH."""
        }
        
        user_message = {
            "role": "user", 
            "content": f"Based on the code analysis, please explain: {question}"
        }
        
        self.conversation_history = [system_message, user_message]
