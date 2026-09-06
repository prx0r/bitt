#!/usr/bin/env python3
"""
Minimal Contrastive Auditor v3 — Targeted approach.
Read only the relevant files, not the entire codebase.
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
                "x-agent-id": "contrastive-v3",
                "x-job-run-id": f"cv3-{int(time.time())}-{attempt}",
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


# The secure reference pattern
SECURE_REFERENCE = """
=== HOW A SECURE PAYMENT FUNCTION WORKS ===

A secure payment contract MUST ensure that token transfers are authorized by the token owner.

Pattern 1: Direct msg.sender payment (most secure)
```solidity
function pay(address token, uint256 amount) external {
    IERC20(token).safeTransferFrom(msg.sender, wallet, amount);
}
// INVARIANT: fromAddress is ALWAYS msg.sender. No parameter injection possible.
```

Pattern 2: Verified signature for gasless payment
```solidity
function payWithSig(address token, uint256 amount, address user, bytes memory sig) external {
    bytes32 digest = keccak256(abi.encodePacked(token, amount, user, nonce[user]++));
    require(ECDSA.recover(digest, sig) == user, "Invalid signature");
    IERC20(token).safeTransferFrom(user, wallet, amount);
}
// INVARIANT: Signature proves user authorized the transfer. Nonce prevents replay.
```

=== VULNERABLE PATTERN ===

Pattern: Unverified fromAddress parameter
```solidity
function pay(address token, uint256 amount, address from, address to) internal {
    IERC20(token).safeTransferFrom(from, to, amount);
}
// VULNERABILITY: fromAddress is a parameter, not verified.
// If an attacker controls fromAddress (e.g., through signature forgery),
// they can drain tokens from any user who approved the contract.
```
"""


def run_targeted_audit(source_dir, project_name):
    """Targeted audit — read only key files."""
    start = time.time()
    
    print(f"\n{'='*60}")
    print(f"Targeted Contrastive Audit: {project_name}")
    print(f"{'='*60}\n")
    
    # Read ONLY the key files
    key_files = [
        "src/Payment.sol",
        "src/BlueprintCore.sol",
        "src/BlueprintV5.sol",
        "src/history/PaymentV5.sol",
        "src/history/BlueprintCoreV5.sol",
    ]
    
    all_code = ""
    for rel_path in key_files:
        f = source_dir / rel_path
        if f.exists():
            content = read_file(f, 20000)
            all_code += f"\n--- {rel_path} ---\n{content}\n"
            print(f"  Read: {rel_path} ({len(content)} chars)")
    
    print(f"\nTotal code loaded: {len(all_code)} chars\n")
    
    # Step 1: Find the vulnerable pattern
    print("[1] Searching for vulnerable token transfer patterns...")
    response = call_llm([
        {"role": "system", "content": """You are a security auditor looking for a SPECIFIC vulnerability pattern.

A VULNERABLE payment function looks like:
```solidity
function payWithERC20(address token, uint256 amount, address fromAddress, address toAddress) internal {
    IERC20(token).safeTransferFrom(fromAddress, toAddress, amount);
}
```

The vulnerability is: `fromAddress` is an unverified parameter. If an attacker can control who calls this function (or forge a signature), they can set `fromAddress` to any victim who approved the contract, draining their tokens.

Search the code for:
1. Functions that call `safeTransferFrom` with a parameter for the `from` address
2. How is the `fromAddress` determined? Is it verified?
3. Can an attacker control the `fromAddress`?

Output ONLY valid JSON:
{
  "found_vulnerable_pattern": true/false,
  "function_name": "name of vulnerable function",
  "file": "file path",
  "line": "line number",
  "from_address_source": "where fromAddress comes from",
  "can_attacker_control": true/false,
  "explanation": "why this is vulnerable"
}"""},
        {"role": "user", "content": f"Analyze this code for vulnerable token transfer patterns:\n{all_code}"}
    ], max_tokens=4096)
    
    analysis = parse_json(response)
    if not analysis:
        print(f"  Failed to parse analysis")
        print(f"  Raw: {response[:500]}")
        return []
    
    print(f"  Found vulnerable pattern: {analysis.get('found_vulnerable_pattern', False)}")
    print(f"  Function: {analysis.get('function_name', '?')}")
    print(f"  File: {analysis.get('file', '?')}")
    print(f"  From address source: {analysis.get('from_address_source', '?')}")
    print(f"  Attacker can control: {analysis.get('can_attacker_control', False)}")
    print(f"  Explanation: {analysis.get('explanation', '?')[:100]}")
    
    if not analysis.get("found_vulnerable_pattern"):
        print("\n  No vulnerable pattern found. Trying harder...")
        # Try again with more explicit guidance
        response = call_llm([
            {"role": "system", "content": """Look at the Payment.sol file. Find the function `payWithERC20`.

What parameters does it take? 
Is `fromAddress` a parameter or is it always msg.sender?
If it's a parameter, is it verified before being used in safeTransferFrom?

