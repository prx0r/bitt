"""Bitsec Benchmark — uses actual Bitsec Jaccard scoring methodology.

From bitsec/validator/reward.py:
  Jaccard = intersection(categories) / union(categories)
  + LLM-based 1-5 scoring for detailed matching
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoringResult:
    project_id: str = ""
    total_expected: int = 0
    total_found: int = 0
    true_positives: int = 0
    false_negatives: int = 0
    false_positives: int = 0
    jaccard: float = 0.0
    detection_rate: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    matched_findings: list[dict] = field(default_factory=list)
    missed_findings: list[dict] = field(default_factory=list)
    extra_findings: list[dict] = field(default_factory=list)


def jaccard_score(agent_categories: list[str], truth_categories: list[str]) -> float:
    """Bitsec's actual scoring: intersection/union of categories."""
    if not agent_categories and not truth_categories:
        return 1.0
    if not agent_categories or not truth_categories:
        return 0.0
    set_agent = set(c.lower().strip() for c in agent_categories)
    set_truth = set(c.lower().strip() for c in truth_categories)
    intersection = set_agent & set_truth
    union = set_agent | set_truth
    return len(intersection) / len(union) if union else 1.0


def score_findings(findings: list[dict], ground_truth: list, project_id: str = "") -> ScoringResult:
    """Score using title-based matching (ground truth has no categories)."""
    result = ScoringResult(project_id=project_id)
    result.total_expected = len(ground_truth)
    result.total_found = len(findings)

    # Title-based matching (ground truth has titles, not categories)
    matched_gt = set()
    for f in findings:
        f_title = f.get("title", "").lower()
        best_match = None
        best_score = 0

        for j, gt in enumerate(ground_truth):
            if j in matched_gt:
                continue
            gt_title = gt.title.lower()
            # Simple word overlap
            f_words = set(f_title.split())
            gt_words = set(gt_title.split())
            if f_words and gt_words:
                overlap = len(f_words & gt_words) / max(len(f_words | gt_words), 1)
                if overlap > best_score and overlap >= 0.2:
                    best_score = overlap
                    best_match = j

        if best_match is not None:
            result.true_positives += 1
            matched_gt.add(best_match)
            result.matched_findings.append({"agent": f, "truth": ground_truth[best_match], "score": best_score})
        else:
            result.false_positives += 1
            result.extra_findings.append(f)

    result.false_negatives = len(ground_truth) - len(matched_gt)
    result.missed_findings = [gt for j, gt in enumerate(ground_truth) if j not in matched_gt]

    # Jaccard on titles
    agent_titles = set(f.get("title", "").lower() for f in findings)
    truth_titles = set(v.title.lower() for v in ground_truth)
    intersection = agent_titles & truth_titles
    union = agent_titles | truth_titles
    result.jaccard = len(intersection) / len(union) if union else 0.0

    result.detection_rate = result.true_positives / max(result.total_expected, 1)
    result.precision = result.true_positives / max(result.true_positives + result.false_positives, 1)
    result.recall = result.detection_rate
    result.f1_score = 2 * result.precision * result.recall / max(result.precision + result.recall, 0.001)

    return result


def format_report(result: ScoringResult) -> str:
    lines = [
        f"Project: {result.project_id}",
        f"Jaccard: {result.jaccard:.1%}",
        f"Detection Rate: {result.detection_rate:.1%} ({result.true_positives}/{result.total_expected})",
        f"Precision: {result.precision:.1%}",
        f"F1: {result.f1_score:.3f}",
    ]
    return "\n".join(lines)
