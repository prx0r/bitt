# AGENTS.md — Mining Goal

## The Singular Goal

**Get a competitive BitSec miner that can beat the benchmark.**

## What I Was Doing Wrong

1. **Wrong objective** — optimizing F1 instead of all-findings project pass
2. **Wrong approach** — custom evaluators instead of official BitSec sandbox
3. **Wrong prompting** — prompting with known vulnerabilities (hard-steering)
4. **Wrong architecture** — wrapping miner_v5 instead of using official agent

## What Actually Works

1. **Official BitSec sandbox** — `miner/agent.py` with `agent_main()`
2. **Official scorer** — high/critical only, all must be found
3. **Official execution** — 3 runs per project, 2/3 must pass
4. **Methodology** — architecture mapping + hypothesis-driven investigation

## The Real Objective

```
for project in projects:
    executions = run(candidate, project, n=3)
    execution_pass[i] = detected_all_expected_high_critical(execution[i])
    project_pass = sum(execution_pass) >= 2

validator_score = passed_projects / total_projects
```

## The Fastest Path

1. Pin official BitSec sandbox
2. Run official baseline
3. Build methodology improvements (NOT prompt hacking)
4. Test with repeated evaluation (9+ runs per project)
5. Build sealed holdout (prove generalization)
6. Submit

## Don't Ask

Just work. Deliver results.

## Read First

- `subnets/sn60-bitsec/HIGHSIGNAL.md` — the correct path
- `subnets/sn60-bitsec/IMPORTANT.md` — what I was doing wrong
- `subnets/sn60-bitsec/sandbox-v2/miner/agent.py` — official agent
