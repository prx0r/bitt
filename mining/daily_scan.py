"""Daily Mining Scanner — single command, stores to DB, agent-runnable.

Run: python3 mining/daily_scan.py
Output: mining/scan_results.json + DB update + console report
"""
import bittensor as bt
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime


DB_PATH = Path("/root/bitt/market.duckdb")
RESULTS_DIR = Path("/root/bitt/mining/scan_results")
RESULTS_DIR.mkdir(exist_ok=True)


def init_db():
    """Create mining_scan table."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mining_scan (
            scan_id TEXT NOT NULL,
            scan_date TEXT NOT NULL,
            block INTEGER,
            netuid INTEGER,
            neurons INTEGER,
            active INTEGER,
            emitting INTEGER,
            emission_tao REAL,
            per_neuron_tao REAL,
            top1_share REAL,
            median_payout REAL,
            competition_ratio REAL,
            score REAL,
            tier TEXT,
            PRIMARY KEY (scan_id, netuid)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mining_scan_log (
            scan_id TEXT PRIMARY KEY,
            scan_date TEXT,
            block INTEGER,
            subnets_scanned INTEGER,
            top_opportunities TEXT,
            duration_seconds INTEGER
        )
    """)
    conn.commit()
    conn.close()


def score_mining_opportunity(r):
    """Score a mining opportunity (0-100). Higher = easier to profit."""
    score = 0
    
    # Yield per neuron (higher = better)
    if r["per_neuron"] > 100: score += 30
    elif r["per_neuron"] > 50: score += 20
    elif r["per_neuron"] > 20: score += 10
    
    # Competition (lower = better)
    if r["comp"] < 0.05: score += 30
    elif r["comp"] < 0.10: score += 20
    elif r["comp"] < 0.20: score += 10
    elif r["comp"] < 0.50: score += 5
    
    # Seat availability (fewer emitting = more opportunity)
    if r["emitting"] <= 5: score += 20
    elif r["emitting"] <= 10: score += 15
    elif r["emitting"] <= 20: score += 10
    
    # Payout distribution (lower top1 = more distributed)
    if r["top1"] < 0.3: score += 10
    elif r["top1"] < 0.5: score += 5
    
    # Registration cost (all ~0.0005 TAO)
    score += 5
    
    # Tier classification
    if score >= 70: tier = "TIER_A"
    elif score >= 50: tier = "TIER_B"
    elif score >= 30: tier = "TIER_C"
    else: tier = "TIER_D"
    
    return score, tier


def run_scan():
    """Run full mining landscape scan."""
    start = time.time()
    sub = bt.Subtensor(network="finney")
    block = sub.block
    
    print(f"=== Mining Landscape Scan — Block {block} ===\n")
    
    all_subnets = []
    for netuid in range(130):
        try:
            chain = sub.at(block)
            mg = chain.subnets.metagraph(netuid)
            neurons = []
            for n in mg.neurons:
                try:
                    emission = float(n.emission.rao) if hasattr(n.emission, 'rao') else 0
                    neurons.append({"uid": n.uid, "active": n.active, "emission": emission})
                except: pass
            
            if not neurons: continue
            
            total_emission = sum(n["emission"] for n in neurons)
            active_count = sum(1 for n in neurons if n["active"])
            emitting = sum(1 for n in neurons if n["emission"] > 0)
            emissions = sorted([n["emission"] for n in neurons if n["emission"] > 0], reverse=True)
            
            top1 = emissions[0] / max(total_emission, 1) if emissions else 0
            median = emissions[len(emissions)//2] / 1e9 if emissions else 0
            
            r = {
                "netuid": netuid, "neurons": len(neurons), "active": active_count,
                "emitting": emitting, "emission_tao": total_emission / 1e9,
                "per_neuron": total_emission / max(emitting, 1) / 1e9,
                "top1": top1, "median": median,
                "comp": emitting / max(len(neurons), 1),
            }
            
            score, tier = score_mining_opportunity(r)
            r["score"] = score
            r["tier"] = tier
            all_subnets.append(r)
            
            time.sleep(1.5)
        except:
            time.sleep(2)
    
    duration = int(time.time() - start)
    scan_id = datetime.utcnow().strftime("%Y%m%dT%H%M")
    
    # Store to DB
    conn = sqlite3.connect(str(DB_PATH))
    for r in all_subnets:
        conn.execute(
            "INSERT OR REPLACE INTO mining_scan VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (scan_id, datetime.utcnow().isoformat(), block, r["netuid"], r["neurons"],
             r["active"], r["emitting"], r["emission_tao"], r["per_neuron"],
             r["top1"], r["median"], r["comp"], r["score"], r["tier"])
        )
    
    # Top opportunities
    top = sorted(all_subnets, key=lambda x: x["score"], reverse=True)[:10]
    conn.execute(
        "INSERT OR REPLACE INTO mining_scan_log VALUES (?,?,?,?,?,?)",
        (scan_id, datetime.utcnow().isoformat(), block, len(all_subnets),
         json.dumps([{"sn": r["netuid"], "score": r["score"], "tier": r["tier"]} for r in top]),
         duration)
    )
    conn.commit()
    conn.close()
    
    # Save JSON
    with open(RESULTS_DIR / f"scan_{scan_id}.json", "w") as f:
        json.dump({"scan_id": scan_id, "block": block, "subnets": all_subnets, "top": top}, f, indent=2)
    
    # Print report
    print(f"\n{'SN':<5} {'Score':<7} {'Tier':<8} {'Emit/N':<10} {'Emitting':<9} {'Comp':<8} {'Median'}")
    print("-" * 70)
    for r in top:
        print(f"SN{r['netuid']:<3} {r['score']:<7} {r['tier']:<8} {r['per_neuron']:<10.1f} {r['emitting']:<9} {r['comp']:<8.0%} {r['median']:<10.4f}")
    
    print(f"\nScan {scan_id}: {len(all_subnets)} subnets in {duration}s")
    return all_subnets, top


if __name__ == "__main__":
    init_db()
    run_scan()
