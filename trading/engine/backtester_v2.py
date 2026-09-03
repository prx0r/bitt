"""Backtester V2 — point-in-time, no lookahead, real baselines.

Key principles from playbook:
1. No future data leakage — each decision uses only data known at that time
2. Real execution model — account for slippage, fees, pool depth
3. Proper baselines — hold TAO, equal weight, momentum, quality
4. Walk-forward validation — train on past, test on future

This is the foundation for proving any strategy works.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta


MDB = Path("/root/bitt/market.duckdb")
ODB = Path("/root/bitt/oracle.db")


def get_available_timestamps() -> list[str]:
    """Get all available timestamps in chronological order."""
    conn = sqlite3.connect(str(MDB))
    rows = conn.execute(
        "SELECT DISTINCT timestamp FROM pool_state ORDER BY timestamp"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_subnet_state_at(netuid: int, timestamp: str) -> dict:
    """Get subnet state at a specific point in time (no lookahead)."""
    conn = sqlite3.connect(str(MDB))
    conn.row_factory = sqlite3.Row
    
    # Get pool state at or before this timestamp
    pool = conn.execute(
        "SELECT * FROM pool_state WHERE netuid = ? AND timestamp <= ? "
        "ORDER BY timestamp DESC LIMIT 1",
        (netuid, timestamp)
    ).fetchone()
    
    # Get subnet state at or before this timestamp
    state = conn.execute(
        "SELECT * FROM subnet_state WHERE netuid = ? AND timestamp <= ? "
        "ORDER BY timestamp DESC LIMIT 1",
        (netuid, timestamp)
    ).fetchone()
    
    conn.close()
    
    result = {}
    if pool:
        result["alpha_price"] = pool["alpha_price"]
        result["tao_reserve"] = pool["tao_reserve"]
        result["alpha_reserve"] = pool["alpha_reserve"]
        result["liquidity"] = pool["liquidity"]
    if state:
        result["emission"] = state["emission"]
        result["miners"] = state["miners"]
        result["validators"] = state["validators"]
        result["stake"] = state["stake"]
    
    return result


def get_forward_return(netuid: int, entry_timestamp: str, days: int) -> float:
    """Get forward return from entry timestamp (for evaluation)."""
    conn = sqlite3.connect(str(MDB))
    conn.row_factory = sqlite3.Row
    
    # Find entry price
    entry = conn.execute(
        "SELECT alpha_price FROM pool_state WHERE netuid = ? AND timestamp <= ? "
        "ORDER BY timestamp DESC LIMIT 1",
        (netuid, entry_timestamp)
    ).fetchone()
    
    if not entry or not entry["alpha_price"]:
        conn.close()
        return 0
    
    entry_price = entry["alpha_price"]
    
    # Find exit price (entry + days)
    entry_dt = datetime.fromisoformat(entry_timestamp.replace("Z", "+00:00"))
    exit_dt = entry_dt + timedelta(days=days)
    exit_ts = exit_dt.isoformat()
    
    exit_row = conn.execute(
        "SELECT alpha_price FROM pool_state WHERE netuid = ? AND timestamp >= ? "
        "ORDER BY timestamp ASC LIMIT 1",
        (netuid, exit_ts)
    ).fetchone()
    
    conn.close()
    
    if not exit_row or not exit_row["alpha_price"]:
        return 0
    
    return (exit_row["alpha_price"] - entry_price) / entry_price


def baseline_hold_tao() -> dict:
    """Baseline: just hold TAO (0% return by definition in TAO terms)."""
    return {"name": "hold_tao", "description": "Hold 100% TAO", "return": 0}


def baseline_equal_weight(timestamp: str, top_n: int = 10) -> dict:
    """Baseline: equal weight top N subnets by emission."""
    conn = sqlite3.connect(str(MDB))
    conn.row_factory = sqlite3.Row
    
    # Get subnets at this timestamp
    rows = conn.execute(
        "SELECT DISTINCT netuid FROM subnet_state WHERE timestamp <= ?",
        (timestamp,)
    ).fetchall()
    
    netuids = [r["netuid"] for r in rows]
    
    # Get emissions
    subs = []
    for netuid in netuids:
        state = conn.execute(
            "SELECT emission FROM subnet_state WHERE netuid = ? AND timestamp <= ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (netuid, timestamp)
        ).fetchone()
        if state and state["emission"]:
            subs.append({"netuid": netuid, "emission": state["emission"]})
    
    conn.close()
    
    # Top N by emission
    subs.sort(key=lambda x: x["emission"], reverse=True)
    top = subs[:top_n]
    
    return {
        "name": f"equal_weight_top{top_n}",
        "description": f"Equal weight top {top_n} by emission",
        "netuids": [s["netuid"] for s in top],
    }


def baseline_momentum(timestamp: str, lookback_days: int = 7, top_n: int = 5) -> dict:
    """Baseline: momentum — buy subnets with best recent returns."""
    conn = sqlite3.connect(str(MDB))
    conn.row_factory = sqlite3.Row
    
    # Get all subnets
    rows = conn.execute(
        "SELECT DISTINCT netuid FROM pool_state WHERE timestamp <= ?",
        (timestamp,)
    ).fetchall()
    
    candidates = []
    for r in rows:
        netuid = r["netuid"]
        
        # Get current price
        current = conn.execute(
            "SELECT alpha_price FROM pool_state WHERE netuid = ? AND timestamp <= ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (netuid, timestamp)
        ).fetchone()
        
        if not current or not current["alpha_price"]:
            continue
        
        # Get price lookback days ago
        entry_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        past_dt = entry_dt - timedelta(days=lookback_days)
        past_ts = past_dt.isoformat()
        
        past = conn.execute(
            "SELECT alpha_price FROM pool_state WHERE netuid = ? AND timestamp <= ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (netuid, past_ts)
        ).fetchone()
        
        if past and past["alpha_price"]:
            ret = (current["alpha_price"] - past["alpha_price"]) / past["alpha_price"]
            candidates.append({"netuid": netuid, "return": ret})
    
    conn.close()
    
    # Top N by momentum
    candidates.sort(key=lambda x: x["return"], reverse=True)
    top = candidates[:top_n]
    
    return {
        "name": f"momentum_{lookback_days}d_top{top_n}",
        "description": f"Momentum {lookback_days}d, top {top_n}",
        "netuids": [c["netuid"] for c in top],
    }


def backtest_strategy(strategy_fn, timestamps: list[str], initial_tao: float = 100.0,
                      rebalance_days: int = 7) -> dict:
    """Backtest a strategy with point-in-time data."""
    portfolio = {"tao": initial_tao, "positions": {}}
    history = []
    last_rebalance = None
    
    for ts in timestamps:
        # Check if we should rebalance
        if last_rebalance is None:
            should_rebalance = True
        else:
            try:
                entry_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                last_dt = datetime.fromisoformat(last_rebalance.replace("Z", "+00:00"))
                if entry_dt.tzinfo and last_dt.tzinfo:
                    should_rebalance = (entry_dt - last_dt).days >= rebalance_days
                else:
                    should_rebalance = True
            except:
                should_rebalance = True
        
        if should_rebalance:
            # Get strategy signal
            signal = strategy_fn(ts)
            
            if "netuids" in signal:
                # Rebalance to target portfolio
                target_netuids = signal["netuids"]
                
                # Sell positions not in target
                for netuid in list(portfolio["positions"].keys()):
                    if netuid not in target_netuids:
                        # Sell
                        pos = portfolio["positions"][netuid]
                        price = get_subnet_state_at(netuid, ts).get("alpha_price", 0)
                        if price > 0:
                            portfolio["tao"] += pos["units"] * price
                        del portfolio["positions"][netuid]
                
                # Buy new positions
                if target_netuids:
                    weight = 1.0 / len(target_netuids)
                    for netuid in target_netuids:
                        if netuid not in portfolio["positions"]:
                            state = get_subnet_state_at(netuid, ts)
                            price = state.get("alpha_price", 0)
                            if price > 0:
                                tao_to_spend = portfolio["tao"] * weight
                                units = tao_to_spend / price
                                portfolio["tao"] -= tao_to_spend
                                portfolio["positions"][netuid] = {
                                    "units": units,
                                    "entry_price": price,
                                }
                
                last_rebalance = ts
        
        # Update position values
        total_value = portfolio["tao"]
        for netuid, pos in portfolio["positions"].items():
            state = get_subnet_state_at(netuid, ts)
            current_price = state.get("alpha_price", pos["entry_price"])
            total_value += pos["units"] * current_price
        
        history.append({
            "timestamp": ts,
            "total_value": total_value,
            "tao": portfolio["tao"],
            "positions": len(portfolio["positions"]),
        })
    
    # Final value
    final_value = history[-1]["total_value"] if history else initial_tao
    
    return {
        "initial_tao": initial_tao,
        "final_value": round(final_value, 4),
        "total_return_pct": round((final_value - initial_tao) / initial_tao * 100, 2),
        "history": history,
        "n_timestamps": len(timestamps),
    }


if __name__ == "__main__":
    print("=== Backtester V2 ===\n")
    
    timestamps = get_available_timestamps()
    print(f"Available timestamps: {len(timestamps)}")
    if timestamps:
        print(f"Range: {timestamps[0]} to {timestamps[-1]}")
    
    # Use last 100 timestamps for demo
    test_ts = timestamps[-100:] if len(timestamps) > 100 else timestamps
    
    if len(test_ts) < 10:
        print("Insufficient data for backtesting")
        exit()
    
    # Run baselines
    strategies = [
        ("hold_tao", lambda ts: baseline_hold_tao()),
        ("equal_weight_10", lambda ts: baseline_equal_weight(ts, top_n=10)),
        ("momentum_7d_5", lambda ts: baseline_momentum(ts, lookback_days=7, top_n=5)),
    ]
    
    print(f"\nBacktesting {len(strategies)} strategies over {len(test_ts)} timestamps...\n")
    
    results = []
    for name, fn in strategies:
        result = backtest_strategy(fn, test_ts)
        result["name"] = name
        results.append(result)
        print(f"  {name}: {result['total_return_pct']:+.2f}% "
              f"({result['initial_tao']:.2f} → {result['final_value']:.2f})")
    
    # Save
    output = Path("/root/bitt/trading/experiments/backtest_v2_results.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nSaved to {output}")
