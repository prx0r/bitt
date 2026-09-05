# BitSec Evolution Reference Sheet

## The Benchmark

### What ScaBench Actually Measures
- **NOT** "find vulnerabilities in general"
- **YES** "find THESE SPECIFIC vulnerabilities that audit contest judges confirmed"
- Ground truth = real bugs found by human auditors in Code4rena/Sherlock/Cantina contests
- Each project has 2-15 expected high/critical vulns (varies by project)

### Scoring Pipeline
```
Agent finds vulns → Report JSON → Kimi-K3-TEE LLM judge → matches against ground truth → detection_rate
```

### Pass/Fail
- PASS = detection_rate == 1.0 (ALL expected high/critical found)
- FAIL = any expected vuln missed
- 3 runs per project, 2/3 must PASS
- Score = passed_projects / total_projects

### Production Dataset
- File: `validator/curated-highs-only-2025-08-08.json`
- Only HIGH and CRITICAL vulns count
- Superposition: 2 expected highs
- Loopfi: ~7 expected highs
- Varies per project

### The Scorer (Kimi-K3-TEE)
- Model: `moonshotai/Kimi-K3-TEE:throughput` via Chutes
- Temperature: 0.6
- Non-strict mode (confidence >= 0.75 to match)
- Chunked: compares 10 findings at a time
- Prefiltered by lexical similarity before LLM judging

### What the Judge Looks For
1. Correctly identifies the CONTRACT
2. Correctly identifies the FUNCTION
3. Accurately describes the CORE SECURITY ISSUE
4. Accurately describes the CONSEQUENCES

---

## The Agent Architecture

### Entry Point
```python
def agent_main(project_dir="/app/project_code", inference_api=None) -> dict:
```

### Return Format
```json
{
  "project": "...",
  "files_analyzed": 15,
  "total_vulnerabilities": 8,
  "vulnerabilities": [{
    "title": "Reentrancy in withdraw()",
    "description": "Detailed explanation...",
    "vulnerability_type": "reentrancy",
    "severity": "critical|high|medium|low",
    "confidence": 0.95,
    "location": "withdraw() in Vault.sol",
    "file": "src/Vault.sol"
  }],
  "token_usage": {"total_input": 50000, "total_output": 3000}
}
```

### Tools Available
1. `list_files(directory)` → file listing
2. `read_file(file_path)` → file content
3. `report_vulnerabilities(vulnerabilities[])` → submit findings

### Container Constraints
- Memory: 512 MB
- CPU: 2.5 cores
- PIDs: 64
- Timeout: 30 minutes
- Max findings evaluated: 100

### File Discovery
- Patterns: `*.sol`, `*.vy`, `*.cairo`, `*.rs`, `*.move`
- Excluded dirs: testing, mocks, examples, interfaces, script, broadcast, libraries
- Excluded files: anything with "test" in name

---

## What We Know Works

### Our Agent Advantages
1. **No `response_format=text`** — official agent has this bug (kills tool calls)
2. **Content fallback parser** — catches vulns returned as text, not just tool calls
3. **Longer timeout** — 120s vs 30s for inference

### Architecture Mapping (Multi-Agent Phase 1)
- Reads project structure, identifies contracts and relationships
- Found 18 contracts, 6 high-risk areas on Superposition
- Output: structured JSON with contract map and risk areas
- **Works: produces useful project understanding**

### Vulnerability Hunting (Multi-Agent Phase 2)
- Uses architecture map for targeted analysis
- Found 28 specific, architecture-aware vulnerabilities
- **Works: produces more specific findings than single-agent**

---

## What We Know Doesn't Work

### Single-Agent Per-File Analysis
- Finds generic vulns (reentrancy, overflow, access control)
- Misses business logic bugs (slippage, refund math, pool creation)
- 0% detection rate against ground truth

### Generic Prompting
- "Analyze code for vulnerabilities" → generic findings
- Need project-specific understanding
- Need business invariant analysis

### Word-Overlap Scoring (Our Approximation)
- Titles are naturally different from ground truth
- Even GPT-5 baseline has 0% word overlap with expected vulns
- Must use LLM-based semantic matching

---

## What We Need to Figure Out

### The Business Logic Gap
The expected vulns are things like:
- "Users are incorrectly refunded when liquidity is insufficient"
- "No slippage control when withdrawing a position"
- "createPoolD650E2D0 mismatch between Solidity and Stylus"

