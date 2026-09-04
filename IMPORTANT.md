# IMPORTANT.md — Complete Lessons Learned

## Critical Mistakes (Never Repeat)

### 1. Building Custom Evaluators
**WRONG:** Built `evaluator.py`, `scaBench_eval.py` with wrong scorers.
**RIGHT:** Use official BitSec sandbox. The repo is the source of truth.

### 2. Prompt Hacking
**WRONG:** Asked for specific vuln types from ground truth.
**RIGHT:** Build methodology, not prompts. Don't hard-steer.

### 3. Scaling Failing Approaches
**WRONG:** Ran 2-hour test after 175s test failed.
**RIGHT:** Fix approach first, then scale.

### 4. Blocking on Long Tasks
**WRONG:** Ran Python scripts that blocked attention.
**RIGHT:** Always use nohup. Never block.

### 5. Not Defining Success Criteria
**WRONG:** Ran "test" without knowing what success looks like.
**RIGHT:** Define success before testing.

### 6. Not Monitoring During Runs
**WRONG:** Waited until end to check results.
**RIGHT:** Check logs every 30s.

### 7. Not Documenting Failures
**WRONG:** Moved on after failures without documenting.
**RIGHT:** Document every failure. It's data.

## What Actually Works

### 1. Official Baseline
- 87 vulns on Superposition
- Simple, direct, works
- Use as starting point

### 2. Simple Agent
- 318 vulns across 4 projects
- Simpler is better
- Don't overthink

### 3. Token Budget Fix
- Increase max_tokens to 8192
- Add "Keep reasoning under 1500 tokens"
- Prevents token starvation

### 4. Response Format Fix
- Remove response_format={"type": "text"}
- Proxy defaults to json_object
- Allows tool calls to work

## The Pattern

```
WRONG: Test fails → Run longer test → Still fails → Waste time

RIGHT: Test fails → Analyze why → Fix → Retest → Measure improvement
```

## Time is the Scarcest Resource

Every minute spent on a failing approach is a minute not spent on the right one.

## What We Achieved

- 318 vulnerabilities found across 4 projects
- 54 high/critical findings
- Working agent that finds real vulns
- Understanding of what works and what doesn't

## What's Next

1. Test final run on all 4 projects
2. Optimize for BitSec submission format
3. Create proper agent_main() entry point
4. Test in Docker sandbox
5. Submit to BitSec
