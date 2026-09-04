# Improvement Plan — mw-audit-v1

## Current State

| Metric | Official Baseline | mw-audit-v1 |
|--------|-------------------|-------------|
| Files analyzed | 57 | 57 |
| Total findings | 87 | 3 |
| High/Critical | 14 | 3 |
| Inference calls | 690 | 477 |
| Report calls | 75 | 6 |
| Findings submitted | 87 | 1 |

## Root Cause Analysis

**Why does official baseline submit 87 findings while mw-audit-v1 submits 1?**

1. **Report frequency**: Official baseline makes 75 report calls, mw-audit-v1 makes 6
2. **Submission pipeline**: mw-audit-v1 accumulates findings then reports (gets truncated)
3. **Token budget**: mw-audit-v1 runs out of tokens before reporting

## Priority Fixes

### P1: Match Official Baseline's Report Pattern
The official baseline reports findings frequently (75 calls for 87 findings = ~1 finding per call).
mw-audit-v1 should do the same.

**Fix**: After analyzing each file, immediately report findings. Don't accumulate.

### P2: Early Stopping When Context Full
The official baseline stops when context is full. mw-audit-v1 continues until timeout.

**Fix**: Track context usage, stop at 80% budget.

### P3: Deduplication
The official baseline doesn't report duplicates. mw-audit-v1 reports the same finding twice.

**Fix**: Track seen findings by title hash.

## Expected Improvement

If mw-audit-v1 matches official baseline's report pattern:
- Report calls: 6 → 75
- Findings submitted: 1 → ~87
- Detection rate: 27% → ~80%

## Next Steps

1. Implement P1 (report after each file)
2. Test on Superposition
3. Measure improvement
4. If improvement is significant, test on other projects
