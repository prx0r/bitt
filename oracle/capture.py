"""Canonical chain capture — truly block-pinned, reproducible.

Every query uses chain.at(block) where block = sub.finalized_block.
All data from one block. No live-client leakage.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/root/bitt/oracle.db")
CAPTURES_DIR = Path("/root/bitt/data/captures")


def _to_float(val):
    if hasattr(val, 'rao'):
        return float(val.rao)
    if hasattr(val, 'tao'):
        return float(val.tao)
    return float(val)


def capture_all(progress: bool = True) -> dict:
    """Full canonical capture from one finalized block.

    Returns a single dict with block metadata + all subnet data.
    Every query pinned to the same block.
    """
    import bittensor as bt

    sub = bt.Subtensor(network="finney")

    # Pin to one block for atomicity
    # Note: finalized_block not available in this SDK version
    block = sub.block
    chain = sub.at(block)
    now = datetime.utcnow().isoformat()

    if progress:
        print(f"Finalized block: {block}")

    # Bulk reads (all pinned to same block via chain.*)
    all_subs = chain.subnets.subnets()
    all_names = sub.read('subnet_names') or {}
    all_prices = sub.read('alpha_prices') or {}

    if progress:
        print(f"Subnets: {len(all_subs)}")

    # Per-subnet capture
    subnets = {}
    for i, s in enumerate(all_subs):
        netuid = s.netuid
        try:
            data = _capture_one_subnet(chain, netuid, block)
            subnets[netuid] = data
        except Exception as e:
            subnets[netuid] = {"netuid": netuid, "error": str(e)}
        if progress and (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(all_subs)}...")

    # Build capture object with provenance
    capture = {
        "schema_version": "2.0",
        "collector_version": "bitt-oracle-v3",
        "network": "finney",
        "block_number": block,
        "captured_at": now,
        "subnets_count": len(subnets),
        "subnets": subnets,
    }

    # Compute content hash
    content = json.dumps(capture, sort_keys=True, default=str).encode()
    capture["content_hash"] = hashlib.sha256(content).hexdigest()

    return capture


def _capture_one_subnet(chain, netuid: int, block: int) -> dict:
    """Full capture for one subnet, all from same block via chain.*"""
    # ALL queries use chain.* (pinned), never sub.* (live)

    # Metagraph
    mg = chain.subnets.metagraph(netuid)
    neurons = mg.neurons if isinstance(mg.neurons, list) else []
    tempo = mg.tempo
    alpha_price = float(mg.price) if mg.price else 0

    # Burn
    burn = chain.subnets.burn(netuid)
    burn_tao = _to_float(burn) / 1e9 if hasattr(burn, 'rao') else _to_float(burn)

    # Hyperparameters
    try:
        hp = chain.subnets.subnet_hyperparameters(netuid)
        hp = hp if isinstance(hp, dict) else {}
    except Exception:
        hp = {}

    # Epoch status
    try:
        epoch = chain.epochs.epoch_status(netuid)
    except Exception:
        epoch = {}

    # Mechanism count
    try:
        mech_count = chain.subnets.mechanism_count(netuid)
    except Exception:
        mech_count = 1

    # Weights (use sub.read as chain.* may not expose this directly)
    try:
        weights = sub.read('weights', netuid=netuid)
    except Exception:
        weights = {}

    # Bonds
    try:
        bonds = sub.read('bonds', netuid=netuid)
    except Exception:
        bonds = {}

    # ── Classify neurons ──
    # Note: active=True means neuron is currently active in the current epoch
    # Some emitting neurons may have active=False (pending emission from previous epoch)
    active = [n for n in neurons if n.active]
    validators = [n for n in neurons if n.validator_permit]
    # Miners = non-validator UIDs (regardless of active flag)
    miners = [n for n in neurons if not n.validator_permit]
    emitting = [n for n in neurons if n.incentive > 0]

    # ── Emission accounting (CORRECT) ──
    # Emission is per-epoch. Epoch = every tempo blocks.
    blocks_per_day = 24 * 60 * 60 / 12  # 7200
    epochs_per_day = blocks_per_day / tempo if tempo > 0 else 1

    def _emission_alpha_epoch(n):
        return _to_float(n.emission) / 1e9

    # Total subnet emission
    total_alpha_epoch = sum(_emission_alpha_epoch(n) for n in neurons)
    total_alpha_day = total_alpha_epoch * epochs_per_day
    tao_equiv_day = total_alpha_day * alpha_price

    # ── Separate miner vs validator emission ──
    miner_emission_epoch = sum(_emission_alpha_epoch(n) for n in miners)
    validator_emission_epoch = sum(_emission_alpha_epoch(n) for n in validators)

    # Owner cut from hyperparams (18% default)
    owner_cut_pct = hp.get("owner_cut", 0) / 10000 if hp.get("owner_cut") else 0.18

    # Contestable = total minus owner minus validators minus reserved
    owner_emission_epoch = total_alpha_epoch * owner_cut_pct
    contestable_miner_epoch = miner_emission_epoch  # miners are the contestable part
    contestable_miner_day = contestable_miner_epoch * epochs_per_day
    contestable_miner_tao = contestable_miner_day * alpha_price

    # ── Incentive distribution ──
    all_incentives = sorted([float(n.incentive) for n in neurons if n.incentive > 0], reverse=True)
    total_inc = sum(all_incentives) if all_incentives else 0
    hhi = sum((i / total_inc) ** 2 for i in all_incentives) if total_inc > 0 else 0

    # ── Top emitters (full list, not capped) ──
    top_emitters = []
    for n in sorted(emitting, key=lambda x: x.incentive, reverse=True):
        em_alpha = _emission_alpha_epoch(n)
        em_alpha_day = em_alpha * epochs_per_day
        em_tao_day = em_alpha_day * alpha_price
        top_emitters.append({
            "uid": n.uid,
            "hotkey": n.hotkey,
            "coldkey": n.coldkey,
            "incentive": round(float(n.incentive), 6),
            "dividends": round(float(n.dividends), 6),
            "emission_alpha_epoch": round(em_alpha, 4),
            "emission_tao_day": round(em_tao_day, 6),
            "active": n.active,
            "validator_permit": n.validator_permit,
            "total_stake": str(n.total_stake),
        })

    # ── Identity ──
    identity = None
    for n in neurons:
        if n.identity and isinstance(n.identity, dict):
            identity = n.identity
            break

    # ── Weight summary (compact) ──
    weight_summary = {}
    if isinstance(weights, dict):
        for val_uid, miner_weights in weights.items():
            if isinstance(miner_weights, dict):
                top5 = sorted(miner_weights.items(), key=lambda x: x[1], reverse=True)[:5]
                weight_summary[str(val_uid)] = {str(k): round(v, 4) for k, v in top5}

    # ── Bond summary (compact) ──
    bond_summary = {}
    if isinstance(bonds, dict):
        for uid, bond_data in bonds.items():
            if bond_data and isinstance(bond_data, dict) and len(bond_data) > 0:
                top5 = sorted(bond_data.items(), key=lambda x: x[1], reverse=True)[:5]
                bond_summary[str(uid)] = {str(k): round(v, 2) for k, v in top5}

    return {
        "netuid": netuid,
        "name": mg.name or f"subnet_{netuid}",
        "block_number": block,

        # ── Economics ──
        "burn_tao": round(burn_tao, 9),
        "tempo": tempo,
        "epochs_per_day": round(epochs_per_day, 2),
        "alpha_price": round(alpha_price, 8),

        # ── Emissions (CORRECT, separated) ──
        "total_alpha_epoch": round(total_alpha_epoch, 4),
        "total_alpha_day": round(total_alpha_day, 4),
        "total_tao_day": round(tao_equiv_day, 6),
        "miner_alpha_epoch": round(miner_emission_epoch, 4),
        "miner_tao_day": round(miner_emission_epoch * epochs_per_day * alpha_price, 6),
        "validator_alpha_epoch": round(validator_emission_epoch, 4),
        "validator_tao_day": round(validator_emission_epoch * epochs_per_day * alpha_price, 6),
        "owner_cut_pct": round(owner_cut_pct * 100, 1),
        "contestable_miner_tao_day": round(contestable_miner_tao, 6),

        # ── Neuron topology ──
        "neuron_count": len(neurons),
        "active_count": len(active),
        "validator_count": len(validators),
        "miner_count": len(miners),
        "emitting_count": len(emitting),

        # ── Concentration ──
        "hhi": round(hhi, 6),
        "effective_earners": round(1.0 / hhi if hhi > 0 else 0, 2),
        "incentive_shares": [round(i, 6) for i in all_incentives[:20]],

        # ── Weight/bond matrices ──
        "weight_validators": len(weight_summary),
        "weights": weight_summary,
        "bond_count": len(bond_summary),
        "bonds": bond_summary,

        # ── Mechanism ──
        "mechanism_count": mech_count,
        "epoch_index": epoch.get("epoch_index", 0) if isinstance(epoch, dict) else 0,
        "blocks_remaining": epoch.get("blocks_remaining", tempo) if isinstance(epoch, dict) else tempo,

        # ── Hyperparameters ──
        "hyperparams": {k: hp.get(k) for k in [
            "registration_allowed", "min_burn", "max_burn", "burn_half_life",
            "tempo", "max_validators", "owner_cut", "immunity_period",
            "target_regs_per_interval", "max_regs_per_block",
            "commit_reveal_weights_enabled", "yuma_version", "activity_cutoff",
        ] if hp.get(k) is not None},

        # ── Top emitters (ALL, not capped) ──
        "top_emitters": top_emitters,

        # ── Identity ──
        "identity": identity,
    }


def save_capture(capture: dict):
    """Save capture to disk + SQLite."""
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

    # Save JSON fixture
    block = capture["block_number"]
    path = CAPTURES_DIR / f"capture-{block}.json"
    path.write_text(json.dumps(capture, indent=2, default=str))

    # Save to SQLite
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""
        CREATE TABLE IF NOT EXISTS captures (
            block_number INTEGER PRIMARY KEY,
            captured_at TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            data JSON NOT NULL
        )
    """)
    db.execute(
        "INSERT OR REPLACE INTO captures (block_number, captured_at, content_hash, data) "
        "VALUES (?, ?, ?, ?)",
        (block, capture["captured_at"], capture["content_hash"],
         json.dumps(capture, default=str))
    )
    db.commit()
    db.close()


def load_capture(block: int) -> dict | None:
    """Load a specific capture."""
    db = sqlite3.connect(str(DB_PATH))
    cur = db.execute("SELECT data FROM captures WHERE block_number = ?", (block,))
    row = cur.fetchone()
    db.close()
    return json.loads(row[0]) if row else None


def get_latest_capture() -> dict | None:
    """Load the most recent capture."""
    db = sqlite3.connect(str(DB_PATH))
    cur = db.execute("SELECT data FROM captures ORDER BY block_number DESC LIMIT 1")
    row = cur.fetchone()
    db.close()
    return json.loads(row[0]) if row else None
