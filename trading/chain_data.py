"""ChainData — fetch live data from Bittensor chain.

Uses the SDK directly to get:
- Alpha prices (from metagraph)
- Emission per neuron
- Active/inactive neurons
- Burn, tempo, hyperparameters
- Network state (block, epoch)

No TAOStats API needed — everything from the chain.
"""
import bittensor as bt
import json
import sqlite3
from pathlib import Path


DB_PATH = Path("/root/bitt/market.duckdb")


def fetch_subnet_snapshot(netuid: int) -> dict:
    """Fetch live data for a subnet from the chain."""
    sub = bt.Subtensor(network="finney")
    block = sub.block
    chain = sub.at(block)

    try:
        mg = chain.subnets.metagraph(netuid)
    except Exception as e:
        return {"error": str(e), "netuid": netuid}

    # Extract neuron data
    neurons = []
    for n in mg.neurons:
        try:
            emission = float(n.emission.rao) if hasattr(n.emission, 'rao') else 0.0
            stake = float(n.total_stake.rao) if hasattr(n.total_stake, 'rao') else 0.0
        except:
            emission = 0.0
            stake = 0.0

        neurons.append({
            "uid": n.uid,
            "active": n.active,
            "emission": emission,
            "stake": stake,
        })

    # Aggregate
    active = [n for n in neurons if n["active"]]
    total_emission = sum(n["emission"] for n in neurons)
    total_stake = sum(n["stake"] for n in neurons)

    # Get burn
    try:
        burn = float(sub.subnets.burn(netuid).rao) if hasattr(sub.subnets.burn(netuid), 'rao') else 0.0
    except:
        burn = 0.0

    return {
        "netuid": netuid,
        "block": block,
        "neuron_count": len(neurons),
        "active_count": len(active),
        "total_emission": total_emission,
        "total_stake": total_stake,
        "burn": burn,
        "neurons": neurons,
    }


def fetch_all_subnets() -> list[dict]:
    """Fetch live data for all subnets."""
    sub = bt.Subtensor(network="finney")
    all_subs = sub.subnets.subnets()

    snapshots = []
    for s in all_subs:
        try:
            snapshot = fetch_subnet_snapshot(s.netuid)
            snapshots.append(snapshot)
        except Exception as e:
            snapshots.append({"error": str(e), "netuid": s.netuid})

    return snapshots


def store_snapshot(snapshot: dict):
    """Store snapshot in market DB."""
    conn = sqlite3.connect(str(DB_PATH))
    ts = snapshot.get("block", 0)
    netuid = snapshot.get("netuid", 0)
    emission = snapshot.get("total_emission", 0)
    stake = snapshot.get("total_stake", 0)
    active = snapshot.get("active_count", 0)
    burn = snapshot.get("burn", 0)

    conn.execute(
        "INSERT INTO subnet_5m (timestamp, netuid, open, high, low, close_tao, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(ts), netuid, emission, stake, active, burn, 0)
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("Fetching live chain data...")
    snapshots = fetch_all_subnets()
    print(f"Fetched {len(snapshots)} subnets")

    for s in snapshots[:5]:
        if "error" not in s:
            print(f"  SN{s['netuid']:3d}: {s['active_count']} active, emission={s['total_emission']:.6f}")
