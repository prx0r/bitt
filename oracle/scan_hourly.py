#!/usr/bin/env python3
"""Hourly chain scanner — builds historical data for analytics.

Run via cron:
  0 * * * * cd /root/bitt && python3 oracle/scan_hourly.py >> /root/bitt/logs/scan.log 2>&1

Or manually:
  python3 oracle/scan_hourly.py
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.chain_scanner import init_db, scan_all_detailed, store_snapshots
from oracle.analytics import (
    init_analytics_db, populate_metrics, compute_opportunity_scores,
    get_network_summary, get_opportunity_leaders,
)

def run():
    now = datetime.utcnow().isoformat()
    print(f"[{now}] Starting scan...")

    # Init DBs
    db = init_db()
    init_analytics_db(db)

    # Scan
    snapshots = scan_all_detailed(progress=False)
    store_snapshots(db, snapshots)
    print(f"[{now}] Scanned {len(snapshots)} subnets")

    # Update analytics
    n = populate_metrics(db)
    compute_opportunity_scores(db)
    print(f"[{now}] Updated analytics ({n} metrics)")

    # Quick summary
    summary = get_network_summary(db)
    leaders = get_opportunity_leaders(db, 5)
    print(f"[{now}] TAO/day: {summary['total_tao_day']:.2f} | Emitting: {summary['total_emitting']}")
    if leaders:
        top = leaders[0]
        print(f"[{now}] Top: SN{top['netuid']} {top['name']} (score={top['score']:.3f})")

    db.close()


if __name__ == "__main__":
    run()
