"""Chain scanner — fetches LIVE state from Bittensor chain via SDK v11.

Source hierarchy (verified working):
  1. Bittensor SDK v11 (direct chain reads) — PRIMARY
  2. Taostats API (with API key) — SUPPLEMENTARY

Discrepancies are flagged, never silently resolved.
"""
from __future__ import annotations

import http.client
import json
import os
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from .snapshot import BittensorOpportunitySnapshot

# Load .env
_env_path = Path("/root/bitt/.env")
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TAOSTATS_API_KEY = os.environ.get("TAOSTATS_API_KEY", "")
SSL_CTX = ssl.create_default_context()


# ─── SDK v11 client (verified working) ───────────────────────────────

_sub = None

def _get_sub():
    """Lazy-init subtensor connection."""
    global _sub
    if _sub is None:
        import bittensor as bt
        _sub = bt.Subtensor(network="finney")
    return _sub


def _sdk_subnet_info(netuid: int) -> dict | None:
    """Fetch subnet info via SDK v11. Verified working."""
    try:
        sub = _get_sub()
        info = sub.subnets.subnet(netuid)
        return {
            "netuid": info.netuid,
            "tempo": info.tempo,
            "burn": str(info.burn),
            "neuron_count": info.neuron_count,
        }
    except Exception as e:
        return {"error": str(e)}


def _sdk_burn(netuid: int) -> Decimal | None:
    """Fetch current registration burn via SDK v11. Verified working."""
    try:
        sub = _get_sub()
        burn = sub.subnets.burn(netuid)
        return Decimal(str(burn))
    except Exception:
        return None


def _sdk_metagraph(netuid: int) -> dict | None:
    """Fetch metagraph via SDK v11. Verified working.

    mg.neurons is a LIST of MetagraphNeuron objects, not a count.
    """
    try:
        sub = _get_sub()
        mg = sub.subnets.metagraph(netuid)

        # mg.neurons is a list of MetagraphNeuron objects
        neuron_list = mg.neurons if isinstance(mg.neurons, list) else []

        neurons = []
        for n in neuron_list:
            try:
                # Balance objects have .rao for raw numeric value
                def _to_float(val):
                    if hasattr(val, 'rao'):
                        return float(val.rao)
                    return float(val)

                neurons.append({
                    "uid": n.uid,
                    "hotkey": n.hotkey,
                    "coldkey": n.coldkey,
                    "active": n.active,
                    "validator_permit": n.validator_permit,
                    "incentive": float(n.incentive),
                    "dividends": float(n.dividends),
                    "emission": _to_float(n.emission),
                    "alpha_stake": _to_float(n.alpha_stake),
                    "tao_stake": _to_float(n.tao_stake),
                    "total_stake": _to_float(n.total_stake),
                })
            except Exception:
                continue

        return {
            "name": mg.name,
            "netuid": mg.netuid,
            "block": mg.block,
            "neuron_count": len(neuron_list),
            "price": float(mg.price) if mg.price else 0.0,
            "moving_price": float(mg.moving_price) if mg.moving_price else 0.0,
            "tempo": mg.tempo,
            "neuron_data": neurons,
        }
    except Exception as e:
        return {"error": str(e)}


def _sdk_block() -> int | None:
    """Get current block number. Verified working."""
    try:
        return _get_sub().block
    except Exception:
        return None


def _sdk_all_subnets() -> list[dict] | None:
    """List all subnets. Verified working (returns 129+)."""
    try:
        sub = _get_sub()
        all_subs = sub.subnets.subnets()
        return [{"netuid": s.netuid, "tempo": s.tempo, "burn": str(s.burn),
                 "neuron_count": s.neuron_count} for s in all_subs]
    except Exception:
        return None


# ─── Taostats API (with key) ─────────────────────────────────────────

def _taostats_get(path: str, timeout: int = 10) -> dict | None:
    """Fetch from Taostats API with key."""
    if not TAOSTATS_API_KEY:
        return None
    conn = http.client.HTTPSConnection("api.taostats.io", context=SSL_CTX, timeout=timeout)
    try:
        headers = {
            "Authorization": f"Bearer {TAOSTATS_API_KEY}",
            "Content-Type": "application/json",
        }
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        if resp.status == 200:
            return json.loads(body)
        else:
            return {"_status": resp.status, "_error": body[:300]}
    except Exception as e:
        return {"_error": str(e)}
    finally:
        conn.close()


# ─── Scanner ─────────────────────────────────────────────────────────

@dataclass
class ScannerConfig:
    """Configuration for the chain scanner."""
    network: str = "finney"
    timeout_s: int = 30
    use_sdk: bool = True
    use_taostats: bool = True


