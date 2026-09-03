"""Low Competition Miner Strategy.

Identifies subnets where mining is least competitive and most profitable.
Goal: Find subnets where a new miner can enter and earn emissions with
minimal stake and competition.

Key signals:
  1. Low neuron count (few miners)
  2. High emission per neuron (lots of TAO to earn)
  3. Low total stake (don't need much capital)
  4. Active but not saturated (emission gate open)
  5. Reasonable registration cost (not too expensive to enter)
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime


DB_PATH = Path("/root/bitt/oracle.db")


def get_subnet_data() -> list[dict]:
    """Get latest subnet data."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    conn.close()
    return [json.loads(row['data']) for row in rows]


def score_mining_opportunity(subnet: dict) -> dict:
    """Score a subnet for mining opportunity (0-100).
    
    Scoring:
    - Competition score (40%): fewer neurons = better
    - Emission score (30%): higher emission/neuron = better
    - Stake score (20%): lower total stake needed = better
    - Access score (10%): registration cost + emission gate
    """
    netuid = subnet.get('netuid', 0)
    neurons = subnet.get('neuron_count', 1)
    active = subnet.get('active_count', 0)
    emission = subnet.get('tao_equiv_day', 0)
    total_stake = subnet.get('total_stake', 0)
    reg_cost = subnet.get('registration_cost', 0)
    emitting = subnet.get('emitting_count', 0)
    
    # === COMPETITION SCORE (40%) ===
    # Fewer neurons = less competition
    if neurons <= 10:
        comp_score = 100
    elif neurons <= 25:
        comp_score = 80
    elif neurons <= 50:
        comp_score = 60
    elif neurons <= 100:
        comp_score = 40
    elif neurons <= 200:
        comp_score = 20
    else:
        comp_score = 5
    
    # === EMISSION SCORE (30%) ===
    # Higher emission per neuron = more profitable
    yield_per_neuron = emission / max(neurons, 1)
    if yield_per_neuron > 0.1:
        em_score = 100
    elif yield_per_neuron > 0.05:
        em_score = 80
    elif yield_per_neuron > 0.01:
        em_score = 60
    elif yield_per_neuron > 0.005:
        em_score = 40
    elif yield_per_neuron > 0.001:
        em_score = 20
    else:
        em_score = 5
    
    # === STAKE SCORE (20%) ===
    # Lower total stake = easier to become significant
    stake_per_neuron = total_stake / max(neurons, 1)
    if stake_per_neuron < 100:
        stake_score = 100
    elif stake_per_neuron < 500:
        stake_score = 80
    elif stake_per_neuron < 1000:
        stake_score = 60
    elif stake_per_neuron < 5000:
        stake_score = 40
    elif stake_per_neuron < 10000:
        stake_score = 20
    else:
        stake_score = 5
    
    # === ACCESS SCORE (10%) ===
    # Low registration cost + emission gate open
    access_score = 50  # baseline
    if reg_cost < 1.0:
        access_score += 25
    elif reg_cost < 5.0:
        access_score += 15
    
    # Emission gate: if emitting > 50% of neurons, gate is open
    emit_ratio = emitting / max(neurons, 1)
    if emit_ratio > 0.5:
        access_score += 25
    elif emit_ratio > 0.3:
        access_score += 15
    access_score = min(access_score, 100)
    
    # === COMPOSITE ===
    total_score = (
        comp_score * 0.40 +
        em_score * 0.30 +
        stake_score * 0.20 +
        access_score * 0.10
    )
    
    return {
        "netuid": netuid,
        "total_score": round(total_score, 1),
        "competition_score": comp_score,
        "emission_score": em_score,
        "stake_score": stake_score,
        "access_score": access_score,
        "neurons": neurons,
        "active": active,
        "emission": emission,
        "yield_per_neuron": yield_per_neuron,
        "total_stake": total_stake,
        "stake_per_neuron": stake_per_neuron,
        "reg_cost": reg_cost,
        "emit_ratio": emit_ratio,
    }


def rank_mining_opportunities(subnets: list[dict], min_score: float = 40.0,
                               max_positions: int = 10) -> list[dict]:
    """Rank all subnets by mining opportunity score."""
    scored = []
    for s in subnets:
        result = score_mining_opportunity(s)
        if result['total_score'] >= min_score:
            scored.append(result)
    
    return sorted(scored, key=lambda x: x['total_score'], reverse=True)[:max_positions]


def generate_mining_signals(min_score: float = 40.0) -> dict:
    """Generate mining opportunity signals."""
    subnets = get_subnet_data()
    opportunities = rank_mining_opportunities(subnets, min_score=min_score)
    
    return {
        "strategy": "low_competition_miner",
        "timestamp": datetime.utcnow().isoformat(),
        "total_subnets": len(subnets),
        "above_threshold": len(opportunities),
        "threshold": min_score,
        "opportunities": opportunities,
    }


def format_mining_report(signals: dict) -> str:
    """Format mining signals as readable report."""
    lines = [
        "=" * 70,
        "LOW COMPETITION MINER STRATEGY",
        "=" * 70,
        f"Timestamp: {signals['timestamp']}",
        f"Subnets analyzed: {signals['total_subnets']}",
        f"Above threshold ({signals['threshold']}): {signals['above_threshold']}",
        "",
        "TOP MINING OPPORTUNITIES:",
        f"{'Rank':<5} {'SN':<5} {'Score':<7} {'Neurons':<8} {'Yield/N':<10} {'Stake/N':<10} {'RegCost':<8}",
        "-" * 70,
    ]
    
    for i, opp in enumerate(signals['opportunities'], 1):
        lines.append(
            f"{i:<5} {opp['netuid']:<5} {opp['total_score']:<7.1f} "
            f"{opp['neurons']:<8} {opp['yield_per_neuron']:<10.4f} "
            f"{opp['stake_per_neuron']:<10.1f} {opp['reg_cost']:<8.2f}"
        )
    
    if not signals['opportunities']:
        lines.append("  No opportunities above threshold")
    
    lines.append("=" * 70)
    return "\n".join(lines)


def get_entry_cost(opp: dict) -> dict:
    """Estimate cost to enter a subnet as a miner."""
    # Registration cost (burn)
    reg = opp['reg_cost']
    
    # Minimum stake to be competitive (target top 50%)
    target_stake = opp['stake_per_neuron'] * 0.5
    
    # Total entry cost
    total = reg + target_stake
    
    return {
        "netuid": opp['netuid'],
        "registration_cost": reg,
        "target_stake": target_stake,
        "total_entry_tao": total,
        "expected_daily_yield": opp['yield_per_neuron'] * 1.0,  # Assume 1 neuron
        "payback_days": total / max(opp['yield_per_neuron'], 0.0001),
    }


if __name__ == "__main__":
    signals = generate_mining_signals(min_score=40.0)
    print(format_mining_report(signals))
    
    # Show entry costs for top 3
    print("\nENTRY COSTS (Top 3):")
    for opp in signals['opportunities'][:3]:
        cost = get_entry_cost(opp)
        print(f"  SN{cost['netuid']:3d}: {cost['total_entry_tao']:.2f} TAO "
              f"(reg={cost['registration_cost']:.2f} + stake={cost['target_stake']:.2f}) "
              f"payback={cost['payback_days']:.0f} days")
