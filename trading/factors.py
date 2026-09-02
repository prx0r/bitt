"""TAO Factors — trading signals based on subnet fundamentals.

Each factor returns a score per subnet. Higher = more attractive.
"""
import sqlite3
import json
from pathlib import Path


DB_PATH = Path("/root/bitt/oracle.db")


def get_subnets() -> list[dict]:
    """Get current subnet data."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    subs = [json.loads(row['data']) for row in rows]
    conn.close()
    return subs


def factor_yield_price(subnets: list[dict]) -> dict[str, float]:
    """Factor 1: Yield/price ratio (higher = more undervalued)."""
    scores = {}
    for s in subnets:
        uid = s.get('netuid', 0)
        tao_day = s.get('tao_equiv_day', 0)
        neurons = s.get('neuron_count', 1)
        price = s.get('alpha_price', 0)

        yield_per = tao_day / max(neurons, 1)
        ratio = yield_per / price if price > 0 else 0
        scores[uid] = ratio

    return scores


def factor_emission_momentum(subnets: list[dict]) -> dict[str, float]:
    """Factor 2: Emission momentum (higher emission = stronger signal)."""
    scores = {}
    for s in subnets:
        uid = s.get('netuid', 0)
        tao_day = s.get('tao_equiv_day', 0)
        scores[uid] = tao_day

    # Normalize to 0-1
    max_val = max(scores.values()) if scores else 1
    return {k: v / max_val for k, v in scores.items()}


def factor_miner_quality(subnets: list[dict]) -> dict[str, float]:
    """Factor 3: Mining quality (active/total ratio, distribution)."""
    scores = {}
    for s in subnets:
        uid = s.get('netuid', 0)
        total = s.get('neuron_count', 1)
        active = s.get('active_count', 0)
        hhi = s.get('hhi', 0)  # Concentration (lower = better)

        active_ratio = active / max(total, 1)
        # Lower HHI = more distributed = better
        hhi_score = 1.0 - min(hhi, 1.0)

        scores[uid] = active_ratio * 0.5 + hhi_score * 0.5

    return scores


def factor_emission_gate(subnets: list[dict]) -> dict[str, float]:
    """Factor 4: Emission gate (if emission is gated, it's restricted)."""
    scores = {}
    for s in subnets:
        uid = s.get('netuid', 0)
        emitting = s.get('emitting_count', 0)
        total = s.get('neuron_count', 1)
        # Higher emitting ratio = more participants earning
        scores[uid] = emitting / max(total, 1)

    return scores


def factor_top_incentive_distribution(subnets: list[dict]) -> dict[str, float]:
    """Factor 5: Incentive distribution (lower top concentration = better)."""
    scores = {}
    for s in subnets:
        uid = s.get('netuid', 0)
        top1 = s.get('top1_incentive', 0)
        top10 = s.get('top10_incentive', 0)
        # Lower ratio = more distributed rewards
        if top10 > 0:
            scores[uid] = 1.0 - (top1 / top10)
        else:
            scores[uid] = 0.5

    return scores


def calculate_composite_score(subnets: list[dict]) -> dict[str, dict]:
    """Calculate composite score from all factors."""
    factors = {
        "yield_price": factor_yield_price(subnets),
        "emission_momentum": factor_emission_momentum(subnets),
        "miner_quality": factor_miner_quality(subnets),
        "emission_gate": factor_emission_gate(subnets),
        "incentive_dist": factor_top_incentive_distribution(subnets),
    }

    # Weights
    weights = {
        "yield_price": 0.35,
        "emission_momentum": 0.20,
        "miner_quality": 0.15,
        "emission_gate": 0.15,
        "incentive_dist": 0.15,
    }

    # Normalize each factor to 0-1
    normalized = {}
    for fname, fscores in factors.items():
        max_val = max(fscores.values()) if fscores else 1
        min_val = min(fscores.values()) if fscores else 0
        range_val = max_val - min_val if max_val > min_val else 1
        normalized[fname] = {k: (v - min_val) / range_val for k, v in fscores.items()}

    # Calculate composite
    composite = {}
    for s in subnets:
        uid = s.get('netuid', 0)
        score = 0
        for fname, weight in weights.items():
            score += normalized.get(fname, {}).get(uid, 0) * weight

        composite[uid] = {
            "composite_score": score,
            "yield_price": normalized.get("yield_price", {}).get(uid, 0),
            "emission_momentum": normalized.get("emission_momentum", {}).get(uid, 0),
            "miner_quality": normalized.get("miner_quality", {}).get(uid, 0),
            "emission_gate": normalized.get("emission_gate", {}).get(uid, 0),
            "incentive_dist": normalized.get("incentive_dist", {}).get(uid, 0),
            "alpha_price": s.get('alpha_price', 0),
            "tao_equiv_day": s.get('tao_equiv_day', 0),
        }

    return composite


if __name__ == "__main__":
    subnets = get_subnets()
    scores = calculate_composite_score(subnets)

    print("=== COMPOSITE SCORES ===")
    sorted_scores = sorted(scores.items(), key=lambda x: x[1]['composite_score'], reverse=True)

    for uid, s in sorted_scores[:15]:
        print(f"  SN{uid:3d}: composite={s['composite_score']:.3f} "
              f"yield_price={s['yield_price']:.3f} "
              f"emission={s['emission_momentum']:.3f} "
              f"alpha={s['alpha_price']:.4f}")
