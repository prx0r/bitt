"""Low Fruit Scan — Daily scan for low-competition high-reward opportunities.

Unlike the decision engine (which ranks by EV), this scan:
1. Scores EVERY subnet on competition × reward × quality
2. Stores results with timestamp → building historical moat
3. Compares to yesterday → delta alerts
4. Everything weighted — nothing explicitly excluded

The moat: after 30/90/365 days of daily scans, we have unique data
nobody else has about what opportunities look like before they pop.

Architecture:
- Reads oracle.db + market.duckdb
- Outputs to daily_subnet_scores (append-only table)
- Runs in <30 seconds (all local data)
"""
import sqlite3
import json
import math
from pathlib import Path
from datetime import datetime, timedelta


ORACLE_DB = Path("/root/bitt/oracle.db")
MARKET_DB = Path("/root/bitt/market.duckdb")


def get_current_subnets() -> list[dict]:
    """Get latest snapshot for all subnets."""
    conn = sqlite3.connect(str(ORACLE_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    conn.close()
    return [json.loads(r['data']) for r in rows]


def get_pool_latest(netuid: int) -> dict:
    """Get latest pool state."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM pool_state WHERE netuid = ? ORDER BY timestamp DESC LIMIT 1",
        (netuid,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def get_price_history(netuid: int, days: int = 7) -> list[float]:
    """Get recent price history for volatility/momentum."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT close_tao FROM subnet_candles WHERE netuid = ? AND close_tao IS NOT NULL "
        "ORDER BY timestamp DESC LIMIT ?",
        (netuid, days * 288)  # 5-min candles
    ).fetchall()
    conn.close()
    return [r['close_tao'] for r in rows if r['close_tao']]


def score_subnet(subnet: dict, pool: dict, prices: list[float]) -> dict:
    """Score a subnet for LOW FRUIT opportunity.
    
    Low fruit = easy, regular, repeatable income.
    NOT jackpots. NOT winner-take-all.
    
    Key insight: we want subnets where we can pluck 0.1 TAO easily and regularly.
    Only weight outsized winner-take-all if they have EXCEPTIONAL opportunity.
    
    Scores (0-100):
    - easiness: broad participation + low barrier + regular payouts
    - yield: TAO/day we can actually earn (not theoretical)
    - stability: low volatility + consistent emissions
    - access: low registration cost + no GPU + no special requirements
    - stickiness: will this still be paying in 30 days?
    """
    netuid = subnet.get('netuid', 0)
    neurons = subnet.get('neuron_count', 0)
    active = subnet.get('active_count', 0)
    emitting = subnet.get('emitting_count', 0)
    emission = subnet.get('tao_equiv_day', 0)
    price = subnet.get('alpha_price', 0)
    validators = subnet.get('validator_count', 0)
    
    liquidity = pool.get('liquidity', 0) or 0
    tao_reserve = pool.get('tao_reserve', 0) or 0
    
    if neurons <= 0 or emission <= 0:
        return {"netuid": netuid, "total": 0, "skip": True}
    
    competition_ratio = emitting / max(neurons, 1)
    emission_per = emission / max(emitting, 1)
    
    # === EASINESS (0-100) — Can we actually earn regularly? ===
    # Broad participation = many miners earning = repeatable income
    # Low competition ratio = fewer mouths to feed
    # High emitting ratio = most participants are earning
    
    easiness = 0
    
    # Participation breadth: what % of miners are earning?
    emit_ratio = emitting / max(neurons, 1)
    if emit_ratio > 0.8:
        easiness += 35  # Almost everyone earns — easy entry
    elif emit_ratio > 0.6:
        easiness += 28
    elif emit_ratio > 0.4:
        easiness += 20
    elif emit_ratio > 0.2:
        easiness += 12
    else:
        easiness += 5   # Most miners not earning — hard
    
    # Competition density: how many competitors per earning slot?
    competitors_per_earner = max(neurons, 1) / max(emitting, 1)
    if competitors_per_earner < 1.5:
        easiness += 30  # Almost no competition
    elif competitors_per_earner < 2.5:
        easiness += 22
    elif competitors_per_earner < 4:
        easiness += 15
    elif competitors_per_earner < 8:
        easiness += 8
    else:
        easiness += 2
    
    # Absolute count: more earning slots = more opportunity
    if emitting >= 50:
        easiness += 20
    elif emitting >= 20:
        easiness += 15
    elif emitting >= 10:
        easiness += 10
    elif emitting >= 5:
        easiness += 5
    
    # HHI penalty: high concentration = one miner takes most
    hhi_est = 1.0 / max(emitting, 1) if emitting > 0 else 1.0
    if hhi_est < 0.05:
        easiness += 15  # Very distributed
    elif hhi_est < 0.1:
        easiness += 10
    elif hhi_est < 0.2:
        easiness += 5
    else:
        easiness -= 10  # Concentrated — penalize
    
    easiness = min(max(easiness, 0), 100)
    
    # === YIELD (0-100) — How much can we actually earn? ===
    # Emission per neuron is the real metric
    # But we want SUSTAINABLE yield, not one spike
    
    if emission_per > 1.0:
        yield_score = 90
    elif emission_per > 0.5:
        yield_score = 75
    elif emission_per > 0.1:
        yield_score = 60
    elif emission_per > 0.05:
        yield_score = 45
    elif emission_per > 0.01:
        yield_score = 30
    else:
        yield_score = 10
    
    # === STABILITY (0-100) — Is this consistent? ===
    stability = 50  # baseline
    
    # Price stability (low vol = predictable)
    if len(prices) >= 10:
        returns = [(prices[i] - prices[i+1]) / prices[i+1] for i in range(len(prices)-1) if prices[i+1] > 0]
        vol = (sum(r**2 for r in returns) / len(returns)) ** 0.5 if returns else 0
        if vol < 0.01:
            stability += 25  # Very stable
        elif vol < 0.03:
            stability += 18
        elif vol < 0.05:
            stability += 10
        elif vol < 0.1:
            stability += 5
        else:
            stability -= 10  # Volatile
    
    # Validator count = network health
    if validators >= 10:
        stability += 15
    elif validators >= 5:
        stability += 8
    
    # Active ratio = miners actually showing up
    active_ratio = active / max(neurons, 1)
    if active_ratio > 0.8:
        stability += 10
    elif active_ratio > 0.5:
        stability += 5
    
    stability = min(max(stability, 0), 100)
    
    # === ACCESS (0-100) — How easy to start? ===
    # Based on what we know about the subnet type
    # Low neuron count often means low barrier
    access = 50
    if neurons < 20:
        access += 25  # Very few people — easy to join
    elif neurons < 50:
        access += 15
    elif neurons < 100:
        access += 8
    
    # TAO reserve suggests some infrastructure
    if tao_reserve > 100:
        access += 10
    elif tao_reserve > 10:
        access += 5
    
    access = min(max(access, 0), 100)
    
    # === STICKINESS (0-100) — Will this still pay in 30 days? ===
    stickiness = 50
    # More validators + more emitters = more established = stickier
    if validators >= 10 and emitting >= 20:
        stickiness += 25
    elif validators >= 5 and emitting >= 10:
        stickiness += 15
    
    # High emission share of network = harder to kill
    total_emission_proxy = emission
    if total_emission_proxy > 1000:
        stickiness += 15
    elif total_emission_proxy > 100:
        stickiness += 8
    
    stickiness = min(max(stickiness, 0), 100)
    
    # === WINNER-TAKE-ALL ADJUSTMENT ===
    # WTA subnets CAN be good if the outsized opportunity justifies it
    # But by default they're penalized for low fruit
    is_wta = hhi_est > 0.2 or emit_ratio < 0.1
    wta_multiplier = 0.6 if is_wta else 1.0  # Penalize WTA unless exceptional
    
    # Exceptional WTA: very high emission_per justifies the risk
    if is_wta and emission_per > 10:
        wta_multiplier = 0.85  # Less penalty
    elif is_wta and emission_per > 5:
        wta_multiplier = 0.75
    
    # === COMBINED SCORE ===
    # Low fruit weights: easiness 35%, yield 25%, stability 20%, access 10%, stickiness 10%
    raw_total = (
        easiness * 0.35 +
        yield_score * 0.25 +
        stability * 0.20 +
        access * 0.10 +
        stickiness * 0.10
    )
    
    total = raw_total * wta_multiplier
    
    # Topology label (informational, not exclusionary)
    if is_wta:
        topology = "WINNER_TAKE_ALL"
    elif emit_ratio > 0.6 and emitting >= 10:
        topology = "BROAD_PARTICIPATION"
    elif emitting >= 5:
        topology = "PROPORTIONAL"
    else:
        topology = "EMERGING"
    
    return {
        "netuid": netuid,
        "total": round(total, 1),
        "easiness": round(easiness, 1),
        "yield_score": round(yield_score, 1),
        "stability": round(stability, 1),
        "access": round(access, 1),
        "stickiness": round(stickiness, 1),
        "competition_ratio": round(competition_ratio, 4),
        "emit_ratio": round(emit_ratio, 4),
        "emission_per_neuron": round(emission_per, 4),
        "emitting": emitting,
        "neurons": neurons,
        "validators": validators,
        "emission_day": emission,
        "price": price,
        "liquidity": round(liquidity, 0),
        "tao_reserve": round(tao_reserve, 0),
        "hhi_est": round(hhi_est, 4),
        "topology": topology,
        "wta_adjusted": is_wta,
        "skip": False,
    }


def init_daily_table():
    """Create daily_subnet_scores table (append-only)."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_subnet_scores (
            scan_date TEXT NOT NULL,
            netuid INTEGER NOT NULL,
            total_score REAL,
            competition_score REAL,
            reward_score REAL,
            infrastructure_score REAL,
            momentum_score REAL,
            quality_score REAL,
            competition_ratio REAL,
            emission_per_neuron REAL,
            emitting INTEGER,
            neurons INTEGER,
            emission_day REAL,
            price REAL,
            liquidity REAL,
            topology TEXT,
            PRIMARY KEY (scan_date, netuid)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_scan_summary (
            scan_date TEXT PRIMARY KEY,
            total_subnets INTEGER,
            actionable_count INTEGER,
            avg_score REAL,
            top_subnet INTEGER,
            top_score REAL,
            scan_duration_ms INTEGER
        )
    """)
    conn.commit()
    conn.close()


