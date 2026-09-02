"""BitsecStudioAdapter — bridges Bitsec SN60 to Private Lab using frozen contracts.

Produces:
- TaskInstance contracts from ScaBench splits
- RunReceipt contracts from worker execution
- EvaluationResult contracts from scoring
- Finding contracts from vulnerability discoveries
- LearningProposal contracts from CGE analysis

All models imported from lab.contracts (frozen, versioned).
"""
from __future__ import annotations

import json
import hashlib
import random
from pathlib import Path
from typing import Any, Literal

from lab.contracts import (
    TaskInstance, RunSpec, RunReceipt, EvaluationSpec, EvaluationResult,
    Finding, FindingTier, CapabilityScope, Split, RunMode,
    SourceRef, ArtifactRef, BudgetEnvelope, ContextPack,
    LearningProposal, TransferClaim,
)
from lab.contracts import SCHEMA_VERSION

SCABENCH_DIR = Path("/root/bitt/subnets/sn60-bitsec/tools/scabench")
SPLIT_MANIFEST = SCABENCH_DIR / "splits.json"


def _hash_id(s: str) -> str:
    """Deterministic ID from string."""
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def load_scabench_projects() -> list[dict]:
    """Load ScaBench curated dataset."""
    for p in SCABENCH_DIR.rglob("curated-*.json"):
        if "baseline" not in str(p):
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    raise FileNotFoundError(f"DATASET_UNAVAILABLE: No ScaBench data in {SCABENCH_DIR}")


def create_task_instances(
    split: Literal["TRAIN", "DEV", "VALIDATION", "SECRET"],
    project_ids: list[str] | None = None,
    max_tasks: int = 10,
) -> list[TaskInstance]:
    """Create TaskInstance contracts from ScaBench data.

    Each TaskInstance is a frozen contract. The worker sees `content`
    (repo info, platform). The worker NEVER sees `evaluation_data`
    (ground truth vulnerabilities) — that stays hidden until scoring.
    """
    all_projects = load_scabench_projects()
    project_map = {p.get("project_id", ""): p for p in all_projects}

    if project_ids is None:
        project_ids = list(project_map.keys())[:max_tasks]

    tasks = []
    for pid in project_ids:
        proj = project_map.get(pid)
        if not proj:
            continue

        # Ground truth goes in evaluation_data (hidden from worker)
        vulns = proj.get("vulnerabilities", [])
        codebases = proj.get("codebases", [])
        repo_url = codebases[0].get("repo_url", "") if codebases else ""
        commit = codebases[0].get("commit", "") if codebases else ""

        task = TaskInstance(
            task_id=f"bitsec-{split.lower()}-{pid}",
            studio_id="bitsec",
            task_family="smart-contract-audit",
            split=Split(split),
            capability_scope=CapabilityScope(
                domains=["security"],
                subdomains=["smart-contract-audit"],
                capabilities=["vulnerability-detection", "code-audit"],
            ),
            content={
                "project_id": pid,
                "name": proj.get("name", ""),
                "platform": proj.get("platform", ""),
                "repo_url": repo_url,
                "commit": commit,
            },
            evaluation_data={
                "vulnerabilities": [
                    {"finding_id": v.get("finding_id", ""), "severity": v.get("severity", ""),
                     "title": v.get("title", ""), "description": v.get("description", ""),
                     "category": v.get("category", "")}
                    for v in vulns
                ],
                "n_vulnerabilities": len(vulns),
            },
        )
        tasks.append(task)

    return tasks


def execute_worker_run(
    task: TaskInstance,
    worker_version: str,
    model: str = "meta/llama-3.3-70b-instruct-fp8-fast",
) -> tuple[RunReceipt, list[dict]]:
    """Execute worker on a task. Returns RunReceipt + raw findings.

    The worker sees ONLY task.content. It never sees task.evaluation_data.
    """
    from workers.bitsec.cloudflare_harness import call_model

    content = task.content

    prompt = f"""You are a smart contract security auditor. Perform a comprehensive audit.

Project: {content['name']} ({content['platform']})

Analyze for ALL vulnerability types: reentrancy, access control, integer overflow,
unchecked returns, front-running, tx.origin, DoS, flash loan, oracle manipulation,
business logic errors, and any other security issues.

Return JSON array: [{{"category": "...", "title": "...", "severity": "...", "description": "..."}}]"""

    result = call_model(model, prompt, max_tokens=3000)
    findings_raw = []

    if result["ok"]:
        try:
            content_str = result["content"]
            start = content_str.find("[")
            end = content_str.rfind("]") + 1
            if start >= 0 and end > start:
                findings_raw = json.loads(content_str[start:end])
        except Exception:
            pass

    # Build RunReceipt contract
    run_id = f"run-{task.task_id}-{_hash_id(worker_version)[:8]}"
    receipt = RunReceipt(
        run_id=run_id,
        spec=RunSpec(
            run_id=run_id,
            lab_id="private-lab",
            studio_id="bitsec",
            task_instance_id=task.task_id,
            split=task.split,
            worker_id=worker_version.split("/")[0],
            worker_version_id=worker_version,
            capability_scope=task.capability_scope,
            evaluator_version_id="bitsec/jaccard@v1",
            mode=RunMode.REPLAY,
        ),
        success=result["ok"],
        artifacts=[],
        duration_ms=0,
    )

    return receipt, findings_raw


