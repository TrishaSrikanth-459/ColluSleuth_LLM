"""
Simple JSONL logger for messages and actions.
"""
import json
import os

class Logger:
    def __init__(self, experiment_id: str, log_dir: str = "logs"):
        self.experiment_id = experiment_id
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.message_file = open(f"{log_dir}/{experiment_id}_messages.jsonl", "a")
        self.action_file = open(f"{log_dir}/{experiment_id}_actions.jsonl", "a")

    def log_message(self, message):
        self.message_file.write(json.dumps(message.dict()) + "\n")
        self.message_file.flush()

    def log_action(self, action):
        self.action_file.write(json.dumps(action.dict()) + "\n")
        self.action_file.flush()

    def close(self):
        self.message_file.close()
        self.action_file.close()