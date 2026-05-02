import random

import pytest

from covert_collusive_hotpot.core.models import Role
from covert_collusive_hotpot.experiments.role_assignment import (
    assign_roles,
    malicious_count_from_label,
    mark_malicious,
)


def test_assign_roles_creates_exactly_one_reporter():
    agents = assign_roles("knowledge_qa", num_workers=6, rng=random.Random(0))

    reporter_count = sum(agent.role == Role.REPORTER for agent in agents)

    assert len(agents) == 6
    assert reporter_count == 1


def test_assign_roles_rejects_wrong_domain():
    with pytest.raises(ValueError, match="QA-only"):
        assign_roles("finance", num_workers=6, rng=random.Random(0))


def test_malicious_count_from_label_all_returns_total_agents():
    assert malicious_count_from_label("all", 6) == 6


def test_malicious_count_from_label_invalid_count_raises_value_error():
    with pytest.raises(ValueError, match="between 0 and 6"):
        malicious_count_from_label(7, 6)


def test_mark_malicious_anchor_reporter_marks_reporter_malicious():
    agents = assign_roles("knowledge_qa", num_workers=6, rng=random.Random(0))

    marked_agents = mark_malicious(
        agents,
        1,
        rng=random.Random(0),
        anchor_reporter=True,
    )

    reporters = [agent for agent in marked_agents if agent.role == Role.REPORTER]
    malicious_count = sum(agent.is_malicious for agent in marked_agents)

    assert len(reporters) == 1
    assert malicious_count == 1
    assert reporters[0].is_malicious is True
