#!/usr/bin/env python3
"""
CodeFusion Evaluation Script

Compares CodeFusion responses against reference answers using different models as judge.
"""

import sys
import yaml
import json
import re
from datetime import datetime

from cf.configs.config_mgr import ConfigManager
from cf.llm.client import LLMClient
from langfuse import get_client


langfuse = get_client()


generationStartTime = datetime.now()

MODELS = []

# Function to evaluate using LLM (Judge) via unified provider APIs
def ask_openai_evaluation(question, reference_answer, response, model_name):
    # Set the evaluation prompt based on the tier and the response
    evaluation_prompt = f"""
    You are a senior software engineer with 10 years of experience in software development.
    The question and answer pairs are designed to helped a software engineer ramp up on code base for FastAPI.
    The answers should follow the life of X (if the question is about understanding how something works and flows through the system i.e how does request processing work) style format so that it is helpful for an engineer to meaninfgfully contribute to the code base.
    Please evaluate the following responses based on accuracy, coherence, reasoning consistency, and grounding:

    **Question:** {question}

    **Reference Answer:** {reference_answer} if available and not N/A

    **Model Response:** {response}

    **Evaluation Criteria:**
    1. **Architecture-Level Reasoning**: Does the response provide clear reasoning about the system's design, modules, or architecture? (Score 0-5)
    2. **Reasoning Consistency**: Is the reasoning consistent? Does it follow a logical and coherent flow? (Score 0-5)
    3. **Code Understanding Tier**: Categorize the question into one of the following tiers: performance-related, runtime-related, inter-module, or architectural. How well does the model understand the question within the given code understanding tier? (Score 0-5)
    4. **Grounding Score**: How factual and accurate is the response? Does it align with the reference answer if available and not N/A? (Score 0-5)

    Provide a detailed evaluation based on these criteria, and include the feedback and justification for each score. Be very strict in your evaluation. A high score needs to be backed by strong justification. Give your answer in the following JSON format (note: all scores should be integers, not strings):

    {{
        "architecture_reasoning": {{
            "score": "int",
            "feedback": "Detailed feedback about architecture reasoning"
        }},
        "reasoning_consistency": {{
            "score": "int",
            "feedback": "Feedback about reasoning consistency"
        }},
        "code_understanding_tier": {{
            "tier": "tier name",
            "score": "int",
            "feedback": "Feedback about code understanding"
        }},
        "grounding": {{
            "score": "int",
            "feedback": "Feedback about grounding"
        }}
    }}
    """
    config_mgr = ConfigManager("cf/configs/config.yaml")
    config = config_mgr.get_config()

    # Use unified LLMClient with provider APIs instead of direct SDK calls
    # LLMClient automatically handles Azure, Anthropic, Gemini, and OpenAI-compatible APIs
    llm_client = LLMClient(config.get("llm", {}))

    system_prompt = "You are a senior software engineer with 10 years of experience in software development."

    # Get temperature from config
    temperature = config.get("llm", {}).get("temperature")
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature

    # Call LLM via unified provider API (handles all providers automatically)
    result = llm_client.generate(
        prompt=evaluation_prompt,
        system_prompt=system_prompt,
        model=model_name,
        **kwargs
    )

    if not result.get('success'):
        raise Exception(f"LLM evaluation failed: {result.get('error', 'Unknown error')}")

    return result['content'].strip()

# Function to compare responses based on all criteria
def compare_responses(question, reference_answer, model_name, *model_responses):
    """
    Compare model responses against the reference answer and evaluate them.
    
    Args:
        question (str): The question that was asked
        reference_answer (str): The reference/expected answer
        *model_responses: Variable number of model responses to evaluate
        
    Returns:
        list: List of evaluation results for each model response
    """
    evaluations = []
    
    print("Using judge model: {}".format(model_name))
    print(f"Evaluating responses for question: {question[:100]}...")
    for i, (model_id, response) in enumerate(model_responses, 1):
        print(f"Evaluating {model_id} response...")
        evaluation = ask_openai_evaluation(question, reference_answer, response, model_name)
        evaluations.append(evaluation)
        
        # Print the response and its evaluation
        print(f"{model_id} Response: {response[:200]}...")
        print(f"{model_id} Evaluation: {evaluation[:200]}...\n")
    
    return evaluations

