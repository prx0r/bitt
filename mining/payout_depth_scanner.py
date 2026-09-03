"""Payout Depth Scanner — CP0 from Oracle email.

Scans all subnets and calculates:
- N_0.25, N_0.5, N_1, N_2, N_5 (miners earning >= threshold TAO/day)
- paid_miners, median_paid_tao_day, p10-p90
- top1_share, top3_share, top10_share, HHI, Gini
- TAO_DEPTH_1 = N_1 (most important metric)
- ENTRY_PERCENTILE_1TAO = N_1 / realistic_miner_population

This is the foundation for the Low Competition Miner strategy.
"""
import bittensor as bt
import json
import sqlite3
import math
from pathlib import Path


DB_PATH = Path("/root/bitt/oracle.db")


def fetch_subnet_emission_vector(netuid: int) -> dict:
    """Fetch emission vector for a subnet from the chain.
    
    Returns per-miner emission data needed for payout depth analysis.
    """
    sub = bt.Subtensor(network="finney")
    block = sub.block
    
    try:
        # Get metagraph
        chain = sub.at(block)
        mg = chain.subnets.metagraph(netuid)
        
        # Extract miner emissions
        miners = []
        for n in mg.neurons:
            try:
                emission_rao = float(n.emission.rao) if hasattr(n.emission, 'rao') else 0.0
                emission_tao_day = emission_rao / 1e9 * 7200  # Convert rao to TAO/day (rough)
                stake = float(n.total_stake.rao) if hasattr(n.total_stake, 'rao') else 0.0
                incentive = float(n.incentive) if hasattr(n, 'incentive') else 0.0
                dividends = float(n.dividends) if hasattr(n, 'dividends') else 0.0
            except:
                emission_tao_day = 0.0
                stake = 0.0
                incentive = 0.0
                dividends = 0.0
            
            miners.append({
                "uid": n.uid,
                "hotkey": n.hotkey if hasattr(n, 'hotkey') else "",
                "emission_tao_day": emission_tao_day,
                "stake": stake,
                "incentive": incentive,
                "dividends": dividends,
                "active": n.active if hasattr(n, 'active') else False,
            })
        
        # Get subnet info
        try:
            subnet_info = sub.subnets.get_subnet_info(netuid)
            burn = float(subnet_info.tao_weight) if hasattr(subnet_info, 'tao_weight') else 0.0
            owner_cut = float(subnet_info.owner_cut) if hasattr(subnet_info, 'owner_cut') else 0.0
            emission_enabled = True  # Default
        except:
            burn = 0.0
            owner_cut = 0.0
            emission_enabled = True
        
        return {
            "netuid": netuid,
            "block": block,
            "miners": miners,
            "burn": burn,
            "owner_cut": owner_cut,
            "emission_enabled": emission_enabled,
        }
        
    except Exception as e:
        return {"netuid": netuid, "error": str(e), "miners": []}


def calculate_payout_depth(emission_data: dict) -> dict:
    """Calculate payout depth metrics from emission vector.
    
    Key metrics:
    - N_X: number of miners earning >= X TAO/day
    - HHI: Herfindahl-Hirschman Index (concentration)
    - Gini: inequality coefficient
    - TAO_DEPTH_1: most important metric
    """
    miners = emission_data.get("miners", [])
    if not miners:
        return {"netuid": emission_data.get("netuid", 0), "error": "no data"}
    
    netuid = emission_data.get("netuid", 0)
    
    # Filter to active miners with emissions
    active_miners = [m for m in miners if m.get("active", False)]
    earning_miners = [m for m in active_miners if m.get("emission_tao_day", 0) > 0]
    
    # Emission values in TAO/day
    emissions = sorted([m["emission_tao_day"] for m in earning_miners], reverse=True)
    
    if not emissions:
        return {"netuid": netuid, "error": "no earning miners"}
    
    total_emission = sum(emissions)
    
    # N_X: miners earning >= threshold TAO/day
    thresholds = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
    n_x = {}
    for t in thresholds:
        n_x[f"N_{t}"] = len([e for e in emissions if e >= t])
    
    # Percentiles
    n = len(emissions)
    p10 = emissions[min(int(n * 0.9), n - 1)]
    p25 = emissions[min(int(n * 0.75), n - 1)]
    p50 = emissions[min(int(n * 0.5), n - 1)]  # median
    p75 = emissions[min(int(n * 0.25), n - 1)]
    p90 = emissions[0] if emissions else 0  # top earner
    
    # Shares
    top1_share = emissions[0] / total_emission if total_emission > 0 and emissions else 0
    top3_share = sum(emissions[:3]) / total_emission if total_emission > 0 else 0
    top10_share = sum(emissions[:10]) / total_emission if total_emission > 0 else 0
    
    # HHI (Herfindahl-Hirschman Index)
    shares = [e / total_emission for e in emissions] if total_emission > 0 else []
    hhi = sum(s ** 2 for s in shares) if shares else 0
    
    # Gini coefficient
    if n > 1:
        sorted_em = sorted(emissions)
        gini_num = sum((2 * i - n - 1) * sorted_em[i] for i in range(n))
        gini = gini_num / (n * sum(sorted_em)) if sum(sorted_em) > 0 else 0
    else:
        gini = 0
    
    # TAO_DEPTH_1 (most important)
    tao_depth_1 = n_x.get("N_1.0", 0)
    
    # Entry percentile
    realistic_pop = max(len(earning_miners), 1)
    entry_percentile = tao_depth_1 / realistic_pop
    
    return {
        "netuid": netuid,
        "block": emission_data.get("block", 0),
        "total_miners": len(miners),
        "active_miners": len(active_miners),
        "earning_miners": len(earning_miners),
        "total_emission_tao_day": total_emission,
        **n_x,
        "median_paid_tao_day": p50,
        "p10": p10,
        "p25": p25,
        "p75": p75,
        "p90": p90,
        "top1_share": top1_share,
        "top3_share": top3_share,
        "top10_share": top10_share,
        "hhi": hhi,
        "gini": gini,
        "tao_depth_1": tao_depth_1,
        "entry_percentile_1tao": entry_percentile,
        "owner_cut": emission_data.get("owner_cut", 0),
        "emission_enabled": emission_data.get("emission_enabled", True),
    }


