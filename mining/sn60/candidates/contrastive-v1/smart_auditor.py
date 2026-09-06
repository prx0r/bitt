#!/usr/bin/env python3
"""
Smart Contrastive Auditor v4 — Uses grep to find relevant files first.
Then contrasts against appropriate reference patterns.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

PROXY = os.environ.get("INFERENCE_API", "http://localhost:8087")
API_KEY = os.environ.get("INFERENCE_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "mimo-v2.5")

SCABENCH_REPOS = Path("/root/bitt/data/scabench-repos")
LOG_DIR = Path("/root/bitt/data/contrastive-logs-v4")

PROJECTS = {
    "crestal": {"id": "sherlock_crestal-network_2025_03", "hc": 1, "type": "payment"},
    "coded-estate": {"id": "code4rena_coded-estate-invitational_2024_12", "hc": 9, "type": "rental"},
    "liquid-ron": {"id": "code4rena_liquid-ron_2025_03", "hc": 5, "type": "staking"},
    "cork": {"id": "sherlock_cork-protocol_2025_01", "hc": 18, "type": "defi"},
    "iq-ai": {"id": "code4rena_iq-ai_2025_03", "hc": 9, "type": "governance"},
    "mantra": {"id": "code4rena_mantra-dex_2025_03", "hc": 55, "type": "dex"},
}


def call_llm(messages, max_tokens=4096, temperature=0.1):
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "smart-v4",
                "x-job-run-id": f"v4-{int(time.time())}-{attempt}",
                "x-request-phase": "execution"
            }, json={
                "model": MODEL, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature
            }, timeout=300)
            if resp.status_code == 200:
                r = resp.json()
                if "choices" in r and r["choices"]:
                    content = r["choices"][0].get("message", {}).get("content", "")
                    if content and len(content) > 10:
                        return content
        except Exception as e:
            print(f"  LLM error: {e}")
        time.sleep(2)
    return ""


def parse_json(text):
    for pattern in [r'\[[\s\S]*\]', r'\{[\s\S]*\}']:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return None


def read_file(path, max_chars=15000):
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


def grep_transfer_files(project_dir):
    """Find files containing transfer calls."""
    result = subprocess.run(
        ["grep", "-rl", "safeTransferFrom\\|transferFrom\\|BankMsg\\|send\\|transfer\\|mint\\|burn",
         str(project_dir), "--include=*.sol", "--include=*.rs"],
        capture_output=True, text=True, timeout=30
    )
    files = [f for f in result.stdout.strip().split("\n") if f and "test" not in f.lower()]
    return files[:15]  # Limit to 15 files


def load_references(project_type):
    """Load reference patterns for the project type."""
    patterns_path = Path("/root/bitt/data/reference-patterns/all-patterns.json")
    if not patterns_path.exists():
        return []
    
    data = json.loads(patterns_path.read_text())
    patterns = data.get("patterns", {})
    
    # Get patterns for this project type
    relevant = []
    for category, pattern_list in patterns.items():
        if category == project_type or category in ["access-control", "nft"]:
            relevant.extend(pattern_list)
    
    return relevant


def audit_project(project_key):
    """Audit a single project."""
    project = PROJECTS[project_key]
    project_id = project["id"]
    project_dir = SCABENCH_REPOS / project_id
    
    print(f"\n{'='*70}")
    print(f"AUDITING: {project_key} ({project['type']})")
    print(f"Expected high/critical: {project['hc']}")
    print(f"{'='*70}\n")
    
    start = time.time()
    
    if not project_dir.exists():
        print(f"  Project not found: {project_dir}")
        return {"project": project_key, "findings": [], "dr": 0}
    
    # Step 1: Find transfer files via grep
    print("[1] Finding transfer files via grep...")
    transfer_files = grep_transfer_files(project_dir)
    print(f"  Found {len(transfer_files)} files with transfers")
    
    if not transfer_files:
        print("  No transfer files found!")
        return {"project": project_key, "findings": [], "dr": 0}
    
    # Step 2: Read only transfer files
    print("\n[2] Reading transfer files...")
    all_code = ""
    for f in transfer_files:
        content = read_file(f, 12000)
        if content:
            rel = str(Path(f).relative_to(project_dir))
            all_code += f"\n--- {rel} ---\n{content}\n"
    
    print(f"  Total code: {len(all_code)} chars")
    
    if len(all_code) > 60000:
        print("  Code too large, truncating...")
        all_code = all_code[:60000]
    
    # Step 3: Load references
    references = load_references(project["type"])
    print(f"\n[3] Loaded {len(references)} reference patterns for {project['type']}")
    
    # Step 4: Find vulnerable patterns
    print("\n[4] Searching for vulnerable patterns...")
    response = call_llm([
        {"role": "system", "content": f"""You are a security auditor specializing in {project['type']} smart contracts.

Search this code for vulnerabilities. Focus on:
1. Missing access control checks
2. Unverified parameters in critical functions
3. State inconsistencies
4. Missing validation
5. Logic errors

