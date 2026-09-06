# Miner Codenames & Promotion Tracker

## Codename Registry

| Codename | Version | Created | Projects Passed | Status |
|----------|---------|---------|-----------------|--------|
| (none yet) | | | | |

## Active Miners

| Codename | Current Project | DR | Status | Notes |
|----------|----------------|-----|--------|-------|
| (none yet) | | | | |

## Promotion Criteria

1. **100% DR on a project** → candidate (not yet promoted)
2. **100% DR on 2+ projects** → PROMOTED
3. **Promoted miner added to regression suite** — must re-pass on all future runs
4. **Lesson extracted** → added to MEGAMINER rubric

## Anti-Overfitting Protocol

### The Problem
A miner that memorizes "iq-ai has bug X" won't find bug Y on liquid-ron.
Overfitting = high DR on training project, low DR on new project.

### The Solution
1. **Cross-validation**: promoted miner must pass on HELD-OUT project
2. **Lesson abstraction**: extract WHAT was learned, not just WHERE
3. **Rubric inheritance**: new miners inherit all lessons as constraints
4. **Regression testing**: every mutation must re-pass all previously passed projects

### The Flow

```
Probe A: miner v0 on iq-ai → 100% DR → STORED (not promoted)
Probe B: miner v0 on liquid-ron → 0% DR → FAILED
Analysis: what did v0 miss on liquid-ron?
Mutation: add lesson "must check X"
Probe C: miner v1 on iq-ai → 100% DR (regression OK)
Probe D: miner v1 on liquid-ron → 100% DR → PROMOTED
Lesson: "must check X" → added to MEGAMINER rubric
```

## Winning Versions (Promoted)

| Codename | Version | Projects Passed | Lesson Added |
|----------|---------|-----------------|-------------|
| (none yet) | | | |

## Failed Probes (Lessons Learned)

| Codename | Version | Project | DR | What Was Missed |
|----------|---------|---------|-----|-----------------|
| (none yet) | | | | |
