# Critical Issue — Model Finds Vulns But Doesn't Report Them

## The Problem

The model (mimo-v2.5) finds real vulnerabilities in reasoning_content but reports empty arrays in tool calls.

**Evidence:**
- Superposition: 78 vulnerabilities found in report, but 0 submitted via tool calls
- Lambowin: 0 vulnerabilities found (model analyzes but doesn't report)
- Reasoning shows detailed analysis of inverted checks, stale approvals, etc.

## Root Cause

The model is doing deep analysis in reasoning but not converting findings to structured output. This is likely because:

1. **Reasoning consumes token budget** — model generates 3000-4000 tokens of analysis
2. **Tool calls come after reasoning** — but tokens are exhausted
3. **Model prefers reasoning over tool calls** — it's analyzing, not reporting

## The Fix

The model needs to be instructed to:
1. Keep reasoning short (<1500 tokens)
2. Report findings IMMEDIATELY after analyzing each file
3. Not try to be too thorough in reasoning

## Current State

| Project | Files | Findings | High/Critical |
|---------|-------|----------|---------------|
| Superposition | 57 | 78 | 18 |
| Lambowin | 7 | 0 | 0 |

## Next Steps

1. Test with different models (not mimo-v2.5)
2. Try different prompting strategies
3. Consider using the official baseline as-is (it works)
