# mw-audit-v1 Performance Analysis — Superposition Audit

**Project:** code4rena_superposition_2025_01  
**Agent:** mw-audit-v1  
**Model:** mimo-v2.5  
**Date:** 2026-09-04  

---

## 1. Detection Rate vs Ground Truth

| Metric | Value |
|--------|-------|
| Ground truth (expected) | 11 |
| Findings in reasoning | 3 |
| Findings submitted | 1 (2 in superposition-findings.json) |
| True positives (submitted) | 1 |
| Detection rate (reasoning) | 27.3% (3/11) |
| Detection rate (submitted) | 9.1% (1/11) |
| WINNER baseline DR | 81.8% (9/11) |

**Gap: 72.7 percentage points below the WINNER.**

---

## 2. What the Agent Found (3 Real Vulnerabilities)

### Finding 1 — Inverted ERC721 onERC721Received selector (SUBMITTED)
- **File:** `pkg/sol/OwnershipNFTs.sol:93`
- **Severity:** Critical
- **Bug:** `require(data != selector)` should be `require(data == selector)`
- **Impact:** Bricks safeTransferFrom to legitimate contract recipients; allows transfers to incompatible contracts, permanently locking NFT positions
- **Status:** Submitted and correct

### Finding 2 — Stale Approval Persistence After Transfer (NOT SUBMITTED)
- **File:** `pkg/sol/OwnershipNFTs.sol:109-116`
- **Severity:** Critical
- **Bug:** `getApproved[_tokenId]` never cleared in `_transfer()`. Previous approvee retains access after position transfer
- **Impact:** Attacker who was approved can steal positions from new owners
- **Loss reason:** "Identified in reasoning but not reported in tool call"

### Finding 3 — calc_base_rewards Formula Inversion (NOT SUBMITTED)
- **File:** `pkg/leo/src/seawater.rs`
- **Severity:** Critical
- **Bug:** Uses `pool_lp * per_second / user_lp` instead of `user_lp * per_second / pool_lp`. Inverts reward distribution.
- **Impact:** Users with LESS liquidity get MORE rewards; inflates payouts beyond campaign rate
- **Loss reason:** "Truncated before report_vulnerabilities call" (finish_reason: length)

---

## 3. Root Cause Analysis — Why 2 of 3 Were Lost

### Root Cause A: Report tool not invoked for Finding 2
The agent identified the stale approval bug in its reasoning chain but never called `report_vulnerabilities` for it. The finding sat in the agent's "thinking" without being serialized to a submission.

**Cause:** The agent batches findings for later reporting but loses them when the session ends or context window shifts. No explicit "report all found so far" checkpoint.

### Root Cause B: Token truncation killed Finding 3
The `calc_base_rewards` inversion was identified but the response was truncated at the token limit (`finish_reason: length`). The report call never completed.

**Cause:** Agent spent too many tokens on detailed analysis of earlier findings, leaving insufficient budget for the final submission.

### Combined Diagnosis
The agent's pipeline has a **reasoning-to-report gap**. It finds vulnerabilities in its thinking but fails to reliably move them through the `report_vulnerabilities` tool call. Two distinct failure modes:

```
Findings discovered:  3
     ↓
Reasoning captured:   3  (100%)
     ↓
Report calls made:    6  (but only 2 non-empty)
     ↓
Submitted to server:  1  (33% of found, 9% of ground truth)
```

---

## 4. Comparison with WINNER Approach

| Aspect | mw-audit-v1 | WINNER (two-round-specific) |
|--------|-------------|----------------------------|
| Method | Single long reasoning | 2 focused rounds + merge |
| Inference calls | 477 | ~12 (6 per round) |
| Findings submitted | 1 | 9 |
| DR | 9.1% | 81.8% |
| F1 | ~0.15 | 0.818 |
| Token efficiency | Very low | High |

The WINNER works because it uses **structured, bounded prompts** — each round asks for a specific set of vulnerability types, and results are merged. The agent doesn't need to maintain context across a 477-call marathon.

---

## 5. Recommended Improvements

### Priority 1 (Critical — Fixes submission bottleneck)
- **Add periodic report checkpoints.** Every N findings or M inference calls, force a `report_vulnerabilities` call. Don't accumulate all findings until the end.
- **Implement a "report-all" flush at context budget 80%.** When approaching token limit, dump everything found so far into a report call before truncation.

### Priority 2 (High — Improves detection rate)
- **Adopt two-round structure.** Round 1: scan for common vuln types (reentrancy, access control, logic errors). Round 2: scan for domain-specific vulns (AMM math, position management). Merge results.
- **Reduce per-finding token spend.** The agent wrote 500+ tokens per finding description. Cap at 150 tokens per finding; save detail for the report call.

### Priority 3 (Medium — Reduces wasted compute)
- **477 inference calls is absurd.** The WINNER used ~12 calls and found 9x more. Implement early stopping — if no new findings in last 10 calls, terminate and report.
- **Dedup before report, not after.** Track finding hashes in a set; skip duplicate analyses.

### Priority 4 (Low — Polish)
- **Severity calibration.** The agent marked Finding 1 as "high" in one file and "critical" in another for the same bug. Be consistent.
- **Ground truth gap analysis.** The agent only analyzed 3 files deeply. The project has 57 Solidity files. Broaden the scan surface.

---

## 6. Priority Fix Summary

| Priority | Fix | Expected Impact |
|----------|-----|-----------------|
| P1 | Report checkpoints every 5 findings | +1 submitted per checkpoint |
| P1 | Flush at 80% context budget | Prevents truncation loss |
| P2 | Two-round scan structure | +6 findings (based on WINNER) |
| P2 | Cap finding descriptions at 150 tokens | 3x more findings fit in budget |
| P3 | Early stopping after 10 empty calls | Saves ~400 inference calls |
| P3 | Dedup via finding hash set | Eliminates duplicate analysis |
| P4 | Broader file coverage | Catches more of the 11 ground truth |

---

## 7. Bottom Line

**The agent CAN find vulnerabilities.** It identified 3 real critical bugs, including an inverted ERC721 check and a reward formula inversion. But it submitted only 1 of 3, yielding a 9.1% detection rate vs the WINNER's 81.8%.

The bottleneck is not detection — it's **submission pipeline reliability**. Fix the reasoning-to-report gap (P1), adopt structured scan rounds (P2), and cut token waste (P3), and this agent should reach 50-70% DR on comparable projects.