def store_scan_results(scores: list[dict], scan_date: str):
    """Store scan results (append-only)."""
    conn = sqlite3.connect(str(MARKET_DB))
    
    for s in scores:
        if s.get("skip"):
            continue
        conn.execute(
            "INSERT OR REPLACE INTO daily_subnet_scores "
            "(scan_date, netuid, total_score, competition_score, reward_score, "
            "infrastructure_score, momentum_score, quality_score, competition_ratio, "
            "emission_per_neuron, emitting, neurons, emission_day, price, liquidity, topology) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scan_date, s["netuid"], s["total"], s.get("easiness", 0), s.get("yield_score", 0),
                s.get("stability", 0), s.get("access", 0), s.get("stickiness", 0), s.get("competition_ratio", 0),
                s.get("emission_per_neuron", 0), s.get("emitting", 0), s.get("neurons", 0), s.get("emission_day", 0),
                s.get("price", 0), s.get("liquidity", 0), s.get("topology", ""),
            )
        )
    
    # Store summary
    actionable = [s for s in scores if not s.get("skip") and s["total"] > 30]
    valid = [s for s in scores if not s.get("skip")]
    
    conn.execute(
        "INSERT OR REPLACE INTO daily_scan_summary "
        "(scan_date, total_subnets, actionable_count, avg_score, top_subnet, top_score) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            scan_date,
            len(valid),
            len(actionable),
            round(sum(s["total"] for s in valid) / max(len(valid), 1), 1),
            valid[0]["netuid"] if valid else 0,
            valid[0]["total"] if valid else 0,
        )
    )
    
    conn.commit()
    conn.close()


