"""BitSec Local Simulator — exact format matching the on-chain subnet.

Uses:
- Actual VulnerabilityCategory enum (13 categories)
- Actual PredictionResponse format
- Actual Jaccard scoring
- ScaBench datasets for ground truth

No TAO needed. Same evaluation as on-chain.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from enum import Enum

sys.path.insert(0, str(Path("/root/bitt")))
sys.path.insert(0, str(Path("/root/mwgym")))
sys.path.insert(0, str(Path("/root/cg")))

from vault import Vault
v = Vault()
os.environ['OPENCODE_API_KEY'] = v.get('opencode_go_api_key') or ''
os.environ['GROQ_API_KEY'] = v.get('groq_api_key') or ''

from workers.bitsec.cloudflare_harness import call_model


# ─── BitSec Vulnerability Categories (exact match) ──────────────────

class VulnerabilityCategory(str, Enum):
    WEAK_ACCESS_CONTROL = "weak access control"
    GOVERNANCE_ATTACKS = "governance attacks"
    REENTRANCY = "reentrancy"
    FRONT_RUNNING = "frontrunning"
    ARITHMETIC_OVERFLOW = "arithmetic overflow and underflow vulnerability"
    SELF_DESTRUCT = "self destruct"
    UNINITIALIZED_PROXY = "uninitialized proxy"
    INCORRECT_CALCULATION = "incorrect calculation"
    ROUNDING_ERROR = "rounding error"
    IMPROPER_INPUT_VALIDATION = "improper input validation"
    BAD_RANDOMNESS = "bad randomness vulnerability"
    REPLAY_SIGNATURE = "replay attacks/signature malleability"
    ORACLE_MANIPULATION = "oracle/price manipulation"


# ─── Prediction Response (BitSec format) ─────────────────────────────

class Vulnerability:
    def __init__(self, title: str, severity: str, category: str,
                 description: str = "", vulnerable_code: str = ""):
        self.title = title
        self.severity = severity
        self.category = category
        self.description = description
        self.vulnerable_code = vulnerable_code

    def to_dict(self):
        return {
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "vulnerable_code": self.vulnerable_code,
        }


class PredictionResponse:
    def __init__(self, prediction: bool, vulnerabilities: list[Vulnerability]):
        self.prediction = prediction
        self.vulnerabilities = vulnerabilities

    def to_dict(self):
        return {
            "prediction": self.prediction,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
        }


# ─── Jaccard Scoring (BitSec official) ──────────────────────────────

def jaccard_score(expected: list[str], found: list[str]) -> float:
    """Jaccard similarity of vulnerability categories.
    
    This is BitSec's official scoring metric.
    """
    if not expected and not found:
        return 1.0
    if not expected or not found:
        return 0.0

    set_expected = set(e.lower().strip() for e in expected)
    set_found = set(f.lower().strip() for f in found)

    intersection = set_expected & set_found
    union = set_expected | set_found

    return len(intersection) / len(union) if union else 0.0


# ─── Challenge Generator ─────────────────────────────────────────────

def generate_challenge(code: str, target_category: str) -> dict:
    """Generate a BitSec challenge by injecting a specific vulnerability.
    
    This simulates what BitSec's validator does:
    1. Takes clean code
    2. Injects a known vulnerability category
    3. Returns vulnerable code + ground truth
    """
    # Category-specific injection prompts
    injection_prompts = {
        "weak access control": "Remove or weaken access control checks (e.g., remove onlyOwner, allow anyone to call privileged functions)",
        "governance attacks": "Add a governance mechanism that can be manipulated (e.g., flash loan voting, proposal spam, delegate call abuse)",
        "reentrancy": "Add an external call before state update (classic reentrancy pattern)",
        "frontrunning": "Add a transaction ordering dependency (e.g., predictable nonce, front-runnable DEX swap)",
        "arithmetic overflow and underflow vulnerability": "Use unchecked arithmetic or remove SafeMath checks (note: Solidity 0.8+ has built-in checks, so use unchecked{} block or older pragma)",
        "self destruct": "Add a selfdestruct function callable by anyone or with weak authorization",
        "uninitialized proxy": "Add a proxy pattern without proper initialization",
        "incorrect calculation": "Add a flawed calculation (e.g., wrong order of operations, missing precision)",
        "rounding error": "Add integer division that loses precision (e.g., multiply before divide)",
        "improper input validation": "Remove input validation checks (e.g., allow zero amounts, negative values)",
        "bad randomness vulnerability": "Use block.timestamp or blockhash for randomness",
        "replay attacks/signature malleability": "Use ecrecover without nonce or chain ID",
        "oracle/price manipulation": "Use spot price from a single oracle without TWAP",
    }

    injection_instruction = injection_prompts.get(target_category, 
        f"Inject a {target_category} vulnerability")

    prompt = f"""You are creating a security test challenge.

Take this Solidity code and inject a realistic vulnerability.

INSTRUCTION: {injection_instruction}

The vulnerability should be:
- Subtle enough to require careful analysis
- Real enough to be exploitable
- Specifically a {target_category} vulnerability

Clean code:
```solidity
{code}
```

