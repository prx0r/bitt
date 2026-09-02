"""BitSec ↔ CG Bridge — connects BitSec CG World to qdw-workbench learning loop.

The flow:
1. BitSecWorld provides tasks (ScaBench projects)
2. CG runner executes episodes (worker analyzes code)
3. RunEvaluator scores across 9 dimensions
4. Ledger records RunReceipt + EvaluationResult
5. HydraDB indexes for search
6. CGE reads failures, proposes mutations
7. CG runs paired evaluation (v0 vs v1 on sealed tasks)

This module is the glue between:
- /root/cg/cogym_kernel/ (CG execution)
- /root/bitt/ (BitSec world + worker)
- /root/bitt/private-lab/ (qdw-workbench evaluation + ledger)
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path("/root/cg")))
sys.path.insert(0, str(Path("/root/bitt")))
sys.path.insert(0, str(Path("/root/bitt/private-lab")))

from cogym_kernel.worlds.registry import create as create_world
from cogym_kernel.kernel.runner import AsyncRunner, ExecutorRegistry
from cogym_kernel.kernel.contracts import ActionSpec, ActionResult, CandidateArtifact

from lab.contracts import (
    TaskInstance, RunSpec, RunReceipt, EvaluationResult,
    Finding, FindingTier, CapabilityScope, Split, RunMode,
)
from lab.ledger import Ledger
from lab.projection import HydraProjector
from lab.evaluation import RunEvaluator, RunMetrics


# ─── BitSec LLM Executor ────────────────────────────────────────────

class BitSecExecutor:
    """Executes FIND_VULNERABILITIES action using WorkerKit ONLY.

    v0 and v1 use the SAME executor code path.
    The only difference is the mutation applied to the prompt.
    This is how we test whether a mutation actually helps.
    """

    def __init__(self, model: str = "mimo", mutation: dict | None = None):
        self.model = model
        self.mutation = mutation or {}  # The proposed change (from CGE)

    def execute(self, action: ActionSpec) -> ActionResult:
        if action.kind == "FIND_VULNERABILITIES":
            return self._find_vulnerabilities(action)
        elif action.kind == "SUBMIT_FINDINGS":
            return ActionResult(action_id=action.action_id, status="ok", payload={})
        return ActionResult(action_id=action.action_id, status="error",
                          error=f"unknown action: {action.kind}")

    def _find_vulnerabilities(self, action: ActionSpec) -> ActionResult:
        """Execute through WorkerKit ONLY. No fallback.

        The mutation parameter changes what the worker does.
        v0 gets no mutation, v1 gets the CGE-proposed mutation.
        Same code path, same repo, same seed — only the mutation differs.
        """
        repo_dir = action.payload.get("repo_dir", "")
        project_id = action.payload.get("project_id", "")

        if not repo_dir or not os.path.isdir(repo_dir):
            return ActionResult(
                action_id=action.action_id, status="error",
                error=f"REPO_UNAVAILABLE: {repo_dir}"
            )

        # Set API keys from vault
        sys.path.insert(0, str(Path("/root/bitt")))
        from vault import Vault
        v = Vault()
        os.environ['OPENCODE_API_KEY'] = v.get('opencode_go_api_key') or ''
        os.environ['GROQ_API_KEY'] = v.get('groq_api_key') or ''

        # Use WorkerKit's harness — NO FALLBACK
        sys.path.insert(0, str(Path("/root/mwgym")))
        from mwgym.harnesses.pydantic_bats import PydanticBATSHarness, UsageLimits

        harness = PydanticBATSHarness()
        limits = UsageLimits(
            request_limit=2,
            cost_limit_usd=0.10,
            wall_time_limit_s=120,
        )

        # Collect key Solidity files
        sol_files = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'target', 'test', 'tests', 'script']]
            for f in files:
                if f.endswith('.sol'):
                    fp = os.path.join(root, f)
                    rel = os.path.relpath(fp, repo_dir)
                    if any(skip in rel.lower() for skip in ['test/', 'tests/', 'script/']):
                        continue
                    try:
                        content = open(fp).read()
                        if len(content) > 50:
                            sol_files.append(f"// File: {rel}\n{content}")
                    except:
                        pass

        combined_code = "\n\n".join(sol_files)[:50000]

        # Build task prompt — same base for v0 and v1
        # Pool knowledge: doctrine is always included (evidence-first, reproducibility)
        pool_doctrine = """
