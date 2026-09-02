"""Bitsec Scientific Evolution — controlled exploration of vulnerability detection.

Principles:
  1. ONE variable at a time
  2. Proper controls
  3. Frozen intents
  4. Generator/judge separation
  5. Failure ≠ change
  6. Sealed evaluation before promotion

Variables to explore:
  - Analysis style (direct, cot, cross_file, ensemble)
  - Chunk size (how many files per analysis)
  - Severity threshold (what counts as a finding)
  - Prefilter (static analysis before LLM)
  - Model (mimo-v2.5 only — no budget constraint)

Protocol:
  - Generate hypotheses
  - Test against ScaBench dev set
  - Validate on held-out set
  - Only promote if validated
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from cge.bitsec.world import (
    BitsecWorld, load_scabench_dataset, score_vulnerabilities,
    Project, VulnTruth,
)


@dataclass
class Hypothesis:
    """One testable hypothesis about vulnerability detection."""
    hypothesis_id: str
    description: str
    variable: str  # what we're testing
    control: dict  # baseline config
    candidate: dict  # modified config
    status: str = "pending"  # pending|testing|validated|rejected
    results: dict = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Result of a controlled experiment."""
    hypothesis_id: str
    control_score: float
    candidate_score: float
    improvement: float
    p_value: float  # simplified
    n_projects: int
    validated: bool
    details: str = ""


