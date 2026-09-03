"""Subnet Intelligence Engine — classify, predict, trade any subnet.

Takes raw on-chain data → structured profile → edge prediction → trade signal.

Usage:
  profile = classify_subnet(netuid=22)
  # Returns: {type: "quiet_niche", vol_profile: "calm", child_score: 85, ...}
  
  signal = predict_and_trade(profile)
  # Returns: {action: "BUY", confidence: 0.78, hold_days: 7, ...}
"""
import sqlite3
import json
import math
from pathlib import Path
from datetime import datetime


MDB = Path("/root/bitt/market.duckdb")
ODB = Path("/root/bitt/oracle.db")
PROFILES_DIR = Path("/root/bitt/trading/profiles")
PROFILES_DIR.mkdir(exist_ok=True)


# === CLASSIFICATION SCHEMA ===
SUBNET_TYPES = {
    "quiet_niche": "Few miners, low pay, unknown — potential sleeper",
    "research_utility": "Research/utility subnet, organic usage, low velocity",
    "infrastructure": "Provides services (compute, storage, APIs)",
    "long_term_miners": "Miners who stake and hold, less selling pressure",
    "competitive_goldrush": "Many miners, high pay — crowded, volatile",
    "exclusive_high_pay": "Few miners, high pay — attracts attention fast",
    "crowded_low_pay": "Many miners, low pay — saturated, declining",
    "balanced": "Neither extreme — default category",
    "dying": "Low activity, negative trajectory, declining",
    "emerging": "Very new, insufficient data to classify",
}

VOL_PROFILES = {
    "ultra_calm": {"range": (0, 0.005), "edge": "high", "description": "Almost no price movement"},
    "calm": {"range": (0.005, 0.02), "edge": "high", "description": "Stable, predictable drift"},
    "moderate": {"range": (0.02, 0.05), "edge": "medium", "description": "Normal volatility"},
    "volatile": {"range": (0.05, 0.10), "edge": "low", "description": "Price swings, harder to predict"},
    "wild": {"range": (0.10, 999), "edge": "none", "description": "Unpredictable, avoid"},
}


