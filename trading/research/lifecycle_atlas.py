"""Lifecycle Atlas — cohort analysis of subnet age vs returns.

Answers: "How do new subnets behave vs mature ones?"
- Age-bucket returns
- Survival curves
- Volatility by age
- Forward return distributions
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime


DB = Path("/root/bitt/market.duckdb")


def get_subnet_age_returns() -> list[dict]:
    """Calculate age-bucketed returns for all subnets."""
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    
    # Get all subnet instances with pool data
    instances = conn.execute(
        "SELECT si.*, "
        "MIN(ps.alpha_price) as first_price, "
        "MAX(ps.alpha_price) as max_price, "
        "COUNT(ps.timestamp) as data_points "
        "FROM subnet_instances si "
        "LEFT JOIN pool_state ps ON si.netuid = ps.netuid "
        "GROUP BY si.instance_id "
        "HAVING data_points > 1"
    ).fetchall()
    
    results = []
    for inst in instances:
        first_price = inst['first_price'] or 0
        max_price = inst['max_price'] or 0
        
        if first_price <= 0:
            continue
        
        # Get first and last price
        prices = conn.execute(
            "SELECT alpha_price FROM pool_state WHERE netuid = ? AND alpha_price > 0 "
            "ORDER BY timestamp ASC",
            (inst['netuid'],)
        ).fetchall()
        
        if len(prices) < 2:
            continue
        
        entry_price = prices[0][0]
        current_price = prices[-1][0]
        
        # Calculate return
        total_return = (current_price - entry_price) / entry_price if entry_price > 0 else 0
        
        # Max drawdown
        peak = entry_price
        max_dd = 0
        for p in prices:
            p_val = p[0]
            if p_val > peak:
                peak = p_val
            dd = (peak - p_val) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # Age in data points (proxy for days)
        age_points = len(prices)
        
        results.append({
            "instance_id": inst['instance_id'],
            "netuid": inst['netuid'],
            "age_points": age_points,
            "entry_price": entry_price,
            "current_price": current_price,
            "total_return": round(total_return, 4),
            "max_drawdown": round(max_dd, 4),
            "max_price": max_price,
        })
    
    conn.close()
    return results


def cohort_analysis(results: list[dict]) -> dict:
    """Group subnets by age cohort and calculate stats."""
    cohorts = {}
    
    for r in results:
        age = r['age_points']
        if age <= 10:
            bucket = "0-10"
        elif age <= 50:
            bucket = "11-50"
        elif age <= 100:
            bucket = "51-100"
        else:
            bucket = "100+"
        
        if bucket not in cohorts:
            cohorts[bucket] = []
        cohorts[bucket].append(r)
    
    stats = {}
    for bucket, subs in sorted(cohorts.items()):
        returns = [s['total_return'] for s in subs]
        drawdowns = [s['max_drawdown'] for s in subs]
        win_rate = len([r for r in returns if r > 0]) / len(returns) if returns else 0
        
        stats[bucket] = {
            "count": len(subs),
            "avg_return": round(sum(returns) / len(returns), 4) if returns else 0,
            "median_return": round(sorted(returns)[len(returns)//2], 4) if returns else 0,
            "avg_drawdown": round(sum(drawdowns) / len(drawdowns), 4) if drawdowns else 0,
            "win_rate": round(win_rate, 4),
            "best_return": round(max(returns), 4) if returns else 0,
            "worst_return": round(min(returns), 4) if returns else 0,
        }
    
    return stats


def survival_curve(results: list[dict]) -> dict:
    """Calculate survival rate by age."""
    # Group by age buckets
    buckets = [10, 25, 50, 100, 200]
    survival = {}
    
    for b in buckets:
        alive = len([r for r in results if r['age_points'] >= b])
        total = len(results)
        survival[f"age_{b}"] = {
            "alive": alive,
            "total": total,
            "rate": round(alive / total, 4) if total > 0 else 0,
        }
    
    return survival


if __name__ == "__main__":
    print("=== Lifecycle Atlas ===\n")
    
    results = get_subnet_age_returns()
    print(f"Subnets with price data: {len(results)}")
    
    # Cohort analysis
    cohorts = cohort_analysis(results)
    print(f"\n--- Age Cohort Returns ---")
    print(f"{'Cohort':<12} {'Count':<7} {'Avg Ret':<10} {'Med Ret':<10} {'Win%':<7} {'Avg DD':<10}")
    print("-" * 60)
    for bucket, stats in sorted(cohorts.items()):
        print(f"{bucket:<12} {stats['count']:<7} {stats['avg_return']:<+10.2%} "
              f"{stats['median_return']:<+10.2%} {stats['win_rate']:<7.1%} "
              f"{stats['avg_drawdown']:<10.2%}")
    
    # Survival
    survival = survival_curve(results)
    print(f"\n--- Survival Curve ---")
    for age, data in survival.items():
        print(f"  {age}: {data['alive']}/{data['total']} alive ({data['rate']:.1%})")
    
    # Save
    output = Path("/root/bitt/trading/experiments/lifecycle_atlas.json")
    with open(output, "w") as f:
        json.dump({
            "cohorts": cohorts,
            "survival": survival,
            "total_subnets": len(results),
        }, f, indent=2)
    
    print(f"\nSaved to {output}")
