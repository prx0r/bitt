"""Mechanism Classifier (CP2) — Auto-classifies subnet payout topology.

Scans subnet repos, reads incentive mechanism code, and classifies:
- PROPORTIONAL / BROAD_PARTICIPATION / TOP_K / WINNER_TAKE_ALL / BOUNTY / UNKNOWN

Uses repo structure + code patterns to classify without human review.
"""
import json
import os
import re
from pathlib import Path


SUBNET_REPOS = {
    67: Path("/root/bitt/subnets/sn67-harnyx"),
    62: Path("/root/bitt/subnets/sn62-ridges"),
    61: Path("/root/bitt/subnets/sn61-redteam"),
}


def scan_repo_patterns(repo_path: Path) -> dict:
    """Scan a subnet repo for payout topology patterns."""
    patterns = {
        "winner_take_all": [
            r"winner.?take.?all",
            r"first.?place",
            r"top.?1\b",
            r"only.*winner",
            r"single.?winner",
        ],
        "broad_participation": [
            r"all.*miner.*earn",
            r"proportional.*reward",
            r"participation.*reward",
            r"every.*miner",
            r"broad.*distribution",
        ],
        "top_k": [
            r"top.?[\d]+",
            r"top.?percent",
            r"top.?tier",
            r"leaderboard.*top",
        ],
        "decay": [
            r"decay",
            r"diminish",
            r"half.?life",
            r"exponential.*decay",
        ],
        "bounty": [
            r"bounty",
            r"prize",
            r"reward.*per.*task",
            r"fixed.*reward",
        ],
    }
    
    findings = {k: 0 for k in patterns}
    code_files = []
    
    # Scan key files
    for ext in ["*.py", "*.yaml", "*.yml", "*.md", "*.toml"]:
        for f in repo_path.rglob(ext):
            if any(skip in str(f) for skip in [".git", "node_modules", "__pycache__", ".venv"]):
                continue
            try:
                content = f.read_text(errors="replace")[:50000]
                code_files.append(str(f.name))
                
                for category, regexes in patterns.items():
                    for regex in regexes:
                        matches = re.findall(regex, content, re.IGNORECASE)
                        findings[category] += len(matches)
            except:
                pass
    
    return findings, code_files


def classify_topology(findings: dict) -> str:
    """Classify topology from pattern counts."""
    if findings["winner_take_all"] > 3:
        return "WINNER_TAKE_ALL"
    if findings["broad_participation"] > 3:
        return "BROAD_PARTICIPATION"
    if findings["top_k"] > 3:
        return "TOP_K"
    if findings["decay"] > 2:
        return "DECAYING_PORTFOLIO"
    if findings["bounty"] > 2:
        return "BOUNTY"
    return "UNKNOWN"


def classify_all_subnets() -> dict:
    """Classify all known subnet mechanisms."""
    results = {}
    
    for netuid, repo_path in SUBNET_REPOS.items():
        if not repo_path.exists():
            results[netuid] = {"topology": "MISSING_REPO", "repo": str(repo_path)}
            continue
        
        findings, files = scan_repo_patterns(repo_path)
        topology = classify_topology(findings)
        
        results[netuid] = {
            "netuid": netuid,
            "topology": topology,
            "findings": findings,
            "files_scanned": len(files),
            "repo": str(repo_path),
        }
    
    return results


if __name__ == "__main__":
    print("=== Mechanism Classifier (CP2) ===\n")
    
    results = classify_all_subnets()
    
    for netuid, data in sorted(results.items()):
        print(f"SN{netuid}: {data['topology']}")
        if "findings" in data:
            for k, v in data['findings'].items():
                if v > 0:
                    print(f"  {k}: {v}")
        print()
    
    # Save
    output = Path("/root/bitt/trading/experiments/mechanism_classifier.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved to {output}")