These require understanding:
1. What the protocol is supposed to do
2. What invariants must hold
3. Where the code violates those invariants

### Possible Approaches

#### Approach A: Protocol Reader + Invariant Checker
```
Phase 0: Read protocol docs/README/comments → extract invariants
Phase 1: Map architecture (already works)
Phase 2: For each invariant, trace code paths
Phase 3: Find violations
Phase 4: Report with exact location
```

#### Approach B: Two-Pass Analysis
```
Pass 1: Broad scan (current approach) → find implementation bugs
Pass 2: Focused deep-dive on high-risk areas → find logic bugs
Combine both sets of findings
```

#### Approach C: Contrast with Baseline
```
1. Run official baseline on same project
2. Compare: what did it find that we didn't?
3. Analyze why it found those specific bugs
4. Apply those insights to our prompts
```

#### Approach D: Iterative Questioning
```
1. Ask: "What does this protocol do?"
2. Ask: "What could go wrong?"
3. Ask: "Where specifically in the code?"
4. Ask: "What's the impact?"
Each question narrows the search
```

---

## Mutation Strategy for CGE

### Parameters to Mutate
| Parameter | Range | Why |
|-----------|-------|-----|
| System prompt | 10 variants | Affects what model focuses on |
| Analysis phases | 0-4 phases | How many passes over the code |
| Seed strategy | list-only, content-only, both | What context model gets first |
| Tool loop turns | 2, 3, 5 | How deep model can explore |
| Max tokens | 4096, 8192, 16384 | Prevents token starvation |
| File chunking | whole file, first 8000, first 4000 | How much code model sees |
| Concurrency | 1, 2, 4 threads | Speed vs quality tradeoff |
| Report threshold | 0.3, 0.5, 0.7 | Minimum confidence to report |
| Priority ordering | by file size, by risk, random | Which files get analyzed first |
| Architecture mapping | on/off | Whether to do Phase 1 |

### Fitness Function
```
fitness = detection_rate * 100  (0-100 scale)
```

Tiebreaker: fewer false positives (precision)

### Selection
- Population: 6 strategies
- Tournament: top 2 survive
- Each produces 2 mutated children
- Generation 0: random initialization
- Max generations: 10

### Budget
- 6 strategies × 1 project × ~50 LLM calls = ~300 calls per generation
- At 3s/call = ~15 minutes per generation
- 10 generations = ~2.5 hours total
- All free via proxy (mimo-v2.5)

---

## Logged Test Protocol

### Every Run Logs
```json
{
  "strategy_id": "gen0-3",
  "project": "code4rena_superposition_2025_01",
  "timestamp": "...",
  "params": { "prompt": "...", "turns": 3, "max_tokens": 8192 },
  "findings": [...],
  "detection_rate": 0.5,
  "precision": 0.3,
  "f1": 0.375,
  "matched": ["H-02", "H-03"],
  "missed": [],
  "false_positives": [...],
  "token_usage": { "input": 50000, "output": 3000 },
  "duration_seconds": 120
}
```

### Test Projects (Use 2 for speed)
1. **Superposition** — 2 expected highs, well-understood
2. **Lambowin** — different project type, tests generalization

### Validation Criteria
- detection_rate > 0 → improvement over baseline (0%)
- detection_rate >= 0.5 → serious contender
- detection_rate == 1.0 → PASS on that project

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `mining/sn60/candidates/simple-v1/agent.py` | Our working agent |
| `subnets/sn60-bitsec/sandbox-v2/miner/agent.py` | Official agent (reference) |
| `subnets/sn60-bitsec/sandbox-v2/validator/scorer.py` | Official scorer |
| `subnets/sn60-bitsec/sandbox-v2/validator/evaluator.py` | Pass/fail logic |
| `subnets/sn60-bitsec/sandbox-v2/validator/curated-highs-only-2025-08-08.json` | Ground truth |
| `cge/bitsec/evolution.py` | CGE evolution engine |
| `cge/bitsec/world.py` | ScaBench data + scoring |
| `cge/bitsec/real_eval.py` | Real LLM evaluation |
| `workers/bitsec/cloudflare_harness.py` | Free inference |
| `data/architecture/` | Architecture maps |
| `data/hunter-results/` | Hunter findings |
| `data/scores-v2/` | LLM-matched scores |
| `data/live-results-*/` | Raw agent outputs |
