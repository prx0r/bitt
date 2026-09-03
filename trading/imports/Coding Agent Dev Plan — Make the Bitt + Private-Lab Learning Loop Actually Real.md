# Coding Agent Dev Plan — Make the Bitt + Private-Lab Learning Loop Actually Real

**Date:** Tue, 1 Sep 2026 22:27:28 -0400

---

# Coding Agent Directive — Bitt / Private-Lab CP1

**Date:** 2 Sep 2026  
**Repos reviewed:** `prx0r/bitt`, `prx0r/qdw-workbench`, `prx0r/mw`  
**Primary objective:** stop expanding scope and make **one scientifically valid autonomous learning loop** work end-to-end.

## Mission

The system is successful when this exact chain is real, replayable and auditable:

```text
frozen WorkerVersion v0
  -> deterministic ContextPack + real BitSec TaskInstance
  -> WorkerKit execution (one canonical execution path)
  -> real authoritative BitSec/ScaBench evaluation
  -> immutable trajectory + artifacts + RunReceipt
  -> append-only canonical ledger
  -> rebuildable HydraDB projection
  -> CGE failure analysis
  -> one LearningProposal
  -> immutable candidate WorkerVersion v1
  -> sealed paired CG experiment on fixed tasks/seeds/budgets
  -> ExperimentResult
  -> deterministic REJECT or PromotionReceipt
  -> if promoted, v1 becomes the next frozen worker version
```

Nothing else matters until this is rock-solid. Do **not** build marketplace functionality, fancy UI, ten workers, more external intelligence imports, Bittensor submission automation, or cost optimization yet.

---

# 0. P0 SECURITY REMEDIATION BEFORE MORE AUTONOMOUS EXECUTION

The public `prx0r/mw` repository currently contains credential material in `HANDOVER-2026-09-01.md`. Do not echo any values into logs, issues, commits, prompts or reports.

Required immediately:

1. Rotate every credential/token/password/OAuth secret exposed in that file or its Git history.
2. Replace literal secrets in docs with vault key names only.
3. Purge leaked material from Git history using a history-rewrite tool, then force-push after making a local backup.
4. Enable secret scanning/pre-commit checks (e.g. gitleaks/trufflehog style scanning) and CI failure on detected secrets.
5. `mw` docs may say `CredentialRef("oracle/.../")`; they must never contain secret values.
6. Run a full repository + history secret scan on `mw`, `bitt`, `qdw-workbench`, `mwgym` before resuming unattended workers.

This is P0 because an autonomous worker executing with already-public credentials is not acceptable.

---

# 1. PEER REVIEW: WHAT IS REAL NOW

There is useful real infrastructure already:

- `qdw-workbench` has frozen Pydantic contracts, append-only SQLite/WAL ledger, content-addressed artifact storage, a Hydra client/projector, worker/version registry, experiment objects, evaluator models and API surface.
- Hydra has been exercised live and a delete/rebuild test exists.
- `bitt` has a real CG BitSec world and real ScaBench-shaped evaluation flow.
- The Bitt bridge records run/evaluation/completion events.
- A WorkerKit/Pydantic BATS harness exists in the environment and has previously been used for real model calls.
- The latest Bitt code now produces a negative learning-cycle result (proposal -> paired run -> reject), which is a useful milestone.

But the current code does **not yet prove the learning loop**. Several of the most important invariants are currently violated.

---

# 2. CRITICAL FINDINGS IN `/bitt`

## 2.1 WorkerKit execution is currently not trustworthy

File: `workers/bitsec/cg_bridge.py`

Current problems:

- The file uses `os.environ` / `os.path` but the current import block does not import `os`. That means the WorkerKit path can throw and immediately enter the broad fallback.
- The entire WorkerKit block is inside `except Exception`, and on *any* failure it silently falls back to a direct Cloudflare call and still returns `status="ok"`.
- Therefore a run labeled as a WorkerKit run can actually be a different executor.
- This destroys provenance and makes comparison results scientifically invalid.

