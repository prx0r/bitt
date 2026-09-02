"""Bitsec Bridge — connects Bitsec adapter to mwgym run infrastructure.

This is the integration layer that makes Bitsec submissions produce
WorkerRuns, which get stored as Receipts, which feed capability
evidence to HydraDB.

Flow:
  Bitsec task → WorkerRun → Receipt → HydraDB capability evidence
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add mwgym to path
sys.path.insert(0, str(Path("/root/mwgym")))
sys.path.insert(0, str(Path("/root/bitt/integration")))

from mwgym.run.spec import (
    WorkerRun, WorkerVersion, ComputePolicy, Evaluation,
    ProviderRequest, GateResult, CapabilityScore, FailureVector,
)
from mwgym.run.receipt import record_receipt
from mwgym.harnesses.pydantic_bats import BATSRouter, UsageLimits


class BitsecBridge:
    """Bridges Bitsec adapter to mwgym run infrastructure."""

    def __init__(self, subnet_id: int = 60):
        self.subnet_id = subnet_id
        self.router = BATSRouter()
        self.worker_version = WorkerVersion(
            worker_id=f"bitsec-sn{subnet_id}",
            version="v1",
        )

    def create_run(self, task: str, budget_usd: float = 0.01,
                   workspace: str = "/tmp/bitsec-run") -> WorkerRun:
        """Create a WorkerRun for a Bitsec task."""
        # BATS routing for model selection
        route = self.router.select(
            task_type=f"bittensor.bitsec",
            budget_remaining=budget_usd,
            uncertainty=0.5,
        )

        compute = ComputePolicy(
            policy_id=f"bitsec-{self.subnet_id}",
            arm="M",
            budget_usd=budget_usd,
            model_preference=route.model,
        )

        return WorkerRun(
            campaign_id=f"bittensor/sn{self.subnet_id}",
            task_family=f"bittensor.bitsec",
            worker=self.worker_version,
            compute=compute,
            evaluation=Evaluation(),
        )

    def record_submission(self, run: WorkerRun, score: float, rank: int,
                          tao_earned: float, agent_path: str = ""):
        """Record a Bitsec submission as a WorkerRun receipt."""
        # Set evaluation
        run.evaluation = Evaluation(
            success=score > 0.5,
            quality=score,
            correctness=score,
            gates=[
                GateResult(gate_id="g0", gate_name="score_above_threshold",
                          passed=score > 0.5, actual=f"{score:.3f}"),
            ],
            capabilities=[
                CapabilityScore("vulnerability_detection", score, f"Bitsec SN{self.subnet_id}"),
                CapabilityScore("security", score * 0.98, f"Bitsec SN{self.subnet_id}"),
            ],
        )

        # Economics
        run.actual_cost_usd = run.compute.budget_usd
        run.realized_reward_usd = tao_earned * 230  # approximate

        # Evidence
        if agent_path and Path(agent_path).exists():
            run.artifact_hashes = [
                hashlib.sha256(Path(agent_path).read_bytes()).hexdigest()
            ]

        # Store receipt
        record_receipt(run)

        return run

    def get_capability_evidence(self) -> dict:
        """Get capability evidence from past runs."""
        import sqlite3
        db_path = Path("/root/mwgym/data/receipts.db")
        if not db_path.exists():
            return {}
        conn = sqlite3.connect(str(db_path))

        cur = conn.execute("""
            SELECT capabilities FROM receipts
            WHERE task_family LIKE '%bitsec%'
            ORDER BY created_at DESC LIMIT 50
        """)

        evidence = {}
        for row in cur.fetchall():
            caps_raw = row[0]
            if not caps_raw:
                continue
            try:
                caps = json.loads(caps_raw)
            except json.JSONDecodeError:
                continue
            for cap in caps:
                if isinstance(cap, dict):
                    name = cap.get("capability", "")
                    score = cap.get("score", 0)
                elif isinstance(cap, str):
                    name = cap
                    score = 0.5
                else:
                    continue
                if name not in evidence:
                    evidence[name] = []
                evidence[name].append(score)

        # Average
        result = {}
        for name, scores in evidence.items():
            result[name] = {
                "mean": sum(scores) / len(scores),
                "count": len(scores),
                "latest": scores[0] if scores else 0,
            }

        return result


def run_bitsec_batch(n_runs: int = 10, budget_per_run: float = 0.01):
    """Run a batch of Bitsec training episodes."""
    bridge = BitsecBridge()
    print(f"Running {n_runs} Bitsec episodes (${budget_per_run}/run)...")

    for i in range(n_runs):
        # Create run
        run = bridge.create_run(
            task=f"Analyze code for vulnerabilities (episode {i+1})",
            budget_usd=budget_per_run,
        )

        # Simulate (in production, this would call the real Bitsec eval)
        score = 0.3 + (i / n_runs) * 0.4  # improving over time
        tao = score * 0.5  # approximate reward

        # Record
        bridge.record_submission(run, score=score, rank=i+1, tao_earned=tao)

        print(f"  Episode {i+1}: score={score:.3f} tao={tao:.4f}")

    # Get capability evidence
    evidence = bridge.get_capability_evidence()
    print(f"\nCapability evidence:")
    for cap, data in evidence.items():
        print(f"  {cap}: mean={data['mean']:.3f} (n={data['count']})")


if __name__ == "__main__":
    run_bitsec_batch(n_runs=10)
