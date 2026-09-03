"""Steady Collection Runner — slow but reliable data pipeline.

Runs every 6 hours, collects what it can, stores everything.
No rushing, no rate limit fights. Just steady accumulation.

Usage:
  python3 steady_collector.py          # Run once
  python3 steady_collector.py --daemon  # Run every 6 hours
"""
import bittensor as bt
import json
import sqlite3
import time
import sys
from pathlib import Path
from datetime import datetime


MARKET_DB = Path("/root/bitt/market.duckdb")
ORACLE_DB = Path("/root/bitt/oracle.db")
STATE_FILE = Path("/root/bitt/trading/experiments/collection_state.json")
DELAY_BETWEEN_SUBNETS = 3.0  # seconds


def load_state() -> dict:
    """Load collection progress."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_netuid": 0, "last_block": 0, "total_collected": 0, "errors": 0}


def save_state(state: dict):
    """Save collection progress."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def collect_one_subnet(netuid: int, block: int, sub) -> bool:
    """Collect data for one subnet. Returns True on success."""
    try:
        chain = sub.at(block)
        mg = chain.subnets.metagraph(netuid)
        
        neurons = []
        for n in mg.neurons:
            try:
                neurons.append({
                    "uid": n.uid,
                    "hotkey": n.hotkey if hasattr(n, 'hotkey') else "",
                    "coldkey": n.coldkey if hasattr(n, 'coldkey') else "",
                    "active": 1 if n.active else 0,
                    "stake": float(n.total_stake.rao) if hasattr(n.total_stake, 'rao') else 0,
                    "incentive": float(n.incentive) if hasattr(n, 'incentive') else 0,
                    "dividends": float(n.dividends) if hasattr(n, 'dividends') else 0,
                    "emission": float(n.emission.rao) if hasattr(n.emission, 'rao') else 0,
                })
            except:
                pass
        
        # Aggregate
        active = [n for n in neurons if n["active"]]
        emitting = [n for n in neurons if n["emission"] > 0]
        total_emission = sum(n["emission"] for n in neurons)
        total_stake = sum(n["stake"] for n in neurons)
        
        # HHI
        if emitting:
            total_inc = sum(n["incentive"] for n in neurons if n["incentive"] > 0)
            if total_inc > 0:
                shares = [n["incentive"] / total_inc for n in neurons if n["incentive"] > 0]
                hhi = sum(s ** 2 for s in shares)
            else:
                hhi = 1.0
        else:
            hhi = 1.0
        
        # Store
        conn = sqlite3.connect(str(MARKET_DB))
        
        # Metagraph snapshot
        for n in neurons:
            conn.execute(
                "INSERT OR REPLACE INTO metagraph_snapshot "
                "(block, netuid, uid, hotkey, coldkey, active, stake, stake, "
                "incentive, dividends, emission, trust, consensus, validator_trust, "
                "rank, validator_permit, updated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0)",
                (block, netuid, n["uid"], n["hotkey"], n["coldkey"], n["active"],
                 n["stake"], n["stake"], n["incentive"], n["dividends"], n["emission"])
            )
        
        # Subnet metrics
        conn.execute(
            "INSERT OR REPLACE INTO subnet_metrics_live "
            "(block, netuid, emitting_count, total_emission, total_stake, hhi_incentive) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (block, netuid, len(emitting), total_emission, total_stake, hhi)
        )
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        return False


def run_collection_batch(state: dict, max_subnets: int = 20) -> dict:
    """Collect a batch of subnets (respecting rate limits)."""
    sub = bt.Subtensor(network="finney")
    block = sub.block
    
    start_netuid = state["last_netuid"]
    collected = 0
    errors = 0
    
    for netuid in range(start_netuid, start_netuid + max_subnets):
        if netuid >= 130:
            break
        
        success = collect_one_subnet(netuid, block, sub)
        
        if success:
            collected += 1
            state["total_collected"] += 1
        else:
            errors += 1
            state["errors"] += 1
        
        state["last_netuid"] = netuid + 1
        state["last_block"] = block
        
        time.sleep(DELAY_BETWEEN_SUBNETS)
    
    state["last_run"] = datetime.utcnow().isoformat()
    save_state(state)
    
    return {
        "collected": collected,
        "errors": errors,
        "block": block,
        "next_netuid": state["last_netuid"],
    }


if __name__ == "__main__":
    print("=== Steady Collection Runner ===\n")
    
    state = load_state()
    print(f"Starting from SN{state['last_netuid']}")
    print(f"Previously collected: {state['total_collected']}")
    
    if "--daemon" in sys.argv:
        print("Running in daemon mode (every 6 hours)...")
        while True:
            try:
                result = run_collection_batch(state, max_subnets=20)
                print(f"[{datetime.utcnow().isoformat()}] Collected {result['collected']}, "
                      f"errors {result['errors']}, next SN{result['next_netuid']}")
            except Exception as e:
                print(f"Error: {e}")
            
            time.sleep(6 * 3600)  # 6 hours
    else:
        result = run_collection_batch(state, max_subnets=20)
        print(f"\nCollected: {result['collected']}")
        print(f"Errors: {result['errors']}")
        print(f"Next: SN{result['next_netuid']}")
        print(f"Block: {result['block']}")