**Fix:** remove the fallback completely for CP1. If WorkerKit fails, the run fails closed with a typed execution error and no evaluation/promotion eligibility.

Required receipt fields:

```text
executor_kind
executor_version/commit
runtime
model_provider
model_name
model_revision if available
worker_version_id
request_count
tokens_in/tokens_out
cost_usd
wall_ms
trajectory_artifact_digest
output_artifact_digest
error_type/error_message if failed
```

## 2.2 The task is truncated to 10,000 characters

The current bridge embeds `code[:10000]` in the prompt and writes only `code[:10000]` to the workspace. This explains the Coded Estate failures and makes cross-file analysis impossible by construction.

**Fix:** never pass a whole repository as one prompt string. Materialize the complete pinned repo/worktree and let the worker inspect it through file tools. The task prompt should point at the workspace and define the audit objective/output schema.

A TaskInstance must pin:

```text
benchmark_id
benchmark_commit/version
project_id
repo/source digest
split
task_manifest_digest
evaluator_version
allowed tools
seed
```

## 2.3 Candidate WorkerVersion is currently only a label

`learning_loop.py` calls:

```text
control_version="security-01/v0"
candidate_version="security-01/v1"
```

but the actual execution does not resolve those immutable versions from the WorkerRegistry. In `cg_bridge.py`, `worker_genome_id` is hardcoded to `security-01/v0`. In the paired loop, candidate behavior is hardcoded as `arm='D'`.

So today:

- the LearningProposal patch is not what is actually being tested;
- v1 does not necessarily exist as an immutable WorkerVersion;
- the candidate version ID is mostly a display label;
- the same harness can still report itself as v0.

**Fix:** WorkerVersion must be executable configuration, not metadata. Resolve it before every run and pass the resolved immutable config into WorkerKit.

At minimum pin:

```text
model/provider
system prompt digest
process policy + source commit/path/digest
skills + revisions
memory revision
context policy
tool policy
routing policy
runtime/harness commit
```

## 2.4 Findings are not actually being carried into canonical evidence

The current bridge contains an empty findings loop (`enumerate([])`), so `Finding` contracts are never populated from the actual worker result. The canonical qdw `RunReceipt` also currently has `artifacts=[]`.

That means the ledger has aggregate evaluation numbers but not the full evidence needed to understand *why* the worker failed.

**Fix:** structured WorkerKit output must become a Pydantic `Finding[]`, each with evidence locations (file/path/line span or artifact evidence), then be stored as artifacts and linked into the RunReceipt.

## 2.5 Several of the “9 dimensions” are currently synthetic

Current bridge values include constants such as:

- `tokens_used=0`
- `cost_usd=0.0`
- `tool_calls=1`
- `worker_confidence=0.5`
- observations hardcoded to 1

These metrics must either be measured from the trajectory or explicitly marked unavailable. Never fabricate a numeric value that looks observed.

## 2.6 Direct Hydra writes from `/bitt` must be removed

The latest bridge writes Cypher directly from Bitt after the ledger write. This violates the agreed architecture: Hydra is a derived projection owned by the private lab.

The current direct write also interpolates strings into Cypher and constructs duplicate-looking `Run` nodes rather than using the canonical projector.

**Fix:** `/bitt` writes canonical events/artifacts only. `qdw-workbench` is the only component that projects canonical events to Hydra. No domain adapter writes Hydra directly.

---

# 3. CRITICAL FINDINGS IN `/qdw-workbench`

## 3.1 The Hydra projector currently mutates the canonical ledger

File: `lab/projection/__init__.py`

`project_evaluation_completed()` appends a new `run.outcome_recorded` event while projecting an existing event.

That means a Hydra **rebuild changes canonical truth**. Rebuilding repeatedly can mutate the ledger. This breaks the central invariant.

**Fix immediately:** projectors are pure consumers. A projector may write only to Hydra and projector checkpoint state. It may never append canonical domain events.

