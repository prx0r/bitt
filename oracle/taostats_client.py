"""Taostats API client — enriches chain data with market/competition intel.

Key endpoints:
  /api/subnet/latest/v1              — all subnets (emission, flows, difficulty)
  /api/dtao/pool/latest/v1?netuid=N  — pool (price, root_prop, fear/greed, volume)
  /api/metagraph/latest/v1?netuid=N  — neurons (stake, incentive, emission)
  /api/subnet/registration/v1?netuid=N — registration cost, owner
  /api/dtao/validator/yield/latest/v1?netuid=N — validator APYs

Rate limit: 5 calls/minute (free tier)
"""
from __future__ import annotations

import http.client
import json
import os
import ssl
import time
from pathlib import Path

# Load API key from vault
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from vault import Vault

_CTX = ssl.create_default_context()
BASE = "api.taostats.io"


def _get_api_key() -> str:
    v = Vault()
    return v.get("taostats_api_key") or ""


def _get(path: str, timeout: int = 15) -> dict | None:
    """Make authenticated GET to Taostats."""
    api_key = _get_api_key()
    if not api_key:
        return None
    conn = http.client.HTTPSConnection(BASE, context=_CTX, timeout=timeout)
    try:
        conn.request("GET", path, headers={
            "Authorization": api_key,
            "accept": "application/json",
        })
        resp = conn.getresponse()
        body = resp.read().decode()
        if resp.status == 200:
            return json.loads(body)
        return {"_status": resp.status, "_error": body[:500]}
    except Exception as e:
        return {"_error": str(e)}
    finally:
        conn.close()


# ─── Subnet endpoints ───────────────────────────────────────────────

def get_all_subnets() -> list[dict]:
    """Get all subnets with emission, flows, difficulty."""
    r = _get("/api/subnet/latest/v1")
    return r.get("data", []) if r and "data" in r else []


def get_subnet(netuid: int) -> dict | None:
    """Get single subnet details."""
    r = _get(f"/api/subnet/latest/v1?netuid={netuid}")
    if r and "data" in r and r["data"]:
        return r["data"][0]
    return None


def get_subnet_registration(netuid: int) -> dict | None:
    """Get registration cost and owner."""
    r = _get(f"/api/subnet/registration/v1?netuid={netuid}")
    if r and "data" in r and r["data"]:
        return r["data"][0]
    return None


# ─── Pool/market endpoints ──────────────────────────────────────────

def get_pool(netuid: int) -> dict | None:
    """Get pool data: price, root_prop, fear/greed, volume, liquidity."""
    r = _get(f"/api/dtao/pool/latest/v1?netuid={netuid}")
    if r and "data" in r and r["data"]:
        return r["data"][0]
    return None


def get_pool_history(netuid: int, limit: int = 30) -> list[dict]:
    """Get historical pool snapshots."""
    r = _get(f"/api/dtao/pool/history/v1?netuid={netuid}&limit={limit}")
    return r.get("data", []) if r and "data" in r else []


# ─── Metagraph endpoints ────────────────────────────────────────────

def get_metagraph(netuid: int, limit: int = 256) -> list[dict]:
    """Get all neurons with stake, incentive, emission."""
    r = _get(f"/api/metagraph/latest/v1?netuid={netuid}&limit={limit}")
    return r.get("data", []) if r and "data" in r else []


# ─── Validator endpoints ────────────────────────────────────────────

def get_validator_yields(netuid: int) -> list[dict]:
    """Get validator APYs."""
    r = _get(f"/api/dtao/validator/yield/latest/v1?netuid={netuid}")
    return r.get("data", []) if r and "data" in r else []


# ─── Enriched subnet intel ──────────────────────────────────────────

def get_subnet_intel(netuid: int) -> dict:
    """Get comprehensive intel for one subnet from Taostats."""
    result = {"netuid": netuid, "source": "taostats"}

    # Pool data
    pool = get_pool(netuid)
    if pool:
        result["pool"] = {
            "price": pool.get("price"),
            "root_prop": pool.get("root_prop"),
            "fear_and_greed": pool.get("fear_and_greed_index"),
            "fear_sentiment": pool.get("fear_and_greed_sentiment"),
            "market_cap": pool.get("market_cap"),
            "liquidity": pool.get("liquidity"),
            "total_tao": pool.get("total_tao"),
            "total_alpha": pool.get("total_alpha"),
            "volume_24h": pool.get("tao_volume_24_hr"),
            "alpha_volume_24h": pool.get("alpha_volume_24_hr"),
            "buys_24h": pool.get("buys_24_hr"),
            "sells_24h": pool.get("sells_24_hr"),
            "high_24h": pool.get("highest_price_24_hr"),
            "low_24h": pool.get("lowest_price_24_hr"),
            "change_1h": pool.get("price_change_1_hour"),
            "change_1d": pool.get("price_change_1_day"),
            "change_1w": pool.get("price_change_1_week"),
            "change_1m": pool.get("price_change_1_month"),
        }

    # Registration
    reg = get_subnet_registration(netuid)
    if reg:
        result["registration"] = {
            "cost": reg.get("registration_cost"),
            "owner": reg.get("owner", {}).get("ss58") if isinstance(reg.get("owner"), dict) else reg.get("owner"),
        }

    # Metagraph top miners
    neurons = get_metagraph(netuid, limit=20)
    if neurons:
        result["top_neurons"] = [{
            "uid": n.get("uid"),
            "incentive": n.get("incentive"),
            "emission": n.get("emission"),
            "trust": n.get("trust"),
            "consensus": n.get("consensus"),
            "stake": n.get("stake"),
            "updated": n.get("updated"),
        } for n in neurons[:10]]

    # Validator yields
    yields = get_validator_yields(netuid)
    if yields:
        best = max(yields, key=lambda x: x.get("seven_day_apy", 0))
        result["best_validator_apy"] = best.get("seven_day_apy")
        result["best_validator_name"] = best.get("name")

    return result


# ─── Batch scan ─────────────────────────────────────────────────────

def scan_all_pools() -> list[dict]:
    """Get pool data for all subnets (one API call)."""
    r = _get("/api/dtao/pool/latest/v1")
    return r.get("data", []) if r and "data" in r else []


def scan_opportunity_subnets(netuids: list[int] | None = None) -> list[dict]:
    """Get enriched intel for specific subnets."""
    if netuids is None:
        netuids = [0, 1, 3, 4, 6, 8, 9, 15, 44, 51, 56, 61, 62, 64, 67,
                    80, 90, 95, 97, 107, 110, 114, 118, 120]

    results = []
    for netuid in netuids:
        intel = get_subnet_intel(netuid)
        results.append(intel)
        time.sleep(0.3)  # respect rate limit

    return results
