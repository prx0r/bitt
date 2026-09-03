"""TAOStats Rate-Limited Ingestion with Exponential Backoff.

Handles API rate limits gracefully:
- 1 second between requests
- Exponential backoff on 429/500
- Resume from where we left off
- Progress tracking
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

# Rate limit state
_last_request = 0
_consecutive_errors = 0
REQUEST_DELAY = 1.0  # seconds between requests


def api(path, params=None, retries=3):
    """Make API request with retry and backoff."""
    global _last_request, _consecutive_errors
    
    # Enforce minimum delay
    elapsed = time.time() - _last_request
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    
    for attempt in range(retries):
        try:
            query = ""
            if params:
                query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
            
            conn = http.client.HTTPSConnection(HOST, timeout=30, context=CTX)
            conn.request("GET", f"/api{path}{query}", headers={"Authorization": KEY})
            resp = conn.getresponse()
            _last_request = time.time()
            
            data = json.loads(resp.read().decode())
            conn.close()
            
            if resp.status == 429:
                # Rate limited
                wait = (2 ** attempt) * 2
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                _consecutive_errors += 1
                continue
            
            if resp.status >= 500:
                wait = (2 ** attempt) * 2
                time.sleep(wait)
                _consecutive_errors += 1
                continue
            
            _consecutive_errors = 0
            return data
            
        except Exception as e:
            wait = (2 ** attempt) * 2
            time.sleep(wait)
            _consecutive_errors += 1
    
    return {"error": "max_retries_exceeded"}


def backfill_pool_history(netuid: int, max_pages: int = 20):
    """Backfill pool history for one subnet with pagination."""
    conn = sqlite3.connect(str(DB))
    total = 0
    
    for page in range(1, max_pages + 1):
        data = api("/dtao/pool/history/v1", {
            "netuid": netuid,
            "frequency": "by_hour",
            "limit": 500,
            "page": page,
        })
        
        if "error" in data or "data" not in data:
            break
        
        rows = data["data"]
        if not rows:
            break
        
        for d in rows:
            try:
                ts = d.get("timestamp", "")
                block = d.get("block_number", 0)
                price = float(d.get("market_cap", 0) or 0) / max(float(d.get("total_alpha", 1) or 1), 1)
                tao = float(d.get("total_tao", 0) or 0)
                alpha = float(d.get("total_alpha", 0) or 0)
                liq = float(d.get("liquidity", 0) or 0)
                
                conn.execute(
                    "INSERT OR REPLACE INTO pool_state "
                    "(timestamp, block, netuid, tao_reserve, alpha_reserve, alpha_price, liquidity) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ts, block, netuid, tao, alpha, price, liq)
                )
                total += 1
            except:
                pass
        
        pagination = data.get("pagination", {})
        if page >= pagination.get("total_pages", 1):
            break
    
    conn.commit()
    conn.close()
    return total


def backfill_all(max_subnets=130):
    """Backfill pool history for all subnets."""
    results = {"subnets": 0, "total_rows": 0, "errors": []}
    
    # Check progress file
    progress_file = Path("/root/bitt/trading/experiments/backfill_progress.json")
    start_netuid = 0
    if progress_file.exists():
        with open(progress_file) as f:
            prog = json.load(f)
            start_netuid = prog.get("last_netuid", 0)
            print(f"Resuming from SN{start_netuid}")
    
    for netuid in range(start_netuid, max_subnets):
        try:
            rows = backfill_pool_history(netuid, max_pages=10)
            results["total_rows"] += rows
            results["subnets"] += 1
            
            # Save progress
            with open(progress_file, "w") as f:
                json.dump({"last_netuid": netuid + 1, "total_rows": results["total_rows"]}, f)
            
            if netuid % 10 == 0:
                print(f"  SN{netuid}: {rows} rows (total: {results['total_rows']})")
            
        except Exception as e:
            results["errors"].append(f"SN{netuid}: {str(e)[:80]}")
    
    return results


if __name__ == "__main__":
    print("=== TAOStats Backfill (Rate-Limited) ===")
    print(f"Delay: {REQUEST_DELAY}s between requests")
    print()
    
    results = backfill_all(max_subnets=130)
    
    print(f"\n=== RESULTS ===")
    print(f"Subnets: {results['subnets']}")
    print(f"Total rows: {results['total_rows']}")
    print(f"Errors: {len(results['errors'])}")
