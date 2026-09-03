"""Mine vs Buy Calculator — the playbook's most Bittensor-native insight.

For every subnet, answer: "Is it cheaper to mine alpha or buy it on the AMM?"

Mining cost = sunk_burn + opportunity_cost + compute_cost
Market cost = alpha_price from pool

Decision: MINE if mining cheaper | BUY if market cheaper | PASS if neither
"""
import sqlite3
import json
from pathlib import Path


ORACLE_DB = Path("/root/bitt/oracle.db")
MARKET_DB = Path("/root/bitt/market.duckdb")


def calculate_mine_vs_buy_all() -> list[dict]:
    """Calculate mine-vs-buy for all subnets."""
    # Load subnet data
    conn = sqlite3.connect(str(ORACLE_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    conn.close()
    
    subnets = [json.loads(r['data']) for r in rows]
    
    results = []
    for subnet in subnets:
        netuid = subnet.get('netuid', 0)
        emission = subnet.get('tao_equiv_day', 0)
        neurons = subnet.get('neuron_count', 0)
        emitting = subnet.get('emitting_count', 0)
        price = subnet.get('alpha_price', 0)
        active = subnet.get('active_count', 0)
        
        if emission <= 0 or neurons <= 0 or price <= 0:
            continue
        
        # Get pool data
        conn2 = sqlite3.connect(str(MARKET_DB))
        conn2.row_factory = sqlite3.Row
        pool = conn2.execute(
            "SELECT * FROM pool_state WHERE netuid = ? ORDER BY timestamp DESC LIMIT 1",
            (netuid,)
        ).fetchone()
        conn2.close()
        
        tao_reserve = float(pool['tao_reserve']) if pool and pool['tao_reserve'] else 0
        alpha_reserve = float(pool['alpha_reserve']) if pool and pool['alpha_reserve'] else 0
        
        # === MINING SIDE ===
        emission_per = emission / max(emitting, 1)
        
        # Entry cost assumptions
        reg_cost_tao = 0.0005  # Default, would come from chain
        collateral_share = 0.0
        sunk_burn = reg_cost_tao * (1 - collateral_share)
        opportunity_cost = 0.001  # 30-day lock at 5% annual
        total_entry = sunk_burn + opportunity_cost
        
        # Compute cost (assume 0 for CPU-only, varies for GPU)
        compute_cost_per_day = 0.001  # Minimal for CPU miner
        
        # Total mining cost per day (amortized entry + compute)
        amortized_entry = total_entry / 30  # 30-day amortization
        mining_cost_per_day = amortized_entry + compute_cost_per_day
        
        # Mining cost per alpha unit
        mining_cost_per_alpha = mining_cost_per_day / max(emission_per, 1e-9)
        
        # Mining yield per TAO invested
        mining_yield_per_tao = emission_per * price / max(total_entry, 1e-9)
        
        # === MARKET SIDE ===
        market_cost_per_alpha = price
        
        # Buy yield (staking return equivalent)
        # If you buy alpha, you're betting on price appreciation + emissions
        buy_yield = emission_per / max(price, 1e-9)  # Emission yield
        
        # === DECISION ===
        # Mining advantage: how much cheaper is mining vs buying?
        if mining_cost_per_alpha > 0 and market_cost_per_alpha > 0:
            advantage_pct = (market_cost_per_alpha - mining_cost_per_alpha) / market_cost_per_alpha * 100
        else:
            advantage_pct = 0
        
        # Days to ROI
        daily_earnings = emission_per * price
        days_to_roi = total_entry / max(daily_earnings, 1e-9)
        
        # Decision logic
        if advantage_pct > 20 and days_to_roi < 30:
            decision = "MINE"
            confidence = min(0.9, 0.5 + advantage_pct / 200)
        elif advantage_pct < -20:
            decision = "BUY"
            confidence = min(0.9, 0.5 + abs(advantage_pct) / 200)
        elif days_to_roi < 7:
            decision = "MINE"  # Quick ROI regardless
            confidence = 0.7
        else:
            decision = "PASS"
            confidence = 0.5
        
        results.append({
            "netuid": netuid,
            "decision": decision,
            "confidence": round(confidence, 2),
            # Mining
            "mining_cost_per_alpha": round(mining_cost_per_alpha, 8),
            "mining_cost_per_day": round(mining_cost_per_day, 8),
            "emission_per_neuron": round(emission_per, 4),
            "total_entry_tao": round(total_entry, 8),
            "mining_yield_per_tao": round(mining_yield_per_tao, 4),
            # Market
            "market_cost_per_alpha": round(market_cost_per_alpha, 8),
            "buy_yield": round(buy_yield, 4),
            # Comparison
            "advantage_pct": round(advantage_pct, 2),
            "days_to_roi": round(days_to_roi, 1),
            # Context
            "neurons": neurons,
            "emitting": emitting,
            "tao_reserve": round(tao_reserve, 0),
            "alpha_reserve": round(alpha_reserve, 0),
        })
    
    results.sort(key=lambda x: abs(x["advantage_pct"]), reverse=True)
    return results


def format_mine_vs_buy_report(results: list[dict]) -> str:
    """Format report."""
    lines = [
        "=" * 90,
        "MINE vs BUY ANALYSIS",
        "=" * 90,
        f"Subnets analyzed: {len(results)}",
        "",
        f"{'#':<4} {'SN':<5} {'Decision':<7} {'Conf':<6} {'Adv%':<8} {'Mine$/α':<12} {'Buy$/α':<12} {'ROI(d)':<8} {'Emit/N':<8} {'Emit'}",
        "-" * 90,
    ]
    
    for i, r in enumerate(results[:25], 1):
        lines.append(
            f"{i:<4} SN{r['netuid']:<4} {r['decision']:<7} {r['confidence']:<6.2f} "
            f"{r['advantage_pct']:<+8.1f} {r['mining_cost_per_alpha']:<12.8f} "
            f"{r['market_cost_per_alpha']:<12.8f} {r['days_to_roi']:<8.1f} "
            f"{r['emission_per_neuron']:<8.2f} {r['emitting']}"
        )
    
    # Summary
    decisions = {}
    for r in results:
        d = r["decision"]
        decisions[d] = decisions.get(d, 0) + 1
    
    lines.extend([
        "",
        f"Decisions: {decisions}",
        "",
        "Top MINE opportunities:",
    ])
    mines = [r for r in results if r["decision"] == "MINE"][:5]
    for r in mines:
        lines.append(f"  SN{r['netuid']}: advantage={r['advantage_pct']:+.1f}%, "
                     f"ROI={r['days_to_roi']:.1f}d, emit/neuron={r['emission_per_neuron']:.2f}")
    
    lines.append("=" * 90)
    return "\n".join(lines)


if __name__ == "__main__":
    results = calculate_mine_vs_buy_all()
    print(format_mine_vs_buy_report(results))
    
    # Save
    output = Path("/root/bitt/trading/experiments/mine_vs_buy.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {output}")
