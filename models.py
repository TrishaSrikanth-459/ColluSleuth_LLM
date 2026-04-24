"""
Core data models for the LLM-MAS collaborative knowledge-QA study.
"""
from __future__ import annotations

import time
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, field_validator


class Role(str, Enum):
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    REPORTER = "reporter"


class ChannelAccess(str, Enum):
    NONE = "none"


class AttackType(str, Enum):
    NONE = "none"
    LINGUISTIC_COLLUSION = "linguistic_collusion"
    MULTIMODAL_HIDING = "multimodal_hiding"


class CoordinationStructure(str, Enum):
    EGALITARIAN = "egalitarian"
    HIERARCHICAL = "hierarchical"


class KnowledgeLevel(str, Enum):
    UNAWARE = "unaware"
    AWARE_OF_PRESENCE = "aware_of_presence"
    FULLY_PREPARED = "fully_prepared"


class PermissionLevel(str, Enum):
    FULL_ACCESS = "full_access"
    RESTRICTED = "restricted"
    QUARANTINE = "quarantine"
    REMOVED = "removed"


class RecommendationAction(str, Enum):
    DECREASE = "decrease_credibility"
    QUARANTINE = "quarantine"
    REMOVE = "remove"


class Agent(BaseModel):
    id: int
    role: Role
    channel_access: ChannelAccess
    is_malicious: bool = False
    hidden_prompt: Optional[str] = None
    knowledge_level: Optional[KnowledgeLevel] = None

    @field_validator("role", mode="before")
    def validate_role(cls, value):
        if isinstance(value, str):
            return Role(value)
        return value

    @field_validator("channel_access", mode="before")
    def validate_channel(cls, value):
        if isinstance(value, str):
            return ChannelAccess(value)
        return value

    @field_validator("knowledge_level", mode="before")
    def validate_knowledge(cls, value):
        if isinstance(value, str):
            return KnowledgeLevel(value)
        return value


class Message(BaseModel):
    turn: int
    sender_id: int
    content: str
    is_private: bool = False
    recipient_id: Optional[int] = None
    timestamp: float = None

    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = time.time()
        super().__init__(**data)


class Action(BaseModel):
    turn: int
    agent_id: int
    action_type: str
    content: str
    timestamp: float = None

    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = time.time()
        super().__init__(**data)


class Recommendation(BaseModel):
    target_agent_id: int
    action: str
    magnitude: Optional[float] = None
    confidence: float
    detector_ids: List[int]
    evidence: str
    turn: int
    timestamp: float = None

    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = time.time()
        super().__init__(**data)


class PermissionChange(BaseModel):
    timestamp: float
    agent_id: int
    old_credibility: float
    new_credibility: float
    reason: str
    recommending_detectors: Optional[List[int]] = None
