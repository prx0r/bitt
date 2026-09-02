"""Opportunity scorer — combines all signals into actionable recommendations.

Takes: chain data + mechanism + reward analysis + difficulty + lab value
Produces: opportunity score + recommendation state
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .snapshot import BittensorOpportunitySnapshot
from .mechanism import MechanismInfo
from .reward_analyzer import RewardAnalysis
from .difficulty import DifficultyBreakdown, LabValueBreakdown


# ─── Recommendation states ───────────────────────────────────────────

VALID_RECOMMENDATIONS = {
    "IGNORE",             # not worth any attention
    "WATCH",              # interesting but not ready
    "CLONE_AND_REPLAY",   # clone repo, run local evaluation
    "OFFLINE_TRAIN",      # actively training via CGE/Hydra
    "SHADOW",             # shadow-scoring alongside live miners
    "REGISTER_SMALL",     # register with bounded capital
    "LIVE_COMPETE",       # actively competing
    "DEFEND_POSITION",    # maintaining earned position
    "EXIT",               # leave subnet
}


@dataclass
class OpportunityAssessment:
    """Final opportunity assessment for a subnet."""
    netuid: int
    name: str

    # Component scores (all 0-1)
    economic_score: float = 0.0
    lab_value: float = 0.0
    difficulty: float = 0.0
    capital_risk: float = 0.0
    confidence: float = 0.0

    # Economic metrics
    expected_tao_day: float = 0.0
    p_any_reward: float = 0.0
    p_top5: float = 0.0
    p_champion: float = 0.0

    # Recommendation
    recommendation: str = "WATCH"
    recommendation_reason: str = ""

    # Component breakdowns (for the daily report)
    difficulty_breakdown: dict = field(default_factory=dict)
    lab_value_breakdown: dict = field(default_factory=dict)

    # Priority ranking (across all subnets)
    priority_rank: int = 0
    priority_score: float = 0.0  # composite for ranking


def score_opportunity(
    snapshot: BittensorOpportunitySnapshot,
    mechanism: MechanismInfo,
    reward: RewardAnalysis,
    difficulty_score: float,
    difficulty_breakdown: DifficultyBreakdown,
    lab_value_score: float,
    lab_value_breakdown: LabValueBreakdown,
    our_sealed_score: float | None = None,
    current_miner_count: int = 0,
) -> OpportunityAssessment:
    """Produce final opportunity assessment.

    This is the core scoring function. It combines:
    - economic attractiveness (pool size, our probability of earning)
    - training value (how useful for Moltwork evolution)
    - difficulty (how hard to actually earn)
    - capital risk (how much TAO at stake)
    - confidence (how much we trust our data)
    """
    a = OpportunityAssessment(
        netuid=snapshot.netuid,
        name=snapshot.name,
    )

    # ─── Economic score ─────────────────────────────────────────────
    # Combine pool size, attainable reward, and probability
    pool_factor = min(1.0, reward.miner_pool_tao_equiv_day / 100.0)  # 100 TAO/day = max
    attainable_factor = min(1.0, reward.expected_tao_day / 10.0)  # 10 TAO/day = max
    prob_factor = reward.p_top5  # probability of being in top 5

    a.economic_score = (
        0.35 * pool_factor
        + 0.35 * attainable_factor
        + 0.30 * prob_factor
    )

    # ─── Lab value (already calculated) ─────────────────────────────
    a.lab_value = lab_value_score

    # ─── Difficulty (invert for scoring — lower difficulty = higher score) ──
    a.difficulty = 1.0 - difficulty_score

    # ─── Capital risk ───────────────────────────────────────────────
    from ..config import SUBNETS, tao_to_usd
    subnet_cfg = SUBNETS.get(snapshot.netuid)
    if subnet_cfg:
        burn_usd = tao_to_usd(float(snapshot.registration_burn_tao))
        a.capital_risk = min(1.0, burn_usd / 500.0)  # $500 = max risk
    else:
        a.capital_risk = 0.5

    # ─── Confidence ─────────────────────────────────────────────────
    a.confidence = snapshot.source_confidence

    # ─── Economic metrics ──────────────────────────────────────────
    a.expected_tao_day = reward.expected_tao_day
    a.p_any_reward = reward.p_any_reward
    a.p_top5 = reward.p_top5
    a.p_champion = reward.p_champion

    # ─── Breakdowns ────────────────────────────────────────────────
    a.difficulty_breakdown = {
        "competitive_depth": difficulty_breakdown.competitive_depth,
        "score_gap_to_paid": difficulty_breakdown.score_gap_to_paid,
        "reward_concentration": difficulty_breakdown.reward_concentration,
        "domain_specialization": difficulty_breakdown.domain_specialization,
        "compute_barrier": difficulty_breakdown.compute_barrier,
        "entry_risk": difficulty_breakdown.entry_risk,
        "feedback_latency": difficulty_breakdown.feedback_latency,
        "benchmark_uncertainty": difficulty_breakdown.benchmark_uncertainty,
        "protocol_instability": difficulty_breakdown.protocol_instability,
    }
    a.lab_value_breakdown = {
        "verifier_strength": lab_value_breakdown.verifier_strength,
        "replayability": lab_value_breakdown.replayability,
        "iteration_frequency": lab_value_breakdown.iteration_frequency,
        "feedback_richness": lab_value_breakdown.feedback_richness,
        "skill_transferability": lab_value_breakdown.skill_transferability,
        "artifact_reusability": lab_value_breakdown.artifact_reusability,
        "curriculum_generatability": lab_value_breakdown.curriculum_generatability,
        "economic_reality": lab_value_breakdown.economic_reality,
    }

    # ─── Priority score (for ranking across subnets) ────────────────
    # Balance economic value with training value
    a.priority_score = (
        0.30 * a.economic_score
        + 0.35 * a.lab_value
        + 0.15 * a.difficulty
        + 0.10 * (1.0 - a.capital_risk)
        + 0.10 * a.confidence
    )

    # ─── Recommendation ────────────────────────────────────────────
    a.recommendation, a.recommendation_reason = _decide_recommendation(
        snapshot=snapshot,
        mechanism=mechanism,
        reward=reward,
        difficulty=difficulty_score,
        lab_value=lab_value_score,
        our_sealed_score=our_sealed_score,
        current_miner_count=current_miner_count,
    )

    return a


def _decide_recommendation(
    snapshot: BittensorOpportunitySnapshot,
    mechanism: MechanismInfo,
    reward: RewardAnalysis,
    difficulty: float,
    lab_value: float,
    our_sealed_score: float | None,
    current_miner_count: int,
) -> tuple[str, str]:
    """Decide recommendation state based on all signals."""

    netuid = snapshot.netuid

    # ─── IGNORE: low lab value AND low economic value ──────────────
    if lab_value < 0.3 and reward.expected_tao_day < 0.1:
        return "IGNORE", f"Low lab value ({lab_value:.2f}) and negligible reward ({reward.expected_tao_day:.2f} TAO/day)"

    # ─── High registration cost gate ──────────────────────────────
    burn = float(snapshot.registration_burn_tao)
    if burn > 0.25:
        # Expensive: need high confidence before spending
        if snapshot.source_confidence < 0.95:
            return "CLONE_AND_REPLAY", f"High burn ({burn:.3f} TAO) but mechanism confidence only {snapshot.source_confidence:.2f}"
        if our_sealed_score is None:
            return "OFFLINE_TRAIN", f"High burn ({burn:.3f} TAO) — need sealed evaluation before registration"
        # Have sealed score — check if competitive
        if reward.p_top5 > 0.3:
            return "REGISTER_SMALL", f"Sealed score competitive, P(top5)={reward.p_top5:.2f}"
        else:
            return "OFFLINE_TRAIN", f"Sealed score not yet competitive, P(top5)={reward.p_top5:.2f}"

    # ─── Low/free registration ─────────────────────────────────────
    if burn <= 0.01:
        if lab_value > 0.7 and our_sealed_score is None:
            return "CLONE_AND_REPLAY", f"High lab value ({lab_value:.2f}), free entry — clone and establish baseline"
        if our_sealed_score is not None and reward.p_top5 > 0.2:
            return "REGISTER_SMALL", f"Have sealed eval, P(top5)={reward.p_top5:.2f}, low burn"
        if lab_value > 0.5:
            return "OFFLINE_TRAIN", f"Good training environment, still improving"
        return "WATCH", f"Interesting but not yet actionable (lab={lab_value:.2f}, P5={reward.p_top5:.2f})"

    # ─── Medium registration cost ──────────────────────────────────
    if our_sealed_score is not None and reward.p_top5 > 0.5:
        return "LIVE_COMPETE", f"Strong sealed score, P(top5)={reward.p_top5:.2f}"
    if our_sealed_score is not None and reward.p_top5 > 0.2:
        return "REGISTER_SMALL", f"Competitive but not dominant, P(top5)={reward.p_top5:.2f}"
    if lab_value > 0.6:
        return "OFFLINE_TRAIN", f"Good training env, need better score before spending"

    return "WATCH", f"General interest (lab={lab_value:.2f}, diff={difficulty:.2f})"


def rank_opportunities(
    assessments: list[OpportunityAssessment],
) -> list[OpportunityAssessment]:
    """Rank all assessments by priority score. Assigns priority_rank."""
    sorted_a = sorted(assessments, key=lambda a: a.priority_score, reverse=True)
    for i, a in enumerate(sorted_a):
        a.priority_rank = i + 1
    return sorted_a
