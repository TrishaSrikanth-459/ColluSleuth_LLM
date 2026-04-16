"""
SQLite-based logger for experiments. Each experiment gets its own database file.
Tables: metadata, messages, actions, recommendations, permission_changes.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, Optional

from models import Message, Action, Recommendation, PermissionChange


class Logger:
    def __init__(self, experiment_id: str, metadata: dict, log_dir: str = "logs"):
        self.experiment_id = experiment_id
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.db_path = os.path.join(log_dir, f"{experiment_id}.db")

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # Performance + durability balance
        self.cursor.execute("PRAGMA journal_mode=WAL;")
        self.cursor.execute("PRAGMA synchronous=NORMAL;")
        self.cursor.execute("PRAGMA foreign_keys=ON;")

        self._create_tables()
        self._store_metadata(metadata)

    def _create_tables(self) -> None:
        print(f"Creating tables with schema version 3 (INCLUDING turn) for {self.experiment_id}")

        self.cursor.execute("DROP TABLE IF EXISTS metadata")
        self.cursor.execute("DROP TABLE IF EXISTS messages")
        self.cursor.execute("DROP TABLE IF EXISTS actions")
        self.cursor.execute("DROP TABLE IF EXISTS recommendations")
        self.cursor.execute("DROP TABLE IF EXISTS permission_changes")

        self.cursor.execute("""
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        self.cursor.execute("""
            CREATE TABLE messages (
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
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn INTEGER,
                agent_id INTEGER,
                action_type TEXT,
                content TEXT,
                timestamp REAL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_agent_id INTEGER,
                action TEXT,
                magnitude REAL,
                confidence REAL,
                detector_ids TEXT,
                evidence TEXT,
                turn INTEGER,
                timestamp REAL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE permission_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER,
                old_credibility REAL,
                new_credibility REAL,
                reason TEXT,
                recommending_detectors TEXT,
                timestamp REAL
            )
        """)

        # Useful indexes for faster analysis
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_turn ON messages(turn)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_turn ON actions(turn)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_recs_turn ON recommendations(turn)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_recs_target ON recommendations(target_agent_id)")

        self.conn.commit()

    def _to_json(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def _store_metadata(self, metadata: Dict[str, Any]) -> None:
        for key, value in metadata.items():
            self.cursor.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (key, self._to_json(value))
            )
        self.conn.commit()

    def log_message(self, message: Message) -> None:
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

    def log_action(self, action: Action) -> None:
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

    def log_recommendation(self, rec: Recommendation) -> None:
        self.cursor.execute("""
            INSERT INTO recommendations (
                target_agent_id, action, magnitude, confidence,
                detector_ids, evidence, turn, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec.target_agent_id,
            rec.action,
            rec.magnitude,
            rec.confidence,
            self._to_json(rec.detector_ids),
            rec.evidence,
            rec.turn,
            rec.timestamp
        ))
        self.conn.commit()

    def log_permission_change(self, change: PermissionChange) -> None:
        self.cursor.execute("""
            INSERT INTO permission_changes (agent_id, old_credibility, new_credibility, reason, recommending_detectors, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            change.agent_id,
            change.old_credibility,
            change.new_credibility,
            change.reason,
            self._to_json(change.recommending_detectors) if change.recommending_detectors else None,
            change.timestamp
        ))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()