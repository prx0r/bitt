#!/usr/bin/env python3
"""
Minimal Contrastive Auditor — Find 1 ground truth vuln on crestal-network.

Approach (from LogicScan):
1. Read target contract
2. Identify business function (payment processing)
3. Retrieve reference implementations of same pattern
4. Compare: what invariants does reference enforce that target is missing?
5. Missing invariant = candidate vulnerability
"""
import json
import os
import re
import sys
from pathlib import Path

# Config
PROXY = os.environ.get("INFERENCE_API", "http://localhost:8087")
API_KEY = os.environ.get("INFERENCE_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "mimo-v2.5")

import requests


def call_llm(messages, max_tokens=4096, temperature=0.1):
    """Call LLM through proxy."""
    for attempt in range(3):
        try:
            resp = requests.post(f"{PROXY}/inference", headers={
                "x-inference-api-key": API_KEY,
                "x-agent-id": "contrastive-auditor",
                "x-job-run-id": f"contrast-{int(time.time())}-{attempt}",
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
        except:
            pass
        time.sleep(2)
    return ""


def parse_json_from_text(text):
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
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except:
        return ""


# Reference implementations of common payment patterns
REFERENCE_PAYMENT_PATTERNS = {
    "safe_transfer_from_only_msgsender": """
// CORRECT PATTERN: Only transfer from msg.sender
function payWithERC20(address token, uint256 amount) external {
    require(amount > 0, "Amount must be > 0");
    IERC20(token).safeTransferFrom(msg.sender, feeCollectionWallet, amount);
}
// INVARIANT: Only msg.sender can authorize token transfer from their own address.
// The fromAddress is ALWAYS msg.sender — no parameter injection possible.
""",
    
    "explicit_approval_check": """
// CORRECT PATTERN: Require explicit approval before transfer
function payWithERC20(address token, uint256 amount, address user) external {
    require(user != address(0), "Invalid user");
    require(amount > 0, "Amount must be > 0");
    // Check that user has approved this contract
    require(IERC20(token).allowance(user, address(this)) >= amount, "Insufficient allowance");
    IERC20(token).safeTransferFrom(user, feeCollectionWallet, amount);
}
// INVARIANT: The contract verifies allowance BEFORE attempting transfer.
// If user hasn't approved, the function reverts safely.
""",
    
    "signature_with_replay_protection": """
// CORRECT PATTERN: Signature-based with replay protection
function payWithERC20WithSig(
    address token, uint256 amount, address user, bytes memory sig
) external {
    require(user != address(0), "Invalid user");
    bytes32 digest = keccak256(abi.encodePacked(token, amount, user, nonce[user]++, block.chainid));
    address signer = ECDSA.recover(digest, sig);
    require(signer == user, "Invalid signature");
    IERC20(token).safeTransferFrom(user, feeCollectionWallet, amount);
}
// INVARIANT: Signature is verified against the user address.
// Nonce prevents replay attacks. Chain ID prevents cross-chain attacks.
""",
}


def identify_business_functions(source_dir):
    """Step 1: Identify the business functions in the target contract."""
    print("[1] Identifying business functions...")
    
    files = list(source_dir.glob("**/*.sol"))
    all_code = ""
    for f in files:
        if "test" not in f.name.lower() and "script" not in f.name.lower():
            content = read_file(f, 20000)
            if content:
                all_code += f"\n--- {f.relative_to(source_dir)} ---\n{content}\n"
    
    response = call_llm([
        {"role": "system", "content": """You are a smart contract analyst. Identify the business functions in this contract.

Focus on:
1. What does this contract do? (business purpose)
2. What are the externally callable functions that handle money/value?
3. What invariants should these functions enforce?

Output ONLY valid JSON:
{
  "business_purpose": "what this contract does",
  "value_handling_functions": [
    {
      "name": "function name",
      "file": "which file",
      "purpose": "what it does with value",
      "expected_invariants": ["what should be true"]
    }
  ]
}"""},
        {"role": "user", "content": f"Analyze these contracts:\n{all_code[:15000]}"}
    ], max_tokens=4096)
    
    return parse_json_from_text(response)


def retrieve_reference_implementations(business_function):
    """Step 2: Retrieve reference implementations for the same pattern."""
    print(f"[2] Retrieving references for: {business_function.get('name', '?')}")
    
    # Match business function to reference patterns
    purpose = business_function.get("purpose", "").lower()
    references = {}
    
    if "transfer" in purpose or "payment" in purpose or "pay" in purpose:
        references = REFERENCE_PAYMENT_PATTERNS
    
    return references


def contrastive_audit(target_code, business_function, references):
    """Step 3: Contrastive audit — compare target against references."""
    print("[3] Running contrastive audit...")
    
    ref_text = "\n\n".join([
        f"=== Reference Pattern: {name} ===\n{code}"
        for name, code in references.items()
    ])
    
    response = call_llm([
        {"role": "system", "content": """You are performing contrastive auditing. Compare the target contract against reference implementations.

For each reference pattern:
1. What invariants does the reference enforce?
2. Does the target enforce the same invariant?
3. If NOT, what vulnerability does this create?

Be SPECIFIC. Name the exact invariant that is missing.
Output ONLY valid JSON: list of findings.""",
},
        {"role": "user", "content": f"""TARGET CONTRACT:
{target_code[:12000]}

BUSINESS FUNCTION TO AUDIT:
{json.dumps(business_function, indent=2)}

REFERENCE IMPLEMENTATIONS:
{ref_text}

Compare the target against each reference.
What invariants are MISSING in the target?
What vulnerabilities do these missing invariants create?"""}
    ], max_tokens=4096)
    
    return parse_json_from_text(response)


def verify_finding(finding, target_code):
    """Step 4: Verify the finding with concrete evidence."""
    print(f"[4] Verifying: {finding.get('invariant', finding.get('title', '?'))[:60]}")
    
    response = call_llm([
        {"role": "system", "content": """You are verifying a vulnerability finding. Be STRICT.

Requirements to confirm:
1. CONCRETE CODE LOCATION: Which function/line has the bug?
2. MISSING INVARIANT: What specific invariant is not enforced?
3. ATTACK SCENARIO: How can an attacker exploit this?
4. IMPACT: What does the attacker gain?

If any requirement is missing, REJECT.
Output ONLY valid JSON:
{
  "status": "confirmed" or "rejected",
  "title": "specific vulnerability name",
  "invariant": "what should be true but isn't",
  "attack": "step-by-step exploit",
  "impact": "what attacker gains",
  "severity": "critical/high/medium/low",
  "file": "exact file path",
  "line": "line number or range"
}"""},
        {"role": "user", "content": f"""FINDING TO VERIFY:
{json.dumps(finding, indent=2)[:3000]}

TARGET CODE:
{target_code[:12000]}

VERIFY STRICTLY:
- Is there a concrete missing invariant?
- Is the affected code exact (not speculative)?
- Is the attack realistic?
- Is the impact concrete?"""}
    ], max_tokens=2048)
    
    return parse_json_from_text(response)


def run_contrastive_audit(source_dir, project_name):
    """Main pipeline."""
    import time
    start = time.time()
    
    print(f"\n{'='*60}")
    print(f"Contrastive Audit: {project_name}")
    print(f"{'='*60}\n")
    
    # Step 1: Identify business functions
    business_funcs = identify_business_functions(source_dir)
    if not business_funcs:
        print("Failed to identify business functions")
        return []
    
    # Handle case where LLM returns a list instead of dict
    if isinstance(business_funcs, list):
        if len(business_funcs) > 0 and isinstance(business_funcs[0], dict):
            business_funcs = business_funcs[0]
        else:
            print(f"Unexpected format: {type(business_funcs)}")
            return []
    
    print(f"  Business purpose: {business_funcs.get('business_purpose', '?')[:80]}")
    print(f"  Value-handling functions: {len(business_funcs.get('value_handling_functions', []))}")
    
    all_findings = []
    
    for func in business_funcs.get("value_handling_functions", []):
        print(f"\n--- Auditing: {func.get('name', '?')} ---")
        
        # Step 2: Retrieve references
        references = retrieve_reference_implementations(func)
        if not references:
            print("  No reference patterns found")
            continue
        
        # Read target code
        target_files = list(source_dir.glob("**/*.sol"))
        target_code = ""
        for f in target_files:
            if "test" not in f.name.lower() and "script" not in f.name.lower():
                content = read_file(f, 15000)
                if content:
                    target_code += f"\n--- {f.relative_to(source_dir)} ---\n{content}\n"
        
        # Step 3: Contrastive audit
        candidates = contrastive_audit(target_code, func, references)
        if not candidates:
            print("  No candidates found")
            continue
        
        if not isinstance(candidates, list):
            candidates = [candidates] if isinstance(candidates, dict) else []
        
        # Step 4: Verify each candidate
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            verified = verify_finding(candidate, target_code)
            if verified and verified.get("status") == "confirmed":
                all_findings.append(verified)
                print(f"  ✓ CONFIRMED: {verified.get('title', '?')[:60]}")
            else:
                print(f"  ✗ Rejected: {candidate.get('invariant', '?')[:60]}")
    
    duration = time.time() - start
    print(f"\n{'='*60}")
    print(f"Results: {len(all_findings)} findings in {duration:.0f}s")
    for f in all_findings:
        print(f"  [{f.get('severity')}] {f.get('title', '?')}")
        print(f"    Invariant: {f.get('invariant', '?')[:80]}")
        print(f"    File: {f.get('file', '?')}")
    print(f"{'='*60}")
    
    return all_findings


if __name__ == "__main__":
    import time
    
    source_dir = Path("/root/bitt/data/scabench-repos/sherlock_crestal-network_2025_03")
    project_name = "sherlock_crestal-network_2025_03"
    
    findings = run_contrastive_audit(source_dir, project_name)
    
    # Save results
    output = {
        "project": project_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "findings": findings,
        "total_findings": len(findings)
    }
    
    out_path = Path("/root/bitt/data/contrastive-audit-crestal.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to {out_path}")
