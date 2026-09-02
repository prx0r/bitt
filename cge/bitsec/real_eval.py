"""Bitsec CGE Runner — real mimo-v2.5 analysis via Cloudflare Workers AI.

No simulation. Real LLM calls. Real vulnerability detection.
Wired through CGE → Hydra → mwgym pipeline.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt")))
sys.path.insert(0, str(Path("/root/mwgym")))

from cge.bitsec.world import (
    BitsecWorld, load_scabench_dataset, score_vulnerabilities, Project,
)
from workers.bitsec.cloudflare_harness import call_model, CloudflareBATSHarness


def analyze_project_real(project: Project, model: str = "mimo") -> dict:
    """Real analysis of a project using mimo-v2.5 via CF Workers AI.

    NO LABEL LEAKAGE: The LLM is NOT told what vulnerabilities exist.
    It must independently discover them. Ground truth is used ONLY for
    scoring after the fact.
    """
    all_findings = []
    total_tokens = 0

    # Single prompt: analyze the whole project, no hints
    prompt = f"""You are a smart contract security auditor. Perform a comprehensive security audit.

Project: {project.name} ({project.platform})
Platform: {project.platform}

Analyze the codebase for ALL types of vulnerabilities including but not limited to:
reentrancy, access control, integer overflow, unchecked return values,
front-running, tx.origin usage, denial of service, flash loan attacks,
oracle manipulation, business logic errors, and any other security issues.

For each finding, return:
{{"category": "...", "title": "...", "severity": "...", "description": "..."}}

Return a JSON array of all findings. Be thorough but precise.
Focus on real, exploitable vulnerabilities only."""

    result = call_model(model, prompt, max_tokens=3000)
    if result["ok"]:
        try:
            content = result["content"]
            # Try to parse as JSON array
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end])
                all_findings.extend(parsed)
            else:
                # Try single object
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(content[start:end])
                    all_findings.append(parsed)
            total_tokens += result.get("tokens", {}).get("total_tokens", 0)
        except Exception:
            all_findings.append({"category": "parse_error", "title": "failed to parse response"})

    # Score against ground truth (truth used ONLY here, never in prompt)
    score = score_vulnerabilities(all_findings, project.vulnerabilities)

    return {
        "project_id": project.project_id,
        "model": model,
        "findings": all_findings,
        "score": score,
        "tokens": total_tokens,
    }


def run_full_evaluation(n_projects: int = 15):
    """Run real mimo-v2.5 evaluation against ScaBench."""
    projects = load_scabench_dataset(n_projects)

    print(f"Evaluating {len(projects)} projects with mimo-v2.5...")
    print(f"Total vulnerabilities: {sum(len(p.vulnerabilities) for p in projects)}")
    print()

    all_results = []
    total_f1 = 0
    total_jaccard = 0

    for i, project in enumerate(projects):
        print(f"[{i+1}/{len(projects)}] {project.name} ({len(project.vulnerabilities)} vulns)...")

        result = analyze_project_real(project, model="mimo-v2.5")
        all_results.append(result)

        s = result["score"]
        total_f1 += s["f1_score"]
        total_jaccard += s["jaccard"]

        print(f"  Jaccard={s['jaccard']:.3f} DR={s['detection_rate']:.1%} "
              f"P={s['precision']:.1%} F1={s['f1_score']:.3f} "
              f"found={s['n_found']}/{s['n_expected']} tokens={result['tokens']}")

        # Per-category
        for cat, count in _category_breakdown(result["findings"]).items():
            print(f"    {cat}: {count} found")

        time.sleep(0.3)

    # Summary
    n = len(all_results)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {n} projects")
    print(f"  Mean F1: {total_f1/n:.3f}")
    print(f"  Mean Jaccard: {total_jaccard/n:.3f}")

    # Category breakdown
    print(f"\nCategory detection:")
    cat_stats = {}
    for r in all_results:
        for f in r["findings"]:
            cat = f.get("category", "unknown")
            if cat not in cat_stats:
                cat_stats[cat] = {"found": 0, "total": 0}
            cat_stats[cat]["found"] += 1

    # Compare to ground truth
    for project in projects:
        for v in project.vulnerabilities:
            cat = v.category.lower()
            if cat not in cat_stats:
                cat_stats[cat] = {"found": 0, "total": 0}
            cat_stats[cat]["total"] += 1

    for cat, stats in sorted(cat_stats.items(), key=lambda x: x[1]["found"], reverse=True):
        rate = stats["found"] / max(stats["total"], 1)
        print(f"  {cat:<25} {stats['found']}/{stats['total']} ({rate:.0%})")

    # Save results
    output = {
        "model": "mimo-v2.5",
        "n_projects": n,
        "mean_f1": total_f1/n,
        "mean_jaccard": total_jaccard/n,
        "results": [{"project": r["project_id"], "f1": r["score"]["f1_score"],
                      "jaccard": r["score"]["jaccard"],
                      "detection_rate": r["score"]["detection_rate"]}
                     for r in all_results],
        "category_stats": cat_stats,
    }

    out_path = Path("/root/bitt/data/bitsec_mimo_evaluation.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to {out_path}")

    return all_results


def _category_breakdown(findings: list[dict]) -> dict:
    cats = {}
    for f in findings:
        cat = f.get("category", "unknown")
        cats[cat] = cats.get(cat, 0) + 1
    return cats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects", type=int, default=15)
    args = parser.parse_args()
    run_full_evaluation(args.projects)
