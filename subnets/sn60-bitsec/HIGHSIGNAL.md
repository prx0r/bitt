# HIGHSIGNAL.md — The Correct Path to a Competitive BitSec Miner

## The Singular Goal

**Get a competitive BitSec miner that can beat the benchmark.**

## What I Was Doing Wrong

### Wrong Objective
- Optimizing F1/DR instead of all-findings project pass
- The real objective: find ALL high/critical vulns in 2/3 runs

### Wrong Approach
- Building custom evaluators instead of using official BitSec sandbox
- Prompting with known vulnerabilities (hard-steering, will get banned)
- Not testing against the real BitSec scorer

### Wrong Assumptions
-以为 generic prompting works (it doesn't)
- 以为 project-specific prompting scales (it doesn't without ground truth)
- 以为 API reliability is the problem (it's not — the architecture is wrong)

## What Actually Works

### The Official BitSec Architecture
1. **Official sandbox** — `miner/agent.py` with `agent_main()`
2. **Official scorer** — only high/critical, all must be found
3. **Official execution** — 3 runs per project, 2/3 must pass
4. **Official projects** — 4 codebases from validator/projects.json

### The Real Objective
```
for project in projects:
    executions = run(candidate, project, n=3)
    execution_pass[i] = detected_all_expected_high_critical(execution[i])
    project_pass = sum(execution_pass) >= 2

validator_score = passed_projects / total_projects
```

### What Makes a Finding Count
- Must be high/critical severity
- Must match ground truth (contract, function, mechanism, impact)
- Must be found in 2/3 runs

## What I Need to Build

### 1. Official Baseline
- Copy `miner/agent.py` from BitSec sandbox
- Run unchanged
- Establish baseline performance

### 2. Methodology Improvements (NOT prompt hacking)
- Architecture mapping (understand code structure)
- Hypothesis-driven investigation (targeted, not generic)
- Cross-file analysis (trace value flows)
- Independent verification (confirm before reporting)

### 3. Repeated Evaluation
- Run each candidate 9+ times per project
- Measure detection probability per vulnerability
- Optimize for reliability, not just recall

### 4. Sealed Holdout
- Test on projects NOT in BitSec benchmark
- Prove methodology generalizes
- Prevent hard-steering

## The Fastest Path to Submission

1. **Pin official BitSec sandbox** — exact commit, exact scorer
2. **Run official baseline** — establish baseline performance
3. **Build methodology improvements** — inside official agent contract
4. **Test with repeated evaluation** — 9+ runs per project
5. **Build sealed holdout** — prove generalization
6. **Submit** — when passing 2/3 on all 4 projects

## What NOT to Do

- ❌ Build custom evaluators
- ❌ Prompt with known vulnerabilities
- ❌ Optimize F1 instead of project pass
- ❌ Skip repeated evaluation
- ❌ Ignore hard-steering rules
- ❌ Submit without Docker testing

## Time is the Scarcest Resource

Every hour spent on the wrong approach is an hour not spent on the right one.

**Right approach:** Official sandbox + methodology improvements + repeated evaluation
**Wrong approach:** Custom evaluators + prompt hacking + F1 optimization

Start with the right approach NOW.
