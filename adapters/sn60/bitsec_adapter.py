"""Bitsec SN60 Adapter — manages the Bitsec program lifecycle.

From the architecture review:
  - /bitt owns Bittensor internals
  - Private Lab receives standardized program status
  - Internal Bitsec rounds stay inside /bitt
  - Cross-module intelligence goes through HydraDB capability pools
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt/integration")))

from bittensor_gym.config import SUBNETS


DB_PATH = Path("/root/bitt/data/sn60_state.db")


@dataclass
class ProgramState:
    """What Private Lab sees about Bitsec — no internal details leaked."""
    program_id: str = "bittensor/sn60"
    module: str = "bitt"
    venue: str = "bitsec"
    mode: str = "DISCOVER"  # DISCOVER|REPRODUCE|LOCAL_BASELINE|TRAINING|SEALED|SHADOW|LIVE
    current_round: int = 0
    next_submission_deadline: str | None = None
    registration_state: str = "unregistered"  # unregistered|registered|active
    economics: dict = field(default_factory=dict)
    capability_demand: dict = field(default_factory=dict)
    our_state: dict = field(default_factory=dict)
    possible_actions: list[str] = field(default_factory=list)


@dataclass
class SubmissionRecord:
    """Internal record of a Bitsec submission."""
    submission_id: str
    worker_version: str
    submitted_at: str
    agent_hash: str
    status: str  # pending|evaluated|scored|accepted|rejected
    score: float | None = None
    rank: int | None = None
    tao_earned: float = 0.0
    feedback: str = ""
    cost_usd: float = 0.0


class BitsecAdapter:
    """Adapter for Bitsec SN60.

    Owns all Bitsec-specific state.
    Exposes standardized program interface to Private Lab.
    """
    def __init__(self):
        self.db = self._init_db()
        self._ensure_tables()

    def _init_db(self) -> sqlite3.Connection:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(DB_PATH))

    def _ensure_tables(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                submission_id TEXT PRIMARY KEY,
                worker_version TEXT,
                submitted_at TEXT,
                agent_hash TEXT,
                status TEXT,
                score REAL,
                rank INTEGER,
                tao_earned REAL DEFAULT 0,
                feedback TEXT,
                cost_usd REAL DEFAULT 0
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS state_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT,
                data JSON
            )
        """)
        self.db.commit()

    # ─── Program interface (what Private Lab sees) ──────────────────

    def get_program_status(self) -> ProgramState:
        """Standardized status for Private Lab consumption."""
        from oracle.capture import get_latest_capture
        cap = get_latest_capture()
        subnet = cap.get("subnets", {}).get("60", {}) if cap else {}

        # Determine mode from state
        mode = self._determine_mode()

        # Economics
        economics = {
            "registration_cost_tao": subnet.get("burn_tao", 0),
            "registration_cost_usd": subnet.get("burn_tao", 0) * 230,
            "contestable_miner_tao_day": subnet.get("contestable_miner_tao_day", 0),
            "total_tao_day": subnet.get("total_tao_day", 0),
            "alpha_price": subnet.get("alpha_price", 0),
        }

        # Our state
        submissions = self._get_recent_submissions(5)
        latest_score = submissions[0]["score"] if submissions else None
        our_state = {
            "worker_version": "sec-v1",
            "sealed_score": latest_score,
            "total_submissions": len(submissions),
            "accepted": sum(1 for s in submissions if s["status"] == "accepted"),
            "rejected": sum(1 for s in submissions if s["status"] == "rejected"),
        }

        # Capability demand (what Bitsec trains)
        capability_demand = {
            "security": 0.99,
            "smart_contract_security": 0.94,
            "vulnerability_detection": 0.98,
        }

        # Possible actions
        actions = ["train"]
        if mode in ("LIVE", "SHADOW"):
            actions.append("submit_candidate")
        if mode == "DISCOVER":
            actions.append("clone_and_replay")
        actions.append("explore_new_worker")

        return ProgramState(
            mode=mode,
            economics=economics,
            capability_demand=capability_demand,
            our_state=our_state,
            possible_actions=actions,
        )

    def get_actions(self) -> list[dict]:
        """Available actions for Private Lab to consider."""
        return [
            {"action": "train", "description": "Run CGE training loop"},
            {"action": "submit_candidate", "description": "Submit agent to Bitsec"},
            {"action": "hold", "description": "Wait for better version"},
            {"action": "explore_new_worker", "description": "Try new vulnerability patterns"},
        ]

    def get_performance(self) -> dict:
        """Our performance metrics."""
        submissions = self._get_recent_submissions(20)
        if not submissions:
            return {"no_data": True}

        scored = [s for s in submissions if s["score"] is not None]
        return {
            "total_submissions": len(submissions),
            "scored": len(scored),
            "avg_score": sum(s["score"] for s in scored) / max(len(scored), 1),
            "best_score": max((s["score"] for s in scored), default=0),
            "acceptance_rate": sum(1 for s in submissions if s["status"] == "accepted") / max(len(submissions), 1),
            "total_tao_earned": sum(s["tao_earned"] for s in submissions),
            "total_cost_usd": sum(s["cost_usd"] for s in submissions),
            "capability_evidence": self._get_capability_evidence(),
        }

    # ─── Actions (Private Lab can call these) ──────────────────────

    def submit_candidate(self, worker_version: str, agent_path: str,
                         cost_usd: float = 0.0) -> dict:
        """Submit an agent to Bitsec. Returns submission record."""
        import hashlib
        agent_hash = hashlib.sha256(Path(agent_path).read_bytes()).hexdigest()[:16]
        submission_id = f"sn60-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        self.db.execute("""
            INSERT INTO submissions (submission_id, worker_version, submitted_at,
                                    agent_hash, status, cost_usd)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (submission_id, worker_version, datetime.utcnow().isoformat(),
              agent_hash, cost_usd))
        self.db.commit()

        return {
            "submission_id": submission_id,
            "status": "pending",
            "worker_version": worker_version,
            "agent_hash": agent_hash,
        }

    def record_outcome(self, submission_id: str, score: float, rank: int,
                       tao_earned: float, feedback: str = ""):
        """Record the outcome of a submission."""
        self.db.execute("""
            UPDATE submissions SET status='scored', score=?, rank=?,
                   tao_earned=?, feedback=?
            WHERE submission_id=?
        """, (score, rank, tao_earned, feedback, submission_id))
        self.db.commit()

    # ─── Internal state ─────────────────────────────────────────────

    def _determine_mode(self) -> str:
        """Determine current mode from state."""
        submissions = self._get_recent_submissions(1)
        if not submissions:
            return "DISCOVER"
        if submissions[0]["status"] == "accepted":
            return "LIVE"
        if submissions[0]["score"] is not None:
            return "SEALED"
        return "TRAINING"

    def _get_recent_submissions(self, limit: int = 10) -> list[dict]:
        cur = self.db.execute(
            "SELECT * FROM submissions ORDER BY submitted_at DESC LIMIT ?",
            (limit,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _get_capability_evidence(self) -> dict:
        """Capability evidence from past runs."""
        submissions = self._get_recent_submissions(50)
        scored = [s for s in submissions if s["score"] is not None]
        if not scored:
            return {}

        avg_score = sum(s["score"] for s in scored) / len(scored)
        return {
            "vulnerability_detection": min(1.0, avg_score),
            "smart_contract_security": min(1.0, avg_score * 0.95),
            "security": min(1.0, avg_score * 0.98),
        }

    def to_private_lab_format(self) -> dict:
        """Export as Private Lab program status."""
        status = self.get_program_status()
        perf = self.get_performance()
        actions = self.get_actions()

        return {
            "program": {
                "id": status.program_id,
                "module": status.module,
                "venue": status.venue,
            },
            "state": {
                "mode": status.mode,
                "current_round": status.current_round,
                "registration_state": status.registration_state,
            },
            "economics": status.economics,
            "capability_demand": status.capability_demand,
            "our_state": status.our_state,
            "performance": perf,
            "possible_actions": actions,
            "capabilities": perf.get("capability_evidence", {}),
        }
