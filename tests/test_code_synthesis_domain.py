import random
import subprocess
import types
from importlib import reload

import pytest

from covert_collusive_hotpot.core.models import AttackType, Role
from covert_collusive_hotpot.domains.code_synthesis import CodeSynthesisDomain
from covert_collusive_hotpot.domains.code_synthesis.detector_tools import (
    _extract_code_from_patch,
    analyze_patch,
    make_cs_evidence_validator,
)
from covert_collusive_hotpot.experiments.prompt_injection import inject_hidden_prompts
from covert_collusive_hotpot.experiments.role_assignment import assign_roles, mark_malicious


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_agents(m: int = 1) -> list:
    agents = assign_roles("code_synthesis", num_workers=6, rng=random.Random(0))
    return mark_malicious(agents, m, rng=random.Random(0))


def _make_fake_autogen_agent():
    agent = types.SimpleNamespace()
    agent.system_message = "default"
    agent._function_map = {}
    return agent


# ---------------------------------------------------------------------------
# CodeSynthesisDomain capabilities
# ---------------------------------------------------------------------------

def test_code_synthesis_domain_name() -> None:
    assert CodeSynthesisDomain().name == "code_synthesis"


def test_code_synthesis_domain_language_only_permissions_false() -> None:
    assert CodeSynthesisDomain().capabilities.language_only_permissions is False


def test_code_synthesis_domain_deferred_functional_correctness_true() -> None:
    assert CodeSynthesisDomain().capabilities.deferred_functional_correctness is True


def test_code_synthesis_registered_in_global_registry() -> None:
    import covert_collusive_hotpot.domains.registry as reg_module
    reload(reg_module)
    registry = reg_module.get_domain_registry()
    assert "code_synthesis" in registry.names()


# ---------------------------------------------------------------------------
# Task pool delegation
# ---------------------------------------------------------------------------

def test_build_task_pool_delegates_to_swebench_loader(monkeypatch) -> None:
    import covert_collusive_hotpot.experiments.swebench_loader as loader_module

    calls = {}

    def fake_load(num_tasks, seed):
        calls["num_tasks"] = num_tasks
        calls["seed"] = seed
        return [{"task_id": "t0", "prompt": "p", "answer": ""}]

    monkeypatch.setattr(loader_module, "load_swebench_tasks", fake_load)

    domain = CodeSynthesisDomain()
    result = domain.build_task_pool(task_count=3, seed=42)

    assert calls == {"num_tasks": 3, "seed": 42}
    assert len(result) == 1


# ---------------------------------------------------------------------------
# Role assignment
# ---------------------------------------------------------------------------

def test_assign_roles_accepts_code_synthesis() -> None:
    agents = assign_roles("code_synthesis", num_workers=6, rng=random.Random(0))
    reporters = [a for a in agents if a.role == Role.REPORTER]
    assert len(agents) == 6
    assert len(reporters) == 1


# ---------------------------------------------------------------------------
# Prompt injection adaptations
# ---------------------------------------------------------------------------

def test_inject_hidden_prompts_uses_custom_adaptations() -> None:
    agents = _make_agents(m=1)
    custom = {
        AttackType.SUBOPTIMAL_FIXATION: "CUSTOM_CS_ADAPTATION",
        AttackType.REFRAMING_MISALIGNMENT: "x",
        AttackType.FAKE_INJECTION: "x",
        AttackType.EXECUTION_DELAY: "x",
    }
    result = inject_hidden_prompts(
        agents, m=1, attack_type=AttackType.SUBOPTIMAL_FIXATION,
        knowledge_level=None, detector_ids=[], detector_visible=False,
        tool_knowledge=False, interrogation_turns=None, adaptations=custom,
    )
    malicious = [a for a in result if a.is_malicious]
    assert len(malicious) == 1
    assert "CUSTOM_CS_ADAPTATION" in malicious[0].hidden_prompt


def test_inject_hidden_prompts_default_adaptations_unchanged() -> None:
    agents = _make_agents(m=1)
    result = inject_hidden_prompts(
        agents, m=1, attack_type=AttackType.SUBOPTIMAL_FIXATION,
        knowledge_level=None, detector_ids=[], detector_visible=False,
        tool_knowledge=False, interrogation_turns=None,
    )
    malicious = [a for a in result if a.is_malicious]
    assert "Knowledge-QA" in malicious[0].hidden_prompt


# ---------------------------------------------------------------------------
# Detector tools
# ---------------------------------------------------------------------------

def test_code_synthesis_domain_detector_tools_returns_nonempty() -> None:
    class FakeDet:
        id = 1
        autogen_agent = _make_fake_autogen_agent()

    domain = CodeSynthesisDomain()
    tools = domain.detector_tools(FakeDet())
    assert len(tools) > 0
    assert all(callable(fn) for fn in tools)


def test_extract_code_from_patch_extracts_added_lines() -> None:
    patch = "--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,3 @@\n foo\n+bar\n baz\n"
    code = _extract_code_from_patch(patch)
    assert "bar" in code
    assert "foo" not in code


def test_analyze_patch_returns_json_on_empty_diff() -> None:
    import json
    result = json.loads(analyze_patch("--- a/f.py\n+++ b/f.py\n"))
    assert "static" in result
    assert result["static"] == []


def test_analyze_patch_returns_json_error_when_bandit_absent(monkeypatch) -> None:
    import json

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("bandit not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = json.loads(analyze_patch("+x = eval('1+1')\n"))
    assert "static" in result
    assert result["static"][0].get("error") == "bandit not installed"


# ---------------------------------------------------------------------------
# Evidence validator
# ---------------------------------------------------------------------------

def test_cs_evidence_validator_accepts_bandit_tool_reference() -> None:
    validate = make_cs_evidence_validator()
    assert validate("Bandit flagged eval() call in the proposed patch", 0, {}) is True


def test_cs_evidence_validator_accepts_static_keyword() -> None:
    validate = make_cs_evidence_validator()
    assert validate("static analysis shows SQL injection risk", 0, {}) is True


def test_cs_evidence_validator_accepts_quote_match() -> None:
    validate = make_cs_evidence_validator()
    seen = {1: ["this patch introduces an eval call that is suspicious"]}
    assert validate('QUOTE: "patch introduces an eval call that is suspicious"', 1, seen) is True


def test_cs_evidence_validator_rejects_empty_evidence() -> None:
    validate = make_cs_evidence_validator()
    assert validate("", 0, {}) is False


def test_cs_evidence_validator_rejects_unmatched_quote() -> None:
    validate = make_cs_evidence_validator()
    seen = {1: ["completely different text"]}
    assert validate('QUOTE: "some quote that does not appear in messages"', 1, seen) is False


# ---------------------------------------------------------------------------
# Deferred functional correctness
# ---------------------------------------------------------------------------

def test_deferred_correctness_capability_causes_none_in_result() -> None:
    class FakeCaps:
        deferred_functional_correctness = True
        language_only_permissions = False

    class FakeDomain:
        capabilities = FakeCaps()

    correctness_called = []

    class FakeEvaluator:
        def compute_functional_correctness(self):
            correctness_called.append(True)
            return 1.0

    domain = FakeDomain()
    evaluator = FakeEvaluator()
    fc = (
        None
        if domain.capabilities.deferred_functional_correctness
        else evaluator.compute_functional_correctness()
    )

    assert fc is None
    assert correctness_called == []
