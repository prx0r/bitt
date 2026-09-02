"""SN88 (Investing) Integration — portfolio management subnet.

Winning strategies from SN88:
- Strategy 1: "all in 1" — 100% in subnet 1
- Strategy 2: "ease in" — gradual entry
- Strategy 3: "rotate" — rotate through top subnets
- Strategy 4: "diversified" — 5-subnet portfolio with cash buffer
- Strategy 5: "all cash" — 100% cash (baseline)

Strategy format: {netuid: weight}
Example: {1: 0.27, 2: 0.15, 4: 0.21, 19: 0.16, 41: 0.16}
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


def strategy_all_in_one(netuid: int = 1) -> dict:
    """Strategy 1: 100% in one subnet."""
    return {netuid: 1.0}


def strategy_rotate(top_n: int = 5) -> dict:
    """Strategy 3: rotate through top N subnets by emission."""
    subnets = get_subnets()
    eligible = [s for s in subnets if s.get('neuron_count', 0) > 10]
    eligible.sort(key=lambda x: x.get('tao_equiv_day', 0), reverse=True)
    top = eligible[:top_n]

    allocation = {}
    for s in top:
        allocation[s.get('netuid', 0)] = 1.0 / top_n

    return allocation


def strategy_diversified(top_n: int = 5, cash_pct: float = 0.05) -> dict:
    """Strategy 4: diversified portfolio with cash buffer."""
    subnets = get_subnets()
    eligible = [s for s in subnets if s.get('neuron_count', 0) > 10]
    eligible.sort(key=lambda x: x.get('tao_equiv_day', 0), reverse=True)
    top = eligible[:top_n]

    weight_per = (1.0 - cash_pct) / top_n
    allocation = {0: cash_pct}  # Root = cash
    for s in top:
        allocation[s.get('netuid', 0)] = weight_per

    return allocation


def strategy_yield_top(top_n: int = 5) -> dict:
    """Strategy: top N by yield/price ratio."""
    subnets = get_subnets()
    eligible = [s for s in subnets if s.get('neuron_count', 0) > 10]

    for s in eligible:
        tao_day = s.get('tao_equiv_day', 0)
        neurons = s.get('neuron_count', 1)
        price = s.get('alpha_price', 0)
        yield_per = tao_day / max(neurons, 1)
        s['_yield_price'] = yield_per / price if price > 0 else 0

    eligible.sort(key=lambda x: x.get('_yield_price', 0), reverse=True)
    top = eligible[:top_n]

    allocation = {}
    for s in top:
        allocation[s.get('netuid', 0)] = 1.0 / top_n

    return allocation


def get_strategy_performance() -> list[dict]:
    """Get performance of different strategies."""
    strategies = [
        {"name": "all_in_1", "allocation": strategy_all_in_one(1)},
        {"name": "rotate_top5", "allocation": strategy_rotate(5)},
        {"name": "diversified_5", "allocation": strategy_diversified(5)},
        {"name": "yield_top5", "allocation": strategy_yield_top(5)},
    ]

    return strategies


if __name__ == "__main__":
    strategies = get_strategy_performance()
    print("=== SN88 STRATEGIES ===")
    for s in strategies:
        print(f"\n{s['name']}:")
        for netuid, weight in s['allocation'].items():
            print(f"  SN{netuid}: {weight:.2%}")
