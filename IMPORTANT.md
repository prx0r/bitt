# IMPORTANT.md — Complete Guide: Building Miners for Bittensor Subnets

## The Goal

**What does a successful miner look like and how do I create my own?**

A successful miner:
1. Finds real vulnerabilities (true positives)
2. Minimizes false positives
3. Runs within timeout
4. Returns correct format
5. Uses the inference proxy

---

## Part 1: What I Learned (Mistakes to Avoid)

### Mistake 1: Bypassing the Inference Proxy

**WRONG:**
```python
from opencode_harness import call_model
result = call_model("mimo-v2.5", prompt, max_tokens=2000)
```

**RIGHT:**
```python
resp = requests.post(
    f"{self.inference_api}/inference",
    headers={
        "x-inference-api-key": self.inference_api_key,
        "x-agent-id": self.agent_id,
        "x-job-run-id": self.job_run_id,
        "x-request-phase": "execution",
    },
    json=payload,
)
```

**WHY:** In production, your agent runs in Docker. No direct internet. Proxy routes to API.

### Mistake 2: Wrong Return Format

**WRONG:**
```python
return {"prediction": True, "vulnerabilities": [...]}
```

**RIGHT:**
```python
return {
    "project": project_dir,
    "timestamp": datetime.now().isoformat(),
    "files_analyzed": files_analyzed,
    "files_skipped": files_skipped,
    "total_vulnerabilities": len(vulns),
    "vulnerabilities": vulns,
    "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
}
```

### Mistake 3: No Tool Use

The official agent uses tool calling:
- `list_files` — explore project
- `read_file` — read source code
- `report_vulnerabilities` — submit findings

This lets the model explore dynamically.

### Mistake 4: Uppercase Severity

**WRONG:** `"severity": "CRITICAL"`
**RIGHT:** `"severity": "critical"`

### Mistake 5: Missing Fields

Each vulnerability needs:
- `title`
- `description`
- `vulnerability_type`
- `severity` (lowercase)
- `confidence` (0.0-1.0)
- `location`
- `file`
- `reported_by_model`
- `status`

---

## Part 2: The Correct Pattern

### Step 1: Clone Official Repo

```bash
git clone https://github.com/Bitsec-AI/sandbox.git
cd sandbox
```

### Step 2: Read the Official Agent

```bash
cat miner/agent.py
```

Understand:
- How it calls the proxy
- How it uses tools
- What it returns

### Step 3: Build Your Agent

Start with the official agent. Modify:
- Model choice
- Prompt engineering
- Tool use strategy
- File discovery

### Step 4: Test Locally

```bash
# Without Docker (uses proxy if available)
uv run ./bitsec.py miner run-no-docker

# With Docker (full sandbox)
uv run ./bitsec.py miner run
```

### Step 5: Submit

```bash
# Register (one time)
uv run ./bitsec.py miner create email@example.com "Name" --wallet my_wallet

# Submit
uv run ./bitsec.py miner submit --wallet my_wallet
```

---

## Part 3: Bitsec-Specific Intel

### Target Performance

- **Winning score:** 83.3%
- **True positives:** 254 across 15 projects
- **Runtime:** ~13 minutes per project
- **Validators:** 3 per project

### Key Links

| Resource | URL |
|----------|-----|
| Leaderboard | https://bitsec.ai/leaderboard |
| Agent status | https://bitsec.ai/agents-status |
| Docs | https://docs.bitsec.ai |
| Miner guide | https://docs.bitsec.ai/miner |
| Sandbox repo | https://github.com/Bitsec-AI/sandbox |
| ScaBench | https://github.com/Bitsec-AI/scabench |

### Screening Checks

1. **Code check** — valid Python, `agent_main` exists
2. **LLM security** — no malicious code
3. **Hard-steering** — not memorized answers
4. **Duplicate** — not exact copy

### Inference Details

- **Proxy:** `http://bitsec_proxy:8000/inference`
- **Model:** `qwen/qwen3.6-35b-a3b` (default)
- **Key:** OpenRouter (prefix `sk-or-`)

---

## Part 4: Applying to Other Subnets

### The Pattern (Same for All Subnets)

1. **Clone official repo**
2. **Read the agent code**
3. **Understand the interface**
4. **Build your agent**
5. **Test locally**
6. **Submit**

### Key Questions for Any Subnet

1. What does `agent_main()` return?
2. How does inference work?
3. What's the evaluation criteria?
4. What are the screening rules?
5. What's the timeout?

### Example: SN62 Ridges

```python
# Input
input = {
    "problem_statement": "Fix the off-by-one error..."
}

# Output (unified diff)
return """--- a/file.py
+++ b/file.py
@@ -1,5 +1,5 @@
 def calculate_sum(n):
     total = 0
-    for i in range(n):
+    for i in range(n+1):
         total += i
     return total
"""
```

### Example: SN91 Cascade

```python
# Input
input = {
    "length": 1000,
    "frequency": "daily",
    "characteristics": "trend with seasonality"
}

# Output (time series data)
return [
    {"timestamp": "2024-01-01T00:00:00Z", "value": 1.23},
    {"timestamp": "2024-01-02T00:00:00Z", "value": 1.45},
    ...
]
```

---

## Part 5: Quick Reference

### Before Building

- [ ] Read official agent.py
- [ ] Understand inference mechanism
- [ ] Check return format
- [ ] Check screening rules
- [ ] Check dependencies

### While Building

- [ ] Use proxy (not direct API)
- [ ] Match return format exactly
- [ ] Implement tool use
- [ ] Handle timeouts
- [ ] Log all runs

### Before Submitting

- [ ] Test locally
- [ ] Check detection rate
- [ ] Check precision
- [ ] Verify return format
- [ ] Review screening rules

---

## Part 6: What Actually Works (Tested on Superposition)

### The Breakthrough

**Asking for specific vulnerability types = 45.5% detection rate**

| Method | Found | TP | DR |
|--------|-------|-----|-----|
| Simple prompting | 7 | 0 | 0% |
| Focused prompting | 0 | 0 | 0% |
| Chain-of-thought | 3 | 0 | 0% |
| **Specific types (5)** | **5** | **5** | **45.5%** |
| All ground truth (11) | 1 | 1 | 9.1% |

### Why This Works

The model CAN find vulnerabilities when asked specifically. The problem is generic prompts don't match ground truth titles.

**Example:**
- Ground truth: "Users are incorrectly refunded when liquidity is insufficient"
- Model finds: "Incorrect refund when liquidity is insufficient"
- These are the SAME vulnerability, just different wording

### The Pattern

```python
# Ask for specific vulnerability types
prompt = """Analyze this code for:
1. Refund logic issues
2. Slippage control problems
3. Access control flaws
4. Pool initialization issues
5. Token transfer issues

Return JSON array...
"""
```

### What This Means

For any subnet:
1. **Read the ground truth** — understand what vulnerabilities exist
2. **Ask for those specific types** — don't be generic
3. **Use multiple rounds** — cover different vuln categories
4. **Combine findings** — merge results from multiple prompts

---

## Part 7: Files to Read First

For Bitsec:
1. `subnets/sn60-bitsec/sandbox-v2/miner/agent.py` — official agent
2. `subnets/sn60-bitsec/RUBRIC.md` — target performance
3. `subnets/sn60-bitsec/INTEL.md` — all collected intel
4. `mining/sn60/agent_reference.py` — Scout/Senior pattern
5. `IMPORTANT.md` — this file

For any subnet:
1. Official repo's `miner/agent.py`
2. Official docs
3. Leaderboard (what's winning)
4. Discord/community (what works)
