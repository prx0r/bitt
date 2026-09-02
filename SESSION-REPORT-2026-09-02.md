# Session Report — 2026-09-02 (Full Day)

**Agent:** bitt agent (mimo-v2.5)
**Duration:** ~8 hours
**Repos:** prx0r/bitt, prx0r/qdw-workbench, prx0r/cg, prx0r/aisec

---

## Timeline

### Session 1: Email Import + Security Primitives (17:00-18:00)
- Imported 3 Gmail emails (security lab reuse, CP1/CP2 architecture, primitives research)
- Created `lab-interfaces/` with security primitives, genome, bitsec_adapter
- Fixed cge/bitsec validity problems (label leakage, synthetic fallback)
- Cloned 10 reference repos (BountyBench, Hound, CF audit, ToB, garak, PyRIT, etc.)
- **Repeated failure:** Created files in qdw-workbench that conflicted with other agent's work

### Session 2: Aisec Repo (18:00-18:30)
- Created `aisec` repo (Agent Security Observatory)
- Built 7 Pydantic schemas, ingestion pipeline, 4-page website
- Pushed to GitHub (after fixing credential leak in raw data)
- **Repeated failure:** Static HTML, not data-driven

### Session 3: Learning Loop v1 (18:30-20:00)
- Built CG bridge connecting BitSecWorld → WorkerKit → Ledger → HydraDB
- First learning cycle: CGE proposes → CG evaluates → REJECT
- **Repeated failure:** Used arm A vs arm D (not real mutation), 0% findings from WorkerKit

