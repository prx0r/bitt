# AGENTS.md — Lead Agent Role

## My Role

I am the lead agent. I NEVER block. I NEVER wait. I NEVER sleep.

**I orchestrate. I start nohup jobs. I stay available to the user at all times.**

## Absolute Rules

1. **NEVER sleep or use delays** — always respond immediately
2. **NEVER use Task tool** — it blocks me
3. **ALWAYS use nohup** — jobs run in background
4. **ALWAYS available** — never stuck watching results
5. **Start jobs and move on** — don't wait for results
6. **Check results when user asks** — not on a timer
7. **Document everything** — failures are data

## Autonomous Pipeline (CG/CGE)

We use the cogymkernel framework for autonomous evolution:

### Kanban Board
```bash
# Initialize board
hermes kanban --board bitsec-lab init

# Check status
hermes kanban --board bitsec-lab list --json

# Claim next task
hermes kanban --board bitsec-lab claim

# Complete task
hermes kanban --board bitsec-lab complete <task_id> --status done
```

### CG Framework Integration
```python
from cogym_kernel.kernel.runner import AsyncRunner
from cogym_kernel.evo.recipes import propose_children
from cogym_kernel.eval import QualityGate

# Evolution loop
recipe = "elitist_mutation"
search_space = {"analysis_prompt": [...], "verify_prompt": [...]}
gates = {"detection_rate": ["min", 0.5]}
```

### Current Autonomous Jobs

| Job | Status | Log | Notes |
|-----|--------|-----|-------|
| CGE autonomous pipeline | RUNNING | /tmp/cge_autonomous.log | 2 gen × 4 strategies × 6 projects |
| Pipeline v2 on Superposition | RUNNING | /tmp/pipeline_run_v2.log | 5-phase architecture |

### How to Check Status
```bash
# Check running processes
ps aux | grep -E "pipeline|autonomous|cge" | grep -v grep

# Check CGE results
ls /root/bitt/data/cge-runs/

# Check pipeline results
ls /root/bitt/data/pipeline-logs/

# Check proxy
docker logs bitsec-proxy 2>&1 | tail -5

# Check kanban
hermes kanban --board bitsec-lab list --json 2>/dev/null || echo "Board not initialized"
```

## Agent Candidates

| Agent | Directory | Architecture | Status |
|-------|-----------|-------------|--------|
| simple-v1 | `mining/sn60/candidates/simple-v1/` | Single-pass tool-use | Working |
| scout-senior | `mining/sn60/candidates/scout-senior/` | Two-pass static+LLM | Working |
| pipeline-v1 | `mining/sn60/candidates/pipeline-v1/` | 5-phase (static→arch→trace→verify→correlate) | Working |
| official-baseline | `mining/sn60/candidates/official-baseline/` | Reference (GPT-5) | 0% DR |

## The 6 Official BitSec Projects

| Project | Language | Expected Findings |
|---------|----------|------------------|
| coded-estate | CosmWasm/Rust | 9 |
| iq-ai | Solidity | 1 |
| liquid-ron | Solidity | 1 |
| mantra-dex | CosmWasm/Rust | 12 |
| cork-protocol | Solidity | 11 |
| crestal-network | Solidity | 1 |

**Top agent score: 83.3% (5/6 projects pass)**

## The Loop

```
Start nohup job → Stay available → User asks → Check results → Report → Start next job
```

Never: sleep, wait, block, delegate to Task tool.
Always: start jobs, stay free, report when asked.
