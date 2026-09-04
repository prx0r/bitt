"""Bitsec Run Log — tracks all evaluation runs."""
import json
import time
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("/root/bitt/data/runs")
LOG_DIR.mkdir(exist_ok=True)


def log_run(run_id: str, subnet: str, method: str, model: str, results: dict, notes: str = "", findings: list = None):
    """Log a run to disk."""
    entry = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "subnet": subnet,
        "method": method,
        "model": model,
        "results": results,
        "notes": notes,
    }
    
    if findings:
        entry["findings"] = findings
    
    log_file = LOG_DIR / f"{run_id}.json"
    log_file.write_text(json.dumps(entry, indent=2))
    print(f"Logged: {log_file}")
    return entry


def list_runs(subnet: str = None):
    """List all runs, optionally filtered by subnet."""
    runs = []
    for f in sorted(LOG_DIR.glob("*.json")):
        entry = json.loads(f.read_text())
        if subnet is None or entry.get("subnet") == subnet:
            runs.append(entry)
    return runs


if __name__ == "__main__":
    import sys
    subnet = sys.argv[1] if len(sys.argv) > 1 else None
    runs = list_runs(subnet)
    for r in runs:
        print(f"{r['run_id']} | {r['subnet']} | {r['method']} | {r['model']} | {r['timestamp']}")
