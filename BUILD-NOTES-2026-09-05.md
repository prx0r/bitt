# Build Notes — September 5, 2026

## Session Summary

Full-day deep dive into BitSec SN60 miner architecture, ScaBench scoring, and vulnerability detection pipeline design. Started at 0% DR, built up to 50% on single run, then built proper 5-phase pipeline.

## What We Built Today

### 1. Content Fallback Parser (simple-v1 patch)
- **Problem:** Model returns vulns as text content, not tool calls
- **Fix:** Added `_parse_vulns_from_content()` to parse JSON from text responses
- **Result:** 0 → 34 vulns found on Superposition (from 0)
- **Key learning:** The model DOES find vulns, it just doesn't always use tool calls

### 2. Proxy URL Fix
- **Problem:** Mapper agent used `http://localhost:8087/inference` but code appended `/inference`, creating double URL
- **Fix:** Changed PROXY to `http://localhost:8087`
- **Key learning:** Always verify the actual URL being sent

### 3. Architecture Mapper (Multi-Agent Phase 1)
- **What:** Reads project structure, identifies contracts and relationships
- **Result:** Found 18 contracts, 6 high-risk areas on Superposition
- **Key learning:** Architecture mapping produces useful project understanding

### 4. Scout/Senior Agent (Two-Pass)
- **Architecture:** Regex static analysis → Scout pass → Senior pass
- **Result:** 50% DR on Superposition (single lucky run), 0% on batch
- **Key learning:** Non-deterministic — same agent gets different results each run

### 5. Pipeline Agent v1 (5-Phase)
- **Phases:** Static → Arch Map → Targeted Trace → Verify → Correlate
- **Result:** 25 min runtime, 94 candidates, 1 confirmed
- **Key learning:** Pipeline architecture is correct, prompts need tuning

### 6. Pipeline Agent v2 (Improved)
- **Fixes:** Less aggressive verification, implementation-first region selection
- **Status:** Running, results pending

## Key Discoveries

### Scoring System
- **Scorer model:** Kimi-K3-TEE (Moonshot AI), not GPT-5
- **PASS = 100% detection rate** (binary, no partial credit)
- **Only highs-only dataset used** for production scoring
- **Non-deterministic** — same agent can score differently across runs

### Official Baseline
- **GPT-5 baseline also scores 0%** on Superposition
- Baseline found 9 vulns but they're not the 2 expected ones
- Finding vulns ≠ finding THE SPECIFIC vulns the benchmark expects

### What Works
- Static analysis pre-filtering (regex patterns)
- Two-pass Scout/Senior architecture
- Architecture mapping for project comprehension
- Content fallback for non-tool-call reports

### What Doesn't Work
- Single-pass per-file analysis
- Generic prompts ("find vulnerabilities")
- Word-overlap scoring (too strict)
- Phase 3 verification too aggressive

### The Gap
- Agent finds real vulnerabilities but wrong TYPE
- Ground truth: business logic bugs (slippage, refund math)
- Agent finds: implementation bugs (access control, overflow)
- Gap requires understanding protocol invariants

## Files Created/Modified Today

| File | Status | Purpose |
|------|--------|---------|
| `mining/sn60/candidates/simple-v1/agent.py` | Modified | Content fallback parser |
| `mining/sn60/candidates/scout-senior/agent.py` | New | Two-pass Scout/Senior |
| `mining/sn60/candidates/scout-senior/evolve.py` | New | Evolution loop |
| `mining/sn60/candidates/pipeline-v1/agent.py` | New | 5-phase pipeline |
| `cge/bitsec/evolution_runner.py` | New | CGE evolution runner |
| `BUG-REPORT.md` | New | 4 bugs found and fixed |
| `GOAL.md` | New | Goal and protocol |
| `MULTI-AGENT-ARCHITECTURE.md` | New | Multi-agent design |
| `MULTI-AGENT-RESULTS.md` | New | Multi-agent experiment results |
| `STATUS-2026-09-05.md` | New | Overall status |
| `WHAT_WE_WERE_DOING_WRONG.md` | New | Official docs analysis |
| `EVOLUTION-REFERENCE.md` | New | Complete reference sheet |

## Results Summary

| Agent | Superposition DR | Method | Runtime |
|-------|-----------------|--------|---------|
| simple-v1 (original) | 0% | Per-file tool-use | ~5 min |
| simple-v1 (patched) | 0-50% | Content fallback | ~5 min |
| Scout/Senior | 0-50% | Two-pass static+LLM | ~3 min |
| Pipeline v1 | 0% | 5-phase architecture | ~25 min |
| Pipeline v2 | ? | Improved verification | Running |

## Key Metrics

- **7 projects tested** across all agents
- **104 total findings** (simple-v1 patched)
- **11 total findings** (Scout/Senior batch)
- **1 finding** (Pipeline v1)
- **0% batch DR** across all agents (non-deterministic single runs hit higher)

## What's Next

1. Pipeline v2 results (better verification)
2. Evolution loop to tune prompts
3. Run on more projects for consistency
4. Submit to BitSec for real validator feedback
5. Consider Slither installation for proper static analysis
