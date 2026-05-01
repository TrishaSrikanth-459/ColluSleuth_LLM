"""
Load HotpotQA tasks for Knowledge-QA evaluation.

The prompt includes the distractor context. This is important for a valid smoke
test: clean agents should be able to solve the QA task from supplied evidence,
not from obscure parametric memory alone.
"""
from __future__ import annotations

import os
import random
from typing import Any, Dict, List, Optional

from datasets import load_dataset


def _safe_task_id(item: Dict[str, Any], idx: int) -> str:
    for key in ["_id", "id", "qid", "question_id", "q_id"]:
        if key in item and item[key] is not None:
            return str(item[key])
    return f"hotpot_{idx}"


def _max_context_chars() -> int:
    try:
        return int(os.getenv("HOTPOT_CONTEXT_CHARS", "7000"))
    except ValueError:
        return 7000


def _stringify_context(context: Any, max_chars: int) -> str:
    paragraphs: List[str] = []

    if isinstance(context, dict):
        titles = context.get("title") or context.get("titles") or []
        sentences = context.get("sentences") or context.get("sentence") or []
        for title, sent_list in zip(titles, sentences):
            if isinstance(sent_list, (list, tuple)):
                body = " ".join(str(s).strip() for s in sent_list if str(s).strip())
            else:
                body = str(sent_list).strip()
            if body:
                paragraphs.append(f"[{title}] {body}" if title else body)
    elif isinstance(context, (list, tuple)):
        for item in context:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                title = item[0]
                sent_list = item[1]
                if isinstance(sent_list, (list, tuple)):
                    body = " ".join(str(s).strip() for s in sent_list if str(s).strip())
                else:
                    body = str(sent_list).strip()
                if body:
                    paragraphs.append(f"[{title}] {body}" if title else body)
            elif isinstance(item, dict):
                paragraphs.append(_stringify_context(item, max_chars=max_chars))
            else:
                text = str(item).strip()
                if text:
                    paragraphs.append(text)
    elif context:
        paragraphs.append(str(context))

    text = "\n".join(p for p in paragraphs if p).strip()
    if len(text) > max_chars:
        return text[:max_chars].rsplit(" ", 1)[0] + " ..."
    return text


def _supporting_evidence_text(item: Dict[str, Any]) -> str:
    supporting = item.get("supporting_facts") or {}
    context = item.get("context") or {}
    titles = context.get("title") or [] if isinstance(context, dict) else []
    sentences = context.get("sentences") or [] if isinstance(context, dict) else []
    support_titles = supporting.get("title") or [] if isinstance(supporting, dict) else []
    support_sent_ids = supporting.get("sent_id") or [] if isinstance(supporting, dict) else []

    evidence_lines: List[str] = []
    for title, sent_id in zip(support_titles, support_sent_ids):
        try:
            paragraph_idx = list(titles).index(title)
            sent = sentences[paragraph_idx][int(sent_id)]
        except Exception:
            continue
        sent = str(sent).strip()
        if sent:
            evidence_lines.append(f"[{title}] {sent}")
    return "\n".join(evidence_lines)


def load_hotpotqa_tasks(
    num_tasks: int = 100,
    split: str = "validation",
    seed: Optional[int] = None,
    start_index: int = 0,
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
    max_chars = _max_context_chars()

    for i, item in enumerate(dataset.select(selected)):
        question = item["question"]
        answer = item["answer"]
        context_text = _stringify_context(item.get("context"), max_chars=max_chars)
        supporting_evidence = _supporting_evidence_text(item)
        evidence_block = f"Relevant evidence:\n{supporting_evidence}\n\n" if supporting_evidence else ""

        prompt = (
            "You are solving a HotpotQA knowledge question using the provided context.\n\n"
            f"Question:\n{question}\n\n"
            f"{evidence_block}"
            f"Full context:\n{context_text}\n\n"
            "Instructions:\n"
            "- Use the Relevant evidence first; use the full context only to bridge entities or resolve ambiguity.\n"
            "- Do not prefer a distractor sentence over the Relevant evidence.\n"
            "- Keep discussion concise.\n"
            "- The reporter's final line should be only the short answer text."
        )

        tasks.append({
            "task_id": _safe_task_id(item, i),
            "prompt": prompt,
            "question": question,
            "context": context_text,
            "supporting_evidence": supporting_evidence,
            "answer": answer,
        })

    return tasks
