# IMPORTANT.md — What I Was Doing Wrong vs What Actually Works

## What I Was Doing Wrong

### 1. Wrong Objective
**I was optimizing F1/DR instead of all-findings project pass.**

The real BitSec objective:
- Find ALL high/critical vulnerabilities
- In at least 2/3 runs per project
- Pass 2/3 of all projects

Not: maximize F1 or detection rate.

### 2. Wrong Approach
**I was building custom evaluators instead of using official BitSec sandbox.**

My evaluators:
- `workers/bitsec/evaluator.py` — leaks labels, wrong scorer
- `workers/bitsec/scaBench_eval.py` — doesn't call miner_v5, wrong scorer
- `cge/bitsec/real_eval.py` — no label leakage but doesn't give code to model

Official BitSec:
- `miner/agent.py` with `agent_main()`
- Official sandbox execution
- Official scorer (high/critical only)

### 3. Wrong Prompting
**I was prompting with known vulnerabilities (hard-steering).**

The "81.8% winning approach" was:
- Asking for specific vulnerability types from ground truth
- This is hard-steering and WILL get banned

What works:
- Generic audit methodology
- Code-derived hypotheses
- Targeted investigation (not benchmark-specific)

### 4. Wrong Architecture
**I was trying to wrap miner_v5 instead of using official agent.**

miner_v5:
- Expects `predict(code)` with giant code string
- Imports from `/root/bitt`
- No `agent_main()`
- Not BitSec-compatible

Official agent:
- Exposes `agent_main()`
- Uses inference proxy
- Works in Docker sandbox
- Returns proper format

## What Actually Works

### 1. Official BitSec Architecture
```bash
# Clone official sandbox
git clone https://github.com/Bitsec-AI/sandbox.git

# Run official agent
uv run ./bitsec.py miner run-no-docker

# Score with official scorer
# Find ALL high/critical in 2/3 runs
```

### 2. Real Objective
```python
for project in projects:
    executions = run(candidate, project, n=3)
    execution_pass[i] = detected_all_expected_high_critical(execution[i])
    project_pass = sum(execution_pass) >= 2

validator_score = passed_projects / total_projects
```

### 3. Methodology (NOT Prompt Hacking)
- Architecture mapping
- Hypothesis-driven investigation
- Cross-file analysis
- Independent verification
- Repeated evaluation

### 4. What Makes a Finding Count
- High/critical severity
- Matches ground truth (contract, function, mechanism, impact)
- Found in 2/3 runs

## The Fastest Path to Submission

1. Pin official BitSec sandbox
2. Run official baseline
3. Build methodology improvements
4. Test with repeated evaluation
5. Build sealed holdout
6. Submit

## Time is the Scarcest Resource

**Right:** Official sandbox + methodology + repeated eval
**Wrong:** Custom evaluators + prompt hacking + F1 optimization

Start with the right approach NOW.
