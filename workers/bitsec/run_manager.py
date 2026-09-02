"""Security Run Manager — end-to-end runs with qdw-workbench integration.

Produces:
- TaskInstances from ScaBench splits
- RunSpecs for each execution
- Real LLM execution via miner_v5
- EvaluationResults with proper scoring
- RunReceipts recorded to Ledger (canonical truth)
- HydraDB projection (derived, rebuildable)
- Findings with tier system (OBSERVATION → STUDIO_FINDING)
- Pool knowledge connection (doctrine, skills, findings)

All contracts imported from lab.contracts (frozen, versioned).
"""
from __future__ import annotations

import json
import hashlib
import time
import os
import sys
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path("/root/bitt/private-lab")))
sys.path.insert(0, str(Path("/root/bitt")))

from lab.contracts import (
    TaskInstance, RunSpec, RunReceipt, EvaluationSpec, EvaluationResult,
    Finding, FindingTier, CapabilityScope, Split, RunMode,
    SourceRef, ArtifactRef, BudgetEnvelope, ContextPack, ContextFragment,
    TrustTier, WorkerVersion,
)
from lab.ledger import Ledger
from lab.projection import HydraProjector
from workers.bitsec.miner_v5 import analyze_code, PROCESS_ARMS
from workers.bitsec.cloudflare_harness import call_model
from cge.bitsec.world import load_scabench_dataset, score_vulnerabilities


SCABENCH_DIR = Path("/root/bitt/subnets/sn60-bitsec/tools/scabench")
REPOS_DIR = Path("/root/bitt/data/scabench-repos")


