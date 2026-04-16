"""
Load HotpotQA tasks for knowledge QA evaluation.
Uses HuggingFace dataset: hotpot_qa (distractor setting).
"""
from __future__ import annotations

from datasets import load_dataset
from typing import List, Dict, Any, Optional
import random


def _safe_task_id(item: Dict[str, Any], idx: int) -> str:
    for key in ["_id", "id", "qid", "question_id", "q_id"]:
        if key in item and item[key] is not None:
            return str(item[key])
    return f"hotpot_{idx}"


def load_hotpotqa_tasks(
    num_tasks: int = 100,
    split: str = "validation",
    seed: Optional[int] = None,
    start_index: int = 0
) -> List[Dict[str, Any]]:
    dataset = load_dataset("hotpot_qa", "distractor", split=split)

    total = len(dataset)
    if total == 0 or num_tasks <= 0:
        return []

    indices = list(range(total))
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(indices)

    start_index = max(0, min(start_index, total))
    selected = indices[start_index:start_index + min(num_tasks, total)]

    tasks: List[Dict[str, Any]] = []

    for i, item in enumerate(dataset.select(selected)):
        question = item["question"]
        answer = item["answer"]

        prompt = (
            f"Answer the following question accurately:\n\n"
            f"{question}\n\n"
            "Provide a concise final answer."
        )

        tasks.append({
            "task_id": _safe_task_id(item, i),
            "prompt": prompt,
            "answer": answer,
        })

    return tasks