# Mining AGENTS.md — Evolutionary Mining via Bittensor Markets

## Focus Order

**NOW: SN62 (Ridges) + SN60 (Bitsec) — parallel**
- Both are LLM-based agents analyzing code
- Bitsec pipeline transfers directly to SN62
- Same pattern: read task → build prompt → call LLM → parse response

**NEXT: SN91 (Cascade) — after SN62/Bitsec**
- Fewest miners (12), decent payout (9.5 TAO/day)
- Time series data generation
- Simpler than code analysis

**LATER: SN19, SN44 — heavier infrastructure**
- SN19: needs full RPC node
- SN44: needs GPU for computer vision

## The Pattern (Same for SN62 + Bitsec)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   INPUT              LLM PIPELINE           OUTPUT              │
│                                                                 │
│   SN62: Problem    → Scout/Strategist/   → Unified diff        │
│         + repo       Analyst/Verifier      (code fix)          │
│                                                                 │
│   Bitsec: Code     → Scout/Strategist/   → Findings JSON       │
│           (.sol)      Analyst/Verifier      (vulnerabilities)   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Same core:**
1. Read task
2. Build prompt with context
3. Call LLM (free via CF Workers AI)
4. Parse structured response
5. Return output

**Different:**
- SN62: output is unified diff (code fix)
- Bitsec: output is JSON findings (vulnerability list)

## What We Already Have

### From /root/bitt (Bitsec)
- **LLM pipeline** — Scout/Strategist/Analyst/Verifier (4 phases)
- **Free inference** — CF Workers AI (llama-3.3-70b)
- **4 process arms** — default, hound, cloudflare-audit, tob-stack
- **ScaBench evaluation** — 31 projects, 555 vulnerabilities
- **25 repos cloned** — `/root/bitt/data/scabench-repos/`
- **Learning loop** — failure analysis → mutation → paired evaluation
- **Ledger** — append-only, chain-hashed, immutable
- **Pool knowledge** — doctrine + skills

### From /root/bitt/subnets/sn62-ridges
- **Repo cloned** — full miner/validator codebase
- **agent.py interface** — `agent_main(input) -> str`
- **Local testing** — `ridges miner run-local`
- **Submission** — `ridges upload --file agent.py`

### From /root/cg (cogymkernel)
- **10 evolution recipes** — random_search, elitist_mutation, tournament, etc.
- **33 reasoning styles** — 16 families
- **Content-addressed receipts** — blake3
- **Quality gates** — Wilson/bootstrap stats

## What to Do

### Phase 1: Bitsec (get working end-to-end)
- [ ] Get bitsec agent running on ScaBench
- [ ] Measure detection rate, precision, F1
- [ ] Identify failure modes
- [ ] Run learning loop (propose mutations, evaluate)

### Phase 2: SN62 (transfer bitsec → Ridges)
- [ ] Write agent.py using bitsec LLM pipeline
- [ ] Change output format to unified diff
- [ ] Test locally with `ridges miner run-local`
- [ ] Score against real tasks
- [ ] Iterate until score > 0.5

### Phase 3: SN91 (after SN62/Bitsec)
- [ ] Understand cascade mechanism
- [ ] Build data generator
- [ ] Test locally
- [ ] Submit

## Key Files

| File | Purpose |
|------|---------|
| `workers/bitsec/miner_v5.py` | LLM pipeline (4 phases) |
| `workers/bitsec/cloudflare_harness.py` | Free inference |
| `workers/bitsec/learning_loop.py` | Failure analysis + mutation |
| `workers/bitsec/scaBench_eval.py` | Evaluation |
| `subnets/sn62-ridges/agent.py` | SN62 interface |
| `mining/OBJECTIVE-PROCESS-SN62.md` | SN62 process |