def classify_subnet(netuid: int) -> dict:
    """Classify a subnet from raw on-chain data.
    
    Returns structured profile with:
    - type: subnet category
    - vol_profile: volatility classification
    - child_score: likelihood of being a "quiet winner"
    - edge_scores: individual edge measurements
    - recommendations: what to do
    """
    # Load data
    conn = sqlite3.connect(str(ODB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots) '
        'AND json_extract(data, "$.netuid") = ?', (netuid,)
    ).fetchone()
    conn.close()
    
    if not row:
        return {"error": f"SN{netuid} not found in oracle data"}
    
    subnet = json.loads(row['data'])
    
    # Get price history
    conn2 = sqlite3.connect(str(MDB))
    prices = conn2.execute(
        "SELECT alpha_price FROM pool_state WHERE netuid = ? AND alpha_price > 0 ORDER BY timestamp",
        (netuid,)
    ).fetchall()
    price_list = [p[0] for p in prices]
    conn2.close()
    
    if len(price_list) < 10:
        return {"error": f"SN{netuid} insufficient price data ({len(price_list)} points)"}
    
    # === EXTRACT RAW METRICS ===
    neurons = subnet.get('neuron_count', 0)
    active = subnet.get('active_count', 0)
    emission = subnet.get('tao_equiv_day', 0)
    price = price_list[-1]
    
    # Volatility
    rets = [(price_list[i] - price_list[i-1]) / price_list[i-1] 
            for i in range(1, len(price_list)) if price_list[i-1] > 0]
    vol = (sum(r**2 for r in rets) / len(rets)) ** 0.5 if rets else 0
    
    # Trajectory
    q = max(len(price_list) // 5, 1)
    early = sum(price_list[:q]) / q
    late = sum(price_list[-q:]) / q
    trajectory = (late - early) / early if early > 0 else 0
    
    # Returns
    total_return = (price_list[-1] - price_list[0]) / price_list[0] if price_list[0] > 0 else 0
    
    # Ratios
    active_ratio = active / max(neurons, 1)
    emit_per = emission / max(neurons, 1)
    
    # === CLASSIFY TYPE ===
    subnet_type = classify_type(neurons, emit_per, active_ratio, trajectory)
    
    # === CLASSIFY VOL PROFILE ===
    vol_profile = classify_volatility(vol)
    
    # === CALCULATE EDGE SCORES ===
    edge_scores = {
        "low_vol": score_low_vol(vol),
        "positive_trajectory": score_trajectory(trajectory),
        "low_activity": score_low_activity(active_ratio),
        "low_yield": score_low_yield(emit_per),
        "price_level": score_price_level(price),
    }
    
    # === CHILD SUBNET SCORE ===
    child_score = calculate_child_score(vol, trajectory, active_ratio, emit_per, len(price_list))
    
    # === GENERATE RECOMMENDATION ===
    recommendation = generate_recommendation(subnet_type, vol_profile, edge_scores, child_score)
    
    return {
        "netuid": netuid,
        "timestamp": datetime.utcnow().isoformat(),
        "raw_metrics": {
            "neurons": neurons,
            "active": active,
            "emission": emission,
            "price": price,
            "volatility": round(vol, 6),
            "trajectory": round(trajectory, 4),
            "total_return": round(total_return, 4),
            "active_ratio": round(active_ratio, 4),
            "emit_per_neuron": round(emit_per, 4),
            "price_data_points": len(price_list),
        },
        "classification": {
            "type": subnet_type,
            "type_description": SUBNET_TYPES.get(subnet_type, "Unknown"),
            "vol_profile": vol_profile,
            "vol_description": VOL_PROFILES.get(vol_profile, {}).get("description", ""),
        },
        "edge_scores": edge_scores,
        "child_score": child_score,
        "recommendation": recommendation,
    }


def classify_type(neurons, emit_per, active_ratio, trajectory):
    """Classify subnet type from metrics."""
    if neurons < 10 and emit_per > 2.0:
        return "exclusive_high_pay"
    elif neurons > 100 and emit_per < 0.05:
        return "crowded_low_pay"
    elif neurons < 20 and emit_per < 0.1:
        return "quiet_niche"
    elif neurons > 100 and emit_per > 2.0:
        return "competitive_goldrush"
    elif trajectory < -0.1 and active_ratio < 0.05:
        return "dying"
    elif active_ratio > 0.3 and emit_per > 0.5:
        return "long_term_miners"
    elif active_ratio < 0.1 and emit_per < 0.2:
        return "research_utility"
    else:
        return "balanced"


def classify_volatility(vol):
    """Classify volatility profile."""
    for name, info in VOL_PROFILES.items():
        low, high = info["range"]
        if low <= vol < high:
            return name
    return "wild"


def score_low_vol(vol):
    """Score for low volatility edge (0-100)."""
    if vol < 0.002: return 100
    elif vol < 0.005: return 90
    elif vol < 0.01: return 75
    elif vol < 0.02: return 50
    elif vol < 0.05: return 25
    else: return 0


def score_trajectory(traj):
    """Score for positive trajectory (0-100)."""
    if traj > 0.10: return 100
    elif traj > 0.05: return 80
    elif traj > 0: return 60
    elif traj > -0.05: return 30
    else: return 0


def score_low_activity(ratio):
    """Score for low activity (underfollowed) (0-100)."""
    if ratio < 0.03: return 100
    elif ratio < 0.05: return 80
    elif ratio < 0.10: return 60
    elif ratio < 0.20: return 40
    elif ratio < 0.50: return 20
    else: return 0


def score_low_yield(emit_per):
    """Score for low yield (not a trap) (0-100)."""
    if emit_per < 0.05: return 100
    elif emit_per < 0.1: return 80
    elif emit_per < 0.5: return 60
    elif emit_per < 1.0: return 40
    elif emit_per < 5.0: return 10
    else: return 0


def score_price_level(price):
    """Score for price level (higher = more established) (0-100)."""
    if price > 0.1: return 100
    elif price > 0.05: return 80
    elif price > 0.01: return 60
    elif price > 0.005: return 40
    elif price > 0.001: return 20
    else: return 0


def calculate_child_score(vol, traj, active_ratio, emit_per, age_hours):
    """Calculate child subnet potential score (0-100)."""
    score = 0
    
    # Low vol (30%)
    score += score_low_vol(vol) * 0.30
    
    # Positive trajectory (25%)
    score += score_trajectory(traj) * 0.25
    
    # Low activity (20%)
    score += score_low_activity(active_ratio) * 0.20
    
    # Low yield (15%)
    score += score_low_yield(emit_per) * 0.15
    
    # Young (10%)
    if age_hours < 100: score += 10
    elif age_hours < 300: score += 5
    
    return round(score, 1)


def generate_recommendation(subnet_type, vol_profile, edge_scores, child_score):
    """Generate trading recommendation."""
    # Calculate composite edge
    composite = sum(edge_scores.values()) / len(edge_scores)
    
    # Decision logic
    if child_score > 70 and vol_profile in ["ultra_calm", "calm"]:
        action = "BUY"
        confidence = min(0.9, 0.5 + child_score / 200)
        hold_days = 7
        reason = f"High child score ({child_score:.0f}) + calm volatility"
    elif child_score > 50 and vol_profile in ["ultra_calm", "calm"]:
        action = "WATCH"
        confidence = 0.5
        hold_days = 14
        reason = f"Moderate child score ({child_score:.0f}), worth monitoring"
    elif subnet_type in ["dying", "competitive_goldrush"]:
        action = "AVOID"
        confidence = 0.8
        hold_days = 0
        reason = f"Type '{subnet_type}' has poor historical returns"
    elif vol_profile in ["volatile", "wild"]:
        action = "AVOID"
        confidence = 0.7
        hold_days = 0
        reason = f"Volatility too high ({vol_profile})"
    else:
        action = "HOLD"
        confidence = 0.5
        hold_days = 0
        reason = "No clear edge detected"
    
    return {
        "action": action,
        "confidence": round(confidence, 2),
        "hold_days": hold_days,
        "reason": reason,
        "composite_edge": round(composite, 1),
    }


def batch_classify(netuids: list[int]) -> list[dict]:
    """Classify multiple subnets."""
    results = []
    for netuid in netuids:
        profile = classify_subnet(netuid)
        if "error" not in profile:
            results.append(profile)
    return results


if __name__ == "__main__":
    print("=== Subnet Intelligence Engine ===\n")
    
    # Classify top 20 subnets
    conn = sqlite3.connect(str(ODB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    conn.close()
    
    subnets = [json.loads(r['data']) for r in rows]
    netuids = [s.get('netuid', 0) for s in subnets[:20]]
    
    profiles = batch_classify(netuids)
    
    print(f"Classified {len(profiles)} subnets\n")
    
    # Sort by child score
    profiles.sort(key=lambda x: x.get('child_score', 0), reverse=True)
    
    print(f"{'#':<4} {'SN':<5} {'Type':<22} {'Vol':<12} {'Child':<7} {'Action':<8} {'Conf':<6}")
    print("-" * 80)
    for i, p in enumerate(profiles[:15], 1):
        r = p['recommendation']
        print(f"{i:<4} SN{p['netuid']:<4} {p['classification']['type']:<22} "
              f"{p['classification']['vol_profile']:<12} {p['child_score']:<7.0f} "
              f"{r['action']:<8} {r['confidence']:<6.2f}")
    
    # Save profiles
    output = PROFILES_DIR / "latest_profiles.json"
    with open(output, "w") as f:
        json.dump(profiles, f, indent=2)
    print(f"\nSaved to {output}")
