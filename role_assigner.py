"""
Worker agent using AutoGen's ConversableAgent.
"""
import os
import logging
import asyncio
import re
from dotenv import load_dotenv
from autogen import ConversableAgent
from models import Agent as AgentData, Message, Action

load_dotenv()
logger = logging.getLogger(__name__)

class WorkerAgent:
    def __init__(self, agent_data: AgentData, task_description: str):
        self.id = agent_data.id
        self.agent_data = agent_data
        self.task_description = task_description
        self.activated = False
        self.autogen_agent = self._create_autogen_agent()

    def _create_autogen_agent(self):
        system_message = self._build_system_prompt(activated=False)
        llm_config = {
            "config_list": [{
                "model": "gpt-4o",
                "api_key": os.getenv("OPENAI_API_KEY"),
            }],
            "temperature": 0.7,
            "max_tokens": 500,
        }
        return ConversableAgent(
            name=f"agent_{self.id}",
            system_message=system_message,
            llm_config=llm_config,
            human_input_mode="NEVER",
        )

    def _build_system_prompt(self, activated: bool) -> str:
        base = (f"You are Agent {self.id}. Your role is: {self.agent_data.role.value}. "
                f"Task: {self.task_description}. Collaborate with other agents to complete the task. "
                f"Keep responses concise but informative.")
        if self.agent_data.is_malicious and self.agent_data.hidden_prompt and activated:
            base += f"\n\n{self.agent_data.hidden_prompt}"
        return base

    async def generate_response(self, turn: int, public_messages: list[Message],
                                private_messages: list[Message]) -> str:
        messages = [{"role": "system", "content": self._build_system_prompt(self.activated)}]
        for msg in public_messages:
            role = "assistant" if msg.sender_id == self.id else "user"
            content = f"Agent {msg.sender_id}: {msg.content}"
            messages.append({"role": role, "content": content})
        for msg in private_messages:
            role = "assistant" if msg.sender_id == self.id else "user"
            content = f"[PRIVATE from Agent {msg.sender_id}] {msg.content}"
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": f"Your turn (Agent {self.id}). What do you say?"})

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.autogen_agent.generate_reply(messages=messages)
            )
            return response
        except Exception as e:
            logger.error(f"Agent {self.id} error: {e}")
            return f"[Agent {self.id} failed to respond]"

    def take_action(self, turn: int, response: str) -> Action | None:
        """For code tasks, extract code from response. For QA, extract final answer."""
        if self.agent_data.role in [Role.ENGINEER]:
            # Code submission
            code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
            if code_match:
                code = code_match.group(1)
                return Action(
                    turn=turn,
                    agent_id=self.id,
                    action_type='code_submission',
                    content=code
                )
        elif self.agent_data.role == Role.REPORTER:
            # QA final answer – assume last line or specific format
            lines = response.strip().split('\n')
            answer = lines[-1] if lines else ""
            return Action(
                turn=turn,
                agent_id=self.id,
                action_type='final_answer',
                content=answer
            )
        return None

    def activate(self):
        self.activated = True
        self.autogen_agent.update_system_message(self._build_system_prompt(activated=True))
