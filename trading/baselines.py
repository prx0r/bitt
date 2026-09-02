"""TAO Baselines — boring strategies to beat.

These are the minimum performance bars. Any learned strategy must
outperform ALL of these on out-of-sample data.

1. Free TAO: 100% TAO, no action
2. Root TAO: stake on root (lowest risk)
3. Equal-weight: equal allocation across all eligible subnets
4. Momentum: 7-day cross-sectional momentum (top N by return)
5. Yield: top N by yield/price ratio
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


def baseline_free_tao(initial_tao: float = 100.0) -> dict:
    """Baseline 1: 100% TAO, no action."""
    return {
        "name": "Free TAO",
        "strategy": "hold 100% TAO, no trading",
        "initial_tao": initial_tao,
        "final_tao": initial_tao,  # No change (no staking yield in sim)
        "positions": {},
    }


def baseline_root_staking(initial_tao: float = 100.0) -> dict:
    """Baseline 2: stake all TAO on root."""
    return {
        "name": "Root TAO",
        "strategy": "100% TAO staked on root",
        "initial_tao": initial_tao,
        "final_tao": initial_tao * 1.001,  # Simplified root yield
        "positions": {0: {"amount_tao": initial_tao}},
    }


def baseline_equal_weight(subnets: list[dict], initial_tao: float = 100.0) -> dict:
    """Baseline 3: equal weight across all eligible subnets."""
    eligible = [s for s in subnets if s.get('neuron_count', 0) > 10]
    n = len(eligible)
    if n == 0:
        return baseline_free_tao(initial_tao)

    per_subnet = initial_tao / n
    positions = {}
    for s in eligible:
        positions[s.get('netuid', 0)] = {"amount_tao": per_subnet}

    return {
        "name": f"Equal-Weight ({n} subnets)",
        "strategy": f"equal allocation across {n} eligible subnets",
        "initial_tao": initial_tao,
        "final_tao": initial_tao,  # Simplified
        "positions": positions,
    }


def baseline_momentum(subnets: list[dict], initial_tao: float = 100.0, top_n: int = 10) -> dict:
    """Baseline 4: 7-day cross-sectional momentum (top N by emission)."""
    eligible = [s for s in subnets if s.get('neuron_count', 0) > 10]
    eligible.sort(key=lambda x: x.get('tao_equiv_day', 0), reverse=True)
    top = eligible[:top_n]

    per_subnet = initial_tao / len(top) if top else 0
    positions = {}
    for s in top:
        positions[s.get('netuid', 0)] = {"amount_tao": per_subnet}

    return {
        "name": f"Momentum Top-{top_n}",
        "strategy": f"7d momentum: top {top_n} by emission",
        "initial_tao": initial_tao,
        "final_tao": initial_tao,
        "positions": positions,
    }


def baseline_yield(subnets: list[dict], initial_tao: float = 100.0, top_n: int = 10) -> dict:
    """Baseline 5: top N by yield/price ratio."""
    eligible = [s for s in subnets if s.get('neuron_count', 0) > 10]

    # Calculate yield/price
    for s in eligible:
        tao_day = s.get('tao_equiv_day', 0)
        neurons = s.get('neuron_count', 1)
        price = s.get('alpha_price', 0)
        yield_per = tao_day / max(neurons, 1)
        s['_yield_price'] = yield_per / price if price > 0 else 0

    eligible.sort(key=lambda x: x.get('_yield_price', 0), reverse=True)
    top = eligible[:top_n]

    per_subnet = initial_tao / len(top) if top else 0
    positions = {}
    for s in top:
        positions[s.get('netuid', 0)] = {"amount_tao": per_subnet}

    return {
        "name": f"Yield Top-{top_n}",
        "strategy": f"top {top_n} by yield/price ratio",
        "initial_tao": initial_tao,
        "final_tao": initial_tao,
        "positions": positions,
    }


def run_all_baselines() -> list[dict]:
    """Run all baselines and return results."""
    subnets = get_subnets()
    initial_tao = 100.0

    baselines = [
        baseline_free_tao(initial_tao),
        baseline_root_staking(initial_tao),
        baseline_equal_weight(subnets, initial_tao),
        baseline_momentum(subnets, initial_tao),
        baseline_yield(subnets, initial_tao),
    ]

    return baselines


if __name__ == "__main__":
    baselines = run_all_baselines()
    print("=== BASELINES ===")
    for b in baselines:
        print(f"  {b['name']}: {b['strategy']}")
        print(f"    Positions: {len(b['positions'])} subnets")