Generate `run.outcome_recorded` during evaluation/run completion before projection, not inside the projector.

Acceptance test:

```text
ledger_digest_before = digest(all ledger events)
rebuild Hydra 3 times
ledger_digest_after = digest(all ledger events)
assert before == after
assert event_count unchanged
assert Hydra graph digest identical all 3 times
```

## 3.2 Experiment state machine is not enforced

`ExperimentLifecycle` exposes create/seal/evaluate/promote, but currently it does not require a valid state transition.

Today the Bitt loop creates an arbitrary `experiment_id`, calls `seal_experiment()` on it without first calling `propose_experiment()`, then evaluates it. If a candidate ever passes, `promote()` looks for `experiment.created`, cannot find it, and cannot produce a valid promotion.

This means the current negative path works, but the positive promotion path is structurally broken.

**Fix:** implement an explicit state machine:

```text
PROPOSED -> SEALED -> RUNNING -> EVALUATED -> REJECTED|PROMOTED
```

Every method must read prior canonical state and reject illegal transitions.

A sealed experiment must store a content-addressed manifest containing:

```text
experiment_id
hypothesis
control_worker_version_digest
candidate_worker_version_digest
exact task IDs
exact task source digests
exact seeds
split
budget per run
runtime/harness revision
evaluator revision
primary metric
secondary metrics
promotion rule
manifest digest
```

After sealing, none of these fields can change.

## 3.3 Promotion statistic is wrong

`ExperimentLifecycle.evaluate()` currently uses a condition equivalent to:

```python
quality_delta > 0 and abs(ci_lower) < abs(quality_delta)
```

That does **not** reliably mean the CI excludes zero. A CI may cross zero and still satisfy that condition.

Also, `learning_loop.py` computes its own `promoted = delta > 0 and ci_lower > 0` but does not pass that decision through; the lifecycle recomputes it with the different rule.

**Fix:** there must be exactly one promotion rule implementation.

For CP1 use a simple predeclared paired rule:

```text
primary metric = per-task detection rate (or chosen authoritative task score)
compute per-task candidate-control deltas
paired bootstrap CI (or exact paired permutation/randomization test)
promote only if lower bound of 95% CI > 0
AND no predeclared secondary regression threshold is breached
AND minimum sample count reached
```

Do not claim significance from `n=2` or `n=3` real tasks. Use small n only as smoke tests.

## 3.4 WorkerRegistry immutability verification is not real enough

`verify_version_immutability()` currently checks the creation event exists and returns the digest recorded in it, but does not re-load the stored WorkerVersion artifact and recompute/compare its digest.

**Fix:** verification must:

1. find exactly one creation event;
2. resolve exactly one CAS artifact;
3. recompute canonical serialization digest;
4. verify Git source commit/path/digest;
5. verify parent lineage;
6. fail on any mismatch.

Also fix the known `SourceRef` timestamp/default issue so creating the same logical config produces the same digest.

## 3.5 WorkerKitBackend is not yet a correct WorkerVersion executor

File: `lab/execution/__init__.py`

Current issues:

- hardcoded worker ID (`lab-worker-v1`);
- hardcoded model;
- task is just `Complete task: <task_instance_id>` rather than a materialized task;
- no explicit fresh Letta conversation/session per run;
- error handling returns dictionaries instead of typed fail-closed execution errors;
- cost is hardcoded to zero;
- the method stores trajectory/output but does not itself produce the authoritative evaluation + final RunReceipt described by its docstring.

**Fix:** make `WorkerKitBackend.execute(run_spec, worker_version, task, context_pack, budget)` the one execution boundary. No hardcoded worker/model config.

---

# 4. REPO OWNERSHIP / ARCHITECTURE DRIFT

The current `prx0r/mw` default branch is the **Oracle** (“map of machine-work markets”). It says it provides intelligence to WorkerKit. The Bitt code currently imports `PydanticBATSHarness` from `/root/mwgym`, not from `/mw`.

Do not create a third copy of WorkerKit logic to fix this.

