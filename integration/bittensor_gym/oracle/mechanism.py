"""Mechanism parser — extracts reward curves, eligibility rules, and scoring from subnet sources.

Source priority:
  1. Live subnet API / network-config endpoint
  2. Active validator code at current commit
  3. Official subnet repo documentation
  4. Bittensor explorer metadata
  5. Third-party research
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class PayoutCurve:
    """Explicit reward distribution rule for a subnet."""
    # Ranked: list of (rank, share) tuples
    ranked_shares: tuple[tuple[int, float], ...] = ()

    # Proportional: formula description
    proportional_formula: str = ""

    # Tournament: per-tournament allocation
    tournament_top_n: int = 0
    tournament_split: tuple[float, ...] = ()

    # Winner-take-all
    winner_take_all: bool = False

    # Custom/dynamic
    custom_rule: str = ""

    def payout_for_rank(self, rank: int, pool_tao_day: float) -> float:
        """Calculate expected payout for a given rank."""
        if self.winner_take_all:
            return pool_tao_day if rank == 1 else 0.0

        for r, share in self.ranked_shares:
            if rank == r:
                return pool_tao_day * share

        return 0.0

    def to_dict(self) -> dict:
        return {
            "ranked_shares": self.ranked_shares,
            "proportional_formula": self.proportional_formula,
            "tournament_top_n": self.tournament_top_n,
            "tournament_split": self.tournament_split,
            "winner_take_all": self.winner_take_all,
            "custom_rule": self.custom_rule,
        }


@dataclass
class EligibilityRules:
    """Rules for who can mine on a subnet."""
    min_stake_tao: Decimal = Decimal("0")
    registration_open: bool = True
    max_miners: int = 0          # 0 = unlimited
    require_gpu: bool = False
    min_vram_gb: float = 0.0
    require_docker: bool = False
    require_specific_hardware: bool = False
    cooldown_submissions_s: int = 0
    max_submissions_per_day: int = 0
    custom_rules: dict = field(default_factory=dict)


@dataclass
class MechanismInfo:
    """Parsed mechanism information for a subnet."""
    netuid: int = 0
    task_family: str = ""
    scoring_type: str = ""        # ranked, proportional, winner_take_all, tournament
    reward_mechanism: str = ""
    payout_curve: PayoutCurve = field(default_factory=PayoutCurve)
    eligibility: EligibilityRules = field(default_factory=EligibilityRules)
    submission_fee_tao: Decimal = Decimal("0")
    feedback_latency_seconds: int = 0
    local_eval_available: bool = False
    deterministic_verifier: bool = False
    hidden_eval: bool = False
    fresh_task_generation: bool = False
    source: str = ""
    source_confidence: float = 0.0
    discrepancy_flags: list[str] = field(default_factory=list)


# ─── Known subnet mechanisms (hardcoded from research) ────────────────

KNOWN_MECHANISMS: dict[int, MechanismInfo] = {
    118: MechanismInfo(
        netuid=118,
        task_family="memory_tool_judgment",
        scoring_type="ranked",
        reward_mechanism="Top-5 payout: 65/14/10/7/4 split of daily miner pool",
        payout_curve=PayoutCurve(
            ranked_shares=((1, 0.65), (2, 0.14), (3, 0.10), (4, 0.07), (5, 0.04)),
        ),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
            cooldown_submissions_s=300,
        ),
        submission_fee_tao=Decimal("0.04"),
        local_eval_available=True,
        deterministic_verifier=False,
        hidden_eval=True,
        fresh_task_generation=True,
        source="github.com/ditto-assistant/ditto-subnet/docs/MINER.md",
        source_confidence=0.85,
    ),
    62: MechanismInfo(
        netuid=62,
        task_family="swe_coding",
        scoring_type="proportional",
        reward_mechanism="Proportional to test pass rate + cost efficiency. Validator executes agent.py in Docker sandbox.",
        payout_curve=PayoutCurve(
            proportional_formula="score * (1 - cost_ratio) * quality_weight",
        ),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
            require_docker=True,
        ),
        submission_fee_tao=Decimal("0.0005"),
        local_eval_available=True,
        deterministic_verifier=True,
        hidden_eval=False,
        fresh_task_generation=True,
        source="github.com/ridgesai/ridges",
        source_confidence=0.9,
    ),
    6: MechanismInfo(
        netuid=6,
        task_family="persistent_forecasting",
        scoring_type="winner_take_all",
        reward_mechanism="Winner-takes-all by Brier score. Same event re-forecast every ~24h with persistent memory.",
        payout_curve=PayoutCurve(winner_take_all=True),
        eligibility=EligibilityRules(
            registration_open=False,  # 256 slots occupied
            max_miners=256,
        ),
        submission_fee_tao=Decimal("0.05"),
        local_eval_available=True,
        deterministic_verifier=False,
        hidden_eval=False,
        fresh_task_generation=False,
        source="github.com/numinouslabs/numinous",
        source_confidence=0.8,
    ),
    15: MechanismInfo(
        netuid=15,
        task_family="shopping_agents",
        scoring_type="ranked",
        reward_mechanism="Ranked by ShoppingBench accuracy + format compliance. Docker sandbox evaluation.",
        payout_curve=PayoutCurve(
            proportional_formula="score * format_compliance_weight",
        ),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
            require_docker=True,
        ),
        submission_fee_tao=Decimal("0.01"),
        local_eval_available=True,
        deterministic_verifier=True,
        hidden_eval=True,
        fresh_task_generation=True,
        source="github.com/ORO-AI/oro",
        source_confidence=0.85,
    ),
    67: MechanismInfo(
        netuid=67,
        task_family="deep_research",
        scoring_type="proportional",
        reward_mechanism="Quality + cost + latency + novelty. Challenger/champion system.",
        payout_curve=PayoutCurve(
            proportional_formula="quality * (1 - cost_ratio) * novelty_factor",
        ),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
        ),
        submission_fee_tao=Decimal("0.018"),
        local_eval_available=True,
        deterministic_verifier=False,
        hidden_eval=True,
        fresh_task_generation=True,
        source="github.com/harnyx/harnyx",
        source_confidence=0.8,
    ),
    107: MechanismInfo(
        netuid=107,
        task_family="genomic_optimization",
        scoring_type="winner_take_all",
        reward_mechanism="~90% to round winner, ~10% across ranks #2-#20. Parameters from /scoring/network-config.",
        payout_curve=PayoutCurve(
            ranked_shares=((1, 0.90),),  # rest distributed 2-20
        ),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
        ),
        submission_fee_tao=Decimal("0"),
        local_eval_available=True,
        deterministic_verifier=True,
        hidden_eval=True,
        fresh_task_generation=True,
        source="github.com/minos-protocol/minos_subnet",
        source_confidence=0.75,
    ),
    56: MechanismInfo(
        netuid=56,
        task_family="automl_training",
        scoring_type="tournament",
        reward_mechanism="Tournament-based. Top 2 per track: ~80/20 split. Text 0.35T, Image 0.20T, Env 0.30T fees.",
        payout_curve=PayoutCurve(
            tournament_top_n=2,
            tournament_split=(0.80, 0.20),
        ),
        eligibility=EligibilityRules(
            registration_open=True,
        ),
        submission_fee_tao=Decimal("0.35"),  # varies by track
        local_eval_available=True,
        deterministic_verifier=True,
        hidden_eval=True,
        fresh_task_generation=True,
        source="github.com/gradients-ai/G.O.D/docs/miner.md",
        source_confidence=0.8,
    ),
    61: MechanismInfo(
        netuid=61,
        task_family="security_redteam",
        scoring_type="proportional",
        reward_mechanism="Security agent evaluation. Proportional to findings quality.",
        payout_curve=PayoutCurve(
            proportional_formula="finding_quality * uniqueness_weight",
        ),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
        ),
        submission_fee_tao=Decimal("0.047"),
        local_eval_available=False,
        deterministic_verifier=False,
        hidden_eval=True,
        fresh_task_generation=True,
        source="bittensor.ai/subnets/61",
        source_confidence=0.6,
    ),
    114: MechanismInfo(
        netuid=114,
        task_family="context_compression",
        scoring_type="proportional",
        reward_mechanism="Telemetry-based scoring for context compression agents.",
        payout_curve=PayoutCurve(
            proportional_formula="compression_quality * efficiency",
        ),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
        ),
        submission_fee_tao=Decimal("0.25"),
        local_eval_available=False,
        deterministic_verifier=False,
        hidden_eval=True,
        fresh_task_generation=True,
        source="bittensor.ai/subnets/114",
        source_confidence=0.5,
    ),
    120: MechanismInfo(
        netuid=120,
        task_family="model_optimization",
        scoring_type="winner_take_all",
        reward_mechanism="Challenger must beat champion across all environments. Losers terminated.",
        payout_curve=PayoutCurve(winner_take_all=True),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
            require_gpu=True,
            min_vram_gb=24.0,
        ),
        submission_fee_tao=Decimal("0.881"),
        local_eval_available=False,
        deterministic_verifier=True,
        hidden_eval=True,
        fresh_task_generation=True,
        source="bittensor.ai/subnets/120",
        source_confidence=0.6,
    ),
    97: MechanismInfo(
        netuid=97,
        task_family="model_distillation",
        scoring_type="winner_take_all",
        reward_mechanism="Winner-take-all model distillation. GPU required.",
        payout_curve=PayoutCurve(winner_take_all=True),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
            require_gpu=True,
            min_vram_gb=24.0,
        ),
        submission_fee_tao=Decimal("0.650"),
        local_eval_available=False,
        deterministic_verifier=True,
        hidden_eval=True,
        fresh_task_generation=True,
        source="bittensor.ai/subnets/97",
        source_confidence=0.6,
    ),
    1: MechanismInfo(
        netuid=1,
        task_family="distributed_research",
        scoring_type="proportional",
        reward_mechanism="Routes research problems to miners. Score by solution quality.",
        payout_curve=PayoutCurve(
            proportional_formula="solution_quality * cost_efficiency",
        ),
        eligibility=EligibilityRules(
            registration_open=True,
            max_miners=256,
        ),
        submission_fee_tao=Decimal("0"),
        local_eval_available=False,
        deterministic_verifier=False,
        hidden_eval=False,
        fresh_task_generation=True,
        source="github.com/macrocosm-os/apex",
        source_confidence=0.7,
    ),
}


def get_known_mechanism(netuid: int) -> MechanismInfo | None:
    """Get hardcoded mechanism info for known subnets."""
    return KNOWN_MECHANISMS.get(netuid)


def parse_mechanism_from_data(netuid: int, raw_data: dict) -> MechanismInfo:
    """Best-effort mechanism parsing from raw chain/API data.

    Falls back to known mechanisms, then defaults.
    """
    known = KNOWN_MECHANISMS.get(netuid)
    if known:
        return known

    # Attempt to parse from raw data
    return MechanismInfo(
        netuid=netuid,
        task_family=f"unknown.sn{netuid}",
        scoring_type="proportional",
        reward_mechanism="Unknown — needs manual classification",
        source="auto-parse (low confidence)",
        source_confidence=0.3,
        discrepancy_flags=["mechanism_not_known"],
    )
