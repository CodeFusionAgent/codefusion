# Import necessary libraries
from dotenv import load_dotenv

import yaml
from langfuse import Langfuse
# Load environment variables
load_dotenv()


# Generate dataset


dataset_file = 'cf/evals/django_qa.yaml'
# dataset_names = ["claude_code", "codefusion (gpt-5)", "codefusion (sonnet)", "codewalk"]
dataset_names = ["django_qa_1"]
        
# Note: we're choosing to create the dataset in Langfuse below, but it's equally easy to create it in another platform.
langfuse = Langfuse()

for dataset_name in dataset_names:
    langfuse.create_dataset(
        name=dataset_name,
        description=""
    )

with open(dataset_file, 'r') as f:
    django_dataset = yaml.safe_load(f)

for qdata in django_dataset["questions"]:
    question = qdata["question"]
    reference_answer = qdata["reference_answer"]
    claude_code_answer = qdata["claude_code_answer"]
    codefusion_claude_sonnet_answer = qdata["codefusion_claude-sonnet-4-20250514_answer"]
    codefusion_gpt_5_answer = qdata.get("codefusion_gpt-5_answer")
    codewalk_answer = qdata.get("codewalk_answer")
    answers = [claude_code_answer, codefusion_gpt_5_answer, codefusion_claude_sonnet_answer, codewalk_answer]

    for i, dataset_name in enumerate(dataset_names):
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            input=question,
            expected_output=reference_answer
        )