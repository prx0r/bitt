"""Low Fruit Scan v2 — with real entry economics.

Now includes from TAOStats subnet history:
- neuron_registration_cost (actual cost to register as miner)
- collateral_lock_share (collateral requirement)
- max_neurons / active_keys (slot availability)
- recycled_24_hours (registration churn)
- owner_cut, fee_rate, immunity_period
- registration_allowed

The key metric: TIME TO ROI
  days_to_roi = registration_cost_tao / daily_earnings_tao
  
If days_to_roi < 7 → instant fruit
If days_to_roi < 30 → ripe fruit  
If days_to_roi < 90 → maturing fruit
If days_to_roi >= 90 → not worth it
"""
import http.client
import ssl
import json
import sqlite3
import math
import time
from pathlib import Path
from datetime import datetime


KEY = "tao-126d9423-6d33-4b80-aea5-c56dee33b199:605376d4"
CTX = ssl.create_default_context()
ORACLE_DB = Path("/root/bitt/oracle.db")
MARKET_DB = Path("/root/bitt/market.duckdb")


def api(path, params=None, retries=3):
    for attempt in range(retries):
        try:
            query = ""
            if params:
                query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
            conn = http.client.HTTPSConnection("api.taostats.io", timeout=30, context=CTX)
            conn.request("GET", f"/api{path}{query}", headers={"Authorization": KEY})
            data = json.loads(conn.getresponse().read().decode())
            conn.close()
            time.sleep(1.0)  # Rate limit
            return data
        except:
            time.sleep(2 ** attempt)
    return {"error": "failed"}


def fetch_subnet_economics(netuid: int) -> dict:
    """Fetch full economics for a subnet from TAOStats."""
    r = api("/subnet/history/v1", {"netuid": netuid, "limit": 1, "frequency": "by_day"})
    data = r.get("data", [])
    if not data:
        return {}
    return data[0]


