# Checkpoint 1 — Summary

## What We Achieved

**Superposition: 54.5% DR** (two-round specific prompting)
- 6 out of 11 vulns found
- Requires knowing ground truth vulnerability types

**Other projects: 0% DR** (generic approach)
- lambowin: 0% DR
- loopfi: 0% DR
- fenix-finance: 0% DR

## Key Insight

**Project-specific prompting works. Generic prompting doesn't.**

The winning approach on Superposition asked for specific vulnerability types that matched the ground truth. This doesn't scale to new projects without knowing the ground truth.

## What Needs to Happen

### 1. Automated Prompt Generation
- For each project, automatically determine what vulnerability types to ask for
- Use static analysis to identify high-risk areas
- Use call graph to find dangerous patterns

### 2. Multi-Round Strategy
- Round 1: Broad scan for common vulnerability types
- Round 2: Focus on high-risk areas identified in Round 1
- Round 3: Deep dive into specific functions

### 3. Learning Loop
- Track which prompts work for which projects
- Learn from failures
- Evolve strategies over time

## Files Created

| File | Purpose |
|------|---------|
| `mining/sn60/CANONICAL-SUPERPOSITION.md` | Winning approach for Superposition |
| `mining/sn60/strategy.py` | Strategy framework |
| `mining/sn60/REFERENCE-AGENT.md` | Scout/Senior pattern |
| `workers/bitsec/experiment_runner.py` | Experiment logging |
| `workers/bitsec/run_log.py` | Run logging |

## Next Steps

1. Build automated prompt generation
2. Test on more projects
3. Wire to CGE for evolution
4. Build canonical miners for each benchmark