def parse_evaluation_json(eval_text):
    """Parse JSON evaluation response, handling potential formatting issues."""
    try:
        # Try to find JSON content between curly braces
        json_match = re.search(r'\{.*\}', eval_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            return json.loads(json_str)
        else:
            # Fallback - try to parse the whole text
            return json.loads(eval_text)
    except (json.JSONDecodeError, AttributeError):
        # Return a default structure if parsing fails
        return {
            "architecture_reasoning": {"score": 0, "feedback": "Parse error"},
            "reasoning_consistency": {"score": 0, "feedback": "Parse error"},
            "code_understanding_tier": {"tier": "unknown", "score": 0, "feedback": "Parse error"},
            "grounding": {"score": 0, "feedback": "Parse error"}
        }

def get_score_class(score):
    """Return CSS class based on score value (out of 5)."""
    if score >= 4:
        return "score-high"
    elif score >= 3:
        return "score-mid"
    else:
        return "score-low"  

def run_langfuse_eval(item, input, output, eval_data, repo_name, model_name):
    """Run Langfuse evaluation"""
    # Update the dataset item with the evaluation results
    with item.run(run_name=f"{model_name}_{generationStartTime}") as root_span:
        with langfuse.start_as_current_generation(
            name="{}_qa_{}".format(repo_name, model_name),
            input=input,
            model="gpt-4.1",
        ) as langfuse_generation:
            langfuse_generation.update(output=output)
        
            # Update the trace with the input and output
            langfuse_generation.update_trace(
                input=input,
                output=output,
                )
            langfuse_generation.score(
                    name="architecture_reasoning",
                    value=eval_data["architecture_reasoning"]["score"],
                    comment=eval_data["architecture_reasoning"]["feedback"]
                )
            langfuse_generation.score(
                    name="reasoning_consistency",
                    value=eval_data["reasoning_consistency"]["score"],
                    comment=eval_data["reasoning_consistency"]["feedback"]
                )
            langfuse_generation.score(
                    name="code_understanding_tier",
                    value=eval_data["code_understanding_tier"]["score"],
                    comment=eval_data["code_understanding_tier"]["feedback"]
                )
            langfuse_generation.score(
                    name="grounding",
                    value=eval_data["grounding"]["score"],
                    comment=eval_data["grounding"]["feedback"]
                )


def generate_html_report(evaluation_results, output_path, model_name):
    """Generate comprehensive HTML report from evaluation results.
    
    Args:
        evaluation_results (list): List of evaluation results
        output_path (str): Path to save the HTML report
        model_ids (list): List of model IDs to include in the report
    """
    # Initialize data structures with dynamic model IDs
    all_evaluations = {model["id"]: [] for model in MODELS}
    all_scores = {
        model["id"]: {"arch": [], "consistency": [], "understanding": [], "grounding": []}
        for model in MODELS
    }
    avg_scores = {
        model["id"]: {"arch": 0, "consistency": 0, "understanding": 0, "grounding": 0}
        for model in MODELS
    }
    overall_scores = {model["id"]: 0 for model in MODELS}
    # Calculate summary statistics
    

    #dataset = langfuse.get_dataset("Codepath_qa_1")
    
    for result in evaluation_results:
        # Parse evaluations for each model
        for model in MODELS:
            model_id = model["id"]
            eval_key = f"{model_id}_evaluation"
            if eval_key in result and result[eval_key]:
                try:
                    parsed_eval = parse_evaluation_json(result[eval_key])
                    all_evaluations[model_id].append(parsed_eval)
                except Exception as e:
                    print(f"Error parsing evaluation for {model_id}: {e}")
                    all_evaluations[model_id].append({
                        "architecture_reasoning": {"score": 0, "feedback": "Parse error"},
                        "reasoning_consistency": {"score": 0, "feedback": "Parse error"},
                        "code_understanding_tier": {"score": 0, "tier": "unknown", "feedback": "Parse error"},
                        "grounding": {"score": 0, "feedback": "Parse error"}
                    })
        
        # Process Langfuse evaluations
        #for ds_item in dataset.items:
        #    if ds_item.input != result["question"]:
        #        continue
                
        # Run Langfuse evaluation for each model
        #for model in MODELS:
        #    model_id = model["id"]
        #    output = result[f"{model_id}_answer"]
        #    #try:
        #    #    run_langfuse_eval(ds_item, result["question"], output, all_evaluations[model_id][-1], "django", model_id)
        #    #except Exception as e:
        #    #    print(f"Error in Langfuse evaluation for {model_id}: {type(e).__name__} - {str(e)}")
        
        # Collect scores for each model
        for model in MODELS:
            model_id = model["id"]
            eval_data = all_evaluations[model_id][-1]
            if "N/A" not in result[model_id + "_answer"] and "Parse error" not in eval_data["architecture_reasoning"]["feedback"]:
                all_scores[model_id]["arch"].append(eval_data.get("architecture_reasoning", {}).get("score", 0))
                all_scores[model_id]["consistency"].append(eval_data.get("reasoning_consistency", {}).get("score", 0))
                all_scores[model_id]["understanding"].append(eval_data.get("code_understanding_tier", {}).get("score", 0))
                all_scores[model_id]["grounding"].append(eval_data.get("grounding", {}).get("score", 0))
    
    for model in MODELS:
        model_id = model["id"]
        avg_scores[model_id] = {
            "arch": sum(all_scores[model_id]["arch"]) / len(all_scores[model_id]["arch"]),
            "consistency": sum(all_scores[model_id]["consistency"]) / len(all_scores[model_id]["consistency"]),
            "understanding": sum(all_scores[model_id]["understanding"]) / len(all_scores[model_id]["understanding"]),
            "grounding": sum(all_scores[model_id]["grounding"]) / len(all_scores[model_id]["grounding"]),
        }
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codepath Q&A Evaluation Report (Judge Model: {model_name})</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f7fa;
            color: #333;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        h1 {{
            color: #2c3e50;
            text-align: center;
            margin-bottom: 40px;
            font-size: 2.2em;
        }}
        
        h2 {{
            color: #34495e;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 40px;
        }}
        
        .question-section {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            margin: 20px 0;
            padding: 0;
            overflow: hidden;
        }}
        
        .question-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            cursor: pointer;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .question-header:hover {{
            background: linear-gradient(135deg, #5a6fd8 0%, #6b42c4 100%);
        }}
        
        .question-content {{
            padding: 20px;
            display: none;
        }}
        
        .question-content.expanded {{
            display: block;
        }}
        
        .toggle-icon {{
            font-size: 1.2em;
            transition: transform 0.3s;
        }}
        
        .toggle-icon.expanded {{
            transform: rotate(180deg);
        }}
        
        .answer-section {{
            margin: 15px 0;
            padding: 15px;
            border-left: 4px solid #ddd;
            background: #fff;
            border-radius: 6px;
        }}
        
        .reference-answer {{ border-left-color: #28a745; }}
        
        {''.join([f'.{model["id"]}_answer {{ border-left-color: {model.get("answer_color", "#cccccc")}; }}' for model in MODELS])}
        .answer-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #495057;
        }}
        
        .answer-text {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 4px;
            margin: 10px 0;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.9em;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            border: 1px solid #e9ecef;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .answer-text.expanded {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            max-height: none;
            height: 100vh;
            z-index: 1000;
            margin: 0;
            padding: 20px;
            border-radius: 0;
            overflow-y: auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.3);
        }}
        
        .evaluation-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin: 15px 0;
        }}
        
        .eval-metric {{
            background: white;
            padding: 12px;
            border-radius: 6px;
            border: 1px solid #e9ecef;
            text-align: center;
        }}
        
        .eval-metric h4 {{
            margin: 0 0 8px 0;
            font-size: 0.85em;
            color: #6c757d;
            font-weight: 600;
        }}
        
        .score {{
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 4px;
            color: white;
            display: inline-block;
            margin: 5px 0;
            font-size: 0.9em;
        }}
        
        .score-high {{ background-color: #28a745; }}
        .score-mid {{ background-color: #ffc107; color: #333; }}
        .score-low {{ background-color: #dc3545; }}
        
        .feedback {{
            font-size: 0.8em;
            color: #6c757d;
            margin-top: 8px;
            text-align: left;
            line-height: 1.4;
        }}
        
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .summary-table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
            padding: 15px 12px;
            text-align: left;
            font-size: 0.9em;
        }}
        
        .summary-table td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
            font-size: 0.9em;
        }}
        
        .summary-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        .summary-table tr:hover {{
            background-color: #e8f4f8;
        }}
        
        .full-question {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            border-left: 4px solid #007bff;
        }}
        
        .question-text {{
            font-weight: 500;
            color: #495057;
        }}
        
        .models-comparison {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 20px 0;
        }}
        
        .model-column {{
            background: #fff;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        {''.join([f'.{model["id"]}_column {{ border-top: 4px solid {model.get("column_color", "#cccccc")}; }}' for model in MODELS])}
                
        .model-header {{
            padding: 12px 15px;
            font-weight: bold;
            color: white;
            text-align: center;
        }}
        
        {''.join([f'.{model["id"]}_column .model-header {{ background: {model.get("gradient", "#cccccc")}; {"color: #333;" if model.get('light_text', False) else ""}}}' for model in MODELS])}
        
        .feedback-section {{
            padding: 15px;
        }}
        
        .feedback-item {{
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        
        .feedback-item:last-child {{
            border-bottom: none;
        }}
        
        .feedback-text {{
            margin-top: 5px;
            color: #6c757d;
            font-size: 0.9em;
            line-height: 1.4;
        }}
        
        .question-tooltip {{
            position: relative;
            cursor: help;
        }}
        
        .question-tooltip::after {{
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 0.85em;
            white-space: normal;
            width: 400px;
            max-width: 90vw;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s;
            line-height: 1.4;
            text-align: left;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }}
        
        .question-tooltip:hover::after {{
            opacity: 1;
        }}
        
        .tier-badge {{
            background: #e9ecef;
            color: #495057;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.75em;
            margin-left: 4px;
            text-transform: capitalize;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }}
        
        @media (max-width: 768px) {{
            .container {{ padding: 15px; }}
            .evaluation-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .stats-grid {{ grid-template-columns: 1fr; }}
            .question-header {{ padding: 12px 15px; font-size: 0.9em; }}
            .models-comparison {{ grid-template-columns: repeat(2, 1fr); }}
            @media (max-width: 480px) {{
                .models-comparison {{ grid-template-columns: 1fr; }}
            }}
            .summary-table {{ font-size: 0.8em; }}
            .summary-table th, .summary-table td {{ padding: 8px 4px; }}
        }}
    </style>
    <script>
        function toggleExpand(element) {{
            // Toggle the expanded class on the clicked element
            element.classList.toggle('expanded');
            
            // If expanded, add overlay to the body
            if (element.classList.contains('expanded')) {{
                // Create overlay if it doesn't exist
                let overlay = document.getElementById('overlay');
                if (!overlay) {{
                    overlay = document.createElement('div');
                    overlay.id = 'overlay';
                    overlay.style.position = 'fixed';
                    overlay.style.top = '0';
                    overlay.style.left = '0';
                    overlay.style.right = '0';
                    overlay.style.bottom = '0';
                    overlay.style.background = 'rgba(0, 0, 0, 0.5)';
                    overlay.style.zIndex = '999';
                    overlay.style.display = 'none';
                    overlay.onclick = function() {{
                        document.body.removeChild(overlay);
                        const expanded = document.querySelector('.answer-text.expanded');
                        if (expanded) {{
                            expanded.classList.remove('expanded');
                        }}
                    }};
                    document.body.appendChild(overlay);
                }}
                overlay.style.display = 'block';
                
                // Scroll to the expanded element
                setTimeout(() => {{
                    element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}, 10);
            }} else {{
                // Remove overlay if no expanded elements remain
                const overlay = document.getElementById('overlay');
                if (overlay && !document.querySelector('.answer-text.expanded')) {{
                    overlay.style.display = 'none';
                }}
            }}
        }}
        
        // Close expanded answer when clicking outside
        document.addEventListener('click', function(event) {{
            const answerTexts = document.querySelectorAll('.answer-text');
            const overlay = document.getElementById('overlay');
            let isAnswerText = false;
            
            // Check if click is inside any answer text
            answerTexts.forEach(text => {{
                if (text.contains(event.target)) {{
                    isAnswerText = true;
                }}
            }});
            
            // If click is outside any answer text but overlay is visible
            if (!isAnswerText && overlay && overlay.style.display === 'block') {{
                const expanded = document.querySelector('.answer-text.expanded');
                if (expanded) {{
                    expanded.classList.remove('expanded');
                }}
                overlay.style.display = 'none';
            }}
        }});
    </script>
</head>
<body>
    <div class="container">
        <h1>📊 Codepath Q&A Evaluation Report (Judge Model: {model_name})</h1>
        <p style="text-align: center; color: #6c757d; margin-bottom: 40px;">
            Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | 
            {len(evaluation_results)} questions evaluated
        </p>
        
        <h2>📋 Question-by-Question Score Comparison</h2>
        <table class="summary-table">
            <thead>
                <tr>
                    <th style="width: 20%;">Question</th>
                    {''.join([
                        f'<th colspan="4" style="text-align: center; background: {model.get("title_gradient", "#cccccc")}; {"color: #333;" if model.get("light_text", False) else ""}">{model["title_icon"]} {model["name"]}</th>'
                        for model in MODELS])}
                </tr>
                <tr>
                    <th></th>
               {''.join([
        '<th>Arch</th><th>Reasoning</th><th>Code Tier</th><th>Grounding</th>'
        for _ in MODELS
    ])}
                </tr>
            </thead>
            <tbody>
"""
    
    # Add score comparison rows
    for i, result in enumerate(evaluation_results, 1):
        
        question_preview = result['question'][:50] + ('...' if len(result['question']) > 50 else '')
        
        # Escape quotes for HTML tooltip attribute
        full_question_escaped = result['question'].replace('"', '&quot;').replace("'", "&#39;")
        
        score_cells = "".join([
            f"""
            <td><span class="score {get_score_class(all_evaluations[model_id][i-1]['architecture_reasoning']['score'])}">{all_evaluations[model_id][i-1]['architecture_reasoning']['score']}/5</span></td>
            <td><span class="score {get_score_class(all_evaluations[model_id][i-1]['reasoning_consistency']['score'])}">{all_evaluations[model_id][i-1]['reasoning_consistency']['score']}/5</span></td>
            <td><span class="score {get_score_class(all_evaluations[model_id][i-1]['code_understanding_tier']['score'])}">{all_evaluations[model_id][i-1]['code_understanding_tier']['score']}/5</span><span class="tier-badge">{all_evaluations[model_id][i-1]['code_understanding_tier'].get('tier', 'unknown')}</span></td>
            <td><span class="score {get_score_class(all_evaluations[model_id][i-1]['grounding']['score'])}">{all_evaluations[model_id][i-1]['grounding']['score']}/5</span></td>
            """ 
            for model_id in [model['id'] for model in MODELS]
        ])
        html_content += f"""
                <tr onclick="toggleDetails({i})" style="cursor: pointer;" title="Click to view detailed answers and feedback">
                    <td style="font-weight: 500;" class="question-tooltip" data-tooltip="{full_question_escaped}"><strong>Q{i}:</strong> {question_preview}</td>
                    {score_cells}
                </tr>
        """
    
    html_content += """
            </tbody>
        </table>
        
        <h2>📋 Detailed Question Analysis</h2>
        <p style="color: #6c757d; margin-bottom: 30px;"><em>Click on any question below to expand detailed answers and feedback</em></p>
"""

    # Add detailed expandable sections
    for i, result in enumerate(evaluation_results, 1):
        
        question_preview = result['question'][:80] + ('...' if len(result['question']) > 80 else '')

        model_columns = "".join([
            f"""
            <div class="model-column {model['id']}_column">
                <div class="model-header">{model.get('title_icon', '')} {model['name']}</div>
                <div class="answer-text" onclick="toggleExpand(this)">{result.get(f"{model['id']}_answer", "No answer provided")}</div>
                <div class="feedback-section">
                    {f'''
                    <div class="feedback-item">
                        <strong>Architecture ({all_evaluations[model['id']][i-1]['architecture_reasoning']['score']}/5):</strong>
                        <div class="feedback-text">{all_evaluations[model['id']][i-1]['architecture_reasoning']['feedback']}</div>
                    </div>
                    <div class="feedback-item">
                        <strong>Reasoning Consistency ({all_evaluations[model['id']][i-1]['reasoning_consistency']['score']}/5):</strong>
                        <div class="feedback-text">{all_evaluations[model['id']][i-1]['reasoning_consistency']['feedback']}</div>
                    </div>
                    <div class="feedback-item">
                        <strong>Code Tier ({all_evaluations[model['id']][i-1]['code_understanding_tier']['score']}/5 - {all_evaluations[model['id']][i-1]['code_understanding_tier'].get('tier', 'unknown')}):</strong>
                        <div class="feedback-text">{all_evaluations[model['id']][i-1]['code_understanding_tier']['feedback']}</div>
                    </div>
                    <div class="feedback-item">
                        <strong>Grounding ({all_evaluations[model['id']][i-1]['grounding']['score']}/5):</strong>
                        <div class="feedback-text">{all_evaluations[model['id']][i-1]['grounding']['feedback']}</div>
                    </div>
                    ''' if model['id'] in all_evaluations and i-1 < len(all_evaluations[model['id']]) else 
                    '<div class="feedback-item">No evaluation data available</div>'}
                </div>
            </div>
            """ 
        for model in MODELS
    ])     
        
        html_content += f"""
        <div class="question-section" id="details-{i}">
            <div class="question-header" onclick="toggleQuestion({i})">
                <span>Question {i}: {question_preview}</span>
                <span class="toggle-icon" id="icon-{i}">▼</span>
            </div>
            <div class="question-content" id="content-{i}">
                <div class="full-question">
                    <h4>📝 Full Question</h4>
                    <div class="question-text">{result['question']}</div>
                </div>
                
                <div class="answer-section reference-answer">
                    <div class="answer-title">📖 Reference Answer</div>
                    <div class="answer-text" onclick="toggleExpand(this)">{result['reference_answer']}</div>
                </div>
                
                <div class="models-comparison">
                    {model_columns}
                </div>
            </div>
        </div>
        """
    
    # Calculate overall averages for winner determination
    for model in MODELS:
        model_id = model['id']
        overall_scores[model_id] = (avg_scores[model_id]['arch'] + avg_scores[model_id]['consistency'] + avg_scores[model_id]['understanding'] + avg_scores[model_id]['grounding']) / 4
    
    # Determine winner
    scores = [(model['name'], overall_scores[model['id']]) for model in MODELS]
    
    winner, winner_score = max(scores, key=lambda x: x[1])
    
    # Determine best category across all models
    category_averages = {
        "Architecture": sum(avg_scores[model['id']]['arch'] for model in MODELS) / len(avg_scores),
        "Reasoning": sum(avg_scores[model['id']]['consistency'] for model in MODELS) / len(avg_scores),
        "Code Tier": sum(avg_scores[model['id']]['understanding'] for model in MODELS) / len(avg_scores),
        "Grounding": sum(avg_scores[model['id']]['grounding'] for model in MODELS) / len(avg_scores)
    }
    best_category = max(category_averages, key=category_averages.get)
    summary_rows = "".join([
        f"""
        <tr>
            <td><strong>{model['name']}</strong></td>
            <td><span class="score {get_score_class(avg_scores[model['id']]['arch'])}">{avg_scores[model['id']]['arch']:.1f}/5</span></td>
            <td><span class="score {get_score_class(avg_scores[model['id']]['consistency'])}">{avg_scores[model['id']]['consistency']:.1f}/5</span></td>
            <td><span class="score {get_score_class(avg_scores[model['id']]['understanding'])}">{avg_scores[model['id']]['understanding']:.1f}/5</span></td>
            <td><span class="score {get_score_class(avg_scores[model['id']]['grounding'])}">{avg_scores[model['id']]['grounding']:.1f}/5</span></td>
            <td><span class="score {get_score_class(overall_scores[model['id']])}">{overall_scores[model['id']]:.1f}/5</span></td>
        </tr>
        """
        for model in MODELS
    ])

    # Add summary statistics
    html_content += f"""
        <h2>📈 Summary Statistics</h2>
        
        <table class="summary-table">
            <thead>
                <tr>
                    <th>Model</th>
                    <th>Architecture Reasoning</th>
                    <th>Reasoning Consistency</th>
                    <th>Code Tier</th>
                    <th>Grounding Score</th>
                    <th>Overall Average</th>
                </tr>
            </thead>
            <tbody>
                {summary_rows}
            </tbody>
        </table>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>🏆 Overall Winner</h3>
                <div class="stat-value">{winner}</div>
                <p>{winner_score:.1f}/5 average score</p>
            </div>
            <div class="stat-card">
                <h3>🎯 Best Category</h3>
                <div class="stat-value">{best_category}</div>
                <p>{category_averages[best_category]:.1f}/5 average across models</p>
            </div>
            <div class="stat-card">
                <h3>📊 Questions Evaluated</h3>
                <div class="stat-value">{len(evaluation_results)}</div>
                <p>Comprehensive evaluation</p>
            </div>
        </div>
        
        <script>
            function toggleQuestion(num) {{
                const content = document.getElementById('content-' + num);
                const icon = document.getElementById('icon-' + num);
                
                if (content.classList.contains('expanded')) {{
                    content.classList.remove('expanded');
                    icon.classList.remove('expanded');
                    icon.textContent = '▼';
                }} else {{
                    content.classList.add('expanded');
                    icon.classList.add('expanded');
                    icon.textContent = '▲';
                }}
            }}
            
            function toggleDetails(num) {{
                const detailSection = document.getElementById('details-' + num);
                if (detailSection) {{
                    detailSection.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                    // Auto-expand the details section
                    setTimeout(() => {{
                        const content = document.getElementById('content-' + num);
                        const icon = document.getElementById('icon-' + num);
                        if (content && !content.classList.contains('expanded')) {{
                            content.classList.add('expanded');
                            icon.classList.add('expanded');
                            icon.textContent = '▲';
                        }}
                    }}, 500);
                }}
            }}
        </script>
        
        <div style="text-align: center; margin-top: 40px; color: #7f8c8d; font-size: 14px;">
            <p>📊 Codepath Q&A Evaluation Report - {len(MODELS)}-Model Comparison</p>
        </div>
    </div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML report generated: {output_path}")
    return output_path

def evaluate_responses(eval_data, output_path, model_name):
    # Collect all evaluation results
    evaluation_results = []
    global MODELS
    
    # Get model IDs from the eval_data
    MODELS = eval_data.get('models', [])
    
    for qdata in eval_data["questions"]:
        question = qdata["question"]
        reference_answer = qdata["reference_answer"]
        
        # Collect model responses
        model_responses = []
        for model in MODELS:
            response = qdata.get(f"{model['id']}_answer", "N/A")
            model_responses.append((model['id'], response))
        
        # Evaluate all model responses
        evaluations = compare_responses(question, reference_answer, model_name, *model_responses)
        
        # Store results for HTML generation
        result_data = {
            "question": question,
            "reference_answer": reference_answer,
        }
        
        # Add model responses and evaluations to result data
        for i, model in enumerate(MODELS):
            result_data[f"{model['id']}_answer"] = model_responses[i][1]
            result_data[f"{model['id']}_evaluation"] = evaluations[i]
        evaluation_results.append(result_data)
    
    # Generate HTML report
    html_file = generate_html_report(evaluation_results, output_path, model_name)
    
    return html_file

def main():
    eval_data_path = 'cf/evals/eval_qa_llama4_mav_codewalk.yaml'
    with open(eval_data_path, 'r') as f:
         eval_data = yaml.safe_load(f)
    model_name = "gpt-5"
    if model_name == "meta-llama/llama-4-maverick-17b-128e-instruct":
        output_path = "evaluation_results_codepath_{}_{}.html".format("llama-4-maverick-17b-128e-instruct", datetime.now().strftime("%Y%m%d_%H%M%S"))
    else:
        output_path = "evaluation_results_codepath_{}_{}.html".format(model_name, datetime.now().strftime("%Y%m%d_%H%M%S"))
    html_file = evaluate_responses(eval_data, output_path, model_name)
    print(f"\n🎉 Evaluation complete! HTML report generated: {html_file}")

if __name__ == "__main__":
    main()