For each vulnerability found, output:
- title: specific name
- file: file path
- line: line number
- severity: critical/high/medium/low
- invariant: what should be true
- attack: step-by-step exploit
- impact: concrete damage

Output ONLY valid JSON: list of findings."""},
        {"role": "user", "content": f"Analyze this {project['type']} contract code:\n{all_code}"}
    ], max_tokens=4096)
    
    findings = parse_json(response)
    if not findings:
        print("  Failed to parse findings")
        return {"project": project_key, "findings": [], "dr": 0}
    
    if isinstance(findings, dict):
        findings = findings.get("findings", [findings])
    if not isinstance(findings, list):
        findings = []
    
    print(f"  Found {len(findings)} candidate vulnerabilities")
    
    # Step 5: Verify each finding
    print("\n[5] Verifying findings...")
    verified = []
    
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            continue
        
        print(f"  [{i+1}/{len(findings)}] {f.get('title', '?')[:50]}")
        
        response = call_llm([
            {"role": "system", "content": """Verify this vulnerability. Check:
1. Does the vulnerable code exist?
2. Is the invariant actually missing?
3. Is the attack realistic?

Output ONLY valid JSON:
{
  "status": "confirmed" or "rejected",
  "title": "vulnerability name",
  "file": "exact file",
  "line": "line number",
  "severity": "critical/high/medium/low",
  "invariant": "what's missing",
  "attack": "concrete attack",
  "impact": "concrete damage"
}"""},
            {"role": "user", "content": f"Verify this finding:\n{json.dumps(f, indent=2)[:2000]}\n\nCode:\n{all_code[:15000]}"}
        ], max_tokens=2048)
        
        result = parse_json(response)
        if result and result.get("status") == "confirmed":
            verified.append(result)
            print(f"    ✓ CONFIRMED: {result.get('title', '?')[:40]}")
        else:
            print(f"    ✗ Rejected")
    
    duration = time.time() - start
    
    # Calculate DR
    high_crit = [v for v in verified if v.get("severity", "").lower() in ["high", "critical"]]
    dr = len(high_crit) / project["hc"] if project["hc"] > 0 else 0
    
    # Summary
    print(f"\n{'='*70}")
    print(f"RESULTS: {project_key}")
    print(f"{'='*70}")
    print(f"Duration: {duration:.0f}s")
    print(f"Files analyzed: {len(transfer_files)}")
    print(f"Code size: {len(all_code)} chars")
    print(f"Total findings: {len(verified)}")
    print(f"High/Critical: {len(high_crit)}")
    print(f"Expected: {project['hc']}")
    print(f"DR: {dr:.0%}")
    
    for v in high_crit:
        print(f"\n  [{v.get('severity')}] {v.get('title', '?')}")
        print(f"  File: {v.get('file', '?')}:{v.get('line', '?')}")
        print(f"  Invariant: {v.get('invariant', '?')[:80]}")
    
    print(f"{'='*70}")
    
    # Save
    result = {
        "project": project_key,
        "project_id": project_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": round(duration, 1),
        "files_analyzed": len(transfer_files),
        "code_size": len(all_code),
        "total_findings": len(verified),
        "high_critical": len(high_crit),
        "expected_hc": project["hc"],
        "detection_rate": dr,
        "findings": verified,
    }
    
    log_dir = LOG_DIR / project_key / time.strftime("%Y%m%d-%H%M%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "results.json").write_text(json.dumps(result, indent=2))
    
    return result


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    if len(sys.argv) > 1:
        key = sys.argv[1]
        if key not in PROJECTS:
            print(f"Unknown: {key}. Available: {', '.join(PROJECTS.keys())}")
            return
        audit_project(key)
    else:
        results = []
        for key in PROJECTS:
            try:
                r = audit_project(key)
                results.append(r)
            except Exception as e:
                print(f"Error on {key}: {e}")
                import traceback
                traceback.print_exc()
                results.append({"project": key, "error": str(e)})
        
        # Final summary
        print(f"\n{'='*70}")
        print(f"FINAL SUMMARY")
        print(f"{'='*70}")
        
        total_hc = 0
        total_found = 0
        for r in results:
            if "error" in r:
                print(f"  {r['project']:15s} — ERROR")
            else:
                found = r.get("high_critical", 0)
                expected = r.get("expected_hc", 0)
                dr = r.get("detection_rate", 0)
                total_hc += expected
                total_found += found
                mark = "✓" if dr >= 1.0 else ("~" if dr > 0 else "✗")
                print(f"  {mark} {r['project']:15s} — {found}/{expected} ({dr:.0%})")
        
        overall = total_found / total_hc if total_hc > 0 else 0
        print(f"\n  Overall: {total_found}/{total_hc} ({overall:.0%})")
        print(f"{'='*70}")
        
        summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": results,
            "total_expected": total_hc,
            "total_found": total_found,
            "overall_dr": overall,
        }
        (LOG_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
        print(f"\nSummary: {LOG_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
