# Multi-Agent Results — What We Learned

## The Experiment

Phase 1 (single-agent): 104 vulns, 0% matched ground truth
Phase 2 (multi-agent): 28 vulns, 0% matched ground truth

Both approaches find REAL vulnerabilities. Neither finds the RIGHT ones.

## Why

The ground truth contains **business logic bugs**:
- "createPoolD650E2D0 mismatch between Solidity and Stylus" — requires understanding the protocol's pool creation mechanism
- "Users incorrectly refunded when liquidity is insufficient" — requires understanding the refund math
- "No slippage control when withdrawing" — requires understanding withdrawal invariants

Our agent finds **implementation bugs**:
- "Storage Collision in Proxy Pattern" — real, but not what auditors found
- "Reentrancy in _onTransferReceived" — real, but not what auditors found
- "Access control bypass in transferFrom" — real, but not what auditors found

The gap is: **understanding the business rules well enough to find their violations.**

## What Would Actually Work

The model needs to:
1. Read the protocol documentation/README
2. Understand the intended business invariants
3. Find code paths that violate those invariants
4. Report specific instances with exact function/line

This requires a **business logic analysis** pass before the vulnerability hunt. Something like:

```
Agent 0: ProtocolReader
- Read README, docs, comments
- Extract: what does this protocol do? what are the invariants?
- Output: list of "the protocol guarantees X" statements

Agent 1: InvariantChecker  
- For each invariant from Agent 0
- Trace the code paths that implement it
- Find paths where the invariant could be violated
- Output: specific vulnerability findings
```

This is fundamentally different from pattern-matching for common vulnerability types.

## The Honest Question

Is mimo-v2.5 capable of this level of reasoning? The research says:
- LLM-SmartAudit (GPT-4o based): 47.6% on real-world vulns
- VulTrial (GPT-4o based): 81 P-C score
- Current best: Claude achieves 23% on C/C++ vulnerability detection

The state of the art is ~48% on real-world projects with GPT-4o-class models. Getting to 80% with mimo-v2.5 may not be realistic for business logic bugs.

## What IS Realistic

1. **Implementation bugs** (reentrancy, access control, overflow) — our agent finds these well
2. **Architecture issues** (proxy patterns, cross-contract risks) — the multi-agent approach finds these
3. **Business logic bugs** — this is the hard part, may require a more capable model

## Recommendation

1. Accept that 80% DR on ScaBench may not be achievable with mimo-v2.5
2. Focus on what mimo-v2.5 IS good at: implementation-level security review
3. Position the agent as a "first pass" that catches common issues, not a replacement for human auditors
4. Test on a different benchmark that focuses on implementation bugs rather than business logic
5. Or: try with a more capable model (GPT-4o, Claude) for the business logic analysis pass