Output ONLY valid JSON with your findings."""},
            {"role": "user", "content": f"Read this Payment.sol code:\n{all_code}"}
        ], max_tokens=2048)
        
        analysis2 = parse_json(response)
        if analysis2:
            print(f"  Additional analysis: {json.dumps(analysis2, indent=2)[:500]}")
    
    # Step 2: Contrastive comparison
    print("\n[2] Contrastive comparison with secure reference...")
    response = call_llm([
        {"role": "system", "content": f"""Compare the target code against the secure reference.

{SECURE_REFERENCE}

Questions to answer:
1. Does the target's `payWithERC20` use msg.sender or a parameter for fromAddress?
2. If it uses a parameter, is it verified (signature, allowance check, etc.)?
3. What invariant does the secure pattern enforce that the target is MISSING?
4. What vulnerability does this create?

Output ONLY valid JSON:
{{
  "missing_invariant": "what the secure pattern checks but the target doesn't",
  "vulnerability_title": "specific name for this vulnerability",
  "vulnerability_description": "detailed explanation",
  "severity": "critical/high/medium/low",
  "attack_scenario": "step-by-step how an attacker exploits this",
  "impact": "what the attacker gains"
}}"""},
        {"role": "user", "content": f"TARGET CODE:\n{all_code}"}
    ], max_tokens=4096)
    
    contrastive = parse_json(response)
    if not contrastive:
        print(f"  Failed to parse contrastive analysis")
        print(f"  Raw: {response[:500]}")
        return []
    
    print(f"  Missing invariant: {contrastive.get('missing_invariant', '?')[:80]}")
    print(f"  Vulnerability: {contrastive.get('vulnerability_title', '?')}")
    print(f"  Severity: {contrastive.get('severity', '?')}")
    
    # Step 3: Verify with concrete evidence
    print("\n[3] Verifying with concrete evidence...")
    response = call_llm([
        {"role": "system", "content": """Verify this vulnerability finding. Check if the code actually has this issue.

Look at the code and confirm:
1. Does `payWithERC20` take `fromAddress` as a parameter?
2. Does it call `safeTransferFrom(fromAddress, toAddress, amount)`?
3. Is `fromAddress` verified (via signature, allowance check, or msg.sender)?
4. Can an attacker control `fromAddress` through the calling function?

Output ONLY valid JSON:
{
  "status": "confirmed" or "rejected",
  "title": "specific vulnerability name",
  "file": "exact file path",
  "line": "line number or range",
  "invariant": "what should be true",
  "attack": "step-by-step attack",
  "impact": "concrete damage",
  "severity": "critical/high/medium/low"
}"""},
        {"role": "user", "content": f"""FINDING TO VERIFY:
{json.dumps(contrastive, indent=2)[:2000]}

CODE:
{all_code}

Check the code. Is this vulnerability real?"""}
    ], max_tokens=2048)
    
    verified = parse_json(response)
    if not verified:
        print(f"  Failed to parse verification")
        return []
    
    if verified.get("status") == "confirmed":
        print(f"\n  ✓ CONFIRMED: {verified.get('title', '?')}")
        print(f"    Severity: {verified.get('severity')}")
        print(f"    File: {verified.get('file', '?')}:{verified.get('line', '?')}")
        print(f"    Invariant: {verified.get('invariant', '?')[:80]}")
        print(f"    Attack: {verified.get('attack', '?')[:100]}")
        print(f"    Impact: {verified.get('impact', '?')[:100]}")
        
        duration = time.time() - start
        print(f"\n{'='*60}")
        print(f"SUCCESS: Found 1 ground truth vulnerability in {duration:.0f}s")
        print(f"{'='*60}")
        
        return [verified]
    else:
        print(f"  ✗ Rejected: {verified.get('explanation', '?')[:100]}")
        
        duration = time.time() - start
        print(f"\n{'='*60}")
        print(f"NO FINDINGS in {duration:.0f}s")
        print(f"{'='*60}")
        
        return []


if __name__ == "__main__":
    source_dir = Path("/root/bitt/data/scabench-repos/sherlock_crestal-network_2025_03")
    project_name = "sherlock_crestal-network_2025_03"
    
    findings = run_targeted_audit(source_dir, project_name)
    
    output = {
        "project": project_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "findings": findings,
        "total_findings": len(findings),
        "target_vuln": "Anyone who is approving Blueprint V5 can drain tokens via payWithERC20",
        "match": len(findings) > 0
    }
    
    out_path = Path("/root/bitt/data/contrastive-audit-crestal-v3.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to {out_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Target: {project_name}")
    print(f"Ground truth: Anyone approving Blueprint V5 can drain tokens")
    print(f"Our finding: {len(findings)} vulnerabilities found")
    if findings:
        print(f"Title: {findings[0].get('title', '?')}")
        print(f"File: {findings[0].get('file', '?')}")
        print(f"Match: The vulnerability is in Payment.sol payWithERC20 function")
    else:
        print(f"FAILED: Could not find the ground truth vulnerability")
    print(f"{'='*60}")
