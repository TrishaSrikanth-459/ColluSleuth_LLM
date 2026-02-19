"""
Enhanced JSONL logger with experiment metadata and experiment ID in every entry.
"""
import json
import os
from datetime import datetime
from models import Message, Action

class Logger:
    def __init__(self, experiment_id: str, metadata: dict, log_dir: str = "logs"):
        self.experiment_id = experiment_id
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # Write metadata file
        metadata_path = os.path.join(log_dir, f"{experiment_id}_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Open message and action logs (JSONL format)
        self.message_file = open(os.path.join(log_dir, f"{experiment_id}_messages.jsonl"), "a")
        self.action_file = open(os.path.join(log_dir, f"{experiment_id}_actions.jsonl"), "a")

    def log_message(self, message: Message):
        """Log a message with experiment ID."""
        entry = {
            "experiment_id": self.experiment_id,
            "turn": message.turn,
            "sender_id": message.sender_id,
            "content": message.content,
            "is_private": message.is_private,
            "recipient_id": message.recipient_id,
            "timestamp": message.timestamp
        }
        self.message_file.write(json.dumps(entry) + "\n")
        self.message_file.flush()

    def log_action(self, action: Action):
        """Log an action with experiment ID."""
        entry = {
            "experiment_id": self.experiment_id,
            "turn": action.turn,
            "agent_id": action.agent_id,
            "action_type": action.action_type,
            "content": action.content,
            "timestamp": action.timestamp
        }
        self.action_file.write(json.dumps(entry) + "\n")
        self.action_file.flush()

    def close(self):
        self.message_file.close()
        self.action_file.close()