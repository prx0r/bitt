"""Per-subnet live data — leaderboard, API, and competition intelligence.

For each target subnet, pulls:
  - Leaderboard from subnet API/website
  - Current champion/miner details
  - Submission history if available
  - Competition metrics

Organized in subnets/{sn}-{name}/leaderboard.json
"""
from __future__ import annotations

import json
import http.client
import ssl
import time
from datetime import datetime
from pathlib import Path

SUBNETS_DIR = Path("/root/bitt/subnets")
_CTX = ssl.create_default_context()


def _http_get(host: str, path: str, timeout: int = 15) -> dict | None:
    conn = http.client.HTTPSConnection(host, context=_CTX, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read().decode()
        if resp.status == 200:
            return json.loads(body)
    except Exception:
        pass
    finally:
        conn.close()
    return None


def fetch_ditto_leaderboard() -> dict:
    """Fetch Ditto leaderboard from dittobench.com."""
    # Try the API
    data = _http_get("dittobench.com", "/api/leaderboard")
    if data:
        return {"source": "dittobench_api", "data": data, "fetched_at": datetime.utcnow().isoformat()}
    
    # Try GitHub for latest benchmark results
    data = _http_get("api.github.com", "/repos/ditto-assistant/ditto-subnet/commits?per_page=5")
    if data:
        commits = [{"sha": c["sha"][:8], "message": c["commit"]["message"][:100], "date": c["commit"]["author"]["date"]} for c in data]
        return {"source": "github_commits", "data": commits, "fetched_at": datetime.utcnow().isoformat()}
    
    return {"source": "unavailable", "fetched_at": datetime.utcnow().isoformat()}


def fetch_ridges_leaderboard() -> dict:
    """Fetch Ridges leaderboard."""
    data = _http_get("api.github.com", "/repos/ridgesai/ridges/commits?per_page=5")
    if data:
        commits = [{"sha": c["sha"][:8], "message": c["commit"]["message"][:100]} for c in data]
        return {"source": "github_commits", "data": commits, "fetched_at": datetime.utcnow().isoformat()}
    return {"source": "unavailable", "fetched_at": datetime.utcnow().isoformat()}


def fetch_minos_leaderboard() -> dict:
    """Fetch Minos leaderboard."""
    data = _http_get("api.github.com", "/repos/minos-protocol/minos_subnet/commits?per_page=5")
    if data:
        commits = [{"sha": c["sha"][:8], "message": c["commit"]["message"][:100]} for c in data]
        return {"source": "github_commits", "data": commits, "fetched_at": datetime.utcnow().isoformat()}
    return {"source": "unavailable", "fetched_at": datetime.utcnow().isoformat()}


def fetch_harnyx_leaderboard() -> dict:
    """Fetch Harnyx leaderboard."""
    data = _http_get("api.github.com", "/repos/harnyx/harnyx/commits?per_page=5")
    if data:
        commits = [{"sha": c["sha"][:8], "message": c["commit"]["message"][:100]} for c in data]
        return {"source": "github_commits", "data": commits, "fetched_at": datetime.utcnow().isoformat()}
    return {"source": "unavailable", "fetched_at": datetime.utcnow().isoformat()}


def fetch_chutes_leaderboard() -> dict:
    """Fetch Chutes leaderboard."""
    data = _http_get("api.github.com", "/repos/chutesai/chutes/commits?per_page=5")
    if data:
        commits = [{"sha": c["sha"][:8], "message": c["commit"]["message"][:100]} for c in data]
        return {"source": "github_commits", "data": commits, "fetched_at": datetime.utcnow().isoformat()}
    return {"source": "unavailable", "fetched_at": datetime.utcnow().isoformat()}


# Registry of fetchers
FETCHERS = {
    118: fetch_ditto_leaderboard,
    62: fetch_ridges_leaderboard,
    107: fetch_minos_leaderboard,
    67: fetch_harnyx_leaderboard,
    64: fetch_chutes_leaderboard,
}


def fetch_all_leaderboards() -> dict[int, dict]:
    """Fetch leaderboards for all target subnets."""
    results = {}
    for netuid, fetcher in FETCHERS.items():
        try:
            results[netuid] = fetcher()
        except Exception as e:
            results[netuid] = {"source": "error", "error": str(e)}
        time.sleep(0.5)
    return results


def save_leaderboard(netuid: int, data: dict):
    """Save leaderboard data to subnet folder."""
    subnet_dirs = list(SUBNETS_DIR.glob(f"sn{netuid}-*"))
    if subnet_dirs:
        path = subnet_dirs[0] / "leaderboard.json"
        path.write_text(json.dumps(data, indent=2, default=str))


def load_leaderboard(netuid: int) -> dict | None:
    """Load saved leaderboard."""
    subnet_dirs = list(SUBNETS_DIR.glob(f"sn{netuid}-*"))
    if subnet_dirs:
        path = subnet_dirs[0] / "leaderboard.json"
        if path.exists():
            return json.loads(path.read_text())
    return None
