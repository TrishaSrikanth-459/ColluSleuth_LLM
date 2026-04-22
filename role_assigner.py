"""
Role assignment for worker agents based on task domain.

We keep the worker pool size fixed, but ensure exactly one output-capable role per
experiment so evaluation maps cleanly to one canonical final artifact.
"""
from __future__ import annotations

import random
from typing import List, Optional

from models import Agent, Role, ChannelAccess


DOMAIN_ROLE_PLANS = {
    "knowledge_qa": [
        Role.REPORTER,
        Role.ANALYST,
        Role.RESEARCHER,
        Role.ANALYST,
        Role.RESEARCHER,
        Role.ANALYST,
    ],
    "code_synthesis": [
        Role.ENGINEER,
        Role.REVIEWER,
        Role.MANAGER,
        Role.REVIEWER,
        Role.MANAGER,
        Role.REVIEWER,
    ],
}

SUPPORT_ROLES = {
    "knowledge_qa": [Role.ANALYST, Role.RESEARCHER],
    "code_synthesis": [Role.REVIEWER, Role.MANAGER],
}

ROLE_CHANNEL_ACCESS = {
    Role.RESEARCHER: ChannelAccess.NONE,
    Role.ANALYST: ChannelAccess.NONE,
    Role.REPORTER: ChannelAccess.NONE,
    Role.ENGINEER: ChannelAccess.CODE,
    Role.REVIEWER: ChannelAccess.NONE,
    Role.MANAGER: ChannelAccess.NONE,
}


def assign_roles(domain: str, num_workers: int = 6, rng: Optional[random.Random] = None) -> List[Agent]:
    if domain not in DOMAIN_ROLE_PLANS:
        raise ValueError(f"Unknown domain: {domain}. Choose from {list(DOMAIN_ROLE_PLANS.keys())}")
    if num_workers <= 0:
        raise ValueError("num_workers must be positive")

    role_pool = list(DOMAIN_ROLE_PLANS[domain])
    support_roles = SUPPORT_ROLES[domain]

    support_idx = 0
    while len(role_pool) < num_workers:
        role_pool.append(support_roles[support_idx % len(support_roles)])
        support_idx += 1

    role_pool = role_pool[:num_workers]
    (rng or random).shuffle(role_pool)

    finishers = {
        role for role in role_pool
        if role in {Role.REPORTER, Role.ENGINEER}
    }
    if domain == "knowledge_qa" and finishers != {Role.REPORTER}:
        raise RuntimeError("Knowledge QA role assignment must contain exactly one reporter")
    if domain == "code_synthesis" and finishers != {Role.ENGINEER}:
        raise RuntimeError("Code synthesis role assignment must contain exactly one engineer")

    agents: List[Agent] = []
    for i, role in enumerate(role_pool):
        agents.append(Agent(
            id=i,
            role=role,
            channel_access=ROLE_CHANNEL_ACCESS[role],
            is_malicious=False,
        ))

    return agents


def mark_malicious(agents: List[Agent], m: int, rng: Optional[random.Random] = None) -> List[Agent]:
    if m < 0 or m > len(agents):
        raise ValueError(f"m must be between 0 and {len(agents)}")

    indices = (rng or random).sample(range(len(agents)), m)
    for idx in indices:
        agents[idx].is_malicious = True

    return agents
