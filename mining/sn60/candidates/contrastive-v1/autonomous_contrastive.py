#!/usr/bin/env python3
"""
Autonomous Contrastive Auditor — Run on all 6 official BitSec projects.

Usage:
    python3 autonomous_contrastive.py                    # Run all 6 projects
    python3 autonomous_contrastive.py --project crestal  # Run one project
    python3 autonomous_contrastive.py --list             # List projects
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# Config
PROXY = os.environ.get("INFERENCE_API", "http://localhost:8087")
API_KEY = os.environ.get("INFERENCE_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "mimo-v2.5")

# Official projects
PROJECTS = {
    "crestal": {
        "id": "sherlock_crestal-network_2025_03",
        "name": "Crestal Network",
        "high_critical": 1,
        "lang": "solidity",
    },
    "coded-estate": {
        "id": "code4rena_coded-estate-invitational_2024_12",
        "name": "Coded Estate",
        "high_critical": 9,
        "lang": "cosmwasm",
    },
    "liquid-ron": {
        "id": "code4rena_liquid-ron_2025_03",
        "name": "Liquid RON",
        "high_critical": 5,
        "lang": "solidity",
    },
    "cork": {
        "id": "sherlock_cork-protocol_2025_01",
        "name": "Cork Protocol",
        "high_critical": 18,
        "lang": "solidity",
    },
    "iq-ai": {
        "id": "code4rena_iq-ai_2025_03",
        "name": "IQ AI",
        "high_critical": 9,
        "lang": "solidity",
    },
    "mantra": {
        "id": "code4rena_mantra-dex_2025_03",
        "name": "Mantra DEX",
        "high_critical": 55,
        "lang": "cosmwasm",
    },
}

# Load reference patterns
REFERENCE_PATH = Path("/root/bitt/data/reference-patterns/defi-patterns.json")
SCABENCH_REPOS = Path("/root/bitt/data/scabench-repos")
LOG_DIR = Path("/root/bitt/data/contrastive-logs")


def call_llm(messages, max_tokens=4096, temperature=0.1, timeout=300):
    """Call LLM through proxy."""
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "contrastive-auto",
                "x-job-run-id": f"auto-{int(time.time())}-{attempt}",
                "x-request-phase": "execution"
            }, json={
                "model": MODEL, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature
            }, timeout=timeout)
            if resp.status_code == 200:
                r = resp.json()
                if "choices" in r and r["choices"]:
                    content = r["choices"][0].get("message", {}).get("content", "")
                    if content and len(content) > 10:
                        return content
        except Exception as e:
            print(f"  LLM error (attempt {attempt+1}): {e}")
        time.sleep(2)
    return ""


def parse_json(text):
    """Extract JSON from LLM text."""
    for pattern in [r'\[[\s\S]*\]', r'\{[\s\S]*\}']:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return None


def read_file(path, max_chars=30000):
    """Read a file safely."""
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


def load_references():
    """Load reference patterns."""
    if REFERENCE_PATH.exists():
        data = json.loads(REFERENCE_PATH.read_text())
        return data.get("patterns", [])
    return []


def find_project_files(project_id, max_files=10):
    """Find the key source files for a project."""
    project_dir = SCABENCH_REPOS / project_id
    if not project_dir.exists():
        print(f"  Project directory not found: {project_dir}")
        return []
    
    # Find source files (not test/script)
    all_files = []
    for ext in ["*.sol", "*.rs"]:
        for f in project_dir.rglob(ext):
            if "test" not in f.name.lower() and "script" not in f.name.lower():
                if "mock" not in f.name.lower():
                    all_files.append(f)
    
    # Sort by relevance (smaller files first = more focused)
    all_files.sort(key=lambda f: f.stat().st_size)
    
    return all_files[:max_files]


def identify_entry_points(source_files, project_dir):
    """Identify entry points in the codebase."""
    all_code = ""
    for f in source_files:
        content = read_file(f, 15000)
        if content:
            rel = str(f.relative_to(project_dir))
            all_code += f"\n--- {rel} ---\n{content}\n"
    
    response = call_llm([
        {"role": "system", "content": """Identify ALL externally callable functions in this smart contract code.

For each function, output:
- name: function name
- file: which file it's in
- purpose: what it does
- handles_value: does it transfer tokens/ETH/NFTs?
- risk_level: high/medium/low based on what it can do

