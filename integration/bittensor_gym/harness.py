"""BittensorHarness — MWGym HarnessAdapter for Bittensor subnet tasks.

Implements the HarnessAdapter protocol so Bittensor subnet tasks can be
run through MWGym's evolution pipeline.

Three modes:
  1. SUBNET_LOCAL   — run subnet's miner locally in Docker sandbox
  2. SUBNET_REMOTE  — query subnet axons via Bittensor network
  3. SUBNET_EMULATE — simulate subnet scoring locally using cloned code
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# MWGym imports (sibling repo)
import sys
MWGYM_ROOT = Path("/root/mwgym")
WORKERKIT_ROOT = Path("/root/workerkit")
if str(MWGYM_ROOT) not in sys.path:
    sys.path.insert(0, str(MWGYM_ROOT))
if str(WORKERKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKERKIT_ROOT))

from mwgym.harnesses.base import HarnessInstance, HarnessRun, StateSnapshot
from mwgym.schema.genome import WorkerGenome
from mwgym.schema.world import (
    CapabilityScore, FailureVector, GateResult, WorldGenome,
)

from .config import SUBNETS, SubnetConfig


# ─── Bittensor Subnet Harness ────────────────────────────────────────

@dataclass
class BittensorHarnessConfig:
    """Configuration for Bittensor subnet execution."""
    subnet_id: int = 67
    mode: str = "SUBNET_EMULATE"  # SUBNET_LOCAL, SUBNET_REMOTE, SUBNET_EMULATE
    docker_image: str = ""        # override Docker image for local mode
    timeout_s: float = 300.0
    max_retries: int = 3
    wallet_path: str = "~/.bittensor/wallets/"
    network: str = "finney"
    rpc_endpoint: str = ""        # override RPC
    task_type: str = "research"   # research, coding, forecasting, shopping


class BittensorHarness:
    """MWGym HarnessAdapter for Bittensor subnet tasks.

    Maps Bittensor subnet evaluation into MWGym's harness interface.
    The worker (miner agent) gets:
      - task from the subnet's task distribution
      - sandbox environment (Docker or simulated)
      - scoring from the subnet's validator logic

    Returns standard HarnessRun + FailureVector for CGE evolution.
    """

    def __init__(self, config: BittensorHarnessConfig | None = None):
        self.config = config or BittensorHarnessConfig()
        self.subnet = SUBNETS.get(self.config.subnet_id)
        if not self.subnet:
            raise ValueError(f"Unknown subnet {self.config.subnet_id}. Known: {list(SUBNETS.keys())}")
        self._subnet_dir = self._find_subnet_dir()

    def _find_subnet_dir(self) -> Path:
        """Locate cloned subnet repo."""
        mapping = {
            67: Path("/root/bitt/subnets/sn67-harnyx"),
            62: Path("/root/bitt/subnets/sn62-ridges"),
            6: Path("/root/bitt/subnets/sn6-numinous"),
            15: Path("/root/bitt/subnets/sn15-oro"),
        }
        d = mapping.get(self.config.subnet_id, Path())
        return d if d.exists() else Path()

    # ─── HarnessAdapter Protocol ──────────────────────────────────────

    async def provision(self, genome: WorkerGenome, worker_id: str) -> HarnessInstance:
        """Provision a Bittensor miner agent for execution."""
        return HarnessInstance(
            harness=f"bittensor.sn{self.config.subnet_id}",
            worker_id=worker_id,
            session_id=f"bt-{self.config.subnet_id}-{int(time.time())}",
            metadata={
                "subnet_id": self.config.subnet_id,
                "subnet_name": self.subnet.name,
                "mode": self.config.mode,
                "family_id": self.subnet.family_id,
            },
        )

    async def run(self, instance: HarnessInstance, task: str,
                  workspace: str) -> HarnessRun:
        """Execute a Bittensor subnet task."""
        t0 = time.time()
        ws = Path(workspace)
        ws.mkdir(parents=True, exist_ok=True)

        if self.config.mode == "SUBNET_EMULATE":
            return await self._run_emulate(instance, task, workspace, t0)
        elif self.config.mode == "SUBNET_LOCAL":
            return await self._run_local(instance, task, workspace, t0)
        elif self.config.mode == "SUBNET_REMOTE":
            return await self._run_remote(instance, task, workspace, t0)
        else:
            return HarnessRun(ok=False, output=f"Unknown mode: {self.config.mode}")

    async def _run_emulate(self, instance: HarnessInstance, task: str,
                           workspace: str, t0: float) -> HarnessRun:
        """Run subnet task locally using cloned subnet code.

        This is the primary development mode — no network, no wallet.
        Loads the subnet's miner code and executes against local test data.
        """
        ws = Path(workspace)

        # Write task to workspace
        task_file = ws / "task.json"
        task_data = {
            "task_id": instance.session_id,
            "subnet": self.config.subnet_id,
            "task": task,
            "family": self.subnet.family_id,
            "timestamp": time.time(),
        }
        task_file.write_text(json.dumps(task_data, indent=2))

        # Write subnet config
        config_file = ws / "subnet_config.json"
        config_file.write_text(json.dumps({
            "netuid": self.subnet.netuid,
            "name": self.subnet.name,
            "score_dimensions": list(self.subnet.score_dimensions),
            "gates": list(self.subnet.gates),
            "capabilities": list(self.subnet.capabilities),
        }, indent=2))

        # Check if subnet has a test runner
        test_runner = None
        for candidate in ["run_tests.sh", "test.sh", "Makefile", "run_miner.sh"]:
            if (self._subnet_dir / candidate).exists():
                test_runner = candidate
                break

        # For SN62 (Ridges), use their agent runner
        if self.config.subnet_id == 62 and (self._subnet_dir / "ridges.py").exists():
            test_runner = "ridges.py"

        # For SN67 (Harnyx), check for sandbox runner
        if self.config.subnet_id == 67 and (self._subnet_dir / "sandbox").exists():
            test_runner = "sandbox"

        # Write the worker's agent code placeholder
        agent_file = ws / "agent.py"
        if not agent_file.exists():
            agent_file.write_text(self._generate_agent_skeleton())

        # Run validation if possible
        validation_result = self._run_validation(ws, test_runner)

        duration_ms = int((time.time() - t0) * 1000)
        ok = validation_result.get("ok", False)

        # Build gate results
        gates = self._build_gates(validation_result)

        return HarnessRun(
            ok=ok,
            output=json.dumps(validation_result, indent=2),
            artifacts=[str(f) for f in ws.iterdir() if f.is_file()],
            model_calls=validation_result.get("model_calls", 0),
            duration_ms=duration_ms,
            cost_usd=validation_result.get("cost_usd", 0.0),
            total_tokens=validation_result.get("total_tokens", 0),
            metadata={
                "run_id": instance.session_id,
                "subnet_id": self.config.subnet_id,
                "mode": "SUBNET_EMULATE",
                "test_runner": test_runner,
                "validation": validation_result,
            },
        )

    async def _run_local(self, instance: HarnessInstance, task: str,
                         workspace: str, t0: float) -> HarnessRun:
        """Run subnet miner in local Docker sandbox."""
        ws = Path(workspace)
        ws.mkdir(parents=True, exist_ok=True)

        # Check if subnet has docker-compose
        docker_compose = self._subnet_dir / "docker-compose.yml"
        if not docker_compose.exists():
            return HarnessRun(
                ok=False,
                output=f"No docker-compose.yml in {self._subnet_dir}",
                duration_ms=int((time.time() - t0) * 1000),
                metadata={"error": "no_docker_compose"},
            )

        # Build and run in Docker
        try:
            result = subprocess.run(
                ["docker", "compose", "up", "--build", "-d"],
                cwd=str(self._subnet_dir),
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return HarnessRun(
                    ok=False,
                    output=f"Docker build failed: {result.stderr[:500]}",
                    duration_ms=int((time.time() - t0) * 1000),
                    metadata={"error": "docker_build_failed"},
                )
        except subprocess.TimeoutExpired:
            return HarnessRun(
                ok=False,
                output="Docker build timed out",
                duration_ms=int((time.time() - t0) * 1000),
                metadata={"error": "docker_timeout"},
            )

        # TODO: send task to container, collect results
        duration_ms = int((time.time() - t0) * 1000)
        return HarnessRun(
            ok=True,
            output="Docker sandbox started (task injection TODO)",
            duration_ms=duration_ms,
            metadata={"subnet_id": self.config.subnet_id, "mode": "SUBNET_LOCAL"},
        )

    async def _run_remote(self, instance: HarnessInstance, task: str,
                          workspace: str, t0: float) -> HarnessRun:
        """Query subnet axons via Bittensor network.

        Requires: bittensor package installed, wallet configured.
        """
        try:
            import bittensor as bt
        except ImportError:
            return HarnessRun(
                ok=False,
                output="bittensor package not installed. pip install bittensor",
                duration_ms=int((time.time() - t0) * 1000),
                metadata={"error": "bittensor_not_installed"},
            )

        # TODO: query metagraph, find best axons, send task via Synapse
        duration_ms = int((time.time() - t0) * 1000)
        return HarnessRun(
            ok=False,
            output="Remote query TODO — requires wallet + network setup",
            duration_ms=duration_ms,
            metadata={"subnet_id": self.config.subnet_id, "mode": "SUBNET_REMOTE"},
        )

    def _generate_agent_skeleton(self) -> str:
        """Generate a skeleton miner agent for the subnet."""
        return f'''"""Skeleton miner agent for SN{self.config.subnet_id} ({self.subnet.name}).

