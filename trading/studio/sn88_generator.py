"""SN88 Strategy Generator — convert our signals to SN88-compatible format.

SN88 format: CSV with columns uid, date, block, init, fund, strat
strat = Python dict like {1: 0.27, 2: 0.15, 4: 0.21}

Also generates our own format for live execution.
"""
import json
import csv
from pathlib import Path
from datetime import datetime


STRATEGIES_DIR = Path("/root/bitt/trading/strategies")
STRATEGIES_DIR.mkdir(exist_ok=True)


def generate_sn88_csv(allocation: dict, hotkey: str, output_path: Path):
    """Generate SN88-compatible CSV file.
    
    Format: uid, date, block, init, fund, strat
    - uid = hotkey ss58
    - init = 1 (first submission)
    - fund = 2000 (TAO)
    - strat = Python dict {netuid: weight}
    """
    # Convert allocation to SN88 format
    # Remove cash (0) and normalize
    alpha_alloc = {k: v for k, v in allocation.items() if k != 0 and v > 0}
    total = sum(alpha_alloc.values())
    if total > 0:
        alpha_alloc = {k: v / total for k, v in alpha_alloc.items()}
    
    # SN88 strat format: all keys are integers
    strat_dict = {int(k): round(v, 4) for k, v in alpha_alloc.items()}
    
    now = datetime.utcnow()
    
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["uid", "date", "block", "init", "fund", "strat"])
        writer.writerow([
            hotkey,
            now.strftime("%Y-%m-%d"),
            0,  # block (0 = use current)
            1,  # init = first submission
            2000,  # fund = 2000 TAO
            str(strat_dict),
        ])
    
    print(f"Generated SN88 CSV: {output_path}")
    return strat_dict


def generate_live_allocation(allocation: dict, output_path: Path):
    """Generate our own allocation format for live execution."""
    now = datetime.utcnow()
    
    live_data = {
        "timestamp": now.isoformat(),
        "strategy": "composite",
        "allocation": allocation,
        "meta": {
            "total_tao": 100.0,
            "positions": len([k for k, v in allocation.items() if k != 0 and v > 0]),
            "cash_pct": allocation.get(0, 0),
        },
    }
    
    with open(output_path, "w") as f:
        json.dump(live_data, f, indent=2)
    
    print(f"Generated live allocation: {output_path}")


def strategy_to_sn88(strategy_name: str, top_n: int = 5):
    """Convert a strategy result to SN88 format."""
    # Load leaderboard
    lb_path = Path("/root/bitt/trading/studio/leaderboard.json")
    with open(lb_path) as f:
        leaderboard = json.load(f)
    
    # Find strategy
    for key, entry in leaderboard["strategies"].items():
        if entry["strategy"] == strategy_name and entry["params"].get("top_n") == top_n:
            # Generate allocation from strategy
            # For now, use the top subnets from our latest scan
            allocation = {0: 0.05}  # 5% cash
            
            # Load latest scan results
            scan_path = Path("/root/bitt/trading/experiments/full_scan.json")
            if scan_path.exists():
                with open(scan_path) as f:
                    scan = json.load(f)
                # Take top subnets
                sorted_scan = sorted(scan, key=lambda x: x.get("combined", 0), reverse=True)
                for s in sorted_scan[:top_n]:
                    allocation[s["netuid"]] = round(0.95 / top_n, 4)
            
            # Generate files
            hotkey = "5DFqEAQY6DhFh7WbSNFH85kX7VrcT4TjbVCtscHP1VHDWyPN"  # placeholder
            
            strat_dict = generate_sn88_csv(
                allocation, hotkey,
                STRATEGIES_DIR / f"sn88_{strategy_name}_{top_n}pos.csv"
            )
            
            generate_live_allocation(
                allocation,
                STRATEGIES_DIR / f"live_{strategy_name}_{top_n}pos.json"
            )
            
            return strat_dict
    
    return None


if __name__ == "__main__":
    print("=== SN88 Strategy Generator ===\n")
    
    # Generate for top strategies
    for strategy in ["support", "child", "low_vol", "anti_vol"]:
        for top_n in [3, 5, 10]:
            result = strategy_to_sn88(strategy, top_n)
            if result:
                print(f"{strategy}_{top_n}pos: {result}")
    
    print(f"\nFiles saved to {STRATEGIES_DIR}")