Output ONLY valid JSON: list of entry points.
Focus on functions that handle money/value — these are highest risk."""},
        {"role": "user", "content": f"Identify entry points in this code:\n{all_code[:20000]}"}
    ], max_tokens=4096)
    
    entry_points = parse_json(response)
    if isinstance(entry_points, dict):
        entry_points = entry_points.get("entry_points", [entry_points])
    if not isinstance(entry_points, list):
        entry_points = []
    
    return entry_points, all_code


def match_references(entry_point, references):
    """Match entry point to relevant reference patterns."""
    purpose = entry_point.get("purpose", "").lower()
    name = entry_point.get("name", "").lower()
    
    matched = []
    for ref in references:
        category = ref.get("category", "").lower()
        # Match based on keywords
        if any(kw in purpose or kw in name for kw in ["transfer", "pay", "token", "erc20"]):
            if category == "payment":
                matched.append(ref)
        if any(kw in purpose or kw in name for kw in ["approve", "allowance"]):
            if category in ["payment", "nft"]:
                matched.append(ref)
        if any(kw in purpose or kw in name for kw in ["withdraw", "deposit", "lend", "borrow"]):
            if category == "lending":
                matched.append(ref)
        if any(kw in purpose or kw in name for kw in ["swap", "trade", "dex"]):
            if category == "dex":
                matched.append(ref)
        if any(kw in purpose or kw in name for kw in ["upgrade", "admin", "owner"]):
            if category in ["access-control", "upgradeable"]:
                matched.append(ref)
    
    # If no specific match, return general payment patterns
    if not matched:
        matched = [r for r in references if r.get("category") in ["payment", "access-control"]]
    
    return matched[:5]  # Top 5 matches


def contrastive_analyze(entry_point, matched_refs, code_context):
    """Perform contrastive analysis on one entry point."""
    ref_text = "\n\n".join([
        f"=== Reference: {r['name']} ===\nInvariants: {', '.join(r['invariants'])}\nCode:\n{r['code']}"
        for r in matched_refs
    ])
    
    response = call_llm([
        {"role": "system", "content": """You are performing contrastive auditing.

Compare the target entry point against secure reference implementations.

For each reference:
1. What invariants does it enforce?
2. Does the target enforce the same invariant?
3. If NOT, what vulnerability does this create?

Focus on MISSING invariants — checks that the reference performs but the target does not.

Output ONLY valid JSON:
{
  "findings": [
    {
      "title": "specific vulnerability name",
      "invariant": "what should be true but isn't",
      "severity": "critical/high/medium/low",
      "file": "file path",
      "line": "line number",
      "attack": "step-by-step exploit",
      "impact": "concrete damage"
    }
  ]
}"""},
        {"role": "user", "content": f"""TARGET ENTRY POINT:
Name: {entry_point.get('name', '?')}
Purpose: {entry_point.get('purpose', '?')}
File: {entry_point.get('file', '?')}
Handles value: {entry_point.get('handles_value', '?')}

TARGET CODE:
{code_context[:15000]}

SECURE REFERENCES:
{ref_text}

Compare the target against each reference.
What invariants are MISSING? What vulnerabilities exist?"""}
    ], max_tokens=4096)
    
    result = parse_json(response)
    if not result:
        return []
    
    if isinstance(result, dict):
        result = result.get("findings", [result])
    if not isinstance(result, list):
        result = []
    
    return result


def verify_finding(finding, code_context):
    """Verify a finding with concrete evidence."""
    response = call_llm([
        {"role": "system", "content": """Verify this vulnerability finding. Check the code.

Confirm:
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
        {"role": "user", "content": f"""FINDING:
{json.dumps(finding, indent=2)[:2000]}

CODE:
{code_context[:12000]}

Is this a real vulnerability?"""}
    ], max_tokens=2048)
    
    result = parse_json(response)
    if result and result.get("status") == "confirmed":
        return result
    return None