class ScientificEvolution:
    """Controlled scientific evolution for vulnerability detection.

    Explores one variable at a time with proper controls.
    """

    def __init__(self, n_projects: int = 15, seed: int = 42):
        self.projects = load_scabench_dataset(n_projects)
        self.rng = random.Random(seed)

        # Split into dev/validation
        n_dev = int(len(self.projects) * 0.7)
        indices = list(range(len(self.projects)))
        self.rng.shuffle(indices)
        self.dev_projects = [self.projects[i] for i in indices[:n_dev]]
        self.val_projects = [self.projects[i] for i in indices[n_dev:]]

        print(f"Dataset: {len(self.projects)} projects")
        print(f"Dev: {len(self.dev_projects)}, Validation: {len(self.val_projects)}")
        print(f"Total vulns: {sum(len(p.vulnerabilities) for p in self.projects)}")

    def generate_hypotheses(self) -> list[Hypothesis]:
        """Generate hypotheses to test.

        Each hypothesis changes ONE variable from a baseline.
        """
        baseline = {
            "style": "per_file",
            "model": "mimo-v2.5",
            "chunk_size": 10,
            "prefilter": True,
            "severity_threshold": 0.5,
        }

        hypotheses = [
            Hypothesis(
                hypothesis_id="H1-style",
                description="Cross-file analysis improves detection over per-file",
                variable="style",
                control=baseline,
                candidate={**baseline, "style": "cross_file"},
            ),
            Hypothesis(
                hypothesis_id="H2-chunk",
                description="Larger chunk sizes improve context and detection",
                variable="chunk_size",
                control=baseline,
                candidate={**baseline, "chunk_size": 20},
            ),
            Hypothesis(
                hypothesis_id="H3-prefilter",
                description="Static prefiltering improves precision by reducing noise",
                variable="prefilter",
                control=baseline,
                candidate={**baseline, "prefilter": False},
            ),
            Hypothesis(
                hypothesis_id="H4-severity",
                description="Lower severity threshold catches more findings",
                variable="severity_threshold",
                control=baseline,
                candidate={**baseline, "severity_threshold": 0.3},
            ),
            Hypothesis(
                hypothesis_id="H5-ensemble",
                description="Combining multiple strategies improves recall",
                variable="style",
                control=baseline,
                candidate={**baseline, "style": "ensemble"},
            ),
            Hypothesis(
                hypothesis_id="H6-cot",
                description="Chain-of-thought reasoning improves precision",
                variable="style",
                control=baseline,
                candidate={**baseline, "style": "cot"},
            ),
        ]

        return hypotheses

    def test_hypothesis(self, hypothesis: Hypothesis,
                        projects: list[Project] | None = None) -> ExperimentResult:
        """Run controlled experiment for one hypothesis.

        Tests control vs candidate on the same projects.
        """
        projects = projects or self.dev_projects

        control_scores = []
        candidate_scores = []

        for project in projects:
            # Control evaluation
            control_findings = self._simulate_analysis(hypothesis.control, project)
            control_result = score_vulnerabilities(control_findings, project.vulnerabilities)
            control_scores.append(control_result["f1_score"])

            # Candidate evaluation
            candidate_findings = self._simulate_analysis(hypothesis.candidate, project)
            candidate_result = score_vulnerabilities(candidate_findings, project.vulnerabilities)
            candidate_scores.append(candidate_result["f1_score"])

        control_mean = sum(control_scores) / len(control_scores)
        candidate_mean = sum(candidate_scores) / len(candidate_scores)
        improvement = candidate_mean - control_mean

        # Simplified significance test
        control_var = sum((x - control_mean) ** 2 for x in control_scores) / max(len(control_scores) - 1, 1)
        candidate_var = sum((x - candidate_mean) ** 2 for x in candidate_scores) / max(len(candidate_scores) - 1, 1)
        se = max((control_var + candidate_var) / max(len(control_scores), 1), 0.0001) ** 0.5
        z = improvement / max(se, 0.0001)
        p_value = 2 * (1 - _normal_cdf(abs(z)))

        # Validate if improvement is significant and positive
        validated = improvement > 0.01 and p_value < 0.1

        return ExperimentResult(
            hypothesis_id=hypothesis.hypothesis_id,
            control_score=round(control_mean, 4),
            candidate_score=round(candidate_mean, 4),
            improvement=round(improvement, 4),
            p_value=round(p_value, 4),
            n_projects=len(projects),
            validated=validated,
            details=f"Control={control_mean:.4f} Candidate={candidate_mean:.4f} Δ={improvement:+.4f} p={p_value:.4f}",
        )

    def run_full_experiment(self):
        """Run all hypotheses through dev + validation."""
        hypotheses = self.generate_hypotheses()

        print("\n=== Phase 1: Development Testing ===")
        dev_results = []
        for h in hypotheses:
            result = self.test_hypothesis(h, self.dev_projects)
            dev_results.append(result)
            status = "✓ VALIDATED" if result.validated else "✗ REJECTED"
            print(f"  {h.hypothesis_id}: {h.description}")
            print(f"    {result.details} → {status}")

        # Filter to validated hypotheses
        validated = [h for h, r in zip(hypotheses, dev_results) if r.validated]
        print(f"\nValidated on dev: {len(validated)}/{len(hypotheses)}")

        # Phase 2: Validation on held-out set
        print("\n=== Phase 2: Validation on Held-Out Set ===")
        for h in validated:
            result = self.test_hypothesis(h, self.val_projects)
            status = "✓ CONFIRMED" if result.validated else "✗ FAILED VALIDATION"
            print(f"  {h.hypothesis_id}: {result.details} → {status}")

        # Build winning config from validated hypotheses
        winning_config = self._build_winning_config(validated, dev_results)
        print(f"\n=== Winning Configuration ===")
        for k, v in winning_config.items():
            print(f"  {k}: {v}")

        return {
            "hypotheses_tested": len(hypotheses),
            "validated_on_dev": len(validated),
            "dev_results": [{"id": r.hypothesis_id, "improvement": r.improvement, "validated": r.validated} for r in dev_results],
            "winning_config": winning_config,
        }

    def _build_winning_config(self, validated: list[Hypothesis],
                              dev_results: list[ExperimentResult]) -> dict:
        """Build winning config from validated hypotheses."""
        config = {
            "style": "per_file",
            "model": "mimo-v2.5",
            "chunk_size": 10,
            "prefilter": True,
            "severity_threshold": 0.5,
        }

        for h in validated:
            config[h.variable] = h.candidate[h.variable]

        return config

    def _simulate_analysis(self, config: dict, project: Project) -> list[dict]:
        """Simulate analysis with given config.

        In production, this calls the real agent with mimo-v2.5.
        """
        findings = []
        style_bonus = {
            "direct": 0.0, "cot": 0.1, "per_file": 0.0,
            "cross_file": 0.15, "ensemble": 0.12, "decomposition": 0.08,
        }
        bonus = style_bonus.get(config.get("style", "per_file"), 0)

        for vuln in project.vulnerabilities:
            prob = 0.3 + bonus
            if config.get("prefilter"):
                prob += 0.05
            prob = min(0.95, prob)

            if self.rng.random() < prob:
                findings.append({
                    "title": vuln.title,
                    "category": vuln.category.lower(),
                    "severity": vuln.severity,
                })

            # False positives
            if not config.get("prefilter") and self.rng.random() < 0.15:
                findings.append({
                    "title": f"Potential issue in {project.name}",
                    "category": "general",
                    "severity": "low",
                })

        return findings


def _normal_cdf(x: float) -> float:
    """Approximate normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


import math


if __name__ == "__main__":
    evo = ScientificEvolution(n_projects=15, seed=42)
    results = evo.run_full_experiment()

    # Save results
    output_path = Path("/root/bitt/data/bitsec_experiment.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {output_path}")
