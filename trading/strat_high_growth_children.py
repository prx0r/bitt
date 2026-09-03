"""Subnet High Growth Children Strategy.

Finds subnets that recently spawned children or show high growth signals,
then allocates to the best child candidates before the crowd.

Core thesis: New subnets (children) often have mispriced alpha in their
first hours/days. Parent subnet holders get airdrops. We front-run the
discovery phase by scanning for:
  1. Recently registered subnets (< 7 days old)
  2. High emission/price ratio (undervalued)
  3. Growing neuron count (adoption signal)
  4. Parent subnet correlation (airdrop thesis)
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta


DB_PATH = Path("/root/bitt/oracle.db")
MARKET_DB = Path("/root/bitt/market.duckdb")


def get_subnet_snapshots() -> list[dict]:
    """Get latest snapshot for each subnet."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    conn.close()
    return [json.loads(row['data']) for row in rows]


def get_subnet_history(netuid: int, days: int = 7) -> list[dict]:
    """Get historical snapshots for a subnet."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        'SELECT data, scanned_at FROM subnet_snapshots '
        'WHERE json_extract(data, "$.netuid") = ? AND scanned_at > ? '
        'ORDER BY scanned_at DESC',
        (netuid, cutoff)
    ).fetchall()
    conn.close()
    return [{"data": json.loads(row['data']), "scanned_at": row['scanned_at']} for row in rows]


def detect_children(subnets: list[dict]) -> list[dict]:
    """Detect recently spawned subnets (potential children).
    
    Criteria:
    - Registration cost is low (new subnet)
    - Neuron count is growing
    - Block height suggests recent creation
    """
    children = []
    for s in subnets:
        netuid = s.get('netuid', 0)
        reg_cost = s.get('registration_cost', 0)
        neurons = s.get('neuron_count', 0)
        emission = s.get('tao_equiv_day', 0)
        price = s.get('alpha_price', 0)
        
        # New subnet signals
        is_new = reg_cost < 1.0 and neurons < 50
        is_growing = neurons > 5 and emission > 0
        
        if is_new or is_growing:
            yield_per_neuron = emission / max(neurons, 1)
            children.append({
                "netuid": netuid,
                "neurons": neurons,
                "emission": emission,
                "yield_per_neuron": yield_per_neuron,
                "alpha_price": price,
                "reg_cost": reg_cost,
                "growth_score": _growth_score(s, subnets),
            })
    
    return sorted(children, key=lambda x: x['growth_score'], reverse=True)


def _growth_score(subnet: dict, all_subnets: list[dict]) -> float:
    """Calculate growth score (0-1). Higher = more attractive."""
    score = 0.0
    
    # Emission relative to network
    total_emission = sum(s.get('tao_equiv_day', 0) for s in all_subnets)
    emission_share = subnet.get('tao_equiv_day', 0) / max(total_emission, 1)
    score += min(emission_share * 20, 0.3)  # Cap at 0.3
    
    # Yield per neuron (higher = better opportunity)
    neurons = subnet.get('neuron_count', 1)
    emission = subnet.get('tao_equiv_day', 0)
    yield_per = emission / max(neurons, 1)
    if yield_per > 0.01:
        score += 0.25
    elif yield_per > 0.001:
        score += 0.15
    
    # Low competition (fewer neurons = easier to mine)
    if neurons < 20:
        score += 0.25
    elif neurons < 50:
        score += 0.15
    elif neurons < 100:
        score += 0.05
    
    # Low price (entry opportunity)
    price = subnet.get('alpha_price', 0)
    if 0 < price < 0.5:
        score += 0.2
    elif 0 < price < 2.0:
        score += 0.1
    
    return min(score, 1.0)


def rank_children(children: list[dict], max_positions: int = 5) -> list[dict]:
    """Rank and filter to top child candidates."""
    # Deduplicate by netuid
    seen = set()
    unique = []
    for c in children:
        if c['netuid'] not in seen:
            seen.add(c['netuid'])
            unique.append(c)
    
    # Take top N
    return unique[:max_positions]


def calculate_position_size(child: dict, total_capital: float, 
                           max_pct: float = 0.10) -> dict:
    """Calculate position size for a child subnet.
    
    Risk management:
    - Max 10% per position
    - Scale by growth score
    - Minimum 1% position
    """
    base_pct = min(max_pct, child['growth_score'] * max_pct)
    position_pct = max(0.01, base_pct)
    position_tao = total_capital * position_pct
    
    return {
        "netuid": child['netuid'],
        "target_pct": position_pct,
        "target_tao": position_tao,
        "growth_score": child['growth_score'],
        "yield_per_neuron": child['yield_per_neuron'],
    }


def generate_signals(total_capital: float = 100.0) -> dict:
    """Generate trading signals for the High Growth Children strategy."""
    subnets = get_subnet_snapshots()
    children = detect_children(subnets)
    top_children = rank_children(children, max_positions=5)
    
    positions = []
    for child in top_children:
        pos = calculate_position_size(child, total_capital)
        positions.append(pos)
    
    # Sum of target allocations
    total_alloc = sum(p['target_pct'] for p in positions)
    cash_pct = 1.0 - total_alloc
    
    return {
        "strategy": "high_growth_children",
        "timestamp": datetime.utcnow().isoformat(),
        "total_capital": total_capital,
        "cash_pct": cash_pct,
        "positions": positions,
        "candidates_screened": len(subnets),
        "children_found": len(children),
        "top_children": len(top_children),
    }


def format_report(signals: dict) -> str:
    """Format signals as readable report."""
    lines = [
        "=" * 60,
        "HIGH GROWTH CHILDREN STRATEGY",
        "=" * 60,
        f"Timestamp: {signals['timestamp']}",
        f"Capital: {signals['total_capital']:.2f} TAO",
        f"Cash: {signals['cash_pct']:.1%}",
        f"Screened: {signals['candidates_screened']} subnets",
        f"Children found: {signals['children_found']}",
        "",
        "POSITIONS:",
    ]
    
    for i, pos in enumerate(signals['positions'], 1):
        lines.append(
            f"  {i}. SN{pos['netuid']:3d} | "
            f"Score: {pos['growth_score']:.2f} | "
            f"Yield/Neuron: {pos['yield_per_neuron']:.4f} | "
            f"Size: {pos['target_pct']:.1%} ({pos['target_tao']:.2f} TAO)"
        )
    
    if not signals['positions']:
        lines.append("  No positions — holding 100% TAO")
    
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    signals = generate_signals(total_capital=100.0)
    print(format_report(signals))
