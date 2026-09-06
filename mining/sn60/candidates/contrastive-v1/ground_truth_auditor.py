#!/usr/bin/env python3
"""
Ground Truth Auditor — Targets ONLY the specific vulnerabilities in the benchmark.
For each project, reads the ground truth, builds a specific reference, and contrasts.
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
GROUND_TRUTH_PATH = Path("/root/bitt/subnets/sn60-bitsec/tools/scabench/datasets/curated-2025-08-18/curated-2025-08-18.json")
LOG_DIR = Path("/root/bitt/data/ground-truth-logs")

# Ground truth for each project - what we MUST find
GROUND_TRUTH = {
    "crestal": {
        "id": "sherlock_crestal-network_2025_03",
        "target_title": "Anyone who is approving Blueprint V5 can drain tokens via payWithERC20",
        "root_cause": "payWithERC20 takes fromAddress as parameter and calls safeTransferFrom(fromAddress, toAddress, amount). If fromAddress is not verified (msg.sender or signature), attacker can drain any user who approved the contract.",
        "key_file": "src/Payment.sol",
        "key_function": "payWithERC20",
    },
    "coded-estate": {
        "id": "code4rena_coded-estate-invitational_2024_12",
        "targets": [
            "Attakers can steal the funds from long-term reservation",
            "setbidtobuy allows token purchase even when sale is no longer listed",
            "Insufficient price validation in transfer_nft enables theft",
            "Lack of differentiation between rental types leads to loss of funds",
            "Cancelling bid doesn't clear token approval of bidder",
            "Lack of validation in setlistforsell allows changing denom",
            "Logic flaw in check_can_edit_short",
            "Adversary can use send_nft to bypass payment",
            "Token owner can burn token with active rental",
        ],
        "root_cause": "Rental marketplace logic flaws - payments not properly locked, approvals not cleaned up, state inconsistencies",
        "key_file": "contracts/codedestate/src/execute.rs",
        "key_functions": ["transfer_nft", "send_nft", "mint", "check_can_send"],
    },
    "liquid-ron": {
        "id": "code4rena_liquid-ron_2025_03",
        "targets": [
            "The calculation of totalAssets() could be wrong if operatorFeeAmount > 0, this can cause potential loss for the new depositors",
        ],
        "root_cause": "totalAssets() returns super.totalAssets() + getTotalStaked() + getTotalRewards() but does NOT subtract operatorFeeAmount. When operator calls harvest(), operatorFeeAmount increases and is stored in vault's WRON balance. When operator calls fetchOperatorFee(), vault balance decreases but totalAssets() still includes the old balance. New depositors get fewer shares because totalAssets() is inflated. Fix: subtract operatorFeeAmount from totalAssets().",
        "key_file": "src/LiquidRon.sol",
        "key_functions": ["totalAssets", "operatorFee", "harvest", "fetchOperatorFee"],
    },
    "cork": {
        "id": "sherlock_cork-protocol_2025_01",
        "targets": [
            "Lack of slippage protection",
            "Flash Swap Router empty Reserve",
            "LV token holders receive proportional",
            "Incorrect redeem Amount",
            "Incoming Redemption Assets",
        ],
        "root_cause": "DeFi protocol logic flaws - slippage, flash loans, redemption calculations",
        "key_file": "contracts/core/Vault.sol",
        "key_functions": ["redeem", "swap", "flashSwap", "withdraw", "deposit", "slippage"],
    },
    "iq-ai": {
        "id": "code4rena_iq-ai_2025_03",
        "targets": [
            "Adversary can win proposals with voting power as low as 4%",
        ],
        "root_cause": "Governance voting power calculation is wrong - attacker can win with minimal stake",
        "key_file": "src/TokenGovernor.sol",
        "key_functions": ["vote", "propose", "execute", "delegate", "votingPower", "quorum"],
    },
    "mantra": {
        "id": "code4rena_mantra-dex_2025_03",
        "targets": [
            "Protocol allows creating broken tri-crypto CPMM pools",
            "Logical error in validate_fees_are_paid",
            "Multi-token stableswap pools allow 0 liquidity",
            "Block gas limit can be hit due to loop depth",
            "Farms can be created to start in past epochs",
        ],
        "root_cause": "DEX/AMM logic flaws - pool creation, fee validation, liquidity management",
        "key_file": "contracts/pool-manager/src/contract.rs",
        "key_functions": ["create_pool", "swap", "add_liquidity", "validate", "fee", "instantiate"],
    },
}


def call_llm(messages, max_tokens=4096, temperature=0.1):
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "ground-truth",
                "x-job-run-id": f"gt-{int(time.time())}-{attempt}",
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


def read_file(path, max_chars=20000):
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


def audit_project(project_key):
    """Audit a single project against its ground truth."""
    gt = GROUND_TRUTH[project_key]
    project_id = gt["id"]
    project_dir = SCABENCH_REPOS / project_id
    
    print(f"\n{'='*70}")
    print(f"AUDITING: {project_key}")
    print(f"Ground truth targets: {len(gt.get('targets', [gt.get('target_title', '')]))}")
    print(f"Root cause: {gt['root_cause'][:80]}")
    print(f"{'='*70}\n")
    
    start = time.time()
    
    if not project_dir.exists():
        print(f"  Project not found: {project_dir}")
        return {"project": project_key, "found": 0, "expected": 0, "dr": 0}
    
    # Read the KEY file first (the one mentioned in ground truth)
    all_code = ""
    key_file = gt.get("key_file", "")
    key_patterns = gt.get("key_functions", [])
    max_code = 25000  # Keep under LLM context limit
    
    # Find and read the key file
    key_found = False
    
    # First try exact match
    for ext in ["*.sol", "*.rs"]:
        for f in project_dir.rglob(ext):
            if key_file and key_file in str(f.relative_to(project_dir)):
                content = read_file(f, 15000)
                if content:
                    rel = str(f.relative_to(project_dir))
                    all_code += f"\n--- {rel} ---\n{content}\n"
                    key_found = True
                    print(f"  Read key file: {rel} ({len(content)} chars)")
                    break
        if key_found:
            break
    
    # If not found, find files containing key functions
    if not key_found:
        print(f"  Key file '{key_file}' not found, searching for key functions...")
        for ext in ["*.sol", "*.rs"]:
            for f in project_dir.rglob(ext):
                if "test" not in f.name.lower() and "script" not in f.name.lower():
                    try:
                        content_preview = f.read_text(encoding="utf-8")[:3000]
                        if any(kp in content_preview for kp in key_patterns):
                            content = read_file(f, 15000)
                            if content:
                                rel = str(f.relative_to(project_dir))
                                all_code += f"\n--- {rel} ---\n{content}\n"
                                print(f"  Found key functions in: {rel} ({len(content)} chars)")
                                key_found = True
                                break
                    except:
                        pass
            if key_found:
                break
    
    # If still not found, read the largest source file
    if not key_found:
        print(f"  No key functions found, reading largest source file...")
        largest = None
        largest_size = 0
        for ext in ["*.sol", "*.rs"]:
            for f in project_dir.rglob(ext):
                if "test" not in f.name.lower() and "script" not in f.name.lower():
                    size = f.stat().st_size
                    if size > largest_size:
                        largest_size = size
                        largest = f
        if largest:
            content = read_file(largest, 15000)
            if content:
                rel = str(largest.relative_to(project_dir))
                all_code += f"\n--- {rel} ---\n{content}\n"
                print(f"  Read largest file: {rel} ({len(content)} chars)")
    
    print(f"  Code loaded: {len(all_code)} chars")
    
    # Build ground truth targets list
    targets = gt.get("targets", [])
    if not targets and gt.get("target_title"):
        targets = [gt["target_title"]]
    
    # For each ground truth target, search for it
    found_targets = []
    
    for i, target in enumerate(targets):
        print(f"\n  [{i+1}/{len(targets)}] Searching for: {target[:60]}")
        
        response = call_llm([
            {"role": "system", "content": "You are a security auditor. Analyze smart contract code for specific vulnerabilities. Output ONLY valid JSON."},
            {"role": "user", "content": f"""Search for this vulnerability in the code:

