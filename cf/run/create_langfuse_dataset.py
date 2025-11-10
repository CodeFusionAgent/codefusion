# Import necessary libraries
from dotenv import load_dotenv

import yaml
from langfuse import Langfuse
# Load environment variables
load_dotenv()


# Generate dataset


dataset_file = 'cf/evals/fastapi_qa.yaml'
# dataset_names = ["claude_code", "codefusion (gpt-5)", "codefusion (sonnet)", "codewalk"]
dataset_names = ["fastapi_qa"]
        
# Note: we're choosing to create the dataset in Langfuse below, but it's equally easy to create it in another platform.
langfuse = Langfuse()

for dataset_name in dataset_names:
    langfuse.create_dataset(
        name=dataset_name,
        description=""
    )

with open(dataset_file, 'r') as f:
    fastapi_dataset = yaml.safe_load(f)

for qdata in fastapi_dataset["questions"]:
    question = qdata["question"]
    reference_answer = qdata["reference_answer"]
    claude_answer = qdata["claude_answer"]
    codefusion_answer = qdata["codefusion_answer_oai"]
    claude_sonnet_answer = qdata["claude_sonnet_answer"]
    codewalk_answer = qdata.get("codewalk_answer")  # CodeWalk might not be present
    answers = [claude_answer, codefusion_answer, claude_sonnet_answer, codewalk_answer]

    for i, dataset_name in enumerate(dataset_names):
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            input=question,
            expected_output=reference_answer
        )