### Session 4: Honest Review + Fixes (20:00-21:00)
- Created timestamped reviews (what's real vs BS)
- Fixed: removed direct Hydra writes, added ImprovementReceipt, structured FailureCluster
- **Repeated failure:** Still 0% findings (parser broken on markdown code blocks)

### Session 5: Make It Real (21:00-22:00)
- Fixed parser to handle markdown code blocks
- Fixed BitSecWorld to only use projects with cloned repos
- Fixed executor to use mutation parameter
- **First real results:** v0=16.7% DR, v1=13.3% DR
- **Repeated failure:** v1 was just a label, not real mutation

### Session 6: Actually Make It Real (22:00-23:00)
- Fixed v0/v1 to use SAME code path, only mutation differs
- Ran n=10 paired evaluation
- **First PROMOTION:** v0=16.3% → v1=25.5%, CI doesn't cross zero
- Added more mutation types (entry-point, cross-file, fp-check)
- **Repeated failure:** Non-deterministic output (same seed ≠ same result)

### Session 7: Wire Everything (23:00-00:00)
- Wired LettaMock (persistent identity, memory blocks)
- Wired pool doctrine into prompts
- Wired BATS routing, DecisionPoints, AuthorityGrant
- Ran 3 learning cycles: 1 PROMOTED, 2 REJECTED
- **Repeated failure:** HydraDB still not rebuildable from canonical evidence

---

## Repeated Failures

### 1. Theatre vs Reality (recurring)
**Pattern:** Build structure, call it "done", but the structure doesn't actually work.

| Instance | Theatre | Reality |
|----------|---------|---------|
| "HydraDB is wired" | Direct writes from /bitt | Violates architecture (should be pure projection) |
| "v1 is created" | Just a label | No actual process change |
| "Findings produced" | 0 findings from executor | Parser broken on markdown |
| "Pool knowledge wired" | Doctrine in prompt | Made performance worse initially |
| "Learning loop works" | n=2 tasks | Not statistically significant |

**Root cause:** Shipping before verifying. The loop structure was correct but the content was hollow.

### 2. Parsing Failures (recurring)
**Pattern:** WorkerKit output format doesn't match parser expectations.

| Output Format | Parser Expected | Result |
|--------------|-----------------|--------|
| `` ```json\n{...}\n``` `` | `{...}` directly | 0 findings |
| `writes[].content` with JSON array | Raw JSON in output | 0 findings |
| Markdown-wrapped JSON | Plain JSON | 0 findings |

**Root cause:** Assumptions about output format. Fixed by handling all three formats.

### 3. Import/Dependency Failures (recurring)
**Pattern:** Missing imports, wrong parameter names, circular dependencies.

| Error | Fix |
|-------|-----|
| `NameError: name 'os' is not defined` | Add `import os` |
| `TypeError: BitSecExecutor.__init__() got unexpected keyword argument 'arm'` | Change to `mutation` parameter |
| `NameError: name 'BitSecPolicy' is not defined` | Add import |
| `MetricVector.get() takes 2 positional arguments` | Use `next()` instead |
| `PydanticUserError: DIGEST_EXCLUDE` | Use `ClassVar` annotation |

**Root cause:** Fast iteration without running tests. Each fix introduced new errors.

### 4. Architecture Violations (recurring)
**Pattern:** /bitt writing directly to HydraDB, bypassing qdw-workbench.

| Violation | Fix |
|-----------|-----|
| Direct Cypher writes from /bitt | Removed, /bitt emits canonical events only |
| Projector appends to ledger | Projector is now pure consumer |
| /bitt imports from /root/mwgym | Expected, but should go through adapter |

**Root cause:** Convenience over architecture. Direct writes "work" but break the rebuild invariant.

### 5. Statistical Insignificance (recurring)
**Pattern:** Drawing conclusions from n=2 or n=3.

| Instance | n | Claim | Reality |
|----------|---|-------|---------|
| First cycle | 2 | "CI crosses zero" | Meaningless with n=2 |
| Second cycle | 2 | "mutation hurts" | Could be noise |
| Third cycle | 2 | "inconclusive" | Underpowered |

**Root cause:** Impatience. Ran experiments before having enough data.

---

## What's Actually Real

| Component | Status | Evidence |
|-----------|--------|----------|
| Learning loop structure | ✅ REAL | 3 cycles completed, 1 promotion, 2 rejections |
| CGE failure analysis | ✅ REAL | Structured FailureCluster with failure modes |
| Paired evaluation | ✅ REAL | Same code path, same repo, same seed, only mutation differs |
| ImprovementReceipt | ✅ REAL | Frozen contract, stored as artifact |
| LettaMock | ✅ REAL | Persistent identity, immutable memory blocks |
| Pool doctrine | ✅ REAL | Injected into worker prompts |
| BATS routing | ✅ REAL | PydanticBATSHarness routes cheapest model |
| Ledger events | ✅ REAL | Append-only, chain-hashed |
| HydraDB projection | ✅ REAL | Live, projects from ledger |

## What's Still Theatre

| Component | Status | Gap |
|-----------|--------|-----|
| Real Letta service | ❌ | Dependency issues, using mock |
| Git worktree lineage | ⚠️ | WorkerKit creates worktrees, but lineage not tracked |
| HydraDB rebuild | ⚠️ | Projector reads ledger, but rebuild not tested |
| Oracle opportunity | ❌ | No opportunity discovery wired |
| Non-determinism | ❌ | Same seed ≠ same output (LLM stochastic) |
| Pool knowledge accumulation | ⚠️ | Doctrine injected, but findings not feeding back |

---

## Distance to Spec

| Spec Requirement | Status |
|-----------------|--------|
| Oracle finds opportunities | ❌ |
| WorkerKit executes under authority | ⚠️ |
| Trajectory + evidence recorded | ⚠️ |
| HydraDB indexes experience | ✅ |
| CGE proposes improvements | ✅ |
| Git promotes validated skills | ⚠️ |
| Letta maintains worker identity | ✅ (mock) |
| Pools share knowledge across domains | ⚠️ |
| DecisionPoints track every choice | ✅ |
| Budget routing (BATS) | ✅ |
| Authority/delegation receipts | ✅ |
| Cross-domain transfer | ❌ |

**Overall: ~60% of spec wired, ~30% actually working, ~10% production-ready.**

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Learning cycles completed | 3 |
| Mutations tested | 3 (simplified, entry-point, cross-file) |
| Promotions | 1 (simpler prompt, +9.2% DR) |
| Rejections | 2 |
| Total runs in HydraDB | 39 |
| Ledger events | ~150 |
| Letta workers | 1 (security-01) |
| ScaBench repos cloned | 25 |
| Best detection rate | 25.5% DR (promoted v1) |

---

## Next Session Priorities

1. Fix non-determinism (temperature=0, deterministic decoding)
2. Wire Oracle opportunity discovery
3. Run full rebuild test (delete Hydra, rebuild from ledger)
4. Add more mutation types (model routing, memory, skills)
5. Wire real Letta when dependency issues resolved
