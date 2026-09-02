"""Replay — chronological historical simulation.

Treats historical data as if it were happening live.
No look-ahead. Each decision uses only information available at that timestamp.
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional


DB_PATH = Path("/root/bitt/trading/market.duckdb")


def get_timestamps() -> list[str]:
    """Get all available timestamps in chronological order."""
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT DISTINCT timestamp FROM crypto_5m ORDER BY timestamp"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_candles(symbol: str, up_to: str, limit: int = 48) -> list[dict]:
    """Get candles for a symbol up to a timestamp."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM crypto_5m WHERE symbol = ? AND timestamp <= ? "
        "ORDER BY timestamp DESC LIMIT ?",
        (symbol, up_to, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def decide(symbol: str, candles: list[dict], portfolio: dict) -> dict:
    """Make a trading decision based on candles."""
    if len(candles) < 20:
        return {"action": "HOLD", "reason": "insufficient data"}
    
    # Simple momentum strategy
    closes = [c['close'] for c in candles]
    
    # 10-period vs 20-period moving average
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    current = closes[-1]
    
    # RSI (14-period)
    gains = []
    losses = []
    for i in range(1, min(15, len(closes))):
        diff = closes[-i] - closes[-i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0.001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Decision logic
    if ma10 > ma20 and rsi < 70:
        # Uptrend, not overbought
        position = portfolio.get("positions", {}).get(symbol)
        if position:
            return {"action": "HOLD", "reason": "trend intact"}
        else:
            return {"action": "BUY", "weight": 0.25, "reason": f"MA10>{ma10:.0f} > MA20>{ma20:.0f}, RSI={rsi:.0f}"}
    elif ma10 < ma20 or rsi > 75:
        # Downtrend or overbought
        position = portfolio.get("positions", {}).get(symbol)
        if position:
            return {"action": "SELL", "reason": f"MA10={ma10:.0f} < MA20={ma20:.0f}, RSI={rsi:.0f}"}
        else:
            return {"action": "HOLD", "reason": "no position"}
    else:
        return {"action": "HOLD", "reason": "no signal"}


def replay(initial_tao: float = 100.0, max_steps: int = 100) -> dict:
    """Run chronological replay on crypto data."""
    timestamps = get_timestamps()
    if not timestamps:
        return {"error": "No historical data"}

    timestamps = timestamps[:max_steps+1]  # +1 for outcome measurement
    portfolio = {"cash": initial_tao, "positions": {}}
    history = []

    symbols = ['BTC', 'ETH', 'SOL']

    for i in range(len(timestamps) - 1):
        ts = timestamps[i]
        next_ts = timestamps[i + 1]

        # Get candles for each symbol up to current timestamp
        symbol_candles = {}
        for sym in symbols:
            symbol_candles[sym] = get_candles(sym, ts)

        # Make decisions
        for sym in symbols:
            decision = decide(sym, symbol_candles[sym], portfolio)
            
            if decision["action"] == "BUY":
                weight = decision.get("weight", 0.25)
                tao_to_spend = portfolio["cash"] * weight
                if tao_to_spend > 0 and symbol_candles[sym]:
                    price = symbol_candles[sym][-1]['close']
                    units = tao_to_spend / price
                    portfolio["cash"] -= tao_to_spend
                    portfolio["positions"][sym] = {
                        "units": units,
                        "entry_price": price,
                        "current_price": price,
                    }
                    print(f"  {ts}: BUY {sym} {weight:.0%} ({units:.4f} @ ${price:,.0f})")
            
            elif decision["action"] == "SELL":
                position = portfolio["positions"].get(sym)
                if position:
                    # Sell at current price
                    sell_value = position["units"] * position["current_price"]
                    portfolio["cash"] += sell_value
                    del portfolio["positions"][sym]
                    print(f"  {ts}: SELL {sym} (${sell_value:,.2f})")

        # Update positions with next timestamp prices
        for sym, position in portfolio["positions"].items():
            next_candles = get_candles(sym, next_ts, limit=1)
            if next_candles:
                position["current_price"] = next_candles[-1]['close']

        # Calculate total value
        total_value = portfolio["cash"]
        for sym, pos in portfolio["positions"].items():
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
    print(f"Initial: ${result.get('initial_tao', 0):,.2f}")
    print(f"Final: ${result.get('final_value', 0):,.2f}")
    print(f"Return: {result.get('total_return', 0):+.1f}%")
    print(f"Steps: {result.get('n_steps', 0)}")
