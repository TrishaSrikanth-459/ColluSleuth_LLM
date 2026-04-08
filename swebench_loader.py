"""
Load SWE-bench Verified tasks for code synthesis.

STRICT VERSION:
- No test extraction
- No patch cleaning
- Fully compatible with SWE-bench harness
"""
from datasets import load_dataset
from typing import List, Dict, Any


def load_swebench_tasks(num_tasks: int = 100) -> List[Dict[str, Any]]:
    """
    Load SWE-bench Verified tasks from Hugging Face.

    Each task contains:
    - task_id
    - prompt (issue description)
    - repo
    - base_commit
    - patch (ground truth, NOT for execution)
    """

    dataset = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

    tasks: List[Dict[str, Any]] = []

    for item in dataset.select(range(min(num_tasks, len(dataset)))):

        issue = item["problem_statement"]

        # 🔥 FIX: prompt must request PATCH, not code
        prompt = (
            f"You are fixing a real GitHub issue.\n\n"
            f"Issue:\n{issue}\n\n"
            "IMPORTANT:\n"
            "- You MUST output a unified diff patch\n"
            "- Do NOT output raw Python code\n"
            "- Format:\n"
            "--- a/file.py\n"
            "+++ b/file.py\n"
            "@@ ...\n"
        )

        tasks.append({
            "task_id": item["instance_id"],
            "prompt": prompt,
            "repo": item["repo"],
            "base_commit": item["base_commit"],
            "patch": item["patch"],  # ground truth (for reference only)
        })

    return tasks