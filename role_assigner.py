"""
Role assignment for the collaborative knowledge-QA worker pool.
"""
from __future__ import annotations

import random
from typing import List, Optional

from models import Agent, ChannelAccess, Role


QA_ROLE_PLAN = [
    Role.REPORTER,
    Role.ANALYST,
    Role.RESEARCHER,
    Role.ANALYST,
    Role.RESEARCHER,
    Role.ANALYST,
]


def assign_roles(domain: str, num_workers: int = 6, rng: Optional[random.Random] = None) -> List[Agent]:
    if domain != "knowledge_qa":
        raise ValueError("This codebase is QA-only. Use domain='knowledge_qa'.")
    if num_workers <= 0:
        raise ValueError("num_workers must be positive")

    role_pool = list(QA_ROLE_PLAN)
    while len(role_pool) < num_workers:
        role_pool.append(Role.ANALYST)
    role_pool = role_pool[:num_workers]
    (rng or random).shuffle(role_pool)

    finishers = {role for role in role_pool if role == Role.REPORTER}
    if finishers != {Role.REPORTER}:
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


def mark_malicious(agents: List[Agent], m: int, rng: Optional[random.Random] = None) -> List[Agent]:
    if m < 0 or m > len(agents):
        raise ValueError(f"m must be between 0 and {len(agents)}")
    indices = (rng or random).sample(range(len(agents)), m)
    for idx in indices:
        agents[idx].is_malicious = True
    return agents
