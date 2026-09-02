"""Oracle Analytics — compute mining opportunity metrics over time.

Tables:
  subnet_metrics     — denormalized per-scan metrics (fast SQL queries)
  opportunity_scores — computed opportunity scores per subnet per scan

Key metrics tracked:
  - TAO equiv/day (reward)
  - Alpha price (risk)
  - Emitting miners (competition)
  - HHI (concentration)
  - Burn (entry cost)
  - Score stability over time
  - Trend direction

Analytics queries for dashboard:
  - Line charts: TAO/day over time per subnet
  - Stability ranking: lowest variance TAO/day
  - Trend detection: improving vs declining subnets
  - Opportunity score: composite of reward, competition, stability, cost
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/root/bitt/oracle.db")


def init_analytics_db(conn: sqlite3.Connection):
    """Create analytics tables."""
    # Denormalized metrics — one row per subnet per scan
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subnet_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT NOT NULL,
            chain_block INTEGER NOT NULL,
            netuid INTEGER NOT NULL,
            name TEXT,
            -- Economics
            burn_tao REAL,
            alpha_price REAL,
            tao_equiv_day REAL,
            total_alpha_day REAL,
            -- Competition
            neuron_count INTEGER,
            active_count INTEGER,
            validator_count INTEGER,
            miner_count INTEGER,
            emitting_count INTEGER,
            -- Concentration
            hhi REAL,
            effective_earners REAL,
            top1_incentive REAL,
            top5_incentive REAL,
            -- Tempo
            tempo INTEGER,
            -- Unique per scan
            UNIQUE(scanned_at, netuid)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_netuid ON subnet_metrics(netuid, scanned_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_time ON subnet_metrics(scanned_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_tao ON subnet_metrics(tao_equiv_day DESC)")

    # Opportunity scores — computed per subnet per scan
    conn.execute("""
        CREATE TABLE IF NOT EXISTS opportunity_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT NOT NULL,
            netuid INTEGER NOT NULL,
            -- Component scores (0-1)
            reward_score REAL,
            competition_score REAL,
            stability_score REAL,
            trend_score REAL,
            cost_score REAL,
            concentration_score REAL,
            -- Composite
            opportunity_score REAL,
            recommendation TEXT,
            UNIQUE(scanned_at, netuid)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_os_netuid ON opportunity_scores(netuid, scanned_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_os_score ON opportunity_scores(opportunity_score DESC)")

    conn.commit()


def populate_metrics(conn: sqlite3.Connection):
    """Fill subnet_metrics from existing subnet_snapshots."""
    cur = conn.execute("""
        SELECT scanned_at, chain_block, netuid, data FROM subnet_snapshots
        ORDER BY scanned_at
    """)

    inserted = 0
    for row in cur:
        scanned_at, chain_block, netuid, data_json = row
        d = json.loads(data_json)

        try:
            conn.execute("""
                INSERT OR IGNORE INTO subnet_metrics
                (scanned_at, chain_block, netuid, name, burn_tao, alpha_price,
                 tao_equiv_day, total_alpha_day, neuron_count, active_count,
                 validator_count, miner_count, emitting_count, hhi,
                 effective_earners, top1_incentive, top5_incentive, tempo)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                scanned_at, chain_block, netuid, d.get("name"),
                d.get("burn_tao"), d.get("alpha_price"),
                d.get("tao_equiv_day"), d.get("total_alpha_day"),
                d.get("neuron_count"), d.get("active_count"),
                d.get("validator_count"), d.get("miner_count"),
                d.get("emitting_count"), d.get("hhi"),
                d.get("effective_earners"), d.get("top1_incentive"),
                d.get("top5_incentive"), d.get("tempo"),
            ))
            inserted += 1
        except Exception:
            pass

    conn.commit()
    return inserted


def compute_opportunity_scores(conn: sqlite3.Connection):
    """Compute opportunity scores for all subnets in latest scan."""
    # Get all scans
    cur = conn.execute("SELECT DISTINCT scanned_at FROM subnet_metrics ORDER BY scanned_at")
    scans = [row[0] for row in cur.fetchall()]

    if not scans:
        return

    # For each scan, compute scores
    for scan_ts in scans:
        cur = conn.execute(
            "SELECT * FROM subnet_metrics WHERE scanned_at = ?", (scan_ts,)
        )
        rows = cur.fetchall()

        # Get column names
        cols = [desc[0] for desc in cur.description]

        for row in rows:
            data = dict(zip(cols, row))
            score = _compute_one_score(conn, data, scan_ts)
            if score:
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO opportunity_scores
                        (scanned_at, netuid, reward_score, competition_score,
                         stability_score, trend_score, cost_score,
                         concentration_score, opportunity_score, recommendation)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        scan_ts, data["netuid"],
                        score["reward"], score["competition"],
                        score["stability"], score["trend"],
                        score["cost"], score["concentration"],
                        score["total"], score["recommendation"],
                    ))
                except Exception:
                    pass

    conn.commit()


def _compute_one_score(conn, data: dict, scan_ts: str) -> dict | None:
    """Compute opportunity score for one subnet at one time."""
    tao = data.get("tao_equiv_day", 0) or 0
    miners = data.get("emitting_count", 0) or 0
    burn = data.get("burn_tao", 0) or 0
    hhi = data.get("hhi", 0) or 0
    emitting = data.get("emitting_count", 0) or 0
    netuid = data.get("netuid")

    # Reward score: higher TAO/day = better (log scale, cap at 500 TAO)
    reward = min(1.0, math.log1p(tao) / math.log1p(500))

    # Competition score: fewer emitting miners = easier to enter
    if emitting <= 1:
        competition = 1.0
    elif emitting <= 5:
        competition = 0.8
    elif emitting <= 20:
        competition = 0.5
    elif emitting <= 50:
        competition = 0.3
    else:
        competition = 0.1

    # Stability score: variance of TAO/day over recent scans
    history = _get_recent_tao(conn, netuid, scan_ts, n=10)
    if len(history) >= 3:
        mean_tao = sum(history) / len(history)
        variance = sum((x - mean_tao) ** 2 for x in history) / len(history)
        cv = math.sqrt(variance) / max(mean_tao, 0.001)  # coefficient of variation
        stability = max(0, 1.0 - cv)  # lower CV = more stable
    else:
        stability = 0.5  # not enough data

    # Trend score: is TAO/day increasing or decreasing?
    if len(history) >= 2:
        recent = history[0]
        older = history[-1]
        if older > 0:
            change = (recent - older) / older
            trend = min(1.0, max(0.0, 0.5 + change * 2))  # 0=declining, 1=improving
        else:
            trend = 0.5
    else:
        trend = 0.5

    # Cost score: lower burn = easier entry
    if burn <= 0.001:
        cost = 1.0
    elif burn <= 0.01:
        cost = 0.8
    elif burn <= 0.1:
        cost = 0.5
    elif burn <= 0.5:
        cost = 0.3
    else:
        cost = 0.1

    # Concentration: lower HHI = more distributed = better for newcomers
    concentration = max(0, 1.0 - hhi)

    # Composite score
    total = (
        0.30 * reward      # how much you can earn
        + 0.20 * competition  # how easy to get in
        + 0.15 * stability   # how predictable
        + 0.10 * trend       # improving or declining
        + 0.15 * cost        # how cheap to enter
        + 0.10 * concentration  # how distributed
    )

    # Recommendation
    if total >= 0.7 and reward >= 0.5:
        rec = "STRONG_OPPORTUNITY"
    elif total >= 0.5 and reward >= 0.3:
        rec = "GOOD_OPPORTUNITY"
    elif total >= 0.3:
        rec = "MODERATE"
    elif reward >= 0.3 and competition < 0.3:
        rec = "HIGH_REWARD_HIGH_COMPETITION"
    else:
        rec = "WEAK"

    return {
        "reward": round(reward, 4),
        "competition": round(competition, 4),
        "stability": round(stability, 4),
        "trend": round(trend, 4),
        "cost": round(cost, 4),
        "concentration": round(concentration, 4),
        "total": round(total, 4),
        "recommendation": rec,
    }


def _get_recent_tao(conn, netuid: int, before: str, n: int = 10) -> list[float]:
    """Get recent TAO/day values for a subnet."""
    cur = conn.execute("""
        SELECT tao_equiv_day FROM subnet_metrics
        WHERE netuid = ? AND scanned_at <= ?
        ORDER BY scanned_at DESC LIMIT ?
    """, (netuid, before, n))
    return [row[0] for row in cur.fetchall() if row[0] is not None]


# ─── Analytics queries for dashboard ────────────────────────────────

def get_tao_time_series(conn, netuid: int, hours: int = 168) -> list[dict]:
    """TAO/day line chart data for one subnet."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    cur = conn.execute("""
        SELECT scanned_at, tao_equiv_day, alpha_price, emitting_count, hhi
        FROM subnet_metrics
        WHERE netuid = ? AND scanned_at >= ?
        ORDER BY scanned_at
    """, (netuid, cutoff))
    return [{"time": r[0], "tao_day": r[1], "alpha_price": r[2],
             "emitting": r[3], "hhi": r[4]} for r in cur.fetchall()]


def get_stability_ranking(conn, n: int = 30) -> list[dict]:
    """Rank subnets by TAO/day stability (lowest coefficient of variation)."""
    cur = conn.execute("""
        SELECT netuid, name,
               AVG(tao_equiv_day) as avg_tao,
               COUNT(*) as scans,
               MIN(tao_equiv_day) as min_tao,
               MAX(tao_equiv_day) as max_tao
        FROM subnet_metrics
        GROUP BY netuid
        HAVING scans >= 2 AND avg_tao > 0
        ORDER BY (MAX(tao_equiv_day) - MIN(tao_equiv_day)) / MAX(avg_tao, 0.001) ASC
        LIMIT ?
    """, (n,))
    return [{"netuid": r[0], "name": r[1], "avg_tao": round(r[2], 4),
             "scans": r[3], "min_tao": round(r[4], 4), "max_tao": round(r[5], 4),
             "volatility": round((r[5] - r[4]) / max(r[2], 0.001), 4)}
            for r in cur.fetchall()]


def get_trend_ranking(conn, n: int = 30) -> list[dict]:
    """Rank subnets by recent trend (improving vs declining)."""
    cur = conn.execute("""
        SELECT netuid, name,
               (SELECT tao_equiv_day FROM subnet_metrics m2
                WHERE m2.netuid = m1.netuid ORDER BY m2.scanned_at DESC LIMIT 1) as latest,
               (SELECT tao_equiv_day FROM subnet_metrics m2
                WHERE m2.netuid = m1.netuid ORDER BY m2.scanned_at ASC LIMIT 1) as earliest
        FROM subnet_metrics m1
        GROUP BY netuid
        HAVING latest > 0
        ORDER BY (latest - earliest) / MAX(earliest, 0.001) DESC
        LIMIT ?
    """, (n,))
    results = []
    for r in cur.fetchall():
        change = ((r[2] or 0) - (r[3] or 0)) / max(r[3] or 0.001, 0.001)
        results.append({"netuid": r[0], "name": r[1],
                        "latest_tao": round(r[2] or 0, 4),
                        "change_pct": round(change * 100, 1)})
    return results


def get_opportunity_leaders(conn, n: int = 30) -> list[dict]:
    """Top subnets by composite opportunity score."""
    cur = conn.execute("""
        SELECT os.*, sm.name FROM opportunity_scores os
        JOIN subnet_metrics sm ON os.netuid = sm.netuid AND os.scanned_at = sm.scanned_at
        WHERE os.scanned_at = (SELECT MAX(scanned_at) FROM opportunity_scores)
        ORDER BY os.opportunity_score DESC
        LIMIT ?
    """, (n,))
    return [{"netuid": r[2], "name": r[-1],
             "reward": r[3], "competition": r[4], "stability": r[5],
             "trend": r[6], "cost": r[7], "concentration": r[8],
             "score": r[9], "rec": r[10]}
            for r in cur.fetchall()]


def get_network_summary(conn) -> dict:
    """Network-wide summary stats."""
    cur = conn.execute("""
        SELECT COUNT(DISTINCT netuid) as subnets,
               SUM(tao_equiv_day) as total_tao,
               AVG(alpha_price) as avg_price,
               SUM(emitting_count) as total_emitting
        FROM subnet_metrics
        WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_metrics)
    """)
    r = cur.fetchone()
    return {
        "subnets": r[0], "total_tao_day": round(r[1] or 0, 4),
        "avg_alpha_price": round(r[2] or 0, 8),
        "total_emitting": r[3],
    }
