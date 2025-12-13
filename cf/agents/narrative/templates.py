"""
Narrative Templates - Template Repository for Different Narrative Styles
"""

from .types import NarrativeStyle, NarrativeTemplate


class NarrativeTemplates:
    """Repository of narrative templates for different styles"""

    LIFE_OF_X = NarrativeTemplate(
        style=NarrativeStyle.LIFE_OF_X,
        prompt_template="""Trace the complete lifecycle of "{subject}" through the codebase.

Follow the journey from creation to completion, documenting each step with specific file and line references.

Required structure:
1. **Entry Point**: Where does {subject} first appear/get created?
2. **Initialization**: How is it set up or configured?
3. **Processing**: What operations happen to it?
4. **Data Flow**: How does it move through the system?
5. **Output/Completion**: Where does the journey end?

For each step, provide:
- Exact file path and line numbers
- Code snippets showing the relevant logic
- Explanation of what happens and why""",
        section_templates={
            'entry_point': "## Entry Point\n\nThe journey of {subject} begins in `{file}` at line {line}:\n\n```{lang}\n{code}\n```\n\n{explanation}",
            'processing': "## Processing\n\nIn `{file}` (lines {start}-{end}), {subject} is processed:\n\n```{lang}\n{code}\n```\n\n{explanation}",
            'data_flow': "## Data Flow\n\n{subject} moves through the following components:\n{flow_diagram}\n\n{explanation}",
            'output': "## Completion\n\nThe lifecycle concludes in `{file}` at line {line}:\n\n```{lang}\n{code}\n```\n\n{explanation}",
        },
        required_sections=['entry_point', 'processing', 'output'],
        optional_sections=['initialization', 'data_flow', 'error_handling'],
        grounding_rules=[
            "Every claim must cite specific file:line_number",
            "Include actual code snippets, not paraphrases",
            "Only reference files you have analyzed",
            "Use present tense for code behavior",
        ],
        min_code_references=5,
        example_format="In `supervisor.py` at line 142, the agent receives the request..."
    )

    ARCHITECTURE = NarrativeTemplate(
        style=NarrativeStyle.ARCHITECTURE,
        prompt_template="""Describe the architecture and design of "{subject}".

Document the structure, components, and their relationships.

Required structure:
1. **Overview**: High-level summary of the system/component
2. **Components**: Key modules/classes and their responsibilities
3. **Interactions**: How components communicate
4. **Design Patterns**: Patterns and principles used
5. **Data Flow**: How data moves through the system

Provide concrete file references and code examples for each section.""",
        section_templates={
            'overview': "## Architecture Overview\n\n{subject} is organized around these core concepts:\n\n{summary}\n\nKey files:\n{file_list}",
            'components': "## Core Components\n\n{components_description}\n\nComponent relationships:\n```\n{diagram}\n```",
            'patterns': "## Design Patterns\n\nThe following patterns are employed:\n\n{patterns_list}",
        },
        required_sections=['overview', 'components', 'interactions'],
        optional_sections=['patterns', 'data_flow', 'extension_points'],
        grounding_rules=[
            "Reference actual files and classes",
            "Show import relationships from code",
            "Use real class/function names",
        ],
        min_code_references=3,
        example_format="The SupervisorAgent in `supervisor.py` coordinates..."
    )

    EXPLANATION = NarrativeTemplate(
        style=NarrativeStyle.EXPLANATION,
        prompt_template="""Explain how "{subject}" works in this codebase.

Provide a clear, educational explanation with code references.

Required structure:
1. **Purpose**: What problem does it solve?
2. **How It Works**: Step-by-step explanation
3. **Key Implementation Details**: Important code sections
4. **Usage Examples**: How is it used?

Include specific file references and code snippets.""",
        section_templates={
            'purpose': "## Purpose\n\n{purpose_description}\n\nDefined in: `{file}`",
            'how_it_works': "## How It Works\n\n{explanation}\n\nCore implementation in `{file}` (lines {start}-{end}):\n\n```{lang}\n{code}\n```",
            'usage': "## Usage\n\n{usage_examples}",
        },
        required_sections=['purpose', 'how_it_works'],
        optional_sections=['usage', 'related_concepts', 'caveats'],
        grounding_rules=[
            "Explain what the code actually does",
            "Reference specific functions and classes",
            "Avoid speculation about intent",
        ],
        min_code_references=3,
        example_format="The `analyze()` method in `code_agent.py:45` performs..."
    )

    COMPARISON = NarrativeTemplate(
        style=NarrativeStyle.COMPARISON,
        prompt_template="""Compare "{subject}" in this codebase.

Provide an objective comparison with concrete code evidence.

Required structure:
1. **Overview**: What is being compared?
2. **Similarities**: Common patterns and approaches
3. **Differences**: Key distinctions
4. **Trade-offs**: Pros and cons of each
5. **Recommendations**: When to use each

Support each point with code references.""",
        section_templates={
            'similarities': "## Similarities\n\n{similarity_analysis}\n\nBoth implement:\n```{lang}\n{common_pattern}\n```",
            'differences': "## Differences\n\n{difference_analysis}\n\n**Option A** (`{file_a}`):\n```{lang}\n{code_a}\n```\n\n**Option B** (`{file_b}`):\n```{lang}\n{code_b}\n```",
        },
        required_sections=['overview', 'similarities', 'differences'],
        optional_sections=['trade_offs', 'recommendations', 'historical_context'],
        grounding_rules=[
            "Show actual code from both implementations",
            "Make objective, evidence-based comparisons",
            "Avoid subjective quality judgments without evidence",
        ],
        min_code_references=4,
        example_format="While both agents inherit from BaseAgent..."
    )

    TUTORIAL = NarrativeTemplate(
        style=NarrativeStyle.TUTORIAL,
        prompt_template="""Create a tutorial for "{subject}".

Guide the reader through understanding and using this feature.

Required structure:
1. **Introduction**: What will they learn?
2. **Prerequisites**: What they need to know
3. **Step-by-Step**: Detailed walkthrough
4. **Code Examples**: Working examples
5. **Next Steps**: Where to go from here

Make it practical with runnable examples.""",
        section_templates={
            'introduction': "## Introduction\n\nIn this tutorial, you'll learn {learning_goals}.\n\n{overview}",
            'steps': "## Step {n}: {step_title}\n\n{explanation}\n\n```{lang}\n{code}\n```\n\n{notes}",
        },
        required_sections=['introduction', 'steps'],
        optional_sections=['prerequisites', 'troubleshooting', 'next_steps'],
        grounding_rules=[
            "Use actual file paths from the codebase",
            "Show real, working code examples",
            "Reference existing implementations",
        ],
        min_code_references=5,
        example_format="First, open `config.yaml` and add..."
    )

    DEBUG_TRACE = NarrativeTemplate(
        style=NarrativeStyle.DEBUG_TRACE,
        prompt_template="""Trace the execution path for debugging "{subject}".

Follow the code path to understand behavior or identify issues.

Required structure:
1. **Starting Point**: Where execution begins
2. **Call Stack**: Function calls in order
3. **Key Decision Points**: Conditionals and branches
4. **Data Transformations**: How data changes
5. **Potential Issues**: Areas that might cause problems

Include line-by-line analysis where relevant.""",
        section_templates={
            'call_stack': "## Call Stack\n\n```\n{stack_trace}\n```\n\n{explanation}",
            'decision_point': "## Decision Point: {description}\n\nIn `{file}` at line {line}:\n```{lang}\n{code}\n```\n\nThis condition determines: {outcome}",
        },
        required_sections=['starting_point', 'call_stack'],
        optional_sections=['decision_points', 'data_transformations', 'potential_issues'],
        grounding_rules=[
            "Show exact execution order",
            "Reference specific line numbers",
            "Document actual variable values if known",
        ],
        min_code_references=8,
        example_format="At line 45, the condition `if agent.ready:` evaluates..."
    )

    API_REFERENCE = NarrativeTemplate(
        style=NarrativeStyle.API_REFERENCE,
        prompt_template="""Document the API for "{subject}".

Create a reference-style documentation for this interface.

Required structure:
1. **Overview**: What this API provides
2. **Classes/Functions**: Main interfaces
3. **Parameters**: Input requirements
4. **Returns**: Output specifications
5. **Examples**: Usage examples

Use documentation-style formatting.""",
        section_templates={
            'class_doc': "### `{class_name}`\n\n{description}\n\n**Location**: `{file}`\n\n**Methods**:\n{methods_list}",
            'method_doc': "#### `{method_name}({params})`\n\n{description}\n\n**Parameters**:\n{params_doc}\n\n**Returns**: {returns}\n\n**Example**:\n```{lang}\n{example}\n```",
        },
        required_sections=['overview', 'interfaces'],
        optional_sections=['examples', 'error_handling', 'related'],
        grounding_rules=[
            "Use actual function signatures",
            "Document real parameter types",
            "Show working examples from codebase",
        ],
        min_code_references=4,
        example_format="```python\nresult = agent.analyze(question='How...')\n```"
    )

    @classmethod
    def get_template(cls, style: NarrativeStyle) -> NarrativeTemplate:
        """Get template for a style"""
        templates = {
            NarrativeStyle.LIFE_OF_X: cls.LIFE_OF_X,
            NarrativeStyle.ARCHITECTURE: cls.ARCHITECTURE,
            NarrativeStyle.EXPLANATION: cls.EXPLANATION,
            NarrativeStyle.COMPARISON: cls.COMPARISON,
            NarrativeStyle.TUTORIAL: cls.TUTORIAL,
            NarrativeStyle.DEBUG_TRACE: cls.DEBUG_TRACE,
            NarrativeStyle.API_REFERENCE: cls.API_REFERENCE,
        }
        return templates.get(style, cls.EXPLANATION)