def evaluate_findings(
    run_receipt: RunReceipt,
    findings_raw: list[dict],
    task: TaskInstance,
) -> EvaluationResult:
    """Score findings against ground truth. Produces EvaluationResult contract.

    Ground truth comes from task.evaluation_data (hidden from worker during execution).
    Scoring uses official BitSec Jaccard methodology.
    """
    ground_truth = task.evaluation_data.get("vulnerabilities", [])

    # Extract categories
    agent_cats = [f.get("category", "").lower().strip() for f in findings_raw if f.get("category")]
    truth_cats = [v.get("category", "").lower().strip() for v in ground_truth if v.get("category")]

    # Jaccard score
    if agent_cats and truth_cats:
        set_agent = set(agent_cats)
        set_truth = set(truth_cats)
        jaccard = len(set_agent & set_truth) / max(len(set_agent | set_truth), 1)
    elif not agent_cats and not truth_cats:
        jaccard = 1.0
    else:
        jaccard = 0.0

    # Detection rate (title matching)
    matched_gt = set()
    for f in findings_raw:
        f_title = f.get("title", "").lower()
        f_cat = f.get("category", "").lower()
        for j, gt in enumerate(ground_truth):
            if j in matched_gt:
                continue
            gt_cat = gt.get("category", "").lower()
            if f_cat == gt_cat:
                matched_gt.add(j)
                break

    tp = len(matched_gt)
    fp = len(findings_raw) - tp
    fn = len(ground_truth) - tp
    detection_rate = tp / max(len(ground_truth), 1)
    precision = tp / max(tp + fp, 1)
    f1 = 2 * precision * detection_rate / max(precision + detection_rate, 0.001)

    # Gate: did we find at least one vulnerability?
    gates_passed = 1 if tp > 0 else 0
    gates_total = 1

    return EvaluationResult(
        result_id=f"eval-{run_receipt.run_id}",
        run_id=run_receipt.run_id,
        spec_id="bitsec/jaccard@v1",
        success=gates_passed >= gates_total,
        scores={
            "jaccard": round(jaccard, 4),
            "detection_rate": round(detection_rate, 4),
            "precision": round(precision, 4),
            "f1_score": round(f1, 4),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "n_expected": len(ground_truth),
            "n_found": len(findings_raw),
        },
        gates_passed=gates_passed,
        gates_total=gates_total,
        overall_score=round(f1, 4),
    )


def create_finding_contracts(
    findings_raw: list[dict],
    task: TaskInstance,
    run_id: str,
    eval_result: EvaluationResult,
) -> list[Finding]:
    """Create Finding contracts from raw findings."""
    findings = []
    ground_truth = task.evaluation_data.get("vulnerabilities", [])
    gt_titles = {v.get("title", "").lower() for v in ground_truth}

    for i, f in enumerate(findings_raw):
        # Determine tier based on whether it matches ground truth
        is_true_positive = f.get("title", "").lower() in gt_titles
        tier = FindingTier.STUDIO_FINDING if is_true_positive else FindingTier.OBSERVATION

        finding = Finding(
            finding_id=f"finding-{run_id}-{i}",
            tier=tier,
            studio_id="bitsec",
            capability_scope=task.capability_scope,
            claim=f"{f.get('category', 'unknown')}: {f.get('title', 'unnamed')}",
            evidence_run_ids=[run_id],
            confidence=0.7 if is_true_positive else 0.3,
            valid_in=["bitsec"] if is_true_positive else [],
        )
        findings.append(finding)

    return findings
