# Real Execution Review — 2026-09-02 (final)

**What just happened:** Ran real BitSec execution through the CG → qdw-workbench loop. Got actual results.

---

## Real Results

| Project | Vulns | TP | FP | DR | F1 | Duration |
|---------|-------|----|----|-----|-----|----------|
| Coded Estate | 33 | 0 | 0 | 0.0% | 0.000 | 0.2s |
| Fenix Finance | 15 | 5 | 17 | 33.3% | 0.270 | 104.2s |
| Superposition | 11 | 0 | 0 | 0.0% | 0.000 | 0.0s |

**Fenix Finance is real:** 5 out of 15 specific vulnerabilities found by mimo-v2.5 with pool knowledge. The model actually found real issues (reentrancy, access control, etc.) and matched them against ground truth.

**The other two failed** because:
- Coded Estate: code too large, truncated before vulnerable functions
- Superposition: CG executor didn't get called (timing bug in code loading)

---

## What Emails Require vs What Exists

### From Email 1 (Architecture):

| Requirement | Status | Notes |
|------------|--------|-------|
| ONE Lab with multiple Studios | ✅ | qdw-workbench has Studio concept |
| Frozen Pydantic contracts | ✅ | 23+ models in lab/contracts |
| Append-only ledger | ✅ | SQLite WAL with chain hashing |
| Content-addressed artifacts | ✅ | SHA-256 CAS |
| Hydra as derived projection | ✅ | Rebuildable from ledger |
| Worker/WorkerVersion lineage | ✅ | WorkerRegistry + Git SourceRef |
| ContextPack with trust tiers | ⚠️ | Structure exists, not wired to BitSec runs |
| 5 knowledge tiers | ⚠️ | Defined, not enforced |
| CG as sole promotion evaluator | ⚠️ | CG integration exists but not tested |
| CGE as curriculum generator | ⚠️ | CGE integration exists but not tested |
| Letta for worker identity | ⚠️ | Letta client exists but not connected |
| BATS budget experiment | ❌ | Not implemented |
| Dashboard with 9 tabs | ⚠️ | Tauri scaffold exists |

### From Email 2 (Testing):

| Requirement | Status | Notes |
|------------|--------|-------|
| Fail closed on errors | ✅ | DATASET_UNAVAILABLE pattern |
| Every component gets broken test | ⚠️ | 29 unit tests, not chaos tests |
| Letta cannot mutate scientific state | ⚠️ | Not tested |
| Hydra rebuildable from canonical history | ✅ | CRITICAL TEST PASSED |
| WorkerVersions from Git + contracts | ⚠️ | Structure exists, not validated |
| Only sealed evidence promotes | ⚠️ | ExperimentLifecycle exists, not tested |
| Real BitSec vertical integration | ✅ | Just ran it — 33.3% DR on Fenix |
| Paired CG experiment | ❌ | Not run yet |

### From Email 3 (Security Specialization):

| Requirement | Status | Notes |
|------------|--------|-------|
| Security capability pool | ⚠️ | Structure exists, not populated |
| External intelligence ingest | ✅ | 3 sources imported (Arcanum, AgentDojo, ATBench) |
| ExternalTrajectory ≠ RunReceipt | ✅ | Separate Pydantic models |
| Trace2Skill pipeline | ❌ | Not implemented |
| Contamination control | ⚠️ | Splits defined, not enforced |
| No fake learning | ✅ | No `if score > prev: write memory` |

---

## What's Real Now

1. **CG World works** — BitSecWorld provides deterministic ScaBench episodes
2. **CG Runner works** — AsyncRunner executes episodes, produces RunReceipts
3. **Bridge works** — CG RunReceipt → qdw-workbench contracts
4. **Ledger works** — Events recorded with chain hashing
5. **HydraDB works** — Projections survive (30 runs now)
6. **Real detection** — 33.3% DR on real ScaBench project (Fenix Finance)
7. **Real scoring** — 9-dimensional RunMetrics, not collapsed scalar

---

## What's Still Broken

1. **Code loading** — some projects get truncated, no findings
2. **Executor timing** — CG executor doesn't always get called
3. **Scoring** — title-based matching misses findings with different wording
4. **CGE loop** — not wired: CGE doesn't read failures, doesn't propose mutations
5. **Paired evaluation** — not run: v0 vs v1 on sealed tasks
6. **Pool knowledge** — loaded but not injected (made performance worse)
7. **Transfer detection** — code exists, never called
8. **Letta** — client exists, not connected

---

## Next Session Priority

1. Fix code loading (ensure all projects get full code)
2. Fix executor timing (ensure LLM always gets called)
3. Wire CGE to read failures from Ledger
4. Run one paired evaluation (v0 vs v1 on sealed tasks)
5. That's the loop. Everything else is refinement.
