"""
Role assignment for worker agents based on task domain.
Only knowledge_qa and code_synthesis are used.
"""
from __future__ import annotations

import random
from typing import List, Optional

from models import Agent, Role, ChannelAccess


DOMAIN_ROLES = {
    "knowledge_qa": [Role.RESEARCHER, Role.ANALYST, Role.REPORTER],
    "code_synthesis": [Role.ENGINEER, Role.REVIEWER, Role.MANAGER],
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
    if domain not in DOMAIN_ROLES:
        raise ValueError(f"Unknown domain: {domain}. Choose from {list(DOMAIN_ROLES.keys())}")
    if num_workers <= 0:
        raise ValueError("num_workers must be positive")

    base_roles = DOMAIN_ROLES[domain]
    role_pool = (base_roles * ((num_workers // len(base_roles)) + 1))[:num_workers]

    # Guarantee at least one role that can finish the task
    if domain == "code_synthesis" and Role.ENGINEER not in role_pool:
        role_pool[0] = Role.ENGINEER
    if domain == "knowledge_qa" and Role.REPORTER not in role_pool:
        role_pool[0] = Role.REPORTER

    (rng or random).shuffle(role_pool)

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