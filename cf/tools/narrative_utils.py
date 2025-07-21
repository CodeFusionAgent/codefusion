"""
Utility functions for Life of X narrative generation and display.
"""

from cf.llm.real_llm import get_real_llm

def extract_key_entity(question: str) -> str:
    """
    Extract the key entity from a question using LLM intelligence.
    
    Args:
        question: The user's question
        
    Returns:
        The extracted entity for narrative display
    """
    try:
        real_llm = get_real_llm()
        if not real_llm or not real_llm.client:
            return _fallback_entity_extraction(question)
        
        prompt = f"""Question: "{question}"

Extract the main subject/entity that this question is asking about. This will be used in a "Life of X" narrative format.

Examples:
- "How does routing work?" -> "Routing"
- "What happens when a user logs in?" -> "User Login"
- "How is data validation handled?" -> "Data Validation"
- "Explain authentication flow" -> "Authentication"
- "How do webhooks work?" -> "Webhooks"
- "Explain the relationship between FastAPI and Starlette" -> "FastAPI Starlette Integration"
- "What specific responsibilities does Starlette handle?" -> "Starlette"
- "How are requests processed?" -> "Request Processing"

Return ONLY the entity name (1-4 words max), properly capitalized. Focus on the PRIMARY concept being asked about:
- For relationship questions, combine both entities (e.g., "FastAPI Starlette Integration")
- For responsibility/role questions, use the main subject (e.g., "Starlette", "Authentication")
- Avoid verbs like "handle", "work", "process" - focus on the WHAT, not the HOW"""
        
        response = real_llm._call_llm(prompt)
        
        if isinstance(response, dict):
            entity = response.get('content', '').strip()
        else:
            entity = str(response).strip()
        
        # Clean up the response - remove quotes, extra text
        entity = entity.replace('"', '').replace("'", "")
        if '\n' in entity:
            entity = entity.split('\n')[0]
        
        # Validate the entity (should be 1-4 words)
        words = entity.split()
        if 1 <= len(words) <= 4 and all(word.replace('-', '').replace('_', '').isalpha() for word in words):
            return entity
        else:
            return _fallback_entity_extraction(question)
            
    except Exception:
        return _fallback_entity_extraction(question)

def _fallback_entity_extraction(question: str) -> str:
    """
    Fallback entity extraction when LLM is not available.
    
    Args:
        question: The user's question
        
    Returns:
        The extracted entity using simple rules
    """
    question_lower = question.lower()
    
    # Handle relationship questions generically
    if "relationship between" in question_lower:
        # Extract entities after "between"
        after_between = question_lower.split("relationship between")[1]
        if " and " in after_between:
            parts = after_between.split(" and ")
            entity1 = parts[0].strip().title()
            entity2 = parts[1].strip().replace("?", "").split()[0].title()
            return f"{entity1} {entity2}"
    
    # Handle responsibility questions generically
    if "responsibilities" in question_lower or "what does" in question_lower:
        # Find capitalized words (likely proper nouns/entities)
        words = question.split()
        for word in words:
            if word[0].isupper() and word.lower() not in ['what', 'does', 'how', 'when', 'where', 'why']:
                return word
    
    # Simple pattern matching for common question types
    if "how does" in question_lower:
        words = question_lower.replace("how does", "").replace("work", "").replace("?", "").strip().split()
        if words:
            return words[0].title()
    
    if "what happens when" in question_lower:
        words = question_lower.replace("what happens when", "").replace("?", "").strip().split()
        if len(words) >= 2:
            return f"{words[1].title()} {words[2].title()}" if len(words) > 2 else words[1].title()
    
    # Look for capitalized words as entities (proper nouns)
    words = question.split()
    for word in words:
        if word[0].isupper() and word not in ['How', 'What', 'When', 'Where', 'Why', 'Does', 'Is', 'Are']:
            return word
    
    # Default fallback
    words = question.replace("?", "").split()
    if words:
        return "System"  # Generic fallback
    else:
        return "Request"


