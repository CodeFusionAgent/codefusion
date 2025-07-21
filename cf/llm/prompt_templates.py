"""
Template-based prompt generation for LLM interactions.
"""

from typing import Dict, Any, List


class PromptTemplate:
    """Base class for prompt templates."""
    
    def __init__(self, template: str, is_llama_compatible: bool = True):
        self.template = template
        self.is_llama_compatible = is_llama_compatible
    
    def format(self, **kwargs) -> str:
        """Format the template with provided variables."""
        formatted = self.template.format(**kwargs)
        return formatted
    
    def format_for_model(self, model_name: str, **kwargs) -> str:
        """Format the template for a specific model."""
        formatted = self.format(**kwargs)
        
        # Check if this is a LLaMA model for special formatting
        if self.is_llama_compatible and any(llama_indicator in model_name.lower() 
                                           for llama_indicator in ['llama', 'meta-llama']):
            return f"<s>[INST] {formatted} [/INST]"
        
        return formatted


# Reasoning prompt template
REASONING_TEMPLATE = PromptTemplate("""
You are a {agent_type} agent in a ReAct (Reasoning + Acting) framework analyzing a codebase.

Your task is to reason about what action to take next based on the current context and goal. **Think like a senior developer exploring an unfamiliar codebase** - be curious, methodical, and adaptive to whatever architecture you discover.

CONTEXT:
{context}

QUESTION/GOAL:
{question}

**Reasoning Guidelines:**
- Start broad, then narrow down based on what you find
- Look for patterns in filenames, directory structures, and code organization  
- When you find interesting files, read and analyze them deeply
- Build understanding progressively rather than making assumptions
- Be adaptive - every codebase has unique architecture and patterns

Please provide your reasoning following this structure:
1. REASONING: What should I do next and why? Think step-by-step about exploration strategy.
2. CONFIDENCE: How confident are you in this reasoning (0.0-1.0)?  
3. SUGGESTED_ACTIONS: List of 2-3 specific actions to take next
4. CONTEXT_ANALYSIS: Key insights from current context and what they suggest about the architecture

Format your response as JSON with these keys: reasoning, confidence, suggested_actions, context_analysis.

Focus on being systematic, thorough, and adaptive based on what you've learned so far.
""".strip())


# Summary prompt template
SUMMARY_TEMPLATE = PromptTemplate("""
You are analyzing codebase content and need to generate a {summary_type} summary with focus on {focus}.

CONTENT TO SUMMARIZE:
{content}

Please provide a comprehensive summary following this structure:
1. SUMMARY: Clear, concise summary of the key findings
2. KEY_POINTS: List of 3-5 most important points
3. CONFIDENCE: How confident are you in this summary (0.0-1.0)?
4. CONTENT_ANALYSIS: Additional insights about the content

Format your response as JSON with these keys: summary, key_points, confidence, content_analysis.

Focus on extracting the most valuable insights and presenting them clearly.
""".strip())


# Life of X narrative prompt template
LIFE_OF_X_TEMPLATE = PromptTemplate("""
You are a senior software architect creating a technical "Life of {key_entity}" architectural overview following this feature/request through the entire system.

QUESTION: {question}

SYSTEM INSIGHTS:
{insights}

SYSTEM COMPONENTS:
{components}

DATA/CONTROL FLOWS:
{flows}

CODE EXAMPLES (with function signatures and class details):
{code_examples}

**CRITICAL**: If code_examples are limited, be honest about the limitations but work with whatever architectural insights are available. Suggest what additional exploration would be valuable based on the patterns you observe in the provided data.

Create a technical "Life of {key_entity}" architectural analysis that:

1. **NARRATIVE**: Provide a comprehensive architectural overview that traces the {key_entity} through the entire system from initiation to completion. Discover and explain the actual architecture by analyzing the provided insights, components, flows, and code examples. **Be adaptive** - work with whatever code structure exists rather than assuming specific frameworks. **Include concrete references** to actual function names, class names, file structures, and implementation patterns found in the code examples. Focus on understanding the unique architecture of THIS specific codebase.

2. **JOURNEY_STAGES**: Break down the technical flow into clear stages (e.g., "Request Reception", "Routing & Validation", "Business Logic Processing", "Data Persistence", "Response Generation") with technical explanations of what happens at each stage. **Where possible, reference specific functions or classes from the code examples** that handle each stage.

3. **KEY_COMPONENTS**: List the most important system components, services, modules, or layers involved in this flow and their architectural roles. **Map these to actual code files and classes from the examples** when available.

4. **FLOW_SUMMARY**: Provide a concise technical summary of the overall architectural flow, patterns, and design principles. **Include references to concrete implementation patterns** visible in the code examples.

5. **CODE_INSIGHTS**: Extract key technical insights from the code examples that demonstrate how this architecture is implemented. **Be specific about:**
   - Function signatures that show data transformations
   - Class hierarchies that reveal architectural patterns
   - Implementation details that demonstrate design decisions
   - Code patterns that illustrate system behavior
   - Actual code snippets that support the architectural narrative

6. **CONFIDENCE**: Your confidence level (0.0-1.0) in this architectural analysis.

Format your response as JSON with these keys: narrative, journey_stages, key_components, flow_summary, code_insights, confidence.

**IMPORTANT**: Make extensive use of the provided code examples to ground your architectural analysis in concrete implementation details. Reference specific function names, class names, method signatures, and code patterns throughout your response. This should be a code-informed architectural analysis, not just high-level theoretical discussion.

Focus on technical accuracy and architectural clarity - imagine explaining the system design to a senior developer who needs to understand both the theoretical architecture AND the actual implementation details.
""".strip())