def classify_payout_topology(depth: dict) -> str:
    """Classify payout topology based on depth metrics.
    
    Returns one of:
    - PROPORTIONAL (highest priority)
    - BROAD_PARTICIPATION (highest priority)
    - DECAYING_PORTFOLIO (high priority)
    - TOP_K (depends on K)
    - WINNER_TAKE_ALL (jackpot queue)
    - BOUNTY
    - UNKNOWN
    """
    hhi = depth.get("hhi", 0)
    gini = depth.get("gini", 0)
    n_1 = depth.get("tao_depth_1", 0)
    top1_share = depth.get("top1_share", 0)
    earning = depth.get("earning_miners", 0)
    
    if earning == 0:
        return "UNKNOWN"
    
    # Winner-take-all: one miner gets almost everything
    if top1_share > 0.8 or hhi > 0.5:
        return "WINNER_TAKE_ALL"
    
    # Broad participation: many miners earning > 1 TAO/day
    if n_1 >= 10 and gini < 0.5:
        return "BROAD_PARTICIPATION"
    
    # Proportional: moderate distribution
    if gini < 0.6 and n_1 >= 3:
        return "PROPORTIONAL"
    
    # Top-K: few miners dominate
    if top1_share > 0.5 or gini > 0.7:
        return "TOP_K"
    
    return "UNKNOWN"


def calculate_income_score(depth: dict) -> float:
    """Calculate income score for mining opportunity.
    
    From email spec:
    income_score = (
        5.0 * log1p(N_1)
      + 3.0 * log1p(N_0_5)
      + 2.0 * log1p(N_0_25)
      + 2.0 * min(median_paid_tao_day, 3)
      + 1.5 * payout_persistence_7d
      + 1.0 * open_slot_score
      - 2.0 * sunk_burn_tao
      - 2.0 * churn_risk
      - 3.0 * mechanism_uncertainty
    )
    """
    n_1 = depth.get("tao_depth_1", 0)
    n_05 = depth.get("N_0.5", 0)
    n_025 = depth.get("N_0.25", 0)
    median = depth.get("median_paid_tao_day", 0)
    hhi = depth.get("hhi", 0)
    
    # Simplified version (no persistence/churn data yet)
    score = (
        5.0 * math.log1p(n_1)
      + 3.0 * math.log1p(n_05)
      + 2.0 * math.log1p(n_025)
      + 2.0 * min(median, 3)
      - 2.0 * hhi  # Higher concentration = worse
    )
    
    return round(score, 2)


def scan_all_subnets(max_subnets: int = 130) -> list[dict]:
    """Run payout depth scan on all subnets."""
    results = []
    
    for netuid in range(max_subnets):
        try:
            emission = fetch_subnet_emission_vector(netuid)
            if "error" in emission:
                continue
            
            depth = calculate_payout_depth(emission)
            if "error" in depth:
                continue
            
            depth["payout_topology"] = classify_payout_topology(depth)
            depth["income_score"] = calculate_income_score(depth)
            
            results.append(depth)
            
            if netuid % 10 == 0:
                print(f"  Scanned {netuid}/130 subnets...")
                
        except Exception as e:
            print(f"  Error SN{netuid}: {str(e)[:80]}")
    
    return sorted(results, key=lambda x: x.get("income_score", 0), reverse=True)


if __name__ == "__main__":
    print("=== Payout Depth Scanner (CP0) ===")
    print()
    
    results = scan_all_subnets(max_subnets=130)
    
    # Save results
    output = Path("/root/bitt/trading/experiments/payout_depth_scan.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    
    # Print top 15
    print(f"\n=== TOP 15 MINING OPPORTUNITIES ===")
    print(f"{'Rank':<5} {'SN':<5} {'Score':<8} {'N_1':<5} {'N_0.5':<6} {'Median':<8} {'HHI':<6} {'Topology':<20}")
    print("-" * 70)
    
    for i, r in enumerate(results[:15], 1):
        print(f"{i:<5} {r['netuid']:<5} {r['income_score']:<8.1f} "
              f"{r.get('tao_depth_1', 0):<5} {r.get('N_0.5', 0):<6} "
              f"{r.get('median_paid_tao_day', 0):<8.4f} "
              f"{r.get('hhi', 0):<6.3f} {r.get('payout_topology', 'UNK'):<20}")
    
    print(f"\nTotal subnets scanned: {len(results)}")
    print(f"Results saved to: {output}")