Generated by bittensor_gym. Replace with your actual agent logic.
"""
import json
import sys


def handle_task(task: dict) -> dict:
    """Process a subnet task and return result.

    Args:
        task: dict with task_id, subnet, task description

    Returns:
        dict with score, output, metadata
    """
    # TODO: implement actual agent logic
    # This is where your research/coding/forecasting/shopping agent lives

    return {{
        "score": 0.0,
        "output": "Agent not implemented yet",
        "metadata": {{
            "subnet": {self.config.subnet_id},
            "task_id": task.get("task_id", ""),
        }},
    }}


if __name__ == "__main__":
    task_file = sys.argv[1] if len(sys.argv) > 1 else "task.json"
    with open(task_file) as f:
        task = json.load(f)
    result = handle_task(task)
    print(json.dumps(result))
'''

    def _run_validation(self, workspace: str, test_runner: str | None) -> dict:
        """Run subnet-specific validation."""
        ws = Path(workspace)

        if not test_runner:
            # No test runner available — basic file existence check
            return {
                "ok": ws.exists(),
                "gates": {"files_written": ws.exists()},
                "model_calls": 0,
                "cost_usd": 0.0,
            }

        runner_path = self._subnet_dir / test_runner

        if test_runner.endswith(".py"):
            try:
                result = subprocess.run(
                    ["python", str(runner_path), str(ws / "task.json")],
                    cwd=str(workspace),
                    capture_output=True, text=True, timeout=60,
                )
                return {
                    "ok": result.returncode == 0,
                    "output": result.stdout[:2000],
                    "error": result.stderr[:500] if result.returncode != 0 else "",
                    "model_calls": 1,
                    "cost_usd": 0.0,
                }
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "validation_timeout"}
        elif test_runner.endswith(".sh"):
            try:
                result = subprocess.run(
                    ["bash", str(runner_path)],
                    cwd=str(workspace),
                    capture_output=True, text=True, timeout=60,
                )
                return {
                    "ok": result.returncode == 0,
                    "output": result.stdout[:2000],
                    "error": result.stderr[:500] if result.returncode != 0 else "",
                }
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "validation_timeout"}

        return {"ok": True, "gates": {}, "model_calls": 0}

    def _build_gates(self, validation: dict) -> list[GateResult]:
        """Build GateResult list from validation output."""
        gates = []
        for i, gate_name in enumerate(self.subnet.gates):
            passed = validation.get("gates", {}).get(gate_name, False)
            if not validation.get("gates"):
                # If no gate data, infer from overall ok
                passed = validation.get("ok", False)
            gates.append(GateResult(
                gate_id=f"g{i}",
                gate_name=gate_name,
                passed=passed,
                actual="pass" if passed else "fail",
            ))
        return gates

    async def snapshot(self, instance: HarnessInstance) -> StateSnapshot:
        return StateSnapshot(
            harness=instance.harness,
            snapshot_id=f"snap-{instance.session_id}",
            data=instance.metadata,
        )

    async def restore(self, snapshot: StateSnapshot) -> HarnessInstance:
        return HarnessInstance(
            harness=snapshot.harness,
            worker_id=snapshot.data.get("worker_id", ""),
            session_id=snapshot.data.get("session_id", ""),
            metadata=snapshot.data,
        )

    async def close(self, instance: HarnessInstance) -> None:
        pass  # nothing to clean up for emulation mode
