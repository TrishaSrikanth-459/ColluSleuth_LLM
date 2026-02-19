"""
Simulation engine for multi‑agent collaboration.
"""
import asyncio
from typing import List
from models import Message, Action
from agent import WorkerAgent

class Simulation:
    def __init__(self, agents: List[WorkerAgent], total_turns: int = 10):
        self.agents = {a.id: a for a in agents}
        self.total_turns = total_turns
        self.turn = 0
        self.message_log: List[Message] = []
        self.action_log: List[Action] = []

    async def run_turn(self):
        """Execute one turn: each agent speaks in order of ID."""
        self.turn += 1
        for agent_id in sorted(self.agents.keys()):
            agent = self.agents[agent_id]
            # Only public messages are visible to all
            visible = [m for m in self.message_log if not m.is_private]
            response = await agent.generate_response(self.turn, visible)
            # Record public message
            msg = Message(turn=self.turn, sender_id=agent_id, content=response, is_private=False)
            self.message_log.append(msg)
            # Check for actions (Phase 1 none)
            action = agent.take_action(self.turn, response)
            if action:
                self.action_log.append(action)

    async def run(self):
        """Run the simulation for total_turns."""
        while self.turn < self.total_turns:
            await self.run_turn()
        return self.message_log, self.action_log