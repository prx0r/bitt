"""Security CGE Genome — compositional mutation space for security workers.

Produces LearningProposal contracts from failure analysis.
Each genome is a compositional security process configuration.

CGE proposes mutations, CG evaluates via sealed paired experiments.
Only CG produces ExperimentResult and PromotionReceipt contracts.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lab.contracts import LearningProposal, Finding, FindingTier


# ─── Genome Definition ───────────────────────────────────────────────

@dataclass
class ProcessGenome:
    """A compositional security process configuration.

    CGE mutates individual genes. CG evaluates whether the new genome
    improves performance on sealed tasks.
    """
    genome_id: str = "default"

    # Process selection
    process: str = "moltwork-default"

    # Static analysis tools
    tools_slither: bool = True
    tools_semgrep: bool = True
    tools_codeql: bool = False
    tools_mythril: bool = False

    # Audit skills
    skill_entry_point_analyzer: bool = True
    skill_fp_check: bool = True
    skill_audit_context_building: bool = True
    skill_differential_review: bool = False
    skill_variant_analysis: bool = False
    skill_property_testing: bool = False
    property_tester: str = ""

    # Model routing
    scout_model: str = "meta/llama-3.1-8b-instruct-fp8"
    strategist_model: str = "meta/llama-3.3-70b-instruct-fp8-fast"
    verifier_model: str = "meta/llama-3.3-70b-instruct-fp8-fast"

    # Context retrieval
    context_retrieval: bool = True
    retrieval_corpus: str = "sec-context"
    max_context_tokens: int = 8000

    # Graph-driven analysis
    graph_views: list[str] = field(default_factory=lambda: ["authorization", "value_flow"])
    sweep_vs_intuition: str = "both"

    # Budget
    max_findings: int = 20
    max_model_calls: int = 10
    budget_usd: float = 0.10

    # Evolution metadata
    parent_id: str = ""
    generation: int = 0
    fitness: float = 0.0

    def to_process_config(self) -> dict:
        """Convert genome to a process configuration for WorkerKit."""
        return {
            "process": self.process,
            "tools": {
                "slither": self.tools_slither,
                "semgrep": self.tools_semgrep,
                "codeql": self.tools_codeql,
                "mythril": self.tools_mythril,
            },
            "skills": {
                "entry_point_analyzer": self.skill_entry_point_analyzer,
                "fp_check": self.skill_fp_check,
                "audit_context_building": self.skill_audit_context_building,
                "differential_review": self.skill_differential_review,
                "variant_analysis": self.skill_variant_analysis,
                "property_testing": self.skill_property_testing,
                "property_tester": self.property_tester,
            },
            "models": {
                "scout": self.scout_model,
                "strategist": self.strategist_model,
                "verifier": self.verifier_model,
            },
            "context": {
                "retrieval": self.context_retrieval,
                "corpus": self.retrieval_corpus,
                "max_tokens": self.max_context_tokens,
            },
            "graph": {
                "views": self.graph_views,
                "sweep_intuition": self.sweep_vs_intuition,
            },
            "budget": {
                "max_findings": self.max_findings,
                "max_model_calls": self.max_model_calls,
                "budget_usd": self.budget_usd,
            },
        }

    def to_learning_proposal(
        self,
        source_run_ids: list[str],
        hypothesis: str = "",
    ) -> LearningProposal:
        """Convert genome to a LearningProposal contract.

        This is how CGE proposes changes: as frozen contracts that CG evaluates.
        """
        return LearningProposal(
            proposal_id=f"proposal-{self.genome_id}",
            source_run_ids=source_run_ids,
            target=f"security-01/v{self.generation + 1}",
            hypothesis=hypothesis or f"Genome {self.genome_id} improves over parent {self.parent_id}",
            patch=self.to_process_config(),
            confidence=self.fitness,
            status="proposed",
        )


# ─── Genome Space ────────────────────────────────────────────────────

GENE_RANGES = {
    "process": ["moltwork-default", "hound", "cloudflare-audit", "tob-stack"],
    "tools_slither": [True, False],
    "tools_semgrep": [True, False],
    "tools_codeql": [True, False],
    "tools_mythril": [True, False],
    "skill_entry_point_analyzer": [True, False],
    "skill_fp_check": [True, False],
    "skill_audit_context_building": [True, False],
    "skill_differential_review": [True, False],
    "skill_variant_analysis": [True, False],
    "skill_property_testing": [True, False],
    "property_tester": ["", "echidna", "medusa"],
    "scout_model": [
        "meta/llama-3.1-8b-instruct-fp8",
        "qwen/qwen3-30b-a3b-fp8",
    ],
    "strategist_model": [
        "meta/llama-3.3-70b-instruct-fp8-fast",
        "deepseek-ai/deepseek-v4-flash",
    ],
    "verifier_model": [
        "meta/llama-3.3-70b-instruct-fp8-fast",
        "mistralai/mistral-small-3.1-24b-instruct",
    ],
    "context_retrieval": [True, False],
    "retrieval_corpus": ["sec-context", "arc_pi_taxonomy", ""],
    "max_context_tokens": [4000, 8000, 16000],
    "sweep_vs_intuition": ["sweep", "intuition", "both"],
    "max_findings": [10, 20, 30],
    "max_model_calls": [5, 10, 20],
    "budget_usd": [0.05, 0.10, 0.20],
}


def random_genome(rng: random.Random, genome_id: str = "") -> ProcessGenome:
    kwargs = {"genome_id": genome_id or f"rand-{rng.randint(0, 99999)}"}
    for gene, values in GENE_RANGES.items():
        kwargs[gene] = rng.choice(values)
    return ProcessGenome(**kwargs)


def mutate_genome(
    parent: ProcessGenome,
    rng: random.Random,
    mutation_rate: float = 0.2,
    genome_id: str = "",
) -> ProcessGenome:
    child = ProcessGenome(
        genome_id=genome_id or f"mut-{parent.genome_id}-{rng.randint(0, 999)}",
        parent_id=parent.genome_id,
        generation=parent.generation + 1,
    )
    for gene, values in GENE_RANGES.items():
        parent_val = getattr(parent, gene)
        if rng.random() < mutation_rate:
            candidates = [v for v in values if v != parent_val]
            setattr(child, gene, rng.choice(candidates) if candidates else parent_val)
        else:
            setattr(child, gene, parent_val)
    return child


def crossover_genomes(
    parent_a: ProcessGenome,
    parent_b: ProcessGenome,
    rng: random.Random,
    genome_id: str = "",
) -> ProcessGenome:
    child = ProcessGenome(
        genome_id=genome_id or f"cross-{parent_a.genome_id}-{parent_b.genome_id}",
        parent_id=parent_a.genome_id,
        generation=max(parent_a.generation, parent_b.generation) + 1,
    )
    for gene in GENE_RANGES:
        if rng.random() < 0.5:
            setattr(child, gene, getattr(parent_a, gene))
        else:
            setattr(child, gene, getattr(parent_b, gene))
    return child


# ─── Experiment Arms (A/B/C/D from email) ────────────────────────────

EXPERIMENT_ARMS = {
    "A": ProcessGenome(
        genome_id="arm-A-moltwork-default",
        process="moltwork-default",
    ),
    "B": ProcessGenome(
        genome_id="arm-B-hound",
        process="hound",
        graph_views=["authorization", "value_flow"],
        sweep_vs_intuition="both",
    ),
    "C": ProcessGenome(
        genome_id="arm-C-cloudflare-audit",
        process="cloudflare-audit",
        skill_audit_context_building=True,
    ),
    "D": ProcessGenome(
        genome_id="arm-D-tob-stack",
        process="tob-stack",
        tools_codeql=True,
        skill_differential_review=True,
        skill_variant_analysis=True,
        skill_property_testing=True,
        property_tester="echidna",
    ),
}
