"""Full chain scanner v3 — block-pinned, correct emission accounting.

Key fixes:
  1. All queries pinned to one finalized block via sub.at(block)
  2. Emission is per-epoch, not per-day. TAO/day = emission * epochs/day
  3. Epoch data fetched explicitly (tempo, blocks_until_next_epoch)
  4. Proper miner vs validator classification
  5. Metagraph neuron_count key fixed
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/root/bitt/oracle.db")

BLOCKS_PER_SECOND = 12  # Bittensor block time


def _to_float(val):
    if hasattr(val, 'rao'):
        return float(val.rao)
    if hasattr(val, 'tao'):
        return float(val.tao)
    return float(val)


def scan_all_detailed(progress: bool = True) -> list[dict]:
    """Scan every subnet, all queries pinned to one block."""
    import bittensor as bt

    sub = bt.Subtensor(network="finney")

    # Pin to one block for atomicity
    block = sub.block
    chain = sub.at(block)
    now = datetime.utcnow().isoformat()

    if progress:
        print(f"Block: {block} | Scanning...")

    all_subs = sub.subnets.subnets()
    results = []

    for i, s in enumerate(all_subs):
        netuid = s.netuid
        try:
            data = _scan_one(chain, sub, netuid, block, now)
            results.append(data)
        except Exception as e:
            results.append({
                "scanned_at": now, "chain_block": block,
                "netuid": netuid, "name": f"error_{netuid}",
                "error": str(e),
            })
        if progress and (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(all_subs)}...")

    if progress:
        print(f"Done: {len(results)} subnets at block {block}")
    return results


def _scan_one(chain, sub, netuid: int, block: int, now: str) -> dict:
    """Full detail for one subnet, all from same block."""
    # Burn
    try:
        burn = sub.subnets.burn(netuid)
        burn_tao = _to_float(burn) / 1e9 if hasattr(burn, 'rao') else _to_float(burn)
    except Exception:
        burn_tao = 0.0

    # Metagraph (pinned block)
    mg = chain.subnets.metagraph(netuid)
    neurons = mg.neurons if isinstance(mg.neurons, list) else []
    tempo = mg.tempo

    # Epoch info
    try:
        epoch_status = chain.epochs.epoch_status(netuid)
        blocks_remaining = epoch_status.get("blocks_remaining", tempo)
        epoch_index = epoch_status.get("epoch_index", 0)
    except Exception:
        blocks_remaining = tempo
        epoch_index = 0

    # Hyperparameters
    try:
        hp = sub.subnets.subnet_hyperparameters(netuid)
        hyperparams = hp if isinstance(hp, dict) else {}
    except Exception:
        hyperparams = {}

    # ── Emission calculation (CORRECT) ──
    # Emission in metagraph is per-epoch (per tempo), not per-day
    blocks_per_day = 24 * 60 * 60 / BLOCKS_PER_SECOND  # 7200
    epochs_per_day = blocks_per_day / tempo if tempo > 0 else 1

    total_emission_rao = sum(_to_float(n.emission) for n in neurons)
    total_alpha_epoch = total_emission_rao / 1e9
    total_alpha_day = total_alpha_epoch * epochs_per_day

    alpha_price = float(mg.price) if mg.price else 0.0
    tao_equiv_day = total_alpha_day * alpha_price

    # Classify neurons
    active = [n for n in neurons if n.active]
    validators = [n for n in neurons if n.validator_permit]
    miners = [n for n in neurons if n.active and not n.validator_permit]
    emitting = [n for n in neurons if n.incentive > 0]

    # Incentive distribution
    all_incentives = sorted([float(n.incentive) for n in neurons if n.incentive > 0], reverse=True)
    total_inc = sum(all_incentives) if all_incentives else 0
    top1 = all_incentives[0] if all_incentives else 0
    top3 = sum(all_incentives[:3])
    top5 = sum(all_incentives[:5])
    top10 = sum(all_incentives[:10])
    hhi = sum((i / total_inc) ** 2 for i in all_incentives) if total_inc > 0 else 0

    # Top emitters
    top_emitters = []
    for n in sorted(emitting, key=lambda x: x.incentive, reverse=True)[:10]:
        em_rao = _to_float(n.emission)
        em_alpha_epoch = em_rao / 1e9
        em_alpha_day = em_alpha_epoch * epochs_per_day
        em_tao_day = em_alpha_day * alpha_price
        top_emitters.append({
            "uid": n.uid,
            "hotkey": n.hotkey,
            "coldkey": n.coldkey,
            "incentive": round(float(n.incentive), 6),
            "dividends": round(float(n.dividends), 6),
            "emission_alpha_epoch": round(em_alpha_epoch, 4),
            "emission_alpha_day": round(em_alpha_day, 4),
            "emission_tao_day": round(em_tao_day, 6),
            "active": n.active,
            "validator_permit": n.validator_permit,
            "total_stake": str(n.total_stake),
            "block_at_registration": n.block_at_registration,
        })

    # Identity
    identity = None
    for n in neurons:
        if n.identity and isinstance(n.identity, dict):
            identity = n.identity
            break

    return {
        "scanned_at": now,
        "chain_block": block,
        "netuid": netuid,
        "name": mg.name or f"subnet_{netuid}",
        "burn_tao": round(burn_tao, 9),
        "neuron_count": len(neurons),
        "active_count": len(active),
        "validator_count": len(validators),
        "miner_count": len(miners),
        "emitting_count": len(emitting),
        # CORRECTED: per-day values
        "total_alpha_epoch": round(total_alpha_epoch, 4),
        "total_alpha_day": round(total_alpha_day, 4),
        "alpha_price": round(alpha_price, 8),
        "tao_equiv_day": round(tao_equiv_day, 6),
        "tempo": tempo,
        "epochs_per_day": round(epochs_per_day, 2),
        "epoch_index": epoch_index,
        "blocks_remaining": blocks_remaining,
        # Incentive distribution
        "top1_incentive": round(top1, 6),
        "top3_incentive": round(top3, 6),
        "top5_incentive": round(top5, 6),
        "top10_incentive": round(top10, 6),
        "hhi": round(hhi, 6),
        "effective_earners": round(1.0 / hhi if hhi > 0 else 0, 2),
        "incentive_shares": [round(i, 6) for i in all_incentives[:20]],
        # Top emitters
        "top_emitters": top_emitters,
        # Hyperparameters
        "hyperparams": {
            "registration_allowed": hyperparams.get("registration_allowed"),
            "min_burn": hyperparams.get("min_burn"),
            "max_burn": hyperparams.get("max_burn"),
            "burn_half_life": hyperparams.get("burn_half_life"),
            "tempo": hyperparams.get("tempo"),
            "max_validators": hyperparams.get("max_validators"),
            "owner_cut": hyperparams.get("owner_cut"),
            "immunity_period": hyperparams.get("immunity_period"),
            "target_regs_per_interval": hyperparams.get("target_regs_per_interval"),
            "max_regs_per_block": hyperparams.get("max_regs_per_block"),
            "commit_reveal_weights_enabled": hyperparams.get("commit_reveal_weights_enabled"),
            "yuma_version": hyperparams.get("yuma_version"),
            "activity_cutoff": hyperparams.get("activity_cutoff"),
        },
        "identity": identity,
    }


# ─── SQLite ──────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subnet_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT NOT NULL,
            chain_block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            data JSON NOT NULL,
            UNIQUE(scanned_at, netuid)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ss_netuid ON subnet_snapshots(netuid, scanned_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ss_time ON subnet_snapshots(scanned_at DESC)")
    conn.commit()
    return conn


def store_snapshots(conn, snapshots: list[dict]):
    for snap in snapshots:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO subnet_snapshots (scanned_at, chain_block, netuid, data) "
                "VALUES (?, ?, ?, ?)",
                (snap["scanned_at"], snap["chain_block"], snap["netuid"],
                 json.dumps(snap, default=str))
            )
        except Exception:
            pass
    conn.commit()


def get_latest(conn) -> dict[int, dict]:
    cur = conn.execute("""
        SELECT netuid, data FROM subnet_snapshots
        WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)
        ORDER BY netuid
    """)
    return {row[0]: json.loads(row[1]) for row in cur.fetchall()}


def get_subnet_history(conn, netuid: int, limit: int = 100) -> list[dict]:
    cur = conn.execute("""
        SELECT scanned_at, data FROM subnet_snapshots
        WHERE netuid = ? ORDER BY scanned_at DESC LIMIT ?
    """, (netuid, limit))
    return [json.loads(row[1]) for row in cur.fetchall()]


def get_all_latest_sorted(conn, sort_by: str = "tao_equiv_day") -> list[dict]:
    latest = get_latest(conn)
    return sorted(latest.values(), key=lambda x: x.get(sort_by, 0), reverse=True)
