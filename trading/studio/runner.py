"""Studio Runner — log every run, store every result, build the moat.

Inspired by Fleece's approach:
- Every run = one labeled experiment
- Results stored in immutable format
- Strategies compete in a league
- Losers go to graveyard (preserved as evidence)
- Winners get more capital allocation
"""
import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime


STUDIO_DIR = Path("/root/bitt/trading/studio")
RUNS_DIR = STUDIO_DIR / "runs"
GRAVEYARD_DIR = STUDIO_DIR / "graveyard"
REPORTS_DIR = STUDIO_DIR / "reports"
DB_PATH = Path("/root/bitt/market.duckdb")

for d in [RUNS_DIR, GRAVEYARD_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class StudioRun:
    """One experiment run with immutable logging."""
    
    def __init__(self, name: str, strategy: str, params: dict):
        self.name = name
        self.strategy = strategy
        self.params = params
        self.run_id = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}_{name}"
        self.start_time = datetime.utcnow()
        self.results = {}
        self.trades = []
    
    def log_trade(self, timestamp: str, netuid: int, action: str, 
                  price: float, units: float, pnl: float = 0):
        """Log a single trade."""
        self.trades.append({
            "timestamp": timestamp,
            "netuid": netuid,
            "action": action,
            "price": price,
            "units": units,
            "pnl": pnl,
        })
    
    def save(self, results: dict):
        """Save run to immutable log."""
        self.results = results
        self.end_time = datetime.utcnow()
        
        run_data = {
            "run_id": self.run_id,
            "name": self.name,
            "strategy": self.strategy,
            "params": self.params,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "results": results,
            "trades": self.trades,
            "n_trades": len(self.trades),
        }
        
        # Save run log
        run_file = RUNS_DIR / f"{self.run_id}.json"
        with open(run_file, "w") as f:
            json.dump(run_data, f, indent=2)
        
        # Save manifest hash
        manifest = json.dumps(run_data, sort_keys=True)
        manifest_hash = hashlib.sha256(manifest.encode()).hexdigest()
        
        # Update strategy leaderboard
        self._update_leaderboard(results, manifest_hash)
        
        return run_file
    
    def _update_leaderboard(self, results: dict, manifest_hash: str):
        """Update the strategy leaderboard."""
        leaderboard_file = STUDIO_DIR / "leaderboard.json"
        
        if leaderboard_file.exists():
            with open(leaderboard_file) as f:
                leaderboard = json.load(f)
        else:
            leaderboard = {"strategies": {}}
        
        strategy_key = f"{self.strategy}_{json.dumps(self.params, sort_keys=True)}"
        
        if strategy_key not in leaderboard["strategies"]:
            leaderboard["strategies"][strategy_key] = {
                "name": self.name,
                "strategy": self.strategy,
                "params": self.params,
                "runs": [],
                "best_return": -999,
                "avg_return": 0,
                "total_runs": 0,
            }
        
        entry = leaderboard["strategies"][strategy_key]
        entry["runs"].append({
            "run_id": self.run_id,
            "return_pct": results.get("ret", 0),
            "max_dd": results.get("mdd", 0),
            "trades": results.get("trades", 0),
            "win_rate": results.get("wr", 0),
            "manifest_hash": manifest_hash,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Update stats
        returns = [r["return_pct"] for r in entry["runs"]]
        entry["best_return"] = max(returns)
        entry["avg_return"] = sum(returns) / len(returns)
        entry["total_runs"] = len(returns)
        
        with open(leaderboard_file, "w") as f:
            json.dump(leaderboard, f, indent=2)


def get_leaderboard() -> dict:
    """Get current leaderboard."""
    leaderboard_file = STUDIO_DIR / "leaderboard.json"
    if leaderboard_file.exists():
        with open(leaderboard_file) as f:
            return json.load(f)
    return {"strategies": {}}


def format_leaderboard() -> str:
    """Format leaderboard as report."""
    lb = get_leaderboard()
    lines = [
        "=" * 70,
        "STRATEGY LEADERBOARD",
        "=" * 70,
        f"{'Strategy':<30} {'AvgRet%':<10} {'Best%':<10} {'Runs':<6} {'Status'}",
        "-" * 70,
    ]
    
    for key, entry in sorted(lb["strategies"].items(), 
                              key=lambda x: x[1]["avg_return"], reverse=True):
        status = "ACTIVE" if entry["avg_return"] > 0 else "GRAVEYARD"
        lines.append(
            f"{entry['name']:<30} {entry['avg_return']:<+10.2f} "
            f"{entry['best_return']:<+10.2f} {entry['total_runs']:<6} {status}"
        )
    
    lines.append("=" * 70)
    return "\n".join(lines)


if __name__ == "__main__":
    print("=== Trading Studio ===\n")
    print(format_leaderboard())
