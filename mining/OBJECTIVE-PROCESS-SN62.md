# Objective Process — SN62 Ridges (First Subnet)

## Goal

Produce a miner good enough to get emissions on SN62 Ridges. Do this perfectly once, then repeat.

## What We Have (from bitsec)

**Reusable Components:**
1. LLM pipeline (Scout/Strategist/Analyst/Verifier)
2. Free inference harness (CF Workers AI)
3. Evaluation framework
4. Learning loop for improvement

**Key Files:**
- `workers/bitsec/cloudflare_harness.py` — Free LLM calls
- `workers/bitsec/miner_v5.py` — Multi-phase pipeline
- `workers/bitsec/learning_loop.py` — Failure analysis + mutation

## SN62 Ridges Interface

**Input:** `agent_main(input)` receives dict with:
- `input["problem_statement"]` — the coding problem
- `/repo` — mounted repository
- `SANDBOX_PROXY_URL` — for LLM inference
- `RIDGES_MAX_COST_USD` — cost budget
- `AGENT_TIMEOUT` — time limit

**Output:** Unified diff string (like `git diff HEAD`)

**Evaluation:** Test cases pass/fail (deterministic)

## The Process

### Phase 1: Build Agent (1-2 hours)

1. **Read problem statement** from input
2. **Read repo code** from /repo
3. **Build prompt** with problem + code context
4. **Call LLM** via SANDBOX_PROXY_URL (or CF Workers AI for local)
5. **Parse response** into unified diff
6. **Return diff**

### Phase 2: Test Locally (2-4 hours)

1. **Clone SN62 repo** (already done)
2. **Install dependencies** (`uv sync --extra miner`)
3. **Configure inference** (OpenRouter key)
4. **Run local tests** (`ridges miner run-local`)
5. **Score against tasks** (0-1 score per task)
6. **Iterate** based on results

### Phase 3: Submit (when ready)

1. **Register on subnet** (requires TAO)
2. **Upload agent** (`ridges upload --file agent.py`)
3. **Monitor scoring** on platform
4. **Track emissions**

### Phase 4: Learn and Evolve

1. **Read validator scores** from on-chain
2. **Feed to CGE** as fitness signals
3. **CGE proposes mutations** (prompt changes, model changes, etc.)
4. **Deploy new candidates**
5. **Repeat**

## Success Criteria

**Minimum viable:**
- Agent produces valid unified diffs
- Local tests score > 0.5
- Agent runs within cost/timeout limits

**Target:**
- Agent scores in top 50% of miners
- Consistent emissions
- Learning loop improving over time

## Key Insight

**The subnet market IS the objective function.**

We don't need to:
- Build perfect miners
- Understand every mechanism
- Register immediately

We DO need to:
- Build agents that work locally
- Test against real tasks
- Submit and get scored
- Learn from results

## Next Steps

1. **Write agent.py** for SN62 using bitsec's LLM pipeline
2. **Test locally** with `ridges miner run-local`
3. **Score against tasks**
4. **Iterate** until score > 0.5
5. **Then** worry about registration and submission
