"""
SQLite-based logger for experiments. Each experiment gets its own database file.
Tables: metadata, messages, actions, recommendations, permission_changes.
"""
import sqlite3
import json
import os
from models import Message, Action, Recommendation, PermissionChange

class Logger:
    def __init__(self, experiment_id: str, metadata: dict, log_dir: str = "logs"):
        self.experiment_id = experiment_id
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.db_path = os.path.join(log_dir, f"{experiment_id}.db")
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._store_metadata(metadata)

    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
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
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_agent_id INTEGER,
                action TEXT,
                magnitude REAL,
                confidence REAL,
                detector_ids TEXT,
                evidence TEXT,
                timestamp REAL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER,
                old_credibility REAL,
                new_credibility REAL,
                reason TEXT,
                recommending_detectors TEXT,
                timestamp REAL
            )
        """)
        self.conn.commit()

    def _store_metadata(self, metadata: dict):
        for key, value in metadata.items():
            if not isinstance(value, str):
                value = json.dumps(value)
            self.cursor.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (key, value)
            )
        self.conn.commit()

    def log_message(self, message: Message):
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

    def log_recommendation(self, rec: Recommendation):
        self.cursor.execute("""
            INSERT INTO recommendations (target_agent_id, action, magnitude, confidence, detector_ids, evidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            rec.target_agent_id,
            rec.action,
            rec.magnitude,
            rec.confidence,
            json.dumps(rec.detector_ids),
            rec.evidence,
            rec.timestamp
        ))
        self.conn.commit()

    def log_permission_change(self, change: PermissionChange):
        self.cursor.execute("""
            INSERT INTO permission_changes (agent_id, old_credibility, new_credibility, reason, recommending_detectors, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            change.agent_id,
            change.old_credibility,
            change.new_credibility,
            change.reason,
            json.dumps(change.recommending_detectors) if change.recommending_detectors else None,
            change.timestamp
        ))
        self.conn.commit()

    def close(self):
        self.conn.close()