def display_comparison_analysis(narrative_result: dict, question: str) -> None:
    """
    Display a technical comparison analysis format.
    
    Args:
        narrative_result: The comparison result from LLM
        question: The original question
    """
    print(f"\n🔍 Technical Comparison Analysis: {question}")
    print("=" * 70)
    
    # Display main analysis
    analysis = narrative_result.get('analysis', '')
    if analysis:
        print(f"\n📊 **Analysis:** {analysis}")
    
    # Display comparison points
    comparison_points = narrative_result.get('comparison_points', [])
    if comparison_points:
        print(f"\n⚖️ **Key Comparisons:**")
        for point in comparison_points:
            if isinstance(point, dict):
                aspect = point.get('aspect', 'Comparison')
                option_a = point.get('option_a', '')
                option_b = point.get('option_b', '')
                recommendation = point.get('recommendation', '')
                print(f"\n   **{aspect}:**")
                print(f"   • Option A: {option_a}")
                print(f"   • Option B: {option_b}")
                if recommendation:
                    print(f"   • Recommendation: {recommendation}")
    
    # Display code examples
    code_examples = narrative_result.get('code_examples', [])
    if code_examples:
        print(f"\n💻 **Code Examples:**")
        for example in code_examples:
            print(f"   • {example}")
    
    # Display performance insights
    performance_insights = narrative_result.get('performance_insights', [])
    if performance_insights:
        print(f"\n⚡ **Performance Insights:**")
        for insight in performance_insights:
            print(f"   • {insight}")
    
    # Display best practices
    best_practices = narrative_result.get('best_practices', [])
    if best_practices:
        print(f"\n✅ **Best Practices:**")
        for practice in best_practices:
            print(f"   • {practice}")
    
    # Display conclusion
    conclusion = narrative_result.get('conclusion', '')
    if conclusion:
        print(f"\n🎯 **Conclusion:** {conclusion}")
    
    # Display confidence and metadata
    confidence = narrative_result.get('confidence', 0.0)
    if confidence > 0:
        print(f"\n📈 **Analysis Confidence:** {confidence:.1%}")

def display_life_of_x_narrative(narrative_result: dict, question: str) -> None:
    """
    Display the unified Life of X narrative in a comprehensive flow format.
    
    Args:
        narrative_result: The narrative result from LLM
        question: The original question
    """
    entity = extract_key_entity(question)
    print(f"\n🎯 Life of {entity}: A Journey Through the System")
    print("=" * 70)
    
    # Create a unified narrative combining all components
    unified_narrative = _build_life_of_x_journey_narrative(narrative_result, entity)
    
    if unified_narrative:
        print(f"\n{unified_narrative}")
    
    # Display confidence and metadata
    confidence = narrative_result.get('confidence', 0.0)
    model_used = narrative_result.get('model_used', 'unknown')
    
    print("\n" + "=" * 70)
    if confidence > 0:
        print(f"🎯 **Analysis Confidence:** {confidence:.1%}")
    if model_used != 'unknown':
        print(f"🤖 **Powered by:** {model_used}")
    print("💡 This unified narrative traces the complete journey of how your")
    print("   question flows through interconnected system components.")


