#!/usr/bin/env python3
"""
CodeFusion Evaluation Script

Compares CodeFusion responses against reference answers using OpenAI as judge.
"""

import openai
import sys
import yaml
import json
import re
from datetime import datetime

from cf.configs.config_mgr import ConfigManager
from langfuse import get_client

langfuse = get_client()


generationStartTime = datetime.now()

# Function to evaluate using OpenAI (Judge)
def ask_openai_evaluation(question, reference_answer, response):
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
    # Send the prompt to OpenAI for evaluation
    openai.api_key=config.get("llm", {}).get("api_key")
    client = openai.OpenAI()
    # Prepare parameters for the API call
    params = {
        "model": "gpt-4.1",
        "messages": [
            {"role": "system", "content": "You are a senior software engineer with 10 years of experience in software development."},
            {"role": "user", "content": evaluation_prompt}
        ]
    }
    
    # Only add temperature if it's explicitly set in the config
    temperature = config.get("llm", {}).get("temperature")
    if temperature is not None:
        params["temperature"] = temperature
    
    response = client.chat.completions.create(**params)
    return response.choices[0].message.content.strip()

# Function to compare responses based on all criteria
def compare_responses(question, reference_answer, claude_code_answer, codefusion_claude_sonnet_answer, codefusion_gpt_5_answer, codewalk_answer=None):
    # Get OpenAI evaluation for all responses
    #print("Evaluating Claude Code's response...")
    claude_code_evaluation = ask_openai_evaluation(question, reference_answer, claude_code_answer)

    #print("Evaluating CodeFusion (Sonnet)'s response...")
    codefusion_claude_sonnet_evaluation = ask_openai_evaluation(question, reference_answer, codefusion_claude_sonnet_answer)

    codefusion_gpt_5_evaluation = None
    #print("Evaluating CodeFusion (GPT-5)'s response...")
    if codefusion_gpt_5_answer:
        codefusion_gpt_5_evaluation = ask_openai_evaluation(question, reference_answer, codefusion_gpt_5_answer)
    

    
    # Evaluate CodeWalk if provided
    codewalk_evaluation = None
    if codewalk_answer:
        #print("Evaluating CodeWalk's response...")
        codewalk_evaluation = ask_openai_evaluation(question, reference_answer, codewalk_answer)

    # Print the results
    print(f"Question: {question}")
    print(f"Reference Answer: {reference_answer}")
    print(f"Claude Code's Answer: {claude_code_answer}")
    print(f"Claude Code's Evaluation: {claude_code_evaluation}")
    print(f"CodeFusion (Sonnet)'s Answer: {codefusion_claude_sonnet_answer}")
    print(f"CodeFusion (Sonnet)'s Evaluation: {codefusion_claude_sonnet_evaluation}")
    if codefusion_gpt_5_answer:
        print(f"CodeFusion (GPT-5) Answer: {codefusion_gpt_5_answer}")
        print(f"CodeFusion (GPT-5) Evaluation: {codefusion_gpt_5_evaluation}")
    if codewalk_answer and codewalk_evaluation:
        print(f"CodeWalk's Answer: {codewalk_answer}")
        print(f"CodeWalk's Evaluation: {codewalk_evaluation}")

    return claude_code_evaluation, codefusion_claude_sonnet_evaluation, codefusion_gpt_5_evaluation, codewalk_evaluation

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


