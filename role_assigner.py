"""
Role assignment for worker agents based on task domain.
Only knowledge_qa and code_synthesis are used.
"""
import random
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

def assign_roles(domain: str, num_workers: int = 6) -> list[Agent]:
    if domain not in DOMAIN_ROLES:
        raise ValueError(f"Unknown domain: {domain}. Choose from {list(DOMAIN_ROLES.keys())}")
    role_pool = DOMAIN_ROLES[domain] * 2
    random.shuffle(role_pool)
    agents = []
    for i, role in enumerate(role_pool):
        agent = Agent(
            id=i,
            role=role,
            channel_access=ROLE_CHANNEL_ACCESS[role],
            is_malicious=False,
        )
        agents.append(agent)
    return agents

def mark_malicious(agents: list[Agent], m: int) -> list[Agent]:
    if m < 0 or m > len(agents):
        raise ValueError(f"m must be between 0 and {len(agents)}")
    indices = random.sample(range(len(agents)), m)
    for idx in indices:
        agents[idx].is_malicious = True
    return agents
