"""
SQLite‑based logger for experiments. Each experiment gets its own database file.
Tables: metadata (single row), messages, actions.
"""
import sqlite3
import json
import os
from datetime import datetime
from models import Message, Action

class Logger:
    def __init__(self, experiment_id: str, metadata: dict, log_dir: str = "logs"):
        self.experiment_id = experiment_id
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # Database path
        self.db_path = os.path.join(log_dir, f"{experiment_id}.db")
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._store_metadata(metadata)

    def _create_tables(self):
        """Create the necessary tables if they don't exist."""
        # Metadata table (single row)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Messages table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn INTEGER,
                sender_id INTEGER,
                content TEXT,
                is_private INTEGER,
                recipient_id INTEGER,
                timestamp REAL
            )
        """)

        # Actions table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn INTEGER,
                agent_id INTEGER,
                action_type TEXT,
                content TEXT,
                timestamp REAL
            )
        """)
        self.conn.commit()

    def _store_metadata(self, metadata: dict):
        """Store experiment‑level metadata as key‑value pairs."""
        for key, value in metadata.items():
            # Convert non‑string values to JSON strings
            if not isinstance(value, str):
                value = json.dumps(value)
            self.cursor.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (key, value)
            )
        self.conn.commit()

    def log_message(self, message: Message):
        """Insert a message into the messages table."""
        self.cursor.execute("""
            INSERT INTO messages (turn, sender_id, content, is_private, recipient_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            message.turn,
            message.sender_id,
            message.content,
            1 if message.is_private else 0,
            message.recipient_id,
            message.timestamp
        ))
        self.conn.commit()

    def log_action(self, action: Action):
        """Insert an action into the actions table."""
        self.cursor.execute("""
            INSERT INTO actions (turn, agent_id, action_type, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            action.turn,
            action.agent_id,
            action.action_type,
            action.content,
            action.timestamp
        ))
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.conn.close()