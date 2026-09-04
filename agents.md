# AGENTS.md — Mining Goal

## The Singular Goal

**Get a competitive Bitsec miner that can beat the benchmark.**

## Current Status

| Project | DR | Status |
|---------|-----|--------|
| Superposition | 54.5% | Works (but requires ground truth) |
| lambowin | 0% | Broken |
| loopfi | 0% | Not tested |
| fenix-finance | 0% | Not tested |

**Target:** >50% DR across all projects without knowing ground truth.

## What's Blocking

1. **Generic prompting doesn't work** — need project-specific approach
2. **API unreliable** — sometimes returns empty responses
3. **No automated prompt generation** — can't determine what to ask for

## What I'm Doing Now

Building a miner that:
1. Analyzes code structure
2. Identifies high-risk areas automatically
3. Generates targeted prompts
4. Finds vulnerabilities without ground truth

## Don't Ask

Just work. Deliver results.
