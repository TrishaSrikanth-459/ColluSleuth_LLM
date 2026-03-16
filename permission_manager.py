"""
Non-LLM trusted component that maintains credibility scores and enforces permission levels.
"""
from typing import Dict, List, Set
from models import Recommendation, PermissionLevel
import config

class PermissionManager:
    def __init__(self):
        self.credibility: Dict[int, float] = {}
        self.clean_turns: Dict[int, int] = {}
        self.agents_with_decrease_this_turn: Set[int] = set()

    def initialize_agents(self, agent_ids: List[int]):
        for aid in agent_ids:
            self.credibility[aid] = 1.0
            self.clean_turns[aid] = 0

    def process_recommendation(self, rec: Recommendation):
        target = rec.target_agent_id
        if target not in self.credibility:
            return

        if rec.action == "decrease_credibility":
            magnitude = rec.magnitude if rec.magnitude is not None else 0.1
            magnitude = max(0.0, min(0.3, magnitude))
            self.credibility[target] = max(0.0, self.credibility[target] - magnitude)
            self.agents_with_decrease_this_turn.add(target)

        elif rec.action == "quarantine":
            if self.credibility[target] > config.CREDIBILITY_QUARANTINE + 0.1:  # 0.3
                self.credibility[target] = config.CREDIBILITY_QUARANTINE + 0.1

        elif rec.action == "remove":
            self.credibility[target] = 0.0

    def end_turn(self):
        for aid in self.credibility.keys():
            if aid in self.agents_with_decrease_this_turn:
                self.clean_turns[aid] = 0
            else:
                self.clean_turns[aid] += 1
                if self.clean_turns[aid] >= config.CLEAN_TURNS_FOR_RECOVERY:
                    self.credibility[aid] = min(1.0, self.credibility[aid] + config.RECOVERY_INCREMENT)
                    self.clean_turns[aid] = 0
        self.agents_with_decrease_this_turn.clear()

    def get_permission_level(self, agent_id: int, is_language_only: bool = False) -> str:
        c = self.credibility.get(agent_id, 1.0)
        if c >= config.CREDIBILITY_FULL:
            return "full_access"
        elif c >= config.CREDIBILITY_RESTRICTED:
            return "restricted" if not is_language_only else "quarantine"  # skip restricted for language tasks
        elif c >= config.CREDIBILITY_QUARANTINE:
            return "quarantine"
        else:
            return "removed"
