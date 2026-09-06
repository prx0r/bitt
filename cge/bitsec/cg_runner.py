"""BitSec CG Integration — runs pipeline-v1 agent through the CG world framework.

Each SCA-Bench project is a CG world fork (different instance_id/seed).
Evolution mutates the agent's analysis strategy across generations.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/root/cg")
sys.path.insert(0, "/root/bitt")

from cogym_kernel.worlds.bitsec import BitSecWorld, BitSecState
from cogym_kernel.kernel.contracts import ActionResult, ActionSpec

# ── Config ─────────────────────────────────────────────────────────

PROXY = "http://localhost:8087"
API_KEY = "sk-A5QHR5MRtUNec7BWqiRsZ0GAYck0CRT2Movsk7Q6U3UwcV77Y6G3TMXOhhyKh855"
MODEL = "mimo-v2.5"

# The 6 official BitSec projects (use as fixed instance_ids for reproducibility)
OFFICIAL_PROJECTS = [
    "code4rena_coded-estate-invitational_2024_12",
    "code4rena_iq-ai_2025_03",
    "code4rena_liquid-ron_2025_03",
    "code4rena_mantra-dex_2025_03",
    "sherlock_cork-protocol_2025_01",
    "sherlock_crestal-network_2025_03",
]

RESULTS_DIR = Path("/root/bitt/data/cg-bitsec-runs")


# ── Worker: runs pipeline-v1 agent ────────────────────────────────

def run_worker(project_id: str) -> list[dict]:
    """Run pipeline-v1 agent on a project and return findings."""
    import subprocess

    source_dir = Path(f"/root/bitt/data/scabench-repos/{project_id}")
    if not source_dir.exists():
        return []

    agent_path = Path("/root/bitt/mining/sn60/candidates/pipeline-v1/agent.py")
    if not agent_path.exists():
        return []

    env = os.environ.copy()
    env["INFERENCE_API"] = PROXY
    env["INFERENCE_API_KEY"] = API_KEY
    env["AGENT_ID"] = "cg-worker"
    env["OPENAI_MODEL"] = MODEL

    try:
        result = subprocess.run(
            [sys.executable, str(agent_path), str(source_dir)],
            capture_output=True, text=True, timeout=900,
            env=env
        )
    except subprocess.TimeoutExpired:
        return []

    # Read report
    report_path = source_dir / "agent_report.json"
    if report_path.exists():
        try:
            report = json.load(open(report_path))
            return report.get("vulnerabilities", [])
        except:
            pass

    return []


# ── CG Episode Runner ──────────────────────────────────────────────

def run_episode(world: BitSecWorld, instance_id: str, seed: int) -> dict:
    """Run one episode: world.reset → worker → world.score."""
    # Reset world to specific project
    state = world.reset(instance_id=instance_id, seed=seed)

    # Worker observes (no ground truth)
    observation = world.observe(state)

    # Worker runs pipeline-v1
    print(f"    Running worker on {state.project_id}...", flush=True)
    start = time.time()
    findings = run_worker(state.project_id)
    duration = time.time() - start

    # Create action result
    result = ActionResult(
        action_id="find_vulns",
        status="ok",
        payload={"findings": findings},
        wall_ms=duration * 1000,
    )

    # Apply to world
    state = world.apply(state, ActionSpec(kind="FIND_VULNERABILITIES"), result)
    state = world.apply(state, ActionSpec(kind="SUBMIT_FINDINGS"), result)

    # Score against hidden ground truth
    metrics = world.score(state)

    # Extract metrics
    metric_dict = {}
    for m in metrics.metrics:
        metric_dict[m.name] = m.value

    return {
        "project_id": state.project_id,
        "findings_count": len(findings),
        "duration_seconds": round(duration, 1),
        "metrics": metric_dict,
        "detection_rate": metric_dict.get("detection_rate", 0),
        "true_positives": metric_dict.get("true_positives", 0),
        "expected": metric_dict.get("n_expected", 0),
    }


# ── CG Evolution Loop ──────────────────────────────────────────────

def run_cg_evolution(generations=2, n_projects=6):
    """Run CG evolution: evaluate → score → mutate → repeat."""
    world = BitSecWorld()

    log_dir = RESULTS_DIR / f"cg-{int(time.time())}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Use official projects as fixed instance_ids
    projects = OFFICIAL_PROJECTS[:n_projects]

    print(f"CG Evolution: {generations} generations × {len(projects)} projects", flush=True)
    print(f"Projects: {projects}", flush=True)
    print(f"Log: {log_dir}", flush=True)

    # Generation 0: baseline evaluation
    print(f"\n{'='*60}", flush=True)
    print("GENERATION 0 — Baseline", flush=True)
    print(f"{'='*60}", flush=True)

    gen0_results = []
    for project_id in projects:
        print(f"\n  Project: {project_id}", flush=True)
        result = run_episode(world, project_id, seed=42)
        gen0_results.append(result)
        dr = result["detection_rate"]
        tp = result["true_positives"]
        exp = result["expected"]
        print(f"    DR={dr:.0%} ({int(tp)}/{int(exp)}) {result['duration_seconds']}s", flush=True)

    # Save gen0
    (log_dir / "gen0.json").write_text(json.dumps(gen0_results, indent=2))

    # Summary
    avg_dr = sum(r["detection_rate"] for r in gen0_results) / len(gen0_results)
    total_tp = sum(r["true_positives"] for r in gen0_results)
    total_exp = sum(r["expected"] for r in gen0_results)
    print(f"\n  Gen 0 Summary: avg DR={avg_dr:.0%} ({int(total_tp)}/{int(total_exp)} total TPs)", flush=True)

    # For now, just run baseline. Evolution requires strategy mutation.
    # The mutation happens at the prompt level — we'd need to modify the pipeline-v1
    # agent's prompts based on what worked/didn't work.

    # Save summary
    summary = {
        "generations_run": 1,
        "projects": projects,
        "gen0_avg_dr": round(avg_dr, 3),
        "gen0_total_tp": int(total_tp),
        "gen0_total_expected": int(total_exp),
        "gen0_results": gen0_results,
        "log_dir": str(log_dir),
    }
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n{'='*60}", flush=True)
    print(f"CG BASELINE COMPLETE", flush=True)
    print(f"Average DR: {avg_dr:.0%} ({int(total_tp)}/{int(total_exp)})", flush=True)
    print(f"Log: {log_dir}", flush=True)
    print(f"{'='*60}", flush=True)

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--projects", type=int, default=6)
    args = parser.parse_args()
    run_cg_evolution(generations=args.generations, n_projects=args.projects)
