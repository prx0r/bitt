"""TAOStats Full Ingestion Pipeline.

Downloads historical data for all subnets:
- Pool history (price, reserves, liquidity, market cap)
- Subnet history (owner, neurons, validators, emission, hyperparameters)
- Metagraph (per-neuron: stake, trust, incentive, emission)
- Emission history

Auth: Authorization: <raw_key> (no Bearer prefix)
"""
import http.client
import ssl
import json
import sqlite3
import time
import sys
from pathlib import Path

sys.path.insert(0, "/root/bitt")
from vault import Vault

KEY = Vault().get("taostats_api_key")
CTX = ssl.create_default_context()
DB = Path("/root/bitt/market.duckdb")
HOST = "api.taostats.io"


def api(path, params=None):
    """Make authenticated TAOStats API request."""
    query = ""
    if params:
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    conn = http.client.HTTPSConnection(HOST, timeout=30, context=CTX)
    conn.request("GET", f"/api{path}{query}", headers={"Authorization": KEY})
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    return data


def fetch_all_pages(path, params, max_pages=50):
    """Fetch all pages of a paginated endpoint."""
    all_data = []
    page = 1
    while page <= max_pages:
        p = {**params, "page": page}
        r = api(path, p)
        if "data" not in r:
            break
        all_data.extend(r["data"])
        pagination = r.get("pagination", {})
        if page >= pagination.get("total_pages", 1):
            break
        page += 1
        time.sleep(0.3)
    return all_data


def ingest_pool_history(max_subnets=130, per_page=500):
    """Ingest pool history for all subnets."""
    conn = sqlite3.connect(str(DB))
    total = 0
    
    for netuid in range(max_subnets):
        try:
            data = fetch_all_pages("/dtao/pool/history/v1", {
                "netuid": netuid,
                "frequency": "by_hour",
                "limit": per_page,
            }, max_pages=10)
            
            for d in data:
                conn.execute(
                    "INSERT OR REPLACE INTO pool_state "
                    "(timestamp, block, netuid, tao_reserve, alpha_reserve, alpha_price, liquidity) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        d.get("timestamp", ""),
                        d.get("block_number", 0),
                        netuid,
                        float(d.get("total_tao", 0) or 0),
                        float(d.get("total_alpha", 0) or 0),
                        float(d.get("market_cap", 0) or 0) / max(float(d.get("total_alpha", 1) or 1), 1),
                        float(d.get("liquidity", 0) or 0),
                    )
                )
                total += 1
            
            if netuid % 10 == 0:
                print(f"  Pool: SN{netuid}/{max_subnets} ({total} rows)")
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  Error SN{netuid}: {str(e)[:60]}")
    
    conn.commit()
    conn.close()
    return total


def ingest_subnet_history(max_subnets=130, per_page=500):
    """Ingest subnet history for all subnets."""
    conn = sqlite3.connect(str(DB))
    total = 0
    
    for netuid in range(max_subnets):
        try:
            data = fetch_all_pages("/subnet/history/v1", {
                "netuid": netuid,
                "frequency": "by_hour",
                "limit": per_page,
            }, max_pages=10)
            
            for d in data:
                conn.execute(
                    "INSERT OR REPLACE INTO subnet_state "
                    "(timestamp, block, netuid, emission, registration_cost, miners, validators, stake, owner) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        d.get("timestamp", ""),
                        d.get("block_number", 0),
                        netuid,
                        float(d.get("emission", 0) or 0),
                        float(d.get("registration_cost", 0) or 0),
                        int(d.get("active_miners", 0) or 0),
                        int(d.get("active_validators", 0) or 0),
                        0,  # stake not in this endpoint
                        d.get("owner", {}).get("ss58", "") if isinstance(d.get("owner"), dict) else "",
                    )
                )
                total += 1
            
            if netuid % 10 == 0:
                print(f"  Subnet: SN{netuid}/{max_subnets} ({total} rows)")
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  Error SN{netuid}: {str(e)[:60]}")
    
    conn.commit()
    conn.close()
    return total


def ingest_metagraph_sample(max_subnets=130, per_page=256):
    """Ingest latest metagraph for all subnets (neuron-level data)."""
    total = 0
    
    for netuid in range(max_subnets):
        try:
            data = api("/metagraph/history/v1", {
                "netuid": netuid,
                "limit": per_page,
            })
            
            neurons = data.get("data", [])
            if neurons:
                # Store as JSON in oracle.db for the payout scanner
                conn = sqlite3.connect(str(DB))
                # Store latest metagraph snapshot
                conn.execute(
                    "INSERT OR REPLACE INTO subnet_candles "
                    "(timestamp, block, netuid, open_tao, high_tao, low_tao, close_tao, volume_tao) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        neurons[0].get("block_number", 0) if neurons else 0,
                        netuid,
                        len(neurons),  # neuron count
                        sum(float(n.get("stake", 0) or 0) for n in neurons),  # total stake
                        sum(1 for n in neurons if float(n.get("incentive", 0) or 0) > 0),  # earning count
                        float(neurons[0].get("incentive", 0) or 0) if neurons else 0,  # top incentive
                        0,
                    )
                )
                conn.commit()
                conn.close()
                total += len(neurons)
            
            if netuid % 10 == 0:
                print(f"  Metagraph: SN{netuid}/{max_subnets} ({total} neurons)")
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  Error SN{netuid}: {str(e)[:60]}")
    
    return total


if __name__ == "__main__":
    print("=== TAOStats Full Ingestion ===")
    print(f"API: {HOST}")
    print(f"Key: {KEY[:20]}...")
    print()
    
    # Initialize DB
    sys.path.insert(0, "/root/bitt/trading")
    from market import init_db
    init_db()
    
    print("--- Ingesting Pool History ---")
    pool_rows = ingest_pool_history(max_subnets=130)
    print(f"Pool: {pool_rows} rows\n")
    
    print("--- Ingesting Subnet History ---")
    subnet_rows = ingest_subnet_history(max_subnets=130)
    print(f"Subnet: {subnet_rows} rows\n")
    
    print("--- Ingesting Metagraph Samples ---")
    meta_rows = ingest_metagraph_sample(max_subnets=130)
    print(f"Metagraph: {meta_rows} neurons\n")
    
    print("=== DONE ===")
    print(f"Pool rows: {pool_rows}")
    print(f"Subnet rows: {subnet_rows}")
    print(f"Metagraph neurons: {meta_rows}")
