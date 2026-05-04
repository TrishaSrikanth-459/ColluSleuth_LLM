from covert_collusive_hotpot.core.models import AttackType, Role
from covert_collusive_hotpot.experiments.prompt_injection import inject_hidden_prompts
from covert_collusive_hotpot.experiments.role_assignment import assign_roles, mark_malicious
import random


def _make_agents(m: int = 1) -> list:
    agents = assign_roles("code_synthesis", num_workers=6, rng=random.Random(0))
    return mark_malicious(agents, m, rng=random.Random(0))


def test_inject_hidden_prompts_uses_custom_adaptations():
    agents = _make_agents(m=1)
    custom = {
        AttackType.SUBOPTIMAL_FIXATION: "CUSTOM_CS_ADAPTATION",
        AttackType.REFRAMING_MISALIGNMENT: "x",
        AttackType.FAKE_INJECTION: "x",
        AttackType.EXECUTION_DELAY: "x",
    }
    result = inject_hidden_prompts(
        agents,
        m=1,
        attack_type=AttackType.SUBOPTIMAL_FIXATION,
        knowledge_level=None,
        detector_ids=[],
        detector_visible=False,
        tool_knowledge=False,
        interrogation_turns=None,
        adaptations=custom,
    )
    malicious = [a for a in result if a.is_malicious]
    assert len(malicious) == 1
    assert "CUSTOM_CS_ADAPTATION" in malicious[0].hidden_prompt


def test_inject_hidden_prompts_default_adaptations_unchanged():
    agents = _make_agents(m=1)
    result = inject_hidden_prompts(
        agents,
        m=1,
        attack_type=AttackType.SUBOPTIMAL_FIXATION,
        knowledge_level=None,
        detector_ids=[],
        detector_visible=False,
        tool_knowledge=False,
        interrogation_turns=None,
    )
    malicious = [a for a in result if a.is_malicious]
    assert "Knowledge-QA" in malicious[0].hidden_prompt
