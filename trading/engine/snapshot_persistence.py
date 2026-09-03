"""Daily Snapshot Persistence — the moat builder.

Every scan, every day, stored forever. This is what makes the dataset unique.

Tables:
- daily_subnet_scan: one row per subnet per day (append-only)
- daily_scan_log: one row per scan run (metadata)
- daily_alerts: triggered alerts from delta detection

After 30 days: pattern recognition
After 90 days: statistical significance
After 365 days: unique dataset nobody else has
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime


MARKET_DB = Path("/root/bitt/market.duckdb")


def init_persistence_tables():
    """Create persistence tables (append-only)."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.executescript("""
        -- Daily subnet scan results (append-only, never overwrite)
        CREATE TABLE IF NOT EXISTS daily_subnet_scan (
            scan_id TEXT NOT NULL,
            scan_date TEXT NOT NULL,
            scan_timestamp TEXT NOT NULL,
            netuid INTEGER NOT NULL,
            -- Scores
            total_score REAL,
            easiness REAL,
            yield_score REAL,
            stability REAL,
            access_score REAL,
            stickiness REAL,
            -- Economics
            emission_per_neuron REAL,
            competition_ratio REAL,
            emit_ratio REAL,
            neurons INTEGER,
            emitting INTEGER,
            validators INTEGER,
            -- Price
            alpha_price REAL,
            alpha_price_usd REAL,
            -- Liquidity
            tao_reserve REAL,
            liquidity REAL,
            -- Entry economics
            reg_cost_tao REAL,
            open_slots INTEGER,
            max_neurons INTEGER,
            days_to_roi REAL,
            -- Classification
            classification TEXT,
            topology TEXT,
            ripeness TEXT,
            -- Market context
            tao_usd REAL,
            btc_usd REAL,
            -- Raw data hash for dedup
            data_hash TEXT,
            PRIMARY KEY (scan_id, netuid)
        );
        
        -- Scan log (metadata per run)
        CREATE TABLE IF NOT EXISTS daily_scan_log (
            scan_id TEXT PRIMARY KEY,
            scan_date TEXT NOT NULL,
            scan_timestamp TEXT NOT NULL,
            subnets_scanned INTEGER,
            actionable_count INTEGER,
            avg_score REAL,
            top_subnet INTEGER,
            top_score REAL,
            duration_ms INTEGER,
            data_source TEXT,
            block_number INTEGER
        );
        
        -- Alerts from delta detection
        CREATE TABLE IF NOT EXISTS daily_alerts (
            alert_id TEXT PRIMARY KEY,
            scan_date TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            netuid INTEGER NOT NULL,
            metric TEXT,
            old_value REAL,
            new_value REAL,
            delta REAL,
            severity TEXT,
            details TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_dss_date ON daily_subnet_scan(scan_date);
        CREATE INDEX IF NOT EXISTS idx_dss_netuid ON daily_subnet_scan(netuid);
        CREATE INDEX IF NOT EXISTS idx_dss_scan_id ON daily_subnet_scan(scan_id);
    """)
    conn.commit()
    conn.close()


def generate_scan_id() -> str:
    """Generate unique scan ID."""
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def store_scan_results(scores: list[dict], scan_date: str, 
                       tao_usd: float = 0, btc_usd: float = 0,
                       block: int = 0) -> str:
    """Store scan results (append-only). Returns scan_id."""
    scan_id = generate_scan_id()
    timestamp = datetime.utcnow().isoformat()
    
    conn = sqlite3.connect(str(MARKET_DB))
    
    for s in scores:
        if s.get("skip"):
            continue
        
        # Calculate data hash for dedup
        data_str = json.dumps({
            "netuid": s.get("netuid"),
            "price": s.get("price"),
            "emission": s.get("emission_day"),
            "neurons": s.get("neurons"),
        }, sort_keys=True)
        data_hash = str(hash(data_str))
        
        conn.execute(
            "INSERT OR IGNORE INTO daily_subnet_scan "
            "(scan_id, scan_date, scan_timestamp, netuid, total_score, easiness, "
            "yield_score, stability, access_score, stickiness, emission_per_neuron, "
            "competition_ratio, emit_ratio, neurons, emitting, validators, alpha_price, "
            "alpha_price_usd, tao_reserve, liquidity, reg_cost_tao, open_slots, "
            "max_neurons, days_to_roi, classification, topology, ripeness, "
            "tao_usd, btc_usd, data_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scan_id, scan_date, timestamp, s["netuid"],
                s.get("total", 0), s.get("easiness", 0), s.get("yield_score", 0),
                s.get("stability", 0), s.get("access", 0), s.get("stickiness", 0),
                s.get("emission_per_neuron", 0), s.get("competition_ratio", 0),
                s.get("emit_ratio", 0), s.get("neurons", 0), s.get("emitting", 0),
                s.get("validators", 0), s.get("price", 0),
                round(s.get("price", 0) * tao_usd, 4) if tao_usd else 0,
                s.get("tao_reserve", 0), s.get("liquidity", 0),
                s.get("reg_cost_tao", 0), s.get("open_slots", 0),
                s.get("max_neurons", 256), s.get("days_to_roi", 999),
                s.get("classification", ""), s.get("topology", ""),
                s.get("ripeness", ""),
                tao_usd, btc_usd, data_hash,
            )
        )
    
    # Store scan log
    actionable = len([s for s in scores if not s.get("skip") and s.get("total", 0) > 30])
    valid = [s for s in scores if not s.get("skip")]
    
    conn.execute(
        "INSERT OR IGNORE INTO daily_scan_log "
        "(scan_id, scan_date, scan_timestamp, subnets_scanned, actionable_count, "
        "avg_score, top_subnet, top_score, data_source, block_number) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            scan_id, scan_date, timestamp,
            len(valid), actionable,
            round(sum(s.get("total", 0) for s in valid) / max(len(valid), 1), 1),
            valid[0]["netuid"] if valid else 0,
            valid[0].get("total", 0) if valid else 0,
            "oracle+taostats",
            block,
        )
    )
    
    conn.commit()
    conn.close()
    
    return scan_id


def detect_deltas(scan_date: str, scores: list[dict]) -> list[dict]:
    """Compare to previous scan and detect significant changes."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    
    # Get previous scan
    prev = conn.execute(
        "SELECT * FROM daily_subnet_scan WHERE scan_date < ? ORDER BY scan_date DESC LIMIT 130",
        (scan_date,)
    ).fetchall()
    conn.close()
    
    if not prev:
        return []
    
    # Index by netuid
    prev_map = {r['netuid']: dict(r) for r in prev}
    
    alerts = []
    for s in scores:
        if s.get("skip"):
            continue
        
        netuid = s["netuid"]
        if netuid not in prev_map:
            continue
        
        p = prev_map[netuid]
        
        # Check significant changes
        checks = [
            ("total_score", "score_change", 10),
            ("emission_per_neuron", "yield_change", 0.1),
            ("open_slots", "slots_change", 10),
            ("competition_ratio", "competition_change", 0.1),
            ("days_to_roi", "roi_change", 5),
        ]
        
        for metric, alert_type, threshold in checks:
            old = p.get(metric, 0) or 0
            new = s.get(metric, 0) or 0
            delta = new - old
            
            if abs(delta) > threshold:
                severity = "high" if abs(delta) > threshold * 2 else "medium"
                alerts.append({
                    "alert_type": alert_type,
                    "netuid": netuid,
                    "metric": metric,
                    "old_value": round(old, 4),
                    "new_value": round(new, 4),
                    "delta": round(delta, 4),
                    "severity": severity,
                })
    
    return alerts


def get_scan_history(netuid: int = None, days: int = 30) -> list[dict]:
    """Get historical scan results."""
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    
    if netuid is not None:
        rows = conn.execute(
            "SELECT * FROM daily_subnet_scan WHERE netuid = ? ORDER BY scan_date DESC LIMIT ?",
            (netuid, days * 130)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM daily_subnet_scan ORDER BY scan_date DESC LIMIT ?",
            (days * 130,)
        ).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("=== Daily Snapshot Persistence ===\n")
    
    init_persistence_tables()
    
    # Load existing scan results
    import sys
    sys.path.insert(0, "/root/bitt/trading/engine")
    
    scan_file = Path("/root/bitt/trading/experiments/full_scan.json")
    if scan_file.exists():
        with open(scan_file) as f:
            scores = json.load(f)
        print(f"Loaded {len(scores)} scores from full_scan.json")
    else:
        print("No scan file found, running fresh scan...")
        from low_fruit_scan_v2 import fetch_current_subnets_from_oracle, fetch_subnet_economics, score_low_fruit_v2
        subnets = fetch_current_subnets_from_oracle()
        scores = []
        for subnet in subnets:
            netuid = subnet.get('netuid', 0)
            econ = fetch_subnet_economics(netuid)
            if econ:
                score = score_low_fruit_v2(subnet, econ)
                if not score.get("skip"):
                    scores.append(score)
    
    scan_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    scan_id = store_scan_results(
        scores,
        scan_date,
        tao_usd=217.9,
        btc_usd=0,
        block=0,
    )
    
    print(f"Stored scan {scan_id}")
    print(f"Subnets: {len(scores)}")
    
    # Check history
    history = get_scan_history()
    print(f"\nTotal historical scans: {len(history)}")