class PromptBuilder:
    """Simplified prompt builder using templates."""
    
    def __init__(self):
        self.templates = {
            'reasoning': REASONING_TEMPLATE,
            'summary': SUMMARY_TEMPLATE,
            'life_of_x': LIFE_OF_X_TEMPLATE
        }
    
    def build_reasoning_prompt(self, context: str, question: str, agent_type: str, model_name: str) -> str:
        """Build reasoning prompt."""
        return self.templates['reasoning'].format_for_model(
            model_name=model_name,
            context=context,
            question=question,
            agent_type=agent_type
        )
    
    def build_summary_prompt(self, content: str, summary_type: str, focus: str, model_name: str) -> str:
        """Build summary prompt."""
        return self.templates['summary'].format_for_model(
            model_name=model_name,
            content=content,
            summary_type=summary_type,
            focus=focus
        )
    
    def build_life_of_x_prompt(self, question: str, insights: str, components: str, 
                              flows: str, code_examples: str, key_entity: str, model_name: str) -> str:
        """Build Life of X prompt."""
        return self.templates['life_of_x'].format_for_model(
            model_name=model_name,
            question=question,
            insights=insights,
            components=components,
            flows=flows,
            code_examples=code_examples,
            key_entity=key_entity
        )
    
    def format_insights(self, insights: Dict[str, Any]) -> str:
        """Format insights for the prompt."""
        if not insights:
            return "No specific insights available."
        
        formatted = []
        for agent_name, agent_insights in insights.items():
            if isinstance(agent_insights, dict):
                summary = agent_insights.get('summary', '')
                if summary:
                    formatted.append(f"- {agent_name.title()}: {summary}")
        
        return "\n".join(formatted) if formatted else "No insights available."
    
    def format_components(self, components: List[Dict]) -> str:
        """Format components for the prompt."""
        if not components:
            return "No components identified."
        
        formatted = []
        for comp in components[:10]:  # Limit to top 10 components
            name = comp.get('name', 'Unknown')
            comp_type = comp.get('type', 'unknown')
            description = comp.get('description', '')
            formatted.append(f"- {name} ({comp_type}): {description}")
        
        return "\n".join(formatted) if formatted else "No components available."
    
    def format_flows(self, flows: List[Dict]) -> str:
        """Format flows for the prompt."""
        if not flows:
            return "No data flows identified."
        
        formatted = []
        for flow in flows[:15]:  # Limit to top 15 flows
            source = flow.get('source', 'Unknown')
            target = flow.get('target', 'Unknown')
            flow_type = flow.get('flow_type', 'unknown')
            description = flow.get('description', '')
            formatted.append(f"- {source} -> {target} ({flow_type}): {description}")
        
        return "\n".join(formatted) if formatted else "No flows available."
    
    def format_code_examples(self, code_examples: List[Dict]) -> str:
        """Format enhanced code examples with function/class details for the prompt."""
        if not code_examples:
            return "No code examples available."
        
        formatted = []
        for example in code_examples[:5]:  # Limit to top 5 examples
            file_path = example.get('file_path', 'Unknown')
            snippet = example.get('snippet', '')
            context = example.get('context', '')
            language = example.get('language', 'unknown')
            
            # Format the main code snippet
            example_text = f"- **{file_path}** ({language}): {context}\n"
            
            if snippet:
                # Limit snippet to 400 chars but don't cut off in middle of line
                truncated_snippet = snippet
                if len(snippet) > 400:
                    lines = snippet.split('\n')
                    truncated_lines = []
                    char_count = 0
                    for line in lines:
                        if char_count + len(line) > 400:
                            truncated_lines.append('  # ... (truncated for brevity)')
                            break
                        truncated_lines.append(line)
                        char_count += len(line) + 1
                    truncated_snippet = '\n'.join(truncated_lines)
                
                example_text += f"  ```{language}\n  {truncated_snippet}\n  ```\n"
            
            # Add function details if available
            function_details = example.get('function_details', [])
            if function_details:
                example_text += "  **Key Functions:**\n"
                for func in function_details[:3]:  # Top 3 functions
                    func_name = func.get('name', 'unknown')
                    func_purpose = func.get('purpose', '')
                    func_signature = func.get('signature', '')
                    line_num = func.get('line_number', 0)
                    
                    example_text += f"    • `{func_name}()` (line {line_num})"
                    if func_purpose:
                        example_text += f": {func_purpose[:80]}{'...' if len(func_purpose) > 80 else ''}"
                    example_text += "\n"
                    
                    if func_signature and len(func_signature) < 100:
                        example_text += f"      ```{language}\n      {func_signature}\n      ```\n"
            
            # Add class details if available
            class_details = example.get('class_details', [])
            if class_details:
                example_text += "  **Key Classes:**\n"
                for cls in class_details[:2]:  # Top 2 classes
                    cls_name = cls.get('name', 'unknown')
                    cls_purpose = cls.get('purpose', '')
                    cls_inheritance = cls.get('inheritance', '')
                    methods = cls.get('methods', [])
                    line_num = cls.get('line_number', 0)
                    
                    example_text += f"    • `{cls_name}`"
                    if cls_inheritance:
                        example_text += f" (extends {cls_inheritance})"
                    example_text += f" (line {line_num})"
                    if cls_purpose:
                        example_text += f": {cls_purpose[:80]}{'...' if len(cls_purpose) > 80 else ''}"
                    example_text += "\n"
                    
                    if methods:
                        example_text += "      Methods: "
                        method_names = [m.get('name', 'unknown') for m in methods[:3]]
                        example_text += ", ".join(f"`{name}()`" for name in method_names)
                        example_text += "\n"
            
            formatted.append(example_text)
        
        return "\n".join(formatted) if formatted else "No code examples available."