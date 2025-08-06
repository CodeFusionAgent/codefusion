#!/usr/bin/env python3
"""
CodeFusion Evaluation Script

Compares CodeFusion responses against reference answers using OpenAI as judge.
"""

import openai
import sys
import yaml

from cf.configs.config_mgr import ConfigManager

# Function to evaluate using OpenAI (Judge)
def ask_openai_evaluation(question, reference_answer, response):
    # Set the evaluation prompt based on the tier and the response
    evaluation_prompt = f"""
    Please evaluate the following responses based on accuracy, coherence, reasoning consistency, and grounding:

    **Question:** {question}

    **Reference Answer:** {reference_answer}

    **Model Response:** {response}

    **Evaluation Criteria:**
    1. **Architecture-Level Reasoning**: Does the response provide clear reasoning about the system's design, modules, or architecture? (Score 1-10)
    2. **Reasoning Consistency**: Is the reasoning consistent? Does it follow a logical and coherent flow? (Score 1-10)
    3. **Code Understanding Tier**: Categorize the question into one of the following tiers: performance-related, runtime-related, inter-module, or architectural. How well does the model understand the question within the given code understanding tier? (Score 1-10)
    4. **Grounding Score**: How factual and accurate is the response? Does it align with the reference answer? (Score 1-10)

    Provide a detailed evaluation based on these criteria, and include any necessary feedback.
    """
    config_mgr = ConfigManager("cf/configs/config.yaml")
    config = config_mgr.get_config()
    # Send the prompt to OpenAI for evaluation
    openai.api_key=config.get("llm.api_key")
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": evaluation_prompt}
        ],
        temperature=config.get("llm.temperature"),
    )
    return response.choices[0].message.content.strip()

# Function to compare responses based on all criteria
def compare_responses(question, reference_answer, claude_response, your_response):
    # Get OpenAI evaluation for both responses (Claude and your response)
    #print("Evaluating Claude's response...")
    claude_evaluation = ask_openai_evaluation(question, reference_answer, claude_response)
    
    #print("Evaluating Your response...")
    your_evaluation = ask_openai_evaluation(question, reference_answer, your_response)

    # Print the results
    print(f"Question: {question}")
    #print(f"Reference Answer: {reference_answer}")
    #print(f"Claude's Response: {claude_response}")
    #print(f"Your Response: {your_response}")
    print("-" * 40)
    print(f"Claude's Evaluation: {claude_evaluation}")
    print("-" * 40)
    print(f"CodeFusion Evaluation: {your_evaluation}")
    print("=" * 80)

def main():
    eval_data_path = 'cf/evals/fastapi_qa.yaml'
    with open(eval_data_path, 'r') as f:
         eval_data = yaml.safe_load(f)
    for qdata in eval_data["questions"]:
        question = qdata["question"]
        reference_answer = qdata["reference_answer"]
        claude_answer = qdata["claude_answer"]
        codefusion_answer = qdata["codefusion_answer"]
        compare_responses(question, reference_answer, claude_answer, codefusion_answer)

if __name__ == "__main__":
    main()
