"""SN88 Strategy Submitter — package our signals as SN88-compatible strategies.

SN88 accepts: {netuid: weight} dicts
We generate these from our signal composite + Thompson sampling.

Usage:
  allocation = generate_sn88_strategy(capital=100.0)
  # Returns: {1: 0.27, 2: 0.15, 4: 0.21, ...}
"""
import sqlite3
import json
import math
from pathlib import Path
from datetime import datetime


MDB = Path("/root/bitt/market.duckdb")
STRATEGIES_DIR = Path("/root/bitt/trading/strategies")


def get_current_scores() -> list[dict]:
    """Get current composite scores for all subnets."""
    conn = sqlite3.connect(str(MDB))
    conn.row_factory = sqlite3.Row
    
    # Get latest scan
    rows = conn.execute(
        "SELECT * FROM daily_subnet_scan ORDER BY scan_date DESC LIMIT 130"
    ).fetchall()
    conn.close()
    
    return [dict(r) for r in rows]


def thompson_sample(scores: list[dict], n_samples: int = 1000) -> dict:
    """Thompson sampling for capital allocation.
    
    Each subnet is a "fish" with win/loss history.
    Posterior: Beta(alpha0 + wins, beta0 + losses)
    Sample from posterior → weight by sampled rate.
    """
    import random
    
    allocations = {}
    
    for s in scores:
        netuid = s.get("netuid")
        score = s.get("total_score", 50)
        
        # Convert score to win/loss (score > 50 = win)
        wins = max(0, (score - 50) / 10)  # Rough conversion
        losses = max(0, (50 - score) / 10)
        
        # Beta posterior
        alpha = 1 + wins  # Prior alpha=1
        beta = 1 + losses  # Prior beta=1
        
        # Sample from posterior
        samples = [random.betavariate(alpha, beta) for _ in range(n_samples)]
        mean_sample = sum(samples) / len(samples)
        
        allocations[netuid] = mean_sample
    
    # Normalize to sum to 1.0
    total = sum(allocations.values())
    if total > 0:
        allocations = {k: v / total for k, v in allocations.items()}
    
    return allocations


def generate_sn88_strategy(capital: float = 100.0, 
                           min_weight: float = 0.02,
                           max_positions: int = 10,
                           cash_pct: float = 0.05) -> dict:
    """Generate SN88-compatible strategy from our signals.
    
    Returns: {netuid: weight} dict
    """
    scores = get_current_scores()
    
    if not scores:
        # Fallback: equal weight top 5
        return {i: 0.19 for i in range(1, 6)}
    
    # Sort by score
    scores.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    
    # Top N
    top = scores[:max_positions]
    
    # Thompson sample for weights
    weights = thompson_sample(top)
    
    # Apply constraints
    filtered = {k: v for k, v in weights.items() if v >= min_weight}
    
    # Add cash
    allocated = sum(filtered.values())
    if allocated > (1 - cash_pct):
        # Scale down
        scale = (1 - cash_pct) / allocated
        filtered = {k: v * scale for k, v in filtered.items()}
    
    # Root = cash position
    result = {0: cash_pct}
    result.update(filtered)
    
    # Normalize
    total = sum(result.values())
    if total > 0:
        result = {k: round(v / total, 4) for k, v in result.items()}
    
    return result


def format_sn88_submission(allocation: dict) -> str:
    """Format as SN88 submission string."""
    return json.dumps(allocation, separators=(',', ':'))


def backtest_strategy(allocation: dict, days: int = 7) -> dict:
    """Backtest a strategy against historical data."""
    conn = sqlite3.connect(str(MDB))
    conn.row_factory = sqlite3.Row
    
    # Get timestamps
    timestamps = conn.execute(
        "SELECT DISTINCT timestamp FROM pool_state ORDER BY timestamp"
    ).fetchall()
    timestamps = [r['timestamp'] for r in timestamps]
    
    if len(timestamps) < days * 24:
        return {"error": "insufficient data"}
    
    # Simulate portfolio
    portfolio = {"tao": 100.0, "positions": {}}
    history = []
    
    for ts in timestamps[-days*24:]:
        # Check if should rebalance (daily)
        if len(history) % 24 == 0:
            # Get prices at this time
            for netuid, weight in allocation.items():
                if netuid == 0:  # Cash
                    continue
                
                price_row = conn.execute(
                    "SELECT alpha_price FROM pool_state WHERE netuid = ? AND timestamp <= ? "
                    "ORDER BY timestamp DESC LIMIT 1",
                    (netuid, ts)
                ).fetchone()
                
                if price_row and price_row['alpha_price'] > 0:
                    price = price_row['alpha_price']
                    target_tao = portfolio["tao"] * weight
                    
                    # Buy if not holding
                    if netuid not in portfolio["positions"]:
                        units = target_tao / price
                        portfolio["tao"] -= target_tao
                        portfolio["positions"][netuid] = {
                            "units": units,
                            "entry_price": price,
                        }
        
        # Update values
        total_value = portfolio["tao"]
        for netuid, pos in portfolio["positions"].items():
            price_row = conn.execute(
                "SELECT alpha_price FROM pool_state WHERE netuid = ? AND timestamp <= ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (netuid, ts)
            ).fetchone()
            if price_row:
                total_value += pos["units"] * price_row['alpha_price']
        
        history.append({"timestamp": ts, "value": total_value})
    
    conn.close()
    
    if not history:
        return {"error": "no history"}
    
    final = history[-1]["value"]
    initial = history[0]["value"]
    
    return {
        "initial": initial,
        "final": round(final, 4),
        "return_pct": round((final - initial) / initial * 100, 2),
        "positions": len([k for k in allocation if k != 0]),
    }


if __name__ == "__main__":
    print("=== SN88 Strategy Generator ===\n")
    
    allocation = generate_sn88_strategy()
    print(f"Strategy: {json.dumps(allocation)}")
    print(f"\nFormatted: {format_sn88_submission(allocation)}")
    
    # Backtest
    result = backtest_strategy(allocation)
    print(f"\nBacktest: {result}")
    
    # Save
    output = STRATEGIES_DIR / "sn88_submitted.json"
    with open(output, "w") as f:
        json.dump({"allocation": allocation, "backtest": result, 
                   "timestamp": datetime.utcnow().isoformat()}, f, indent=2)
    print(f"\nSaved to {output}")
