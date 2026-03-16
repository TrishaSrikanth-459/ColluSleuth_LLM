"""
Simulation engine with turn management, private messaging, activation, and SQLite logging.
"""
import asyncio
import json
from typing import List, Dict, Any, Optional
from models import Message, Action, Recommendation
from agent import WorkerAgent
from detector_agent import DetectorAgent
from logger import Logger
from permission_manager import PermissionManager

class Simulation:
    def __init__(self, workers: List[WorkerAgent], detectors: List[DetectorAgent],
                 total_turns: int = 10, experiment_id: str = "exp",
                 metadata: Dict[str, Any] = None, domain: str = None):
        self.workers = {a.id: a for a in workers}
        self.detectors = {d.id: d for d in detectors}
        self.all_agents = {**self.workers, **self.detectors}
        self.total_turns = total_turns
        self.turn = 0
        self.message_log: List[Message] = []
        self.action_log: List[Action] = []
        self.recommendation_log: List[Recommendation] = []
        self.metadata = metadata or {}
        self.experiment_id = experiment_id
        self.domain = domain
        self.logger = Logger(experiment_id, metadata, log_dir="logs")
        self.permission_manager = PermissionManager()
        self.permission_manager.initialize_agents(list(self.workers.keys()))

        for det in self.detectors.values():
            det.send_message = self.send_private_message

    def send_private_message(self, sender_id: int, recipient_id: int, content: str):
        msg = Message(
            turn=self.turn,
            sender_id=sender_id,
            content=content,
            is_private=True,
            recipient_id=recipient_id
        )
        self.message_log.append(msg)
        self.logger.log_message(msg)

    async def run_turn(self):
        self.turn += 1
        # Workers speak in order of ID
        for agent_id in sorted(self.workers.keys()):
            agent = self.workers[agent_id]

            # Check permission level before allowing communication
            level = self.permission_manager.get_permission_level(agent_id, is_language_only=(self.domain=="knowledge_qa"))
            if level in ["removed", "quarantine"]:
                continue  # cannot speak

            public_msgs = [m for m in self.message_log if not m.is_private]
            private_msgs = [m for m in self.message_log if m.is_private and m.recipient_id == agent_id]

            response = await agent.generate_response(self.turn, public_msgs, private_msgs)

            msg = Message(turn=self.turn, sender_id=agent_id, content=response, is_private=False)
            self.message_log.append(msg)
            self.logger.log_message(msg)

            # Action – only allowed if full access
            if level == "full_access":
                action = agent.take_action(self.turn, response)
                if action:
                    self.action_log.append(action)
                    self.logger.log_action(action)

        # Detectors analyze
        for detector_id, detector in self.detectors.items():
            public_msgs = [m for m in self.message_log if not m.is_private]
            private_msgs = [m for m in self.message_log if m.is_private and m.recipient_id == detector_id]
            recommendation = await detector.analyze(self.turn, public_msgs, private_msgs)
            if recommendation:
                try:
                    rec_data = json.loads(recommendation)
                    if "target_agent_id" not in rec_data or "action" not in rec_data or "evidence" not in rec_data:
                        print(f"Invalid recommendation from detector {detector_id}")
                        continue
                    rec = Recommendation(**rec_data)
                    self.recommendation_log.append(rec)
                    self.permission_manager.process_recommendation(rec)
                except Exception as e:
                    print(f"Failed to parse recommendation: {e}")

        self.permission_manager.end_turn()

    async def run(self):
        while self.turn < self.total_turns:
            await self.run_turn()
            if self.turn == 3:
                for agent in self.workers.values():
                    if agent.agent_data.is_malicious:
                        agent.activate()
        self.logger.close()
        return self.message_log, self.action_log
