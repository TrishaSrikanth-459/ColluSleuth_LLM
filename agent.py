"""
Worker agent with robust OpenAI API handling (v1.x), including retries, token logging, and cost tracking.
Supports mock client for testing.
"""
import openai
import os
import logging
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from dotenv import load_dotenv
from models import Agent as AgentData, Message, Action

# Load environment variables
load_dotenv()

# Determine whether to use mock client
USE_MOCK = os.getenv("USE_MOCK_OPENAI", "0").lower() in ("1", "true", "yes")

if USE_MOCK:
    from mock_openai import MockOpenAIClient
    client = MockOpenAIClient()
    logger = logging.getLogger(__name__)
    logger.info("Using MOCK OpenAI client")
else:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment (or set USE_MOCK_OPENAI=1 for testing)")
    client = openai.OpenAI(api_key=api_key, organization=os.getenv("OPENAI_ORG_ID"))
    logger = logging.getLogger(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkerAgent:
    # ... (rest of the class remains the same as before)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.RateLimitError,
            openai.InternalServerError,
        )) if not USE_MOCK else (),
        before_sleep=before_sleep_log(logger, logging.WARNING)  # type: ignore
    )
    async def _call_openai(self, messages):
        """
        Internal method that calls the OpenAI API (or mock) with retries.
        """
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
        )
        return response

    async def generate_response(self, turn: int, public_messages: list[Message],
                                private_messages: list[Message]) -> str:
        """
        Generate a response given public and private messages visible to this agent.
        Private messages are included with a [PRIVATE] marker.
        """
        messages = [{"role": "system", "content": self._build_system_prompt()}]

        # Add public conversation history
        for msg in public_messages:
            role = "assistant" if msg.sender_id == self.id else "user"
            content = f"Agent {msg.sender_id}: {msg.content}"
            messages.append({"role": role, "content": content})

        # Add private messages (only those addressed to this agent)
        for msg in private_messages:
            role = "assistant" if msg.sender_id == self.id else "user"
            content = f"[PRIVATE from Agent {msg.sender_id}] {msg.content}"
            messages.append({"role": role, "content": content})

        # Add a prompt for the current turn
        messages.append({"role": "user", "content": f"Your turn (Agent {self.id}). What do you say?"})

        try:
            # Call OpenAI with retries
            response = await self._call_openai(messages)

            # --- Token usage and cost logging ---
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens

            # GPT-4o pricing (as of Feb 2025 – update if needed)
            # Input: $5.00 / 1M tokens, Output: $15.00 / 1M tokens
            cost = (prompt_tokens * 5.00 + completion_tokens * 15.00) / 1_000_000

            logger.info(
                f"Agent {self.id} turn {turn} | "
                f"Prompt tokens: {prompt_tokens}, Completion: {completion_tokens}, "
                f"Total: {total_tokens}, Cost: ${cost:.6f}"
            )

            # Append token usage to a CSV file for later analysis
            with open("token_usage.csv", "a") as f:
                f.write(f"{turn},{self.id},{prompt_tokens},{completion_tokens},{total_tokens},{cost:.6f}\n")

            # Extract the response text
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Agent {self.id} failed after retries: {e}")
            return f"[Agent {self.id} failed to respond]"

    def take_action(self, turn: int, response: str) -> Action | None:
        """
        Parse an action from the response if any.
        (To be implemented later by Person B/C for actual attacks.)
        """
        return None

    def activate(self):
        """Mark the agent as activated after turn 3 (for logging/simulation use)."""
        self.activated = True