def _build_life_of_x_journey_narrative(narrative_result: dict, entity: str) -> str:
    """
    Build a unified narrative that combines all sections into a flowing story.
    
    Args:
        narrative_result: The narrative data
        entity: The key entity extracted from the question
        
    Returns:
        A unified narrative string
    """
    sections = []
    
    # Start with architectural overview - combine with flow summary to avoid redundancy
    narrative = narrative_result.get('narrative', '')
    flow_summary = narrative_result.get('flow_summary', '')
    
    if narrative or flow_summary:
        arch_text = narrative
        if flow_summary and flow_summary.lower() not in narrative.lower():
            arch_text = f"{narrative} {flow_summary}" if narrative else flow_summary
        sections.append(f"🏗️ **Architecture & Flow:** {arch_text}")
    
    # Add the technical flow as the main journey (remove repetitive "journey begins" language)
    journey_stages = narrative_result.get('journey_stages', [])
    if journey_stages:
        sections.append(f"\n🛤️ **Technical Flow:** The process follows this path:")
        
        for i, stage in enumerate(journey_stages, 1):
            if isinstance(stage, dict):
                stage_name = stage.get('stage', stage.get('name', f'Step {i}'))
                stage_desc = stage.get('technical_explanation', stage.get('description', ''))
                sections.append(f"\n   **{i}. {stage_name}:** {stage_desc}")
            else:
                sections.append(f"\n   **{i}.** {stage}")
    
    # Integrate key components as the supporting cast
    key_components = narrative_result.get('key_components', [])
    if key_components:
        sections.append(f"\n\n🎯 **Key Components:** The essential pieces working together:")
        
        for component in key_components:
            if isinstance(component, dict):
                comp_name = component.get('component', component.get('name', 'Component'))
                comp_role = component.get('architectural_role', component.get('role', ''))
                sections.append(f"\n   • **{comp_name}** {comp_role}")
            else:
                sections.append(f"\n   • {component}")
    
    # Include meaningful implementation insights with code examples
    code_insights = narrative_result.get('code_insights', [])
    if code_insights:
        meaningful_insights = []
        for insight in code_insights:
            insight_str = str(insight).lower()
            if not any(phrase in insight_str for phrase in [
                "no specific code examples", "no code examples", "unfortunately, no",
                "no examples were provided", "code examples were not provided"
            ]):
                meaningful_insights.append(insight)
        
        if meaningful_insights:
            sections.append(f"\n\n💻 **Code Examples:** Implementation details:")
            for insight in meaningful_insights:
                sections.append(f"\n   • {insight}")
    
    # Web search insights should be integrated into the main narrative by LLM, not shown separately
    # They are handled by generate_llm_driven_narrative() which weaves them into the narrative naturally
    
    return "".join(sections)

def should_consolidate_multi_agent_results(question: str) -> bool:
    """
    Determine if the supervisor should coordinate multiple agents for this question.
    
    The supervisor agent intelligently selects which agents (code analysis, documentation,
    web search) are needed based on the question complexity and type.
    
    Args:
        question: The user's question
        
    Returns:
        True if supervisor should coordinate multiple agents, False for single agent
    """
    try:
        real_llm = get_real_llm()
        if not real_llm or not real_llm.client:
            return True  # Default to multi-agent coordination for complex questions
        
        prompt = f"""Question: "{question}"

Determine if the supervisor should coordinate multiple specialized agents for this question:

Available agents:
- Code Analysis Agent: Examines source code, classes, methods, and implementation details
- Documentation Agent: Analyzes README files, documentation, and code comments
- Web Search Agent: Finds external documentation and best practices

Use MULTI-AGENT coordination for:
- Complex architectural or system flow questions ("How does X work?")
- Questions requiring both code analysis and external context
- Questions about implementation patterns and best practices
- Questions needing comprehensive technical explanations

Use SINGLE-AGENT for:
- Simple file location questions ("Where is X defined?")
- Basic code reading tasks ("What does this function do?")
- Quick factual lookups

Return only: "MULTI_AGENT" or "SINGLE_AGENT"""
        
        response = real_llm._call_llm(prompt)
        
        if isinstance(response, dict):
            decision = response.get('content', '').strip().upper()
        else:
            decision = str(response).strip().upper()
        
        return "MULTI_AGENT" in decision
        
    except Exception:
        return True  # Default to multi-agent coordination

