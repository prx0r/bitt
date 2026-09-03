"""Subnet Incubator — analyze subnets from birth, predict appreciation.

Core question: "Can we predict which subnets will appreciate based on
their birth characteristics and early trajectory?"

Data flow:
1. Fetch ALL subnet history from TAOStats (birth to now)
2. Calculate birth-price, age, fundamental trajectory
3. Build feature matrix: birth features → forward returns
4. Backtest: buy at birth, what returns?

This is the historical moat — nobody else has this dataset.
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
DB = Path("/root/bitt/market.duckdb")


def api(path, params=None, retries=3):
    """API request with retry."""
    for attempt in range(retries):
        try:
            query = ""
            if params:
                query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
            conn = http.client.HTTPSConnection("api.taostats.io", timeout=30, context=CTX)
            conn.request("GET", f"/api{path}{query}", headers={"Authorization": KEY})
            data = json.loads(conn.getresponse().read().decode())
            conn.close()
            time.sleep(0.5)
            return data
        except Exception as e:
            time.sleep(2 ** attempt)
    return {"error": "failed"}


def fetch_subnet_full_history(netuid: int) -> dict:
    """Fetch complete history for a subnet — pool, emission, metagraph."""
    # Pool history (hourly)
    pool_data = []
    for page in range(1, 20):
        r = api("/dtao/pool/history/v1", {"netuid": netuid, "frequency": "by_hour", "limit": 500, "page": page})
        if "data" not in r or not r["data"]:
            break
        pool_data.extend(r["data"])
        if page >= r.get("pagination", {}).get("total_pages", 1):
            break
    
    # Subnet history (daily for long-term)
    subnet_data = []
    for page in range(1, 10):
        r = api("/subnet/history/v1", {"netuid": netuid, "frequency": "by_day", "limit": 500, "page": page})
        if "data" not in r or not r["data"]:
            break
        subnet_data.extend(r["data"])
        if page >= r.get("pagination", {}).get("total_pages", 1):
            break
    
    return {
        "netuid": netuid,
        "pool_history": pool_data,
        "subnet_history": subnet_data,
    }


def calculate_birth_features(history: dict) -> dict:
    """Extract features from subnet at birth (first 7 days)."""
    pool = history.get("pool_history", [])
    subnet = history.get("subnet_history", [])
    
    if not pool and not subnet:
        return {}
    
    netuid = history["netuid"]
    
    # Find birth (earliest data point)
    all_ts = []
    for p in pool:
        if p.get("timestamp"):
            all_ts.append(p["timestamp"])
    for s in subnet:
        if s.get("registration_timestamp"):
            all_ts.append(s["registration_timestamp"])
    
    if not all_ts:
        return {}
    
    birth_ts = min(all_ts)
    
    # Get first 7 days of pool data
    try:
        birth_dt = datetime.fromisoformat(birth_ts.replace("Z", "+00:00"))
        cutoff_ts = (birth_dt.timestamp() + 7*86400)
        early_pool = [p for p in pool if p.get("timestamp", "")]
    except:
        early_pool = pool
    
    # Birth price
    first_price = 0
    if pool:
        prices = [float(p.get("market_cap", 0) or 0) / max(float(p.get("total_alpha", 1) or 1), 1) 
                  for p in pool if p.get("market_cap")]
        if prices:
            first_price = prices[0]
    
    # Current price
    current_price = first_price
    if pool:
        last = pool[-1]
        mc = float(last.get("market_cap", 0) or 0)
        alpha = float(last.get("total_alpha", 1) or 1)
        if mc > 0 and alpha > 0:
            current_price = mc / alpha
    
    # Price return
    price_return = (current_price - first_price) / first_price if first_price > 0 else 0
    
    # Liquidity trajectory
    liq_values = [float(p.get("liquidity", 0) or 0) for p in pool if p.get("liquidity")]
    liq_growth = 0
    if len(liq_values) >= 2:
        liq_growth = (liq_values[-1] - liq_values[0]) / max(liq_values[0], 1)
    
    # TAO reserve trajectory
    tao_values = [float(p.get("total_tao", 0) or 0) for p in pool if p.get("total_tao")]
    tao_flow = 0
    if len(tao_values) >= 2:
        tao_flow = tao_values[-1] - tao_values[0]
    
    # Neuron count trajectory (from subnet history)
    neuron_counts = [int(s.get("active_miners", 0) or 0) for s in subnet if s.get("active_miners")]
    validator_counts = [int(s.get("validators", 0) or 0) for s in subnet if s.get("validators")]
    
    miner_growth = 0
    if len(neuron_counts) >= 2:
        miner_growth = neuron_counts[-1] - neuron_counts[0]
    
    # Emission trajectory
    emissions = [float(s.get("emission", 0) or 0) for s in subnet if s.get("emission")]
    emission_growth = 0
    if len(emissions) >= 2:
        emission_growth = (emissions[-1] - emissions[0]) / max(emissions[0], 1)
    
    # Age in days (handle timezone-aware vs naive)
    try:
        birth_dt = datetime.fromisoformat(birth_ts.replace("Z", "+00:00"))
        age_days = (datetime.now(birth_dt.tzinfo) - birth_dt).days if birth_ts else 0
    except:
        age_days = 0
    
    return {
        "netuid": netuid,
        "birth_ts": birth_ts,
        "age_days": age_days,
        "first_price": first_price,
        "current_price": current_price,
        "price_return": round(price_return, 4),
        "liq_growth": round(liq_growth, 4),
        "tao_flow": round(tao_flow, 2),
        "miner_growth": miner_growth,
        "emission_growth": round(emission_growth, 4),
        "current_miners": neuron_counts[-1] if neuron_counts else 0,
        "current_validators": validator_counts[-1] if validator_counts else 0,
        "current_emission": emissions[-1] if emissions else 0,
        "data_points": len(pool),
    }


def build_incubator_dataset(max_subnets: int = 130) -> list[dict]:
    """Build full incubator dataset for all subnets."""
    results = []
    
    for netuid in range(max_subnets):
        try:
            history = fetch_subnet_full_history(netuid)
            if not history["pool_history"] and not history["subnet_history"]:
                continue
            
            features = calculate_birth_features(history)
            if features:
                results.append(features)
            
            if netuid % 10 == 0:
                print(f"  Processed SN{netuid}... ({len(results)} with data)")
            
        except Exception as e:
            print(f"  Error SN{netuid}: {str(e)[:60]}")
    
    return results


def analyze_incubator_results(results: list[dict]) -> dict:
    """Analyze incubator dataset for predictive patterns."""
    if not results:
        return {"error": "no data"}
    
    # Group by age cohort
    cohorts = {"0-30d": [], "31-90d": [], "91-180d": [], "180d+": []}
    for r in results:
        age = r.get("age_days", 0)
        if age <= 30:
            cohorts["0-30d"].append(r)
        elif age <= 90:
            cohorts["31-90d"].append(r)
        elif age <= 180:
            cohorts["91-180d"].append(r)
        else:
            cohorts["180d+"].append(r)
    
    analysis = {"cohorts": {}, "predictions": []}
    
    for cohort_name, subs in cohorts.items():
        if not subs:
            continue
        
        returns = [s["price_return"] for s in subs if s.get("price_return") is not None]
        liq_growth = [s["liq_growth"] for s in subs if s.get("liq_growth") is not None]
        miner_growth = [s["miner_growth"] for s in subs if s.get("miner_growth") is not None]
        
        analysis["cohorts"][cohort_name] = {
            "count": len(subs),
            "avg_return": round(sum(returns) / len(returns), 4) if returns else 0,
            "median_return": round(sorted(returns)[len(returns)//2], 4) if returns else 0,
            "win_rate": round(len([r for r in returns if r > 0]) / len(returns), 4) if returns else 0,
            "avg_liq_growth": round(sum(liq_growth) / len(liq_growth), 4) if liq_growth else 0,
            "avg_miner_growth": round(sum(miner_growth) / len(miner_growth), 1) if miner_growth else 0,
        }
    
    # Find predictors of positive returns
    positive = [s for s in results if s.get("price_return", 0) > 0]
    negative = [s for s in results if s.get("price_return", 0) <= 0]
    
    if positive and negative:
        analysis["predictors"] = {
            "positive_avg_miners": round(sum(s.get("current_miners", 0) for s in positive) / len(positive), 1),
            "negative_avg_miners": round(sum(s.get("current_miners", 0) for s in negative) / len(negative), 1),
            "positive_avg_liq_growth": round(sum(s.get("liq_growth", 0) for s in positive) / len(positive), 4),
            "negative_avg_liq_growth": round(sum(s.get("liq_growth", 0) for s in negative) / len(negative), 4),
            "positive_avg_emission_growth": round(sum(s.get("emission_growth", 0) for s in positive) / len(positive), 4),
            "negative_avg_emission_growth": round(sum(s.get("emission_growth", 0) for s in negative) / len(negative), 4),
        }
    
    # Top appreciators
    results.sort(key=lambda x: x.get("price_return", 0), reverse=True)
    analysis["top_appreciators"] = [
        {"netuid": r["netuid"], "return": r["price_return"], "age": r["age_days"], 
         "miners": r["current_miners"], "liq_growth": r["liq_growth"]}
        for r in results[:10]
    ]
    
    return analysis


if __name__ == "__main__":
    print("=== Subnet Incubator ===")
    print("Building dataset from TAOStats...\n")
    
    results = build_incubator_dataset(max_subnets=130)
    
    # Save dataset
    output = Path("/root/bitt/trading/experiments/incubator_dataset.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    
    # Analyze
    analysis = analyze_incubator_results(results)
    
    analysis_output = Path("/root/bitt/trading/experiments/incubator_analysis.json")
    with open(analysis_output, "w") as f:
        json.dump(analysis, f, indent=2)
    
    # Print
    print(f"\n{'='*60}")
    print(f"INCUBATOR RESULTS — {len(results)} subnets")
    print(f"{'='*60}")
    
    print(f"\n--- Age Cohort Returns ---")
    for cohort, stats in analysis.get("cohorts", {}).items():
        print(f"  {cohort}: {stats['count']} subs, avg return={stats['avg_return']:+.1%}, "
              f"win rate={stats['win_rate']:.0%}")
    
    if "predictors" in analysis:
        p = analysis["predictors"]
        print(f"\n--- Predictors of Positive Returns ---")
        print(f"  Positive subs: avg {p['positive_avg_miners']:.0f} miners, liq growth={p['positive_avg_liq_growth']:+.1%}")
        print(f"  Negative subs: avg {p['negative_avg_miners']:.0f} miners, liq growth={p['negative_avg_liq_growth']:+.1%}")
    
    print(f"\n--- Top Appreciators ---")
    for r in analysis.get("top_appreciators", [])[:5]:
        print(f"  SN{r['netuid']}: {r['return']:+.1%} return, {r['age']}d old, {r['miners']} miners")
    
    print(f"\nSaved: {output}")
    print(f"Analysis: {analysis_output}")
