"""On-Chain Data Collector — SDK-based, no API rate limits.

Uses bittensor SDK to pull ALL data for ALL subnets directly from chain:
- Metagraph (neurons, emission, stake, incentive, dividends)
- Subnet info (registration cost, max neurons, owner, hyperparameters)
- Pool state (TAO reserve, alpha reserve, price)
- Block data (epoch, tempo, emission schedule)

Stores everything in market.duckdb → our analytics compute from this.
No TAOStats dependency. No rate limits. Pure chain data.
"""
import bittensor as bt
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime


MARKET_DB = Path("/root/bitt/market.duckdb")


def init_comprehensive_tables():
    """Create all tables we need for full subnet analytics."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.executescript("""
        -- Raw metagraph snapshot per subnet per block
        CREATE TABLE IF NOT EXISTS metagraph_snapshot (
            block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            uid INTEGER NOT NULL,
            hotkey TEXT,
            coldkey TEXT,
            active INTEGER,
            stake REAL,
            total_stake REAL,
            incentive REAL,
            dividends REAL,
            emission REAL,
            trust REAL,
            consensus REAL,
            validator_trust REAL,
            rank REAL,
            validator_permit INTEGER,
            updated INTEGER,
            PRIMARY KEY (block, netuid, uid)
        );
        
        -- Subnet-level metrics per block
        CREATE TABLE IF NOT EXISTS subnet_metrics_live (
            block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            owner TEXT,
            registration_cost REAL,
            neuron_registration_cost REAL,
            max_neurons INTEGER,
            active_keys INTEGER,
            emitting_count INTEGER,
            total_emission REAL,
            total_stake REAL,
            avg_incentive REAL,
            avg_dividends REAL,
            hhi_incentive REAL,
            gini_incentive REAL,
            top1_share REAL,
            top5_share REAL,
            tempo INTEGER,
            immunity_period INTEGER,
            activity_cutoff INTEGER,
            registration_allowed INTEGER,
            collateral_lock_share REAL,
            fee_rate REAL,
            burn_24h REAL,
            recycled_24h REAL,
            PRIMARY KEY (block, netuid)
        );
        
        -- Pool state per block
        CREATE TABLE IF NOT EXISTS pool_state_live (
            block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            tao_reserve REAL,
            alpha_reserve REAL,
            alpha_price REAL,
            liquidity REAL,
            k_constant REAL,
            PRIMARY KEY (block, netuid)
        );
        
        -- Daily summary (computed from raw data)
        CREATE TABLE IF NOT EXISTS daily_subnet_summary (
            date TEXT NOT NULL,
            netuid INTEGER NOT NULL,
            avg_emission REAL,
            avg_stake REAL,
            avg_incentive REAL,
            avg_alpha_price REAL,
            miner_count INTEGER,
            validator_count INTEGER,
            emitting_count INTEGER,
            registration_cost REAL,
            open_slots INTEGER,
            hhi REAL,
            gini REAL,
            competition_ratio REAL,
            emission_per_miner REAL,
            days_to_roi REAL,
            PRIMARY KEY (date, netuid)
        );
        
        CREATE INDEX IF NOT EXISTS idx_mg_block ON metagraph_snapshot(block);
        CREATE INDEX IF NOT EXISTS idx_mg_netuid ON metagraph_snapshot(netuid);
        CREATE INDEX IF NOT EXISTS idx_sm_live_block ON subnet_metrics_live(block);
        CREATE INDEX IF NOT EXISTS idx_ps_live_block ON pool_state_live(block);
    """)
    conn.commit()
    conn.close()


def collect_subnet_data(netuid: int, block: int = None) -> dict:
    """Collect ALL data for one subnet from chain."""
    sub = bt.Subtensor(network="finney")
    
    if block is None:
        block = sub.block
    
    chain = sub.at(block)
    
    result = {"netuid": netuid, "block": block, "error": None}
    
    try:
        # Get metagraph
        mg = chain.subnets.metagraph(netuid)
        
        neurons = []
        for n in mg.neurons:
            try:
                emission_rao = float(n.emission.rao) if hasattr(n.emission, 'rao') else 0.0
                stake_rao = float(n.total_stake.rao) if hasattr(n.total_stake, 'rao') else 0.0
                incentive = float(n.incentive) if hasattr(n, 'incentive') else 0.0
                dividends = float(n.dividends) if hasattr(n, 'dividends') else 0.0
                trust = float(n.trust) if hasattr(n, 'trust') else 0.0
                consensus = float(n.consensus) if hasattr(n, 'consensus') else 0.0
                validator_trust = float(n.validator_trust) if hasattr(n, 'validator_trust') else 0.0
                rank = float(n.rank) if hasattr(n, 'rank') else 0.0
                
                neurons.append({
                    "uid": n.uid,
                    "hotkey": n.hotkey if hasattr(n, 'hotkey') else "",
                    "coldkey": n.coldkey if hasattr(n, 'coldkey') else "",
                    "active": 1 if n.active else 0,
                    "stake": stake_rao,
                    "total_stake": stake_rao,
                    "incentive": incentive,
                    "dividends": dividends,
                    "emission": emission_rao,
                    "trust": trust,
                    "consensus": consensus,
                    "validator_trust": validator_trust,
                    "rank": rank,
                    "validator_permit": 1 if getattr(n, 'validator_permit', False) else 0,
                    "updated": int(getattr(n, 'updated', 0)),
                })
            except:
                pass
        
        result["neurons"] = neurons
        
        # Aggregate metrics
        active = [n for n in neurons if n["active"]]
        emitting = [n for n in neurons if n["emission"] > 0]
        total_emission = sum(n["emission"] for n in neurons)
        total_stake = sum(n["stake"] for n in neurons)
        
        # Incentive distribution metrics
        incentives = sorted([n["incentive"] for n in neurons if n["incentive"] > 0], reverse=True)
        if incentives:
            total_inc = sum(incentives)
            shares = [i / total_inc for i in incentives]
            hhi = sum(s ** 2 for s in shares)
            gini_num = sum((2 * i - len(incentives) - 1) * incentives[i] for i in range(len(incentives)))
            gini = gini_num / (len(incentives) * total_inc) if total_inc > 0 else 0
            top1 = shares[0]
            top5 = sum(shares[:5])
        else:
            hhi = 1.0
            gini = 0.0
            top1 = 1.0
            top5 = 1.0
        
        result["metrics"] = {
            "emitting_count": len(emitting),
            "active_count": len(active),
            "total_neurons": len(neurons),
            "total_emission": total_emission,
            "total_stake": total_stake,
            "avg_incentive": sum(n["incentive"] for n in neurons) / max(len(neurons), 1),
            "avg_dividends": sum(n["dividends"] for n in neurons) / max(len(neurons), 1),
            "hhi_incentive": hhi,
            "gini_incentive": gini,
            "top1_share": top1,
            "top5_share": top5,
        }
        
        # Get subnet info (hyperparameters)
        try:
            subnet_info = sub.subnets.get_subnet_info(netuid)
            result["subnet_info"] = {
                "owner": str(getattr(subnet_info, 'owner_ss58', '')),
                "registration_cost": float(getattr(subnet_info, 'tao_weight', 0)),
                "max_neurons": int(getattr(subnet_info, 'max_neurons', 256)),
                "tempo": int(getattr(subnet_info, 'tempo', 0)),
                "immunity_period": int(getattr(subnet_info, 'immunity_period', 0)),
                "activity_cutoff": int(getattr(subnet_info, 'activity_cutoff', 5000)),
                "registration_allowed": bool(getattr(subnet_info, 'registration_allowed', True)),
                "min_burn": float(getattr(subnet_info, 'min_burn', 0)),
                "max_burn": float(getattr(subnet_info, 'max_burn', 0)),
            }
        except:
            result["subnet_info"] = {}
        
        # Get pool state
        try:
            pool = sub.subnets.pool(netuid)
            tao_reserve = float(pool.tao_reserve.rao) / 1e9 if hasattr(pool, 'tao_reserve') else 0
            alpha_reserve = float(pool.alpha_reserve.rao) / 1e9 if hasattr(pool, 'alpha_reserve') else 0
            price = tao_reserve / max(alpha_reserve, 1e-9)
            
            result["pool"] = {
                "tao_reserve": tao_reserve,
                "alpha_reserve": alpha_reserve,
                "alpha_price": price,
                "liquidity": tao_reserve * 2,  # Approximate
                "k_constant": tao_reserve * alpha_reserve,
            }
        except:
            result["pool"] = {}
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


def store_collected_data(data: dict):
    """Store collected data in database."""
    conn = sqlite3.connect(str(MARKET_DB))
    block = data["block"]
    netuid = data["netuid"]
    
    # Store metagraph neurons
    for n in data.get("neurons", []):
        conn.execute(
            "INSERT OR REPLACE INTO metagraph_snapshot "
            "(block, netuid, uid, hotkey, coldkey, active, stake, total_stake, "
            "incentive, dividends, emission, trust, consensus, validator_trust, "
            "rank, validator_permit, updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (block, netuid, n["uid"], n["hotkey"], n["coldkey"], n["active"],
             n["stake"], n["total_stake"], n["incentive"], n["dividends"],
             n["emission"], n["trust"], n["consensus"], n["validator_trust"],
             n["rank"], n["validator_permit"], n["updated"])
        )
    
    # Store subnet metrics
    m = data.get("metrics", {})
    info = data.get("subnet_info", {})
    conn.execute(
        "INSERT OR REPLACE INTO subnet_metrics_live "
        "(block, netuid, owner, registration_cost, neuron_registration_cost, "
        "max_neurons, active_keys, emitting_count, total_emission, total_stake, "
        "avg_incentive, avg_dividends, hhi_incentive, gini_incentive, "
        "top1_share, top5_share, tempo, immunity_period, activity_cutoff, "
        "registration_allowed, collateral_lock_share, fee_rate, burn_24h, recycled_24h) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0)",
        (block, netuid, info.get("owner", ""), info.get("registration_cost", 0),
         info.get("min_burn", 0), info.get("max_neurons", 256),
         m.get("active_count", 0), m.get("emitting_count", 0),
         m.get("total_emission", 0), m.get("total_stake", 0),
         m.get("avg_incentive", 0), m.get("avg_dividends", 0),
         m.get("hhi_incentive", 0), m.get("gini_incentive", 0),
         m.get("top1_share", 0), m.get("top5_share", 0),
         info.get("tempo", 0), info.get("immunity_period", 0),
         info.get("activity_cutoff", 5000), 1 if info.get("registration_allowed", True) else 0)
    )
    
    # Store pool state
    p = data.get("pool", {})
    if p:
        conn.execute(
            "INSERT OR REPLACE INTO pool_state_live "
            "(block, netuid, tao_reserve, alpha_reserve, alpha_price, liquidity, k_constant) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (block, netuid, p.get("tao_reserve", 0), p.get("alpha_reserve", 0),
             p.get("alpha_price", 0), p.get("liquidity", 0), p.get("k_constant", 0))
        )
    
    conn.commit()
    conn.close()


def collect_all_subnets(max_subnets: int = 130, batch_delay: float = 2.0) -> dict:
    """Collect data for ALL subnets from chain.
    
    Uses single connection + delays to avoid rate limits.
    """
    results = {"success": 0, "errors": 0, "neurons_total": 0}
    
    # Single connection
    sub = bt.Subtensor(network="finney")
    block = sub.block
    print(f"Chain block: {block}")
    
    batch = []
    for netuid in range(max_subnets):
        try:
            data = collect_subnet_data(netuid, block)
            if data.get("error"):
                results["errors"] += 1
                time.sleep(1.0)
                continue
            
            store_collected_data(data)
            results["success"] += 1
            results["neurons_total"] += len(data.get("neurons", []))
            
            if netuid % 10 == 0:
                print(f"  SN{netuid}: {len(data.get('neurons', []))} neurons, "
                      f"emit={data.get('metrics', {}).get('emitting_count', 0)}, "
                      f"pool={data.get('pool', {}).get('alpha_price', 'N/A')}")
            
            # Rate limit: pause every 5 subnets
            if netuid % 5 == 4:
                time.sleep(batch_delay)
            
        except Exception as e:
            results["errors"] += 1
            if netuid % 10 == 0:
                print(f"  SN{netuid}: ERROR {str(e)[:60]}")
            time.sleep(2.0)  # Back off on error
    
    return results


if __name__ == "__main__":
    print("=== On-Chain Data Collector (SDK) ===")
    print("Collecting ALL data for ALL subnets...\n")
    
    init_comprehensive_tables()
    results = collect_all_subnets(max_subnets=130)
    
    print(f"\n=== RESULTS ===")
    print(f"Subnets: {results['success']} success, {results['errors']} errors")
    print(f"Total neurons: {results['neurons_total']}")
    print(f"Block: {bt.Subtensor(network='finney').block}")
    
    # Verify data
    conn = sqlite3.connect(str(MARKET_DB))
    for table in ["metagraph_snapshot", "subnet_metrics_live", "pool_state_live"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")
    conn.close()
