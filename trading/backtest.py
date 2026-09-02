"""TAO Backtester — simulate hold TAO + swing trade subnets.

Uses:
- Our oracle.db for current subnet data
- Simulated historical data for backtesting
- Simple yield/price ratio strategy

No real TAO needed. Pure simulation.
"""
import sqlite3
import json
import random
from pathlib import Path


DB_PATH = Path("/root/bitt/oracle.db")


def get_current_subnets() -> list[dict]:
    """Get current subnet data from oracle.db."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()

    subs = []
    for row in rows:
        data = json.loads(row['data'])
        subs.append(data)
    conn.close()
    return subs


def calculate_yield(subnet: dict) -> float:
    """Calculate TAO per neuron per day."""
    tao_day = subnet.get('tao_equiv_day', 0)
    neurons = subnet.get('neuron_count', 1)
    return tao_day / max(neurons, 1)


def calculate_signal(subnet: dict) -> str:
    """Generate buy/hold/sell signal based on yield/price ratio."""
    yield_per_neuron = calculate_yield(subnet)
    price = subnet.get('alpha_price', 0)
    if price <= 0:
        return "hold"
    ratio = yield_per_neuron / price
    if ratio > 100:
        return "buy"
    elif ratio > 50:
        return "hold"
    else:
        return "sell"


def simulate_portfolio(subnets: list[dict], initial_tao: float = 100.0,
                       swing_pct: float = 0.2, n_days: int = 30) -> dict:
    """Simulate portfolio performance over n_days.

    Strategy:
    - Baseline: 100% TAO (root staking)
    - When subnet yield/price > 100: swing swing_pct into subnet
    - When subnet yield/price < 50: swing back to TAO
    """
    portfolio = {"tao": initial_tao, "subnets": {}}
    history = []

    for day in range(n_days):
        # Calculate daily emissions
        total_daily = 0
        for sub in subnets:
            tao_day = sub.get('tao_equiv_day', 0)
            total_daily += tao_day

        # Root staking yield (simplified)
        root_yield = total_daily * 0.01  # 1% of total emissions

        # Check signals
        for sub in subnets:
            netuid = sub.get('netuid', 0)
            signal = calculate_signal(sub)

            if signal == "buy" and netuid not in portfolio["subnets"]:
                # Swing into subnet
                swing_amount = portfolio["tao"] * swing_pct
                portfolio["tao"] -= swing_amount
                portfolio["subnets"][netuid] = {
                    "amount_tao": swing_amount,
                    "entry_day": day,
                    "alpha_price": sub.get('alpha_price', 0),
                }
                print(f"  Day {day}: BUY SN{netuid} ({swing_amount:.2f} TAO)")

            elif signal == "sell" and netuid in portfolio["subnets"]:
                # Swing back to TAO
                held = portfolio["subnets"][netuid]
                portfolio["tao"] += held["amount_tao"]
                del portfolio["subnets"][netuid]
                print(f"  Day {day}: SELL SN{netuid} (back to TAO)")

        # Add staking yield
        portfolio["tao"] += root_yield

        # Record history
        total_value = portfolio["tao"]
        for netuid, holding in portfolio["subnets"].items():
            # Simplified: assume alpha price stays constant
            total_value += holding["amount_tao"]

        history.append({
            "day": day,
            "tao": portfolio["tao"],
            "subnets": len(portfolio["subnets"]),
            "total_value": total_value,
        })

    return {
        "initial_tao": initial_tao,
        "final_tao": portfolio["tao"],
        "total_return": (portfolio["tao"] - initial_tao) / initial_tao * 100,
        "history": history,
        "final_holdings": portfolio,
    }


def run_backtest():
    """Run full backtest with current data."""
    print("=== TAO Backtest ===\n")

    subnets = get_current_subnets()
    print(f"Subnets: {len(subnets)}")

    # Run simulation
    result = simulate_portfolio(subnets, initial_tao=100.0, swing_pct=0.2, n_days=30)

    print(f"\n=== RESULTS ===")
    print(f"Initial: {result['initial_tao']:.2f} TAO")
    print(f"Final: {result['final_tao']:.2f} TAO")
    print(f"Return: {result['total_return']:+.1f}%")
    print(f"Holdings: {len(result['final_holdings']['subnets'])} subnets")
    print(f"\nStrategy: hold TAO baseline, swing into high yield/price subnets")


if __name__ == "__main__":
    run_backtest()