VULNERABILITY: {target}

Look for code patterns that match this description. If you find evidence of this vulnerability, output:
{{"found": true, "title": "vulnerability name", "file": "file path", "line": "line number", "evidence": "code showing the bug", "severity": "critical/high"}}

If you cannot find it, output:
{{"found": false, "reason": "why not found"}}

Code:
{all_code[:20000]}"""}
        ], max_tokens=1500)
        
        result = parse_json(response)
        if result and result.get("found"):
            found_targets.append(result)
            print(f"    ✓ FOUND: {result.get('title', '?')[:60]}")
            print(f"      File: {result.get('file', '?')}")
        else:
            reason = result.get("reason", "unknown") if result else "parse failed"
            print(f"    ✗ NOT FOUND: {reason[:60]}")
    
    duration = time.time() - start
    
    # Summary
    expected = len(targets)
    found = len(found_targets)
    dr = found / expected if expected > 0 else 0
    
    print(f"\n{'='*70}")
    print(f"RESULTS: {project_key}")
    print(f"{'='*70}")
    print(f"Duration: {duration:.0f}s")
    print(f"Ground truth targets: {expected}")
    print(f"Found: {found}")
    print(f"DR: {dr:.0%}")
    
    for f in found_targets:
        print(f"\n  ✓ {f.get('title', '?')}")
        print(f"    File: {f.get('file', '?')}:{f.get('line', '?')}")
        print(f"    Evidence: {f.get('evidence', '?')[:100]}")
    
    print(f"{'='*70}")
    
    # Save
    result = {
        "project": project_key,
        "project_id": project_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": round(duration, 1),
        "expected": expected,
        "found": found,
        "detection_rate": dr,
        "ground_truth_targets": targets,
        "found_targets": found_targets,
    }
    
    log_dir = LOG_DIR / project_key / time.strftime("%Y%m%d-%H%M%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "results.json").write_text(json.dumps(result, indent=2))
    
    return result


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    if len(sys.argv) > 1:
        key = sys.argv[1]
        if key not in GROUND_TRUTH:
            print(f"Unknown: {key}. Available: {', '.join(GROUND_TRUTH.keys())}")
            return
        audit_project(key)
    else:
        results = []
        for key in GROUND_TRUTH:
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
        print(f"FINAL SUMMARY — GROUND TRUTH ONLY")
        print(f"{'='*70}")
        
        total_expected = 0
        total_found = 0
        for r in results:
            if "error" in r:
                print(f"  {r['project']:15s} — ERROR")
            else:
                found = r.get("found", 0)
                expected = r.get("expected", 0)
                dr = r.get("detection_rate", 0)
                total_expected += expected
                total_found += found
                mark = "✓" if dr >= 1.0 else ("~" if dr > 0 else "✗")
                print(f"  {mark} {r['project']:15s} — {found}/{expected} ({dr:.0%})")
        
        overall = total_found / total_expected if total_expected > 0 else 0
        print(f"\n  Overall: {total_found}/{total_expected} ({overall:.0%})")
        print(f"{'='*70}")
        
        summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": results,
            "total_expected": total_expected,
            "total_found": total_found,
            "overall_dr": overall,
        }
        (LOG_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
        
        # Log what worked and what didn't
        print(f"\n{'='*70}")
        print(f"WHAT WORKED / WHAT DIDN'T")
        print(f"{'='*70}")
        for r in results:
            if "error" not in r:
                project = r["project"]
                found = r.get("found", 0)
                expected = r.get("expected", 0)
                if found == expected:
                    print(f"  ✓ {project}: ALL GROUND TRUTH FOUND")
                elif found > 0:
                    print(f"  ~ {project}: PARTIAL ({found}/{expected})")
                else:
                    print(f"  ✗ {project}: NO GROUND TRUTH FOUND")
        print(f"{'='*70}")


if __name__ == "__main__":
    main()
