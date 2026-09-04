# Deterministic Improvement Plan — Bitsec SN60

## The Problem

Current mimo-v2.5 agent finds ~0-2 vulnerabilities per file. Winning agent finds ~17 per project. The gap is in **detection quality**, not infrastructure.

## The Loop (What We Have)

```
1. RUN base agent on ScaBench projects
2. SCORE against ground truth (TP, FP, FN)
3. ANALYZE failures (what was missed?)
4. PROPOSE mutation (prompt change, strategy change)
5. CREATE new version with mutation
6. RUN paired evaluation (v0 vs v1 on SAME tasks)
7. DECIDE: promote if ci_lower > 0
8. REPEAT
```

**All infrastructure exists. The bottleneck is detection quality.**

## Phase 1: Baseline (Do First)

### Step 1: Run Base Agent on 3 Projects

```python
# Use the simple agent
from pathlib import Path
import json

projects = [
    "code4rena_fenix-finance-invitational_2024_10",
    "code4rena_superposition_2025_01", 
    "code4rena_lambowin_2025_02",
]

for project in projects:
    # Load ground truth
    # Run agent on each .sol file
    # Score: TP, FP, FN
    # Record in Ledger
```

### Step 2: Measure Baseline

| Metric | Current | Target |
|--------|---------|--------|
| Detection Rate | ~0% | >50% |
| Precision | ~0% | >70% |
| F1 | ~0.0 | >0.5 |
| Files analyzed | 5 | All |

### Step 3: Identify Failure Modes

For each missed vulnerability:
- Was it in the code we analyzed?
- Did the model see it?
- Why didn't it report it?

Common failure modes:
1. **Code too long** — model loses context
2. **Wrong prompt** — model doesn't know what to look for
3. **Missing code** — model didn't see the vulnerable file
4. **Wrong severity** — model found it but scored it wrong

## Phase 2: Prompt Iteration (CGE Proposals)

### Mutation 1: Better Prompt

**Hypothesis:** More specific prompts find more vulns

**Before:**
```
Analyze this code for security vulnerabilities.
```

**After:**
```
You are a senior smart contract security auditor.
Look for: reentrancy, access control, overflow, logic errors.
Focus on: loss of funds, unauthorized access, contract exploitation.
Return: title, severity, description, location, file.
```

### Mutation 2: Cross-File Analysis

**Hypothesis:** Some vulns require understanding multiple files

**Before:** Analyze each file independently

**After:** Analyze related files together (e.g., token + vault + router)

### Mutation 3: Severity Focus

**Hypothesis:** Focusing on critical/high finds more high-value vulns

**Before:** Find all vulns

**After:** Focus on critical and high severity first

### Mutation 4: Chain-of-Thought

**Hypothesis:** Step-by-step reasoning improves detection

**Before:** Direct JSON output

**After:** First reason through the code, then output JSON

## Phase 3: Paired Evaluation (CG Kernel)

### For Each Mutation

1. **Create v1** with the mutation applied
2. **Run v0 and v1** on the SAME 3 projects
3. **Score both** against ground truth
4. **Compute delta** = v1_score - v0_score
5. **Compute 95% CI** on delta
6. **Promote** if ci_lower > 0

### The Paired Test

```python
# v0: current agent
v0_results = run_agent(base_agent, projects)

# v1: agent with mutation
v1_results = run_agent(mutated_agent, projects)

# Paired comparison
delta = v1_results["f1"] - v0_results["f1"]
ci_lower = bootstrap_ci(delta)

if ci_lower > 0:
    promote(v1)
else:
    reject(v1)
```

## Phase 4: Scale Up (After Baseline Works)

### Step 1: Test on 10 Projects

Expand from 3 to 10 ScaBench projects

### Step 2: Test on All 31 Projects

Full ScaBench evaluation

### Step 3: Submit to Platform

Once F1 > 0.5 on ScaBench, submit to Bitsec

### Step 4: Monitor Validator Scores

Track real-world performance on leaderboard

## The Key Insight

**The evolution machinery is ready. The mutation proposals are structured. The experiment lifecycle is proper. But the underlying worker is not finding vulnerabilities effectively.**

The real improvement needs:
1. **Better code ingestion** — don't concatenate all .sol files
2. **Per-file analysis** — analyze each file separately
3. **Better prompting** — specific to vulnerability types
4. **Cross-file reasoning** — when needed

## Files to Modify

| File | Change |
|------|--------|
| `workers/bitsec/agent.py` | Improve prompting |
| `cge/bitsec/evolution.py` | Test mutations |
| `workers/bitsec/learning_loop.py` | Wire to real evaluation |
| `cge/bitsec/benchmark.py` | Use real ScaBench scoring |

## Success Criteria

| Metric | Baseline | After 5 Mutations | After 10 Mutations |
|--------|----------|-------------------|-------------------|
| Detection Rate | 0% | >30% | >50% |
| F1 | 0.0 | >0.3 | >0.5 |
| Projects passed | 0 | 5 | 15 |

## Timeline

1. **Day 1:** Run baseline on 3 projects
2. **Day 2-3:** Try 3 mutations, paired eval
3. **Day 4-5:** Scale to 10 projects
4. **Day 6-7:** Submit if F1 > 0.5

## The Goal

**Not to build a perfect agent. To build a process that makes agents better over time.**

The subnet market is the evaluator. Our job is to:
1. Deploy candidates
2. Read their scores
3. Understand why some win and some lose
4. Evolve better candidates

This is genetic programming with Bittensor as the fitness landscape.
