"""
Load SWE-bench Verified tasks for code synthesis.

The prompt stays benchmark-compatible, but we now include the repo, base commit,
known hints, and test names so the worker is not operating from issue text alone.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from datasets import load_dataset


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


def load_swebench_tasks(num_tasks: int = 100, start_index: int = 0) -> List[Dict[str, Any]]:
    dataset = load_dataset(DATASET_NAME, split="test")
    total = len(dataset)
    if total == 0 or num_tasks <= 0:
        return []

    start_index = max(0, min(start_index, total))
    selected = dataset.select(range(start_index, min(start_index + num_tasks, total)))

    tasks: List[Dict[str, Any]] = []
    for item in selected:
        issue = _safe_text(item.get("problem_statement"))
        repo = _safe_text(item.get("repo"))
        base_commit = _safe_text(item.get("base_commit"))
        hints_text = _safe_text(item.get("hints_text"))
        fail_to_pass = _format_test_names(item.get("FAIL_TO_PASS"))
        pass_to_pass = _format_test_names(item.get("PASS_TO_PASS"))

        prompt_lines = [
            "You are fixing a real GitHub issue from SWE-bench Verified.",
            "",
            f"Repository: {repo}",
            f"Base commit: {base_commit}",
            f"Instance ID: {_safe_text(item.get('instance_id'))}",
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
            "task_id": item["instance_id"],
            "prompt": "\n".join(prompt_lines),
            "repo": repo,
            "base_commit": base_commit,
            "patch": item.get("patch", ""),
            "test_patch": item.get("test_patch", ""),
            "hints_text": hints_text,
            "fail_to_pass": fail_to_pass,
            "pass_to_pass": pass_to_pass,
        })

    return tasks
