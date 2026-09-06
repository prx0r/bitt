#!/usr/bin/env python3
"""
Universal Contrastive Auditor — Works on any project.
Trace safeTransferFrom calls and check if fromAddress is verified.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

PROXY = os.environ.get("INFERENCE_API", "http://localhost:8087")
API_KEY = os.environ.get("INFERENCE_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "mimo-v2.5")

SCABENCH_REPOS = Path("/root/bitt/data/scabench-repos")
LOG_DIR = Path("/root/bitt/data/contrastive-logs")

# Official projects
PROJECTS = {
    "crestal": {"id": "sherlock_crestal-network_2025_03", "hc": 1},
    "coded-estate": {"id": "code4rena_coded-estate-invitational_2024_12", "hc": 9},
    "liquid-ron": {"id": "code4rena_liquid-ron_2025_03", "hc": 5},
    "cork": {"id": "sherlock_cork-protocol_2025_01", "hc": 18},
    "iq-ai": {"id": "code4rena_iq-ai_2025_03", "hc": 9},
    "mantra": {"id": "code4rena_mantra-dex_2025_03", "hc": 55},
}


def call_llm(messages, max_tokens=4096, temperature=0.1):
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "universal",
                "x-job-run-id": f"uni-{int(time.time())}-{attempt}",
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


def read_file(path, max_chars=30000):
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


def audit_project(project_key):
    """Audit a single project."""
    project = PROJECTS[project_key]
    project_id = project["id"]
    project_dir = SCABENCH_REPOS / project_id
    
    print(f"\n{'='*70}")
    print(f"AUDITING: {project_key} ({project_id})")
    print(f"Expected high/critical: {project['hc']}")
    print(f"{'='*70}\n")
    
    start = time.time()
    
    if not project_dir.exists():
        print(f"  Project directory not found: {project_dir}")
        return {"project": project_key, "findings": [], "dr": 0}
    
    # Read source files (limit to keep prompt small)
    all_code = ""
    file_count = 0
    for ext in ["*.sol", "*.rs"]:
        for f in project_dir.rglob(ext):
            if "test" not in f.name.lower() and "script" not in f.name.lower():
                if "mock" not in f.name.lower():
                    content = read_file(f, 10000)  # Smaller limit per file
                    if content:
                        rel = str(f.relative_to(project_dir))
                        all_code += f"\n--- {rel} ---\n{content}\n"
                        file_count += 1
                        if len(all_code) > 50000:  # Total limit
                            break
        if len(all_code) > 50000:
            break
    
    print(f"  Read {file_count} source files ({len(all_code)} chars)")
    
    # Step 1: Find all token transfers
    print("\n[1] Finding all token transfers...")
    response = call_llm([
        {"role": "system", "content": """Find ALL token transfer calls in this code. Look for:
1. safeTransferFrom
2. transferFrom  
3. transfer
4. call{value:} (ETH transfers)
5. BankMsg::Send (CosmWasm)
6. Any other token transfer pattern

For each transfer:
- Which function contains it?
- What is the `from` address (who pays)?
- Where does `from` come from (msg.sender, parameter, variable)?
- Is `from` verified before the transfer?

Output ONLY valid JSON:
{
  "transfers": [
    {
      "function": "containing function",
      "file": "file path",
      "line": "line number",
      "from_source": "where from comes from",
      "verified": true/false,
      "verification_method": "msg.sender/signature/allowance/none"
    }
  ]
}"""},
        {"role": "user", "content": f"Find all token transfers in this code:\n{all_code[:25000]}"}
    ], max_tokens=4096)
    
    transfers = parse_json(response)
    if not transfers:
        print("  Failed to parse transfers")
        return {"project": project_key, "findings": [], "dr": 0}
    
    if isinstance(transfers, dict):
        transfers = transfers.get("transfers", [])
    
    print(f"  Found {len(transfers)} transfers")
    
    # Step 2: Analyze each transfer
    print("\n[2] Analyzing transfers for vulnerabilities...")
    findings = []
    
    for i, t in enumerate(transfers):
        if not isinstance(t, dict):
            continue
        
        print(f"  [{i+1}/{len(transfers)}] {t.get('function', '?')} — from={t.get('from_source', '?')}")
        
        response = call_llm([
            {"role": "system", "content": """Analyze this token transfer for vulnerabilities.

Check if the `from` address is properly verified:
- Is it msg.sender? (secure)
- Is it verified via signature? (secure if done right)
- Is it verified via allowance check? (secure)
- Is it an unverified parameter? (VULNERABLE)

If from is an unverified parameter, this is a CRITICAL vulnerability.
Anyone who controls from can drain tokens from any user who approved the contract.

Output ONLY valid JSON:
{
  "is_vulnerable": true/false,
  "title": "vulnerability name (be specific)",
  "invariant": "what should be true",
  "attack": "step-by-step attack",
  "impact": "concrete damage",
  "severity": "critical/high/medium/low",
  "file": "exact file",
  "line": "line number"
}"""},
            {"role": "user", "content": f"Analyze this transfer:\n{json.dumps(t, indent=2)}\n\nCode:\n{all_code[:20000]}"}
        ], max_tokens=4096)
        
        result = parse_json(response)
        if result and result.get("is_vulnerable"):
            findings.append(result)
            print(f"    ✓ {result.get('title', '?')[:50]}")
        else:
            print(f"    ✗ Not vulnerable")
    
    duration = time.time() - start
    
    # Calculate DR
    high_crit = [f for f in findings if f.get("severity", "").lower() in ["high", "critical"]]
    dr = len(high_crit) / project["hc"] if project["hc"] > 0 else 0
    
    # Summary
    print(f"\n{'='*70}")
    print(f"RESULTS: {project_key}")
    print(f"{'='*70}")
    print(f"Duration: {duration:.0f}s")
    print(f"Transfers analyzed: {len(transfers)}")
    print(f"Vulnerabilities found: {len(findings)}")
    print(f"High/Critical: {len(high_crit)}")
    print(f"Expected: {project['hc']}")
    print(f"DR: {dr:.0%}")
    
    for f in high_crit:
        print(f"\n  [{f.get('severity')}] {f.get('title', '?')}")
        print(f"  File: {f.get('file', '?')}:{f.get('line', '?')}")
        print(f"  Invariant: {f.get('invariant', '?')[:80]}")
    
    print(f"{'='*70}")
    
    # Save
    result = {
        "project": project_key,
        "project_id": project_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": round(duration, 1),
        "transfers_analyzed": len(transfers),
        "total_findings": len(findings),
        "high_critical": len(high_crit),
        "expected_hc": project["hc"],
        "detection_rate": dr,
        "findings": findings,
    }
    
    log_dir = LOG_DIR / project_key / time.strftime("%Y%m%d-%H%M%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "results.json").write_text(json.dumps(result, indent=2))
    
    return result


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    if len(sys.argv) > 1:
        # Run specific project
        key = sys.argv[1]
        if key not in PROJECTS:
            print(f"Unknown project: {key}. Available: {', '.join(PROJECTS.keys())}")
            return
        audit_project(key)
    else:
        # Run all projects
        results = []
        for key in PROJECTS:
            try:
                r = audit_project(key)
                results.append(r)
            except Exception as e:
                print(f"Error on {key}: {e}")
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
                mark = "✓" if dr >= 1.0 else "✗"
                print(f"  {mark} {r['project']:15s} — {found}/{expected} ({dr:.0%})")
        
        overall = total_found / total_hc if total_hc > 0 else 0
        print(f"\n  Overall: {total_found}/{total_hc} ({overall:.0%})")
        print(f"{'='*70}")
        
        # Save summary
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
