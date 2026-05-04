"""
Load SWE-bench Verified tasks for code synthesis experiments.
"""
from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional


DATASET_NAME = "princeton-nlp/SWE-bench_Verified"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _format_test_names(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return ""
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return ", ".join(str(v).strip() for v in parsed if str(v).strip())
        except Exception:
            pass
        return raw
    return str(value).strip()


def load_swebench_tasks(
    num_tasks: int = 25,
    seed: Optional[int] = None,
    start_index: int = 0,
) -> List[Dict[str, Any]]:
    from datasets import load_dataset

    dataset = load_dataset(DATASET_NAME, split="test")
    total = len(dataset)
    if total == 0 or num_tasks <= 0:
        return []

    indices = list(range(total))
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(indices)

    start_index = max(0, min(start_index, total))
    selected_indices = indices[start_index : start_index + min(num_tasks, total - start_index)]
    selected = dataset.select(selected_indices)

    tasks: List[Dict[str, Any]] = []
    for item in selected:
        issue = _safe_text(item.get("problem_statement"))
        repo = _safe_text(item.get("repo"))
        base_commit = _safe_text(item.get("base_commit"))
        hints_text = _safe_text(item.get("hints_text"))
        fail_to_pass = _format_test_names(item.get("FAIL_TO_PASS"))
        pass_to_pass = _format_test_names(item.get("PASS_TO_PASS"))
        instance_id = _safe_text(item.get("instance_id"))

        prompt_lines = [
            "You are collaboratively fixing a real GitHub issue from SWE-bench Verified.",
            "",
            f"Repository: {repo}",
            f"Base commit: {base_commit}",
            f"Instance ID: {instance_id}",
            "",
            "Issue:",
            issue,
        ]
        if hints_text:
            prompt_lines.extend(["", "Available hint:", hints_text])
        if fail_to_pass:
            prompt_lines.extend(["", "Tests expected to start passing:", fail_to_pass])
        if pass_to_pass:
            prompt_lines.extend(["", "Tests that should remain passing:", pass_to_pass])
        prompt_lines.extend([
            "",
            "Output requirements:",
            "- Return ONLY a unified diff patch.",
            "- Do NOT return prose, markdown fences, or raw standalone code.",
            "- Do NOT use placeholders such as '...', 'TODO', or 'same as above'.",
            "- Modify the smallest plausible set of files.",
            "- Do not invent files or APIs unless the issue clearly requires them.",
            "- Preserve existing behavior outside the bug fix.",
            "",
            "Unified diff format reminder:",
            "--- a/file.py",
            "+++ b/file.py",
            "@@ ...",
        ])

        tasks.append({
            "task_id": instance_id,
            "prompt": "\n".join(prompt_lines),
            "repo": repo,
            "base_commit": base_commit,
            "patch": item.get("patch", ""),
            "test_patch": item.get("test_patch", ""),
            "hints_text": hints_text,
            "fail_to_pass": fail_to_pass,
            "pass_to_pass": pass_to_pass,
            "answer": item.get("patch", ""),
        })

    return tasks
