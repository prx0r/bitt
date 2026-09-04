"""Bitsec Experiment Runner — logs all experiments to disk."""
import json
import time
from pathlib import Path
from datetime import datetime

EXPERIMENT_DIR = Path("/root/bitt/data/experiments")
EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)


def log_experiment(exp_id: str, project: str, method: str, model: str, 
                   prompt: str, findings: list, ground_truth: list, notes: str = ""):
    """Log an experiment to disk."""
    
    # Score against ground truth
    tp = 0
    matched_gt = set()
    for f in findings:
        f_title = f.get('title', '').lower()
        for j, gt in enumerate(ground_truth):
            if j in matched_gt:
                continue
            gt_title = gt.get('title', '').lower()
            f_words = set(f_title.split())
            gt_words = set(gt_title.split())
            if f_words and gt_words:
                overlap = len(f_words & gt_words) / max(len(f_words | gt_words), 1)
                if overlap >= 0.15:
                    matched_gt.add(j)
                    tp += 1
                    break
    
    fn = len(ground_truth) - len(matched_gt)
    fp = len(findings) - tp
    dr = tp / max(len(ground_truth), 1)
    precision = tp / max(tp + fp, 1)
    f1 = 2 * precision * dr / max(precision + dr, 0.001)
    
    entry = {
        "exp_id": exp_id,
        "timestamp": datetime.now().isoformat(),
        "project": project,
        "method": method,
        "model": model,
        "prompt": prompt[:500],  # Truncate for storage
        "results": {
            "expected": len(ground_truth),
            "found": len(findings),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "dr": dr,
            "precision": precision,
            "f1": f1,
        },
        "findings": findings,
        "notes": notes,
    }
    
    # Save to file
    exp_file = EXPERIMENT_DIR / f"{exp_id}.json"
    exp_file.write_text(json.dumps(entry, indent=2))
    
    print(f"Logged: {exp_file.name}")
    return entry


def list_experiments(project: str = None):
    """List all experiments, optionally filtered by project."""
    experiments = []
    for f in sorted(EXPERIMENT_DIR.glob("*.json")):
        entry = json.loads(f.read_text())
        if project is None or entry.get("project") == project:
            experiments.append(entry)
    return experiments


def print_summary(project: str = None):
    """Print summary of all experiments."""
    experiments = list_experiments(project)
    
    print(f"\n{'='*60}")
    print(f"EXPERIMENT SUMMARY ({len(experiments)} experiments)")
    print(f"{'='*60}\n")
    
    for exp in experiments:
        r = exp["results"]
        print(f"{exp['exp_id']}")
        print(f"  Method: {exp['method']}")
        print(f"  Found: {r['found']}, TP: {r['tp']}, DR: {r['dr']:.1%}")
        print()
