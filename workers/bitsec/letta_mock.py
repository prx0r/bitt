"""Letta Mock — SQLite-backed persistent worker identity.

Follows the real Letta interface but stores state locally.
When real Letta is available, swap this adapter for RealLettaAdapter.

Key properties:
- One persistent agent per worker_id (survives restarts)
- Fresh conversation/session per run (no cross-run contamination)
- Memory blocks are read-only during evaluated runs
- Memory changes require LearningProposal → CG experiment → promotion
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


DB_PATH = Path("/root/bitt/data/letta_mock.db")


class LettaMock:
    """SQLite-backed persistent worker identity.

    Follows the real Letta interface:
    - ensure_worker() → agent_id (persistent)
    - start_run() → session_id (fresh per run)
    - send_task() → result
    - get_trajectory() → step history
    """

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or str(DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                worker_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                model TEXT DEFAULT 'mimo-v2.5',
                persona TEXT DEFAULT '',
                memory_blocks TEXT DEFAULT '[]',
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                worker_id TEXT NOT NULL,
                run_id TEXT,
                created_at REAL,
                FOREIGN KEY (worker_id) REFERENCES agents(worker_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trajectory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                step INTEGER,
                role TEXT,
                content TEXT,
                tool_call TEXT,
                tool_result TEXT,
                timestamp REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                label TEXT NOT NULL,
                value TEXT NOT NULL,
                immutable INTEGER DEFAULT 0,
                created_at REAL,
                FOREIGN KEY (agent_id) REFERENCES agents(worker_id)
            )
        """)
        conn.commit()
        conn.close()

    def ensure_worker(self, worker_id: str, model: str = "mimo-v2.5",
                      persona: str = "") -> str:
        """Ensure worker exists. Returns agent_id (persistent)."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT agent_id FROM agents WHERE worker_id = ?", (worker_id,)
        ).fetchone()

        if row:
            agent_id = row[0]
            conn.close()
            return agent_id

        # Create new agent
        agent_id = f"agent-{hashlib.sha256(worker_id.encode()).hexdigest()[:12]}"
        now = time.time()
        conn.execute(
            "INSERT INTO agents (worker_id, agent_id, model, persona, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (worker_id, agent_id, model, persona, now, now)
        )

        # Add default memory blocks
        conn.execute(
            "INSERT INTO memory_blocks (agent_id, label, value, immutable, created_at) "
            "VALUES (?, 'persona', ?, 1, ?)",
            (agent_id, persona or "You are a Moltwork security worker.", now)
        )
        conn.execute(
            "INSERT INTO memory_blocks (agent_id, label, value, immutable, created_at) "
            "VALUES (?, 'worker_identity', ?, 1, ?)",
            (agent_id, json.dumps({"worker_id": worker_id, "version": "v0"}), now)
        )

        conn.commit()
        conn.close()
        return agent_id

    def start_run(self, worker_id: str, run_id: str) -> str:
        """Start a new run session. Returns session_id (fresh per run)."""
        session_id = f"session-{run_id}-{int(time.time())}"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO sessions (session_id, worker_id, run_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, worker_id, run_id, time.time())
        )
        conn.commit()
        conn.close()
        return session_id

    def send_task(self, session_id: str, task: str, workspace: str = "") -> dict:
        """Send task to worker. Returns result with trajectory."""
        # For now, return a mock result
        # In production, this would call the real Letta runtime
        return {
            "ok": True,
            "output": f"Task received: {task[:100]}...",
            "session_id": session_id,
            "trajectory": [],
        }

    def record_step(self, session_id: str, step: int, role: str,
                    content: str, tool_call: str = "", tool_result: str = ""):
        """Record a step in the trajectory."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO trajectory (session_id, step, role, content, tool_call, tool_result, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, step, role, content, tool_call, tool_result, time.time())
        )
        conn.commit()
        conn.close()

    def get_trajectory(self, session_id: str) -> list[dict]:
        """Get trajectory for a session."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT step, role, content, tool_call, tool_result, timestamp "
            "FROM trajectory WHERE session_id = ? ORDER BY step",
            (session_id,)
        ).fetchall()
        conn.close()
        return [
            {"step": r[0], "role": r[1], "content": r[2],
             "tool_call": r[3], "tool_result": r[4], "timestamp": r[5]}
            for r in rows
        ]

    def get_memory_blocks(self, worker_id: str) -> list[dict]:
        """Get memory blocks for a worker."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT label, value, immutable FROM memory_blocks WHERE agent_id = ?",
            (self.ensure_worker(worker_id),)
        ).fetchall()
        conn.close()
        return [{"label": r[0], "value": r[1], "immutable": bool(r[2])} for r in rows]

    def list_workers(self) -> list[dict]:
        """List all workers."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT worker_id, agent_id, model FROM agents").fetchall()
        conn.close()
        return [{"worker_id": r[0], "agent_id": r[1], "model": r[2]} for r in rows]
