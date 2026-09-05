# What We Were Doing Wrong — Official Source Analysis

## The #1 Thing We Got Wrong

**We thought the benchmark was solvable with current approaches.**

The official docs say:

> "This is a **hard benchmark**. Current SOTA performance is less than 10% using GPT-5. If a miner's agent solves all 4 codebases, Bitsec network is the new SOTA."

**GPT-5 gets <10%.** We were comparing ourselves against a baseline that itself barely works. Our 0% is not a failure of architecture — it's the expected starting point.

---

## What the Official Scoring Actually Does

### Per-Codebase, Per-Run
```
Codebase X has N expected high/critical vulns
Each run must find ALL N to PASS
3 runs per codebase
Codebase passes if ≥2/3 runs pass
Score = passed_codebases / total_codebases (0.0 or 1.0 per codebase)
```

### Multiple Validators
- 3 validators run independently
- Each validator runs the agent 3 times per codebase
- Top 3 validator scores averaged for final platform score
- Tie-breaker: confirmed vulnerability count

### The Example from Docs
| Codebase | Vulns | Run1 | Run2 | Run3 | Result |
|----------|-------|------|------|------|--------|
| Codebase 1 | 2 | 2/2 ✓ | 1/2 ✗ | 2/2 ✓ | PASS |
| Codebase 2 | 3 | 2/3 ✗ | 2/3 ✗ | 2/3 ✗ | FAIL |
| Codebase 3 | 4 | 0/4 ✗ | 0/4 ✗ | 0/4 ✗ | FAIL |
| Codebase 4 | 4 | 0/4 ✗ | 0/4 ✗ | 0/4 ✗ | FAIL |

Score: 2/4 = 0.50 (only 2 of 4 codebases pass)

---

## What We Got Right (Accidentally)

### 1. Our Agent Format is Correct
- `agent_main()` with correct signature
- Returns `{"vulnerabilities": [...]}` format
- Uses inference proxy correctly
- Will pass the screener (code check, format check)

### 2. We Identified the Right Problems
- Content fallback for non-tool-call reports ✓
- Token budget starvation ✓
- response_format issue ✓
- Architecture mapping helps ✓

### 3. We Understand the Hard Part
- Business logic bugs vs implementation bugs ✓
- Cross-contract vulnerabilities ✓
- Specificity of findings ✓

---

## What We Were Actually Doing Wrong

### Wrong 1: Comparing Against the Baseline
We thought "GPT-5 baseline found 87 vulns on Superposition" meant the baseline was good. But:
- The baseline is GPT-5 (a strong model)
- The baseline also scores 0% on Superposition against the curated ground truth
- Finding vulns ≠ finding THE SPECIFIC vulns the benchmark expects

### Wrong 2: Optimizing for Total Findings
We counted "104 vulnerabilities found" as success. But:
- Finding 104 random vulns ≠ finding 2 specific vulns
- The scorer only cares about the expected vulns
- Extra findings are wasted computation

### Wrong 3: Single-Pass Analysis
We analyze each file once with 3 turns. But:
- The winning approach likely involves multiple analysis passes
- First pass: understand architecture
- Second pass: trace specific risk areas
- Third pass: deep-dive on high-risk interactions

### Wrong 4: Not Using the Available Tools
The official docs mention:
- "Agent coordination libraries available on request"
- "Tool use is now supported"
- "Reasoning models are supported"
- "Add static analysis outputs for potential analysis"

We haven't explored any of these.

### Wrong 5: Not Enough Context Window
Our agent reads 8000 chars per file. But:
- Some Solidity files are 500+ lines
- Cross-file vulnerabilities require seeing multiple files together
- The model needs MORE context, not less

---

## What the Winning Approach Probably Looks Like

Based on the docs and research:

### 1. Multi-Phase Analysis
```
Phase 1: Map the entire project (all files, relationships)
Phase 2: For each high-risk area, do deep analysis
Phase 3: Cross-reference findings across files
Phase 4: Verify findings against ground truth patterns
```

### 2. Large Context Windows
- Read ENTIRE files, not truncated versions
- Combine related files in single prompts
- Use the full 30-minute timeout wisely

### 3. Reasoning Models
- Use models that show their thinking
- Chain-of-thought for understanding business logic
- Step-by-step analysis of code paths

### 4. Static Analysis Integration
- Run Slither/Mythril first to identify common patterns
- Feed static analysis results as context to the LLM
- LLM focuses on what static analysis misses

### 5. Iterative Refinement
- First pass: broad scan
- Second pass: targeted deep-dive based on first pass results
- Third pass: verify and refine findings

---

## Realistic Expectations

| Metric | Current | Realistic Target |
|--------|---------|-----------------|
| Our DR on Superposition | 0% | 10-30% (find at least 1 of 2) |
| GPT-5 SOTA | <10% | — |
| Winning agent | 83.3% | — |
| Gap to close | 0% → 83% | Massive but not impossible |

The winning agent at 83.3% likely uses:
- A more capable model (GPT-4o/Claude class)
- Multi-phase analysis
- Large context windows
- Possibly fine-tuned for this specific task
- Static analysis pre-processing

---

## What We Should Do Next

### Immediate: Submit What We Have
- Format is correct
- Agent runs in sandbox
- Gets real validator feedback
- Learn from actual scoring results

### Then: Build the Multi-Phase Agent
1. Architecture mapping pass (already built)
2. Large-context file reading (not truncated)
3. Targeted deep-dive on high-risk areas
4. Cross-file vulnerability detection

### Finally: Integrate Static Analysis
- Run Slither on the codebase first
- Feed Slither output as context
- LLM focuses on business logic, not pattern matching

---

## Key Quote from Official Docs

> "Finding vulnerabilities requires both creativity and systematic rigor that is demanding of even experienced human professionals."

This is not a coding competition. It's a security audit competition. The agent needs to think like a human auditor, not a pattern matcher.
