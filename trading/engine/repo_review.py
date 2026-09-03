"""Repo Review — analyze cloned Bittensor trading repos for transferable insights.

Reviews:
- OpenTaoTrader (execution, backtesting)
- TAOplicate (smart wallet tracking)
- dtao-trader (pool analysis)
- miner-spy (concentration metrics)
- tao-trading (rebalancing)
"""
import json
import os
from pathlib import Path


REPOS = {
    "opentao-trader": Path("/root/bitt/tooling/opentao-trader"),
    "taoplicate": Path("/root/bitt/tooling/taoplicate"),
    "dtao-trader": None,  # Check if exists
    "miner-spy": None,
    "sn62-ridges": Path("/root/bitt/subnets/sn62-ridges"),
    "sn67-harnyx": Path("/root/bitt/subnets/sn67-harnyx"),
    "sn61-redteam": Path("/root/bitt/subnets/sn61-redteam"),
}


def scan_repo(repo_path: Path) -> dict:
    """Scan a repo for key files and patterns."""
    if not repo_path or not repo_path.exists():
        return {"exists": False}
    
    files = []
    total_size = 0
    
    for f in repo_path.rglob("*"):
        if f.is_file() and not any(skip in str(f) for skip in [".git", "node_modules", "__pycache__", ".venv"]):
            files.append(str(f.relative_to(repo_path)))
            total_size += f.stat().st_size
    
    # Key patterns to look for
    patterns = {
        "has_backtest": any("backtest" in f.lower() for f in files),
        "has_execution": any("execut" in f.lower() or "trade" in f.lower() for f in files),
        "has_rebalance": any("rebalanc" in f.lower() for f in files),
        "has_pricing": any("price" in f.lower() or "pricing" in f.lower() for f in files),
        "has_slippage": any("slippag" in f.lower() for f in files),
        "has_pool": any("pool" in f.lower() for f in files),
        "has_metagraph": any("metagraph" in f.lower() for f in files),
        "has_validator": any("validator" in f.lower() for f in files),
        "has_miner": any("miner" in f.lower() for f in files),
        "has_staking": any("stak" in f.lower() for f in files),
        "has_config": any(f.endswith((".toml", ".yaml", ".yml", ".json")) for f in files),
        "has_tests": any("test" in f.lower() for f in files),
        "has_docker": any("dockerfile" in f.lower() for f in files),
    }
    
    # Get README if exists
    readme = ""
    readme_path = repo_path / "README.md"
    if readme_path.exists():
        readme = readme_path.read_text(errors="replace")[:2000]
    
    return {
        "exists": True,
        "files": len(files),
        "size_kb": total_size // 1024,
        "patterns": patterns,
        "readme_preview": readme[:500],
        "key_files": [f for f in files if any(k in f.lower() for k in ["main", "app", "config", "strategy", "rebalance", "trade"])][:10],
    }


def review_all_repos() -> dict:
    """Review all cloned repos."""
    results = {}
    
    for name, path in REPOS.items():
        if path is None:
            # Try to find it
            for p in Path("/root/bitt/tooling").glob(f"*{name}*"):
                if p.is_dir():
                    path = p
                    break
            for p in Path("/root/bitt/subnets").glob(f"*{name}*"):
                if p.is_dir():
                    path = p
                    break
        
        print(f"Reviewing {name}...")
        results[name] = scan_repo(path)
    
    return results


def format_review_report(results: dict) -> str:
    """Format review as report."""
    lines = [
        "=" * 70,
        "CLONED REPO REVIEW — Transferable Insights",
        "=" * 70,
    ]
    
    for name, data in results.items():
        if not data.get("exists"):
            lines.append(f"\n{name}: NOT FOUND")
            continue
        
        lines.append(f"\n{name}:")
        lines.append(f"  Files: {data['files']}, Size: {data['size_kb']}KB")
        
        patterns = data.get("patterns", {})
        features = [k.replace("has_", "") for k, v in patterns.items() if v]
        lines.append(f"  Features: {', '.join(features)}")
        
        if data.get("key_files"):
            lines.append(f"  Key files: {', '.join(data['key_files'][:5])}")
        
        if data.get("readme_preview"):
            # Extract first meaningful line
            for line in data["readme_preview"].split("\n"):
                if line.strip() and not line.startswith("#") and len(line.strip()) > 20:
                    lines.append(f"  Description: {line.strip()[:100]}")
                    break
    
    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


if __name__ == "__main__":
    results = review_all_repos()
    print(format_review_report(results))
    
    output = Path("/root/bitt/trading/experiments/repo_review.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {output}")
