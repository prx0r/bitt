"""Live Allocation Loop — Fleece-style Bayesian allocation.

Runs continuously:
1. Collect fresh data
2. Score all subnets
3. Thompson sample for weights
4. Generate allocation
5. Log everything

This is the "brain" that makes decisions.
"""
import sqlite3
import json
import random
import time
from pathlib import Path
from datetime import datetime


MDB = Path("/root/bitt/market.duckdb")
LOG_DIR = Path("/root/bitt/trading/logs")
LOG_DIR.mkdir(exist_ok=True)


class ThompsonAllocator:
    """Bayesian bandit for capital allocation.
    
    Each subnet is a "fish" with win/loss history.
    Posterior: Beta(alpha0 + wins, beta0 + losses)
    Sample from posterior → weight by sampled rate.
    """
    
    def __init__(self):
        self.win_history = {}  # netuid -> (wins, losses)
    
    def update(self, netuid: int, won: bool):
        """Update win/loss history."""
        w, l = self.win_history.get(netuid, (1, 1))
        if won:
            self.win_history[netuid] = (w + 1, l)
        else:
            self.win_history[netuid] = (w, l + 1)
    
    def sample_weights(self, netuids: list[int], n_samples: int = 1000) -> dict:
        """Sample allocation weights from posteriors."""
        weights = {}
        for netuid in netuids:
            w, l = self.win_history.get(netuid, (1, 1))
            samples = [random.betavariate(w, l) for _ in range(n_samples)]
            weights[netuid] = sum(samples) / len(samples)
        
        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights


class RegimeDetector:
    """Detect market regime from TAO price action."""
    
    def __init__(self):
        self.history = []
    
    def update(self, tao_price: float):
        self.history.append(tao_price)
        if len(self.history) > 168:  # Keep 7 days
            self.history = self.history[-168:]
    
    def detect(self) -> str:
        if len(self.history) < 48:
            return "UNKNOWN"
        
        # 24h return
        ret_24h = (self.history[-1] - self.history[-24]) / self.history[-24] if self.history[-24] > 0 else 0
        
        # 7d return
        ret_7d = (self.history[-1] - self.history[-168]) / self.history[-168] if len(self.history) >= 168 and self.history[-168] > 0 else 0
        
        # Volatility
        rets = [(self.history[i] - self.history[i-1]) / self.history[i-1] for i in range(1, len(self.history)) if self.history[i-1] > 0]
        vol = (sum(r**2 for r in rets) / len(rets)) ** 0.5 if rets else 0
        
        # Classify
        if ret_7d > 0.05 and vol < 0.03:
            return "BULL_QUIET"
        elif ret_7d > 0.05:
            return "BULL_VOLATILE"
        elif ret_7d < -0.05 and vol < 0.03:
            return "BEAR_QUIET"
        elif ret_7d < -0.05:
            return "BEAR_VOLATILE"
        else:
            return "SIDEWAYS"


class LiveAllocator:
    """Main allocation engine."""
    
    def __init__(self):
        self.thompson = ThompsonAllocator()
        self.regime = RegimeDetector()
        self.scan_count = 0
    
    def run_scan(self) -> dict:
        """Run one scan cycle."""
        self.scan_count += 1
        timestamp = datetime.utcnow().isoformat()
        
        # Get current subnet data
        conn = sqlite3.connect(str(MDB))
        conn.row_factory = sqlite3.Row
        
        netuids = conn.execute(
            "SELECT DISTINCT netuid FROM pool_state WHERE alpha_price > 0 GROUP BY netuid HAVING COUNT(*) > 20"
        ).fetchall()
        netuids = [r['netuid'] for r in netuids]
        
        # Score each subnet
        scores = {}
        for netuid in netuids:
            prices = conn.execute(
                "SELECT alpha_price FROM pool_state WHERE netuid = ? AND alpha_price > 0 ORDER BY timestamp",
                (netuid,)
            ).fetchall()
            price_list = [p[0] for p in prices]
            
            if len(price_list) < 20:
                continue
            
            # Volatility
            rets = [(price_list[i] - price_list[i-1]) / price_list[i-1] for i in range(1, len(price_list)) if price_list[i-1] > 0]
            vol = (sum(r**2 for r in rets) / len(rets)) ** 0.5 if rets else 1
            
            # Trajectory
            q = max(len(price_list) // 5, 1)
            early = sum(price_list[:q]) / q
            late = sum(price_list[-q:]) / q
            traj = (late - early) / early if early > 0 else 0
            
            scores[netuid] = {"vol": vol, "traj": traj, "price": price_list[-1]}
        
        conn.close()
        
        if not scores:
            return {"error": "no data"}
        
        # Thompson sample for weights
        netuids_scored = list(scores.keys())
        weights = self.thompson.sample_weights(netuids_scored)
        
        # Top 5 by weight
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top_5 = sorted_weights[:5]
        
        # Generate allocation
        allocation = {0: 0.05}  # 5% cash
        for netuid, weight in top_5:
            allocation[netuid] = round(weight * 0.95, 4)  # 95% invested
        
        # Normalize
        total = sum(allocation.values())
        allocation = {k: round(v / total, 4) for k, v in allocation.items()}
        
        # Log
        result = {
            "timestamp": timestamp,
            "scan_id": self.scan_count,
            "regime": self.regime.detect(),
            "allocation": allocation,
            "top_scores": {k: {"vol": round(v["vol"], 4), "traj": round(v["traj"], 4)} 
                          for k, v in sorted(scores.items(), key=lambda x: x[1]["vol"])[:5]},
            "n_subnets": len(netuids),
        }
        
        # Save log
        log_file = LOG_DIR / f"scan_{timestamp.replace(':', '-')}.json"
        with open(log_file, "w") as f:
            json.dump(result, f, indent=2)
        
        return result
    
    def format_report(self, result: dict) -> str:
        """Format scan result as report."""
        lines = [
            "=" * 60,
            f"LIVE ALLOCATION SCAN #{result['scan_id']}",
            "=" * 60,
            f"Time: {result['timestamp']}",
            f"Regime: {result['regime']}",
            f"Subnets: {result['n_subnets']}",
            "",
            "ALLOCATION:",
        ]
        
        for netuid, weight in sorted(result['allocation'].items(), key=lambda x: x[1], reverse=True):
            label = "CASH" if netuid == 0 else f"SN{netuid}"
            lines.append(f"  {label}: {weight:.1%}")
        
        lines.append("\nTOP SCORES (by vol):")
        for netuid, scores in result.get('top_scores', {}).items():
            lines.append(f"  SN{netuid}: vol={scores['vol']:.4f}, traj={scores['traj']:+.1%}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


if __name__ == "__main__":
    print("=== Live Allocation Engine ===\n")
    
    allocator = LiveAllocator()
    
    # Run 5 scans
    for i in range(5):
        result = allocator.run_scan()
        print(allocator.format_report(result))
        print()
        time.sleep(1)  # Simulate time passing
    
    print(f"\nLogs saved to {LOG_DIR}")
    print(f"Total scans: {allocator.scan_count}")