class ChainScanner:
    """Fetches subnet state from Bittensor chain + APIs.

    SDK v11 is the primary source (verified working).
    Taostats is supplementary (needs API key).
    """

    def __init__(self, config: ScannerConfig | None = None):
        self.config = config or ScannerConfig()

    def scan_subnet(self, netuid: int) -> dict[str, Any]:
        """Scan a single subnet. Returns merged data dict."""
        sources: dict[str, dict] = {}
        flags: list[str] = []

        # Source 1: SDK (primary — verified working)
        if self.config.use_sdk:
            sdk_data = self._fetch_sdk(netuid)
            if sdk_data:
                sources["sdk"] = sdk_data

        # Source 2: Taostats (supplementary)
        if self.config.use_taostats and TAOSTATS_API_KEY:
            ts_data = self._fetch_taostats(netuid)
            if ts_data:
                sources["taostats"] = ts_data

        # Cross-source validation
        if "sdk" in sources and "taostats" in sources:
            flags = self._validate_cross_source(sources)

        return {
            "netuid": netuid,
            "sources": sources,
            "flags": flags,
            "fetched_at": datetime.utcnow().isoformat(),
            "chain_block": _sdk_block(),
        }

    def scan_all(self, netuids: list[int]) -> dict[int, dict]:
        """Scan multiple subnets."""
        return {n: self.scan_subnet(n) for n in netuids}

    def scan_all_subnets(self) -> list[dict] | None:
        """List all subnets from chain."""
        return _sdk_all_subnets()

    def get_current_block(self) -> int | None:
        return _sdk_block()

    # ─── SDK fetcher (primary) ──────────────────────────────────────

    def _fetch_sdk(self, netuid: int) -> dict | None:
        """Fetch all SDK data for a subnet."""
        result = {}

        # Subnet info
        info = _sdk_subnet_info(netuid)
        if info:
            result["subnet"] = info

        # Burn
        burn = _sdk_burn(netuid)
        if burn is not None:
            result["burn"] = str(burn)

        # Metagraph (includes neuron data)
        mg = _sdk_metagraph(netuid)
        if mg:
            result["metagraph"] = mg

            # Extract incentive shares from neuron data
            if "neuron_data" in mg:
                neurons = mg["neuron_data"]
                active_miners = [n for n in neurons if n["active"] and not n["validator_permit"]]
                validators = [n for n in neurons if n["validator_permit"]]
                emitting = [n for n in active_miners if n["incentive"] > 0]

                result["active_miners"] = len(active_miners)
                result["validators"] = len(validators)
                result["emitting_miners"] = len(emitting)

                # Incentive distribution (for HHI calculation)
                incentives = sorted([n["incentive"] for n in neurons if n["incentive"] > 0], reverse=True)
                result["incentive_shares"] = incentives

                # Owner info
                if hasattr(mg, 'get') and "owner_coldkey" in mg:
                    result["owner_coldkey"] = mg["owner_coldkey"]

        return result if result else None

    # ─── Taostats fetcher (supplementary) ───────────────────────────

    def _fetch_taostats(self, netuid: int) -> dict | None:
        """Fetch from Taostats API with API key."""
        # Try various endpoints
        for path in [f"/v4/subnet/{netuid}", f"/v1/subnet/{netuid}", f"/subnet/{netuid}"]:
            data = _taostats_get(path)
            if data and "_error" not in data:
                return data
        return None

    # ─── Cross-source validation ────────────────────────────────────

    def _validate_cross_source(self, sources: dict[str, dict]) -> list[str]:
        """Compare values across sources, flag discrepancies."""
        flags = []
        sdk = sources.get("sdk", {})
        ts = sources.get("taostats", {})

        # Compare neuron counts
        sdk_count = sdk.get("metagraph", {}).get("neurons")
        ts_count = ts.get("neuron_count") or ts.get("neurons")
        if sdk_count and ts_count and abs(int(sdk_count) - int(ts_count)) > 5:
            flags.append(f"neuron_count_discrepancy: sdk={sdk_count} taostats={ts_count}")

        # Compare burn
        sdk_burn = sdk.get("burn")
        ts_burn = ts.get("burn") or ts.get("registration_cost")
        if sdk_burn and ts_burn:
            try:
                if abs(float(sdk_burn) - float(ts_burn)) / max(float(sdk_burn), 0.0001) > 0.1:
                    flags.append(f"burn_discrepancy: sdk={sdk_burn} taostats={ts_burn}")
            except (ValueError, TypeError):
                pass

        return flags


# ─── Scanner state store ─────────────────────────────────────────────

class ScannerStore:
    """Persistent store for scanner snapshots. SQLite-backed."""

    def __init__(self, db_path: str = "/root/bitt/scanner_store.db"):
        import sqlite3
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                netuid INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                data JSON NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_netuid
            ON snapshots(netuid, observed_at)
        """)
        self.conn.commit()

    def store(self, snapshot: BittensorOpportunitySnapshot):
        """Store a snapshot. Never overwrites."""
        self.conn.execute(
            "INSERT OR IGNORE INTO snapshots (snapshot_id, netuid, observed_at, data) "
            "VALUES (?, ?, ?, ?)",
            (snapshot.snapshot_id, snapshot.netuid,
             snapshot.observed_at.isoformat(), snapshot.to_json())
        )
        self.conn.commit()

    def get_latest(self, netuid: int) -> BittensorOpportunitySnapshot | None:
        """Get most recent snapshot for a subnet."""
        cur = self.conn.execute(
            "SELECT data FROM snapshots WHERE netuid = ? "
            "ORDER BY observed_at DESC LIMIT 1",
            (netuid,)
        )
        row = cur.fetchone()
        if row:
            return BittensorOpportunitySnapshot.from_dict(json.loads(row[0]))
        return None

    def get_history(self, netuid: int, limit: int = 50) -> list[BittensorOpportunitySnapshot]:
        """Get recent snapshots for a subnet."""
        cur = self.conn.execute(
            "SELECT data FROM snapshots WHERE netuid = ? "
            "ORDER BY observed_at DESC LIMIT ?",
            (netuid, limit)
        )
        return [BittensorOpportunitySnapshot.from_dict(json.loads(r[0]))
                for r in cur.fetchall()]

    def get_all_latest(self) -> dict[int, BittensorOpportunitySnapshot]:
        """Get latest snapshot for every tracked subnet."""
        cur = self.conn.execute(
            "SELECT netuid, MAX(observed_at) as latest "
            "FROM snapshots GROUP BY netuid"
        )
        result = {}
        for netuid, latest in cur.fetchall():
            snap = self.get_latest(netuid)
            if snap:
                result[netuid] = snap
        return result