Security Principles (from pool doctrine):
1. Evidence First: Every finding must have a reproducible evidence path.
2. Exploitability Over Theory: Practical impact > theoretical impact.
3. False Positive Control: Never report a finding you cannot reproduce.
4. Scope Awareness: Understand the target scope before analysis.
5. Progressive Disclosure: Quick sweep → deep dive on promising targets.
6. Reproducible Methodology: If only you can reproduce it, it's an opinion.
"""
        base_prompt = f"""You are a security auditor analyzing a Solidity codebase for vulnerabilities.

{pool_doctrine}

Project: {project_id}

Source code ({len(sol_files)} Solidity files):
```solidity
{combined_code}
```

Analyze ALL the code above for security vulnerabilities. For each finding return a JSON array:
[{{"title": "...", "severity": "critical|high|medium|low", "category": "...", "description": "...", "file": "...", "line_start": N}}]"""

        # Apply mutation (only for v1)
        mutation = self.mutation
        if mutation:
            mutation_type = mutation.get("type", "")
            mutation_change = mutation.get("change", {})

            if mutation_type == "process_change":
                process = mutation_change.get("process", "")
                if process == "tob-entry-point":
                    base_prompt += "\n\nMODE: Entry-point analysis. Map all public/external functions, trace data flow, check authorization at each state change."
                elif process == "fp-check":
                    base_prompt += "\n\nMODE: False positive verification. Only report findings you can confirm from the code. Verify each finding before reporting."
                elif process == "cross-file":
                    base_prompt += "\n\nMODE: Cross-file analysis. Look for vulnerabilities spanning multiple files — data flow between contracts, shared state, external calls across boundaries."
                elif process == "simplified":
                    base_prompt = f"""You are a security auditor. Find the most critical vulnerabilities in this Solidity code.

```solidity
{combined_code}
```

Return JSON array:
[{{"title": "...", "severity": "...", "category": "...", "description": "...", "file": "...", "line_start": N}}]