def detect_response_format(question: str) -> str:
    """
    Determine the best response format for a question.
    
    Args:
        question: The user's question
        
    Returns:
        'journey' for Life of X format, 'comparison' for technical analysis, 'explanation' for general
    """
    try:
        real_llm = get_real_llm()
        if not real_llm or not real_llm.client:
            return 'journey'  # Default fallback
        
        prompt = f"""Question: "{question}"

Determine the best response format for this question:

JOURNEY FORMAT (Life of X) - Use for:
- Process flow questions ("How does routing work?", "What happens when a user logs in?")
- System architecture questions that trace through components
- Request/response lifecycle questions

COMPARISON FORMAT - Use for:
- Performance comparisons ("async def vs def", "X vs Y performance")
- Feature comparison questions ("differences between X and Y")
- Trade-off analysis questions

EXPLANATION FORMAT - Use for:
- Conceptual explanations ("What is dependency injection?")
- Configuration questions ("How to configure X?")
- General how-to questions

Return only: "JOURNEY", "COMPARISON", or "EXPLANATION" """
        
        response = real_llm._call_llm(prompt)
        
        if isinstance(response, dict):
            format_type = response.get('content', '').strip().upper()
        else:
            format_type = str(response).strip().upper()
        
        if "COMPARISON" in format_type:
            return "comparison"
        elif "EXPLANATION" in format_type:
            return "explanation"
        else:
            return "journey"  # Default to journey for complex flows
            
    except Exception:
        return "journey"  # Default fallback

def generate_llm_driven_narrative(question: str, code_results: dict, docs_results: dict, web_results: dict) -> dict:
    """
    Use LLM to consolidate results from supervisor-selected agents into a unified Life of X narrative.
    
    The supervisor agent determines which agents are needed for each question and this function
    consolidates their results into a compelling technical story showing the actual code flow.
    
    Args:
        question: The original question
        code_results: Results from code analysis agent (if used)
        docs_results: Results from documentation agent (if used)
        web_results: Results from web search agent (if used)
        
    Returns:
        Consolidated Life of X narrative with actual code references and technical flow
    """
    try:
        real_llm = get_real_llm()
        if not real_llm or not real_llm.client:
            return _fallback_narrative_consolidation(question, code_results, docs_results, web_results)
        
        # Format web search insights for better integration
        web_search_text = "No external results"
        if web_results and web_results.get('insights'):
            web_search_text = "; ".join(web_results['insights'][:3])
        elif web_results and web_results.get('results'):
            web_search_text = "; ".join([r.get('snippet', '')[:100] for r in web_results['results'][:3] if r.get('snippet')])
        
        # Determine which agents provided results
        active_agents = []
        if code_results and code_results.get('summary'):
            active_agents.append('Code Analysis Agent')
        if docs_results and docs_results.get('summary'):
            active_agents.append('Documentation Agent')
        if web_search_text and web_search_text != "No external results":
            active_agents.append('Web Search Agent')
        
        agents_description = f"Based on analysis from {', '.join(active_agents)}"
        
        # Detect appropriate response format
        response_format = detect_response_format(question)
        
        if response_format == "comparison":
            prompt = f"""Question: "{question}"

CODE ANALYSIS RESULTS:
{_format_agent_results_for_llm(code_results)}

DOCUMENTATION RESULTS:
{_format_agent_results_for_llm(docs_results)}

WEB SEARCH INSIGHTS:
{web_search_text}

INSTRUCTIONS:
Create a comprehensive TECHNICAL COMPARISON analysis. {agents_description}, provide a detailed comparison addressing the question.

For "{question}", create an analysis that:

1. **Direct Comparison**: Compare the key aspects side by side
2. **Performance Analysis**: Analyze performance implications with specific metrics/scenarios
3. **Implementation Details**: Show actual code examples demonstrating the differences
4. **Trade-offs**: Explain when to use each approach and why
5. **Best Practices**: Include recommendations from documentation and external sources

Return a JSON object with this structure:
{{
  "analysis": "Comprehensive comparison analysis addressing the question directly",
  "comparison_points": [{{"aspect": "Performance", "option_a": "async def details", "option_b": "def details", "recommendation": "when to use which"}}],
  "code_examples": ["Actual code examples showing the differences"],
  "performance_insights": ["Specific performance implications and measurements"],
  "best_practices": ["Recommendations and best practices"],
  "conclusion": "Summary recommendation based on the analysis",
  "confidence": 0.85
}}"""
        else:
            prompt = f"""Question: "{question}"

CODE ANALYSIS RESULTS:
{_format_agent_results_for_llm(code_results)}

DOCUMENTATION RESULTS:
{_format_agent_results_for_llm(docs_results)}

WEB SEARCH INSIGHTS:
{web_search_text}

INSTRUCTIONS:
Create a "Life of X" narrative that follows a CONCRETE JOURNEY through the system. {agents_description}, tell the story of how a feature/request/process flows through the actual codebase step by step.

For "{question}", create a narrative that:

1. **Starts with the trigger**: What initiates this process? (e.g., "When a user makes an HTTP request to /api/users...")
2. **Follows the code path**: Step-by-step journey through actual files, classes, methods, and functions
3. **Shows the flow**: How data/control moves from one component to another with specific file references
4. **Uses real implementation details**: Reference actual file paths, class names, method signatures, and code snippets from the analysis
5. **INTEGRATES web search insights NATURALLY**: Weave external documentation insights directly into the narrative and journey stages, don't list them separately
6. **Includes actual code examples**: Show real code snippets with file:line references from the codebase
7. **Ends with the result**: What is the final outcome of this journey?

The narrative should read like a technical story: "When X happens, the system first calls the handle_request() method in router.py:45, which instantiates the UserController class from controllers/user.py:12, then invokes the get_user() method that queries the database..."

IMPORTANT: Integrate web search insights into the main narrative, journey stages, and code examples. Do NOT create a separate web_search_insights section - instead weave external knowledge naturally into the explanation.

Return a JSON object with this structure:
{{
  "narrative": "A concrete step-by-step journey showing how the process flows through actual code files, classes, and methods, enhanced with external insights woven naturally into the explanation",
  "key_components": [{{"component": "ActualClassName/FunctionName", "role": "Specific role in the journey with file:line reference"}}],
  "journey_stages": [{{"stage": "ConcreteStepName", "description": "Specific action with code references and integrated external insights where relevant"}}],
  "code_insights": ["Actual code examples with file references like 'In main.py:123: @app.get(\"/users\") def get_users(): return UserService.fetch_all()'"],
  "flow_summary": "Complete end-to-end technical process summary with integrated external knowledge",
  "confidence": 0.85
}}

Make this a compelling technical story of how "{question}" actually works in THIS specific codebase with real file and method references, enhanced with external documentation insights integrated naturally throughout."""
        
        response = real_llm._call_llm(prompt)
        
        if isinstance(response, dict):
            content = response.get('content', '')
        else:
            content = str(response)
        
        # Try to parse JSON from the response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                import json
                result = json.loads(json_match.group(0))
                
                
                return result
            except json.JSONDecodeError:
                pass
        
        # Fallback if JSON parsing fails
        return _fallback_narrative_consolidation(question, code_results, docs_results, web_results)
        
    except Exception:
        return _fallback_narrative_consolidation(question, code_results, docs_results, web_results)

