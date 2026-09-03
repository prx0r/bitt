"""TAOStats Historical Data Ingestion.

Downloads historical subnet data from TAOStats API:
- Pool history (price, reserves, liquidity)
- Subnet history (owner, neurons, validators, miners, emission)
- Registration events
- OHLCV candles (via TradingView UDF)
- Dev activity

Stores in market.duckdb with proper schema.
"""
import http.client
import ssl
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime


MARKET_DB = Path("/root/bitt/market.duckdb")
TAOSTATS_HOST = "api.taostats.io"
API_KEY = None  # Set from vault if needed
CTX = ssl.create_default_context()


def _get_api_key():
    """Load API key from vault."""
    global API_KEY
    if API_KEY:
        return API_KEY
    try:
        import sys
        sys.path.insert(0, "/root/bitt")
        from vault import Vault
        v = Vault()
        API_KEY = v.get("taostats_api_key")
        return API_KEY
    except:
        return None


def _request(path: str, params: dict = None) -> dict:
    """Make authenticated request to TAOStats API."""
    api_key = _get_api_key()
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    query = ""
    if params:
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    
    conn = http.client.HTTPSConnection(TAOSTATS_HOST, timeout=30, context=CTX)
    conn.request("GET", f"/api{path}{query}", headers=headers)
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    return data


def fetch_subnet_history(netuid: int, frequency: str = "by_hour", limit: int = 500) -> list[dict]:
    """Fetch historical pool state for a subnet."""
    data = _request(f"/dtao/pool/history/v1", {
        "netuid": netuid,
        "frequency": frequency,
        "limit": limit,
    })
    return data.get("data", data.get("history", []))


def fetch_subnet_emission(netuid: int, limit: int = 500) -> list[dict]:
    """Fetch emission history for a subnet."""
    data = _request(f"/dtao/subnet_emission/v1", {
        "netuid": netuid,
        "limit": limit,
    })
    return data.get("data", [])


def fetch_registrations(limit: int = 200) -> list[dict]:
    """Fetch recent registration events."""
    data = _request(f"/subnet/registration/v1", {"limit": limit})
    return data.get("data", [])


def fetch_dev_activity(netuid: int, limit: int = 30) -> list[dict]:
    """Fetch GitHub dev activity for a subnet."""
    data = _request(f"/dev_activity/history/v1", {
        "netuid": netuid,
        "limit": limit,
    })
    return data.get("data", [])


def fetch_incentive_distribution(netuid: int) -> dict:
    """Fetch current incentive distribution for a subnet."""
    data = _request(f"/subnet/distribution/incentive/v1", {"netuid": netuid})
    return data.get("data", {})


def store_pool_history(netuid: int, history: list[dict]):
    """Store pool history in market.duckdb."""
    conn = sqlite3.connect(str(MARKET_DB))
    stored = 0
    for h in history:
        try:
            ts = h.get("timestamp", h.get("date", ""))
            block = h.get("block", 0)
            price = float(h.get("alpha_price", h.get("close", 0)) or 0)
            tao_reserve = float(h.get("tao_reserve", h.get("liquidity_tao", 0)) or 0)
            alpha_reserve = float(h.get("alpha_reserve", h.get("total_alpha", 0)) or 0)
            liquidity = float(h.get("liquidity", h.get("market_cap", 0)) or 0)
            
            conn.execute(
                "INSERT OR REPLACE INTO pool_state "
                "(timestamp, block, netuid, tao_reserve, alpha_reserve, alpha_price, liquidity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ts, block, netuid, tao_reserve, alpha_reserve, price, liquidity)
            )
            stored += 1
        except Exception as e:
            pass  # Skip malformed rows
    conn.commit()
    conn.close()
    return stored


def store_emission_history(netuid: int, emissions: list[dict]):
    """Store emission data as subnet_state entries."""
    conn = sqlite3.connect(str(MARKET_DB))
    stored = 0
    for e in emissions:
        try:
            ts = e.get("timestamp", e.get("date", ""))
            block = e.get("block", 0)
            emission = float(e.get("emission_tao", e.get("emission", 0)) or 0)
            miners = int(e.get("miners", e.get("miner_count", 0)) or 0)
            validators = int(e.get("validators", e.get("validator_count", 0)) or 0)
            stake = float(e.get("total_stake", 0) or 0)
            
            conn.execute(
                "INSERT OR REPLACE INTO subnet_state "
                "(timestamp, block, netuid, emission, registration_cost, miners, validators, stake, owner) "
                "VALUES (?, ?, ?, ?, 0, ?, ?, ?, '')",
                (ts, block, netuid, emission, miners, validators, stake)
            )
            stored += 1
        except:
            pass
    conn.commit()
    conn.close()
    return stored


def ingest_all_subnets(max_subnets: int = 130) -> dict:
    """Ingest pool history for all subnets."""
    results = {"subnets": 0, "pool_rows": 0, "emission_rows": 0, "errors": []}
    
    for netuid in range(max_subnets):
        try:
            # Pool history
            pool = fetch_subnet_history(netuid, frequency="by_hour", limit=500)
            if pool:
                stored = store_pool_history(netuid, pool)
                results["pool_rows"] += stored
            
            # Emission history
            emission = fetch_subnet_emission(netuid, limit=500)
            if emission:
                stored = store_emission_history(netuid, emission)
                results["emission_rows"] += stored
            
            results["subnets"] += 1
            
            if netuid % 10 == 0:
                print(f"  Ingested {netuid}/130 subnets...")
            
            time.sleep(0.5)  # Rate limit
            
        except Exception as e:
            results["errors"].append(f"SN{netuid}: {str(e)[:100]}")
    
    return results


if __name__ == "__main__":
    print("=== TAOStats Data Ingestion ===")
    print(f"Target: {TAOSTATS_HOST}")
    print()
    
    results = ingest_all_subnets(max_subnets=130)
    
    print(f"\n=== RESULTS ===")
    print(f"Subnets: {results['subnets']}")
    print(f"Pool rows: {results['pool_rows']}")
    print(f"Emission rows: {results['emission_rows']}")
    print(f"Errors: {len(results['errors'])}")
    
    if results['errors']:
        print("\nFirst 5 errors:")
        for e in results['errors'][:5]:
            print(f"  {e}")