Return ONLY the vulnerable Solidity code. No explanation, no markdown."""

    result = call_model("mimo", prompt, max_tokens=1500)
    vuln_code = result.get('content', code)

    # Strip markdown
    if vuln_code.startswith('```'):
        lines = vuln_code.split('\n')
        vuln_code = '\n'.join(lines[1:-1])

    return {
        "vulnerable_code": vuln_code,
        "expected_category": target_category,
    }


# ─── Miner (our implementation) ─────────────────────────────────────

def miner_analyze(code: str) -> PredictionResponse:
    """Run our miner on code. Returns BitSec PredictionResponse format."""
    prompt = f"""Thoroughly scan the code line by line for potentially flawed logic or problematic code that could cause security vulnerabilities.

Ignore privacy concerns since the code is deployed on a public blockchain.

### Code:
{code}

### Acceptable Vulnerability Categories (use EXACTLY these strings):
- weak access control
- governance attacks
- reentrancy
- frontrunning
- arithmetic overflow and underflow vulnerability
- self destruct
- uninitialized proxy
- incorrect calculation
- rounding error
- improper input validation
- bad randomness vulnerability
- replay attacks/signature malleability
- oracle/price manipulation

Return a JSON array of vulnerabilities:
[{{"title": "...", "severity": "critical|high|medium|low", "category": "EXACT CATEGORY STRING FROM ABOVE", "description": "..."}}]

IMPORTANT: The "category" field MUST match one of the acceptable categories EXACTLY."""

    result = call_model("mimo", prompt, max_tokens=3000)
    content = result.get('content', '')

    # Parse response
    findings = []
    try:
        clean = content.strip()
        if clean.startswith('```'):
            first_nl = clean.find('\n')
            if first_nl > 0:
                clean = clean[first_nl + 1:]
            if clean.rstrip().endswith('```'):
                clean = clean.rstrip()[:-3].rstrip()

        # Try JSON array
        start = clean.find('[')
        end = clean.rfind(']') + 1
        if start >= 0 and end > start:
            raw_findings = json.loads(clean[start:end])
            for f in raw_findings:
                cat_str = f.get('category', '').lower().strip()
                # Match to VulnerabilityCategory
                matched_cat = None
                for vc in VulnerabilityCategory:
                    if vc.value.lower() == cat_str or cat_str in vc.value.lower():
                        matched_cat = vc.value
                        break
                if not matched_cat:
                    matched_cat = cat_str

                findings.append(Vulnerability(
                    title=f.get('title', 'unknown'),
                    severity=f.get('severity', 'medium'),
                    category=matched_cat,
                    description=f.get('description', ''),
                ))
    except Exception:
        pass

    return PredictionResponse(
        prediction=len(findings) > 0,
        vulnerabilities=findings,
    )


# ─── Run Simulation ──────────────────────────────────────────────────

def run_simulation(n_challenges: int = 10):
    """Run BitSec simulation with exact on-chain format."""
    print(f"=== BitSec LOCAL SIMULATION ({n_challenges} challenges) ===\n")

    # Load clean code from ScaBench repos
    code_samples = []
    for root, dirs, files in os.walk("/root/bitt/data/scabench-repos"):
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'target']]
        for f in files:
            if f.endswith('.sol'):
                fp = os.path.join(root, f)
                try:
                    content = open(fp).read()
                    if 200 < len(content) < 3000:
                        code_samples.append(content)
                except:
                    pass
            if len(code_samples) >= 30:
                break
        if len(code_samples) >= 30:
            break

    # Fallback synthetic code
    if not code_samples:
        code_samples = ["""pragma solidity ^0.8.0;
contract Vault {
    mapping(address => uint256) public balances;
    function deposit() public payable { balances[msg.sender] += msg.value; }
    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success);
        balances[msg.sender] -= amount;
    }
}"""] * 5

    print(f"Using {len(code_samples)} code samples")

    # Distribute challenges across categories
    categories = list(VulnerabilityCategory)
    results = []

    for i in range(n_challenges):
        cat = categories[i % len(categories)]
        code = code_samples[i % len(code_samples)]

        print(f"\nChallenge {i+1}/{n_challenges}: {cat.value}")

        # Generate challenge
        print("  Generating...", end=" ", flush=True)
        challenge = generate_challenge(code, cat.value)
        print(f"OK")

        # Run miner
        print("  Mining...", end=" ", flush=True)
        response = miner_analyze(challenge["vulnerable_code"])
        found_cats = [v.category for v in response.vulnerabilities]
        print(f"Found {len(response.vulnerabilities)} vulns")

        # Score with Jaccard
        expected = [challenge["expected_category"]]
        found = found_cats
        score = jaccard_score(expected, found)

        results.append({
            "challenge": i + 1,
            "category": cat.value,
            "expected": expected,
            "found": found,
            "score": score,
            "prediction": response.prediction,
            "n_vulns": len(response.vulnerabilities),
        })

        print(f"  Expected: {expected}")
        print(f"  Found: {found[:3]}")
        print(f"  Jaccard: {score:.3f}")
        print(f"  {'HIT' if score > 0 else 'MISS'}")

    # Summary
    scores = [r['score'] for r in results]
    hits = sum(1 for r in results if r['score'] > 0)

    print(f"\n{'='*50}")
    print(f"SIMULATION RESULTS ({n_challenges} challenges)")
    print(f"{'='*50}")
    print(f"Average Jaccard: {sum(scores)/len(scores):.3f}")
    print(f"Detection rate: {hits}/{n_challenges} = {hits/n_challenges:.1%}")
    print(f"\nPer category:")
    for r in results:
        print(f"  {r['category'][:30]:30} | Jaccard={r['score']:.3f} | {'HIT' if r['score'] > 0 else 'MISS'}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()
    run_simulation(args.n)
