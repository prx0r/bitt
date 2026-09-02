"""Bitsec CGE World v2 — uses actual Bitsec Jaccard scoring + ScaBench data.

Scoring (from bitsec/validator/reward.py):
  Jaccard = intersection(categories) / union(categories)
  + LLM-based 1-5 scoring for detailed matching

Models: mimo-v2.5 (free via Cloudflare Workers AI)
Dataset: ScaBench curated (31 projects, 555 vulns)
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCABENCH_DIR = Path("/root/bitt/subnets/sn60-bitsec/tools/scabench")


@dataclass
class VulnTruth:
    finding_id: str
    severity: str
    title: str
    description: str
    category: str = ""


@dataclass
class Project:
    project_id: str
    name: str
    platform: str
    repo_url: str
    commit: str
    vulnerabilities: list[VulnTruth] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    baseline_findings: list[dict] = field(default_factory=list)


def load_scabench_dataset(max_projects: int = 31) -> list[Project]:
    """Load ScaBench curated dataset with baseline results."""
    dataset_path = None
    for p in SCABENCH_DIR.rglob("curated-*.json"):
        if "baseline" not in str(p):
            dataset_path = p
            break

    if not dataset_path:
        raise FileNotFoundError(
            f"DATASET_UNAVAILABLE: No ScaBench curated dataset found in {SCABENCH_DIR}. "
            "Production must fail closed — no silent synthetic fallback."
        )

    try:
        with open(dataset_path) as f:
            raw = json.load(f)

        # Load baseline results
        baseline_dir = dataset_path.parent / "baseline-results"
        baselines = {}
        if baseline_dir.exists():
            for bf in baseline_dir.glob("baseline_*.json"):
                try:
                    bd = json.loads(bf.read_text())
                    baselines[bd.get("project", "")] = bd
                except Exception:
                    pass

        projects = []
        for proj in raw[:max_projects]:
            vulns = [
                VulnTruth(
                    finding_id=v.get("finding_id", ""),
                    severity=v.get("severity", "medium"),
                    title=v.get("title", ""),
                    description=v.get("description", ""),
                )
                for v in proj.get("vulnerabilities", [])
            ]

            codebases = proj.get("codebases", [])
            repo_url = codebases[0].get("repo_url", "") if codebases else ""
            commit = codebases[0].get("commit", "") if codebases else ""

            # Get baseline findings
            baseline = baselines.get(proj.get("project_id", ""), {})
            baseline_findings = baseline.get("findings", [])

            projects.append(Project(
                project_id=proj.get("project_id", ""),
                name=proj.get("name", ""),
                platform=proj.get("platform", ""),
                repo_url=repo_url,
                commit=commit,
                vulnerabilities=vulns,
                baseline_findings=baseline_findings,
            ))

        return projects
    except Exception as e:
        raise RuntimeError(
            f"DATASET_UNAVAILABLE: Failed to load ScaBench dataset: {e}. "
            "Production must fail closed — no silent synthetic fallback."
        ) from e


def _generate_synthetic_dataset() -> list[Project]:
    vuln_templates = [
        ("reentrancy", "CRITICAL", "Reentrancy in withdraw()", "External call before state update"),
        ("unchecked_return", "HIGH", "Unchecked return value", "Call return value not checked"),
        ("access_control", "HIGH", "Missing access control", "Function callable by anyone"),
        ("integer_overflow", "HIGH", "Integer overflow", "Arithmetic without SafeMath"),
        ("front_running", "MEDIUM", "Front-running vulnerability", "Commit-reveal without delay"),
        ("tx_origin", "MEDIUM", "tx.origin authentication", "Using tx.origin instead of msg.sender"),
    ]
    projects = []
    for i in range(10):
        vulns = [
            VulnTruth(finding_id=f"synth-{i}-{j}", severity=v[1], title=v[2], description=v[3], category=v[0])
            for j, v in enumerate(random.sample(vuln_templates, random.randint(1, 4)))
        ]
        projects.append(Project(project_id=f"synth-{i}", name=f"Synthetic {i}", platform="synthetic",
                                repo_url=f"https://example.com/synth-{i}", commit="abc", vulnerabilities=vulns))
    return projects


# ─── Jaccard scoring (from bitsec/validator/reward.py) ──────────────

def jaccard_score_agent_vs_truth(agent_categories: list[str],
                                  truth_categories: list[str]) -> float:
    """Jaccard score: intersection(categories) / union(categories).

    This is Bitsec's actual scoring metric.
    """
    if not agent_categories and not truth_categories:
        return 1.0
    if not agent_categories or not truth_categories:
        return 0.0

    set_agent = set(c.lower().strip() for c in agent_categories)
    set_truth = set(c.lower().strip() for c in truth_categories)

    intersection = set_agent & set_truth
    union = set_agent | set_truth

    if not union:
        return 1.0

    return len(intersection) / len(union)


def score_vulnerabilities(agent_findings: list[dict],
                          ground_truth: list[VulnTruth]) -> dict:
    """Score agent findings against ground truth using Bitsec's methodology.

    Returns:
      - jaccard: category-level Jaccard score
      - detection_rate: TP / expected
      - precision: TP / (TP + FP)
      - f1: harmonic mean
      - matched: list of matched pairs
      - missed: list of missed ground truth
      - extra: list of false positives
    """
    # Extract categories (if available)
    agent_cats = [f.get("category", "").lower().strip() for f in agent_findings if f.get("category")]
    truth_cats = [v.category.lower().strip() for v in ground_truth if v.category]

    # Jaccard score — use categories if both have them, otherwise skip
    if agent_cats and truth_cats:
        set_agent = set(agent_cats)
        set_truth = set(truth_cats)
        jaccard = len(set_agent & set_truth) / max(len(set_agent | set_truth), 1)
    else:
        jaccard = 0.0  # No categories to compare — rely on title matching

    # Title-based matching (primary scoring when categories unavailable)
    matched_gt = set()
    matched_findings = []
    extra_findings = []

    for f in agent_findings:
        f_title = f.get("title", "").lower().strip()
        f_desc = f.get("description", "").lower().strip()[:200]
        best_match = None
        best_score = 0

        for j, gt in enumerate(ground_truth):
            if j in matched_gt:
                continue
            gt_title = gt.title.lower().strip()
            gt_desc = gt.description.lower().strip()[:200]

            # Multi-signal matching: title + description + severity
            score = 0.0

            # Title word overlap (strongest signal)
            f_words = set(f_title.split())
            gt_words = set(gt_title.split())
            if f_words and gt_words:
                title_overlap = len(f_words & gt_words) / max(len(f_words | gt_words), 1)
                score += title_overlap * 0.5

            # Description word overlap
            if f_desc and gt_desc:
                f_desc_words = set(f_desc.split())
                gt_desc_words = set(gt_desc.split())
                if f_desc_words and gt_desc_words:
                    desc_overlap = len(f_desc_words & gt_desc_words) / max(len(f_desc_words | gt_desc_words), 1)
                    score += desc_overlap * 0.5

            # Severity match bonus
            f_sev = f.get("severity", "").lower()
            gt_sev = gt.severity.lower()
            if f_sev and gt_sev and f_sev == gt_sev:
                score += 0.1

            # Category match bonus (if both have categories)
            f_cat = f.get("category", "").lower()
            gt_cat = gt.category.lower()
            if f_cat and gt_cat and f_cat == gt_cat:
                score += 0.1

            # Function name match bonus (strong signal)
            f_lower = (f.get("title", "") + " " + f.get("description", "")).lower()
            gt_lower = (gt.title + " " + gt.description).lower()
            # Check if any function names from description appear in finding
            import re
            gt_funcs = set(re.findall(r'(\w+)\(', gt_lower))
            f_funcs = set(re.findall(r'(\w+)\(', f_lower))
            if gt_funcs and f_funcs:
                func_overlap = len(gt_funcs & f_funcs) / max(len(gt_funcs), 1)
                score += func_overlap * 0.3

            if score > best_score and score >= 0.15:
                best_score = score
                best_match = j

        if best_match is not None:
            matched_gt.add(best_match)
            matched_findings.append({"agent": f, "truth": ground_truth[best_match], "score": best_score})
        else:
            extra_findings.append(f)

    tp = len(matched_gt)
    fp = len(extra_findings)
    fn = len(ground_truth) - tp
    detection_rate = tp / max(len(ground_truth), 1)
    precision = tp / max(tp + fp, 1)
    f1 = 2 * precision * detection_rate / max(precision + detection_rate, 0.001)

    missed = [gt for j, gt in enumerate(ground_truth) if j not in matched_gt]

    return {
        "jaccard": round(jaccard, 4),
        "detection_rate": round(detection_rate, 4),
        "precision": round(precision, 4),
        "f1_score": round(f1, 4),
        "n_expected": len(ground_truth),
        "n_found": len(agent_findings),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "matched": matched_findings,
        "missed": missed,
        "extra": extra_findings,
    }


# ─── World ──────────────────────────────────────────────────────────

@dataclass
class BitsecState:
    project: Project | None = None
    step: int = 0
    max_steps: int = 5
    findings: list[dict] = field(default_factory=list)
    files_analyzed: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    latency_ms: int = 0
    terminal: bool = False


class BitsecWorld:
    """CGE world for Bitsec vulnerability detection.

    Uses actual Jaccard scoring from bitsec/validator/reward.py.
    Uses ScaBench curated dataset as ground truth.
    """

    def __init__(self, projects: list[Project] | None = None):
        self.projects = projects or load_scabench_dataset()
        self._rng = random.Random()

    def reset(self, *, instance_id: str = "", seed: int = 0) -> BitsecState:
        self._rng = random.Random(seed)
        project = self._rng.choice(self.projects)
        return BitsecState(project=project)

    def observe(self, state: BitsecState) -> dict:
        if not state.project:
            return {"error": "no project"}
        return {
            "project_id": state.project.project_id,
            "name": state.project.name,
            "platform": state.project.platform,
            "repo_url": state.project.repo_url,
            "n_vulnerabilities": len(state.project.vulnerabilities),
            "severity_dist": self._severity_dist(state.project),
            "step": state.step,
            "findings_so_far": len(state.findings),
        }

    def actions(self, state: BitsecState) -> tuple:
        if state.terminal:
            return ()
        return (
            {"kind": "analyze_code", "payload": {"strategy": "per_file"}, "estimated_cost": 0.005},
            {"kind": "analyze_code", "payload": {"strategy": "cross_file"}, "estimated_cost": 0.012},
            {"kind": "commit_findings", "payload": {}, "estimated_cost": 0.0},
        )

    def apply(self, state: BitsecState, action: dict, result: dict) -> BitsecState:
        state.step += 1
        state.cost_usd += action.get("estimated_cost", 0)
        state.latency_ms += result.get("wall_ms", 0)
        if action["kind"] == "analyze_code":
            state.findings.extend(result.get("findings", []))
            state.files_analyzed.extend(result.get("files_analyzed", []))
        elif action["kind"] == "commit_findings":
            state.terminal = True
        if state.step >= state.max_steps:
            state.terminal = True
        return state

    def terminal(self, state: BitsecState) -> bool:
        return state.terminal

    def score(self, state: BitsecState) -> dict:
        """Score using actual Bitsec Jaccard methodology."""
        if not state.project:
            return {"jaccard": 0, "detection_rate": 0, "f1_score": 0,
                    "cash_cost": state.cost_usd, "wall_latency_ms": state.latency_ms}

        return score_vulnerabilities(state.findings, state.project.vulnerabilities)

    def _severity_dist(self, project: Project) -> dict:
        dist = {}
        for v in project.vulnerabilities:
            dist[v.severity] = dist.get(v.severity, 0) + 1
        return dist
