"""
Core data models for the LLM-MAS collusion detection system.
Based on the threat model specification.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
import time


class Role(str, Enum):
    """All possible worker roles across task domains."""
    # Knowledge QA
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    REPORTER = "reporter"
    # Math Reasoning
    CALCULATOR = "calculator"
    CHECKER = "checker"
    INTEGRATOR = "integrator"
    # Code Synthesis
    ENGINEER = "engineer"
    REVIEWER = "reviewer"
    MANAGER = "manager"
    # Web Application Interaction
    PLANNER = "planner"
    OPERATOR = "operator"
    VALIDATOR = "validator"


class ChannelAccess(str, Enum):
    """Non‑linguistic channels an agent may access."""
    NONE = "none"
    CODE = "code"
    HTTP = "http"


class AttackType(str, Enum):
    """Attack paradigms used in experiments."""
    NONE = "none"
    LINGUISTIC_COLLUSION = "linguistic_collusion"
    MULTIMODAL_HIDING = "multimodal_hiding"


class CoordinationStructure(str, Enum):
    """How agents (malicious or detectors) coordinate."""
    EGALITARIAN = "egalitarian"
    HIERARCHICAL = "hierarchical"


class PermissionLevel(str, Enum):
    """Worker permission levels for progressive isolation."""
    FULL_ACCESS = "full_access"
    RESTRICTED = "restricted"
    QUARANTINE = "quarantine"
    REMOVED = "removed"


class Agent(BaseModel):
    """Represents a worker agent."""
    id: int
    role: Role
    channel_access: ChannelAccess
    is_malicious: bool = False
    hidden_prompt: Optional[str] = None

    class Config:
        use_enum_values = True  # Serialize enums as strings


class Message(BaseModel):
    """A message exchanged between agents."""
    turn: int
    sender_id: int
    content: str
    is_private: bool = False
    recipient_id: Optional[int] = None
    timestamp: float = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = time.time()
        super().__init__(**data)


class Action(BaseModel):
    """An action taken by a worker (code, HTTP request, etc.)."""
    turn: int
    agent_id: int
    action_type: str      # e.g., 'code_submission', 'http_request'
    content: str          # full code or HTTP request details
    timestamp: float = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = time.time()
        super().__init__(**data)


class Recommendation(BaseModel):
    """
    Recommendation sent by a detector agent to the permission manager.
    Format: {target, action, magnitude?, confidence}
    """
    target_agent_id: int
    action: str                     # 'decrease_credibility', 'quarantine', 'remove'
    magnitude: Optional[float] = None   # 0.0‑0.3, required only for decrease
    confidence: float                # 0.0‑1.0
    detector_ids: List[int]          # IDs of detectors that agreed on this recommendation
    timestamp: float = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = time.time()
        super().__init__(**data)


class PermissionChange(BaseModel):
    """Record of a credibility/permission change (for logging)."""
    timestamp: float
    agent_id: int
    old_credibility: float
    new_credibility: float
    reason: str                      # e.g., "detector recommendation", "automatic recovery"
    recommending_detectors: Optional[List[int]] = None


# Convenience constants
ALL_ROLES = [role.value for role in Role]
ALL_CHANNEL_ACCESS = [ca.value for ca in ChannelAccess]