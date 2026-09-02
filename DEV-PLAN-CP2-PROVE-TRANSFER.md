# DEV PLAN — CHECKPOINT 2: Prove Security Transfer

**Date:** 2026-09-01
**Source:** Email thread "work for bitt agent" + "bitt agent security architectures"
**Status:** Active

---

## Goal

> A WorkerVersion promoted using BitSec evidence measurably improves performance on a security task distribution that CGE never trained against, and at least one successful transfer candidate can be packaged and submitted to a real external security venue.

NOT "we submitted to a bounty." A submission alone proves almost nothing.

---

## Transfer Ladder

```
SOURCE WORLD
BitSec / SCA-Bench
    │
    ▼
NEAR TRANSFER
historical bug-bounty / audit replay
Sherlock / Cantina / Immunefi-style disclosed cases
    │
    ▼
LIVE NEAR TRANSFER
real authorized audit / bug-bounty opportunity
    │
    ▼
FAR TRANSFER
RedTeam SN61 challenge
    │
    ▼
LIVE FAR TRANSFER
SN61 miner submission / other AI red-team market
```

This tells us **what** transferred.

---

## CP2.1 — Near Transfer (BountyBench)

Build `studio/security/bugbounty-replay` from BountyBench.

```text
security-01/v0 (no BitSec learning)
vs
security-01/vN (promoted in BitSec)

Same tasks. Same budgets. Same model allowances.
```

**Multi-dimensional evaluation (NOT just "did it say vulnerability"):**
- correct vulnerability
- affected code/location
- exploitability reasoning
- false positives
- severity correctness
- PoC/reproduction success
- patch correctness
- regression safety
- cost / model calls / latency

---

## CP2.2 — Capability Pool Causal Test

**Hypothesis:** A validated BitSec finding that cross-file call-graph investigation improves vulnerability discovery will improve independent bounty replay performance when injected through the SecurityPool Context Compiler.

**Test:**
```
same WorkerVersion
same task
same budget
same model

A = no transferred finding
B = transferred validated finding
```

If B wins on held-out bounty cases:
```
Finding
  ──VALID_IN──> BitSec
  ──TRANSFERRED_TO──> BugBountyReplay
```
→ `STUDIO_FINDING` → `TRANSFER_CLAIM`

If it does not transfer: `TRANSFER_REJECTED`

---

## CP2.3 — Far Transfer (RedTeam SN61)

Same Lab machinery trains/evaluates a RedTeam SN61 candidate **without adding a special second learning system**.

**SN61 challenges include:**
- AB Sniffer — detect browser automation frameworks
- Bot Virus
- FlowRadar v2
- Humanize Behaviour — mimic human web interaction
- Anti-Detect Browser Detection

**BitSec trains:**
code comprehension, vulnerability hypothesis, cross-file reasoning, finding validation, false-positive suppression, security reporting

**RedTeam tests whether general processes transfer:**
scientific experimentation, adversarial hypothesis generation, instrumentation, reproduction, measurement, false-positive minimization, iterative improvement, Dockerized challenge execution

**Do NOT expect Solidity-specific memory to help RedTeam.**

**Experiment:**
```
RedTeam baseline worker
vs
same worker + globally validated security process findings

NOT:
inject every BitSec lesson into RedTeam
```

The Context Compiler prevents capability-pool contamination.

---

## CP2.4 — Real Venue Adapter

WorkerKit can package and submit to at least one authorized live security venue through a venue adapter and record `ExternalSubmissionReceipt` + eventual `ExternalOutcomeReceipt`.

---

## CP2.5 — No Contamination

BitSec-only observations **cannot** automatically enter RedTeam/bug-bounty context. Only validated transfer claims or generic Lab doctrine can cross Studio boundaries.

---

## CP2.6 — Economic Evidence

Record whether transfer is economically useful:
- quality
- accepted finding rate
- cash/TAO reward
- cost per attempt
- human seconds
- submission rate
- expected value

But money remains separate from CG evaluation quality.

---

## SecurityPool Architecture

