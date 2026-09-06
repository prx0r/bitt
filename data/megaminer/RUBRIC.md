# MEGAMINER Rubric — Global Wisdom Store

## What This Is

The MEGAMINER is the accumulated lessons from every successful miner probe.
Each lesson is a BINARY requirement: "must do X" or "must check Y."
All future miners inherit every lesson. No regressions.

## How It Works

```
Miner v0 → Project A → 100% DR → PROMOTED
  → Test on Project B
  → If 100% on B too → lesson extracted → added to rubric
  → If not → mutate → v1 → test on BOTH A and B
  → Must pass BOTH to be promoted

Each promotion adds a binary lesson to the rubric.
New miners must satisfy ALL accumulated lessons.
```

## Current Rubric (empty — building from scratch)

No lessons yet. First miner to hit 100% on any project starts the rubric.

## Promotion Log

| Date | Miner | Project | DR | Promoted? | Lesson Added |
|------|-------|---------|-----|-----------|-------------|
| (none yet) | | | | | |

## Anti-Overfitting Protocol

1. **Single-project win** → stored as candidate, NOT promoted
2. **Multi-project win** (100% on 2+ projects) → PROMOTED, lesson extracted
3. **Cross-validation** → promoted miner must pass on held-out project
4. **Regression test** → every mutation must re-pass all previously passed projects
5. **Rubric inheritance** → new miners start with ALL accumulated lessons

## The MEGAMINER Concept

The MEGAMINER is not a specific miner file. It's the **rubric** — the set of binary lessons that every miner must satisfy.

As probes succeed, the rubric grows:
- "Must trace marketplace lifecycle state transitions"
- "Must check approval cleanup on cancel"
- "Must verify payment bypass via send_nft"
- etc.

New miners are initialized with the full rubric as system prompt constraints.
This ensures no regression and forces generalization.
