"""
Simulation engine with turn management, private messaging, and logging.
"""
import asyncio
from typing import List, Dict, Any
from models import Message, Action
from agent import WorkerAgent
from logger import Logger

class Simulation:
    def __init__(self, agents: List[WorkerAgent], total_turns: int = 10,
                 experiment_id: str = "exp", metadata: Dict[str, Any] = None):
        self.agents = {a.id: a for a in agents}
        self.total_turns = total_turns
        self.turn = 0
        self.message_log: List[Message] = []
        self.action_log: List[Action] = []
        self.metadata = metadata or {}
        self.experiment_id = experiment_id
        self.logger = Logger(experiment_id, metadata)

    async def send_private_message(self, sender_id: int, recipient_id: int, content: str):
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
        for agent_id in sorted(self.agents.keys()):
            agent = self.agents[agent_id]
            public_msgs = [m for m in self.message_log if not m.is_private]
            private_msgs = [m for m in self.message_log if m.is_private and m.recipient_id == agent_id]

            response = await agent.generate_response(self.turn, public_msgs, private_msgs)

            msg = Message(
                turn=self.turn,
                sender_id=agent_id,
                content=response,
                is_private=False,
                recipient_id=None
            )
            self.message_log.append(msg)
            self.logger.log_message(msg)

            action = agent.take_action(self.turn, response)
            if action:
                self.action_log.append(action)
                self.logger.log_action(action)

    async def run(self):
        while self.turn < self.total_turns:
            await self.run_turn()
            if self.turn == 3:
                for agent in self.agents.values():
                    if agent.is_malicious:
                        agent.activate()
        self.logger.close()
        return self.message_log, self.action_log