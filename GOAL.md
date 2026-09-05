# BitSec Evolution Goal & Protocol

## The Goal

**Achieve >80% detection rate across ScaBench curated dataset using mutated miner strategies.**

Current baseline: ~34 vulns found on Superposition (5 high/critical out of 2 expected highs). The agent finds real vulns but doesn't match ground truth titles well enough to score.

The path: evolve the agent's analysis strategy through logged, scored runs — mutating prompts, tooling, and approach — and selecting for higher detection rates.

---

## Protocol: Staggered Autonomous Runs

### RAM Budget

- System: 7.6GB total, ~3.8GB available
- Each agent process: ~50-80MB (Python + requests)
- Each proxy request: negligible (FastAPI async)
- **Max concurrent agent processes: 2** (safety margin for OS + Docker)
- Proxy handles 8 concurrent requests internally

### Run Staggering

```
RUN A (Project N)     ████████████████
RUN B (Project N+1)       ████████████████
                         ↑
                    Start B when A is 30% through
                    (ensures overlap without RAM pressure)
```

1. Start Run A on Project[i]
2. Wait 30 seconds (let API calls begin, RAM settle)
3. Start Run B on Project[i+1]
4. When either finishes, start next project
5. Monitor with: `free -h` every 60s
6. If RAM > 6GB used: drop to 1 concurrent run

### Scoring

Each run produces `agent_report.json`. Score against ground truth:

```
Score = (matched_findings / total_expected_findings) × 100
```

Where "matched" = our finding title overlaps ≥30% with ground truth title (word-level Jaccard).

This is approximate — the official scorer uses LLM matching. But it's fast and free for iteration.

### Mutation Strategy

Mutations apply to the agent's analysis approach, NOT ground truth:

| Parameter | Mutation Range |
|-----------|---------------|
| System prompt | Rotate through 6 styles (direct, CoT, per-file, cross-file, ensemble, decomposition) |
| max_tokens | 4096, 6144, 8192, 12288 |
| Temperature | 0.0, 0.1, 0.3, 0.5 |
| Turns per file | 2, 3, 5 |
| File chunking | Whole file, first 3000 chars, first 5000 chars |
| Dedup strategy | ID-based, title-similarity, none |
| Content fallback | On (current patch) / Off |

### Selection

- Evaluate each strategy on 3 projects (fast)
- Keep top 2 strategies
- Mutate each into 2 children
- Repeat

### Logging

Every run logs to:
```
/root/bitt/data/evolution/
  gen-{N}/
    strategy-{id}.json    # strategy params
    results/              # agent_report.json per project
    score.json            # detection rate per project
    meta.json             # timestamp, parent, mutation applied
```

---

## Failure Conditions (Stop and Report)

1. **RAM > 6.5GB** — drop to 1 run, report to user
2. **Proxy 502/503 errors > 3 in a row** — API limit hit, stop
3. **3 consecutive generations with no improvement** — strategy plateau, need new mutation approach
4. **Agent finds 0 vulns on any project** — regression, investigate
5. **Any unhandled exception** — log and continue, but report if >5 in one generation

---

## What We Know (From Previous Runs)

### Working
- simple-v1 agent finds real vulnerabilities (104 across 7 projects)
- Content-as-JSON fallback patch recovers vulns when tool calls fail
- Proxy on port 8087 works with mimo-v2.5
- ScaBench repos are cloned and available

### Not Working
- Model returns vulns as TEXT content, not tool calls (patched with fallback)
- Title wording doesn't match ground truth (semantic gap)
- Fenix Finance caused 502 error (large project, API timeout?)
- Only 2 expected high/critical vulns for Superposition — scoring is project-dependent

### Unknown
- How the official scorer (LLM-based) would rate our findings
- Whether mutations actually improve detection rate
- Whether 80% is achievable with mimo-v2.5 alone
- Whether the official Docker sandbox works with our patched agent

---

## Execution Order

### Phase 1: Baseline (NOW)
- [x] Run patched agent on 7 projects — DONE (104 vulns)
- [ ] Score against ground truth for each project
- [ ] Identify which projects have the most ground truth to score against

### Phase 2: Mutation Round 1
- [ ] Create 4 strategy variants (different prompts/params)
- [ ] Run each on 3 projects (staggered, 2 concurrent)
- [ ] Score and rank
- [ ] Select top 2

### Phase 3: Mutation Round 2
- [ ] Mutate top 2 strategies (2 children each)
- [ ] Run on 3 projects
- [ ] Score and rank
- [ ] Check for improvement plateau

### Phase 4: Scale
- [ ] Take best strategy
- [ ] Run on all available projects
- [ ] Score comprehensively
- [ ] If <80%, iterate. If >80%, prepare for official sandbox.

---

## Return to User When

1. Baseline scoring is complete
2. Any of the failure conditions trigger
3. After each mutation round (report improvement/regression)
4. Before scaling to all projects (confirm strategy is improving)