def fetch_current_subnets_from_oracle() -> list[dict]:
    """Get current subnet data from oracle.db."""
    conn = sqlite3.connect(str(ORACLE_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
    ).fetchall()
    conn.close()
    return [json.loads(r['data']) for r in rows]


def score_low_fruit_v2(subnet: dict, economics: dict) -> dict:
    """Score subnet for low fruit opportunity with real economics.
    
    Core question: "Can I register for X TAO and earn Y TAO/day?"
    
    Factors (all weighted, nothing excluded):
    1. ROI speed: days_to_roi = reg_cost / daily_earnings
    2. Entry cost: actual neuron_registration_cost in TAO
    3. Slot availability: open_slots / max_slots
    4. Payout reliability: emitting / total ratio
    5. Competition: neurons vs emitting slots
    6. Infrastructure: liquidity, reserve depth
    7. Safety: immunity, deregistration risk, owner trust
    """
    netuid = subnet.get('netuid', 0)
    neurons = subnet.get('neuron_count', 0)
    emitting = subnet.get('emitting_count', 0)
    emission = subnet.get('tao_equiv_day', 0)
    price = subnet.get('alpha_price', 0)
    validators = subnet.get('validator_count', 0)
    active = subnet.get('active_count', 0)
    
    if neurons <= 0 or emission <= 0:
        return {"netuid": netuid, "total": 0, "skip": True}
    
    # === REAL ECONOMICS FROM TAOSTATS ===
    # neuron_registration_cost is in rao (1e-9 TAO)
    reg_cost_rao = float(economics.get("neuron_registration_cost", 0) or 0)
    reg_cost_tao = reg_cost_rao / 1e9
    
    max_neurons = int(economics.get("max_neurons", 256) or 256)
    active_keys = int(economics.get("active_keys", 0) or 0)
    open_slots = max_neurons - active_keys
    
    collateral_share = float(economics.get("collateral_lock_share", 0) or 0)
    fee_rate = float(economics.get("fee_rate", 0) or 0)
    immunity = int(economics.get("immunity_period", 0) or 0)
    activity_cutoff = int(economics.get("activity_cutoff", 5000) or 5000)
    recycled_24h = int(economics.get("recycled_24_hours", 0) or 0)
    registration_allowed = economics.get("registration_allowed", True)
    min_burn = float(economics.get("min_burn", 0) or 0) / 1e9
    max_burn = float(economics.get("max_burn", 0) or 0) / 1e9
    
    # === CORE METRIC: DAYS TO ROI ===
    emission_per = emission / max(emitting, 1)
    # Assume we earn the median emission per neuron
    daily_earnings = emission_per
    # Add staking yield estimate (if we stake 100 TAO)
    staking_yield_per_tao = emission / max(neurons, 1) / price if price > 0 else 0
    
    total_entry_cost = reg_cost_tao
    if collateral_share > 0:
        # Collateral is a % of something — estimate additional cost
        total_entry_cost += reg_cost_tao * collateral_share
    
    days_to_roi = total_entry_cost / max(daily_earnings, 0.0001) if daily_earnings > 0 else 999
    
    # === SCORES (0-100) ===
    
    # 1. ROI SPEED (0-100) — most important for low fruit
    if days_to_roi < 1:
        roi_score = 100
    elif days_to_roi < 3:
        roi_score = 90
    elif days_to_roi < 7:
        roi_score = 80
    elif days_to_roi < 14:
        roi_score = 65
    elif days_to_roi < 30:
        roi_score = 50
    elif days_to_roi < 60:
        roi_score = 35
    elif days_to_roi < 90:
        roi_score = 20
    else:
        roi_score = 5
    
    # 2. ENTRY COST (0-100) — lower = better for low fruit
    if reg_cost_tao <= 0:
        cost_score = 90  # Free or unknown — assume accessible
    elif reg_cost_tao < 0.01:
        cost_score = 95  # Almost free
    elif reg_cost_tao < 0.1:
        cost_score = 85
    elif reg_cost_tao < 1:
        cost_score = 70
    elif reg_cost_tao < 10:
        cost_score = 50
    elif reg_cost_tao < 100:
        cost_score = 30
    else:
        cost_score = 10
    
    # Collateral penalty
    if collateral_share > 0:
        cost_score *= (1 - min(collateral_share, 0.5))
    
    # 3. SLOT AVAILABILITY (0-100)
    slot_ratio = open_slots / max(max_neurons, 1)
    if slot_ratio > 0.5:
        slots_score = 95
    elif slot_ratio > 0.3:
        slots_score = 80
    elif slot_ratio > 0.1:
        slots_score = 60
    elif slot_ratio > 0.05:
        slots_score = 40
    elif open_slots > 0:
        slots_score = 20
    else:
        slots_score = 5  # Full — very hard to enter
    
    # 4. PAYOUT RELIABILITY (0-100)
    emit_ratio = emitting / max(neurons, 1)
    if emit_ratio > 0.8:
        reliability = 90
    elif emit_ratio > 0.6:
        reliability = 75
    elif emit_ratio > 0.4:
        reliability = 55
    elif emit_ratio > 0.2:
        reliability = 35
    else:
        reliability = 15
    
    # Registration churn = activity (high churn = easy to get in)
    if recycled_24h > 10:
        reliability += 10  # Lots of turnover — easy slot
    elif recycled_24h > 3:
        reliability += 5
    
    reliability = min(reliability, 100)
    
    # 5. COMPETITION (0-100)
    competitors_per_slot = neurons / max(open_slots + emitting, 1)
    if competitors_per_slot < 1:
        comp = 95
    elif competitors_per_slot < 2:
        comp = 80
    elif competitors_per_slot < 4:
        comp = 60
    elif competitors_per_slot < 8:
        comp = 40
    else:
        comp = 20
    
    # 6. INFRASTRUCTURE (0-100) — continuous, not binary
    # Use TAO reserve and liquidity as proxies
    infra = 30  # baseline
    # Fee rate indicates active DEX
    if fee_rate > 0:
        infra += 20
    # Validators = network health
    if validators >= 10:
        infra += 20
    elif validators >= 5:
        infra += 12
    elif validators >= 2:
        infra += 5
    # Active miners showing up
    active_ratio = active / max(neurons, 1)
    if active_ratio > 0.8:
        infra += 15
    elif active_ratio > 0.5:
        infra += 8
    # Registration allowed
    if not registration_allowed:
        infra -= 20
    infra = min(max(infra, 0), 100)
    
    # 7. SAFETY (0-100)
    safety = 50
    # Immunity period = protection from deregistration
    if immunity > 10000:
        safety += 20
    elif immunity > 5000:
        safety += 10
    # Activity cutoff = how long before you're at risk
    if activity_cutoff > 3000:
        safety += 15
    elif activity_cutoff > 1000:
        safety += 8
    # Low recycling = stable subnet
    if recycled_24h < 3:
        safety += 10
    elif recycled_24h > 20:
        safety -= 10  # High churn = risky
    safety = min(max(safety, 0), 100)
    
    # === COMBINED LOW FRUIT SCORE ===
    # Weights: ROI 35%, cost 20%, slots 15%, reliability 10%, comp 10%, infra 5%, safety 5%
    total = (
        roi_score * 0.35 +
        cost_score * 0.20 +
        slots_score * 0.15 +
        reliability * 0.10 +
        comp * 0.10 +
        infra * 0.05 +
        safety * 0.05
    )
    
    # Fruit ripeness label
    if days_to_roi < 7:
        ripeness = "INSTANT"
    elif days_to_roi < 30:
        ripeness = "RIPE"
    elif days_to_roi < 90:
        ripeness = "MATURING"
    else:
        ripeness = "UNRIPE"
    
    return {
        "netuid": netuid,
        "total": round(total, 1),
        "roi_score": round(roi_score, 1),
        "cost_score": round(cost_score, 1),
        "slots_score": round(slots_score, 1),
        "reliability": round(reliability, 1),
        "comp_score": round(comp, 1),
        "infra_score": round(infra, 1),
        "safety": round(safety, 1),
        # Real economics
        "reg_cost_tao": round(reg_cost_tao, 6),
        "daily_earnings": round(daily_earnings, 6),
        "days_to_roi": round(days_to_roi, 1),
        "total_entry_cost": round(total_entry_cost, 6),
        "collateral_share": collateral_share,
        "open_slots": open_slots,
        "max_neurons": max_neurons,
        "slot_ratio": round(slot_ratio, 4),
        "recycled_24h": recycled_24h,
        "registration_allowed": registration_allowed,
        # Existing metrics
        "emitting": emitting,
        "neurons": neurons,
        "emission_per": round(emission_per, 4),
        "emit_ratio": round(emit_ratio, 4),
        "ripeness": ripeness,
        "skip": False,
    }


if __name__ == "__main__":
    print("=== Low Fruit Scan v2 — with real entry economics ===\n")
    
    # Get oracle data
    subnets = fetch_current_subnets_from_oracle()
    print(f"Subnets from oracle: {len(subnets)}")
    
    # Fetch economics for each (rate limited)
    results = []
    for i, subnet in enumerate(subnets):
        netuid = subnet.get('netuid', 0)
        econ = fetch_subnet_economics(netuid)
        if not econ:
            continue
        
        score = score_low_fruit_v2(subnet, econ)
        if not score.get("skip"):
            results.append(score)
        
        if netuid % 20 == 0:
            print(f"  Scored SN{netuid}... ({len(results)} done)")
    
    results.sort(key=lambda x: x["total"], reverse=True)
    
    # Save
    output = Path("/root/bitt/trading/experiments/low_fruit_v2.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    
    # Print top 25
    print(f"\n{'='*100}")
    print(f"LOW FRUIT SCAN v2 — {len(results)} subnets with economics")
    print(f"{'='*100}")
    print(f"{'#':<4} {'SN':<5} {'Score':<7} {'ROI':<6} {'Days':<7} {'Cost(TAO)':<12} {'Earn/d':<10} {'Slots':<7} {'Open':<6} {'Ripe':<10} {'Churn'}")
    print("-" * 100)
    
    for i, r in enumerate(results[:25], 1):
        print(f"{i:<4} SN{r['netuid']:<4} {r['total']:<7.1f} {r['roi_score']:<6.0f} "
              f"{r['days_to_roi']:<7.1f} {r['reg_cost_tao']:<12.6f} "
              f"{r['daily_earnings']:<10.6f} {r['max_neurons']:<7} "
              f"{r['open_slots']:<6} {r['ripeness']:<10} {r['recycled_24h']}")
    
    # Summary
    ripeness = {}
    for r in results:
        rip = r["ripeness"]
        ripeness[rip] = ripeness.get(rip, 0) + 1
    
    print(f"\nRipeness distribution:")
    for rip in ["INSTANT", "RIPE", "MATURING", "UNRIPE"]:
        print(f"  {rip}: {ripeness.get(rip, 0)}")
    
    # Instant fruit details
    instant = [r for r in results if r["ripeness"] == "INSTANT"]
    if instant:
        print(f"\nINSTANT FRUIT (ROI < 7 days):")
        for r in instant:
            print(f"  SN{r['netuid']}: {r['days_to_roi']:.1f}d ROI, "
                  f"cost={r['reg_cost_tao']:.6f} TAO, "
                  f"earn={r['daily_earnings']:.6f}/d, "
                  f"{r['open_slots']} open slots")
    
    print(f"\nSaved to {output}")
