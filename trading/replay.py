"""Replay — chronological historical simulation.

Treats historical data as if it were happening live.
No look-ahead. Each decision uses only information available at that timestamp.
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional


DB_PATH = Path("/root/bitt/market.duckdb")


def get_timestamps() -> list[str]:
    """Get all available timestamps in chronological order."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT DISTINCT timestamp FROM subnet_5m ORDER BY timestamp"
    ).fetchall()
    conn.close()
    return [r['timestamp'] for r in rows]


def replay(initial_tao: float = 100.0, strategy: str = "momentum",
           max_steps: int = 100) -> dict:
    """Run chronological replay.

    For each 5m timestamp:
    1. Reveal only data up to that timestamp
    2. Calculate features
    3. Make decision (HOLD_TAO or ALLOCATE)
    4. Record decision
    5. Advance to next timestamp
    6. Measure outcome
    """
    from rebalancer import decide, calculate_yield_price

    timestamps = get_timestamps()
    if not timestamps:
        return {"error": "No historical data"}

    timestamps = timestamps[:max_steps]
    portfolio = {"tao": initial_tao, "subnets": {}}
    history = []

    for i, ts in enumerate(timestamps[:-1]):  # Can't measure outcome for last timestamp
        # Get data available at this timestamp
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # Get all subnet prices up to this timestamp
        rows = conn.execute(
            "SELECT netuid, close_tao FROM subnet_5m WHERE timestamp <= ? "
            "GROUP BY netuid ORDER BY timestamp DESC",
            (ts,)
        ).fetchall()
        subs = {r['netuid']: r['close_tao'] for r in rows}

        # Get candles for each subnet (use alpha_price as close)
        sub_candles = {}
        for netuid in subs:
            candle_rows = conn.execute(
                "SELECT *, COALESCE(alpha_price, 0) as actual_price "
                "FROM subnet_5m WHERE netuid = ? AND timestamp <= ? "
                "AND alpha_price IS NOT NULL AND alpha_price > 0 "
                "ORDER BY timestamp DESC LIMIT 288",
                (netuid, ts)
            ).fetchall()
            # Map to standard format
            candles = []
            for r in candle_rows:
                candles.append({
                    'close_tao': r['actual_price'],
                    'volume': r[6] if len(r) > 6 and r[6] else 0,  # volume column
                })
            sub_candles[netuid] = candles

        conn.close()

        # Get next timestamp for outcome measurement
        next_ts = timestamps[i + 1] if i + 1 < len(timestamps) else None

        # Make decisions for top subnets
        decisions = []
        for netuid in list(subs.keys())[:10]:  # Top 10 subnets
            decision = decide(netuid, sub_candles.get(netuid, []), {}, portfolio)
            decision["netuid"] = netuid
            decision["timestamp"] = ts
            decisions.append(decision)

        # Record decisions
        for d in decisions:
            if d["action"] == "ALLOCATE":
                # Execute allocation — buy alpha units with TAO
                weight = d["target_weight"]
                tao_to_spend = portfolio["tao"] * weight
                netuid = d["netuid"]
                current_price = sub_candles.get(netuid, [{}])[0].get('close_tao', 0) if sub_candles.get(netuid) else 0

                if current_price and current_price > 0:
                    # Buy alpha units (simplified: no slippage)
                    units = tao_to_spend / current_price
                    portfolio["tao"] -= tao_to_spend
                    portfolio["subnets"][netuid] = {
                        "units": units,
                        "entry_price": current_price,
                        "entry_ts": ts,
                        "current_price": current_price,
                    }
                    print(f"  {ts}: ALLOCATE SN{netuid} {weight:.1%} ({units:.2f} alpha @ {current_price:.6f})")

            elif d["action"] == "HOLD_TAO":
                pass  # No action needed

        # Measure outcome (next timestamp)
        if next_ts:
            conn2 = sqlite3.connect(str(DB_PATH))
            conn2.row_factory = sqlite3.Row
            for netuid, holding in list(portfolio["subnets"].items()):
                next_row = conn2.execute(
                    "SELECT COALESCE(alpha_price, 0) as price FROM subnet_5m "
                    "WHERE netuid = ? AND timestamp >= ? AND alpha_price > 0 "
                    "ORDER BY timestamp LIMIT 1",
                    (netuid, next_ts)
                ).fetchone()
                if next_row and next_row['price']:
                    current_price = subs.get(netuid, 0)
                    next_price = next_row['price']
                    if current_price and current_price > 0:
                        # Update holding value (units stay same, price changes)
                        holding["current_price"] = next_price
            conn2.close()

        # Calculate total value
        total_value = portfolio["tao"]
        for netuid, holding in portfolio["subnets"].items():
            price = holding.get("current_price", 0) or 0
            units = holding.get("units", 0)
            total_value += units * price

        history.append({
            "timestamp": ts,
            "tao": portfolio["tao"],
            "subnets": len(portfolio["subnets"]),
            "total_value": total_value,
        })

    return {
        "initial_tao": initial_tao,
        "final_tao": portfolio["tao"],
        "total_return": (portfolio["tao"] - initial_tao) / initial_tao * 100,
        "history": history,
        "n_steps": len(timestamps),
    }


if __name__ == "__main__":
    result = replay(initial_tao=100.0, max_steps=50)
    print(f"\n=== REPLAY RESULTS ===")
    print(f"Initial: {result.get('initial_tao', 0):.2f} TAO")
    print(f"Final: {result.get('final_tao', 0):.2f} TAO")
    print(f"Return: {result.get('total_return', 0):+.1f}%")
    print(f"Steps: {result.get('n_steps', 0)}")