```yaml
security/
  repo-navigation
  threat-modeling
  hypothesis-generation
  source-code-audit
  cross-file-reasoning
  access-control
  token-flow-analysis
  oracle-analysis
  business-logic
  exploit-reproduction
  static-analysis
  fuzzing
  false-positive-control
  finding-deduplication
  severity-estimation
  report-writing
  patch-generation
  regression-testing
  browser-adversarial-testing
  bot-detection
```

Every capability assertion backed by evidence:
```yaml
CapabilityEvidence:
  capability: access-control
  worker_version: security-01/v7
  source_studio: bitsec
  task_family: smart-contract-audit
  evaluator_version: ...
  split: SECRET
  score: ...
  n: ...
  source_run_receipts: [...]
  evidence_strength: VALIDATED
  observed_at: ...
```

Hydra answers:
```
security-01/v7
  strong: access-control, cross-file reasoning
  medium: token-flow analysis
  weak: oracle manipulation
  unknown: browser bot detection
```

---

## Security Lab Structure

```
PRIVATE LAB
│
├── SECURITY POOL
│   │
│   ├── School: code-audit
│   │   ├── BitSec SN60
│   │   ├── BugBountyReplay
│   │   ├── Sherlock
│   │   ├── Cantina
│   │   ├── Immunefi
│   │   ├── Huntr
│   │   └── OSS VRPs
│   │
│   ├── School: ai-redteam
│   │   ├── garak
│   │   ├── PyRIT
│   │   ├── AgentDojo / WASP
│   │   └── RedTeam SN61
│   │
│   └── School: adversarial-systems
│       ├── fuzzing
│       ├── browser detection
│       ├── protocol/incentive attacks
│       └── future security worlds
│
├── Worker: security-01
│   └── immutable versions v0 → v1 → v2 ...
│
├── WorkerKit
├── CG
├── CGE
├── Hydra
├── Letta
└── Budget allocator
```

**Key:** The Security Pool is NOT memory. It is an **evidence index** over what has been observed and validated. Letta remains the worker's cognition. Git owns promoted intellectual artifacts. Receipts are canonical evidence. Hydra projects the evidence graph.

---

## Automatic Private Holdout (SECRET set)

All public benchmarks eventually become trainable/known. Build a **rolling private Security Holdout** from the Oracle:

```
Oracle sees new disclosure
        ↓
freeze vulnerable commit
        ↓
capture tests/environment
        ↓
store fix/report separately
        ↓
create TaskInstance
        ↓
NO WEB / NO FIX / NO WRITEUP
        ↓
SEALED_LOCAL
```

After evaluation, the label can be revealed. The GitHub security-advisory feed already wired into the Security Oracle makes this natural.

---

## Pass Criteria

| ID | Criterion | Status |
|----|-----------|--------|
| CP2.1 | At least one BitSec-promoted worker/process beats its declared control on held-out independent bug-bounty/audit replay suite | ⬜ |
| CP2.2 | At least one STUDIO_FINDING from BitSec tested with/without retrieval on another Studio becomes TRANSFER_CLAIM or TRANSFER_REJECTED | ⬜ |
| CP2.3 | Same Lab machinery trains/evaluates a RedTeam SN61 candidate without adding a special second learning system | ⬜ |
| CP2.4 | WorkerKit can package and submit to at least one authorized live security venue through a venue adapter | ⬜ |
| CP2.5 | BitSec-only observations cannot automatically enter RedTeam/bug-bounty context | ⬜ |
| CP2.6 | Lab starts recording economic evidence for transfer | ⬜ |

---

## Then CP3 Becomes Obvious

Once CP2 proves transfer:

> Given BitSec, RedTeam, Sherlock/Cantina/Immunefi and other security opportunities, can the Lab decide whether to train, evaluate, submit, or hold based on expected capability gain + expected economic value + budget?

That is **autonomous allocation**.

```text
CHECKPOINT 1: Can one worker measurably learn in BitSec?
CHECKPOINT 2: Does that learning transfer across security worlds and produce viable external submissions?
CHECKPOINT 3: Can the Lab autonomously decide where to spend its next dollar/token/hour?
```

The actual object being built is a **general laboratory for measurable autonomous learning and allocation**. Security is the first frontier. BitSec is the first world.