def _format_agent_results_for_llm(results: dict) -> str:
    """
    Format agent results for LLM consumption.
    
    Args:
        results: Agent results dictionary
        
    Returns:
        Formatted string for LLM prompt
    """
    if not results:
        return "No results available"
    
    formatted_parts = []
    
    if results.get('summary'):
        formatted_parts.append(f"Summary: {results['summary']}")
    
    if results.get('findings'):
        formatted_parts.append(f"Findings: {'; '.join(results['findings'][:3])}")
    
    if results.get('code_examples'):
        formatted_parts.append(f"Code Examples: {'; '.join(results['code_examples'][:2])}")
    
    if results.get('file_analysis'):
        formatted_parts.append(f"Files Analyzed: {'; '.join(results['file_analysis'][:3])}")
    
    return "; ".join(formatted_parts) if formatted_parts else "No specific results"

def _fallback_narrative_consolidation(question: str, code_results: dict, docs_results: dict, web_results: dict) -> dict:
    """
    Fallback consolidation when LLM is not available.
    
    Args:
        question: The original question
        code_results: Results from code analysis agent
        docs_results: Results from documentation agent
        web_results: Results from web search agent
        
    Returns:
        Basic consolidated result
    """
    return {
        "narrative": f"Analysis of {question} based on available code and documentation.",
        "key_components": [],
        "journey_stages": [],
        "code_insights": [],
        "web_search_insights": [],
        "flow_summary": "Multiple sources analyzed for comprehensive understanding.",
        "confidence": 0.6
    }