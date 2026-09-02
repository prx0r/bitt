"""Reward analyzer — calculates attainable reward, HHI, and economic metrics.

Takes raw chain data + mechanism info → produces reward distribution analysis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .snapshot import BittensorOpportunitySnapshot
from .mechanism import MechanismInfo, PayoutCurve


@dataclass
class RewardAnalysis:
    """Computed reward distribution and attainable reward metrics."""
    # Raw distribution
    incentive_shares: tuple[float, ...] = ()
    hhi: float = 0.0
    effective_earners: float = 0.0
    top1_share: float = 0.0
    top3_share: float = 0.0
    top5_share: float = 0.0
    top10_share: float = 0.0

    # Attainable reward (our estimated probability of each rank)
    p_any_reward: float = 0.0
    p_top10: float = 0.0
    p_top5: float = 0.0
    p_top3: float = 0.0
    p_champion: float = 0.0

    # Expected values
    expected_tao_day: float = 0.0
    p05_tao_day: float = 0.0
    p50_tao_day: float = 0.0
    p95_tao_day: float = 0.0

    # Pool info
    miner_pool_tao_equiv_day: float = 0.0
    contestable_pool_tao_day: float = 0.0  # pool minus owner/validator shares


def analyze_reward_distribution(
    miner_incentives: list[float],
    pool_tao_day: float,
    mechanism: MechanismInfo,
    owner_share: float | None = None,
    validator_share: float | None = None,
) -> RewardAnalysis:
    """Analyze reward distribution from metagraph incentive data.

    Args:
        miner_incentives: raw incentive values from metagraph for miner UIDs
        pool_tao_day: total TAO-equivalent going to miner side per day
        mechanism: parsed mechanism info
        owner_share: owner's share of subnet emission (if known)
        validator_share: validator share of subnet emission (if known)
    """
    result = RewardAnalysis()

    if not miner_incentives or pool_tao_day <= 0:
        return result

    # Normalize shares
    total = sum(miner_incentives)
    if total <= 0:
        return result

    shares = tuple(x / total for x in miner_incentives)
    shares_sorted = sorted(shares, reverse=True)

    result.incentive_shares = shares_sorted

    # HHI (Herfindahl-Hirschman Index)
    result.hhi = sum(x * x for x in shares_sorted)
    result.effective_earners = 1.0 / result.hhi if result.hhi > 0 else 0

    # Top-N concentration
    result.top1_share = shares_sorted[0] if len(shares_sorted) >= 1 else 0
    result.top3_share = sum(shares_sorted[:3])
    result.top5_share = sum(shares_sorted[:5])
    result.top10_share = sum(shares_sorted[:10])

    # Contestable pool (subtract owner/validator if known)
    contestable = pool_tao_day
    if owner_share is not None:
        contestable *= (1.0 - owner_share)
    if validator_share is not None:
        contestable *= (1.0 - validator_share)
    result.contestable_pool_tao_day = max(0, contestable)
    result.miner_pool_tao_equiv_day = pool_tao_day

    # Calculate expected payout for each rank
    payout = mechanism.payout_curve
    rank_payouts = []
    for i, share in enumerate(shares_sorted):
        rank = i + 1
        payout_tao = payout.payout_for_rank(rank, result.contestable_pool_tao_day)
        rank_payouts.append((rank, payout_tao, share))

    # For ranked protocols, paid ranks are those in the payout_curve
    if payout.ranked_shares:
        paid_ranks = [r for r, _ in payout.ranked_shares]
        max_paid_rank = max(paid_ranks) if paid_ranks else 0

        # Our attainable reward (placeholder — real value comes from sealed eval)
        # For now, estimate based on being "average miner" position
        n_miners = len(shares_sorted)
        if n_miners > 0:
            # Naive: probability of being in top-N is roughly proportional
            # to how many slots pay vs total miners
            result.p_champion = min(1.0, 1.0 / n_miners) if n_miners > 0 else 0
            result.p_top5 = min(1.0, 5.0 / n_miners)
            result.p_top3 = min(1.0, 3.0 / n_miners)
            result.p_top10 = min(1.0, 10.0 / n_miners)
            result.p_any_reward = result.p_top5  # for top-5 protocols

            # Expected TAO/day = sum over paid ranks of P(rank) * payout(rank)
            expected = 0.0
            for rank, payout_tao, _ in rank_payouts:
                p_rank = 1.0 / n_miners if rank <= n_miners else 0
                expected += p_rank * payout_tao
            result.expected_tao_day = expected

    elif payout.winner_take_all:
        n_miners = len(shares_sorted)
        result.p_champion = 1.0 / n_miners if n_miners > 0 else 0
        result.p_top5 = result.p_champion
        result.p_top3 = result.p_champion
        result.p_top10 = result.p_champion
        result.p_any_reward = result.p_champion
        result.expected_tao_day = (
            result.p_champion * result.contestable_pool_tao_day
        )

    elif payout.proportional_formula:
        # Proportional: continuous scoring, no fixed ranks
        n_miners = len(shares_sorted)
        result.p_any_reward = 0.5  # placeholder
        result.p_top10 = 0.3
        result.p_top5 = 0.2
        result.p_top3 = 0.1
        result.p_champion = 0.05
        result.expected_tao_day = result.contestable_pool_tao_day / max(1, n_miners)

    # Percentile estimates (bootstrap-like)
    result.p05_tao_day = result.expected_tao_day * 0.1
    result.p50_tao_day = result.expected_tao_day * 0.8
    result.p95_tao_day = result.expected_tao_day * 2.5

    return result


def calculate_alpha_risk(
    reward_alpha_day: float,
    alpha_price_tao: float,
    alpha_volatility_7d: float = 0.0,
    alpha_volatility_30d: float = 0.0,
) -> dict:
    """Calculate alpha risk metrics.

    Stress tests at spot, -20%, -40%, -60%.
    """
    spot_usd = reward_alpha_day * alpha_price_tao * 230  # approximate TAO/USD
    return {
        "reward_alpha_day": reward_alpha_day,
        "alpha_price_tao": alpha_price_tao,
        "spot_value_usd": spot_usd,
        "stress_neg20_usd": spot_usd * 0.80,
        "stress_neg40_usd": spot_usd * 0.60,
        "stress_neg60_usd": spot_usd * 0.40,
        "alpha_volatility_7d": alpha_volatility_7d,
        "alpha_volatility_30d": alpha_volatility_30d,
    }


def estimate_cost_to_attempt(mechanism: MechanismInfo) -> dict:
    """Estimate total cost to attempt on a subnet."""
    breakdown = {
        "registration_burn_tao": float(mechanism.eligibility.min_stake_tao
                                        if hasattr(mechanism.eligibility, 'min_stake_tao')
                                        else 0),
        "submission_fee_tao": float(mechanism.submission_fee_tao),
        "api_inference_usd": 0.0,   # estimated per episode
        "local_compute_usd": 0.0,
        "gpu_cost_usd": 0.0,
    }
    # Add known registration costs from config
    from ..config import SUBNETS
    subnet_cfg = SUBNETS.get(mechanism.netuid)
    if subnet_cfg:
        breakdown["registration_burn_tao"] = subnet_cfg.registration_cost_approx

    total_tao = (
        breakdown["registration_burn_tao"]
        + breakdown["submission_fee_tao"]
    )
    breakdown["total_tao"] = total_tao
    breakdown["total_usd_approx"] = total_tao * 230  # approximate

    return breakdown