def audit_project(project_key):
    """Audit a single project."""
    project = PROJECTS[project_key]
    project_id = project["id"]
    project_dir = SCABENCH_REPOS / project_id
    
    print(f"\n{'='*70}")
    print(f"AUDITING: {project['name']} ({project_id})")
    print(f"Expected high/critical: {project['high_critical']}")
    print(f"Language: {project['lang']}")
    print(f"{'='*70}\n")
    
    start = time.time()
    
    # Load references
    references = load_references()
    print(f"Loaded {len(references)} reference patterns")
    
    # Find source files
    source_files = find_project_files(project_id)
    if not source_files:
        print("No source files found!")
        return {"project": project_key, "findings": [], "dr": 0}
    
    print(f"Found {len(source_files)} source files")
    
    # Identify entry points
    print("\n[1] Identifying entry points...")
    entry_points, all_code = identify_entry_points(source_files, project_dir)
    print(f"  Found {len(entry_points)} entry points")
    
    # Audit each entry point
    all_findings = []
    for i, ep in enumerate(entry_points):
        print(f"\n[{i+1}/{len(entry_points)}] Auditing: {ep.get('name', '?')}")
        
        # Match references
        matched = match_references(ep, references)
        if not matched:
            print(f"  No matching references, skipping")
            continue
        
        print(f"  Matched {len(matched)} reference patterns")
        
        # Contrastive analysis
        candidates = contrastive_analyze(ep, matched, all_code)
        print(f"  Found {len(candidates)} candidate vulnerabilities")
        
        # Verify each candidate
        for candidate in candidates:
            verified = verify_finding(candidate, all_code)
            if verified:
                all_findings.append(verified)
                print(f"  ✓ CONFIRMED: {verified.get('title', '?')[:60]}")
    
    duration = time.time() - start
    
    # Calculate DR
    confirmed_high_crit = [f for f in all_findings if f.get("severity", "").lower() in ["high", "critical"]]
    dr = len(confirmed_high_crit) / project["high_critical"] if project["high_critical"] > 0 else 0
    
    # Print results
    print(f"\n{'='*70}")
    print(f"RESULTS: {project['name']}")
    print(f"{'='*70}")
    print(f"Duration: {duration:.0f}s")
    print(f"Total findings: {len(all_findings)}")
    print(f"High/Critical findings: {len(confirmed_high_crit)}")
    print(f"Expected high/critical: {project['high_critical']}")
    print(f"Detection Rate: {dr:.1%}")
    print()
    
    for f in confirmed_high_crit:
        print(f"  [{f.get('severity')}] {f.get('title', '?')}")
        print(f"    File: {f.get('file', '?')}:{f.get('line', '?')}")
        print(f"    Invariant: {f.get('invariant', '?')[:80]}")
        print()
    
    print(f"{'='*70}")
    
    # Save results
    result = {
        "project": project_key,
        "project_id": project_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": round(duration, 1),
        "total_findings": len(all_findings),
        "high_critical_findings": len(confirmed_high_crit),
        "expected_high_critical": project["high_critical"],
        "detection_rate": dr,
        "findings": all_findings,
    }
    
    # Save to log
    log_dir = LOG_DIR / project_key / time.strftime("%Y%m%d-%H%M%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "results.json").write_text(json.dumps(result, indent=2))
    print(f"\nSaved to {log_dir}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Autonomous Contrastive Auditor")
    parser.add_argument("--project", help="Run specific project (e.g., crestal)")
    parser.add_argument("--list", action="store_true", help="List available projects")
    args = parser.parse_args()
    
    if args.list:
        print("Available projects:")
        for key, proj in PROJECTS.items():
            print(f"  {key:15s} — {proj['name']:20s} ({proj['high_critical']} high/critical)")
        return
    
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.project:
        if args.project not in PROJECTS:
            print(f"Unknown project: {args.project}")
            print(f"Available: {', '.join(PROJECTS.keys())}")
            return
        result = audit_project(args.project)
    else:
        # Run all projects
        results = []
        for key in PROJECTS:
            try:
                result = audit_project(key)
                results.append(result)
            except Exception as e:
                print(f"Error on {key}: {e}")
                results.append({"project": key, "error": str(e)})
        
        # Summary
        print(f"\n{'='*70}")
        print(f"FINAL SUMMARY")
        print(f"{'='*70}")
        
        total_expected = 0
        total_found = 0
        for r in results:
            if "error" in r:
                print(f"  {r['project']:15s} — ERROR: {r.get('error', '?')[:50]}")
            else:
                dr = r.get("detection_rate", 0)
                found = r.get("high_critical_findings", 0)
                expected = r.get("expected_high_critical", 0)
                total_expected += expected
                total_found += found
                status = "✓" if dr >= 1.0 else "✗"
                print(f"  {status} {r['project']:15s} — {found}/{expected} ({dr:.0%})")
        
        overall_dr = total_found / total_expected if total_expected > 0 else 0
        print(f"\n  Overall: {total_found}/{total_expected} ({overall_dr:.0%})")
        print(f"{'='*70}")
        
        # Save summary
        summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": results,
            "total_expected": total_expected,
            "total_found": total_found,
            "overall_dr": overall_dr,
        }
        summary_path = LOG_DIR / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
