#!/usr/bin/env python3
"""
Minimal Contrastive Auditor v2 — Direct approach.
Skip business function identification, go straight to contrastive comparison.
"""
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


def call_llm(messages, max_tokens=4096, temperature=0.1):
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "contrastive-v2",
                "x-job-run-id": f"cv2-{int(time.time())}-{attempt}",
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


# Reference: What a SECURE payment function looks like
SECURE_PAYMENT_REFERENCE = """
=== SECURE PATTERN: Payment with msg.sender only ===

// In a secure payment contract, the token transfer ALWAYS uses msg.sender:
function payWithERC20(address token, uint256 amount) external {
    require(amount > 0, "Amount must be > 0");
    // SAFE: Only transfers from the caller's own address
    IERC20(token).safeTransferFrom(msg.sender, feeWallet, amount);
}

// OR if allowing gasless payments, the fromAddress must be verified:
function payWithERC20Gasless(
    address token, uint256 amount, address user, bytes memory sig
) external {
    // SAFE: Signature proves user authorized this transfer
    bytes32 digest = keccak256(abi.encodePacked(token, amount, user, nonce++));
    require(ECDSA.recover(digest, sig) == user, "Invalid signature");
    IERC20(token).safeTransferFrom(user, feeWallet, amount);
}

// KEY INVARIANT: A contract should NEVER call safeTransferFrom(fromAddress, ...)
// where fromAddress is an unverified parameter. This allows anyone to drain
// tokens from any address that approved the contract.
"""


def run_direct_contrastive_audit(source_dir, project_name):
    """Direct contrastive audit — no intermediate steps."""
    start = time.time()
    
    print(f"\n{'='*60}")
    print(f"Direct Contrastive Audit: {project_name}")
    print(f"{'='*60}\n")
    
    # Read ALL contract code
    files = list(source_dir.glob("**/*.sol"))
    all_code = ""
    for f in files:
        if "test" not in f.name.lower() and "script" not in f.name.lower():
            content = read_file(f, 15000)
            if content:
                all_code += f"\n--- {f.relative_to(source_dir)} ---\n{content}\n"
    
    print(f"Read {len(files)} Solidity files")
    print(f"Total code: {len(all_code)} chars\n")
    
    # Step 1: Find payment/token transfer patterns
    print("[1] Finding payment patterns in target...")
    response = call_llm([
        {"role": "system", "content": """Find ALL token transfer patterns in this smart contract code.

Look for:
1. safeTransferFrom calls — who is the fromAddress parameter?
2. Functions that take address parameters and transfer tokens
3. Any pattern where an address parameter controls who pays

Output ONLY valid JSON:
{
  "transfer_patterns": [
    {
      "function": "function name",
      "file": "file path",
      "line": "line number",
      "pattern": "what the transfer does",
      "from_address_source": "where fromAddress comes from (msg.sender / parameter / signature)",
      "is_vulnerable": true/false,
      "reason": "why vulnerable"
    }
  ]
}"""},
        {"role": "user", "content": f"Analyze this code for token transfer patterns:\n{all_code[:20000]}"}
    ], max_tokens=4096)
    
    patterns = parse_json(response)
    if not patterns:
        print("  Failed to parse patterns")
        print(f"  Raw response: {response[:500]}")
        return []
    
    if isinstance(patterns, dict):
        patterns = patterns.get("transfer_patterns", [])
    
    print(f"  Found {len(patterns)} transfer patterns")
    for p in patterns:
        if isinstance(p, dict):
            vuln = "⚠️" if p.get("is_vulnerable") else "✓"
            print(f"  {vuln} {p.get('function', '?')} — from={p.get('from_address_source', '?')}")
    
    # Step 2: Contrastive comparison with secure reference
    print("\n[2] Comparing against secure reference patterns...")
    response = call_llm([
        {"role": "system", "content": f"""You are performing contrastive auditing.

SECURE REFERENCE PATTERNS:
{SECURE_PAYMENT_REFERENCE}

For each transfer pattern found in the target:
1. Does it match a secure pattern?
2. If NOT, what invariant is missing?
3. What vulnerability does the missing invariant create?

Output ONLY valid JSON: list of findings.""",
},
        {"role": "user", "content": f"""TARGET TRANSFER PATTERNS:
{json.dumps(patterns, indent=2)[:8000]}

TARGET CODE:
{all_code[:15000]}

Compare each pattern against the secure reference.
What invariants are MISSING? What vulnerabilities exist?"""}
    ], max_tokens=4096)
    
    findings = parse_json(response)
    if not findings:
        print("  Failed to parse findings")
        print(f"  Raw response: {response[:500]}")
        return []
    
    if isinstance(findings, dict):
        findings = findings.get("findings", [findings])
    if not isinstance(findings, list):
        findings = []
    
    print(f"  Found {len(findings)} candidate vulnerabilities")
    
    # Step 3: Verify each finding
    print("\n[3] Verifying findings...")
    verified = []
    
    for i, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        
        print(f"\n  [{i+1}/{len(findings)}] Verifying: {finding.get('title', finding.get('invariant', '?'))[:60]}")
        
        response = call_llm([
            {"role": "system", "content": """Verify this vulnerability finding. Be STRICT.

Requirements to CONFIRM:
1. CONCRETE CODE: Which function and line has the bug?
2. MISSING INVARIANT: What specific check is missing?
3. ATTACK: How can an attacker exploit this? Step by step.
4. IMPACT: What does the attacker gain?

If ANY requirement is missing, REJECT.

Output ONLY valid JSON:
{
  "status": "confirmed" or "rejected",
  "title": "specific vulnerability name (NOT 'Unknown vulnerability')",
  "invariant": "what should be true but isn't",
  "attack": "step-by-step exploit",
  "impact": "concrete damage",
  "severity": "critical/high/medium/low",
  "file": "exact file path",
  "line": "line number"
}"""},
            {"role": "user", "content": f"""FINDING:
{json.dumps(finding, indent=2)[:2000]}

CODE CONTEXT:
{all_code[:12000]}

VERIFY: Is this a real vulnerability with a concrete missing invariant?"""}
        ], max_tokens=2048)
        
        result = parse_json(response)
        if result and result.get("status") == "confirmed":
            verified.append(result)
            print(f"    ✓ CONFIRMED: {result.get('title', '?')[:60]}")
            print(f"      Severity: {result.get('severity')}")
            print(f"      File: {result.get('file', '?')}")
        else:
            print(f"    ✗ Rejected")
    
    duration = time.time() - start
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(verified)} findings in {duration:.0f}s")
    for f in verified:
        print(f"\n  [{f.get('severity')}] {f.get('title', '?')}")
        print(f"  Invariant: {f.get('invariant', '?')}")
        print(f"  File: {f.get('file', '?')}:{f.get('line', '?')}")
        print(f"  Attack: {f.get('attack', '?')[:100]}")
        print(f"  Impact: {f.get('impact', '?')[:100]}")
    print(f"{'='*60}")
    
    return verified


if __name__ == "__main__":
    source_dir = Path("/root/bitt/data/scabench-repos/sherlock_crestal-network_2025_03")
    project_name = "sherlock_crestal-network_2025_03"
    
    findings = run_direct_contrastive_audit(source_dir, project_name)
    
    output = {
        "project": project_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "findings": findings,
        "total_findings": len(findings)
    }
    
    out_path = Path("/root/bitt/data/contrastive-audit-crestal-v2.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to {out_path}")
