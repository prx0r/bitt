"""HydraDB writer — writes Bittensor observations to the shared lab graph.

This connects /bitt's scanner to the private-lab HydraDB.
Private Lab can then query capability evidence across all modules.

Writes:
  - Subnet program nodes
  - Scanner observation edges
  - Submission outcome edges
  - Capability evidence edges
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt")))


def _get_hydra_client():
    """Get HydraDB client if available."""
    try:
        bolt = os.environ.get("HYDRADB_BOLT", "bolt://127.0.0.1:7687")
        token = os.environ.get("HYDRADB_TOKEN", "private-lab-hydradb-token-2026-secure")

        # Try to import from private-lab
        sys.path.insert(0, str(Path("/root/bitt/private-lab")))
        from integrations.hydra.client import HydraClient, hash_id

        client = HydraClient(bolt_url=bolt, auth_token=token)
        client.connect()
        return client
    except Exception as e:
        print(f"HydraDB not available: {e}")
        return None


def write_program(client, netuid: int, name: str, mode: str, economics: dict):
    """Write a subnet program node to HydraDB."""
    program_id = f"bittensor/sn{netuid}"

    client.run_write("""
        MERGE (p:Program {program_id: $pid})
        SET p.name = $name,
            p.module = 'bitt',
            p.venue = 'bittensor',
            p.mode = $mode,
            p.updated_at = $ts
    """, pid=program_id, name=name, mode=mode, ts=datetime.utcnow().isoformat())


def write_observation(client, netuid: int, block: int, metrics: dict):
    """Write a scanner observation edge."""
    program_id = f"bittensor/sn{netuid}"
    obs_id = f"obs-{netuid}-{block}"

    client.run_write("""
        MERGE (p:Program {program_id: $pid})
        MERGE (o:Observation {obs_id: $oid})
        SET o.block = $block,
            o.captured_at = $ts,
            o.metrics = $metrics
        MERGE (p)-[:HAS_OBSERVATION]->(o)
    """, pid=program_id, oid=obs_id, block=block,
        ts=datetime.utcnow().isoformat(), metrics=json.dumps(metrics))


def write_submission(client, program_id: str, submission_id: str,
                     worker_version: str, score: float | None = None,
                     tao_earned: float = 0.0):
    """Write a submission outcome edge."""
    client.run_write("""
        MERGE (p:Program {program_id: $pid})
        MERGE (s:Submission {sid: $sid})
        SET s.worker_version = $wv,
            s.score = $score,
            s.tao_earned = $tao,
            s.submitted_at = $ts
        MERGE (p)-[:HAS_SUBMISSION]->(s)
    """, pid=program_id, sid=submission_id, wv=worker_version,
        score=score or 0, tao=tao_earned, ts=datetime.utcnow().isoformat())


def write_capability_evidence(client, program_id: str, capabilities: dict):
    """Write capability evidence edges."""
    for cap_name, score in capabilities.items():
        cap_id = f"cap:{cap_name}"
        client.run_write("""
            MERGE (p:Program {program_id: $pid})
            MERGE (c:Capability {cap_id: $cid})
            SET c.name = $name, c.updated_at = $ts
            MERGE (p)-[:DEMANDS {score: $score}]->(c)
        """, pid=program_id, cid=cap_id, name=cap_name,
            score=score, ts=datetime.utcnow().isoformat())


def sync_to_hydradb():
    """Sync all /bitt data to HydraDB."""
    client = _get_hydra_client()
    if not client:
        print("Cannot connect to HydraDB. Skipping sync.")
        return

    from adapters.sn60.bitsec_adapter import BitsecAdapter
    adapter = BitsecAdapter()

    # Write program
    write_program(client, 60, "Bitsec", "LIVE",
                  adapter.get_program_status().economics)

    # Write capability evidence
    perf = adapter.get_performance()
    caps = perf.get("capability_evidence", {})
    if caps:
        write_capability_evidence(client, "bittensor/sn60", caps)

    # Write recent submissions
    for sub in adapter._get_recent_submissions(10):
        write_submission(
            client, "bittensor/sn60",
            sub["submission_id"], sub["worker_version"],
            sub.get("score"), sub.get("tao_earned", 0),
        )

    print(f"Synced to HydraDB: program=Bitsec, capabilities={len(caps)}, submissions=10")


if __name__ == "__main__":
    sync_to_hydradb()
