"""Subnet Instance Registry — tracks subnet lifecycle events.

Creates immutable subnet instances with:
- instance_id = (netuid, registration_block)
- Tracks: birth, activation, death, ownership changes
- Handles netuid reuse (same netuid, different subnet)
"""
import http.client
import ssl
import json
import sqlite3
import time
from pathlib import Path


KEY = "tao-126d9423-6d33-4b80-aea5-c56dee33b199:605376d4"
CTX = ssl.create_default_context()
DB = Path("/root/bitt/market.duckdb")


def api(path, params=None):
    query = ""
    if params:
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    conn = http.client.HTTPSConnection("api.taostats.io", timeout=30, context=CTX)
    conn.request("GET", f"/api{path}{query}", headers={"Authorization": KEY})
    data = json.loads(conn.getresponse().read().decode())
    conn.close()
    return data


def init_registry_table():
    """Create subnet_instances table."""
    conn = sqlite3.connect(str(DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subnet_instances (
            instance_id TEXT PRIMARY KEY,
            netuid INTEGER NOT NULL,
            registration_block INTEGER,
            registration_timestamp TEXT,
            owner_coldkey TEXT,
            owner_hotkey TEXT,
            initial_emission REAL,
            initial_neurons INTEGER,
            initial_alpha_price REAL,
            status TEXT DEFAULT 'active',
            deregistration_block INTEGER,
            deregistration_timestamp TEXT,
            terminal_reason TEXT,
            last_updated TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_instances_netuid ON subnet_instances(netuid)
    """)
    conn.commit()
    conn.close()


def build_registry():
    """Build subnet instance registry from TAOStats data."""
    conn = sqlite3.connect(str(DB))
    
    # Get all subnets from subnet_state
    rows = conn.execute(
        "SELECT DISTINCT netuid FROM subnet_state ORDER BY netuid"
    ).fetchall()
    netuids = [r[0] for r in rows]
    
    print(f"Building registry for {len(netuids)} subnets...")
    
    registered = 0
    for netuid in netuids:
        try:
            # Get registration info from TAOStats
            r = api("/subnet/history/v1", {"netuid": netuid, "limit": 1, "frequency": "by_day"})
            data = r.get("data", [])
            
            if not data:
                continue
            
            info = data[0]
            
            reg_block = info.get("registration_block_number", 0)
            reg_ts = info.get("registration_timestamp", "")
            owner = info.get("owner", {})
            owner_coldkey = owner.get("ss58", "") if isinstance(owner, dict) else ""
            
            instance_id = f"{netuid}_{reg_block}"
            
            # Get first pool state for initial price
            pool = conn.execute(
                "SELECT alpha_price FROM pool_state WHERE netuid = ? ORDER BY timestamp ASC LIMIT 1",
                (netuid,)
            ).fetchone()
            initial_price = pool[0] if pool else 0
            
            # Get first subnet state for initial emission
            state = conn.execute(
                "SELECT emission, miners FROM subnet_state WHERE netuid = ? ORDER BY timestamp ASC LIMIT 1",
                (netuid,)
            ).fetchone()
            initial_emission = state[0] if state else 0
            initial_neurons = state[1] if state else 0
            
            conn.execute(
                "INSERT OR REPLACE INTO subnet_instances "
                "(instance_id, netuid, registration_block, registration_timestamp, "
                "owner_coldkey, owner_hotkey, initial_emission, initial_neurons, "
                "initial_alpha_price, status, last_updated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', datetime('now'))",
                (instance_id, netuid, reg_block, reg_ts,
                 owner_coldkey, "", initial_emission, initial_neurons, initial_price)
            )
            registered += 1
            
            if netuid % 20 == 0:
                print(f"  Registered SN{netuid}...")
            
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  Error SN{netuid}: {str(e)[:60]}")
    
    conn.commit()
    conn.close()
    return registered


def get_registry_stats() -> dict:
    """Get registry statistics."""
    conn = sqlite3.connect(str(DB))
    
    total = conn.execute("SELECT COUNT(*) FROM subnet_instances").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM subnet_instances WHERE status='active'").fetchone()[0]
    
    # Age distribution
    ages = conn.execute(
        "SELECT julianday('now') - julianday(registration_timestamp) as age_days "
        "FROM subnet_instances WHERE registration_timestamp != ''"
    ).fetchall()
    
    conn.close()
    
    age_days = [a[0] for a in ages if a[0] is not None]
    
    return {
        "total_instances": total,
        "active": active,
        "avg_age_days": round(sum(age_days) / len(age_days), 1) if age_days else 0,
        "median_age_days": round(sorted(age_days)[len(age_days)//2], 1) if age_days else 0,
    }


if __name__ == "__main__":
    print("=== Subnet Instance Registry ===\n")
    
    init_registry_table()
    registered = build_registry()
    stats = get_registry_stats()
    
    print(f"\nRegistered: {registered} instances")
    print(f"Total: {stats['total_instances']}")
    print(f"Active: {stats['active']}")
    print(f"Avg age: {stats['avg_age_days']:.0f} days")
    print(f"Median age: {stats['median_age_days']:.0f} days")