For CP1 establish these boundaries:

```text
/mw (Oracle)
  finds/ranks opportunities only

/qdw-workbench (Private Lab control plane)
  canonical contracts
  canonical ledger
  artifact CAS
  Worker registry/version lineage
  ContextPack compiler
  experiment lifecycle
  promotion logic
  Hydra projector

WorkerKit execution implementation
  one canonical package/location
  qdw has a thin backend adapter to it
  BitSec never imports an alternative executor directly

/bitt
  BitSec domain module
  task materialization
  CG BitSec world
  authoritative evaluator adapter
  domain-specific structured findings
  NO canonical persistence implementation
  NO direct Hydra writes
  NO hidden fallback executor

/cg
  deterministic experiment/evaluation kernel

/mwgym/CGE
  scientist/adversary/curriculum proposals
  may propose; may not promote
```

If WorkerKit physically remains in `mwgym` for now, that is fine. Document it as the canonical implementation for CP1 and add a stable adapter. Do not spend this session moving packages merely for aesthetics.

---

# 5. IMPLEMENTATION ORDER

Use branches named something like `cp1-real-learning-loop` in `qdw-workbench` and `bitt`. Make small commits that each have a falsifiable acceptance test.

## CHECKPOINT A — canonical truth is safe

### A1. Fix deterministic contracts

- deterministic canonical JSON serialization;
- no timestamp/default variance in identity digests;
- frozen Pydantic models with `extra=forbid`;
- WorkerVersion digest stable across processes/restarts.

### A2. Make Hydra projector pure

- remove ledger writes from projection;
- add projection for all events needed by CP1;
- projector checkpoints are separate from canonical events;
- rebuild must be idempotent and must not mutate ledger.

### A3. Harden worker registry

- prevent duplicate version IDs;
- verify artifact digest and Git source;
- candidate version must exist before experiment seal;
- promotion must reference a valid sealed/evaluated ExperimentResult.

**A acceptance:** all existing tests + new idempotent rebuild + tamper tests pass.

---

## CHECKPOINT B — one real BitSec run through one execution path

### B1. Materialize a real ScaBench task

Implement a BitSec module method such as:

```python
materialize_task(project_id, split, seed) -> TaskInstance + WorkspaceRef
```

It must:

- pin benchmark version/commit;
- pin project/repo digest;
- materialize the **entire repository**;
- keep labels/ground truth outside worker-visible context;
- produce a task artifact digest.

### B2. WorkerKit only

Change Bitt execution so it calls the qdw `WorkerKitBackend` (or a thin canonical WorkerKit adapter) and nothing else.

- remove direct CF fallback;
- missing WorkerKit -> typed failed run;
- execution provenance in receipt;
- no `code[:10000]` anywhere in the real path.

### B3. Structured findings

Use a Pydantic output contract, for example:

```text
FindingCandidate:
  title
  category
  severity
  description
  confidence
  evidence[]:
    file
    line_start
    line_end
    rationale
```

Store raw model output and parsed output separately as CAS artifacts.

### B4. Authoritative evaluation

Do not use title substring heuristics as the promotion authority.

Use the pinned BitSec/ScaBench evaluator/ground-truth adapter already associated with the CG world. Evaluator sees labels; worker does not.

**B acceptance:** one chosen project (start with Fenix Finance because it has already yielded TPs) runs end-to-end and produces:

```text
TaskInstance
ContextPack
WorkerVersion v0
Trajectory artifact
Output artifact
Finding artifacts
EvaluationResult
RunReceipt
ledger events
Hydra projection
```

All IDs/digests must cross-link.

Then run Coded Estate and prove the full repo is available (no truncation failure).

---

## CHECKPOINT C — Letta semantics without hidden mutation

The agreed model is:

- one persistent Letta agent identity per Worker;
- **fresh conversation/session per Run**;
- WorkerVersion pins the memory/skill/config revision used for that run;
- no invisible mid-run/mid-experiment mutation;
- reflection may produce a LearningProposal, but may not mutate the promoted worker directly.