def generate_html_report(evaluation_results, output_path="evaluation_results_django.html"):
    """Generate comprehensive HTML report from evaluation results."""
    
    # Calculate summary statistics
    claude_code_scores = {"arch": [], "consistency": [], "understanding": [], "grounding": []}
    codefusion_claude_sonnet_scores = {"arch": [], "consistency": [], "understanding": [], "grounding": []}
    codefusion_gpt_5_scores = {"arch": [], "consistency": [], "understanding": [], "grounding": []}
    codewalk_scores = {"arch": [], "consistency": [], "understanding": [], "grounding": []}

    dataset = langfuse.get_dataset("django_qa")
    
    for result in evaluation_results:
        # Parse evaluations
        claude_code_eval = parse_evaluation_json(result["claude_code_evaluation"])
        codefusion_claude_sonnet_eval = parse_evaluation_json(result["codefusion_claude_sonnet_evaluation"])
        codefusion_gpt_5_eval = parse_evaluation_json(result.get("codefusion_gpt_5_evaluation", "{}")) if result.get("codefusion_gpt_5_evaluation") else None
        codewalk_eval = parse_evaluation_json(result.get("codewalk_evaluation", "{}")) if result.get("codewalk_evaluation") else None
        for ds_item in dataset.items:
            input = ds_item.input
            if input != result["question"]:
                continue
            
            output = result["claude_code_answer"]
            run_langfuse_eval(ds_item, result["question"], result["claude_code_answer"], claude_code_eval, "django", "claude_code")
            output = result["codefusion_claude_sonnet_answer"]
            run_langfuse_eval(ds_item, result["question"], result["codefusion_claude_sonnet_answer"], codefusion_claude_sonnet_eval, "django", "codefusion_claude_sonnet")
            if result.get("codefusion_gpt_5_answer"):
                output = result["codefusion_gpt_5_answer"]
                run_langfuse_eval(ds_item, result["question"], result["codefusion_gpt_5_answer"], codefusion_gpt_5_eval, "django", "codefusion_gpt_5")
            if result.get("codewalk_answer"):
                output = result["codewalk_answer"]
                run_langfuse_eval(ds_item, result["question"], result["codewalk_answer"], codewalk_eval, "django", "codewalk")
        # Collect Claude Code scores
        claude_code_scores["arch"].append(claude_code_eval["architecture_reasoning"]["score"])
        claude_code_scores["consistency"].append(claude_code_eval["reasoning_consistency"]["score"])
        claude_code_scores["understanding"].append(claude_code_eval["code_understanding_tier"]["score"])
        claude_code_scores["grounding"].append(claude_code_eval["grounding"]["score"])
        
        # Collect CodeFusion scores
        codefusion_claude_sonnet_scores["arch"].append(codefusion_claude_sonnet_eval["architecture_reasoning"]["score"])
        codefusion_claude_sonnet_scores["consistency"].append(codefusion_claude_sonnet_eval["reasoning_consistency"]["score"])
        codefusion_claude_sonnet_scores["understanding"].append(codefusion_claude_sonnet_eval["code_understanding_tier"]["score"])
        codefusion_claude_sonnet_scores["grounding"].append(codefusion_claude_sonnet_eval["grounding"]["score"])
        
        # Collect CodeFusion (GPT-5) scores
        if codefusion_gpt_5_eval:
            codefusion_gpt_5_scores["arch"].append(codefusion_gpt_5_eval["architecture_reasoning"]["score"])
            codefusion_gpt_5_scores["consistency"].append(codefusion_gpt_5_eval["reasoning_consistency"]["score"])
            codefusion_gpt_5_scores["understanding"].append(codefusion_gpt_5_eval["code_understanding_tier"]["score"])
            codefusion_gpt_5_scores["grounding"].append(codefusion_gpt_5_eval["grounding"]["score"])
        
        # Collect CodeWalk scores if available
        if codewalk_eval:
            codewalk_scores["arch"].append(codewalk_eval["architecture_reasoning"]["score"])
            codewalk_scores["consistency"].append(codewalk_eval["reasoning_consistency"]["score"])
            codewalk_scores["understanding"].append(codewalk_eval["code_understanding_tier"]["score"])
            codewalk_scores["grounding"].append(codewalk_eval["grounding"]["score"])
    
    # Calculate averages
    claude_code_avg = {
        "arch": sum(claude_code_scores["arch"]) / len(claude_code_scores["arch"]),
        "consistency": sum(claude_code_scores["consistency"]) / len(claude_code_scores["consistency"]),
        "understanding": sum(claude_code_scores["understanding"]) / len(claude_code_scores["understanding"]),
        "grounding": sum(claude_code_scores["grounding"]) / len(claude_code_scores["grounding"])
    }
    
    codefusion_claude_sonnet_avg = {
        "arch": sum(codefusion_claude_sonnet_scores["arch"]) / len(codefusion_claude_sonnet_scores["arch"]),
        "consistency": sum(codefusion_claude_sonnet_scores["consistency"]) / len(codefusion_claude_sonnet_scores["consistency"]),
        "understanding": sum(codefusion_claude_sonnet_scores["understanding"]) / len(codefusion_claude_sonnet_scores["understanding"]),
        "grounding": sum(codefusion_claude_sonnet_scores["grounding"]) / len(codefusion_claude_sonnet_scores["grounding"])
    }
    codefusion_gpt_5_avg = None
    if codefusion_gpt_5_scores["arch"]:
        codefusion_gpt_5_avg = {
            "arch": sum(codefusion_gpt_5_scores["arch"]) / len(codefusion_gpt_5_scores["arch"]),
            "consistency": sum(codefusion_gpt_5_scores["consistency"]) / len(codefusion_gpt_5_scores["consistency"]),
            "understanding": sum(codefusion_gpt_5_scores["understanding"]) / len(codefusion_gpt_5_scores["understanding"]),
            "grounding": sum(codefusion_gpt_5_scores["grounding"]) / len(codefusion_gpt_5_scores["grounding"])
        }
    
    # Calculate CodeWalk averages if data is available
    codewalk_avg = None
    if codewalk_scores["arch"]:  # Check if we have CodeWalk data
        codewalk_avg = {
            "arch": sum(codewalk_scores["arch"]) / len(codewalk_scores["arch"]),
            "consistency": sum(codewalk_scores["consistency"]) / len(codewalk_scores["consistency"]),
            "understanding": sum(codewalk_scores["understanding"]) / len(codewalk_scores["understanding"]),
            "grounding": sum(codewalk_scores["grounding"]) / len(codewalk_scores["grounding"])
        }
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Django Q&A Evaluation Report</title>
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
        .claude-code-answer {{ border-left-color: #17a2b8; }}
        .codefusion-claude-sonnet-answer {{ border-left-color: #ffc107; }}
        .codefusion-gpt-5-answer {{ border-left-color: #6f42c1; }}
        .codewalk-answer {{ border-left-color: #6f42c1; }}
        
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
        
        .claude-code-column {{
            border-top: 4px solid #17a2b8;
        }}
        
        .codefusion-claude-sonnet-column {{
            border-top: 4px solid #6f42c1;
        }}

        .codefusion-gpt-5-column {{
            border-top: 4px solid #ffc107;
        }}
        
        .codewalk-column {{
            border-top: 4px solid #28a745;
        }}
        
        .model-header {{
            padding: 12px 15px;
            font-weight: bold;
            color: white;
            text-align: center;
        }}
        
        .claude-code-column .model-header {{
            background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
        }}
        
        .codefusion-claude-sonnet-column .model-header {{
            background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
            color: #333;
        }}
        
        .codefusion-gpt-5-column .model-header {{
            background: linear-gradient(135deg, #6f42c1 0%, #5a32a3 100%);
        }}
        
        .codewalk-column .model-header {{
            background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);
        }}
        
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
</head>
<body>
    <div class="container">
        <h1>📊 Django Q&A Evaluation Report</h1>
        <p style="text-align: center; color: #6c757d; margin-bottom: 40px;">
            Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | 
            {len(evaluation_results)} questions evaluated
        </p>
        
        <h2>📋 Question-by-Question Score Comparison</h2>
        <table class="summary-table">
            <thead>
                <tr>
                    <th style="width: 20%;">Question</th>
                    <th colspan="4" style="text-align: center; background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);">🤖 Claude Code</th>
                    <th colspan="4" style="text-align: center; background: linear-gradient(135deg, #6f42c1 0%, #5a32a3 100%);">✨ CodeFusion (Sonnet)</th>
                </tr>
                <tr>
                    <th></th>
                    <th>Arch</th>
                    <th>Reasoning</th>
                    <th>Code Tier</th>
                    <th>Grounding</th>
                    <th>Arch</th>
                    <th>Reasoning</th>
                    <th>Code Tier</th>
                    <th>Grounding</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add score comparison rows
    for i, result in enumerate(evaluation_results, 1):
        claude_code_eval = parse_evaluation_json(result["claude_code_evaluation"])
        codefusion_claude_sonnet_eval = parse_evaluation_json(result["codefusion_claude_sonnet_evaluation"])
        codefusion_gpt_5_eval = parse_evaluation_json(result.get("codefusion_gpt_5_evaluation", "{}")) if result.get("codefusion_gpt_5_evaluation") else None
        codewalk_eval = parse_evaluation_json(result.get("codewalk_evaluation", "{}")) if result.get("codewalk_evaluation") else None
        
        question_preview = result['question'][:50] + ('...' if len(result['question']) > 50 else '')
        
        # Escape quotes for HTML tooltip attribute
        full_question_escaped = result['question'].replace('"', '&quot;').replace("'", "&#39;")
        
        html_content += f"""
                <tr onclick="toggleDetails({i})" style="cursor: pointer;" title="Click to view detailed answers and feedback">
                    <td style="font-weight: 500;" class="question-tooltip" data-tooltip="{full_question_escaped}"><strong>Q{i}:</strong> {question_preview}</td>
                    <td><span class="score {get_score_class(claude_code_eval['architecture_reasoning']['score'])}">{claude_code_eval['architecture_reasoning']['score']}/5</span></td>
                    <td><span class="score {get_score_class(claude_code_eval['reasoning_consistency']['score'])}">{claude_code_eval['reasoning_consistency']['score']}/5</span></td>
                    <td><span class="score {get_score_class(claude_code_eval['code_understanding_tier']['score'])}">{claude_code_eval['code_understanding_tier']['score']}/5</span><span class="tier-badge">{claude_code_eval['code_understanding_tier'].get('tier', 'unknown')}</span></td>
                    <td><span class="score {get_score_class(claude_code_eval['grounding']['score'])}">{claude_code_eval['grounding']['score']}/5</span></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_eval['architecture_reasoning']['score'])}">{codefusion_claude_sonnet_eval['architecture_reasoning']['score']}/5</span></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_eval['reasoning_consistency']['score'])}">{codefusion_claude_sonnet_eval['reasoning_consistency']['score']}/5</span></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_eval['code_understanding_tier']['score'])}">{codefusion_claude_sonnet_eval['code_understanding_tier']['score']}/5</span><span class="tier-badge">{codefusion_claude_sonnet_eval['code_understanding_tier'].get('tier', 'unknown')}</span></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_eval['grounding']['score'])}">{codefusion_claude_sonnet_eval['grounding']['score']}/5</span></td>
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
        claude_code_eval = parse_evaluation_json(result["claude_code_evaluation"])
        codefusion_claude_sonnet_eval = parse_evaluation_json(result["codefusion_claude_sonnet_evaluation"])
        codefusion_gpt_5_eval = parse_evaluation_json(result.get("codefusion_gpt_5_evaluation", "{}")) if result.get("codefusion_gpt_5_evaluation") else None
        codewalk_eval = parse_evaluation_json(result.get("codewalk_evaluation", "{}")) if result.get("codewalk_evaluation") else None
        
        question_preview = result['question'][:80] + ('...' if len(result['question']) > 80 else '')
        
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
                    <div class="answer-text">{result['reference_answer']}</div>
                </div>
                
                <div class="models-comparison">
                    <div class="model-column claude-column">
                        <div class="model-header">🤖 Claude Code</div>
                        <div class="answer-text">{result['claude_code_answer']}</div>
                        <div class="feedback-section">
                            <div class="feedback-item">
                                <strong>Architecture ({claude_code_eval['architecture_reasoning']['score']}/5):</strong>
                                <div class="feedback-text">{claude_code_eval['architecture_reasoning']['feedback']}</div>
                            </div>
                            <div class="feedback-item">
                                <strong>Reasoning Consistency ({claude_code_eval['reasoning_consistency']['score']}/5):</strong>
                                <div class="feedback-text">{claude_code_eval['reasoning_consistency']['feedback']}</div>
                            </div>
                            <div class="feedback-item">
                                <strong>Code Tier ({claude_code_eval['code_understanding_tier']['score']}/5 - {claude_code_eval['code_understanding_tier'].get('tier', 'unknown')}):</strong>
                                <div class="feedback-text">{claude_code_eval['code_understanding_tier']['feedback']}</div>
                            </div>
                            <div class="feedback-item">
                                <strong>Grounding ({claude_code_eval['grounding']['score']}/5):</strong>
                                <div class="feedback-text">{claude_code_eval['grounding']['feedback']}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="model-column claude-sonnet-column">
                        <div class="model-header">✨ CodeFusion (Sonnet)</div>
                        <div class="answer-text">{result['codefusion_claude_sonnet_answer']}</div>
                        <div class="feedback-section">
                            <div class="feedback-item">
                                <strong>Architecture ({codefusion_claude_sonnet_eval['architecture_reasoning']['score']}/5):</strong>
                                <div class="feedback-text">{codefusion_claude_sonnet_eval['architecture_reasoning']['feedback']}</div>
                            </div>
                            <div class="feedback-item">
                                <strong>Reasoning Consistency ({codefusion_claude_sonnet_eval['reasoning_consistency']['score']}/5):</strong>
                                <div class="feedback-text">{codefusion_claude_sonnet_eval['reasoning_consistency']['feedback']}</div>
                            </div>
                            <div class="feedback-item">
                                <strong>Code Tier ({codefusion_claude_sonnet_eval['code_understanding_tier']['score']}/5 - {codefusion_claude_sonnet_eval['code_understanding_tier'].get('tier', 'unknown')}):</strong>
                                <div class="feedback-text">{codefusion_claude_sonnet_eval['code_understanding_tier']['feedback']}</div>
                            </div>
                            <div class="feedback-item">
                                <strong>Grounding ({codefusion_claude_sonnet_eval['grounding']['score']}/5):</strong>
                                <div class="feedback-text">{codefusion_claude_sonnet_eval['grounding']['feedback']}</div>
                            </div>
                        </div>
                    </div>
                """
            
        html_content += """
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """
    
    # Calculate overall averages for winner determination
    claude_code_overall = (claude_code_avg['arch'] + claude_code_avg['consistency'] + claude_code_avg['understanding'] + claude_code_avg['grounding']) / 4
    codefusion_claude_sonnet_overall = (codefusion_claude_sonnet_avg['arch'] + codefusion_claude_sonnet_avg['consistency'] + codefusion_claude_sonnet_avg['understanding'] + codefusion_claude_sonnet_avg['grounding']) / 4
    
    # Calculate CodeWalk overall if available
    codewalk_overall = None
    if codewalk_avg:
        codewalk_overall = (codewalk_avg['arch'] + codewalk_avg['consistency'] + codewalk_avg['understanding'] + codewalk_avg['grounding']) / 4
    
    # Determine winner
    scores = [("Claude Code", claude_code_overall), ("CodeFusion (Sonnet)", codefusion_claude_sonnet_overall)]
    if codewalk_overall is not None:
        scores.append(("CodeWalk", codewalk_overall))
    
    winner, winner_score = max(scores, key=lambda x: x[1])
    
    # Determine best category across all models
    category_averages = {
        "Architecture": (claude_code_avg['arch'] + codefusion_claude_sonnet_avg['arch'] + (codewalk_avg['arch'] if codewalk_avg else 0)) / (2 if codewalk_avg else 2),
        "Reasoning": (claude_code_avg['consistency'] + codefusion_claude_sonnet_avg['consistency'] + (codewalk_avg['consistency'] if codewalk_avg else 0)) / (2 if codewalk_avg else 2),
        "Code Tier": (claude_code_avg['understanding'] + codefusion_claude_sonnet_avg['understanding'] + (codewalk_avg['understanding'] if codewalk_avg else 0)) / (2 if codewalk_avg else 2),
        "Grounding": (claude_code_avg['grounding'] + codefusion_claude_sonnet_avg['grounding'] + (codewalk_avg['grounding'] if codewalk_avg else 0)) / (2 if codewalk_avg else 2)
    }
    best_category = max(category_averages, key=category_averages.get)
    
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
                <tr>
                    <td><strong>Claude Code</strong></td>
                    <td><span class="score {get_score_class(claude_code_avg['arch'])}">{claude_code_avg['arch']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(claude_code_avg['consistency'])}">{claude_code_avg['consistency']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(claude_code_avg['understanding'])}">{claude_code_avg['understanding']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(claude_code_avg['grounding'])}">{claude_code_avg['grounding']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(claude_code_overall)}">{claude_code_overall:.1f}/5</span></td>
                </tr>
                <tr>
                    <td><strong>CodeFusion (Sonnet)</strong></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_avg['arch'])}">{codefusion_claude_sonnet_avg['arch']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_avg['consistency'])}">{codefusion_claude_sonnet_avg['consistency']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_avg['understanding'])}">{codefusion_claude_sonnet_avg['understanding']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_avg['grounding'])}">{codefusion_claude_sonnet_avg['grounding']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(codefusion_claude_sonnet_overall)}">{codefusion_claude_sonnet_overall:.1f}/5</span></td>
                </tr>"""
    
    # Add CodeWalk row if data is available
    if codewalk_avg and codewalk_overall is not None:
        html_content += f"""
                <tr>
                    <td><strong>CodeWalk</strong></td>
                    <td><span class="score {get_score_class(codewalk_avg['arch'])}">{codewalk_avg['arch']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(codewalk_avg['consistency'])}">{codewalk_avg['consistency']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(codewalk_avg['understanding'])}">{codewalk_avg['understanding']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(codewalk_avg['grounding'])}">{codewalk_avg['grounding']:.1f}/5</span></td>
                    <td><span class="score {get_score_class(codewalk_overall)}">{codewalk_overall:.1f}/5</span></td>
                </tr>"""
    
    html_content += f"""
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
            <p>📊 FastAPI Q&A Evaluation Report - Three-Model Comparison</p>
        </div>
    </div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML report generated: {output_path}")
    return output_path

def main():
    eval_data_path = 'cf/evals/django_qa.yaml'
    with open(eval_data_path, 'r') as f:
         eval_data = yaml.safe_load(f)
    
    # Collect all evaluation results
    evaluation_results = []
    
    for qdata in eval_data["questions"]:
        question = qdata["question"]
        reference_answer = qdata["reference_answer"]
        claude_code_answer = qdata["claude_code_answer"]
        codefusion_claude_sonnet_answer = qdata["codefusion_claude-sonnet-4-20250514_answer"]
        codefusion_gpt_5_answer = qdata["codefusion_gpt-5_answer"]
        codewalk_answer = qdata.get("codewalk_answer")  # CodeWalk might not be present
        claude_code_evaluation, codefusion_claude_sonnet_evaluation, codefusion_gpt_5_evaluation, codewalk_evaluation = compare_responses(question, reference_answer, claude_code_answer, codefusion_claude_sonnet_answer, codefusion_gpt_5_answer, codewalk_answer)
        
        # Store results for HTML generation
        result_data = {
            "question": question,
            "reference_answer": reference_answer,
            "claude_code_answer": claude_code_answer,
            "codefusion_claude_sonnet_answer": codefusion_claude_sonnet_answer,
            "codefusion_gpt_5_answer": codefusion_gpt_5_answer,
            "claude_code_evaluation": claude_code_evaluation,
            "codefusion_claude_sonnet_evaluation": codefusion_claude_sonnet_evaluation,
            "codefusion_gpt_5_evaluation": codefusion_gpt_5_evaluation
        }
        
        # Add CodeWalk data if available
        if codewalk_answer:
            result_data["codewalk_answer"] = codewalk_answer
        if codewalk_evaluation:
            result_data["codewalk_evaluation"] = codewalk_evaluation
            
        evaluation_results.append(result_data)
    
    # Generate HTML report
    html_file = generate_html_report(evaluation_results)
    print(f"\n🎉 Evaluation complete! HTML report generated: {html_file}")

if __name__ == "__main__":
    main()