def get_yesterday_scores(scan_date: str) -> dict:
    """Get yesterday's scores for delta comparison."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    
    # Find most recent scan before today
    yesterday = (datetime.fromisoformat(scan_date) - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM daily_subnet_scores WHERE scan_date <= ? ORDER BY scan_date DESC",
        (yesterday,)
    ).fetchall()
    conn.close()
    
    # Get latest per subnet
    latest = {}
    for r in rows:
        d = dict(r)
        if d["netuid"] not in latest:
            latest[d["netuid"]] = d
    
    return latest


def format_low_fruit_report(scores: list[dict], scan_date: str, deltas: dict) -> str:
    """Format scan report."""
    valid = [s for s in scores if not s.get("skip")]
    actionable = [s for s in valid if s["total"] > 30]
    
    lines = [
        "=" * 90,
        f"LOW FRUIT SCAN — {scan_date}",
        "=" * 90,
        f"Subnets: {len(valid)} | Actionable (>30): {len(actionable)} | Avg score: {sum(s['total'] for s in valid)/max(len(valid),1):.1f}",
        "",
        f"{'#':<4} {'SN':<5} {'Total':<7} {'Easy':<6} {'Yield':<6} {'Stab':<6} {'Accs':<6} {'Stick':<6} {'Emit/N':<8} {'Topo':<18} {'WTA'}",
        "-" * 90,
    ]
    
    for i, s in enumerate(sorted(valid, key=lambda x: x["total"], reverse=True)[:30], 1):
        wta = "*" if s.get("wta_adjusted") else ""
        lines.append(
            f"{i:<4} SN{s['netuid']:<4} {s['total']:<7.1f} {s.get('easiness',0):<6.0f} "
            f"{s.get('yield_score',0):<6.0f} {s.get('stability',0):<6.0f} {s.get('access',0):<6.0f} "
            f"{s.get('stickiness',0):<6.0f} {s['emission_per_neuron']:<8.2f} "
            f"{s['topology']:<18} {wta}"
        )
    
    # Top movers
    if deltas:
        moves = []
        for s in valid:
            if s["netuid"] in deltas:
                prev = deltas[s["netuid"]]["total_score"]
                moves.append({"netuid": s["netuid"], "delta": s["total"] - prev, "new": s["total"], "old": prev})
        moves.sort(key=lambda x: x["delta"], reverse=True)
        
        if moves:
            lines.extend(["", "TOP MOVERS (vs yesterday):"])
            for m in moves[:5]:
                lines.append(f"  SN{m['netuid']}: {m['old']:.1f} → {m['new']:.1f} ({m['delta']:+.1f})")
    
    lines.append("=" * 80)
    return "\n".join(lines)


def run_low_fruit_scan() -> dict:
    """Run the full low fruit scan."""
    start = datetime.utcnow()
    scan_date = start.strftime("%Y-%m-%d")
    
    init_daily_table()
    
    subnets = get_current_subnets()
    scores = []
    
    for subnet in subnets:
        netuid = subnet.get('netuid', 0)
        pool = get_pool_latest(netuid)
        prices = get_price_history(netuid, days=1)
        score = score_subnet(subnet, pool, prices)
        scores.append(score)
    
    scores.sort(key=lambda x: x.get("total", 0), reverse=True)
    
    # Store results
    store_scan_results(scores, scan_date)
    
    # Get deltas
    deltas = get_yesterday_scores(scan_date)
    
    duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
    
    return {
        "scan_date": scan_date,
        "subnets_scanned": len(scores),
        "actionable": len([s for s in scores if not s.get("skip") and s["total"] > 30]),
        "top_subnet": scores[0]["netuid"] if scores else 0,
        "top_score": scores[0]["total"] if scores else 0,
        "duration_ms": duration_ms,
        "scores": scores,
        "deltas": deltas,
    }


if __name__ == "__main__":
    result = run_low_fruit_scan()
    print(format_low_fruit_report(result["scores"], result["scan_date"], result["deltas"]))
    
    print(f"\nScan complete: {result['subnets_scanned']} subnets in {result['duration_ms']}ms")
    print(f"Actionable: {result['actionable']}")
    print(f"Top: SN{result['top_subnet']} (score {result['top_score']})")
    
    # Show history
    conn = sqlite3.connect(str(MARKET_DB))
    rows = conn.execute("SELECT * FROM daily_scan_summary ORDER BY scan_date DESC LIMIT 5").fetchall()
    conn.close()
    if rows:
        print(f"\nScan history:")
        for r in rows:
            print(f"  {r[0]}: {r[2]} actionable, avg={r[3]}, top=SN{r[4]} ({r[5]})")