Implement:

```text
Worker.security-01 -> letta_agent_id
WorkerVersion.security-01/v0 -> pinned memory + skills + prompt + process digest
Run -> fresh conversation/session id
```

At run end store the Letta trajectory/session export as an artifact.

If Letta is unavailable, fail the Letta-backed CP1 run; do not silently substitute another agent.

**C acceptance:** restart Letta, rerun the same frozen v0 on the same task/seed/context, and prove version identity/provenance remain valid even though model output may be stochastic.

---

## CHECKPOINT D — real failure analysis -> one mutation

CGE reads only canonical TRAIN/DEV evidence:

```text
RunReceipt
EvaluationResult
Finding TP/FP/FN mapping
trajectory
cost/tool/error data
```

It should produce a structured `FailureCluster`, not merely “DR < 0.5”. Examples:

```text
missed cross-file dataflow
missed authorization edge
false-positive pattern
insufficient repo coverage
premature submission
parsing/format failure
tool/runtime failure
```

Then generate **exactly one** LearningProposal with:

```text
source run IDs
evidence artifact digests
hypothesis
single mutation type
exact patch
expected affected metric
possible regression
confidence
```

Do not let CGE choose from SECRET labels.

---

## CHECKPOINT E — create the candidate for real

A LearningProposal must be compiled into a real immutable `security-01/v1` before evaluation.

Example mutation may change only one thing:

```text
process_policy: v0 -> cross-file-v1
```

or one prompt block / skill revision.

Create v1 through WorkerRegistry with:

```text
parent_version_id = security-01/v0
proposal_id
source commit/path/digest
all inherited pins
only one intentional diff
```

Add a test that compares v0/v1 canonical JSON and asserts the only changed fields are those authorized by the proposal.

---

## CHECKPOINT F — sealed paired experiment

Never select “first N current repos” at evaluation time.

Create the experiment first:

```python
spec = lifecycle.propose_experiment(...)
manifest = cg.materialize_manifest(
    exact_task_ids=[...],
    exact_seeds=[...],
    control_digest=...,
    candidate_digest=...,
    evaluator_digest=...,
    budget=...,
)
lifecycle.seal_experiment(spec.id, manifest_digest)
```

Then execute exactly the sealed manifest.

For each task:

- same repo snapshot;
- same seed/world config;
- same tool permissions;
- same model/provider unless the proposal explicitly changes model;
- same budget;
- randomized or alternated execution order to reduce temporal/provider drift;
- independent trajectory artifacts.

Start with 2 tasks only as an integration smoke test. For a promotion decision use a meaningful DEV set (preferably 10+ paired tasks; use more when available).

Use paired statistics on per-task deltas. Do not use independent-arm standard error for a paired design.

Primary CP1 gate suggestion:

```text
candidate mean primary score > control
AND paired 95% CI lower bound > 0
AND precision/F1 regression does not breach predeclared threshold
AND invalid-action/runtime failure rate does not regress materially
AND minimum task count met
```

Cost can be recorded but **do not optimize for it yet**.

---

## CHECKPOINT G — promotion and rejection both proven

### Negative path

A worse/uncertain candidate must create:

```text
ExperimentResult(promoted=False)
experiment.rejected event
NO active worker change
NO PromotionReceipt
```

### Positive path

First prove the wiring with a deterministic test fixture whose candidate is known to beat control. Then prove it on a real BitSec candidate when evidence warrants it.

A valid promotion must require:

1. experiment exists;
2. experiment was sealed before runs;
3. manifest digest matches all run receipts;
4. control/candidate versions exist and match digests;
5. evaluator version matches manifest;
6. minimum sample count met;
7. promotion rule passes;
8. no disqualifying run errors/fallback execution;
9. ExperimentResult artifact digest matches ledger;
10. only then create PromotionReceipt.

PromotionReceipt must link:

```text
candidate version
parent version
proposal
experiment
experiment result
run receipt IDs
manifest digest
promotion rule version
Git/source digests
timestamp
```

Then v1 becomes the active version for subsequent runs. Do not mutate v0.

---

# 6. HYDRA GRAPH FOR CP1

Hydra must be a disposable projection of canonical evidence.

Project at least:

```text
Worker
WorkerVersion
TaskInstance
Run
TrajectoryArtifact
Finding
EvaluationResult
FailureCluster
LearningProposal
Experiment
ExperimentResult
PromotionReceipt
```

Edges should preserve lineage, e.g.:

```text
Worker -HAS_VERSION-> WorkerVersion
WorkerVersion -EXECUTED-> Run
Run -ON_TASK-> TaskInstance
Run -PRODUCED-> Finding
Run -EVALUATED_BY-> EvaluationResult
FailureCluster -SUPPORTED_BY-> Run
LearningProposal -SUPPORTED_BY-> FailureCluster
LearningProposal -CREATED-> WorkerVersion(v1)
Experiment -CONTROL-> v0
Experiment -CANDIDATE-> v1
Experiment -USES_TASK-> TaskInstance
ExperimentResult -RESULT_OF-> Experiment
PromotionReceipt -PROMOTES-> v1
```

Do not invent graph facts that do not exist in the ledger/artifacts.

Critical Hydra test after a real cycle:

1. snapshot graph logical digest/counts;
2. snapshot ledger digest;
3. destroy Hydra;
4. rebuild only from canonical ledger + artifacts;
5. assert graph digest/counts/lineage match;
6. assert ledger digest/count is unchanged;
7. repeat rebuild twice more.

---

# 7. TEST SUITE THAT ACTUALLY MATTERS

Add these integration/failure tests before claiming CP1:

## Execution

- WorkerKit missing -> run fails, no fallback.
- WorkerKit exception -> run fails with typed reason.
- entire ScaBench repo is materialized; file count/digest matches source.
- malformed model output -> raw output retained, parse error recorded, no fake findings.
- token/cost/tool metrics come from runtime or are explicitly `None`, never fabricated zeroes.

## Letta

- persistent agent ID survives restart.
- fresh conversation/session ID per run.
- v0 memory/skills do not mutate during sealed experiment.
- reflection produces proposal, not direct version mutation.

## WorkerVersion

- duplicate version ID rejected.
- artifact tampering detected.
- Git commit/path digest mismatch detected.
- same logical version produces same digest.
- candidate differs from parent only in approved patch.

## Experiments

- seal nonexistent experiment -> reject.
- evaluate unsealed experiment -> reject.
- mutate manifest after seal -> reject.
- mismatched task/seed/evaluator in a run -> experiment invalid.
- positive CI-crossing-zero case -> reject.
- deterministic known-better fixture -> promote.
- negative fixture -> reject.
- promotion of nonexistent candidate -> reject.

## Hydra

- projector cannot write canonical events.
- repeated rebuild does not change ledger count/digest.
- interrupted projection can resume/rebuild.
- deleting Hydra loses no canonical knowledge.

## Split/contamination

- worker cannot access ground-truth labels.
- CGE cannot access SECRET labels.
- evaluator can access labels through a separate authority boundary.
- task manifest identifies TRAIN/DEV/VALIDATION/SECRET explicitly.

---

# 8. FIRST REAL CP1 RUNBOOK

Once the fixes above are merged:

### Phase 1 — baseline

Run frozen `security-01/v0` on a fixed TRAIN set (e.g. 8–10 real ScaBench tasks). Produce full receipts, failure mappings and Hydra projection.

### Phase 2 — proposal

CGE reads those runs and proposes one process change from the dominant failure cluster.

### Phase 3 — candidate

Compile the proposal to immutable `security-01/v1`.

### Phase 4 — smoke paired test

Run v0/v1 on exactly 2 sealed DEV tasks to catch wiring errors only. No promotion claim.

### Phase 5 — real paired evaluation

