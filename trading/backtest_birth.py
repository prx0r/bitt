"""Subnet Birth Price Action Backtester.

Simulates buying alpha tokens at subnet launch (birth) and tracks
price action over various holding periods.

Questions answered:
  1. What's the average return from buying at birth?
  2. What's the optimal holding period?
  3. Which subnet characteristics predict strong birth performance?
  4. What's the drawdown profile?
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


DB_PATH = Path("/root/bitt/oracle.db")
MARKET_DB = Path("/root/bitt/market.duckdb")


def get_all_subnet_data() -> list[dict]:
    """Get all subnet snapshots sorted by time."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data, scanned_at FROM subnet_snapshots ORDER BY scanned_at ASC'
    ).fetchall()
    conn.close()
    return [{"data": json.loads(row['data']), "ts": row['scanned_at']} for row in rows]


def get_pool_history(netuid: int) -> list[dict]:
    """Get pool state history for a subnet from market.duckdb."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM pool_state WHERE netuid = ? ORDER BY timestamp ASC',
        (netuid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_candle_history(netuid: int) -> list[dict]:
    """Get candle history for a subnet."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM subnet_candles WHERE netuid = ? ORDER BY timestamp ASC',
        (netuid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def identify_subnet_births() -> list[dict]:
    """Identify subnet launch points from data.
    
    A subnet "birth" is detected when:
    - It first appears in the data with neurons > 0
    - Alpha price goes from 0 to non-zero
    - Or registration cost is minimal (new subnet)
    """
    all_data = get_all_subnet_data()
    
    # Track first appearance of each subnet
    first_seen = {}
    for entry in all_data:
        s = entry['data']
        netuid = s.get('netuid', 0)
        neurons = s.get('neuron_count', 0)
        price = s.get('alpha_price', 0)
        emission = s.get('tao_equiv_day', 0)
        
        if netuid not in first_seen and neurons > 0:
            first_seen[netuid] = {
                "netuid": netuid,
                "birth_ts": entry['ts'],
                "birth_neurons": neurons,
                "birth_price": price,
                "birth_emission": emission,
                "birth_data": s,
            }
    
    return list(first_seen.values())


def simulate_birth_trade(birth: dict, holding_days: list[int] = [1, 3, 7, 14, 30],
                         position_size: float = 10.0) -> dict:
    """Simulate buying at birth and selling after holding period.
    
    Returns simulated P&L for each holding period.
    """
    netuid = birth['netuid']
    entry_price = birth['birth_price']
    
    if entry_price <= 0:
        return {"netuid": netuid, "error": "no_entry_price"}
    
    # Get price history after birth
    pool_history = get_pool_history(netuid)
    candle_history = get_candle_history(netuid)
    
    results = {
        "netuid": netuid,
        "entry_price": entry_price,
        "birth_ts": birth['birth_ts'],
        "position_size": position_size,
        "holding_periods": {},
    }
    
    for days in holding_days:
        # Find price at holding period
        target_ts = (datetime.fromisoformat(birth['birth_ts'].replace('Z', '+00:00')) 
                    + timedelta(days=days)).isoformat()
        
        # Try pool history first
        exit_price = None
        for p in pool_history:
            if p.get('timestamp', '') >= target_ts:
                exit_price = p.get('alpha_price')
                break
        
        # Fallback to candle history
        if exit_price is None:
            for c in candle_history:
                if c.get('timestamp', '') >= target_ts:
                    exit_price = c.get('close_tao')
                    break
        
        if exit_price is None or exit_price <= 0:
            # Use entry price as fallback (no data)
            exit_price = entry_price
        
        # Calculate return
        tokens_bought = position_size / entry_price
        position_value = tokens_bought * exit_price
        pnl = position_value - position_size
        ret_pct = (exit_price - entry_price) / entry_price * 100
        
        results["holding_periods"][f"{days}d"] = {
            "exit_price": exit_price,
            "position_value": position_value,
            "pnl": pnl,
            "return_pct": ret_pct,
        }
    
    return results


def calculate_max_drawdown(prices: list[float]) -> float:
    """Calculate maximum drawdown from a price series."""
    if not prices:
        return 0.0
    
    peak = prices[0]
    max_dd = 0.0
    
    for p in prices:
        if p > peak:
            peak = p
        dd = (peak - p) / peak
        if dd > max_dd:
            max_dd = dd
    
    return max_dd * 100


def run_birth_backtest(position_size: float = 10.0,
                       min_neurons: int = 5) -> dict:
    """Run full birth backtest across all subnets."""
    births = identify_subnet_births()
    
    # Filter to subnets with enough data
    valid_births = [b for b in births if b['birth_neurons'] >= min_neurons]
    
    all_trades = []
    for birth in valid_births:
        trade = simulate_birth_trade(birth, position_size=position_size)
        if "error" not in trade:
            all_trades.append(trade)
    
    # Aggregate results
    summary = {
        "total_births": len(births),
        "valid_births": len(all_trades),
        "position_size": position_size,
        "trades": all_trades,
        "by_period": {},
    }
    
    # Calculate stats per holding period
    for period in ["1d", "3d", "7d", "14d", "30d"]:
        returns = [t['holding_periods'][period]['return_pct'] 
                   for t in all_trades if period in t['holding_periods']]
        
        if returns:
            avg_ret = sum(returns) / len(returns)
            win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
            max_ret = max(returns)
            min_ret = min(returns)
            
            summary["by_period"][period] = {
                "count": len(returns),
                "avg_return": avg_ret,
                "win_rate": win_rate,
                "max_return": max_ret,
                "min_return": min_ret,
            }
    
    return summary


def format_birth_report(results: dict) -> str:
    """Format backtest results as report."""
    lines = [
        "=" * 60,
        "SUBNET BIRTH PRICE ACTION BACKTEST",
        "=" * 60,
        f"Total births detected: {results['total_births']}",
        f"Valid trades: {results['valid_births']}",
        f"Position size: {results['position_size']:.2f} TAO",
        "",
        "RETURNS BY HOLDING PERIOD:",
        f"{'Period':<8} {'Count':<7} {'Avg Ret%':<10} {'Win Rate':<10} {'Max%':<8} {'Min%':<8}",
        "-" * 60,
    ]
    
    for period, stats in results['by_period'].items():
        lines.append(
            f"{period:<8} {stats['count']:<7} {stats['avg_return']:<+10.2f} "
            f"{stats['win_rate']:<10.1f} {stats['max_return']:<+8.1f} {stats['min_return']:<+8.1f}"
        )
    
    # Top 5 trades
    if results['trades']:
        lines.extend(["", "TOP 5 TRADES:"])
        sorted_trades = sorted(results['trades'], 
                              key=lambda t: t['holding_periods'].get('7d', {}).get('return_pct', -999),
                              reverse=True)
        for t in sorted_trades[:5]:
            p7d = t['holding_periods'].get('7d', {})
            lines.append(
                f"  SN{t['netuid']:3d} | Entry: {t['entry_price']:.4f} | "
                f"7d return: {p7d.get('return_pct', 0):+.1f}%"
            )
    
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    results = run_birth_backtest(position_size=10.0, min_neurons=5)
    print(format_birth_report(results))
