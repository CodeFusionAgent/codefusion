"""
CodeAgent for CodeFusion

Simple LLM-driven specialist agent that uses function calling to analyze code.
"""

import os
import time
import json
import fnmatch
import traceback
from pathlib import Path

from typing import Dict, List, Any
from cf.agents.base import BaseAgent
from cf.cache.file_summary_cache import FileSummaryCache



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

        # Initialize repository structure variables
        self.repo_tree = {}
        self.path_map = {}
        self.discovered_files = []
        self.file_summaries = {}
        self.directory_summaries = {}

        # OPTIMIZATION: Initialize file summary cache for warm starts
        cache_config = config.get('cache', {})

        # File summary cache has its own config (separate from semantic cache)
        file_cache_config = cache_config.get('file_summary_cache', {})
        file_cache_enabled = file_cache_config.get('enabled', True)
        file_cache_ttl = file_cache_config.get('ttl', 3600)

        cache_dir = cache_config.get('cache_dir', 'cf_cache')
        self.file_cache = FileSummaryCache(f"{cache_dir}/file_summaries", ttl=file_cache_ttl)

        if not file_cache_enabled:
            self.file_cache.disable()
            print("⚠️ [CODE_AGENT] File summary cache is DISABLED")
        else:
            print(f"✅ [CODE_AGENT] File summary cache ENABLED (TTL: {file_cache_ttl}s, dir: {cache_dir}/file_summaries)")
    
    def _analyze_step(self, question: str) -> str:
        """Execute one ReAct step: Reason -> Act -> Observe"""

        # REASON: Determine what to do next based on current state
        reasoning = self._reason_about_next_action(question)
        self.logger.verbose_action("🧠 REASONING PHASE", reasoning)
        print(f"🧠 [CODE_AGENT] Reasoning: {reasoning}")

        # ACT: Execute the decided action
        action_result = self._execute_reasoned_action(reasoning, question)
        self.logger.verbose_action("🎯 ACTION PHASE", f"Executed: {action_result}")
        print(f"🎯 [CODE_AGENT] Action result: {action_result}")

        # OBSERVE: Process results and update state
        observation = self._observe_action_results(action_result, question)
        self.logger.verbose_action("👁️ OBSERVATION PHASE", observation)
        print(f"👁️ [CODE_AGENT] Observation: {observation}")

        return action_result
    
    def _reason_about_next_action(self, question: str) -> str:
        """Use LLM to reason about what action to take next"""

        # Build current state summary
        state_summary = self._build_state_summary(question)

        reasoning_prompt = f"""You are analyzing a codebase to answer: "{question}"

CRITICAL: Your answer MUST be grounded in the ACTUAL CODEBASE, not just conceptual knowledge. Even for "why" questions about design decisions, you must analyze the actual implementation files to show HOW the code demonstrates that design.

Current State:
- Iteration: {self.iteration}/{self.max_iterations}
- Insights gathered: {len(self.insights)}
- Files analyzed: {len(getattr(self, 'file_summaries', {}))}
- Tool calls made: {len(self.tool_results)}

{state_summary}

Based on this state, what should we do next to answer the question? Consider:
1. Do we need to discover more files? (scan or search) - START HERE if no files analyzed yet
2. Do we need to read specific files for details?
3. Do we need to analyze code structure or patterns?
4. Do we have enough information to generate a comprehensive, codebase-grounded answer?

IMPORTANT: If you haven't analyzed any files yet (iteration 1, files analyzed = 0), you MUST start by discovering relevant files through scanning or searching. Never skip file analysis.

Provide reasoning in 2-3 sentences about the next best action."""

        system_prompt = "You are a code analysis expert using the ReAct framework. Reason about what action to take next."

        response = self.call_llm(reasoning_prompt, system_prompt)

        if response.get('success'):
            return response.get('content', 'Continue analysis')
        else:
            return "Continue with standard analysis approach"

    def _build_state_summary(self, question: str) -> str:
        """Build a summary of current analysis state"""
        summary_parts = []

        if hasattr(self, 'file_summaries') and self.file_summaries:
            summary_parts.append(f"Analyzed {len(self.file_summaries)} files:")
            for path in list(self.file_summaries.keys())[:3]:
                summary_parts.append(f"  - {path}")
            if len(self.file_summaries) > 3:
                summary_parts.append(f"  ... and {len(self.file_summaries) - 3} more")

        if self.insights:
            summary_parts.append(f"\nKey insights gathered:")
            for insight in self.insights[-3:]:
                summary_parts.append(f"  - {insight.get('content', '')[:80]}")

        if self.tool_results:
            recent_tools = [r['tool'] for r in self.tool_results[-3:]]
            summary_parts.append(f"\nRecent tools used: {', '.join(recent_tools)}")

        return "\n".join(summary_parts) if summary_parts else "No analysis performed yet"

    def _execute_reasoned_action(self, reasoning: str, question: str) -> str:
        """Execute action based on reasoning"""
        reasoning_lower = reasoning.lower()

        # Ensure repository structure is cached first if we need it
        if not self.path_map and ('search' in reasoning_lower or 'discover' in reasoning_lower or
                                   'find' in reasoning_lower or 'scan' in reasoning_lower):
            self._ensure_repository_structure_cached()

        # Parse reasoning to determine action
        # Priority 1: If no files analyzed yet and reasoning mentions discovering files, do file analysis
        if (self.iteration == 1 or len(self.file_summaries) == 0) and (
            'search' in reasoning_lower or 'discover' in reasoning_lower or
            'find' in reasoning_lower or 'scan' in reasoning_lower
        ):
            return self._question_focused_file_analysis(question)

        elif 'scan' in reasoning_lower and self.iteration == 1:
            return self._scan_repository_structure(question)

        elif 'read' in reasoning_lower or 'analyze files' in reasoning_lower or 'examine' in reasoning_lower:
            if not self.file_summaries:
                return self._question_focused_file_analysis(question)
            return "files_already_analyzed"

        elif 'structure' in reasoning_lower or 'pattern' in reasoning_lower or 'architecture' in reasoning_lower:
            return self._generate_module_summaries(question)

        elif 'enough' in reasoning_lower or 'sufficient' in reasoning_lower or 'answer' in reasoning_lower:
            return "ready_for_answer_generation"

        else:
            # Default: use function calling loop for intelligent tool selection
            return self._run_function_calling_loop()

    def _observe_action_results(self, action_result: str, question: str) -> str:
        """Observe and interpret the results of the action"""

        if 'scan_complete' in action_result:
            files_found = len(getattr(self, 'discovered_files', []))
            return f"Repository scanned: {files_found} files discovered"

        elif 'analysis_complete' in action_result:
            analyzed = len(getattr(self, 'file_summaries', {}))
            return f"File analysis complete: {analyzed} files processed, {len(self.insights)} insights gathered"

        elif 'ready_for_answer' in action_result:
            return f"Sufficient information gathered ({len(self.insights)} insights). Ready to generate comprehensive answer."

        elif 'function_calling_complete' in action_result:
            calls = action_result.split('_')[-2] if '_' in action_result else '0'
            return f"LLM function calling completed after {calls} tool calls"

        else:
            return f"Action completed: {action_result}"

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
        print("[CODE_AGENT] Running function calling loop...")
        max_function_calls = 12  # Hard limit for code analysis
        function_calls_made = 0
        
        # Get available tools for function calling
        available_tools = self.tools.get_all_schemas()
        
        self.logger.verbose_progress("Using LLM function calling for intelligent tool selection", "🔧")
        self.logger.debug(f"Retrieved {len(available_tools)} tool schemas from registry")
        print(f"[CODE_AGENT] Retrieved {len(available_tools)} tool schemas from registry")
        while function_calls_made < max_function_calls:
            try:
                self.logger.debug(f"Function call iteration {function_calls_made + 1}/{max_function_calls}")
                print(f"[CODE_AGENT] Function call iteration {function_calls_made + 1}/{max_function_calls}")
                
                # Get LLM response with function calling
                self.logger.verbose_progress("Calling LLM with function calling enabled...", "📡")
                print(f"[CODE_AGENT] Calling LLM with function calling enabled...")
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
                    print(f"[CODE_AGENT] Executing tool {tool_name} with params: {tool_params}")
                    tool_result = self.use_tool(tool_name, **tool_params)
                    self.logger.debug(f"Tool result success: {not tool_result.get('error')}")
                    print(f"[CODE_AGENT] Tool result success: {not tool_result.get('error')}")
                    
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
                print(f"[CODE_AGENT] Function calling loop error: {traceback.print_exc()}")
                thresholds = self.config.get('agents', {}).get('thresholds', {})
                self.add_insight(
                    f"Function calling loop error: {str(e)}",
                    confidence=thresholds.get('error_confidence', 0.2),
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
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            preview_length = thresholds.get('content_preview_length', 3000)
            preview = content[:preview_length] + ("..." if len(content) > preview_length else "")
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
                thresholds = self.config.get('agents', {}).get('thresholds', {})
                self.add_insight(
                    f"Codebase contains {len(files)} files, primarily {primary_type} files",
                    confidence=thresholds.get('high_confidence', 0.8),
                    source="directory_scan"
                )
        
        elif tool_name == 'search_files':
            matches = result.get('matches', [])
            if matches:
                files = list(set([m.get('file', '') for m in matches]))
                self.add_insight(
                    f"Found {len(matches)} relevant code matches in {len(files)} files",
                    confidence=self.get_confidence('medium'),
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
            
            self.add_insight(insight_text, confidence=self.get_confidence('high'), source="structure_analysis")
        
        elif tool_name == 'extract_functions':
            functions = result.get('functions', [])
            if functions:
                func_names = [f.get('name', '') for f in functions[:5]]
                self.add_insight(
                    f"Key functions: {', '.join(func_names)}",
                    confidence=self.get_confidence('medium'),
                    source="function_analysis"
                )
        
        elif tool_name == 'extract_classes':
            classes = result.get('classes', [])
            if classes:
                class_names = [c.get('name', '') for c in classes[:5]]
                self.add_insight(
                    f"Key classes: {', '.join(class_names)}",
                    confidence=self.get_confidence('medium'),
                    source="class_analysis"
                )
    
    def _is_analysis_complete(self, question: str) -> bool:
        """Check if we have enough information to answer the question comprehensively"""

        # Must have gathered some insights
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        min_insights = thresholds.get('min_insights_for_synthesis', 2)
        if len(self.insights) < min_insights:
            return False

        # Check if last action indicated readiness
        if self.actions_taken and 'ready_for_answer' in self.actions_taken[-1]:
            return True

        # CACHE-AWARE EARLY STOPPING: Adjust thresholds based on cache status
        files_analyzed = len(getattr(self, 'file_summaries', {}))
        cache_enabled = self.file_cache.enabled if hasattr(self, 'file_cache') else False

        # When cache is enabled, file analysis is much faster, so we need more context
        # before triggering early stopping to avoid premature completeness checks
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        if cache_enabled:
            first_check_files = thresholds.get('early_stop_files_warm', 40)
            first_check_insights = thresholds.get('early_stop_insights_warm', 25)
            second_check_files = thresholds.get('early_stop_files_warm_secondary', 50)
            second_check_insights = thresholds.get('early_stop_insights_warm_secondary', 35)
            print(f"🔥 [CODE_AGENT] Cache-aware thresholds: first check at {first_check_files} files, second at {second_check_files} files")
        else:
            first_check_files = thresholds.get('early_stop_files_cold', 20)
            first_check_insights = thresholds.get('early_stop_insights_cold', 15)
            second_check_files = thresholds.get('early_stop_files_cold_secondary', 35)
            second_check_insights = thresholds.get('early_stop_insights_cold_secondary', 25)

        # After analyzing first batch of files with sufficient insights, evaluate quality
        if files_analyzed >= first_check_files and len(self.insights) >= first_check_insights:
            print(f"🎯 [CODE_AGENT] Early stopping check: {files_analyzed} files, {len(self.insights)} insights (cache: {cache_enabled})")
            is_complete = self._llm_evaluate_completeness(question)
            if is_complete:
                print(f"✅ [CODE_AGENT] Early stopping: sufficient information gathered")
                return True

        # More aggressive check after extended analysis
        if files_analyzed >= second_check_files and len(self.insights) >= second_check_insights:
            print(f"🎯 [CODE_AGENT] Secondary early stopping check: {files_analyzed} files, {len(self.insights)} insights (cache: {cache_enabled})")
            is_complete = self._llm_evaluate_completeness(question)
            if is_complete:
                print(f"✅ [CODE_AGENT] Early stopping: sufficient information after extended analysis")
                return True

        # Legacy check for backward compatibility
        iteration_check = thresholds.get('iteration_with_insights_check', 3)
        min_insights_at_iter = thresholds.get('min_insights_at_iteration', 5)
        if self.iteration >= iteration_check and len(self.insights) >= min_insights_at_iter:
            return self._llm_evaluate_completeness(question)

        # Safety: max iterations reached
        if self.iteration >= self.max_iterations:
            return True

        return False

    def _llm_evaluate_completeness(self, question: str) -> bool:
        """Ask LLM if we have enough information to answer comprehensively"""

        # Sample recent insights (last 20 to show latest discoveries)
        insights_summary = "\n".join([f"- {i.get('content', '')}" for i in self.insights[-20:]])

        # Get file list for context
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        max_context_files = thresholds.get('max_context_files_shown', 10)
        files_list = list(self.file_summaries.keys())[:max_context_files]
        files_summary = "\n".join([f"- {f}" for f in files_list])

        eval_prompt = f"""Question to answer: "{question}"

Files analyzed ({len(self.file_summaries)} total):
{files_summary}
{"... and " + str(len(self.file_summaries) - max_context_files) + " more" if len(self.file_summaries) > max_context_files else ""}

Key insights gathered ({len(self.insights)} total, showing last 20):
{insights_summary}

Evaluation criteria:
1. Do we understand WHY this design choice was made?
2. Do we have specific code references (file paths, classes, functions)?
3. Can we explain HOW it works with concrete examples?
4. Have we identified the key architectural patterns involved?
5. Are there enough insights to write a comprehensive "Life of X" narrative?

Respond in JSON format:
{{
  "sufficient": true/false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation",
  "missing_aspects": ["aspect1", "aspect2"] or []
}}"""

        # OPTIMIZATION: Use fast model for completeness checks (10-20x speedup)
        response = self.call_llm_fast(eval_prompt, "You are evaluating if gathered insights are sufficient to answer the question comprehensively.")

        if response.get('success'):
            try:
                # Try to parse JSON response
                content = response.get('content', '')
                # Extract JSON from response (handle markdown code blocks)
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0].strip()

                result = json.loads(content)
                is_sufficient = result.get('sufficient', False)
                confidence = result.get('confidence', 0.0)
                reason = result.get('reason', '')

                print(f"📊 [CODE_AGENT] Completeness evaluation: sufficient={is_sufficient}, confidence={confidence:.2f}, reason={reason}")

                # Require high confidence for early stopping (from config)
                min_certainty = self.config.get('agents', {}).get('thresholds', {}).get('min_analysis_certainty', 0.7)
                return is_sufficient and confidence >= min_certainty

            except json.JSONDecodeError:
                # Fallback to simple YES/NO parsing
                content = response.get('content', '').upper()
                return 'SUFFICIENT": TRUE' in content or ('YES' in content[:50] and 'NO' not in content[:50])
            except Exception as e:
                print(f"⚠️ [CODE_AGENT] Error parsing completeness evaluation: {e}")
                return False

        # Default to continue if LLM fails
        return False
    
    def _generate_results(self, question: str) -> Dict[str, Any]:
        """Generate comprehensive answer by synthesizing all gathered insights"""
        print(f"🔍 [CODE_AGENT] Generating comprehensive answer...")

        # OPTIMIZATION: Report cache statistics
        if hasattr(self, 'file_cache'):
            cache_stats = self.file_cache.get_stats()
            if cache_stats['total_requests'] > 0:
                print(f"📊 [CODE_AGENT] Cache stats: {cache_stats['hits']} hits, {cache_stats['misses']} misses, {cache_stats['expired']} expired, {cache_stats['hit_rate']:.1%} hit rate, {cache_stats['cache_size']} entries stored")

        if not self.insights:
            return {
                'success': False,
                'error': 'No code analysis completed - no insights gathered',
                'question': question
            }

        # Generate comprehensive answer using LLM synthesis
        narrative = self._synthesize_comprehensive_answer(question)

        # Calculate confidence from config thresholds
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        base_conf = thresholds.get('base_confidence', 0.6)
        conf_increment = thresholds.get('confidence_increment', 0.05)
        max_conf = thresholds.get('max_confidence', 0.9)
        confidence = min(max_conf, base_conf + (len(self.insights) * conf_increment))

        return {
            'success': True,
            'question': question,
            'narrative': narrative,
            'insights': self.insights,
            'confidence': confidence,
            'tools_used': len(self.tool_results),
            'function_calls_made': len([r for r in self.tool_results]),
            'files_analyzed': len(getattr(self, 'file_summaries', {})),
            'agent': 'code'
        }

    def _synthesize_comprehensive_answer(self, question: str) -> str:
        """Use LLM to synthesize all insights into comprehensive answer"""
        print(f"🤖 [CODE_AGENT] Synthesizing comprehensive answer from {len(self.insights)} insights...")

        # Store question for potential re-synthesis
        self.current_question = question

        synthesis_start_time = time.time()

        # NOTE: Relevance checking now happens in _analyze_relevant_files with conditional expansion
        # This ensures we can expand the file set BEFORE synthesis if needed

        # Prepare file summaries context with SPECIFIC implementation details
        file_context = ""
        if hasattr(self, 'file_summaries') and self.file_summaries:
            file_context = "\n\n**Files Analyzed (with SPECIFIC implementation details):**\n"
            for file_path, summary in list(self.file_summaries.items())[:10]:
                file_context += f"\n**{file_path}:**\n"
                file_context += f"- Purpose: {summary.get('purpose', 'N/A')}\n"
                file_context += f"- Overview: {summary.get('overview', 'N/A')}\n"

                # Include specific enums/constants
                if summary.get('enums_constants'):
                    enums = summary['enums_constants'][:5]
                    file_context += f"- Enums/Constants: {', '.join(enums)}\n"

                # Include specific model fields
                if summary.get('model_fields'):
                    fields = summary['model_fields'][:5]
                    file_context += f"- Model Fields: {', '.join(fields)}\n"

                # Include specific API endpoints
                if summary.get('api_endpoints'):
                    endpoints = summary['api_endpoints'][:3]
                    file_context += f"- API Endpoints: {', '.join(endpoints)}\n"

                # Include specific functions (WITH IMPLEMENTATION DETAILS from Version 8)
                if summary.get('functions'):
                    funcs = summary['functions'][:3]
                    file_context += f"- Functions: {', '.join(funcs)}\n"

                if summary.get('key_features'):
                    features = summary['key_features'][:2]
                    file_context += f"- Key features: {', '.join(features)}\n"

                # PHASE 1: Include implementation notes (Version 8 - captures HOW it works)
                if summary.get('implementation_notes'):
                    impl_notes = summary['implementation_notes']
                    # Truncate if too long
                    thresholds = self.config.get('agents', {}).get('thresholds', {})
                    max_impl_len = thresholds.get('max_impl_notes_length', 300)
                    if len(impl_notes) > max_impl_len:
                        impl_notes = impl_notes[:max_impl_len] + "..."
                    file_context += f"- Implementation: {impl_notes}\n"

        # Prepare insights summary
        insights_text = "\n".join([f"- {insight.get('content', '')}" for insight in self.insights])

        # External systems context
        external_systems_context = ""
        if hasattr(self, 'domain_info') and self.domain_info.get('external_systems'):
            external_systems = self.domain_info['external_systems']
            external_systems_context = f"""
🔗 EXTERNAL SYSTEMS DETECTED:
This system integrates with the following external services:
{chr(10).join(f"- {sys}" for sys in external_systems)}

CRITICAL: If your file analysis mentions these external systems, you MUST include them in your answer.
Look for API calls, SDK usage, webhooks, or configuration related to these systems.
"""

        # Build synthesis parameters from config
        synthesis_config = self.config.get('agents', {}).get('synthesis', {})
        target_min = synthesis_config.get('target_narrative_min', 3000)
        target_max = synthesis_config.get('target_narrative_max', 5000)
        min_files = synthesis_config.get('min_key_files_cited', 3)
        max_files = synthesis_config.get('max_key_files_cited', 7)
        min_examples = synthesis_config.get('min_code_examples', 2)
        max_examples = synthesis_config.get('max_code_examples', 3)

        synthesis_params = f"""- Target length: {target_min}-{target_max} characters (be comprehensive but concise)
- Cite {min_files}-{max_files} key files maximum (focus on MOST important files)
- Provide {min_examples}-{max_examples} concrete code examples (not 10+)"""

        synthesis_prompt = f"""A new engineer asked: "{question}"

CRITICAL FORMATTING INSTRUCTION: Your answer MUST begin with the heading "**Overview**" followed by 2-3 sentences. Do NOT write "Short answer:" or any other prefix text. Start directly with "**Overview**".
{external_systems_context}
🚨 CRITICAL GROUNDING REQUIREMENT 🚨
Every claim you make MUST be backed by SPECIFIC details from the analyzed files:
- Use EXACT names: class names, function names, constants, enum values (from the analysis below)
- Cite EXACT API endpoints with HTTP methods and URL patterns (from the analysis below)
- Reference EXACT model field names and their types (from the analysis below)
- Use ACTUAL function signatures you found (from the analysis below)
- DESCRIBE ACTUAL IMPLEMENTATIONS: The file summaries now include what functions DO (their implementation logic), not just signatures. USE THIS to explain actual behavior.

🔒 FIX #2: FILE PATH ACCURACY REQUIREMENT
- ONLY cite files that appear in the "Files Analyzed" section below
- Use the EXACT path shown in the analysis (e.g., "tests/module/test_handler.ext" not "module/test_handler.ext")
- DO NOT infer or guess file paths - if it's not in the analyzed files list, don't mention it
- When referencing a file, copy the path EXACTLY as shown in the **Files Analyzed** section

🔢 MANDATORY LINE NUMBER FORMATTING - NO EXCEPTIONS:
- When mentioning a class/model: "The `ClassName` (path/to/file.py:123)..." - LINE NUMBER REQUIRED
- When mentioning a function: "The `function_name(param1, param2)` (path/to/file.py:456)..." - LINE NUMBER REQUIRED
- When mentioning a constant: "The constant `CONSTANT_NAME = 'value'` (line 89)..." - LINE NUMBER REQUIRED
- When mentioning an endpoint: "The endpoint `POST /api/path/{{id}}/` (path/to/file.py:234)..." - LINE NUMBER REQUIRED
- When mentioning a model field: "`ModelName.field_name` (FieldType) defined in file.py:567..."

CRITICAL: Your file analysis includes line numbers for classes, functions, and constants. You MUST use them EVERY TIME.
Format: `ComponentName` (file.py:LINE) not just `ComponentName` in file.py

🚫 ZERO TOLERANCE RULE: If you cannot find the line number for a component in your file analysis, DO NOT MENTION THAT COMPONENT AT ALL. Better to skip it than provide an ungrounded reference.

Examples of FORBIDDEN patterns:
- ❌ "The `Application` class in `src/auth/models.ext`..." (missing line number)
- ✅ "The `Application` class (src/auth/models.ext:145)..." (correct)

⚠️ IF A FILE SUMMARY IS MISSING LINE NUMBERS: That means the component doesn't exist or wasn't properly analyzed. DO NOT mention it in your answer without a line number citation. Skip it entirely rather than provide vague references.

DO NOT:
- Invent class/function names not in the analysis
- Use generic examples if actual names are available
- Describe patterns without citing actual implementation
- Mention details not found in the analyzed files

📏 CONCISENESS REQUIREMENTS:
{synthesis_params}
- Use bullet points for clarity, not verbose paragraphs
- Focus on WHAT and WHY, avoid exhaustive HOW for obvious patterns
- DO NOT repeat the same information multiple times
- DO NOT explain obvious framework patterns
- DO NOT cite every single file you analyzed - be selective

If a specific detail (like exact constant values, specific function names, or API paths) is not in the analysis, either:
1. Describe the pattern generically, OR
2. Skip that level of detail

You're a senior engineer who knows this codebase well. Here's your analysis:

**Analysis Insights ({len(self.insights)} total):**
{insights_text}

{file_context}

**Your answer should adapt based on the question:**

**If the question is about a flow/process** (requests, signals, events, authentication, data processing):
Use "Life of X" narrative format:

1. **Overview** (2-3 sentences)
   - Answer the question directly
   - Explain the core reason WHY this design exists     

2. **Life of [the Feature/Request/Signal] - How It Works & Why** (CRITICAL for actionability)
     **Combine architectural reasoning WITH step-by-step concrete walkthrough:**

   - Start with a real scenario and a narrative flow starting from the relevant entry point. It should be a CONCRETE and CONTEXT-APPROPRIATE starting point:
    * When a user does X, when Y happens, etc. (context-appropriate starting point). For example:
      * "When a user submits the form..."
      * "When a request comes in..."
      * "When the system receives an event..."

    **REQUIREMENTS for concrete example:**
    - MUST use NUMBERED STEPS (1., 2., 3., 4...) - this is mandatory for clarity
    - MUST start with a SPECIFIC code example, not abstract descriptions
    - Show the actual code being executed (e.g., "client.authenticate(credentials)" not "suppose you write an auth call")

   - Walk step-by-step through execution and WHAT HAPPENS with references to the ACTUAL file, class, and functions where the behavior is implemented:
    * first this happens in `actual/file.py`, then that, finally this... For example:
      * "At this point, the request is validated..."
      * "Later, when validation passes, the system..."
      * "First, it calls the handler in src/handlers/auth.py..."
      * "The processor (e.g., src/core/processor.py) then..."
   - Trace execution through the actual codebase with discovered file names
   - USE THE IMPLEMENTATION DETAILS from file summaries: Don't say "function X is called", say "function X is called which does Y (as seen in the implementation at line Z)"
   - CITE ACTUAL LOGIC: If a file summary says a function "iterates over items and filters by status", MENTION THAT in your explanation
   - Explain the architectural reasons as you trace (composability, performance, modularity, trade-offs)
   - Weave in design rationale, trade-offs, and why alternatives weren't chosen AS you explain
   - Use numbered steps or clear sequence markers
   - Explain WHY at key decision points during the flow
   - Make it feel like you're tracing code execution line by line WITH actual implementation details           

3. **Practical Gotchas & Tips**
  - Common mistakes developers make
  - How to avoid pitfalls
  - When to use alternative patterns
  - Performance tips
  - Concrete examples: "Don't do X, do Y instead because..."                                                                                                                                                                        ╎│

4. **Where to Look in the Repo**                                                                                                                                                                                                     ╎│
  - Specific files to read (with line number hints if relevant)                                                                                                                                                                     ╎│
  - Key classes/functions to understand                                                                                                                                                                                             ╎│
  - Suggested reading order for deeper dive    

**If the question is about design/architecture/patterns** (why decisions were made, design rationale):
Use architecture-focused format:

1. **Overview** (2-3 sentences)
   - Answer the question directly
   - Explain the core reason WHY this design exists     

2. **Why This Design Exists & How the Code Shows It**
   - Explain the architectural reasoning (performance, maintainability, flexibility, etc.)
   - Point to ACTUAL files/classes/functions where this is implemented
   - Show design trade-offs and why alternatives weren't chosen
   - Use bullet points for each major architectural reason
   - IMPORTANT: Add a "Why not [alternative approach]?" subsection explaining what was rejected and why

3. **Concrete Example** (STRONGLY RECOMMENDED - include unless truly not applicable)

   **REQUIREMENTS:**
   - MUST use NUMBERED STEPS (1., 2., 3., 4...) if showing a sequence
   - Start with SPECIFIC code: "Suppose you write: qs = Book.objects.filter(x=1)" NOT "suppose you do a chain of operations"

   - Brief walkthrough of a specific scenario to make the architecture tangible
   - "When you do X, here's what happens..."
   - Keep this shorter than flow/process questions but still concrete

4. **Practical Gotchas & Tips**
   - Common mistakes
   - Performance considerations
   - When to use alternatives

5. **Where to Look in the Repo**
   - Key files to understand this design
   - Key classes/functions to understand
   - Suggested reading order for deeper dive    

**Always include:**
- Conversational, mentor-like tone: "You'll find...", "If you look at...", "The code does..."
- ACTUAL file paths, class names, function names from the analysis (not generic examples)
- The WHY behind decisions (woven into the explanation), not just WHAT
- Architectural reasoning integrated with code tracing (not separate sections)
- Practical insights and gotchas
- Specific code references throughout
- Be specific and actionable - new engineer should know exactly what to do/avoid

**Avoid:**
- Generic examples not from the analysis
- Phrases like "the journey begins" or "let's embark"
- Overly formal technical writing style
- Separating architecture discussion from code explanation
- Using narrative style for simple architectural questions

**Style Notes:** 
- Think: Senior engineer doing a code walkthrough over coffee to a smart new engineer, using "Life of X" narrative when tracing flows through the system. Show both WHY (architecture/trade-offs) and HOW (execution flow) together, woven into the same explanation."""

        system_prompt = """You are a senior software engineer with deep knowledge of this codebase, explaining it to a new engineer who just joined the team.

Your explanation should:
- Be conversational and practical, like you're walking them through the code over coffee
- Share insights about WHY things are built this way, not just WHAT they do
- Point to specific files, classes, and functions they should look at
- Explain the journey of data/requests through the system
- Share gotchas, design decisions, and architectural reasoning
- Use "you'll find...", "the code does...", "if you look at..." language
- Be technical but approachable - assume they're smart but new to this codebase

Think of this as onboarding documentation from an experienced engineer who knows all the important details."""

        response = self.call_llm(synthesis_prompt, system_prompt)

        synthesis_duration = time.time() - synthesis_start_time

        # Track synthesis metrics
        synthesis_metrics = {
            'prompt_tokens': response.get('usage', {}).get('prompt_tokens', 0),
            'completion_tokens': response.get('usage', {}).get('completion_tokens', 0),
            'total_tokens': response.get('usage', {}).get('total_tokens', 0),
            'duration_ms': synthesis_duration * 1000,
            'model': self.llm.model
        }

        # Store synthesis metrics separately
        if not hasattr(self, 'synthesis_metrics'):
            self.synthesis_metrics = {}
        self.synthesis_metrics = synthesis_metrics

        print(f"📊 [CODE_AGENT] Synthesis metrics: {synthesis_metrics['total_tokens']} tokens, {synthesis_duration:.2f}s")

        if response.get('success'):
            narrative = response.get('content', self._create_fallback_narrative())

            # ENHANCEMENT: Validate grounding of narrative - NOW BLOCKING
            grounding_check = self._validate_narrative_grounding(narrative)
            if not grounding_check['grounded']:
                print(f"❌ [CODE_AGENT] GROUNDING VALIDATION FAILED: {grounding_check.get('warning', 'Unknown issue')}")
                if grounding_check.get('ungrounded_files'):
                    ungrounded = grounding_check['ungrounded_files']
                    print(f"   ❌ Fabricated file references: {', '.join(ungrounded[:5])}")

                    # BLOCKING: Trigger refinement to find these missing files
                    print(f"🔄 [CODE_AGENT] Attempting to find fabricated files...")
                    additional_files = self._search_for_ungrounded_files(ungrounded)

                    if additional_files:
                        print(f"✅ [CODE_AGENT] Found {len(additional_files)} fabricated files - analyzing them now")
                        self._analyze_files_with_metrics(additional_files, self.current_question if hasattr(self, 'current_question') else '', file_type="recovered file")

                        # Re-synthesize with the newly analyzed files
                        print(f"🔄 [CODE_AGENT] Re-synthesizing answer with recovered files...")
                        return self._synthesize_comprehensive_answer(self.current_question if hasattr(self, 'current_question') else '')
                    else:
                        print(f"❌ [CODE_AGENT] Could not find fabricated files - returning degraded answer")
                        # Prepend warning to narrative
                        warning_prefix = "⚠️ **Note**: This answer may reference files that were not fully analyzed. Please verify details.\n\n"
                        return warning_prefix + narrative
            else:
                print(f"✅ [CODE_AGENT] Grounding validation passed - all cited files were analyzed")

            # NEW: Validate that claimed functions/classes actually exist in analyzed files
            claim_check = self._validate_claims_against_files(narrative)
            if not claim_check['valid']:
                print(f"❌ [CODE_AGENT] CLAIM VALIDATION FAILED")
                print(f"   Fabricated functions: {claim_check.get('fabricated_functions', [])[:5]}")
                print(f"   Fabricated classes: {claim_check.get('fabricated_classes', [])[:5]}")
                print(f"   ({claim_check.get('actual_functions_count', 0)} actual functions, {claim_check.get('actual_classes_count', 0)} actual classes analyzed)")

                # Prepend warning to narrative
                fab_funcs = len(claim_check.get('fabricated_functions', []))
                fab_classes = len(claim_check.get('fabricated_classes', []))
                warning_prefix = f"⚠️ **Warning**: This answer may mention {fab_funcs} functions and {fab_classes} classes not found in analyzed files. Please verify details.\n\n"
                return warning_prefix + narrative
            else:
                print(f"✅ [CODE_AGENT] Claim validation passed - all functions/classes verified")

            return narrative
        else:
            print(f"⚠️ [CODE_AGENT] LLM synthesis failed, using fallback")
            return self._create_fallback_narrative()

    def _search_for_ungrounded_files(self, ungrounded_files: list) -> list:
        """Search for files that were fabricated in the narrative

        This is directory-aware - it extracts the directory path and searches there.
        """
        additional_files = []

        for file_path in ungrounded_files[:5]:  # Limit to 5 to avoid excessive searching
            print(f"🔍 [CODE_AGENT] Searching for fabricated file: {file_path}")

            # Try exact path first
            try:
                read_result = self.use_tool('read_file', file_path=file_path, include_structure=True)
                if read_result and not read_result.get('error'):
                    print(f"✅ [CODE_AGENT] Found exact file: {file_path}")
                    additional_files.append({'path': file_path, 'relevance_score': 1.0})
                    continue
            except:
                pass

            # Extract directory and filename patterns
            # e.g., "src/auth/handler.go" -> dir="src/auth/", pattern="handler"
            if '/' in file_path:
                parts = file_path.rsplit('/', 1)
                directory = parts[0] + '/'
                filename = parts[1]
                basename = filename.split('.')[0]  # "handler.go" -> "handler"

                print(f"🔍 [CODE_AGENT] Searching in directory: {directory} for pattern: {basename}")

                # Search within that specific directory
                search_result = self.use_tool('search_files', pattern=basename, path=directory, max_results=5)
                if search_result and not search_result.get('error'):
                    matches = search_result.get('matches', [])
                    for match in matches:
                        match_file = match.get('file', '')
                        # Prioritize files in the same directory
                        if match_file.startswith(directory) and match_file not in self.file_summaries:
                            print(f"✅ [CODE_AGENT] Found related file: {match_file}")
                            relevance = self.config.get('agents', {}).get('thresholds', {}).get('medium_relevance', 0.9)
                            additional_files.append({'path': match_file, 'relevance_score': relevance})

        return additional_files[:10]  # Limit to 10 files max

    def _validate_narrative_grounding(self, narrative: str) -> Dict[str, Any]:
        """Validate that narrative only cites files that were actually analyzed

        This prevents fabrication of components by checking if all file paths
        mentioned in the narrative were actually analyzed during the session.
        """
        import re

        # Extract all file paths mentioned in narrative
        # Language-agnostic: uses configured file extensions
        cited_files = set()

        # Get configured extensions dynamically
        text_extensions = self.config.get('repo', {}).get('text_extensions', [])
        excluded_dirs = self.config.get('repo', {}).get('excluded_dirs', [])

        # Build extension pattern: [".py", ".js"] -> "py|js|ts|..."
        ext_pattern = '|'.join([ext.lstrip('.') for ext in text_extensions])

        # Build excluded dirs pattern: ["cache", "__pycache__"] -> "cache|__pycache__|..."
        excluded_pattern = '|'.join([d.replace('_', r'\_') for d in excluded_dirs])

        # Pattern: Match file paths with any configured extension, excluding configured cache dirs
        # Matches: path/to/file.ext, tests/path/to/file.ext, etc.
        file_pattern = rf'(?!(?:{excluded_pattern}))[a-z0-9_]+(?:/[a-z0-9_]+)*\.(?:{ext_pattern})'

        matches = re.findall(file_pattern, narrative, re.IGNORECASE)
        cited_files.update(matches)

        # Get list of actually analyzed files
        analyzed_files = set()
        if hasattr(self, 'file_summaries') and self.file_summaries:
            analyzed_files = set(self.file_summaries.keys())

        # Check which cited files were NOT in analyzed_files
        # Use configured test directory prefixes for path normalization
        test_prefixes = self.config.get('repo', {}).get('test_directory_prefixes', ['tests/', 'test/'])

        ungrounded_citations = []
        for cited_file in cited_files:
            if cited_file in analyzed_files:
                continue  # Found exact match

            found_variant = False

            # Check if cited file is missing a test prefix
            for prefix in test_prefixes:
                test_variant = f"{prefix}{cited_file}"
                if test_variant in analyzed_files:
                    found_variant = True
                    break

            if found_variant:
                continue

            # Check if cited file has an extra test prefix
            for prefix in test_prefixes:
                if cited_file.startswith(prefix):
                    no_test_variant = cited_file[len(prefix):]
                    if no_test_variant in analyzed_files:
                        found_variant = True
                        break

            if found_variant:
                continue

            # Not found in any variant
            ungrounded_citations.append(cited_file)

        if ungrounded_citations:
            return {
                'grounded': False,
                'ungrounded_files': ungrounded_citations,
                'cited_files_count': len(cited_files),
                'analyzed_files_count': len(analyzed_files),
                'warning': f"Narrative cites {len(ungrounded_citations)} files that were NOT analyzed - answer may contain fabricated references"
            }

        return {
            'grounded': True,
            'cited_files_count': len(cited_files),
            'analyzed_files_count': len(analyzed_files),
            'all_citations_verified': True
        }

    def _repair_json(self, json_str: str) -> str:
        """FIX 1: Attempt to repair common JSON issues before parsing

        Common issues:
        - Truncated JSON (missing closing braces/brackets)
        - Unclosed strings at end of truncated response

        Note: We do NOT attempt to fix quotes inside strings, as that's too risky
        and would break valid JSON. The retry with lower temperature should handle that.
        """
        # If JSON is truncated (more opening braces than closing), try to close it
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        if open_braces > close_braces:
            # Check if we're inside a string at the end
            # If odd number of quotes before end, close the string first
            quotes_before_end = json_str.rstrip().count('"')
            if quotes_before_end % 2 == 1:
                json_str = json_str.rstrip() + '"'

            # Now close the braces
            json_str += '}' * (open_braces - close_braces)

        # Same for arrays
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        if open_brackets > close_brackets:
            json_str += ']' * (open_brackets - close_brackets)

        return json_str

    def _validate_summary_against_content(self, summary: Dict[str, Any], content: str, file_path: str) -> Dict[str, Any]:
        """PHASE 2: Validate that summary details actually exist in file content

        Prevents hallucination by checking:
        1. Cited line numbers are valid (within file bounds)
        2. Component names (classes, functions) exist in content
        3. Constants/enums exist with cited values

        Returns: {'hallucinations_found': bool, 'issues': [list of issues]}
        """
        import re

        issues = []
        content_lines = content.split('\n')
        max_line = len(content_lines)

        # Check functions
        if summary.get('functions'):
            for func_entry in summary['functions']:
                # Extract function name and line number
                match = re.search(r'([a-z_][a-z0-9_]*)\s*\([^)]*\)\s*\(line\s+(\d+)\)', func_entry, re.IGNORECASE)
                if match:
                    func_name = match.group(1)
                    line_num = int(match.group(2))

                    # Check if line number is valid
                    if line_num > max_line or line_num < 1:
                        issues.append(f"Function {func_name}: Invalid line {line_num} (file has {max_line} lines)")

                    # Check if function name exists in content
                    if func_name not in content:
                        issues.append(f"Function {func_name}: Not found in file content")

        # Check classes
        if summary.get('classes'):
            for class_entry in summary['classes']:
                # Extract class name and line number
                match = re.search(r'([A-Z][a-zA-Z0-9]*)\s*\(line\s+(\d+)\)', class_entry)
                if match:
                    class_name = match.group(1)
                    line_num = int(match.group(2))

                    # Check if line number is valid
                    if line_num > max_line or line_num < 1:
                        issues.append(f"Class {class_name}: Invalid line {line_num} (file has {max_line} lines)")

                    # Check if class name exists in content
                    if class_name not in content:
                        issues.append(f"Class {class_name}: Not found in file content")

        # Check constants/enums
        if summary.get('enums_constants'):
            for const_entry in summary['enums_constants']:
                # Extract constant name
                match = re.search(r'([A-Z_][A-Z0-9_]*)\s*=', const_entry)
                if match:
                    const_name = match.group(1)
                    if const_name not in content:
                        issues.append(f"Constant {const_name}: Not found in file content")

        return {
            'hallucinations_found': len(issues) > 0,
            'issues': issues
        }

    def _validate_line_numbers_in_summary(self, summary: Dict[str, Any]) -> bool:
        """Check if the file summary actually includes line numbers in classes/functions

        Returns True if at least 50% of classes and functions have line numbers
        """
        import re

        # Check functions for line numbers
        functions_with_lines = 0
        total_functions = 0
        if summary.get('functions'):
            for func in summary['functions']:
                total_functions += 1
                if re.search(r'\(line \d+\)', str(func)):
                    functions_with_lines += 1

        # Check classes for line numbers
        classes_with_lines = 0
        total_classes = 0
        if summary.get('classes'):
            for cls in summary['classes']:
                total_classes += 1
                if re.search(r'\(line \d+\)', str(cls)):
                    classes_with_lines += 1

        # Calculate coverage
        total_components = total_functions + total_classes
        components_with_lines = functions_with_lines + classes_with_lines

        if total_components == 0:
            return True  # No components to validate

        coverage = components_with_lines / total_components
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        min_coverage = thresholds.get('min_line_number_coverage', 0.5)
        return coverage >= min_coverage

    def _validate_claims_against_files(self, narrative: str) -> Dict[str, Any]:
        """Context-aware validation of code references in narrative

        Only validates references that have explicit code markers (line numbers, file paths, backticks).
        Skips prose mentions to avoid false positives.

        Validation logic:
        - STRICT: References with line numbers (e.g., "ApplicationView (line 309)") must exist in summaries
        - SKIP: Prose mentions without code markers (e.g., "the Email module", "when changes occur")
        - WARN: Excessive hedge words indicating uncertainty
        """
        import re

        # Get actual functions/classes from file summaries for validation
        actual_functions = set()
        actual_classes = set()

        if hasattr(self, 'file_summaries') and self.file_summaries:
            for file_path, summary in self.file_summaries.items():
                # Extract function names from the functions array
                if summary.get('functions'):
                    for func_entry in summary['functions']:
                        func_match = re.match(r'([a-z_][a-z0-9_]*)\s*\(', str(func_entry), re.IGNORECASE)
                        if func_match:
                            actual_functions.add(func_match.group(1))

                # Extract class names from the classes array
                if summary.get('classes'):
                    for class_entry in summary['classes']:
                        class_match = re.match(r'([A-Z][a-zA-Z0-9]+)', str(class_entry))
                        if class_match:
                            actual_classes.add(class_match.group(1))

        # CONTEXT-AWARE VALIDATION: Only validate references with explicit code markers
        # Pattern: ComponentName (file.ext:LINE) - this is a specific claim that must be verified
        # Language-agnostic: matches any file extension from config
        text_extensions = self.config.get('repo', {}).get('text_extensions', [])
        # Build regex pattern dynamically from configured extensions
        # Convert [".py", ".js", ".go"] to "py|js|go"
        ext_pattern = '|'.join([ext.lstrip('.') for ext in text_extensions])

        # Match: ComponentName (path/to/file.ext:LINE)
        explicit_references = re.findall(
            rf'`?([A-Z][a-zA-Z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)`?\s*\([a-z0-9_/]+\.(?:{ext_pattern}):(\d+)\)',
            narrative
        )

        high_confidence_issues = []
        for ref, line_num in explicit_references:
            # Extract the component name (might be ClassName or ClassName.method)
            if '.' in ref:
                class_name, method_name = ref.split('.', 1)
                # Validate both class and method exist
                if class_name not in actual_classes:
                    high_confidence_issues.append(f"{class_name} (line {line_num}) - class not found in summaries")
                if method_name not in actual_functions:
                    high_confidence_issues.append(f"{method_name} (line {line_num}) - method not found in summaries")
            else:
                # Could be class or function
                if ref[0].isupper():  # Starts with capital = likely a class
                    if ref not in actual_classes:
                        high_confidence_issues.append(f"{ref} (line {line_num}) - class not found in summaries")
                else:  # Starts with lowercase = likely a function
                    if ref not in actual_functions:
                        high_confidence_issues.append(f"{ref} (line {line_num}) - function not found in summaries")

        # Validation result
        has_high_confidence_issues = len(high_confidence_issues) > 0

        # Only fail if we have explicit line number references that don't validate
        is_valid = not has_high_confidence_issues

        if not is_valid:
            return {
                'valid': False,
                'high_confidence_issues': high_confidence_issues[:10],
                'warning': f"{len(high_confidence_issues)} explicit references with line numbers could not be verified",
                'actual_functions_count': len(actual_functions),
                'actual_classes_count': len(actual_classes),
                'explicit_references_checked': len(explicit_references)
            }

        return {
            'valid': True,
            'explicit_references_checked': len(explicit_references),
            'all_references_verified': True,
            'actual_functions_count': len(actual_functions),
            'actual_classes_count': len(actual_classes)
        }

    def _check_analysis_certainty(self, question: str) -> Dict[str, Any]:
        """Check if we have the right files to answer the question before synthesis

        This prevents synthesizing answers from the wrong files by asking the LLM
        to assess whether the analyzed files are actually relevant to the question.
        """
        try:
            # Get list of analyzed files
            analyzed_files = []
            if hasattr(self, 'file_summaries') and self.file_summaries:
                # Include file path and brief summary
                for file_path, summary in list(self.file_summaries.items())[:15]:
                    purpose = summary.get('purpose', 'Unknown')
                    analyzed_files.append(f"- {file_path}: {purpose}")

            if not analyzed_files:
                return {
                    'have_right_files': False,
                    'confidence': 0.0,
                    'missing_keywords': [],
                    'rationale': "No files were analyzed"
                }

            analyzed_files_text = "\n".join(analyzed_files)

            prompt = f"""Question: "{question}"

Files that were analyzed:
{analyzed_files_text}

Before answering this question, assess:
1. Do these files directly address the question's domain/subsystem?
2. Are there any specific models, functions, or modules the question implies that seem to be MISSING?
3. Based on file paths and purposes, do we have the RIGHT layer/component to answer this question?
4. If the question asks about a specific feature, did we analyze files from that specific subsystem?

Respond with JSON only:
{{
  "have_right_files": true/false,
  "confidence": 0.0-1.0,
  "missing_keywords": ["list", "of", "specific", "terms", "to", "search"],
  "rationale": "Brief explanation of whether we have the right files"
}}

Guidelines:
- If question asks about Feature X but files are from unrelated subsystem Y: have_right_files=false
- If question implies specific models/functions that aren't in the analyzed files: have_right_files=false, list those missing components in missing_keywords
- If analyzed files match the question's domain and contain relevant implementation: have_right_files=true, confidence=self.get_confidence('high')+
- Focus on whether the specific question can be answered from the specific files analyzed
"""

            system_prompt = "You are a code analysis expert. Assess whether the analyzed files can answer the specific question being asked."

            response = self.call_llm(prompt, system_prompt)

            if response.get('success'):
                content = response.get('content', '').strip()
                try:
                    # Extract JSON from response
                    import json
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_content = content[start:end]
                        certainty_data = json.loads(json_content)
                        return certainty_data
                except json.JSONDecodeError as e:
                    print(f"⚠️ [CODE_AGENT] Failed to parse certainty check JSON: {e}")

        except Exception as e:
            print(f"⚠️ [CODE_AGENT] Certainty check failed: {e}")

        # Default to allowing synthesis (fail open)
        return {
            'have_right_files': True,
            'confidence': 0.5,
            'missing_keywords': [],
            'rationale': "Unable to validate, proceeding with synthesis"
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
    
    def _llm_validate_file_relevance(self, question: str, file_paths: list) -> dict:
        """Use LLM to validate that analyzed files are relevant to the question"""
        try:
            # Only check first 10 files to avoid token limits
            files_to_check = file_paths[:10]

            prompt = f"""Question: "{question}"

Files that were analyzed:
{chr(10).join(f"- {fp}" for fp in files_to_check)}

Task: Determine if these files are likely to contain the information needed to answer the question.

Consider:
1. Do the file paths suggest they contain relevant implementation code?
2. Based on the question's topic, do these files match the expected subsystem/component?
3. Are these core implementation files or peripheral files (tests, examples, build scripts, static assets, etc.)?
4. Do the file names and paths align with the concepts mentioned in the question?
5. Are we analyzing the right layer/component of the system for this question?

Respond with JSON only:
{{
    "is_relevant": true/false,
    "reason": "Brief explanation of why files are or aren't relevant"
}}

Guidelines:
- If the question asks about a specific subsystem but files are from a different subsystem, mark as NOT relevant
- If files are infrastructure/tooling/build files but question is about business logic, mark as NOT relevant
- If files contain core implementation matching the question's domain, mark as relevant
- Focus on whether the analyzed files can actually answer the specific question being asked
"""

            response = self.call_llm(prompt, "You are a code analysis expert validating file relevance.")

            if response.get('success'):
                content = response.get('content', '').strip()
                try:
                    # Extract JSON from response
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_content = content[start:end]
                        relevance_data = json.loads(json_content)
                        return relevance_data
                except json.JSONDecodeError as e:
                    print(f"⚠️ [CODE_AGENT] Failed to parse relevance JSON: {e}")

        except Exception as e:
            print(f"⚠️ [CODE_AGENT] File relevance check failed: {e}")

        # Default to allowing synthesis (fail open)
        return {"is_relevant": True, "reason": "Unable to validate, proceeding with synthesis"}

    def _create_fallback_narrative(self) -> str:
        """Create improved fallback narrative when LLM synthesis fails"""

        if not self.insights:
            return "Code analysis was unable to gather sufficient information to answer the question."

        # Group insights by source
        narrative_parts = [f"## Code Analysis Results\n"]
        narrative_parts.append(f"Analyzed {len(getattr(self, 'file_summaries', {}))} files and gathered {len(self.insights)} insights:\n")

        # Add key insights
        narrative_parts.append("\n### Key Findings:\n")
        for i, insight in enumerate(self.insights[:8], 1):
            content = insight.get('content', 'N/A')
            confidence = insight.get('confidence', 0)
            narrative_parts.append(f"{i}. {content} (confidence: {confidence:.0%})")

        # Add file references if available
        if hasattr(self, 'file_summaries') and self.file_summaries:
            narrative_parts.append("\n### Files Analyzed:\n")
            for file_path in list(self.file_summaries.keys())[:5]:
                narrative_parts.append(f"- `{file_path}`")

        narrative_parts.append("\n*Note: This is a fallback summary. Full synthesis was unavailable.*")

        return "\n".join(narrative_parts)
    
    def _scan_repository_structure(self, question: str) -> str:
        """Step 1: Scan repository to discover files and structure"""
        try:
            print(f"🔍 [CODE_AGENT] Scanning repository structure...")
            
            # Use scan_directory tool to get repository structure
            max_depth = self.config.get('repo', {}).get('max_scan_depth', 5)
            scan_result = self.use_tool('scan_directory', max_depth=max_depth)
            
            if scan_result.get('error'):
                print(f"❌ [CODE_AGENT] Scan failed: {scan_result['error']}")
                self.add_insight(f"Repository scan failed: {scan_result['error']}", confidence=self.get_confidence('error'), source="scan_error")
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
                    confidence=self.get_confidence('high'),
                    source="repository_scan"
                )
            
            return "scan_complete"
            
        except Exception as e:
            print(f"❌ [CODE_AGENT] Scan exception: {e}")
            self.add_insight(f"Repository scan error: {str(e)}", confidence=self.get_confidence('error'), source="scan_exception")
            return "scan_failed"
    
    def _analyze_files_with_llm(self, question: str) -> str:
        """Step 2: Analyze each important file with LLM to generate per-file summaries"""
        try:
            if not hasattr(self, 'discovered_files') or not self.discovered_files:
                print(f"❌ [CODE_AGENT] No files to analyze")
                return "no_files_found"

            # Filter files for analysis (focus on source code)
            important_files = self._filter_important_files(self.discovered_files)

            # DEDUPLICATION: Skip files already analyzed in previous iterations
            already_analyzed = set(self.file_summaries.keys())
            new_files = [f for f in important_files if f.get('path', '') not in already_analyzed]

            if new_files:
                print(f"📄 [CODE_AGENT] Analyzing {len(new_files)} new files ({len(already_analyzed)} already analyzed, {len(important_files) - len(new_files)} duplicates skipped)...")
            else:
                print(f"✅ [CODE_AGENT] All {len(important_files)} files already analyzed, skipping LLM analysis")
                return "all_files_already_analyzed"

            analyzed_count = 0

            for file_info in new_files:  # Process only new files
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
                                confidence=self.get_confidence('high'),
                                source=f"architectural_analysis_{file_path}"
                            )
                        elif file_summary.get('key_features') and len(file_summary['key_features']) > 0:
                            # Fallback to key features if architectural insights are missing
                            key_feature = file_summary['key_features'][0]
                            if key_feature and not any(generic in key_feature.lower() for generic in ['initializes', 'defines', 'contains', 'implements']):
                                self.add_insight(
                                    f"File {file_path}: {key_feature}",
                                    confidence=self.get_confidence('low'),
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
                    confidence=self.get_confidence('high'),
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
                # Paths are normalized to forward slashes
                directory = '/'.join(file_path.split('/')[:-1]) if '/' in file_path else 'root'
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
                                confidence=self.get_confidence('high'),
                                source=f"directory_patterns_{directory}"
                            )
                        elif relationships:
                            relationship_text = relationships[0] if isinstance(relationships, list) else str(relationships)[:100]
                            self.add_insight(
                                f"Directory {directory}: {relationship_text}",
                                confidence=self.get_confidence('medium'),
                                source=f"directory_relationships_{directory}"
                            )
                        elif dir_summary.get('main_purpose') and 'source code' not in dir_summary['main_purpose'].lower():
                            # Only add purpose if it's not generic
                            self.add_insight(
                                f"Directory {directory}: {dir_summary['main_purpose']}",
                                confidence=self.get_confidence('low'),
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

        # Get file extension lists and exclusion patterns from configuration
        repo_config = self.config.get('repo', {})
        source_code_extensions = set(repo_config.get('source_code_extensions', []))
        config_extensions = set(repo_config.get('config_extensions', []))
        doc_extensions = set(repo_config.get('documentation_extensions', []))
        excluded_patterns = repo_config.get('code_agent_excluded_patterns', {})

        print(f"🔍 [CODE_AGENT] Filtering files for source code analysis...")
        print(f"📋 [CODE_AGENT] Source code extensions: {sorted(source_code_extensions)}")
        print(f"📚 [CODE_AGENT] Documentation extensions (will skip): {sorted(doc_extensions)}")

        doc_files_skipped = 0
        locale_files_skipped = 0
        examples_skipped = 0
        tests_skipped = 0
        build_skipped = 0
        frontend_skipped = 0
        migrations_skipped = 0

        for file_info in files:
            file_path = file_info.get('path', '')
            # Paths are normalized to forward slashes
            file_name = file_path.split('/')[-1] if '/' in file_path else file_path
            file_ext = file_info.get('extension', '').lower()
            file_path_lower = file_path.lower()

            # Check against categorized exclusion patterns from config
            skip_file = False
            for category, patterns in excluded_patterns.items():
                for pattern in patterns:
                    if pattern in file_path_lower:
                        if category == 'locale':
                            locale_files_skipped += 1
                        elif category == 'documentation':
                            doc_files_skipped += 1
                        elif category == 'examples':
                            examples_skipped += 1
                        elif category == 'tests':
                            tests_skipped += 1
                        elif category == 'build':
                            build_skipped += 1
                        elif category == 'frontend_assets':
                            frontend_skipped += 1
                        elif category == 'migrations':
                            migrations_skipped += 1
                        skip_file = True
                        break
                if skip_file:
                    break

            if skip_file:
                continue

            # Skip test files by filename patterns (configurable)
            test_patterns = self.config.get('repo', {}).get('test_filename_patterns', ['test_', '_test', '.test.', 'spec_', '_spec', '.spec.'])
            if any(pattern in file_name.lower() for pattern in test_patterns):
                tests_skipped += 1
                continue

            # Skip extremely large files
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            max_file_size = thresholds.get('max_file_size_bytes', 200000)
            if file_info.get('size', 0) > max_file_size:
                continue

            # Skip non-text files (binaries, images, etc.)
            if not file_info.get('is_text', False):
                continue

            # Skip documentation files by extension (.md, .rst, .txt) - for DocsAgent
            if file_ext in doc_extensions:
                doc_files_skipped += 1
                continue

            # Accept source code files (.py, .js, .java, etc.)
            if file_ext in source_code_extensions:
                processed_files.append(file_info)
                continue

            # Accept config files (all config files may be important)
            if file_ext in config_extensions:
                processed_files.append(file_info)
                continue

            # Everything else is skipped (unknown file types)

        # Report skipped files by category
        total_skipped = (doc_files_skipped + locale_files_skipped + examples_skipped +
                        tests_skipped + build_skipped + frontend_skipped + migrations_skipped)
        if total_skipped > 0:
            print(f"\n📊 [CODE_AGENT] Skipped {total_skipped} files:")
            if doc_files_skipped > 0:
                print(f"   📚 Documentation: {doc_files_skipped} files")
            if locale_files_skipped > 0:
                print(f"   🌍 Locale/i18n: {locale_files_skipped} files")
            if examples_skipped > 0:
                print(f"   📖 Examples/Tutorials: {examples_skipped} files")
            if tests_skipped > 0:
                print(f"   🧪 Tests: {tests_skipped} files")
            if build_skipped > 0:
                print(f"   🔨 Build/Cache: {build_skipped} files")
            if frontend_skipped > 0:
                print(f"   🎨 Frontend Assets: {frontend_skipped} files")
            if migrations_skipped > 0:
                print(f"   🗄️  Migrations: {migrations_skipped} files")

        print(f"🎯 [CODE_AGENT] Selected {len(processed_files)} source code files for analysis")

        # IMPORTANT: Preserve discovery order (already sorted by relevance)
        # DO NOT sort alphabetically - this destroys the relevance ranking
        sorted_files = processed_files

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

            # OPTIMIZATION: Check cache first for warm start
            if self.file_cache.enabled:
                cached_result = self.file_cache.get(file_path, content)
                if cached_result:
                    summary, cached_metrics = cached_result
                    # Return zero tokens for cache hits - no LLM call was made
                    cache_hit_metrics = {
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0,
                        'cached_tokens_saved': cached_metrics.get('total_tokens', 0)  # Track savings
                    }
                    print(f"✅ [CODE_AGENT] Cache HIT for {file_path} (saved ~{cached_metrics.get('total_tokens', 0)} tokens, ~{cached_metrics.get('total_tokens', 0)*0.01:.1f}s)")
                    return summary, cache_hit_metrics
                else:
                    print(f"📄 [CODE_AGENT] Cache MISS for {file_path} - generating with LLM ({self.llm.fast_model if hasattr(self.llm, 'fast_model') else self.llm.model})")
            else:
                print(f"📄 [CODE_AGENT] Cache DISABLED - generating summary with LLM for {file_path}")

            # Build prompt for file analysis with focus on architectural significance and technical detail
            # ENHANCED: Extract specific component names WITH LINE NUMBERS, enums, constants, and endpoints for better grounding
            # PHASE 1 FIX: Read FULL file content to avoid missing implementation details (previously limited to 4000 chars)
            # SAFETY: Intelligent sampling strategy for large files
            max_content_chars = 150000  # Increased limit - fits comfortably in Claude Haiku 200K

            if len(content) <= max_content_chars:
                # Small file - use complete content
                content_to_analyze = content
                content_truncated = False
                sampling_note = ""
            else:
                # Large file - use intelligent sampling: beginning + middle + end
                # This ensures we capture:
                # - Imports and class definitions (beginning)
                # - Core implementation logic (middle)
                # - Helper functions and utilities (end)
                chunk_size = max_content_chars // 3
                beginning = content[:chunk_size]
                middle_start = (len(content) - chunk_size) // 2
                middle = content[middle_start:middle_start + chunk_size]
                end = content[-chunk_size:]

                content_to_analyze = (
                    beginning +
                    "\n\n... [MIDDLE SECTION OMITTED] ...\n\n" +
                    middle +
                    "\n\n... [SECTION OMITTED] ...\n\n" +
                    end
                )
                content_truncated = True
                sampling_note = f"\n\nNOTE: This file is large ({len(content)} chars). Showing sampled sections:\n- Beginning: lines 1-~{len(beginning.split(chr(10)))}\n- Middle: lines ~{middle_start//50}-~{(middle_start+chunk_size)//50}\n- End: last ~{len(end.split(chr(10)))} lines\n"

            prompt = f"""Analyze this source code file and extract SPECIFIC implementation details WITH LINE NUMBERS: class names, functions, enums, constants, and API endpoints.

File: {file_path}
Content ({len(content_to_analyze)} characters{' - SAMPLED from ' + str(len(content)) if content_truncated else ' - FULL FILE'}):
{content_to_analyze}{sampling_note}

Structure Info: {structure}

CRITICAL: Your analysis will be used to determine if this file is relevant to the question: "{question}"

🔢 LINE NUMBER REQUIREMENT: For EVERY component (class, function, constant), you MUST provide the line number where it's defined in the code above. Look at the actual line numbers in the content.

🎯 IMPLEMENTATION DEPTH REQUIREMENT (CRITICAL - This is why we're reading the FULL file):
You have the COMPLETE file content. Don't just extract signatures - READ THE ACTUAL IMPLEMENTATION CODE:
- For functions: What does the body DO? What logic/algorithms? What does it return?
- For classes: What methods does it have? What's the main behavior?
- For workflows: How do components call each other? What's the execution flow?

Extract ALL of these SPECIFIC details WITH LINE NUMBERS:

1. **Class Names**: EXACT names with line numbers and WHAT THEY DO (not just "handles X")
   Example format: "UserManager (line 45): Validates user credentials against database, creates session tokens, logs login attempts"
   BAD: "UserManager (line 45): Manages users"
   GOOD: "UserManager (line 45): Validates credentials via check_password(), creates JWT tokens, updates last_login timestamp"

2. **Function Signatures**: EXACT signatures with line numbers and WHAT THE IMPLEMENTATION DOES
   Example format: "calculate_total(items, discount) (line 123): Iterates items summing prices, applies percentage discount, adds tax, returns decimal total"
   BAD: "calculate_total(items, discount) (line 123): Computes total"
   GOOD: "calculate_total(items, discount) (line 123): Sums item.price * item.quantity, applies discount percentage, adds 8.5% tax, returns Decimal"

⚡ ASYNC/BACKGROUND TASK DETECTION (CRITICAL):

You MUST identify asynchronous and background task patterns (language-agnostic). Look for:

1. **Async/Background Function Decorators**: Any decorator that suggests async/background execution
   - Examples: @async, @task, @background, @scheduled, @worker, @job
   - Report format: "task_name() (line X) - Background task that does Y"

2. **Async Function Calls**: Function calls that suggest asynchronous execution
   - Look for method chains like: obj.method(), obj.async_method(), etc.
   - Common patterns: await, async, goroutine, thread, future, promise
   - Report which functions are called asynchronously

3. **Async/Concurrent Keywords**: Language-specific async patterns
   - Python: async/await, asyncio, threading
   - JavaScript: async/await, Promise, setTimeout
   - Go: go keyword, channels
   - Java: Future, CompletableFuture, ExecutorService
   - Rust: async/await, tokio

4. **Async Library Imports**: Any async/task queue library imports
   - Include in dependencies field

If you find async patterns, MUST include in:
- functions: Mark async tasks with their decorator
- key_features: "Background task for X" or "Runs periodically every Y"
- dependencies: Include task queue library imports

3. **Enums & Constants**: EXACT enum/constant names with line numbers and their values
   Example format: "MAX_RETRY_COUNT = 3 (line 12)", "STATUS_ACTIVE = 'active' (line 67)"
   - Look for: class SomeEnum(Enum), SomeChoices = Choices(...), CONSTANT_NAME = value
   - Include state machine states if present (e.g., "ORDER_STATUS with states: PENDING, PROCESSING, COMPLETED, CANCELLED")

4. **Model Fields**: SPECIFIC model fields with types
   Example format: "User.email: EmailField (unique constraint)", "Order.total: DecimalField"

5. **API Endpoints**: EXACT URL patterns with line numbers and HTTP methods
   Example format: "POST /api/v1/users/ (line 234): Create new user", "GET /api/orders/ (line 567): List all orders"
   - Look for: path(), url(), @api_view decorators, ViewSet actions, route definitions

6. **Integration Points**: EXACT import paths and function calls with line numbers where possible
   Example format: "imports payment_service.charge() from line 15", "calls send_notification() at line 234"

🌐 EXTERNAL SYSTEM DETECTION (CRITICAL FOR GROUNDING):

You MUST distinguish between:
- **Internal code** (files/modules in this codebase)
- **External systems** (APIs, services, databases accessed via HTTP/gRPC/message queues)

If this file makes API calls to EXTERNAL systems (not internal modules), you MUST extract:

1. **External System Name**: The service/API being called
   - Look for: base URLs, API client classes, service endpoint configurations
   - Example: `BASE_URL = "https://api.example.com"` indicates external system
   - Look for: third-party SDK imports (e.g., `import stripe`, `from twilio.rest import Client`)
   - Look for: service client class names (e.g., `ExternalGradebookClient`, `CoursesAPIClient`)

2. **API Endpoint Patterns**: The specific endpoints being called WITH LINE NUMBERS
   - Look for: requests.post(), requests.get(), http.call(), API client methods
   - Look for: SDK method calls (e.g., `stripe.Customer.create()`, `s3_client.upload()`)
   - Look for: service layer methods that wrap external calls (e.g., `sync_to_external_system()`)
   - Example format: "POST /api/v1/resource/{id} (line 145) - Creates resource in external system"

3. **Authentication/Integration Config**: How this file authenticates with the external system
   - Look for: API keys, OAuth tokens, service credentials, client initialization
   - Look for: settings variables (e.g., `settings.EXTERNAL_API_KEY`, `os.getenv('API_TOKEN')`)
   - Example: "Uses API_KEY from settings (line 23) for authentication"

4. **Data Exchange Format**: What data is sent/received from external systems
   - Look for: request payloads, response parsing, data transformation for external APIs
   - Look for: serialization to external format (e.g., `to_external_format()`, `parse_external_response()`)
   - Example: "Sends user_id, action; receives status_code, result"

**Mark external integrations clearly** in "integration_points" and "dependencies" fields:
- BAD: "calls service.method()" (ambiguous - internal or external?)
- GOOD: "calls EXTERNAL API: POST /api/resource (line 145)"
- GOOD: "integrates with External System Name via SDK (line 67)"

**Common external system indicators (CHECK ALL OF THESE):**
- HTTP client usage: Any HTTP/network library (language-agnostic)
- API base URLs: URLs in code (https://, http://, api endpoints, BASE_URL constants)
- Third-party SDK imports: Any import that looks like an external service
- Custom client classes: *Client, *API, *Service classes
- Service layer abstractions: Functions with "sync", "push", "pull", "external", "fetch", "post" in their names
- Background task calls: Any async tasks that might integrate with external systems
- Message queue consumers: Any message queue operations
- Environment variables for auth: Credentials, API keys, tokens in config/environment

**CRITICAL - Don't miss these patterns:**
- Client instantiation followed by method calls - this is likely an external integration
- Imports from packages NOT part of this codebase
- Background/async tasks that call external APIs
- Wrapper functions for external system communication

🔄 ASYNC TASK CALL DETECTION (CRITICAL FOR COMPLETE FLOW ANALYSIS):

You MUST extract ALL asynchronous/background task calls in this file (language-agnostic):
- Look for ANY function/method call that appears to be asynchronous
- Common patterns to detect:
  * Method chaining: `obj.method()`, `task.execute()`, `job.run()`
  * Async keywords: await, async, .then(), go, spawn, fork
  * Queue/worker patterns: enqueue, dispatch, schedule, defer, submit

For EACH async call found, extract:
1. Function/method name being called
2. Line number where the call occurs
3. Add to "async_task_calls" field

Examples (language-agnostic):
- `sync_enrollment.delay(member_id)` at line 145 → Report: "sync_enrollment.delay() (line 145)"
- `await processData(user_id)` at line 200 → Report: "processData() (line 200)"
- `go handleRequest()` at line 67 → Report: "handleRequest() (line 67)"

This is CRITICAL because async calls often trigger integrations that happen in the background.

IMPORTANT: Return ONLY valid JSON with NO extra text before or after. All field values must be strings or arrays, NOT nested objects.

Return a JSON object with these exact fields:
{{
  "overview": "string - What makes this file architecturally significant, its role in data/request flow, and technical approach. INCLUDE specific model/class names WITH LINE NUMBERS.",
  "purpose": "string - The specific architectural role and how it fits in the overall system processing pipeline. BE SPECIFIC about what domain concepts this file handles.",
  "classes": ["array of strings - EXACT class names WITH LINE NUMBERS and WHAT THEY DO. Format: 'ClassName (line X): Detailed behavior - methods it has, what logic it implements, what it returns'. Example: 'UserManager (line 45): Validates credentials via check_password(), creates JWT tokens, updates last_login timestamp, raises AuthError on failure'"],
  "functions": ["array of strings - EXACT function signatures WITH LINE NUMBERS and IMPLEMENTATION DETAILS. Format: 'function_name(params) (line X): What the implementation does - algorithm, data transformations, return value'. Example: 'calculate_total(items, discount) (line 123): Iterates items summing item.price * item.quantity, applies discount as percentage, adds 8.5% tax rate, returns Decimal rounded to 2 places'"],
  "enums_constants": ["array of strings - EXACT enum/constant definitions WITH LINE NUMBERS, e.g., 'MAX_RETRY_COUNT = 3 (line 12)', 'STATUS_ACTIVE = \\'active\\' (line 67)', 'DEFAULT_TIMEOUT = 30 (line 89)'"],
  "model_fields": ["array of strings - SPECIFIC model fields with types, e.g., 'User.email: EmailField (unique)', 'Order.total: DecimalField'"],
  "api_endpoints": ["array of strings - EXACT URL patterns WITH LINE NUMBERS, e.g., 'POST /api/v1/users/ (line 234): Create new user', 'GET /api/orders/ (line 567): List all orders'"],
  "key_features": ["array of strings - Technical patterns, algorithms, data transformations with SPECIFIC details from the code"],
  "dependencies": ["array of strings - EXACT import paths that show integration points, e.g., 'from payment_service import process_charge', 'import redis'"],
  "data_flow": "string - How data enters this file, gets processed/transformed, and exits. Use SPECIFIC model/field names and function calls WITH LINE NUMBERS where possible.",
  "complexity": "low OR medium OR high",
  "architectural_insights": "string - Technical patterns, system design, and how this file enables the overall architecture. Mention SPECIFIC module names it integrates with.",
  "integration_points": "string - How this file connects to other system components. List SPECIFIC file paths or module names with function names and LINE NUMBERS.",
  "async_task_calls": ["array of strings - Background task calls in this file with LINE NUMBERS. Format: 'task_name.delay() (line 123)', 'task_name.apply_async() (line 456)'. Include the task function name being called. Empty array if no async task calls found."],
  "implementation_notes": "string - KEY IMPLEMENTATION DETAILS that explain HOW this file works. Include: main algorithms used, data transformation logic, control flow patterns, error handling approach, performance considerations. This field captures the 'how it actually works' that makes answers grounded."
}}

Context: {question}

Return ONLY the JSON object, no explanations before or after."""

            system_prompt = "You are a software architecture expert. Return ONLY valid JSON - no markdown, no code blocks, no explanations. All fields must be strings or arrays of strings, never nested objects. Follow the exact schema provided."

            # FIX 1: Retry loop for JSON parsing (up to 3 attempts)
            summary = None
            llm_metrics = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
            temperatures = [None, 0.3, 0.1]  # First attempt uses default, then lower temps

            for attempt in range(3):
                temp = temperatures[attempt]
                if attempt > 0:
                    print(f"🔄 [CODE_AGENT] Retry {attempt}/2 for {file_path} with temperature={temp}")

                # OPTIMIZATION: Use fast model for file summaries (10-20x speedup)
                response = self.call_llm_fast(prompt, system_prompt, temperature=temp)

                # Accumulate token metrics
                if response.get('usage'):
                    llm_metrics['prompt_tokens'] += response['usage'].get('prompt_tokens', 0)
                    llm_metrics['completion_tokens'] += response['usage'].get('completion_tokens', 0)
                    llm_metrics['total_tokens'] += response['usage'].get('total_tokens', 0)

                if response.get('success'):
                    try:
                        response_content = response.get('content', '{}')

                        # Handle markdown code blocks
                        if '```json' in response_content:
                            response_content = response_content.split('```json')[1].split('```')[0].strip()
                        elif '```' in response_content:
                            response_content = response_content.split('```')[1].split('```')[0].strip()

                        # FIX 1: Attempt JSON repair for common issues
                        response_content = self._repair_json(response_content)

                        # Try to extract JSON from response
                        start = response_content.find('{')
                        end = response_content.rfind('}') + 1
                        if start >= 0 and end > start:
                            json_str = response_content[start:end]
                            summary = json.loads(json_str)

                            if attempt > 0:
                                print(f"✅ [CODE_AGENT] Retry {attempt} successful for {file_path}")
                            break  # Success! Exit retry loop
                        else:
                            # No JSON found, will retry
                            if attempt < 2:
                                print(f"⚠️ [CODE_AGENT] No JSON braces found in attempt {attempt+1}, will retry...")
                                print(f"   Response preview: {response_content[:200]}...")
                            continue

                    except json.JSONDecodeError as e:
                        # JSON parse failed, will retry
                        if attempt < 2:
                            print(f"⚠️ [CODE_AGENT] JSON parse error in attempt {attempt+1}: {str(e)}, will retry...")
                        continue

            # After retry loop: check if we got a valid summary
            if summary:
                # VALIDATION: Check if line numbers are actually present
                has_line_numbers = self._validate_line_numbers_in_summary(summary)
                if not has_line_numbers:
                    print(f"⚠️ [CODE_AGENT] Summary missing line numbers for {file_path} - marking as incomplete")
                    summary['_line_numbers_incomplete'] = True

                # PHASE 2: ANTI-HALLUCINATION - Validate cited details exist in actual content
                # IMPORTANT: Validate against the SAME content we sent to LLM (content_to_analyze), not full content
                validation_result = self._validate_summary_against_content(summary, content_to_analyze, file_path)
                if validation_result['hallucinations_found']:
                    print(f"⚠️ [CODE_AGENT] Potential hallucinations detected in {file_path}:")
                    for issue in validation_result['issues'][:3]:  # Show first 3 issues
                        print(f"   - {issue}")
                    summary['_hallucination_warnings'] = validation_result['issues']

                # OPTIMIZATION: Store in cache for warm start (not a fallback)
                self.file_cache.put(file_path, content, summary, llm_metrics, is_fallback=False)
                quality = "PARTIAL (missing line numbers)" if not has_line_numbers else "GOOD"
                if validation_result['hallucinations_found']:
                    quality += f" + {len(validation_result['issues'])} warnings"
                print(f"💾 [CODE_AGENT] Cached summary for {file_path} (quality: {quality})")

                return summary, llm_metrics
            else:
                # All retries failed - use fallback
                print(f"❌ [CODE_AGENT] All 3 retry attempts failed for {file_path}")

                # Extract basic info from structure if available
                classes_list = []
                functions_list = []
                if structure:
                    components = structure.get('components', [])
                    classes_list = [c.get('name', '') for c in components if c.get('type') == 'class']
                    functions_list = [c.get('name', '') for c in components if c.get('type') == 'function']

                fallback_summary = {
                    'overview': f"File: {file_path} - LLM returned invalid JSON after 3 retries, using fallback",
                    'purpose': 'Pending valid LLM analysis',
                    'classes': classes_list[:10],  # Limit to 10
                    'functions': functions_list[:10],  # Limit to 10
                    'enums_constants': [],
                    'model_fields': [],
                    'api_endpoints': [],
                    'key_features': ['LLM JSON parse failed after 3 retries - will retry'],
                    'dependencies': [],
                    'complexity': 'unknown',
                    'architectural_insights': 'Invalid JSON response from LLM - scheduled for retry',
                    'data_flow': 'Unknown - pending valid analysis',
                    'integration_points': 'Unknown - pending valid analysis',
                    'async_task_calls': [],
                    'implementation_notes': 'Unknown - pending valid analysis'
                }

                # OPTIMIZATION: Store fallback in cache (will be retried after 1 hour)
                self.file_cache.put(file_path, content, fallback_summary, llm_metrics, is_fallback=True)
                print(f"⚠️ [CODE_AGENT] Cached FALLBACK summary for {file_path} (will retry in 1h)")

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
                confidence=self.get_confidence('max'),
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

        # Step 0: Detect question domain using LLM to constrain search
        domain_info = self._detect_question_domain(question)
        self.domain_info = domain_info  # Store for synthesis
        print(f"🔍 [CODE_AGENT] Question domain: {domain_info.get('domain', 'general')}")
        if domain_info.get('target_directories'):
            print(f"📂 [CODE_AGENT] Target directories: {domain_info['target_directories']}")
        if domain_info.get('external_systems'):
            print(f"🔗 [CODE_AGENT] External systems: {domain_info['external_systems']}")

        # DEBUG: Show complete domain_info
        print(f"\n🐛 [DEBUG] Domain detection complete:")
        print(f"   Domain: {domain_info.get('domain', 'N/A')}")
        print(f"   Target dirs: {domain_info.get('target_directories', [])}")
        print(f"   Priority files: {domain_info.get('priority_files', [])}")
        print(f"   Exclude patterns: {domain_info.get('exclude_patterns', [])}\n")

        # Store priority files and target directories for strict ordering enforcement during analysis
        # Normalize paths to forward slashes for consistency across platforms
        self._current_priority_files = domain_info.get('priority_files', [])
        self._current_target_directories = [d.replace('\\', '/') for d in domain_info.get('target_directories', [])]

        # Step 1: Let LLM determine search strategy based on question
        search_strategy = self._determine_search_strategy(question, domain_info)
        if not search_strategy:
            # Fallback to default strategy when LLM fails
            print(f"🔄 [CODE_AGENT] Using fallback search strategy")
            search_strategy = self._get_fallback_strategy(question)

        # Step 2: Execute targeted file discovery based on strategy
        relevant_files = self._execute_targeted_discovery(search_strategy, domain_info)
        if not relevant_files:
            return "no_relevant_files_found"

        # DEBUG: Show discovered files BEFORE Tier 0 sorting
        print(f"\n🐛 [DEBUG] Files discovered (before Tier 0 sorting): {len(relevant_files)} files")
        for i, f in enumerate(relevant_files[:10], 1):
            print(f"   {i}. {f.get('path', 'N/A')} (score: {f.get('relevance_score', 0):.2f})")
        print()

        # Step 3: Analyze only the discovered relevant files
        result = self._analyze_relevant_files(relevant_files, question)

        # DEBUG: Show which files were actually analyzed
        if hasattr(self, 'file_summaries'):
            print(f"\n🐛 [DEBUG] Files actually analyzed: {len(self.file_summaries)}")
            for i, path in enumerate(list(self.file_summaries.keys())[:10], 1):
                print(f"   {i}. {path}")
            print()

        # ENHANCEMENT: Step 4 - Iterative refinement based on initial analysis
        if result and hasattr(self, 'file_summaries') and len(self.file_summaries) > 0:
            refinement_result = self._refine_file_discovery_if_needed(question)
            if refinement_result == "additional_files_analyzed":
                print(f"✅ [CODE_AGENT] Refinement complete - now have {len(self.file_summaries)} files total")

        return result

    def _refine_file_discovery_if_needed(self, question: str) -> str:
        """Phase 2 refinement: Ask LLM if initial files are sufficient, search for missing components

        This addresses the key issue where CodeFusion analyzes wrong files by:
        1. Reviewing initial file summaries
        2. Identifying missing components/models that the question implies
        3. Performing targeted search for those specific missing components
        """
        try:
            print(f"🔄 [CODE_AGENT] Checking if refinement needed...")

            # Get summaries of files already analyzed
            analyzed_summaries = []
            for file_path, summary in list(self.file_summaries.items())[:10]:
                classes = summary.get('classes', [])
                functions = summary.get('functions', [])
                purpose = summary.get('purpose', '')
                analyzed_summaries.append(f"- {file_path}: {purpose} | Classes: {', '.join(classes[:3]) if classes else 'none'} | Functions: {', '.join(functions[:3]) if functions else 'none'}")

            analyzed_summaries_text = "\n".join(analyzed_summaries)

            prompt = f"""Question: "{question}"

Files analyzed so far ({len(self.file_summaries)} total):
{analyzed_summaries_text}

Task: Determine if we need to search for ADDITIONAL files to answer this question comprehensively.

Consider:
1. Are there specific models, classes, or functions the question implies that we HAVEN'T found yet?
2. Do the analyzed files contain the RIGHT subsystem/component for this question?
3. Based on what we've found, are there obvious MISSING pieces we should search for?

Respond with JSON only:
{{
  "need_refinement": true/false,
  "missing_components": ["specific model/class names", "specific function names", "specific file/module names"],
  "search_keywords": ["additional", "keywords", "to", "search"],
  "rationale": "Brief explanation of what's missing and why we need it"
}}

Examples of when need_refinement=true:
- Question asks about "user authentication" but files analyzed are from "user profile" subsystem
- Question mentions "email sending" but no email-related files were found
- Initial summaries mention "calls external module X" but module X wasn't analyzed

Examples of when need_refinement=false:
- Files contain the exact models/classes/functions needed to answer the question
- Analyzed files are from the correct subsystem matching the question's domain
- File summaries provide comprehensive coverage of the question's topic
"""

            response = self.call_llm(prompt, "You are a code analysis expert identifying gaps in file discovery.")

            if response.get('success'):
                content = response.get('content', '').strip()
                try:
                    import json
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_content = content[start:end]
                        refinement_data = json.loads(json_content)

                        if refinement_data.get('need_refinement'):
                            print(f"🔍 [CODE_AGENT] Refinement needed: {refinement_data.get('rationale', 'Missing components')}")
                            missing = refinement_data.get('missing_components', [])
                            keywords = refinement_data.get('search_keywords', [])

                            if missing:
                                print(f"   Missing components: {', '.join(missing[:5])}")
                            if keywords:
                                print(f"   Additional search: {', '.join(keywords[:5])}")

                            # Perform targeted search for missing components
                            additional_files = self._search_for_missing_components(missing, keywords)

                            if additional_files:
                                print(f"📄 [CODE_AGENT] Found {len(additional_files)} additional files via refinement")
                                # Analyze additional files
                                self._analyze_files_with_metrics(additional_files, question, file_type="refined file")
                                return "additional_files_analyzed"
                            else:
                                print(f"⚠️ [CODE_AGENT] No additional files found during refinement")
                                return "no_additional_files"
                        else:
                            print(f"✅ [CODE_AGENT] No refinement needed - initial files are sufficient")
                            return "refinement_not_needed"

                except json.JSONDecodeError as e:
                    print(f"⚠️ [CODE_AGENT] Failed to parse refinement JSON: {e}")

        except Exception as e:
            print(f"⚠️ [CODE_AGENT] Refinement check failed: {e}")

        return "refinement_skipped"

    def _search_for_missing_components(self, missing_components: list, search_keywords: list) -> list:
        """Search for specific missing components identified during refinement

        ENHANCED: Directory-aware search - looks for app/module names and searches in those directories
        """
        additional_files = []

        # Search for each missing component
        for component in missing_components[:5]:  # Limit to avoid excessive searches
            print(f"🔍 [CODE_AGENT] Searching for missing component: {component}")

            # Check if component looks like a directory/module name
            # Use configurable directory prefixes (from config.yaml)
            dir_prefixes = self.config.get('repo', {}).get('fallback_directory_prefixes', ['', 'src/', 'lib/'])
            potential_dirs = [f"{prefix}{component.lower()}/" for prefix in dir_prefixes]

            found_in_dir = False
            for dir_path in potential_dirs:
                # Search for any files in that directory (language-agnostic)
                # Just search for the component name itself
                search_result = self.use_tool('search_files', pattern=component, path=dir_path, max_results=5)
                if search_result and not search_result.get('error'):
                    matches = search_result.get('matches', [])
                    for match in matches:
                        file_path = match.get('file', '')
                        if file_path and file_path.startswith(dir_path) and file_path not in self.file_summaries:
                            print(f"✅ [CODE_AGENT] Found file in {component} directory: {file_path}")
                            relevance = self.config.get('agents', {}).get('thresholds', {}).get('high_relevance', 0.95)
                            additional_files.append({'path': file_path, 'relevance_score': relevance})
                            found_in_dir = True
                if found_in_dir:
                    break

            # Fallback: general search for component name
            if not found_in_dir:
                search_result = self.use_tool('search_files', pattern=component, max_results=5)
                if search_result and not search_result.get('error'):
                    matches = search_result.get('matches', [])
                    for match in matches:
                        file_path = match.get('file', '')
                        if file_path and file_path not in self.file_summaries:
                            thresholds = self.config.get('agents', {}).get('thresholds', {})
                            additional_files.append({'path': file_path, 'relevance_score': thresholds.get('low_relevance', 0.7)})

        # Also try search keywords (less specific)
        for keyword in search_keywords[:3]:
            print(f"🔍 [CODE_AGENT] Searching with refinement keyword: {keyword}")
            search_result = self.use_tool('search_files', pattern=keyword, max_results=5)
            if search_result and not search_result.get('error'):
                matches = search_result.get('matches', [])
                for match in matches:
                    file_path = match.get('file', '')
                    if file_path and file_path not in self.file_summaries:
                        # Check if not already added
                        if not any(f['path'] == file_path for f in additional_files):
                            thresholds = self.config.get('agents', {}).get('thresholds', {})
                            additional_files.append({'path': file_path, 'relevance_score': thresholds.get('minimal_relevance', 0.5)})

        return additional_files[:10]  # Limit to 10 additional files

    def _detect_question_domain(self, question: str) -> dict:
        """Use LLM to detect which subsystem/domain this question targets"""
        try:
            # Priority 5 Fix: Clarify question intent BEFORE domain detection
            # This helps avoid confusion between similar questions
            question_clarification = self._clarify_question_intent(question)

            # Store clarification for use in synthesis
            if not hasattr(self, 'question_clarification'):
                self.question_clarification = question_clarification

            # ENHANCEMENT: Extract primary keywords and find matching directories
            # This gives us repository-specific hints without hardcoding
            keyword_matched_dirs = self._find_directories_by_keywords(question)
            keyword_hint = ""
            if keyword_matched_dirs:
                keyword_hint = f"\nKeyword-matched directories (prioritize these): {', '.join(keyword_matched_dirs[:5])}\n"

            # Get repository structure overview
            repo_overview = self._get_repository_overview()

            # Use clarification to guide domain detection
            clarification_hint = ""
            if question_clarification.get('question_aspect'):
                clarification_hint = f"\nQuestion Aspect: {question_clarification['question_aspect']} - {question_clarification.get('reasoning', '')}\n"

            prompt = f"""Analyze this question about a codebase: "{question}"
{clarification_hint}{keyword_hint}

{repo_overview}

Your task: Identify which subsystem/domain of the codebase this question is about, select the MOST RELEVANT directories, and identify any external system integrations.

Respond with JSON only:
{{
    "domain": "brief domain name (e.g., 'database-layer', 'authentication', 'admin-interface', 'routing')",
    "target_directories": ["exact/path/from/list/", "another/exact/path/"],
    "priority_files": ["specific_file.ext", "another_file.ext"],
    "exclude_patterns": ["static/", "build/", "vendor/"],
    "external_systems": []
}}

Note: external_systems should list any external services/APIs detected (see EXTERNAL SYSTEMS DETECTION section below)

CRITICAL RULES:
1. target_directories MUST be copied EXACTLY from the directory list shown above
2. DO NOT modify, abbreviate, or create new paths - use ONLY the paths shown above
3. **STRONGLY PREFER keyword-matched directories shown above** - these are direct name matches from the repository
4. Select 2-5 most relevant directories that likely contain the implementation for this question
5. Focus on CORE IMPLEMENTATION directories (where the main logic/algorithms live)
6. AVOID test directories, examples, build output, vendor/third-party code, and documentation directories

DIRECTORY SELECTION STRATEGY:
1. Extract the KEY NOUNS and VERBS from the question (e.g., "tracks", "progress", "sends", "email")
2. For each directory in the list, ask yourself: "Does this directory's name suggest it IMPLEMENTS this specific functionality?"
3. Be PRECISE - avoid directories that sound related but handle different concerns
   - If question asks about "calculating/processing data" → look for "processor", "calculator", "compute" directories
   - If question asks about "displaying/presenting data" → look for "views", "templates", "ui" directories
   - If question asks about "storing data" → look for "models", "database", "storage" directories
4. When multiple directories seem related:
   - Prefer directories with MORE SPECIFIC names matching the question
   - Prefer directories that handle the PRIMARY action in the question (not secondary/related actions)
   - Check if directory names suggest they are for DISPLAY vs CALCULATION vs STORAGE
5. Use directory naming patterns to infer purpose:
   - "processor", "calculator", "engine" → computation/business logic
   - "api", "views", "controllers" → request handling/presentation
   - "models", "schema", "entities" → data definitions
   - "utils", "helpers", "common" → shared utilities (often not the main implementation)

⚠️ AVOID SEMANTIC CONFUSION - Match PRIMARY Purpose:

When multiple directories match keywords, choose based on PRIMARY action:
- **Data computation/aggregation** → "processor", "calculator", "aggregator", "analytics", "metrics"
  NOT: directories that display/track results of computation
- **Access control/permissions** → "auth", "permissions", "security", "access"
  NOT: directories that filter/scope data based on permissions
- **Background processing** → "tasks", "jobs", "workers", "queue"
  NOT: one-off scripts in "commands", "scripts", "management"
- **External integrations** → "integrations", "clients", "connectors", "external"
  NOT: internal API endpoints in "api", "views"
- **Data presentation** → "views", "templates", "serializers", "presenters"
  NOT: underlying data models
- **Business logic** → "services", "domain", "business", "core"
  NOT: infrastructure/utilities

CRITICAL: Choose the directory whose PRIMARY RESPONSIBILITY matches the question's PRIMARY ACTION.

EXTERNAL SYSTEMS DETECTION:
Identify any external system integrations mentioned or implied in the question:
- External APIs (payment processors, email services, cloud storage, analytics, etc.)
- Third-party services (Slack, messaging platforms, CRM systems, etc.)
- Task queues or message brokers (Celery, Redis, RabbitMQ, Kafka, etc.)
- External databases or data stores
- Authentication providers (OAuth, SAML, SSO, etc.)
- Monitoring/logging services
- Other microservices or external applications this system integrates with

Examples:
- "How does email delivery work?" → likely integrates with external email service
- "How does payment processing work?" → likely integrates with payment API
- "How does the system integrate with [ServiceName]?" → ServiceName is external

If external systems detected, ALSO look for directories like: "integrations/", "clients/", "connectors/", "external/", "api_clients/", "services/"

List external systems in the "external_systems" field, or empty array if none detected.

📚 DIRECTORY NAMING PATTERN HINTS (use these to guide selection):

Question Type → Look for these directory name patterns:

1. **Computation/Processing/Aggregation questions** ("How is X calculated?", "How does the system compute Y?", "How are metrics aggregated?")
   → Prefer: processor/, calculator/, compute/, engine/, aggregator/, analytics/, metrics/
   → Avoid: views/, templates/, ui/, display/

2. **Data storage/persistence questions** ("How is X stored?", "Where does data persist?", "What gets saved?")
   → Prefer: models/, storage/, database/, persistence/, repository/, dao/
   → Avoid: views/, controllers/, api/

3. **API/Request handling questions** ("How does endpoint X work?", "What happens when Y is requested?")
   → Prefer: api/, views/, controllers/, handlers/, routes/, endpoints/
   → Avoid: models/, storage/, database/

4. **Background job questions** ("How are scheduled tasks run?", "What background jobs exist?")
   → Prefer: tasks/, jobs/, workers/, queue/, scheduler/, cron/
   → Avoid: commands/, scripts/, management/ (these are typically one-off scripts)

5. **Authentication/Authorization questions** ("How does permission checking work?", "Who can access X?")
   → Prefer: auth/, permissions/, security/, access/, authorization/
   → Avoid: filters/, scoping/ (these enforce permissions but don't define them)

6. **External integration questions** ("How does the system connect to X?", "What external services are called?")
   → Prefer: integrations/, clients/, connectors/, external/, adapters/
   → Avoid: api/ (this is usually internal endpoints, not external calls)

7. **Business logic questions** ("How does the business rule X work?", "What's the workflow for Y?")
   → Prefer: services/, domain/, business/, core/, logic/
   → Avoid: utils/, helpers/, common/ (these are usually utilities)

8. **UI/Presentation questions** ("What data is displayed?", "How is X rendered?")
   → Prefer: views/, templates/, presenters/, serializers/, formatters/
   → Avoid: models/, services/ (these provide data but don't format it)

9. **Lifecycle/Flow/State transition questions** ("How does X work?", "What happens when Y?", "Life of Z")
   → MUST include: tasks/, jobs/, workers/ (background processes that complete the flow)
   → MUST include: integrations/, clients/, external/ (external systems involved in the flow)
   → Also include: models/ (state machines), signals/ (event handlers), receivers/ (signal handlers)
   → Reasoning: Lifecycle questions span multiple subsystems - main flow + async tasks + external integrations

🎯 FEW-SHOT EXAMPLES (learn from these correct mappings):

Example 1:
Question: "How does the system track user progress through levels?"
❌ WRONG: "achievements/" (tracks skill badges, not raw progress data)
✅ CORRECT: "analytics/", "metrics/", "dataprocessor/" (compute and aggregate progress metrics)
Reasoning: "Track progress" = computation/aggregation, not display of achievement badges

Example 2:
Question: "How does the scheduled email notification system work?"
❌ WRONG: "commands/" (one-off admin scripts)
✅ CORRECT: "tasks/", "jobs/", "notifications/" (recurring background processes)
Reasoning: "Scheduled" = background jobs, not one-time management commands

Example 3:
Question: "How does the system integrate with external payment APIs?"
❌ WRONG: "api/" (internal API endpoints)
✅ CORRECT: "integrations/", "payments/", "clients/" (outbound API calls)
Reasoning: "Integrate with external" = calling other services, not exposing endpoints

Example 4:
Question: "How does permission checking work for resource access?"
❌ WRONG: "filters/" (data filtering based on permissions)
✅ CORRECT: "auth/", "permissions/", "security/" (defines access rules)
Reasoning: "Permission checking" = authorization logic, not data scoping

Example 5:
Question: "How does the system compute recommendation scores?"
❌ WRONG: "recommendations/views/" (displays recommendations)
✅ CORRECT: "recommendations/engine/", "ml/", "scoring/" (computes scores)
Reasoning: "Compute scores" = calculation logic, not UI presentation

Example 6:
Question: "How does the application lifecycle work?" or "What happens when a user is enrolled?"
❌ WRONG: Only analyzing "enrollment/models/", "enrollment/views/" (misses background side effects)
✅ CORRECT: "enrollment/" + "tasks/" + "integrations/" + "signals/" (complete flow)
Reasoning: Lifecycle questions require tracing the full flow including async tasks and external system sync

IMPORTANT: Copy paths EXACTLY as shown in the directory structure above."""

            response = self.call_llm(prompt, "You are a code analysis expert identifying relevant code subsystems.")

            if response.get('success'):
                content = response.get('content', '').strip()
                try:
                    # Extract JSON from response
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_content = content[start:end]
                        domain_info = json.loads(json_content)
                        print(f"✅ [CODE_AGENT] Domain detection successful: {domain_info.get('domain', 'unknown')}")
                        print(f"   Target directories: {domain_info.get('target_directories', [])}")

                        # OPTION C: Validate domain selection against question patterns
                        validation_result = self._validate_domain_selection(question, domain_info)
                        if not validation_result['valid']:
                            print(f"⚠️ [CODE_AGENT] Domain validation warning: {validation_result['warning']}")
                            print(f"   Suggested additions: {validation_result.get('suggested_dirs', [])}")
                            # Add suggested directories (avoid duplicates)
                            if validation_result.get('suggested_dirs'):
                                existing = set(domain_info['target_directories'])
                                new_dirs = [d for d in validation_result['suggested_dirs'] if d not in existing]
                                domain_info['target_directories'].extend(new_dirs)
                                print(f"   Updated target directories: {domain_info['target_directories']}")

                        # Priority 3 Fix: Detect and prioritize integration directories
                        # If question mentions external systems, add integration directories
                        domain_info = self._detect_and_prioritize_integration_dirs(question, domain_info)

                        # Priority 1 Fix: Apply module structure validation
                        # Re-rank directories by structural validation (file presence + content sampling)
                        if domain_info.get('target_directories'):
                            validated_dirs = self._validate_module_structure(
                                question,
                                domain_info['target_directories']
                            )
                            domain_info['target_directories'] = validated_dirs

                        return domain_info
                except json.JSONDecodeError as e:
                    print(f"⚠️ [CODE_AGENT] Failed to parse domain JSON: {e}")

        except Exception as e:
            print(f"⚠️ [CODE_AGENT] Domain detection failed: {e}")

        # Fallback to general domain
        return {
            "domain": "general",
            "target_directories": [],
            "priority_files": [],
            "exclude_patterns": [],
            "external_systems": []
        }
    
    def _find_directories_by_keywords(self, question: str) -> List[str]:
        """
        Extract keywords from question and find directories with matching names.
        This is repository-agnostic - works for any codebase structure.

        Example: "How is grading calculated?" → finds "gradebook/", "grading/" directories
        """
        # Extract meaningful keywords (nouns/verbs > 4 chars, exclude common words)
        # Extract keywords from question (language-agnostic: length-based filter)
        question_lower = question.lower()
        words = [w.strip('?.,!:;') for w in question_lower.split()]
        min_len = self.config.get('agents', {}).get('thresholds', {}).get('min_keyword_length', 4)
        keywords = [w for w in words if len(w) > min_len]

        if not keywords:
            return []

        # Get all directories from repository structure
        if not hasattr(self, 'path_map') or not self.path_map:
            return []

        all_dirs = set()
        for path, metadata in self.path_map.items():
            if metadata.get('is_dir'):
                all_dirs.add(path)

        # Score directories by keyword match quality
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        score_exact = thresholds.get('score_exact_match', 100)
        score_partial = thresholds.get('score_partial_match', 50)
        score_plural = thresholds.get('score_plural_match', 80)
        score_substring = thresholds.get('score_substring_match', 30)

        scored_dirs = []
        for dir_path in all_dirs:
            dir_name = dir_path.rstrip('/').split('/')[-1].lower()
            score = 0

            # Check each keyword
            for keyword in keywords:
                # Exact match (highest score)
                if keyword == dir_name:
                    score += score_exact
                # Directory name contains keyword
                elif keyword in dir_name:
                    score += score_partial
                # Keyword is pluralized version or vice versa
                elif (keyword + 's' == dir_name or keyword + 'es' == dir_name or
                      dir_name + 's' == keyword or dir_name + 'es' == keyword):
                    score += score_plural
                # Partial match (keyword is substring)
                elif keyword in dir_name or dir_name in keyword:
                    score += score_substring

            if score > 0:
                scored_dirs.append((dir_path, score))

        # Sort by score descending
        scored_dirs.sort(key=lambda x: x[1], reverse=True)

        # Return top matches
        matched = [d[0] for d in scored_dirs[:5]]

        if matched:
            print(f"🔍 [KEYWORD_MATCH] Found directories for keywords {keywords}: {matched}")

        return matched

    def _clarify_question_intent(self, question: str, initial_domains: List[str] = None) -> Dict[str, Any]:
        """
        Priority 5 Fix: Question Understanding Feedback Loop

        Before committing to domain selection, clarify what the question is actually asking.
        Helps avoid confusion between similar questions (e.g., Q7/Q8: permissions vs data isolation).

        Returns:
            Dict with question classification and confidence score
        """
        try:
            clarification_prompt = f"""Analyze this technical question and identify:

QUESTION: "{question}"

INITIAL DOMAINS DETECTED: {initial_domains if initial_domains else 'Not yet determined'}

Classify the question along these dimensions:

1. **Primary Domain**: What subsystem/module is being asked about?
   (e.g., "authentication", "data processing", "API", "database", "background jobs", "integration")

2. **Key Entities**: What specific models/classes/components are involved?
   (e.g., ["User", "Permission", "Role"] or ["Order", "Payment", "Transaction"])

3. **Question Aspect**: What is really being asked?
   - "data_structure": How is data organized/stored?
   - "business_logic": How does a workflow/algorithm work?
   - "integration": How does system connect to external services?
   - "security": How is access controlled/permissions checked?
   - "performance": How is system optimized/scaled?
   - "lifecycle": What is the full flow/journey of an entity?

4. **Similar Confusable Questions**: What related questions could this be confused with?
   (This helps avoid mixing up Q7 "How does RBAC work?" with Q8 "How is data isolated?")

5. **Confidence**: How clear is the question? (0.0-1.0)

Return JSON only:
{{
    "primary_domain": "string - main subsystem",
    "key_entities": ["Entity1", "Entity2"],
    "question_aspect": "business_logic | data_structure | integration | security | performance | lifecycle",
    "similar_confusable_questions": ["question1", "question2"],
    "reasoning": "1-2 sentences explaining what the question is really asking",
    "confidence": 0.0-1.0
}}"""

            response = self.call_llm_fast(clarification_prompt, "You are a technical question analyzer. Return ONLY valid JSON.")

            if response.get('success'):
                content = response.get('content', '').strip()
                try:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_content = content[start:end]
                        clarification = json.loads(json_content)

                        print(f"❓ [QUESTION_CLARIFICATION] Primary aspect: {clarification.get('question_aspect')}")
                        print(f"   Domain: {clarification.get('primary_domain')}")
                        print(f"   Confidence: {clarification.get('confidence', 0):.2f}")

                        if clarification.get('confidence', 1.0) < 0.7:
                            print(f"   ⚠️  Low confidence - potential for confusion")
                            if clarification.get('similar_confusable_questions'):
                                print(f"   Could be confused with: {clarification['similar_confusable_questions']}")

                        return clarification
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            print(f"⚠️ [QUESTION_CLARIFICATION] Error: {e}")

        # Fallback if clarification fails
        return {
            'primary_domain': 'unknown',
            'key_entities': [],
            'question_aspect': 'business_logic',
            'similar_confusable_questions': [],
            'confidence': 0.5
        }

    def _validate_domain_selection(self, question: str, domain_info: dict) -> dict:
        """Use LLM to validate that selected directories match question intent"""
        try:
            target_dirs = domain_info.get('target_directories', [])

            if not target_dirs:
                return {'valid': True}  # Nothing to validate

            # Get available directories for suggestions
            available_dirs = []
            if hasattr(self, 'path_map') and self.path_map:
                # Extract unique directory paths from path_map
                dirs_set = set()
                for path, metadata in self.path_map.items():
                    if metadata.get('is_dir'):
                        dirs_set.add(path)
                available_dirs = sorted(list(dirs_set))[:50]  # Limit for prompt size

            prompt = f"""Question: "{question}"

Selected directories: {', '.join(target_dirs)}

Available directories in repo: {', '.join(available_dirs) if available_dirs else 'Not available'}

Validate if the selected directories are appropriate for answering this question.

Common mistakes to check:
- Question asks about computation/processing but selected UI/display directories
- Question asks about background jobs but selected one-off script directories
- Question asks about external integrations but selected internal API directories
- Question asks about data aggregation but selected result display/presentation directories

Respond with JSON only:
{{
  "valid": true/false,
  "reasoning": "brief explanation of why selection is good or problematic",
  "missing_patterns": ["processor", "calculator"] (directory name patterns that should be included),
  "suggested_dirs": ["specific/dir/path"] (actual directories from available list to add, or empty if valid)
}}

If the selection looks good, return valid=true with empty suggested_dirs.
If something is missing, suggest up to 3 specific directories from the available list."""

            # Use fast model for validation (simple yes/no task)
            response = self.call_llm_fast(prompt, "You are a code analysis expert. Validate directory selection for answering the question.")

            if response.get('success'):
                content = response.get('content', '').strip()
                try:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_content = content[start:end]
                        validation = json.loads(json_content)

                        if not validation.get('valid'):
                            return {
                                'valid': False,
                                'warning': validation.get('reasoning', 'Domain selection may be incomplete'),
                                'suggested_dirs': validation.get('suggested_dirs', [])
                            }

                        return {'valid': True}
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            print(f"⚠️ [CODE_AGENT] Domain validation error: {e}")

        # Fail open - don't block if validation fails
        return {'valid': True}

    def _validate_module_structure(self, question: str, candidate_dirs: List[str]) -> List[str]:
        """
        Validates candidate directories by combining file structure analysis and grep-based content search.
        Returns re-ranked directories with validation scores.

        Priority 1 Fix: Module Structure Validation
        - Checks for business logic files (not just models)
        - Uses grep to search ENTIRE files for keyword relevance (not just first 1000 chars)
        - Re-ranks directories by combined validation score
        """
        import subprocess

        if not candidate_dirs:
            return candidate_dirs

        print(f"🔍 [MODULE_VALIDATION] Validating {len(candidate_dirs)} candidate directories...")

        # Extract meaningful keywords from question (language-agnostic)
        question_lower = question.lower()
        words = [w.strip('?.,!:;') for w in question_lower.split()]
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        min_keyword_len = thresholds.get('min_keyword_length', 4)
        question_keywords = [w for w in words if len(w) > min_keyword_len]

        scored_dirs = []

        for dir_path in candidate_dirs:
            score = 0
            full_dir_path = Path(self.repo_path) / dir_path

            if not full_dir_path.exists() or not full_dir_path.is_dir():
                continue

            # PART 1: Check for code files (structural signal)
            # Language-agnostic: count any source code files in directory
            source_extensions = self.config.get('repo', {}).get('source_code_extensions', [])
            code_files = []
            for ext in source_extensions:
                code_files.extend(full_dir_path.glob(f'*{ext}'))

            # Give score based on number of source files (more files = more likely relevant)
            thresholds = self.config.get('agents', {}).get('thresholds', {})
            score_per_file = thresholds.get('score_per_source_file', 2)
            max_structure = thresholds.get('score_max_structure', 50)
            grep_multiplier = thresholds.get('score_grep_multiplier', 5)
            grep_timeout = thresholds.get('grep_timeout_seconds', 3)

            structure_score = min(len(code_files) * score_per_file, max_structure)
            score += structure_score

            # PART 2: Use grep to search ENTIRE directory for keywords (content relevance)
            grep_score = 0
            if question_keywords:
                for keyword in question_keywords:
                    try:
                        # Grep recursively, case-insensitive, count matches in entire files
                        result = subprocess.run(
                            ['grep', '-ri', keyword, str(full_dir_path)],
                            capture_output=True,
                            text=True,
                            timeout=grep_timeout
                        )

                        # Count total matches across all files
                        if result.stdout:
                            matches = len(result.stdout.splitlines())
                            grep_score += matches

                            if matches > 0:
                                print(f"   📍 '{keyword}' → {matches} matches in {dir_path}")

                    except subprocess.TimeoutExpired:
                        print(f"   ⏱️  Grep timeout for '{keyword}' in {dir_path}")
                        continue
                    except Exception as e:
                        # Silently skip grep errors (might not have grep on system)
                        continue

                # Weight grep matches higher (they indicate actual relevance)
                score += grep_score * grep_multiplier

            scored_dirs.append((dir_path, score, structure_score, grep_score))

        # Re-rank by validation score
        scored_dirs.sort(key=lambda x: x[1], reverse=True)

        # Log results
        print(f"📊 [MODULE_VALIDATION] Validation scores:")
        for dir_path, total, struct, grep_count in scored_dirs[:5]:  # Show top 5
            print(f"   {dir_path}: {total} points (structure:{struct}, grep:{grep_count})")

        return [d[0] for d in scored_dirs]

    def _detect_and_prioritize_integration_dirs(self, question: str, domain_info: dict) -> dict:
        """
        Priority 3 Fix: Enhanced External Integration Detection

        If question mentions external systems, proactively scan integration directories.
        Adds integration directories to target_directories if external question detected.
        """
        # Keywords that indicate external system questions
        EXTERNAL_SYSTEM_KEYWORDS = [
            'external', 'integration', 'api', 'third-party', 'credentials',
            'oauth', 'authentication', 'sync', 'webhook', 'callback',
            'connect', 'integrate', 'service', 'client', 'sdk',
            'slack', 'github', 'google', 'hubspot', 'sendgrid', 'twilio',
            'stripe', 'aws', 's3', 'redis', 'rabbitmq', 'kafka'
        ]

        question_lower = question.lower()
        is_external_question = any(kw in question_lower for kw in EXTERNAL_SYSTEM_KEYWORDS)

        if not is_external_question:
            return domain_info  # No changes needed

        print(f"🌐 [INTEGRATION_DETECTION] External system question detected")

        # Common integration directory patterns
        INTEGRATION_DIR_PATTERNS = [
            'integrations/', 'clients/', 'connectors/', 'external/',
            'api/external/', 'webhooks/', 'adapters/', 'services/external/',
            'management/commands/'  # Often contain integration setup
        ]

        # Find which integration directories actually exist
        existing_integration_dirs = []
        repo_path = Path(self.repo_path)

        for pattern in INTEGRATION_DIR_PATTERNS:
            # Check if directory exists (handle both absolute and relative)
            dir_path = repo_path / pattern
            if dir_path.exists() and dir_path.is_dir():
                existing_integration_dirs.append(pattern)

        if not existing_integration_dirs:
            print(f"   No integration directories found")
            return domain_info

        # Add integration directories to target_directories (avoid duplicates)
        existing_targets = set(domain_info.get('target_directories', []))
        added_count = 0

        for integration_dir in existing_integration_dirs:
            if integration_dir not in existing_targets:
                domain_info.setdefault('target_directories', []).append(integration_dir)
                print(f"   📁 Added integration directory: {integration_dir}")
                added_count += 1

        if added_count > 0:
            print(f"   ✅ Prioritized {added_count} integration directories for analysis")

        return domain_info

    def _determine_search_strategy(self, question: str, domain_info: dict) -> dict:
        """Use LLM to determine what files/patterns to look for based on question and domain"""
        try:
            # Get high-level repository overview for context
            repo_overview = self._get_repository_overview()

            # Use domain info to constrain search
            domain = domain_info.get('domain', 'general')
            target_dirs = domain_info.get('target_directories', [])
            priority_files = domain_info.get('priority_files', [])
            exclude_patterns = domain_info.get('exclude_patterns', [])

            domain_constraint = ""
            if target_dirs:
                domain_constraint = f"""
DOMAIN CONSTRAINT - Search ONLY in these directories:
{chr(10).join(f"- {d}" for d in target_dirs)}

Priority files to find: {', '.join(priority_files) if priority_files else 'any relevant files'}
"""

            prompt = f"""Based on this question about a codebase: "{question}"

Repository overview:
{repo_overview}

Detected domain: {domain}
{domain_constraint}

You must find the CORE IMPLEMENTATION SOURCE CODE files (not documentation, tutorials, or examples) to answer this question.

ALWAYS EXCLUDE:
- Documentation: docs/, documentation/, /doc/
- Examples/Tutorials: examples/, tutorials/, docs_src/, sample/, demo/
- Tests: tests/, test/, spec/, __tests__/
- Build artifacts: build/, dist/, target/, out/
- Frontend assets: static/, js/, css/, scss/, media/
- Migrations: migrations/, migrate/
- Locale: locale/, locales/, i18n/, l10n/
{chr(10).join(f"- {p}" for p in exclude_patterns) if exclude_patterns else ''}

For "{question}" - search for IMPLEMENTATION FILES only in the target directories.

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
            
            response = self.call_llm(prompt, "You are a code analysis expert. Determine optimal search strategy.")
            
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
        """Generate fallback search strategy based on question keywords

        Language-agnostic: extracts keywords from question without framework-specific assumptions
        """
        question_lower = question.lower()

        # Extract meaningful keywords from question (language-agnostic)
        words = [w.strip('?.,!:;') for w in question_lower.split()]
        thresholds = self.config.get('agents', {}).get('thresholds', {})
        min_keyword_len_fallback = thresholds.get('min_keyword_length_fallback', 3)
        keywords = [w for w in words if len(w) > min_keyword_len_fallback]

        # Use keywords for search patterns (generic wildcard matching)
        patterns = [f'*{keyword}*' for keyword in keywords]
        search_terms = keywords.copy()

        # No hardcoded directories - let the code discover them dynamically
        directories = []

        # Default: if no meaningful keywords extracted, use fallback patterns from config
        if not keywords:
            fallback_keywords = self.config.get('repo', {}).get('fallback_keywords', ['main', 'app'])
            keywords = fallback_keywords
            patterns = [f'*{keyword}*' for keyword in keywords]
        
        return {
            'keywords': keywords,  # No arbitrary limits - let LLM decide scope
            'file_patterns': patterns,  # No arbitrary limits
            'directories': directories,
            'search_terms': search_terms,
            'strategy': 'focused'
        }
    
    def _get_repository_overview(self) -> str:
        """Get repository overview showing nested directory structure"""
        if not hasattr(self, 'repo_tree'):
            return "Repository structure not available"

        # Build nested directory structure (up to 3 levels deep)
        def build_nested_paths(tree: dict, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> list:
            """Recursively build nested directory paths"""
            paths = []

            if current_depth >= max_depth:
                return paths

            for name, node in sorted(tree.items())[:20]:  # Limit to 20 items per level
                if node.get('is_dir'):
                    current_path = f"{prefix}{name}/"
                    paths.append(current_path)

                    # Recurse into subdirectories
                    if node.get('children') and current_depth < max_depth - 1:
                        sub_paths = build_nested_paths(
                            node['children'],
                            current_path,
                            max_depth,
                            current_depth + 1
                        )
                        paths.extend(sub_paths)

            return paths

        # Get nested directory structure
        nested_dirs = build_nested_paths(self.repo_tree, max_depth=3)

        # Get file type distribution
        file_types = {}
        for path, metadata in self.path_map.items():
            if not metadata['is_dir']:
                ext = metadata['extension']
                file_types[ext] = file_types.get(ext, 0) + 1

        # Build overview
        overview = "Repository Directory Structure (up to 3 levels deep):\n"
        overview += "\n".join(f"  - {path}" for path in nested_dirs[:50])  # Show up to 50 directories
        overview += f"\n\nTotal directories shown: {len(nested_dirs[:50])}"
        overview += f"\nFile types: {dict(list(file_types.items())[:5])}"

        # DEBUG: Print what directories are actually being shown
        print(f"🔍 [DEBUG] Repository overview showing {len(nested_dirs[:50])} directories:")
        for i, path in enumerate(nested_dirs[:50], 1):
            if i <= 10 or i > len(nested_dirs[:50]) - 5:  # Show first 10 and last 5
                print(f"   {i}. {path}")
            elif i == 11:
                print(f"   ... ({len(nested_dirs[:50]) - 15} more directories) ...")

        return overview
    
    def _execute_targeted_discovery(self, strategy: dict, domain_info: dict) -> list:
        """Execute targeted file discovery based on search strategy and domain constraints"""
        relevant_files = []

        # Get domain constraints
        target_directories = domain_info.get('target_directories', [])
        priority_files = domain_info.get('priority_files', [])

        print(f"🎯 [DEBUG] Target directories: {target_directories}")
        print(f"⭐ [DEBUG] Priority files: {priority_files}")

        try:
            # If we have target directories, search ONLY in those directories first
            if target_directories:
                print(f"🎯 [CODE_AGENT] Searching in {len(target_directories)} constrained directories")
                for idx, directory in enumerate(target_directories, 1):
                    print(f"\n📂 [DEBUG] Directory {idx}/{len(target_directories)}: '{directory}'")
                    dir_files = self._find_files_in_directory(directory)
                    print(f"   Found {len(dir_files)} files in this directory")
                    if dir_files:
                        print(f"   Sample files: {[f['path'] for f in dir_files[:3]]}")
                    relevant_files.extend(dir_files)

                # If we found files in target directories, prioritize them
                if relevant_files:
                    print(f"\n✅ [CODE_AGENT] Found {len(relevant_files)} files in target directories")
                    print(f"📄 [DEBUG] Sample discovered files: {[f['path'] for f in relevant_files[:5]]}")
                else:
                    print(f"\n⚠️ [CODE_AGENT] No files found in target directories, expanding search")

            # If no target directories or no files found, use broader search
            if not relevant_files:
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

                # Search in strategy-specified directories
                directories = strategy.get('directories', [])
                for directory in directories:
                    dir_files = self._find_files_in_directory(directory)
                    relevant_files.extend(dir_files)

                # Search by content if search terms provided
                search_terms = strategy.get('search_terms', [])
                if search_terms:
                    content_files = self._find_files_by_content(search_terms)
                    relevant_files.extend(content_files)

            # Remove duplicates
            unique_files = list({f['path']: f for f in relevant_files}.values())

            # Sort by priority files if specified
            if priority_files:
                unique_files = self._sort_by_priority(unique_files, priority_files)

            print(f"📁 [CODE_AGENT] Found {len(unique_files)} relevant files")
            return unique_files

        except Exception as e:
            print(f"❌ [CODE_AGENT] Targeted discovery failed: {e}")
            return []

    def _sort_by_priority(self, files: list, priority_files: list) -> list:
        """Sort files so priority files come first"""
        priority_set = set(priority_files)

        # Separate priority and non-priority files
        priority = []
        non_priority = []

        for file_info in files:
            # Paths are normalized to forward slashes
            file_path = file_info['path']
            file_name = file_path.split('/')[-1] if '/' in file_path else file_path
            if any(pf in file_name for pf in priority_set):
                priority.append(file_info)
            else:
                non_priority.append(file_info)

        # Priority files first, then the rest
        sorted_files = priority + non_priority

        if priority:
            print(f"⭐ [CODE_AGENT] Prioritized {len(priority)} files: {[f['path'].split('/')[-1] if '/' in f['path'] else f['path'] for f in priority[:5]]}")

        return sorted_files

    def _find_files_by_keyword(self, keyword: str) -> list:
        """Find files containing keyword in path (excludes non-source directories)"""
        matching_files = []
        excluded_patterns = self.config.get('repo', {}).get('code_agent_excluded_patterns', {})

        for path, metadata in self.path_map.items():
            if metadata['is_dir']:
                continue

            if keyword.lower() not in path.lower():
                continue

            # Skip if path matches any exclusion pattern
            path_lower = path.lower()
            should_exclude = False
            for category, patterns in excluded_patterns.items():
                if any(pattern in path_lower for pattern in patterns):
                    should_exclude = True
                    break

            if not should_exclude:
                # Normalize path to forward slashes for consistency across platforms
                normalized_path = path.replace('\\', '/')
                matching_files.append({
                    'path': normalized_path,
                    'size': metadata['size'],
                    'extension': metadata['extension'],
                    'is_text': metadata['is_text']
                })
        return matching_files
    
    def _find_files_by_pattern(self, pattern: str) -> list:
        """Find files matching pattern (excludes non-source directories)"""
        matching_files = []
        excluded_patterns = self.config.get('repo', {}).get('code_agent_excluded_patterns', {})

        for path, metadata in self.path_map.items():
            if metadata['is_dir']:
                continue

            if not fnmatch.fnmatch(path, pattern):
                continue

            # Skip if path matches any exclusion pattern
            path_lower = path.lower()
            should_exclude = False
            for category, patterns in excluded_patterns.items():
                if any(excl_pattern in path_lower for excl_pattern in patterns):
                    should_exclude = True
                    break

            if not should_exclude:
                # Normalize path to forward slashes for consistency across platforms
                normalized_path = path.replace('\\', '/')
                matching_files.append({
                    'path': normalized_path,
                    'size': metadata['size'],
                    'extension': metadata['extension'],
                    'is_text': metadata['is_text']
                })
        return matching_files
    
    def _find_files_in_directory(self, directory: str) -> list:
        """Find files in specific directory (excludes non-source subdirectories)"""
        matching_files = []
        excluded_patterns = self.config.get('repo', {}).get('code_agent_excluded_patterns', {})

        # Normalize directory path (remove trailing slashes, normalize separators)
        normalized_dir = directory.rstrip('/').rstrip('\\')

        # DEBUG: Log what we're searching for
        print(f"🔍 [DEBUG] Searching for files in directory: '{normalized_dir}'")
        print(f"🔍 [DEBUG] Total files in path_map: {len([p for p in self.path_map if not self.path_map[p]['is_dir']])}")

        # DEBUG: Show sample paths from path_map to verify structure
        sample_paths = [p for p in list(self.path_map.keys())[:20] if not self.path_map[p].get('is_dir', False)]
        print(f"🔍 [DEBUG] Sample file paths in path_map: {sample_paths[:5]}")

        files_checked = 0
        files_matched = 0

        for path, metadata in self.path_map.items():
            if metadata['is_dir']:
                continue

            files_checked += 1

            # Normalize path for comparison
            normalized_path = path.replace('\\', '/')

            # Check if path is in the target directory
            # Match both "src/db/models/query.go" for "src/db/models"
            # and "src/db/models/sql/query.go" for "src/db/models"
            if not (normalized_path.startswith(normalized_dir + '/') or
                    normalized_path == normalized_dir):
                continue

            files_matched += 1

            # Skip if path matches any exclusion pattern
            path_lower = path.lower()
            should_exclude = False
            excluded_category = None
            for category, patterns in excluded_patterns.items():
                if any(pattern in path_lower for pattern in patterns):
                    should_exclude = True
                    excluded_category = category
                    break

            if should_exclude:
                if files_matched <= 5:  # Debug first few matches
                    print(f"   ⏭️  Excluded {path} (category: {excluded_category})")
                continue

            if len(matching_files) < 5:  # Debug first few matches
                print(f"   ✅ Matched {path}")

            # Normalize path to forward slashes for consistency across platforms
            normalized_path = path.replace('\\', '/')
            matching_files.append({
                'path': normalized_path,
                'size': metadata['size'],
                'extension': metadata['extension'],
                'is_text': metadata['is_text']
            })

        print(f"🔍 [DEBUG] Files checked: {files_checked}, matched dir: {files_matched}, after exclusions: {len(matching_files)}")
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
    
    def _analyze_relevant_files(self, relevant_files: list, question: str, files_already_analyzed: int = 0, filtered_files: list = None) -> str:
        """Analyze only the relevant files discovered through question-focused search

        Args:
            relevant_files: List of file metadata dictionaries (used only on first call)
            question: The user's question
            files_already_analyzed: Number of files already analyzed (for conditional expansion)
            filtered_files: Pre-filtered and pre-prioritized files (used on recursive call to avoid redundant work)
        """
        self.discovered_files = relevant_files  # Set for compatibility with existing code

        # Only filter and prioritize on the FIRST call (files_already_analyzed == 0)
        # On recursive calls, we receive pre-filtered and pre-prioritized files
        if files_already_analyzed == 0:
            # First call - must filter and prioritize
            # Apply filtering to ensure we only analyze source code files, not documentation
            filtered_files = self._filter_important_files(relevant_files)

            if len(filtered_files) != len(relevant_files):
                skipped_count = len(relevant_files) - len(filtered_files)
                print(f"📚 [CODE_AGENT] Filtered out {skipped_count} documentation files from question-focused discovery")

            # TIERED PRIORITY ENFORCEMENT: Critical files analyzed FIRST
            # Tier 0: Exact path + filename matches (highest priority - most specific)
            # Tier 1: Exact filename matches (high priority)
            # Tier 2: Path segment matches (medium priority)
            if hasattr(self, '_current_priority_files') and self._current_priority_files:
                priority_set = set(self._current_priority_files)
                tier0_exact_path = []  # Exact path + filename matches (most specific)
                tier1_critical = []  # Exact filename matches
                tier2_implementation = []  # Path segment matches
                non_priority = []

                # First pass: identify target directories from domain detection and normalize them
                target_dirs = set()
                if hasattr(self, '_current_target_directories'):
                    # Remove trailing slashes (paths already normalized to forward slashes)
                    target_dirs = {d.rstrip('/') for d in self._current_target_directories}

                # Sort target directories by path length (longer = more specific)
                # This ensures subdirectories are checked before parent directories
                # Example: domain/api/ checked before domain/, preventing premature matches
                sorted_target_dirs = sorted(target_dirs, key=lambda d: len(d), reverse=True)

                # Optimization: Build lookup set for O(1) tier 0 checking
                # For each priority file, track which target directories it could be in
                tier0_lookup = {}  # Maps (file_name, file_dir) -> True for O(1) lookup
                for pf in priority_set:
                    for target_dir in target_dirs:
                        # Any file named 'pf' in 'target_dir' is Tier 0
                        tier0_lookup[(pf, target_dir)] = True

                # DEBUG: Show Tier 0 lookup configuration
                print(f"\n🐛 [DEBUG] Tier 0 configuration:")
                print(f"   Priority files: {list(priority_set)[:5]}")
                print(f"   Target dirs: {list(sorted_target_dirs)[:5]}")
                print(f"   Tier 0 lookup entries: {len(tier0_lookup)}")
                if tier0_lookup:
                    print(f"   Example entries: {list(tier0_lookup.keys())[:3]}")
                print()



                # DEBUG: Show first 5 files being checked
                print(f"\n🐛 [DEBUG] Checking first 5 files for Tier 0 matching:")
                for idx, file_info in enumerate(filtered_files[:5]):
                    file_path = file_info['path']
                    if '/' in file_path:
                        path_parts = file_path.split('/')
                        file_name = path_parts[-1]
                        file_dir = '/'.join(path_parts[:-1])
                    else:
                        file_name = file_path
                        file_dir = ''

                    print(f"   File {idx+1}: {file_path}")
                    print(f"      file_name: '{file_name}'")
                    print(f"      file_dir: '{file_dir}'")
                    print(f"      in priority_set: {file_name in priority_set}")
                    print(f"      (file_name, file_dir) in tier0_lookup: {(file_name, file_dir) in tier0_lookup}")

                    # Check subdir matching
                    for target_dir in sorted_target_dirs:
                        starts_with = file_path.startswith(target_dir + '/')
                        if starts_with or (file_name in priority_set):
                            print(f"      checking {target_dir}/: startswith={starts_with}, priority={file_name in priority_set}, would_match={starts_with and file_name in priority_set}")
                print()

                for file_info in filtered_files:
                    file_path = file_info['path']
                    # Paths are normalized to forward slashes, use string operations
                    # Split once and reuse for efficiency
                    if '/' in file_path:
                        path_parts = file_path.split('/')
                        file_name = path_parts[-1]
                        file_dir = '/'.join(path_parts[:-1])
                    else:
                        file_name = file_path
                        file_dir = ''

                    # ANTI-PATTERN: Penalize generic/utility modules to avoid analyzing wrong files
                    # Generic modules (from config) often match keywords
                    # but provide low-quality results compared to specific domain modules
                    generic_module_indicators = self.config.get('repo', {}).get('generic_module_names', [])
                    is_generic_module = any(indicator in file_path.lower() for indicator in generic_module_indicators)

                    # Determine priority tier using optimized lookups
                    matched_tier = None

                    # TIER 0: O(1) lookup for exact path + filename in target directories
                    if (file_name, file_dir) in tier0_lookup:
                        matched_tier = 0
                        print(f"      🏆 MATCHED Tier 0 (exact): {file_path}")
                    else:
                        # Check subdirectories (file_path starts with target_dir)
                        # Use sorted list to check most specific directories first
                        for target_dir in sorted_target_dirs:
                            # All paths normalized to forward slashes for consistency
                            if file_name in priority_set and file_path.startswith(target_dir + '/'):
                                matched_tier = 0
                                print(f"      🏆 MATCHED Tier 0 (subdir): {file_path} (in {target_dir}/)")
                                break

                    # TIER 1 & 2: Check only if not Tier 0
                    if matched_tier is None:
                        # TIER 1: O(1) exact filename match using set lookup
                        if file_name in priority_set:
                            # DOWNGRADE: If it's a generic module but matched keywords, demote to Tier 2
                            if is_generic_module:
                                matched_tier = 2
                                print(f"      ⚠️  DEMOTED Tier 1→2 (generic module): {file_path}")
                            else:
                                matched_tier = 1
                                print(f"      ⚡ MATCHED Tier 1 (filename match)")
                        else:
                            # TIER 2: Path segment match (requires loop)
                            for pf in priority_set:
                                if pf in file_path:
                                    matched_tier = 2
                                    print(f"      📍 MATCHED Tier 2 (path segment '{pf}')")
                                    break

                    # Assign to appropriate tier
                    if matched_tier == 0:
                        tier0_exact_path.append(file_info)
                    elif matched_tier == 1:
                        tier1_critical.append(file_info)
                    elif matched_tier == 2:
                        tier2_implementation.append(file_info)
                    else:
                        non_priority.append(file_info)

                # Reorder: Tier 0 → Tier 1 → Tier 2 → Non-priority
                if tier0_exact_path or tier1_critical or tier2_implementation:
                    filtered_files = tier0_exact_path + tier1_critical + tier2_implementation + non_priority
                    print(f"⭐ [CODE_AGENT] TIERED PRIORITY ENFORCEMENT:")
                    if tier0_exact_path:
                        print(f"   🏆 Tier 0 (Exact Match): {len(tier0_exact_path)} files - {[f['path'] for f in tier0_exact_path[:5]]}")
                    if tier1_critical:
                        print(f"   🥇 Tier 1 (Critical): {len(tier1_critical)} files - {[f['path'] for f in tier1_critical[:5]]}")
                    if tier2_implementation:
                        print(f"   🥈 Tier 2 (Implementation): {len(tier2_implementation)} files - {[f['path'] for f in tier2_implementation[:5]]}")
        else:
            # Recursive call - filtered_files should have been passed
            if filtered_files is None:
                # Safety fallback: this should never happen, but filter if needed
                print(f"⚠️ [CODE_AGENT] Warning: filtered_files is None on recursive call, filtering now...")
                filtered_files = self._filter_important_files(relevant_files)

        # Apply configurable file limit with conditional expansion
        max_files = self.config.get('repo', {}).get('max_analysis_files', 50)

        # Determine which files to analyze in this batch
        if files_already_analyzed == 0:
            # First batch: analyze files 0 to max_files
            files_to_analyze = filtered_files[:max_files]
            remaining_files = filtered_files[max_files:]

            if len(filtered_files) > max_files:
                print(f"⚡ [CODE_AGENT] Limiting to {max_files} files for initial analysis ({len(remaining_files)} remaining)")
        else:
            # Expansion batch: analyze NEXT batch of files beyond what was already analyzed
            # Use configurable expansion size (default 20 files)
            expansion_size = self.config.get('repo', {}).get('expansion_files', 20)
            start_idx = files_already_analyzed
            end_idx = files_already_analyzed + expansion_size
            files_to_analyze = filtered_files[start_idx:end_idx]
            remaining_files = filtered_files[end_idx:]

            print(f"🔄 [CODE_AGENT] EXPANDING: Analyzing {len(files_to_analyze)} additional files (#{start_idx+1} to #{end_idx})")
            if files_to_analyze:
                print(f"   Additional files: {[f['path'] for f in files_to_analyze[:5]]}")

        # Analyze this batch of files
        result = self._analyze_files_with_metrics(files_to_analyze, question, "relevant file")

        # CONDITIONAL EXPANSION: Check if we should analyze more files
        # Only expand once (after initial batch) and only if we have remaining files
        if files_already_analyzed == 0 and len(remaining_files) > 0:
            # Check if the analyzed files are relevant using LLM
            if hasattr(self, 'file_summaries') and self.file_summaries:
                file_paths = list(self.file_summaries.keys())
                print(f"🔍 [CODE_AGENT] Validating relevance of {len(file_paths)} analyzed files...")

                relevance_check = self._llm_validate_file_relevance(question, file_paths)

                if not relevance_check.get('is_relevant', True):
                    print(f"⚠️ [CODE_AGENT] Initial batch NOT relevant - analyzing 20 more files...")
                    print(f"   Reason: {relevance_check.get('reason', 'Unknown')}")

                    # DON'T clear file_summaries - keep what we have and add more
                    # Recursively analyze the next batch (files 51-70)
                    # Pass filtered_files to skip re-filtering and re-prioritizing
                    return self._analyze_relevant_files(relevant_files, question, files_already_analyzed=max_files, filtered_files=filtered_files)

        return result
    
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
                            confidence=self.get_confidence('high'),
                            source=f"question_focused_analysis_{file_path}"
                        )
                    elif file_summary.get('key_features') and len(file_summary['key_features']) > 0:
                        # Fallback to key features if architectural insights are missing
                        key_feature = file_summary['key_features'][0]
                        if key_feature and not any(generic in key_feature.lower() for generic in ['initializes', 'defines', 'contains', 'implements']):
                            self.add_insight(
                                f"File {file_path}: {key_feature}",
                                confidence=self.get_confidence('low'),
                                source=f"feature_analysis_{file_path}"
                            )
                else:
                    print(f"❌ [CODE_AGENT] In _analyze_files_with_metrics. Failed to summarize {file_path}")
                    
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

        # TASK FOLLOWING: Extract async task calls and find corresponding task files
        # Only follow tasks once per analysis to avoid infinite recursion
        if file_type != "task file":  # Don't follow tasks from task files
            task_files_to_analyze = self._extract_and_find_task_files()

            if task_files_to_analyze:
                print(f"\n🔄 [TASK_FOLLOWING] Found {len(task_files_to_analyze)} task files to analyze from async calls")
                # Recursively analyze task files (depth = 1, won't follow further)
                self._analyze_files_with_metrics(task_files_to_analyze, question, file_type="task file")

        # Priority 2 Fix: AUTO-INCLUDE COMPANION FILES
        # After analyzing files, check for companion logic files
        if file_type == "relevant file":  # Only for initial batch, not for recursively added files
            companion_files = self._find_companion_files()
            if companion_files:
                print(f"\n🔗 [COMPANION_FILES] Found {len(companion_files)} companion files to analyze")
                # Recursively analyze companion files
                self._analyze_files_with_metrics(companion_files, question, file_type="companion file")

        if analyzed_count > 0:
            self.add_insight(
                f"Question-focused analysis completed: {analyzed_count} relevant files analyzed",
                confidence=self.get_confidence('max'),
                source="question_focused_complete"
            )
            return "question_focused_analysis_complete"
        else:
            return "no_files_analyzed"

    def _extract_and_find_task_files(self) -> list:
        """Extract async task calls from analyzed files and find corresponding task definition files

        Returns:
            List of file_info dicts for task files to analyze
        """
        if not hasattr(self, 'file_summaries') or not self.file_summaries:
            return []

        # Track which files we've already analyzed to avoid re-analysis
        analyzed_paths = set(self.file_summaries.keys())

        # Extract all task function names called in analyzed files
        task_functions_called = set()

        for file_path, summary in self.file_summaries.items():
            async_task_calls = summary.get('async_task_calls', [])
            if not async_task_calls:
                continue

            for task_call in async_task_calls:
                # Extract function name from async task calls (language-agnostic)
                # Examples: "task_name.method() (line 145)", "await task_name() (line 200)", "go task_name() (line 67)"
                import re
                # Pattern 1: obj.method() format
                match = re.match(r'(\w+)\.(\w+)\(\)', task_call)
                if match:
                    task_name = match.group(1)
                    task_functions_called.add(task_name)
                    print(f"🔄 [TASK_FOLLOWING] Found async call: {task_name} in {file_path}")
                    continue

                # Pattern 2: function() format (with optional await/go prefix)
                match = re.match(r'(?:await\s+|go\s+)?(\w+)\(\)', task_call)
                if match:
                    task_name = match.group(1)
                    task_functions_called.add(task_name)
                    print(f"🔄 [TASK_FOLLOWING] Found async call: {task_name} in {file_path}")

        if not task_functions_called:
            print("🔄 [TASK_FOLLOWING] No async task calls found in analyzed files")
            return []

        print(f"🔄 [TASK_FOLLOWING] Searching for {len(task_functions_called)} task definitions: {list(task_functions_called)[:5]}")

        # Find files that likely define these tasks
        task_files_to_analyze = []

        # Language-agnostic: Look for files containing the called function definitions
        # No hardcoded filename patterns

        if hasattr(self, 'structure') and self.structure:
            all_files = self.structure.get('all_files', [])
            source_extensions = set(self.config.get('repo', {}).get('source_code_extensions', []))

            for file_info in all_files:
                file_path = file_info.get('path', '')

                # Skip already analyzed files
                if file_path in analyzed_paths:
                    continue

                # Only check source code files
                file_ext = Path(file_path).suffix
                if file_ext not in source_extensions:
                    continue

                # Read file and check if any called functions are defined here
                try:
                    file_result = self.use_tool('read_file', file_path=file_path, include_structure=False)
                    if not file_result.get('error'):
                        content = file_result.get('content', '')
                        # Check if any task function is defined here
                        # Language-agnostic patterns for function definitions
                        for task_name in task_functions_called:
                            # Generic function definition patterns:
                            # - Python/Ruby: "def task_name("
                            # - JavaScript/TypeScript: "function task_name(" or "const task_name ="
                            # - Java/C++: "type task_name("
                            # - Go: "func task_name("
                            if any(pattern in content for pattern in [
                                f"def {task_name}(",
                                f"function {task_name}(",
                                f"const {task_name} =",
                                f"func {task_name}(",
                                f" {task_name}("  # Generic: any declaration with task_name(
                            ]):
                                print(f"✅ [TASK_FOLLOWING] Found function definition: {task_name} in {file_path}")
                                task_files_to_analyze.append(file_info)
                                analyzed_paths.add(file_path)  # Mark as will-be-analyzed
                                break  # Found a match, add this file
                except Exception as e:
                    print(f"⚠️ [TASK_FOLLOWING] Error checking {file_path}: {e}")
                    continue

                    # Limit task files to avoid explosion
                    thresholds = self.config.get('agents', {}).get('thresholds', {})
                    max_task_files = thresholds.get('max_task_files', 5)
                    if len(task_files_to_analyze) >= max_task_files:
                        break

        return task_files_to_analyze

    def _find_companion_files(self) -> list:
        """
        Priority 2 Fix: Auto-include companion logic files

        When data files are analyzed, automatically include companion files like:
        - utils, helpers, services (business logic)
        - processors, handlers (data processing)

        Returns:
            List of file_info dicts for companion files to analyze
        """
        if not hasattr(self, 'file_summaries') or not self.file_summaries:
            return []

        # Language-agnostic companion file discovery:
        # Instead of hardcoded patterns, find files in the same directory
        # that haven't been analyzed yet

        analyzed_paths = set(self.file_summaries.keys())
        companion_files_to_add = []
        source_extensions = set(self.config.get('repo', {}).get('source_code_extensions', []))

        # For each analyzed file, check for unanalyzed files in same directory
        analyzed_dirs = set()
        for analyzed_file_path in analyzed_paths:
            dir_path = Path(analyzed_file_path).parent
            analyzed_dirs.add(dir_path)

        # For each directory with analyzed files, find unanalyzed source files
        for dir_path in analyzed_dirs:
            if not dir_path.exists():
                continue

            # Get all source files in this directory
            for file_path in dir_path.iterdir():
                if not file_path.is_file():
                    continue

                # Check if it's a source code file
                if file_path.suffix not in source_extensions:
                    continue

                file_path_str = str(file_path)

                # Skip if already analyzed
                if file_path_str in analyzed_paths:
                    continue

                # Add as companion file
                file_info = {'path': file_path_str}

                # Try to get metadata from structure if available
                if hasattr(self, 'structure') and self.structure:
                    all_files = self.structure.get('all_files', [])
                    for f in all_files:
                        if f.get('path') == file_path_str:
                            file_info = f
                            break

                companion_files_to_add.append(file_info)
                print(f"🔗 [COMPANION_FILES] Adding unanalyzed file {file_path.name} from directory {dir_path.name}")

        return companion_files_to_add

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
        print(f"🎯 [CODE_AGENT] Initializing conversation for feature flow analysis...: {question}")
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
        print(f"🎯 [CODE_AGENT] Initializing conversation for feature flow analysis...: {question}\n {system_message}\n {user_message}")
        self.conversation_history = [system_message, user_message]
