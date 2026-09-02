# DEV PLAN — CHECKPOINT 1: BitSec as First World

**Date:** 2026-09-01
**Source:** Email thread "work for bitt agent" + "bitt agent security architectures"
**Status:** Active

---

## Goal

> Discover which existing security methods, tools, memories, models and workflows actually produce a better `security-01` under controlled evaluation.

NOT "make our BitSec prompt better." The object is a **general laboratory for measurable autonomous learning**. BitSec is the first world.

---

## Architecture

```
PRIVATE LAB
    │
WorkerKit
    │
security-01 / WorkerVersion v0
    │
BitSec StudioAdapter
    │
TRAIN / DEV / VALIDATION / SECRET
    │
worker executes
    │
findings.json
    │
BitSec evaluator
    │
EvaluationResult
    │
RunReceipt
    │
Hydra
    │
failure clusters
    │
CGE proposes v1
    │
CG compares v0 vs v1 on sealed tasks
    │
REJECT or PROMOTE
    │
official BitSec local/Docker evaluation
    │
Bittensor submission
    │
rank / score / TAO
    │
ExternalOutcomeReceipt
```

## Universal Loop

```
TaskInstance
  ↓
RunSpec
  ↓
WorkerVersion + BudgetEnvelope + ContextPack
  ↓
fresh execution episode
  ↓
artifact/findings
  ↓
domain evaluator
  ↓
EvaluationResult
  ↓
RunReceipt
  ↓
Hydra projection
  ↓
failure analysis
  ↓
LearningProposal
  ↓
CGE candidate generation
  ↓
candidate WorkerVersion
  ↓
CG sealed paired evaluation
  ├─ FAIL → reject
  └─ PASS → promote WorkerVersion n+1
```

## Granularity

```
Program → Campaign → Run
```

- `/bitt` owns the BitSec **program**.
- Private Lab coordinates the **campaign** and worker lineage.
- WorkerKit/MWGym owns individual **runs**.

---

## Process Arms Experiment (THE key CP1 experiment)

| Worker candidate | Process | Source |
| ---------------- | ------- | ------ |
| A | current Moltwork Scout/Strategist | existing |
| B | Hound unchanged | hound@latest |
| C | Cloudflare security-audit skill | cloudflare-audit@latest |
| D | Trail of Bits smart-contract stack | trail-of-bits-skills@latest |
| E | CGE-generated hybrid | CGE proposes |

**Protocol:**
1. Run A–D under **equal budgets** on ScaBench/BitSec DEV
2. CGE reads the failures
3. CGE proposes E (one falsifiable mutation at a time)
4. CG tests A vs E on **sealed tasks**
5. That's a proper experiment

**CGE search space becomes compositional:**
```yaml
ProcessCandidate:
  recon_policy: true
  hound_graph: [authorization, value_flow]
  static_tools: [slither, semgrep]
  audit_skills: [entry-point-analyzer, fp-check, audit-context-building]
  property_testing: echidna
  scout_model: cheap
  strategist_model: strong
  verifier_model: independent
  context_retrieval: sec-context
  stopping_policy: budget-based
```

---

## Implementation Steps

### Phase 1: Create Worker + Freeze v0
1. Create one persistent worker: `security-01`
2. Freeze immutable `security-01/v0` with exact:
   - Model policy
   - Prompts/processes
   - Tools
   - Memory revision
   - Context policy
   - Source commits
   - Evaluator version

### Phase 2: BitSec StudioAdapter
3. Implement thin `BitsecStudioAdapter`
4. Build explicit TRAIN / DEV / VALIDATION / SECRET splits
5. **Fail closed**: `DATASET_UNAVAILABLE` if ScaBench unavailable — no silent synthetic fallback

### Phase 3: WorkerKit Runs
6. Run v0 through **real WorkerKit runs**, not standalone experiment scripts
7. Store every run as: `RunSpec → ContextPack → execution → Artifact → EvaluationResult → RunReceipt`

### Phase 4: Hydra/CGE Integration
8. Let Hydra/CGE consume TRAIN/DEV failures only
9. CGE proposes **one falsifiable mutation at a time**
10. Materialize as `security-01/v1` — **do not mutate v0 in place**

### Phase 5: Paired Evaluation
11. CG performs paired v0 vs v1 evaluation on **same sealed tasks and budgets**
12. Reject failed changes and preserve the evidence
13. Promote only successful changes

### Phase 6: Official Evaluation + Submission
14. Use official BitSec local/Docker path
15. Optionally submit through `/bitt`
16. Store Bittensor score/rank/TAO as **external outcomes**, never as retrospective evaluator truth

---

## Validity Fixes (from email)

These current `cge/bitsec` scripts are useful experiments but should NOT count as learning evidence:

| Problem | Fix |
|---------|-----|
| `evolution.py` / `experiment.py` sample from known ground truth | Keep only as unit simulations |
| `real_eval.py` supplies expected vulnerability info to model | Label leakage. Fine for TRAIN teacher diagnostics, never CG/SECRET evidence |
| `world.py` silently falls back to synthetic data | Production must fail closed: `DATASET_UNAVAILA` |
| Homemade approximate scoring as authority | Wrap and pin official BitSec evaluation path |
| Mock/heuristic evaluator generating CapabilityClaims | Never. No mock evaluator should generate promotion or dashboard claims |

---

## HydraDB Graph Model for CP1

```cypher
// Worker + version
CREATE (w:Worker {id: hash_id("security-01")})-[:HAS_VERSION]->(v:WorkerVersion {id: hash_id("security-01/v0")})

// Run
CREATE (r:Run {id: hash_id("run-001")})-[:RAN]->(w)
CREATE (r)-[:IN_STUDIO]->(s:Studio {id: hash_id("bitsec")})

// Finding
CREATE (f:Finding {id: hash_id("finding-001")})-[:CREATED]->(r)
CREATE (f)-[:VALID_IN]->(s)

// Experiment
CREATE (e:Experiment {id: hash_id("exp-v0-vs-v1")})-[:PART_OF]->(w)
CREATE (e)-[:SUPPORTED_BY]->(r)
```

---

## Pass Criteria

- [ ] security-01/v0 runs on real BitSec tasks via WorkerKit
- [ ] RunReceipts stored in HydraDB
- [ ] CGE proposes v1 from TRAIN/DEV failures
- [ ] CG compares v0 vs v1 on sealed tasks
- [ ] One successful promotion (v0 → v1) with evidence
- [ ] No label leakage, no silent synthetic fallback
- [ ] Official BitSec evaluator used for final scoring
- [ ] External outcome (score/rank/TAO) recorded separately

---

## What NOT to do

- Don't combine everything immediately (cheat so enthusiastically we can't tell what helped)
- Don't let mock evaluators generate production claims
- Don't overwrite v0 in place — materialize new versions
- Don't use Bittensor score as evaluator truth — it's an external outcome
- Don't bolt every good tool into v0 — make them experimental arms first
