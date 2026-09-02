# Final Session Review — 2026-09-02

**Session:** ~6 hours across bitt, qdw-workbench, aisec
**Repos:** prx0r/bitt, prx0r/qdw-workbench, prx0r/cg, prx0r/aisec

---

## What Actually Works (Verified)

### The Learning Loop (Partial)

```
BitSecWorld (CG kernel)
  → reset(instance_id, seed) → ScaBench project + hidden ground truth
  → observe(state) → code (no ground truth)
  → actions(state) → FIND_VULNERABILITIES, SUBMIT_FINDINGS
  → apply(state, action, result) → state transitions
  → score(state) → 9 metrics (DR, F1, precision, TP, FP, FN)
  → CG RunReceipt (worldpack, scenario, seed, metrics)
      ↓
BitSec Bridge
  → RunSpec (frozen contract)
  → EvaluationResult (9 dimensions)
  → RunReceipt (frozen contract)
  → Finding contracts (tier system)
  → Ledger events (3 per run, append-only, chain-hashed)
  → HydraDB projection (derived, rebuildable)
      ↓
CGE (proposes mutations) ← NOT WIRED
  → LearningProposal ← NOT PRODUCED
      ↓
CG (paired evaluation) ← NOT RUN
  → ExperimentResult ← NOT PRODUCED
  → REJECT / PROMOTE ← NOT TESTED
```

### Real Execution Results

| Project | Vulns | DR | F1 | TP | FP | Duration | Executor |
|---------|-------|-----|-----|----|----|----------|----------|
| Fenix Finance | 15 | 20.0% | 0.300 | 3 | 2 | 11.9s | WorkerKit |
| Coded Estate | 33 | 0.0% | 0.000 | 0 | 0 | 0.0s | (code issue) |
| Fenix Finance | 15 | 33.3% | 0.270 | 5 | 17 | 104.2s | direct CF |

**Key finding:** WorkerKit's PydanticBATSHarness produces real results (20% DR on Fenix Finance). The direct CF call also works (33.3% DR but more false positives).

### Infrastructure That Works

| Component | Status | Proof |
|-----------|--------|-------|
| HydraDB | ✅ LIVE | Docker container running, 30+ runs projected |
| Ledger | ✅ REAL | Append-only, chain-hashed, events recorded |
| Contracts | ✅ FROZEN | 23+ Pydantic models, schema_version 1.0.0 |
| WorkerKit executor | ✅ REAL | PydanticBATSHarness makes real LLM calls |
| CG World | ✅ REAL | BitSecWorld registered, deterministic reset |
| RunEvaluator | ✅ REAL | 9 dimensions scored |
| Finding tiers | ✅ REAL | OBSERVATION / STUDIO_FINDING |
| Pool knowledge | ✅ EXISTS | Doctrine + skills in lab/pools/security/ |

---

## What's Still Missing (vs Emails)

### Critical Gaps

1. **CGE not wired** — CGE doesn't read failures from Ledger, doesn't propose mutations
2. **Paired evaluation not run** — v0 vs v1 on sealed tasks never tested
3. **Promotion gate not tested** — ExperimentResult → REJECT/PROMOTE never exercised
4. **Code loading broken** — Some ScaBench projects get truncated code
5. **Letta not connected** — Worker identity exists but no persistent agent
6. **Transfer detection not run** — Code exists, never called
7. **BATS experiment not run** — F/M/Q comparison never tested

### What Emails Require vs What Exists

| Email Requirement | Status | Gap |
|------------------|--------|-----|
| CGE reads failures | ❌ | No failure analysis pipeline |
| CGE proposes mutations | ❌ | No LearningProposal production |
| CG sealed evaluation | ❌ | No ExperimentResult production |
| Promotion gate | ❌ | No PromotionReceipt linked to evidence |
| Letta worker identity | ⚠️ | Client exists, not connected |
| ContextPack compilation | ⚠️ | Structure exists, not wired to runs |
| BATS budget experiment | ❌ | F/M/Q comparison not implemented |
| Transfer detection | ❌ | Code exists, never called |
| External trajectory import | ⚠️ | 3 sources imported, not used in learning |

---

## Bottom Line

**The execution pipeline is real.** WorkerKit makes actual LLM calls, produces real findings, records to Ledger, projects to HydraDB. Fenix Finance: 20% DR through WorkerKit.

**The learning loop is broken.** CGE doesn't read failures, doesn't propose mutations, doesn't run paired evaluations. The loop stops at "run completed" — nothing learns.

**Next session must:**
1. Wire CGE to read failure clusters from Ledger
2. CGE proposes ONE mutation at a time
3. CG runs paired evaluation (v0 vs v1 on sealed tasks)
4. Record ExperimentResult
5. Test promotion gate

That's the one thing that makes everything else real.
