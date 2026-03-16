"""
Core data models for the LLM-MAS collusion detection system.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
import time

class Role(str, Enum):
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    REPORTER = "reporter"
    CALCULATOR = "calculator"
    CHECKER = "checker"
    INTEGRATOR = "integrator"
    ENGINEER = "engineer"
    REVIEWER = "reviewer"
    MANAGER = "manager"
    PLANNER = "planner"
    OPERATOR = "operator"
    VALIDATOR = "validator"

class ChannelAccess(str, Enum):
    NONE = "none"
    CODE = "code"
    HTTP = "http"

class AttackType(str, Enum):
    NONE = "none"
    LINGUISTIC_COLLUSION = "linguistic_collusion"
    MULTIMODAL_HIDING = "multimodal_hiding"

class CoordinationStructure(str, Enum):
    EGALITARIAN = "egalitarian"
    HIERARCHICAL = "hierarchical"

class KnowledgeLevel(str, Enum):
    """What attackers know about the defense system."""
    UNAWARE = "unaware"
    AWARE_OF_PRESENCE = "aware_of_presence"
    FULLY_PREPARED = "fully_prepared"

class PermissionLevel(str, Enum):
    FULL_ACCESS = "full_access"
    RESTRICTED = "restricted"
    QUARANTINE = "quarantine"
    REMOVED = "removed"

class Agent(BaseModel):
    id: int
    role: Role
    channel_access: ChannelAccess
    is_malicious: bool = False
    hidden_prompt: Optional[str] = None
    knowledge_level: Optional[KnowledgeLevel] = None  # for attackers

    class Config:
        use_enum_values = True

class Message(BaseModel):
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
    target_agent_id: int
    action: str                     # 'decrease_credibility', 'quarantine', 'remove'
    magnitude: Optional[float] = None
    confidence: float
    detector_ids: List[int]
    evidence: str                    # New: must cite specific evidence
    timestamp: float = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = time.time()
        super().__init__(**data)

class PermissionChange(BaseModel):
    timestamp: float
    agent_id: int
    old_credibility: float
    new_credibility: float
    reason: str
    recommending_detectors: Optional[List[int]] = None
