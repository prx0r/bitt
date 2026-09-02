"""Bittensor Intelligence — wired data sources for the lab.

Canonical sources (P0):
- Bittensor SDK: chain state
- TAOStats API: historical data, 156 endpoints
- Taoswap API: trading data
- dTAOscan: signed subnet data
- Binance: BTC/ETH/TAO 5m candles

Data hierarchy:
  Direct chain → TAOStats → dTAOscan → derived
  Never: AlphaGap says X → save X
  Always: block N → chain price = X → TAOStats = X → dTAOscan = X
"""
import sqlite3
import json
import http.client
import ssl
from pathlib import Path


DB_PATH = Path("/root/bitt/market.duckdb")
CTX = ssl.create_default_context()


def query_taostats(endpoint: str, params: dict = None) -> dict:
    """Query TAOStats API."""
    sys.path.insert(0, str(Path("/root/bitt")))
    from vault import Vault
    v = Vault()
    api_key = v.get("taostats_api_key")

    conn = http.client.HTTPSConnection("api.taostats.io", context=CTX, timeout=15)
    path = endpoint
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        path = f"{endpoint}?{query}"

    conn.request("GET", path, headers={
        "Authorization": f"Bearer {api_key}",
    })
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    return data


def get_subnet_history(netuid: int, hours: int = 168) -> list[dict]:
    """Get historical subnet data from TAOStats."""
    try:
        data = query_taostats(f"/v1/subnets/{netuid}/history", {"hours": hours})
        return data if isinstance(data, list) else []
    except:
        return []


def get_all_subnets() -> list[dict]:
    """Get all subnets from TAOStats."""
    try:
        data = query_taostats("/v1/subnets")
        return data if isinstance(data, list) else []
    except:
        return []


if __name__ == "__main__":
    subnets = get_all_subnets()
    print(f"Subnets: {len(subnets)}")
    for s in subnets[:5]:
        print(f"  SN{s.get('netuid', '?')}: {s.get('name', '?')}")