class SecurityRunManager:
    """End-to-end run manager for security workers.

    Integrates with qdw-workbench:
    - Ledger: canonical append-only truth
    - HydraDB: derived searchable projection
    - Contracts: frozen Pydantic models
    - Pool: shared knowledge (doctrine, findings, skills)
    """

    def __init__(self):
        self.ledger = Ledger()
        self.hydra = HydraProjector(self.ledger)

    def create_task_instances(
        self,
        split: Literal["TRAIN", "DEV", "VALIDATION", "SECRET"],
        max_tasks: int = 5,
    ) -> list[TaskInstance]:
        """Create TaskInstances from ScaBench data."""
        projects = load_scabench_dataset(max_projects=31)

        # Split deterministically
        import random
        rng = random.Random(42)
        shuffled = list(projects)
        rng.shuffle(shuffled)

        n = len(shuffled)
        splits = {
            "TRAIN": shuffled[:int(n*0.5)],
            "DEV": shuffled[int(n*0.5):int(n*0.7)],
            "VALIDATION": shuffled[int(n*0.7):int(n*0.85)],
            "SECRET": shuffled[int(n*0.85):],
        }

        tasks = []
        for proj in splits[split][:max_tasks]:
            task = TaskInstance(
                task_id=f"bitsec-{split.lower()}-{proj.project_id}",
                studio_id="bitsec",
                task_family="smart-contract-audit",
                split=Split(split),
                capability_scope=CapabilityScope(
                    domains=["security"],
                    subdomains=["smart-contract-audit"],
                    capabilities=["vulnerability-detection", "code-audit"],
                ),
                content={
                    "project_id": proj.project_id,
                    "name": proj.name,
                    "platform": proj.platform,
                    "repo_url": proj.repo_url,
                    "commit": proj.commit,
                },
                evaluation_data={
                    "vulnerabilities": [
                        {"finding_id": v.finding_id, "severity": v.severity,
                         "title": v.title, "description": v.description,
                         "category": v.category}
                        for v in proj.vulnerabilities
                    ],
                    "n_vulnerabilities": len(proj.vulnerabilities),
                },
            )
            tasks.append(task)

        return tasks

    def load_code(self, project_id: str) -> str:
        """Load source code from cloned repo. Prioritize .sol files."""
        repo_dir = REPOS_DIR / project_id
        if not repo_dir.is_dir():
            return ""

        # First pass: collect .sol files (highest priority)
        sol_parts = []
        other_parts = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'target', 'deps', 'test', 'tests', 'script']]
            for f in files:
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, repo_dir)
                # Skip test files and config
                if any(skip in rel.lower() for skip in ['test/', 'tests/', 'script/', 'hardhat.config', 'foundry.toml', '.config.']):
                    continue
                try:
                    content = open(fp).read()
                    if len(content) > 50:
                        entry = f'// File: {rel}\n{content}'
                        if f.endswith('.sol'):
                            sol_parts.append(entry)
                        elif f.endswith(('.rs', '.js', '.ts', '.py', '.go')):
                            other_parts.append(entry)
                except:
                    pass

        # Prefer Solidity contracts, fall back to other languages
        all_parts = sol_parts + other_parts
        return '\n\n'.join(all_parts)[:15000]

    def execute_run(
        self,
        task: TaskInstance,
        worker_version: str = "security-01/v0",
        arm: str = "A",
    ) -> RunReceipt:
        """Execute a full run: TaskInstance → RunSpec → execution → RunReceipt.

        Records to Ledger (canonical) and projects to HydraDB (derived).
        """
        # 1. Create RunSpec
        run_id = f"run-{task.task_id}-{int(time.time())}"
        spec = RunSpec(
            run_id=run_id,
            lab_id="private-lab",
            studio_id="bitsec",
            task_instance_id=task.task_id,
            split=task.split,
            worker_id=worker_version.split("/")[0],
            worker_version_id=worker_version,
            capability_scope=task.capability_scope,
            evaluator_version_id="bitsec/jaccard@v1",
            seed=42,
            mode=RunMode.REPLAY,
        )

        # 2. Record run.created to Ledger
        self.ledger.append_event(
            event_type="run.created",
            entity_id=run_id,
            schema_version="1.0.0",
            payload=spec.model_dump(),
        )

        # 3. Load code and execute
        code = self.load_code(task.content.get("project_id", ""))
        if not code:
            # No code available — record failure
            receipt = RunReceipt(
                run_id=run_id,
                spec=spec,
                success=False,
                artifacts=[],
                duration_ms=0,
            )
            self.ledger.append_event(
                event_type="run.failed",
                entity_id=run_id,
                schema_version="1.0.0",
                payload=receipt.model_dump(),
            )
            return receipt

        # 4. Execute via miner_v5
        t0 = time.time()
        result = analyze_code(code, arm=arm)
        duration_ms = int((time.time() - t0) * 1000)

        # 5. Score against ground truth
        findings_raw = result.get("vulnerabilities", [])
        ground_truth = task.evaluation_data.get("vulnerabilities", [])

        # Convert ground truth to VulnTruth-like objects for scoring
        from cge.bitsec.world import VulnTruth
        gt_objects = [
            VulnTruth(
                finding_id=v.get("finding_id", ""),
                severity=v.get("severity", ""),
                title=v.get("title", ""),
                description=v.get("description", ""),
                category=v.get("category", ""),
            )
            for v in ground_truth
        ]

        score = score_vulnerabilities(findings_raw, gt_objects)

        # 6. Create EvaluationResult
        eval_result = EvaluationResult(
            result_id=f"eval-{run_id}",
            run_id=run_id,
            spec_id="bitsec/jaccard@v1",
            success=score["detection_rate"] > 0,
            scores={
                "jaccard": score["jaccard"],
                "detection_rate": score["detection_rate"],
                "precision": score["precision"],
                "f1_score": score["f1_score"],
                "true_positives": score["true_positives"],
                "false_positives": score["false_positives"],
                "false_negatives": score["false_negatives"],
                "n_expected": score["n_expected"],
                "n_found": score["n_found"],
            },
            gates_passed=1 if score["true_positives"] > 0 else 0,
            gates_total=1,
            overall_score=score["f1_score"],
        )

        # 7. Record evaluation.completed to Ledger
        self.ledger.append_event(
            event_type="evaluation.completed",
            entity_id=run_id,
            schema_version="1.0.0",
            payload=eval_result.model_dump(),
        )

        # 8. Create Findings with tier system
        findings = self._create_findings(findings_raw, task, run_id, score)

        # 9. Record findings to Ledger
        for f in findings:
            self.ledger.append_event(
                event_type="finding.created",
                entity_id=f.finding_id,
                schema_version="1.0.0",
                payload=f.model_dump(),
            )

        # 10. Create RunReceipt
        receipt = RunReceipt(
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
            payload=receipt.model_dump(),
        )

        # 12. Project to HydraDB (derived, rebuildable)
        try:
            self._project_to_hydra(spec, eval_result, findings, receipt)
        except Exception as e:
            print(f"Warning: Hydra projection failed: {e}")

        return receipt

    def _create_findings(
        self,
        findings_raw: list[dict],
        task: TaskInstance,
        run_id: str,
        score: dict,
    ) -> list[Finding]:
        """Create Finding contracts with proper tier system."""
        ground_truth = task.evaluation_data.get("vulnerabilities", [])
        gt_titles = {v.get("title", "").lower() for v in ground_truth}
        gt_descs = {v.get("description", "").lower()[:100] for v in ground_truth}

        findings = []
        for i, f in enumerate(findings_raw):
            # Determine tier based on match quality
            f_title = f.get("title", "").lower()
            f_desc = f.get("description", "").lower()[:100]

            # Check if matches ground truth
            is_match = False
            for gt_title in gt_titles:
                if any(w in gt_title for w in f_title.split() if len(w) > 3):
                    is_match = True
                    break
            for gt_desc in gt_descs:
                if any(w in gt_desc for w in f_desc.split() if len(w) > 3):
                    is_match = True
                    break

            tier = FindingTier.STUDIO_FINDING if is_match else FindingTier.OBSERVATION

            finding = Finding(
                finding_id=f"finding-{run_id}-{i}",
                tier=tier,
                studio_id="bitsec",
                capability_scope=task.capability_scope,
                claim=f"{f.get('category', 'unknown')}: {f.get('title', 'unnamed')}",
                evidence_run_ids=[run_id],
                confidence=0.7 if is_match else 0.3,
                valid_in=["bitsec"] if is_match else [],
            )
            findings.append(finding)

        return findings

    def _project_to_hydra(
        self,
        spec: RunSpec,
        eval_result: EvaluationResult,
        findings: list[Finding],
        receipt: RunReceipt,
    ):
        """Project run to HydraDB (derived, rebuildable)."""
        from integrations.hydra import get_client, hash_id, create_run_at_venue

        client = get_client()

        # Project run
        create_run_at_venue(
            run_id=spec.run_id,
            outcome="success" if receipt.success else "failure",
            venue_id="bitsec",
            venue_name="Bitsec SN60",
            pool_id="security",
            pool_name="security",
        )

        # Project findings
        for f in findings:
            fid = hash_id(f.finding_id)
            props = {
                "id": fid,
                "finding_id": f.finding_id,
                "tier": f.tier.value,
                "claim": f.claim[:200],
                "confidence": f.confidence,
                "studio": f.studio_id,
            }
            p_str = ", ".join(f"{k}: ${k}" for k in props)
            try:
                client.run_write(
                    f"CREATE (f:Finding {{{p_str}}})-[:_SELF]->(f2:Finding {{id: $id}})", **props
                )
                client.run_write(
                    "MATCH (f:Finding {id: $id})-[r:_SELF]->() DELETE r", id=fid
                )
            except Exception:
                pass

    def run_experiment(
        self,
        split: Literal["TRAIN", "DEV", "SECRET"] = "DEV",
        arms: list[str] | None = None,
        max_tasks: int = 3,
    ) -> dict:
        """Run full experiment across process arms.

        Returns comparison results for CGE analysis.
        """
        if arms is None:
            arms = ["A", "B", "C", "D"]

        tasks = self.create_task_instances(split, max_tasks)
        print(f"Running {len(tasks)} tasks across {len(arms)} arms...")

        all_results = {}
        for arm in arms:
            print(f"\n=== Arm {arm}: {PROCESS_ARMS.get(arm, {}).get('name', '?')} ===")
            arm_results = []

            for task in tasks:
                print(f"  {task.content.get('name', '?')}...", end=" ", flush=True)
                receipt = self.execute_run(task, arm=arm)

                # Get evaluation result from ledger
                events = self.ledger.get_entity_history(receipt.run_id)
                eval_event = next((e for e in events if e["event_type"] == "evaluation.completed"), None)
                if eval_event:
                    payload = json.loads(eval_event["payload_json"])
                    scores = payload.get("scores", {})
                    print(f"DR={scores.get('detection_rate', 0):.1%} F1={scores.get('f1_score', 0):.3f}")
                    arm_results.append(scores)
                else:
                    print("FAILED")

            if arm_results:
                n = len(arm_results)
                avg_dr = sum(r.get("detection_rate", 0) for r in arm_results) / n
                avg_f1 = sum(r.get("f1_score", 0) for r in arm_results) / n
                all_results[arm] = {
                    "name": PROCESS_ARMS.get(arm, {}).get("name", "?"),
                    "n_tasks": n,
                    "avg_dr": round(avg_dr, 4),
                    "avg_f1": round(avg_f1, 4),
                    "results": arm_results,
                }
                print(f"  ARM {arm} AVG: DR={avg_dr:.1%} F1={avg_f1:.3f}")

        return all_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Security Run Manager")
    parser.add_argument("--split", choices=["TRAIN", "DEV", "VALIDATION", "SECRET"],
                        default="DEV")
    parser.add_argument("--arms", nargs="+", default=["A", "B", "C", "D"])
    parser.add_argument("--tasks", type=int, default=3)
    args = parser.parse_args()

    manager = SecurityRunManager()
    results = manager.run_experiment(args.split, args.arms, args.tasks)

    # Save results
    output_path = Path("/root/bitt/data/experiment-results.json")
    output_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {output_path}")
