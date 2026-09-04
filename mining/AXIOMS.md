# AXIOMS.md — How to Mine Any Bittensor Subnet

## The Core Axiom

**Bittensor subnet markets are the evaluator. Your job is to build agents that win those markets.**

Not: build perfect miners. Not: understand every mechanism. Not: register wallets.

**Build agents that get emissions.**

---

## Axiom 1: Read the Official Repo First

Every subnet has an official repo. Read it. The repo is the source of truth, not the docs.

```bash
# Find the official repo
git clone https://github.com/<subnet-owner>/<subnet-name>.git

# Read the miner code
cat miner/agent.py

# Read the validator code
cat validator/evaluator.py

# Understand the interface
grep -n "agent_main\|def main\|def run" miner/*.py
```

**What I learned:** I spent days building custom evaluators before reading the official repo. The official repo already has everything I needed.

---

## Axiom 2: The Interface is Simple

Every subnet miner has the same pattern:

```python
def agent_main(input: dict) -> dict:
    """
    Input: task-specific data
    Output: structured result
    """
    # 1. Read the input
    # 2. Do the work
    # 3. Return the result
```

**Bitsec:** `agent_main()` with no args, returns `{"vulnerabilities": [...]}`
**Ridges:** `agent_main(input)` returns unified diff
**Cascade:** `agent_main(input)` returns time series data

**What I learned:** I overcomplicated this. The interface is always simple.

---

## Axiom 3: Use the Official Evaluation

Never build your own evaluator. Use the official one.

```bash
# Wrong
python3 my_evaluator.py  # Custom, wrong, wastes time

# Right
python3 bitsec.py miner run-no-docker  # Official, correct, fast
```

**What I learned:** My custom evaluator had label leakage and wrong scoring. The official evaluator is the only one that matters.

---

## Axiom 4: The Objective is Binary

For Bitsec:
- Find ALL high/critical vulnerabilities
- In at least 2/3 runs per project
- Pass 2/3 of all projects

Not: maximize F1. Not: maximize detection rate. Not: minimize false positives.

**Binary:** all-found or not-found.

**What I learned:** I was optimizing the wrong metric. F1 is diagnostic, not the objective.

---

## Axiom 5: Methodology > Prompts

Don't hack prompts. Build methodology.

**Wrong:**
```
Prompt: "Find reentrancy in withdraw function"
```

**Right:**
```
1. Map attack surface (entry points, roles, value flows)
2. Investigate each area systematically
3. Verify findings before reporting
4. Report only high/critical with evidence
```

**What I learned:** Prompt hacking gets you banned (hard-steering). Methodology gets you emissions.

---

## Axiom 6: Repeated Evaluation is Mandatory

Never evaluate a candidate once. Run it multiple times.

```python
# Wrong
result = run_once(candidate)  # Could be lucky/unlucky

# Right
results = [run(candidate) for _ in range(9)]  # Measure reliability
```

**What I learned:** A candidate that finds all vulns 55% of the time is worse than one that finds them 80% of the time. Reliability matters.

---

## Axiom 7: Sealed Holdouts Prevent Overfitting

Test on projects NOT in the benchmark. Prove your methodology generalizes.

```python
# Layer A: Official benchmark (4 projects)
# Layer B: Sealed holdout (10-30 projects)

# Promotion requires:
# - BitSec score improves
# AND
# - Holdout doesn't regress
```

**What I learned:** Without holdouts, you optimize for the benchmark, not for general capability.

---

## Axiom 8: Log Everything

Every experiment, every run, every result. Disk is cheap. Memory is not.

```python
log_run(run_id, subnet, method, model, results, findings)
```

**What I learned:** I couldn't reproduce my results because I didn't log properly.

---

## Axiom 9: Time is the Scarcest Resource

Every hour spent on the wrong approach is an hour not spent on the right one.

**Wrong approach:**
- Build custom evaluators
- Optimize F1
- Prompt with known vulnerabilities

**Right approach:**
- Use official sandbox
- Optimize project pass
- Build methodology

**What I learned:** I wasted days on the wrong approach before getting corrected.

---

## Axiom 10: The Learning Loop is the Moat

The subnet market gives you:
- Code → Agent → Report → Ground truth → Missed findings

That's the ideal learning signal. Use it.

```
1. Run candidate on project
2. Score against ground truth
3. Identify missed findings
4. Analyze why they were missed
5. Mutate methodology
6. Repeat
```

**What I learned:** This is genetic programming with Bittensor as the fitness landscape.

---

## The Fastest Path to Any Subnet

### Step 1: Read the Official Repo (1 hour)
```bash
git clone <official-repo>
cat miner/agent.py
cat validator/evaluator.py
```

### Step 2: Understand the Interface (30 minutes)
- What does `agent_main()` expect?
- What does it return?
- How is it evaluated?

### Step 3: Run the Official Baseline (2 hours)
```bash
python3 bitsec.py miner run-no-docker
```

### Step 4: Identify Failure Modes (2 hours)
- Which vulns are missed?
- Why are they missed?
- What's the failure taxonomy?

### Step 5: Build Methodology Improvements (4-8 hours)
- Architecture mapping
- Hypothesis-driven investigation
- Cross-file analysis
- Independent verification

### Step 6: Test with Repeated Evaluation (4 hours)
- Run 9+ times per project
- Measure detection probability
- Optimize for reliability

### Step 7: Build Sealed Holdout (4 hours)
- Test on projects NOT in benchmark
- Prove generalization
- Prevent overfitting

### Step 8: Submit (1 hour)
```bash
python3 bitsec.py miner submit --wallet <wallet>
```

**Total: 1-2 days per subnet**

---

## References

### Official Docs
- Bitsec: https://docs.bitsec.ai
- Ridges: https://docs.ridges.ai
- Bittensor: https://docs.bittensor.com

### Key Files
- `subnets/sn60-bitsec/HIGHSIGNAL.md` — the correct path
- `subnets/sn60-bitsec/IMPORTANT.md` — what I was doing wrong
- `subnets/sn60-bitsec/AGENTS.md` — the singular goal
- `mining/sn60/candidates/official-baseline/agent.py` — official baseline
- `mining/sn60/candidates/mw-audit-v1/agent.py` — improved methodology

### Experiences
- Superposition: 54.5% DR (two-round specific prompting)
- lambowin: 0% DR (API reliability issues)
- loopfi: 0% DR (not tested)
- fenix-finance: 0% DR (not tested)

### Key Insight
The winning approach on Superposition (81.8% DR) was prompt hacking. It works but gets banned. The real approach is methodology improvement.

---

## Summary

**The game is simple:**
1. Read the official repo
2. Understand the interface
3. Run the baseline
4. Identify failures
5. Improve methodology
6. Test with repeated evaluation
7. Build sealed holdout
8. Submit

**The game is hard:**
- API reliability
- Docker setup
- Hard-steering rules
- Repeated evaluation cost
- Sealed holdout complexity

**But it's the only game that works.**
