"""Bitsec Evaluator — runs agent against ScaBench projects, produces real scores.

Uses mimo-v2.5 via Cloudflare Workers AI.
Stores all results in SQLite for historical analysis.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path("/root/bitt")))
from cge.bitsec.world import load_scabench_dataset, score_vulnerabilities, Project
from workers.bitsec.agent_v2 import call_mimo, ANALYSIS_PROMPT


DB_PATH = Path("/root/bitt/data/bitsec_eval.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            agent_version TEXT,
            model TEXT,
            timestamp TEXT,
            jaccard REAL,
            detection_rate REAL,
            precision REAL,
            f1_score REAL,
            n_expected INTEGER,
            n_found INTEGER,
            true_positives INTEGER,
            false_positives INTEGER,
            false_negatives INTEGER,
            tokens_used INTEGER,
            cost_usd REAL,
            raw_result JSON
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vulnerability_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            vuln_category TEXT,
            vuln_severity TEXT,
            detected INTEGER,
            agent_found INTEGER,
            ground_truth_count INTEGER,
            timestamp TEXT
        )
    """)
    conn.commit()
    return conn


def evaluate_project(project: Project, model: str = "cf/meta/llama-3.3-70b-instruct-fp8-fast") -> dict:
    """Evaluate agent against one ScaBench project using real LLM."""
    all_findings = []
    total_tokens = 0

    # For each vulnerability in ground truth, ask LLM to find it
    for vuln in project.vulnerabilities:
        prompt = f"""You are a security auditor. Analyze this code for the specific vulnerability type: {vuln.category}
Title hint: {vuln.title}

Return JSON:
{{
  "prediction": true/false,
  "vulnerabilities": [
    {{
      "title": "...",
      "category": "{vuln.category}",
      "severity": "...",
      "description": "...",
      "line_ranges": [{{"start": 1, "end": 10}}]
    }}
  ]
}}

Code context (from {project.name}):
The codebase contains {project.platform} smart contracts.
Focus on finding: {vuln.category} vulnerabilities.
"""
        result = call_mimo(prompt, max_tokens=2000)

        if result["ok"]:
            try:
                start = result["content"].find("{")
                end = result["content"].rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(result["content"][start:end])
                    findings = parsed.get("vulnerabilities", [])
                    all_findings.extend(findings)
                    total_tokens += result.get("tokens", {}).get("total_tokens", 0)
            except Exception:
                pass

    # Score against ground truth
    score = score_vulnerabilities(all_findings, project.vulnerabilities)

    return {
        "project_id": project.project_id,
        "model": model,
        "timestamp": datetime.utcnow().isoformat(),
        "findings": all_findings,
        "score": score,
        "tokens_used": total_tokens,
    }


def run_evaluation(max_projects: int = 20, model: str = "cf/meta/llama-3.3-70b-instruct-fp8-fast"):
    """Run evaluation across multiple projects."""
    projects = load_scabench_dataset(max_projects)
    conn = init_db()

    results = []
    for i, project in enumerate(projects):
        print(f"[{i+1}/{len(projects)}] {project.name} ({len(project.vulnerabilities)} vulns)...")

        result = evaluate_project(project, model)
        results.append(result)

        # Store in DB
        s = result["score"]
        conn.execute("""
            INSERT INTO evaluations (project_id, agent_version, model, timestamp,
                jaccard, detection_rate, precision, f1_score,
                n_expected, n_found, true_positives, false_positives, false_negatives,
                tokens_used, raw_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result["project_id"], "v2", model, result["timestamp"],
            s["jaccard"], s["detection_rate"], s["precision"], s["f1_score"],
            s["n_expected"], s["n_found"], s["true_positives"], s["false_positives"],
            s["false_negatives"], result["tokens_used"],
            json.dumps({"findings": result["findings"], "score": s}),
        ))

        # Per-vulnerability analysis
        for vuln in projects[i].vulnerabilities:
            detected = any(
                f.get("category", "").lower() == vuln.category.lower()
                for f in result["findings"]
            )
            conn.execute("""
                INSERT INTO vulnerability_analysis
                (project_id, vuln_category, vuln_severity, detected, agent_found,
                 ground_truth_count, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (project.project_id, vuln.category, vuln.severity,
                  1 if detected else 0, len(result["findings"]),
                  len(project.vulnerabilities), result["timestamp"]))

        conn.commit()

        # Print result
        s = result["score"]
        print(f"  Jaccard={s['jaccard']:.3f} DR={s['detection_rate']:.1%} "
              f"P={s['precision']:.1%} F1={s['f1_score']:.3f} "
              f"found={s['n_found']}/{s['n_expected']} tokens={result['tokens_used']}")

        results.append(result)
        time.sleep(0.5)  # rate limit

    # Summary
    all_f1 = [r["score"]["f1_score"] for r in results]
    all_jaccard = [r["score"]["jaccard"] for r in results]
    all_dr = [r["score"]["detection_rate"] for r in results]

    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(results)} projects evaluated")
    print(f"  Mean F1: {sum(all_f1)/len(all_f1):.3f}")
    print(f"  Mean Jaccard: {sum(all_jaccard)/len(all_jaccard):.3f}")
    print(f"  Mean Detection Rate: {sum(all_dr)/len(all_dr):.1%}")
    print(f"  Total tokens: {sum(r['tokens_used'] for r in results)}")

    # Per-category analysis
    print(f"\nPer-category detection:")
    cur = conn.execute("""
        SELECT vuln_category, vuln_severity,
               COUNT(*) as total,
               SUM(detected) as found
        FROM vulnerability_analysis
        GROUP BY vuln_category, vuln_severity
        ORDER BY found*1.0/COUNT(*) DESC
    """)
    for row in cur.fetchall():
        cat, sev, total, found = row
        rate = (found or 0) / max(total, 1)
        print(f"  {cat:<25} {sev:<10} {found}/{total} ({rate:.0%})")

    conn.close()
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects", type=int, default=20)
    parser.add_argument("--model", default="cf/meta/llama-3.3-70b-instruct-fp8-fast")
    args = parser.parse_args()

    run_evaluation(args.projects, args.model)