Run the predeclared DEV/VALIDATION manifest with enough paired tasks for the gate. Record full evidence.

### Phase 6 — decision

Create either a valid rejection or valid PromotionReceipt.

### Phase 7 — rebuild proof

Destroy Hydra, rebuild from canonical data, prove exact lineage is recoverable and ledger is unchanged.

### Phase 8 — next cycle

If v1 was promoted, the next TRAIN run must start from v1. If rejected, v0 remains active and the rejection evidence becomes input to the next CGE proposal.

That is the first actual autonomous learning loop.

---

# 9. DEFINITION OF DONE FOR CP1

Do not mark CP1 complete unless a machine-readable evidence bundle can answer all of these without reading logs manually:

```text
Which exact worker version ran?
What exact source/config/memory/skills did it pin?
Which exact task snapshot did it see?
Which exact context did it receive?
Which executor/model/runtime actually ran?
What did it do step by step?
What artifacts/findings did it produce?
What did the authoritative evaluator score?
Why did it fail?
Which runs caused the LearningProposal?
What exact single change produced v1?
Which exact tasks/seeds compared v0 and v1?
Were all pairs run under the sealed manifest?
What statistic and rule caused reject/promote?
Can the full graph be rebuilt after Hydra is destroyed?
Can the entire lineage be independently verified from Git + ledger + CAS?
```

If any answer is “we infer it from a print statement”, it is not done.

---

# 10. COMMIT PLAN FOR THE CODING AGENT

Keep commits narrow:

1. `security: remove leaked credentials and add secret scanning`
2. `fix(lab): make Hydra projection pure and rebuild idempotent`
3. `fix(lab): deterministic WorkerVersion digests and real immutability verification`
4. `fix(lab): enforce experiment state machine and sealed manifests`
5. `fix(lab): correct paired promotion statistics and single gate implementation`
6. `fix(bitsec): remove fallback executor and full-repo task materialization`
7. `feat(bitsec): structured finding evidence + canonical artifacts`
8. `feat(workerkit): execute resolved WorkerVersion with real provenance`
9. `feat(letta): persistent worker, fresh run session, pinned memory revision`
10. `feat(loop): evidence-backed FailureCluster -> LearningProposal -> real candidate version`
11. `feat(loop): sealed v0/v1 paired CG evaluation`
12. `test(cp1): prove reject path, promotion fixture, Hydra destruction/rebuild`
13. `test(cp1): run first real BitSec learning cycle and save evidence bundle`

After each commit, update one `CP1-STATUS.md` table with **REAL / TEST-ONLY / STUB / BROKEN**. Never call a component “wired” because imports succeed.

---

# 11. THINGS TO DELETE OR DISABLE NOW

Delete/disable from the CP1 production path:

- direct Hydra writes in `/bitt`;
- broad executor fallback from WorkerKit to CF;
- 10k source truncation;
- hardcoded `security-01/v0` inside executor;
- hardcoded candidate `arm='D'` unrelated to proposal;
- synthetic cost/token/tool metrics;
- arbitrary experiment IDs sealed without creation;
- n=2 “statistical” promotion decisions;
- title-substring matching as promotion authority;
- projectors that append canonical events;
- any test that counts synthetic `DirectBackend` output as a real run.

Keep DirectBackend only as an explicitly named test fixture and ensure real CP1 tests assert `metadata.harness != "direct"`.

---

# 12. FINAL PRIORITY

The recent work has crossed an important threshold: the pieces are no longer hypothetical. The next danger is **believing the glue is more real than it is**.

Do not add more pieces. Make the boundaries truthful.

The single target is:

> **One real BitSec failure becomes one evidence-backed mutation, that mutation becomes a real immutable worker version, CG evaluates it on a sealed paired manifest, and the lab can independently reject/promote it and reconstruct the entire decision after deleting Hydra.**

Once this works, BitSec becomes the first Lab/School and the same loop can be reused for Metaculus, benchmarks, bug bounty work and later economic targets. Until then, everything else is secondary.
