"""
Role assignment for the decentralized Knowledge-QA worker pool.
"""
from __future__ import annotations

import random
from typing import List, Optional

from covert_collusive_hotpot.core import config
from covert_collusive_hotpot.core.models import Agent, ChannelAccess, Role


QA_ROLE_PLAN = [
    Role.REPORTER,
    Role.ANALYST,
    Role.RESEARCHER,
    Role.ANALYST,
    Role.RESEARCHER,
    Role.ANALYST,
]


def assign_roles(domain: str, num_workers: int = None, rng: Optional[random.Random] = None) -> List[Agent]:
    if num_workers is None:
        num_workers = config.NUM_WORKERS
    if num_workers <= 0:
        raise ValueError("num_workers must be positive")

    role_pool = list(QA_ROLE_PLAN)
    while len(role_pool) < num_workers:
        role_pool.append(Role.ANALYST)
    role_pool = role_pool[:num_workers]
    (rng or random).shuffle(role_pool)

    if role_pool.count(Role.REPORTER) != 1:
        raise RuntimeError("Knowledge-QA assignment must contain exactly one reporter")

    agents: List[Agent] = []
    for i, role in enumerate(role_pool):
        agents.append(Agent(
            id=i,
            role=role,
            channel_access=ChannelAccess.NONE,
            is_malicious=False,
        ))
    return agents


def malicious_count_from_label(m: int | str, total_agents: int) -> int:
    if isinstance(m, str) and m.strip().lower() == "all":
        return total_agents
    count = int(m)
    if count < 0 or count > total_agents:
        raise ValueError(f"m must be between 0 and {total_agents}, or 'all'")
    return count


def mark_malicious(
    agents: List[Agent],
    m: int | str,
    rng: Optional[random.Random] = None,
    anchor_reporter: Optional[bool] = None,
) -> List[Agent]:
    count = malicious_count_from_label(m, len(agents))
    for agent in agents:
        agent.is_malicious = False
    if count == 0:
        return agents
    if count == len(agents):
        for agent in agents:
            agent.is_malicious = True
        return agents

    chooser = rng or random
    selected: set[int] = set()
    if anchor_reporter if anchor_reporter is not None else config.ANCHOR_MALICIOUS_REPORTER:
        reporter_indices = [idx for idx, agent in enumerate(agents) if agent.role == Role.REPORTER]
        if reporter_indices:
            selected.add(reporter_indices[0])

    remaining = [idx for idx in range(len(agents)) if idx not in selected]
    selected.update(chooser.sample(remaining, count - len(selected)))

    indices = sorted(selected)
    for idx in indices:
        agents[idx].is_malicious = True
    return agents