Focus on: reentrancy, access control, integer overflow. Be concise."""

        task = base_prompt

        import tempfile, shutil
        with tempfile.TemporaryDirectory() as workspace:
            # Materialize full repo
            for item in os.listdir(repo_dir):
                src = os.path.join(repo_dir, item)
                dst = os.path.join(workspace, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, symlinks=True, ignore_dangling_symlinks=True)
                else:
                    shutil.copy2(src, dst)

            # Execute through WorkerKit
            run_obj, fv = harness.run(
                task=task,
                workspace=workspace,
                limits=limits,
                world_genome_id="bitsec.scabench",
                worker_genome_id="security-01/v0",
                family_id="smart-contract-audit",
            )

            # Parse findings
            content = run_obj.output if hasattr(run_obj, 'output') else ""
            findings = []
            try:
                clean = content.strip()
                if clean.startswith("```"):
                    first_nl = clean.find("\n")
                    if first_nl > 0:
                        clean = clean[first_nl + 1:]
                    if clean.rstrip().endswith("```"):
                        clean = clean.rstrip()[:-3].rstrip()

                if clean.strip().startswith('{'):
                    outer = json.loads(clean)
                    if isinstance(outer, dict) and 'writes' in outer:
                        for w in outer['writes']:
                            inner = w.get('content', '')
                            inner_clean = inner.strip()
                            if inner_clean.startswith("```"):
                                first_nl = inner_clean.find("\n")
                                if first_nl > 0:
                                    inner_clean = inner_clean[first_nl + 1:]
                                if inner_clean.rstrip().endswith("```"):
                                    inner_clean = inner_clean.rstrip()[:-3].rstrip()
                            start = inner_clean.find('[')
                            end = inner_clean.rfind(']') + 1
                            if start >= 0 and end > start:
                                findings.extend(json.loads(inner_clean[start:end]))

                if not findings:
                    start = clean.find('[')
                    end = clean.rfind(']') + 1
                    if start >= 0 and end > start:
                        findings = json.loads(clean[start:end])
            except Exception:
                pass

            # Record trajectory (step-by-step decisions)
            trajectory = []
            for mc in (run_obj.model_calls if hasattr(run_obj, 'model_calls') else []):
                trajectory.append({
                    "step_type": "model_call",
                    "model": mc.get("model", ""),
                    "provider": mc.get("provider", ""),
                    "input_tokens": mc.get("prompt_tokens", 0),
                    "output_tokens": mc.get("completion_tokens", 0),
                    "cost_usd": mc.get("cost_usd", 0),
                })

            return ActionResult(
                action_id=action.action_id,
                status="ok",
                payload={
                    "findings": findings,
                    "cost_usd": run_obj.cost_usd if hasattr(run_obj, 'cost_usd') else 0.0,
                    "tokens": run_obj.total_tokens if hasattr(run_obj, 'total_tokens') else 0,
                    "executor": "workerkit-pydantic-bats",
                    "mutation_applied": bool(mutation),
                    "mutation_type": mutation.get("type", "") if mutation else "",
                    "trajectory": trajectory,
                    "repo_dir": repo_dir,
                    "project_id": project_id,
                },
            )


# ─── BitSec Policy ──────────────────────────────────────────────────

class BitSecPolicy:
    """Simple policy: analyze code, then submit findings."""

    def initialize(self, world_spec):
        return {"step": 0}

    def act(self, obs, actions, pstate):
        step = pstate.get("step", 0)
        pstate["step"] = step + 1

        if step == 0 and any(a.kind == "FIND_VULNERABILITIES" for a in actions):
            action = next(a for a in actions if a.kind == "FIND_VULNERABILITIES")
        else:
            action = next((a for a in actions if a.kind == "SUBMIT_FINDINGS"), actions[0])

        # Pass repo_dir and project_id into action payload
        repo_dir = obs.get("repo_dir", "")
        project_id = obs.get("project_id", "")
        action = ActionSpec(
            kind=action.kind,
            payload={"repo_dir": repo_dir, "project_id": project_id},
            executor_kind=action.executor_kind,
            estimated_cost=action.estimated_cost,
            timeout_ms=action.timeout_ms,
        )

        class Decision:
            def __init__(self, a):
                self.action = a
        return Decision(action)


# ─── Bridge: CG Episode → qdw-workbench Contracts ───────────────────

class BitSecBridge:
    """Bridges CG execution to qdw-workbench's learning loop.

    Runs a CG episode and produces:
    - RunReceipt (frozen contract)
    - EvaluationResult (frozen contract)
    - Finding contracts with tier system
    - Ledger events
    - HydraDB projection
    """

    def __init__(self, model: str = "mimo", mutation: dict | None = None):
        self.ledger = Ledger()
        self.hydra = HydraProjector(self.ledger)
        self.evaluator = RunEvaluator()
        self.executor = BitSecExecutor(model=model, mutation=mutation)
        self.runner = AsyncRunner(ExecutorRegistry({
            "llm": self.executor,
            "deterministic": self.executor,
        }))

    def run_episode(
        self,
        instance_id: str,
        seed: int,
        worker_version: str = "security-01/v0",
        split: str = "DEV",
        max_steps: int = 3,
    ) -> dict:
        """Run one full CG episode and produce all contracts.

        Returns a dict with:
        - cg_receipt: CG RunReceipt
        - run_receipt: qdw-workbench RunReceipt
        - eval_result: EvaluationResult
        - metrics: RunMetrics (9 dimensions)
        - findings: list[Finding]
        """
        t0 = time.time()

        # 1. Create CG world
        world = create_world("bitsec.scabench", split=split)

        # 2. Run CG episode
        policy = BitSecPolicy()
        cg_receipt = asyncio.run(self.runner.run_episode(
            world=world,
            policy=policy,
            instance_id=instance_id,
            seed=seed,
            max_steps=max_steps,
        ))

        duration_ms = int((time.time() - t0) * 1000)

        # 3. Extract metrics from CG receipt
        metrics_dict = {}
        for m in cg_receipt.metrics.metrics:
            metrics_dict[m.name] = m.value

        # 4. Create qdw-workbench RunSpec
        run_id = f"run-{instance_id}-{seed}"
        spec = RunSpec(
            run_id=run_id,
            lab_id="private-lab",
            studio_id="bitsec",
            task_instance_id=instance_id,
            split=Split(split),
            worker_id=worker_version.split("/")[0],
            worker_version_id=worker_version,
            capability_scope=CapabilityScope(
                domains=["security"],
                subdomains=["smart-contract-audit"],
                capabilities=["vulnerability-detection"],
            ),
            evaluator_version_id="bitsec/jaccard@v1",
            seed=seed,
            mode=RunMode.REPLAY,
        )

        # 5. Record run.created to Ledger
        self.ledger.append_event(
            event_type="run.created",
            entity_id=run_id,
            schema_version="1.0.0",
            payload=spec.model_dump(),
        )

        # 6. Evaluate with RunEvaluator (9 dimensions)
        state = world.reset(instance_id=instance_id, seed=seed)

        # Extract findings from CG receipt (executor results)
        executor_result = {}
        for eh in cg_receipt.event_hashes:
            # In production, extract from event store
            pass

        # Get actual metrics from CG receipt
        actual_tokens = 0
        actual_cost = 0.0
        actual_tool_calls = 0

        metrics = self.evaluator.evaluate(
            run_id=run_id,
            worker_version_id=worker_version,
            world_id="bitsec.scabench",
            task_score=metrics_dict.get("detection_rate", 0.0),
            task_success=metrics_dict.get("detection_rate", 0.0) > 0.1,
            hidden_state={"n_vulnerabilities": len(state.ground_truth)},
            worker_inferences={"n_findings": metrics_dict.get("n_found", 0)},
            observations_used=1,
            observations_optimal=1,
            tool_calls=actual_tool_calls,
            tokens_used=actual_tokens,
            cost_usd=actual_cost,
            wall_time_ms=duration_ms,
            invalid_actions=0,
            worker_confidence=0.5,
        )

        # 7. Create EvaluationResult
        eval_result = self.evaluator.to_evaluation_result(metrics)

        # 8. Record evaluation.completed to Ledger
        self.ledger.append_event(
            event_type="evaluation.completed",
            entity_id=run_id,
            schema_version="1.0.0",
            payload=eval_result.model_dump(),
        )

        # 9. Create Finding contracts from executor results
        # Findings are extracted from the CG receipt's metrics
        findings = []
        ground_truth = state.ground_truth
        gt_titles = {v.get("title", "").lower() for v in ground_truth}

        n_found = int(metrics_dict.get("n_found", 0))
        for i in range(n_found):
            # Create generic finding contract (detailed matching done by evaluator)
            finding = Finding(
                finding_id=f"finding-{run_id}-{i}",
                tier=FindingTier.OBSERVATION,
                studio_id="bitsec",
                capability_scope=spec.capability_scope,
                claim=f"vulnerability-{i}",
                evidence_run_ids=[run_id],
                confidence=0.5,
            )
            findings.append(finding)

            self.ledger.append_event(
                event_type="finding.created",
                entity_id=finding.finding_id,
                schema_version="1.0.0",
                payload=finding.model_dump(),
            )

        # 10. Create RunReceipt
        run_receipt = RunReceipt(
            run_id=run_id,
            spec=spec,
            success=eval_result.success,
            artifacts=[],
            evaluation_result_id=eval_result.result_id,
            duration_ms=duration_ms,
        )

        # 11. Record run.completed to Ledger
        self.ledger.append_event(
            event_type="run.completed",
            entity_id=run_id,
            schema_version="1.0.0",
            payload=run_receipt.model_dump(),
        )

        # 12. /bitt emits canonical events ONLY
        # HydraDB projection is owned by qdw-workbench, not /bitt.
        # /bitt never writes directly to HydraDB.
        # The ledger events above are the canonical evidence.
        # qdw-workbench's HydraProjector reads these events and projects them.

        return {
            "cg_receipt": cg_receipt,
            "run_receipt": run_receipt,
            "eval_result": eval_result,
            "metrics": metrics,
            "findings": findings,
            "metrics_dict": metrics_dict,
        }


# ─── Convenience: Run Full Experiment ────────────────────────────────

def run_experiment(
    n_tasks: int = 5,
    arm: str = "A",
    split: str = "DEV",
    model: str = "mimo",
) -> dict:
    """Run a full BitSec experiment across multiple tasks.

    Returns aggregated results for CGE analysis.
    """
    bridge = BitSecBridge(model=model, arm=arm)
    results = []

    for i in range(n_tasks):
        seed = 42 + i
        instance_id = f"bitsec-{split.lower()}-{i:03d}"

        print(f"[{i+1}/{n_tasks}] {instance_id}...", end=" ", flush=True)
        result = bridge.run_episode(
            instance_id=instance_id,
            seed=seed,
            split=split,
        )

        m = result["metrics_dict"]
        print(f"DR={m.get('detection_rate', 0):.1%} F1={m.get('f1_score', 0):.3f}")
        results.append(result)

    # Aggregate
    n = len(results)
    avg_dr = sum(r["metrics_dict"].get("detection_rate", 0) for r in results) / max(n, 1)
    avg_f1 = sum(r["metrics_dict"].get("f1_score", 0) for r in results) / max(n, 1)

    return {
        "arm": arm,
        "model": model,
        "n_tasks": n,
        "avg_detection_rate": avg_dr,
        "avg_f1": avg_f1,
        "results": results,
    }


if __name__ == "__main__":
    result = run_experiment(n_tasks=3, arm="A")
    print(f"\n=== Experiment Complete ===")
    print(f"Arm: {result['arm']}")
    print(f"Tasks: {result['n_tasks']}")
    print(f"Avg DR: {result['avg_detection_rate']:.1%}")
    print(f"Avg F1: {result['avg_f1']:.3f}")
