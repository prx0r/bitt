# Contrastive Auditing — Goals & Implementation Plan

## The Goal

**Find ALL high/critical vulnerabilities in all 6 official BitSec projects.**

Score is binary per project: find every single one or score 0. Target: 83.3% (15/15 projects).

## The Approach

**Contrastive Auditing** (from LogicScan, Feb 2026):
- Mature protocols encode well-tested business invariants
- Compare target against reference implementations
- Detect missing invariants = vulnerabilities

## Proof of Concept ✓

We proved this works on crestal-network:
- Found the ground truth vulnerability in 35 seconds
- 1/1 high/critical vulns detected
- Approach: pattern match → contrastive compare → verify

## The 6 Official Projects

| Project | High/Critical Vulns | Language | Status |
|---------|---------------------|----------|--------|
| coded-estate | 9 | CosmWasm/Rust | Pending |
| iq-ai | 9 | Solidity | Pending |
| liquid-ron | 5 | Solidity | Pending |
| mantra-dex | 55 | CosmWasm/Rust | Pending |
| cork-protocol | 18 | Solidity | Pending |
| crestal-network | 1 | Solidity | **PASSED** ✓ |

## Implementation Plan

### Phase 1: Reference Pool (Now)
Build reference implementations for common DeFi patterns:
- Payment processing (ERC20 transfers)
- Token approval patterns
- Access control patterns
- Lending/borrowing invariants
- DEX swap patterns
- NFT marketplace patterns

### Phase 2: Autonomous Pipeline (Next)
Run contrastive auditor on all 6 projects:
1. For each project, identify all entry points
2. For each entry point, retrieve relevant reference patterns
3. Compare target against references
4. Verify findings
5. Report results

### Phase 3: Scale & Iterate
- Add more reference patterns based on failures
- Optimize prompts for each project type
- Build knowledge graph of recurring patterns
- Achieve consistent DR across all projects

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Projects passed | 5/6 | 1/6 |
| High/critical DR | 100% per project | 100% on crestal |
| Time per project | <10 minutes | 35s on crestal |
| False positive rate | <20% | TBD |

## Key Files

| File | Purpose |
|------|---------|
| `contrastive-v1/agent_v3.py` | Working prototype |
| `data/contrastive-audit-crestal-v3.json` | Proof of concept result |
| `data/reference-patterns/` | Secure reference implementations |
