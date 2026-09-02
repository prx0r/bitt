"""Replay — chronological historical simulation.

Treats historical data as if it were happening live.
No look-ahead. Each decision uses only information available at that timestamp.
"""
import sqlite3
from pathlib import Path


DB_PATH = Path("/root/bitt/market.duckdb")


def get_timestamps() -> list[str]:
    """Get all available timestamps in chronological order."""
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT DISTINCT timestamp FROM subnet_candles ORDER BY timestamp"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_candles(netuid: int, up_to: str, limit: int = 48) -> list[dict]:
    """Get candles for a subnet up to a timestamp."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM subnet_candles WHERE netuid = ? AND timestamp <= ? "
        "ORDER BY timestamp DESC LIMIT ?",
        (netuid, up_to, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_pool_at(netuid: int, timestamp: str) -> dict | None:
    """Get pool state at a specific timestamp."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM pool_state WHERE netuid = ? AND timestamp <= ? "
        "ORDER BY timestamp DESC LIMIT 1",
        (netuid, timestamp)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def decide(netuid: int, candles: list[dict], pool: dict | None, portfolio: dict) -> dict:
    """Make a trading decision based on candles and pool state."""
    if len(candles) < 20:
        return {"action": "HOLD", "reason": "insufficient data"}

    closes = [c['close_tao'] for c in candles if c.get('close_tao')]
    if len(closes) < 20:
        return {"action": "HOLD", "reason": "insufficient price data"}

    # 10-period vs 20-period moving average
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    current = closes[-1]

    # RSI (14-period)
    gains = []
    losses = []
    for i in range(1, min(15, len(closes))):
        diff = closes[-i] - closes[-i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0.001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Pool-aware: check liquidity
    liquidity = pool.get('liquidity', 0) if pool else 0
    if liquidity and liquidity < 100:
        return {"action": "HOLD", "reason": "low liquidity"}

    # Decision logic
    if ma10 > ma20 and rsi < 70:
        position = portfolio.get("positions", {}).get(netuid)
        if position:
            return {"action": "HOLD", "reason": "trend intact"}
        else:
            return {"action": "BUY", "weight": 0.25,
                    "reason": f"MA10>{ma10:.4f} > MA20>{ma20:.4f}, RSI={rsi:.0f}"}
    elif ma10 < ma20 or rsi > 75:
        position = portfolio.get("positions", {}).get(netuid)
        if position:
            return {"action": "SELL",
                    "reason": f"MA10={ma10:.4f} < MA20={ma20:.4f}, RSI={rsi:.0f}"}
        else:
            return {"action": "HOLD", "reason": "no position"}
    else:
        return {"action": "HOLD", "reason": "no signal"}


def replay(initial_tao: float = 100.0, max_steps: int = 100) -> dict:
    """Run chronological replay on subnet data."""
    timestamps = get_timestamps()
    if not timestamps:
        return {"error": "No historical data"}

    timestamps = timestamps[:max_steps + 1]
    portfolio = {"cash": initial_tao, "positions": {}}
    history = []

    for i in range(len(timestamps) - 1):
        ts = timestamps[i]
        next_ts = timestamps[i + 1]

        # Get available subnets at this timestamp
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT DISTINCT netuid FROM subnet_candles WHERE timestamp <= ?",
            (ts,)
        ).fetchall()
        netuids = [r['netuid'] for r in rows]
        conn.close()

        # Make decisions for top subnets
        for netuid in netuids[:10]:
            candles = get_candles(netuid, ts)
            pool = get_pool_at(netuid, ts)
            decision = decide(netuid, candles, pool, portfolio)

            if decision["action"] == "BUY":
                weight = decision.get("weight", 0.25)
                tao_to_spend = portfolio["cash"] * weight
                if tao_to_spend > 0 and candles:
                    price = candles[-1]['close_tao']
                    if price and price > 0:
                        units = tao_to_spend / price
                        portfolio["cash"] -= tao_to_spend
                        portfolio["positions"][netuid] = {
                            "units": units,
                            "entry_price": price,
                            "current_price": price,
                        }
                        print(f"  {ts}: BUY SN{netuid} {weight:.0%} "
                              f"({units:.2f} alpha @ {price:.6f})")

            elif decision["action"] == "SELL":
                position = portfolio["positions"].get(netuid)
                if position:
                    sell_value = position["units"] * position["current_price"]
                    portfolio["cash"] += sell_value
                    del portfolio["positions"][netuid]
                    print(f"  {ts}: SELL SN{netuid} ({sell_value:.4f} TAO)")

        # Update positions with next timestamp prices
        for netuid, position in list(portfolio["positions"].items()):
            next_candles = get_candles(netuid, next_ts, limit=1)
            if next_candles and next_candles[-1].get('close_tao'):
                position["current_price"] = next_candles[-1]['close_tao']

        # Calculate total value
        total_value = portfolio["cash"]
        for pos in portfolio["positions"].values():
            total_value += pos["units"] * pos["current_price"]

        history.append({
            "timestamp": ts,
            "cash": portfolio["cash"],
            "positions": len(portfolio["positions"]),
            "total_value": total_value,
        })

    final_value = portfolio["cash"]
    for pos in portfolio["positions"].values():
        final_value += pos["units"] * pos["current_price"]

    return {
        "initial_tao": initial_tao,
        "final_value": final_value,
        "total_return": (final_value - initial_tao) / initial_tao * 100,
        "history": history,
        "n_steps": len(timestamps) - 1,
    }


if __name__ == "__main__":
    result = replay(initial_tao=100.0, max_steps=50)
    print(f"\n=== REPLAY RESULTS ===")
    print(f"Initial: {result.get('initial_tao', 0):.2f} TAO")
    print(f"Final: {result.get('final_value', 0):.2f} TAO")
    print(f"Return: {result.get('total_return', 0):+.1f}%")
    print(f"Steps: {result.get('n_steps', 0)}")
