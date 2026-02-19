"""
Role assignment for worker agents based on task domain.
"""
import random
from models import Agent, Role, ChannelAccess

# Domain‑specific role sets (each appears twice to reach six workers)
DOMAIN_ROLES = {
    "knowledge_qa": [Role.RESEARCHER, Role.ANALYST, Role.REPORTER],
    "math_reasoning": [Role.CALCULATOR, Role.CHECKER, Role.INTEGRATOR],
    "code_synthesis": [Role.ENGINEER, Role.REVIEWER, Role.MANAGER],
    "web_interaction": [Role.PLANNER, Role.OPERATOR, Role.VALIDATOR],
}

# Channel access mapping per role
ROLE_CHANNEL_ACCESS = {
    Role.RESEARCHER: ChannelAccess.NONE,
    Role.ANALYST: ChannelAccess.NONE,
    Role.REPORTER: ChannelAccess.NONE,
    Role.CALCULATOR: ChannelAccess.NONE,
    Role.CHECKER: ChannelAccess.NONE,
    Role.INTEGRATOR: ChannelAccess.NONE,
    Role.ENGINEER: ChannelAccess.CODE,
    Role.REVIEWER: ChannelAccess.NONE,
    Role.MANAGER: ChannelAccess.NONE,
    Role.PLANNER: ChannelAccess.NONE,
    Role.OPERATOR: ChannelAccess.HTTP,
    Role.VALIDATOR: ChannelAccess.NONE,
}


def assign_roles(domain: str, num_workers: int = 6) -> list[Agent]:
    """
    Randomly assign roles to workers for a given domain.
    Returns a list of Agent objects.
    """
    if domain not in DOMAIN_ROLES:
        raise ValueError(f"Unknown domain: {domain}. Choose from {list(DOMAIN_ROLES.keys())}")

    # Each role appears twice to reach six workers
    role_pool = DOMAIN_ROLES[domain] * 2
    random.shuffle(role_pool)

    agents = []
    for i, role in enumerate(role_pool):
        agent = Agent(
            id=i,
            role=role,
            channel_access=ROLE_CHANNEL_ACCESS[role],
            is_malicious=False,  # will be set later by experiment harness
        )
        agents.append(agent)
    return agents


def mark_malicious(agents: list[Agent], m: int) -> list[Agent]:
    """
    Randomly select m agents to be malicious.
    Modifies the agents in place and returns them.
    """
    if m < 0 or m > len(agents):
        raise ValueError(f"m must be between 0 and {len(agents)}")
    indices = random.sample(range(len(agents)), m)
    for idx in indices:
        agents[idx].is_malicious = True
    return agents